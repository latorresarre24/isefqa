# Part of Odoo. See LICENSE file for full copyright and licensing details.
from __future__ import division

import base64
import logging
from io import BytesIO

from lxml import etree, objectify

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round, float_is_zero
from odoo.tools.xml_utils import _check_with_xsd

_logger = logging.getLogger(__name__)


CFDI_TEMPLATE_33 = 'l10n_mx_edi_pos.cfdiv33_pos'
CFDI_TEMPLATE_40 = 'l10n_mx_edi_pos.cfdiv40_pos'
CFDI_XSLT_CADENA = 'l10n_mx_edi/data/3.3/cadenaoriginal.xslt'
CFDI_XSLT_CADENA_40 = 'l10n_mx_edi_40/data/4.0/cadenaoriginal_4_0.xslt'
CFDI_SAT_QR_STATE = {
    'No Encontrado': 'not_found',
    'Cancelado': 'cancelled',
    'Vigente': 'valid',
}


def create_list_html(array):
    # Review if could be removed
    """Convert an array of string to a html list.
    :param array: A list of strings
    :type array: list
    :return: an empty string if not array, an html list otherwise.
    :rtype: str
    """
    if not array:
        return ''
    msg = ''
    for item in array:
        msg += '<li>' + item + '</li>'
    return '<ul>' + msg + '</ul>'


class PosSession(models.Model):
    _name = 'pos.session'
    _inherit = ['pos.session', 'mail.thread']

    l10n_mx_edi_pac_status = fields.Selection(
        selection=[
            ('retry', 'Retry'),
            ('signed', 'Signed'),
            ('to_cancel', 'To cancel'),
            ('cancelled', 'Cancelled')
        ],
        string='PAC status',
        help='Refers to the status of the invoice inside the PAC.',
        readonly=True,
        copy=False)
    l10n_mx_edi_sat_status = fields.Selection(
        selection=[
            ('none', 'State not defined'),
            ('undefined', 'Not Synced Yet'),
            ('not_found', 'Not Found'),
            ('cancelled', 'Cancelled'),
            ('valid', 'Valid'),
        ],
        string='SAT status',
        help='Refers to the status of the invoice inside the SAT system.',
        readonly=True,
        copy=False,
        required=True,
        tracking=True,
        default='undefined')

    def l10n_mx_edi_update_pac_status(self):
        """Synchronize both systems: Odoo & PAC if the invoices need to be
        signed or cancelled.
        """
        for record in self:
            if record.l10n_mx_edi_pac_status == 'to_cancel':
                record.l10n_mx_edi_cancel()
            elif record.l10n_mx_edi_pac_status in ['retry', 'cancelled']:
                record._l10n_mx_edi_retry()

    @api.model
    def _l10n_mx_edi_check_configuration(self):
        """Check PAC Credentials adpted from l10n_mx_edi / account.move is not possible to use that method because it
           uses some exclusive """
        errors = []
        # == Check the certificate ==
        certificate = self.company_id.l10n_mx_edi_certificate_ids.sudo().get_valid_certificate()
        if not certificate:
            errors.append(_('No valid certificate found'))

        # == Check the credentials to call the PAC web-service ==
        if self.company_id.l10n_mx_edi_pac:
            pac_test_env = self.company_id.sudo().l10n_mx_edi_pac_test_env
            pac_password = self.company_id.sudo().l10n_mx_edi_pac_password
            if not pac_test_env and not pac_password:
                errors.append(_('No PAC credentials specified.'))
        else:
            errors.append(_('No PAC specified.'))
        return errors

    def _l10n_mx_edi_retry(self):
        """Generate and sign CFDI with version 3.3, just for the next cases:
        1.- The order was generated without customer, therefore without invoice
        2.- The order was generated with customer, but without invoice
        3.- The order is a refund and do not have invoice related"""
        self.ensure_one()
        errors = self._l10n_mx_edi_check_configuration()
        if errors:
            self.l10n_mx_edi_pac_status = 'retry'
            body_msg = _('Wrong PAC configuration, CFDI sign skipped')
            self.message_post(body=body_msg + create_list_html(errors))

        orders = self.order_ids.filtered(lambda r: r.state != 'invoiced' and not r.l10n_mx_edi_cfdi_generated)
        # skip orders in 0
        skip_orders = orders.filtered(lambda o: not o.lines)
        for order in orders:
            related = order._get_order_related()
            # Refund related in 0 or not refund or partial refund
            if not related or not related.lines or abs(order.amount_total) != abs(related.amount_total):
                continue
            # Refund related to a order not signed
            if (order.amount_total < 0 and not related.l10n_mx_edi_uuid) or (
                    # Full reversal
                    order.amount_total > 0 and related.session_id.state == 'closed'):
                skip_orders |= order
        orders -= skip_orders
        if skip_orders:
            olist = ' '.join(['<li>%s</li>' % (o) for o in skip_orders.mapped('pos_reference')])
            msg_body = _("""The following orders were skipped because it's not
                         necessary to sign them:
                         <br><br><ul>%s</ul>""") % olist
            self.message_post(body=msg_body)
        partners = orders.mapped('partner_id').mapped('commercial_partner_id').filtered(lambda r: r.vat)
        lambda_functions = (
            lambda r: r.amount_total > 0 and  # Order with partner
            r.partner_id and r.partner_id.commercial_partner_id.id
            not in partners.ids,
            lambda r: r.amount_total > 0 and not r.partner_id,  # Order without Partner
            lambda r: r.amount_total < 0 and  # Refund with partner
            r.partner_id and (r.partner_id.commercial_partner_id.id not in partners.ids or not r.invoice_id),
            lambda r: r.amount_total < 0 and not r.partner_id)  # Refund without Partner
        signed = []
        self.l10n_mx_edi_pac_status = 'retry'
        attachment = self.env['ir.attachment']
        for func in lambda_functions:
            order_filter = orders.filtered(func)
            if not order_filter:
                continue
            cfdi_values = order_filter._l10n_mx_edi_create_cfdi()
            error = cfdi_values.pop('error', None)
            cfdi = cfdi_values.pop('cfdi', None)
            if error:
                self.message_post(body=error)
                signed.append(False)
                continue

            filename = order_filter.get_file_name()
            ctx = self.env.context.copy()
            ctx.pop('default_type', False)
            attachment_id = attachment.with_context(**ctx).create({
                'name': '%s.xml' % filename,
                'res_id': self.id,
                'res_model': self._name,
                'datas': base64.encodebytes(cfdi),
                'description': _('Mexican PoS'),
                'mimetype': 'application/xml',
                'type': 'binary',
            })
            self.message_post(
                body=_('CFDI document generated (may be not signed)'),
                attachment_ids=[attachment_id.id])

            cfdi_values = self._l10n_mx_edi_call_service('sign', cfdi)
            if cfdi_values:
                if not cfdi_values.get('errors'):
                    if cfdi_values['cfdi_encoding'] == 'base64':
                        cfdi_values['cfdi_signed'] = base64.decodebytes(cfdi_values['cfdi_signed'])
                    self._l10n_mx_edi_post_sign_process(cfdi_values, order_filter)
                    signed.append(bool(cfdi_values.get('cfdi_signed', False)))
                else:
                    self.message_post(body=cfdi_values.get('errors'))
                    signed.append(False)
                    continue
            orders = orders - order_filter
        if signed and all(signed):
            self.l10n_mx_edi_pac_status = 'signed'

    def _l10n_mx_edi_call_service(self, service_type, cfdi):
        """Call the right method according to the pac_name,
        it's info returned by the '_l10n_mx_edi_%s_info' % pac_name'
        method and the service_type passed as parameter.
        :param service_type: sign or cancel
        :type service_type: str
        :param cfdi: fiscal document
        :type cfdi: etree
        :return: the Result of the service called
        :rtype: dict
        """
        self.ensure_one()
        edi = self.env['account.edi.format']
        company_id = self.config_id.company_id
        pac_name = company_id.l10n_mx_edi_pac
        if not pac_name:
            return False
        # Get the informations about the pac
        credentials = getattr(edi, '_l10n_mx_edi_get_%s_credentials' % pac_name)(self.move_id)
        if credentials.get('errors'):
            self.message_post(body=_("PAC authentication error: %s") % credentials['errors'])
            return False
        return getattr(edi, '_l10n_mx_edi_%s_%s_invoice' % (pac_name, service_type))(self.move_id, credentials, cfdi)

    def l10n_mx_edi_log_error(self, message):
        self.message_post(body=_('Error during the process: %s') % message)

    def _l10n_mx_edi_post_sign_process(self, cfdi_values, order_ids):
        """Post process the results of the sign service.
        :param cfdi_values: info of xml signed
        :type cfdi_values: dict
        :param order_ids: orders use to generate cfdi
        :type order_ids: pos.order
        """
        self.ensure_one()
        post_msg = []
        attach = []
        xml_signed = cfdi_values.get('cfdi_signed', '')
        msg = cfdi_values.get('errors', '')
        filename = order_ids.get_file_name()
        if xml_signed:
            body_msg = _('The sign service has been called with success to %s') % filename
            # attach cfdi
            ctx = self.env.context.copy()
            ctx.pop('default_type', False)
            attachment_id = self.l10n_mx_edi_retrieve_last_attachment('%s.xml' % filename)
            attachment_id.write({
                'datas': base64.encodebytes(xml_signed),
                'mimetype': 'application/xml',
                'type': 'binary',
            })
            attach.extend([attachment_id.id])
            # Generate and attach pdf
            report = self.env.ref('l10n_mx_edi_pos.l10n_mx_edi_report_session')
            xml = objectify.fromstring(xml_signed)
            data = self.move_id._l10n_mx_edi_decode_cfdi(xml_signed)
            data.update({'cfdi': xml, 'company_id': self.company_id})
            pdf, ext = report._render_qweb_pdf(self.ids, data)
            attachment_id = self.env[
                'ir.attachment'].with_context(**ctx).create({
                    'name': '%s.%s' % (filename, ext),
                    'res_id': self.id,
                    'res_model': self._name,
                    'datas': base64.b64encode(pdf),
                    'description': 'Printed representation of the CFDI',
                })
            attach.extend([attachment_id.id])
            uuid = self.l10n_mx_edi_get_tfd_etree(xml).get('UUID', '')
            order_ids.write({
                'l10n_mx_edi_cfdi_generated': True, 'l10n_mx_edi_uuid': uuid})
        else:
            body_msg = _('The sign service requested failed to %s') % filename
        if msg:
            post_msg.extend([_('Reason: %s') % msg])
        self.message_post(body=body_msg + create_list_html(post_msg), attachment_ids=attach)

    def _l10n_mx_edi_post_cancel_process(self, cfdi_values, order_ids, attach):
        """Post process the results of the cancel service.
        :param cfdi_values: info of xml signed
        :type cfdi_values: dict
        :param order_ids: orders use to generate cfdi
        :type order_ids: pos.order
        :param attach: file attachment in invoice
        :type attach: ir.attachment
        """

        self.ensure_one()
        cancelled = cfdi_values.get('cancelled', '')
        code = cfdi_values.get('code', '')
        msg = cfdi_values.get('msg', '')
        filename = cfdi_values.get('filename', '')
        if cancelled:
            body_msg = _('The cancel service has been called with success to %s') % filename
            order_ids.write({'l10n_mx_edi_cfdi_generated': False})
            attach.name = 'cancelled_%s' % '_'.join(filename.split('_')[-2:])
        else:
            body_msg = _('The cancel service requested failed to %s') % filename
        post_msg = []
        if code:
            post_msg.extend([_('Code: ') + str(code)])
        if msg:
            post_msg.extend([_('Message: ') + msg])
        self.message_post(body=body_msg + create_list_html(post_msg))

    def action_pos_session_close(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        orders = self.order_ids.filtered(
            lambda r: r.state != 'invoiced' and not r.l10n_mx_edi_cfdi_generated and r.partner_id and r.partner_id.vat)
        orders.action_create_invoice()
        orders.action_validate_invoice()
        res = super().action_pos_session_close(
            balancing_account=balancing_account, amount_to_balance=amount_to_balance,
            bank_payment_method_diffs=bank_payment_method_diffs)
        self._l10n_mx_edi_retry()
        return res

    def l10n_mx_edi_cancel(self):
        """If the session have XML documents, try send to cancel in SAT system
        """
        att_obj = self.env['ir.attachment']
        for record in self:
            attach_xml_ids = att_obj.search([
                ('name', 'ilike', '%s%%.xml' % record.name.replace('/', '_')),
                ('res_model', '=', record._name),
                ('res_id', '=', record.id),
            ])
            cancel = []
            self.l10n_mx_edi_pac_status = 'to_cancel'
            for att in attach_xml_ids.filtered('datas'):
                cfdi_data = base64.decodebytes(att.with_context(bin_size=False).datas)
                cfdi_values = self._l10n_mx_edi_call_service('cancel', cfdi_data)
                if not cfdi_values:
                    cancel.append([False])
                    continue
                orders = self.order_ids.filtered(lambda r: not r.account_move and r.l10n_mx_edi_cfdi_generated)
                func = (lambda r: r.partner_id) if _('with_partner') in att.name else (lambda r: not r.partner_id)
                order_ids = orders.filtered(func)
                cfdi_values.update({'filename': att.name})
                self._l10n_mx_edi_post_cancel_process(cfdi_values, order_ids, att)
                cancel.append(cfdi_values.get('cancelled', False))
            if all(cancel):
                self.l10n_mx_edi_pac_status = 'cancelled'

    @api.model
    def l10n_mx_edi_retrieve_attachments(self, filename):
        """Retrieve all the cfdi attachments generated for this session
        :return: An ir.attachment recordset
        :rtype: ir.attachment()
        """
        self.ensure_one()
        domain = [
            ('res_id', '=', self.id),
            ('res_model', '=', self._name),
            ('name', '=', filename)]
        return self.env['ir.attachment'].search(domain)

    @api.model
    def l10n_mx_edi_retrieve_last_attachment(self, filename):
        attachment_ids = self.l10n_mx_edi_retrieve_attachments(filename)
        return attachment_ids[0] if attachment_ids else None

    def l10n_mx_edi_amount_to_text(self, amount_total):
        """Method to transform a float amount to text words
        E.g. 100 - ONE HUNDRED
        :returns: Amount transformed to words mexican format for invoices
        :rtype: str
        """
        self.ensure_one()
        currency = self.currency_id.name.upper()
        # M.N. = Moneda Nacional (National Currency)
        # M.E. = Moneda Extranjera (Foreign Currency)
        currency_type = 'M.N' if currency == 'MXN' else 'M.E.'
        # Split integer and decimal part
        amount_i, amount_d = divmod(amount_total, 1)
        amount_d = round(amount_d, 2)
        amount_d = int(round(amount_d * 100, 2))
        words = self.currency_id.with_context(
            lang=self.company_id.partner_id.lang or 'es_ES').amount_to_text(
                amount_i).upper()
        invoice_words = '%(words)s %(amount_d)02d/100 %(curr_t)s' % dict(
            words=words, amount_d=amount_d, curr_t=currency_type)
        return invoice_words

    def l10n_mx_edi_update_sat_status(self):
        """Synchronize both systems: Odoo & SAT to make sure the invoice is valid."""
        att_obj = self.env['ir.attachment']
        edi_format = self.env['account.edi.format']
        for record in self:
            attach_xml_ids = att_obj.search([
                ('name', 'ilike', '%s%%.xml' % record.name.replace('/', '_')),
                ('res_model', '=', record._name),
                ('res_id', '=', record.id),
            ])
            for att in attach_xml_ids.filtered('datas'):
                xml = objectify.fromstring(base64.b64decode(att.datas))
                supplier_rfc = xml.Emisor.get('Rfc')
                customer_rfc = xml.Receptor.get('Rfc')
                total = xml.get('Total')
                uuid = self.l10n_mx_edi_get_tfd_etree(xml).get('UUID', '')
                status = edi_format._l10n_mx_edi_get_sat_status(supplier_rfc, customer_rfc, total, uuid)
                record.l10n_mx_edi_sat_status = CFDI_SAT_QR_STATE.get(status)

    @api.model
    def l10n_mx_edi_get_tfd_etree(self, cfdi):
        """Get the TimbreFiscalDigital node from the cfdi."""
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = 'tfd:TimbreFiscalDigital[1]'
        namespace = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node[0] if node else None


class PosOrder(models.Model):
    _inherit = 'pos.order'

    l10n_mx_edi_cfdi_generated = fields.Boolean(
        'XML Generated', copy=False,
        help='Indicate if this order was consider in the session XML')
    l10n_mx_edi_uuid = fields.Char(
        'Fiscal Folio', copy=False, index=True,
        help='Folio in electronic document, returned by SAT.')
    l10n_mx_edi_usage = fields.Selection(
        selection=lambda self: self._get_usage_selection(),
        string='Usage',
        help='This usage will be used instead of the default one for invoices.',
    )

    def _get_usage_selection(self):
        return self.env['res.partner']._get_usage_selection()

    @api.model
    def ui_get_usage_selection(self):
        """Used to be exposed to the Point of Sale UI.
        We kept the old `_get_usage_selection` to prevent legacy code to
        break the Point of Sale UI.
        """
        return self._get_usage_selection()

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        if 'l10n_mx_edi_usage' in ui_order and ui_order["l10n_mx_edi_usage"]:
            res['l10n_mx_edi_usage'] = ui_order['l10n_mx_edi_usage'].get('id')
        return res

    def _prepare_invoice_vals(self):
        res = super()._prepare_invoice_vals()
        if self.l10n_mx_edi_usage:
            res["l10n_mx_edi_usage"] = self.l10n_mx_edi_usage
        return res

    def _get_order_related(self):
        self.ensure_one()
        return self.search([
            ('pos_reference', '=', self.pos_reference), ('id', '!=', self.id),
            ('partner_id', '=', self.partner_id.id)], limit=1)

    def get_file_name(self):
        """Return the file name, with a consecutive to duplicated names.
        Params:
            partner: Receive True if the file to generate contain the records
            that have partner reference, to set in the fail the label
            'with_partner'
            inc: Indicate if must be add the consecutive"""
        partner = self.mapped('partner_id')
        doc_type = self.filtered(lambda r: r.amount_total < 0)
        type_rec = _('with_partner') if partner else _('wo_partner')
        egre = '' if not doc_type else _('_refund')
        session = self.mapped('session_id')
        session_name = session.name.replace('/', '_')
        fname = "%s_%s%s" % (session_name, type_rec, egre)

        count = self.env['ir.attachment'].search_count([
            ('name', '=', fname),
            ('res_model', '=', session._name),
            ('res_id', '=', session.id),
        ])
        if count > 0:
            fname = "%s_%s%s_%s" % (
                session_name, type_rec, egre, count + 1)
        return fname

    def _get_subtotal_wo_discount(self, precision_digits, line):
        return float(line.price_subtotal / (1 - abs(line.discount/100)) if
                     line.discount != 100 else abs(line.price_unit * line.qty))

    def _get_discount(self, precision_digits, line):
        return float(self._get_subtotal_wo_discount(precision_digits, line) -
                     abs(line.price_subtotal)) if line.discount else False

    def _l10n_mx_edi_create_cfdi_values(self):
        """Generating the base dict with data needed to generate the electronic
        document
        :return: Base data to generate electronic document
        :rtype: dict
        """
        def _format_float_cfdi(amount, precision):
            if amount is None or amount is False:
                return None
            # Avoid things like -0.0, see: https://stackoverflow.com/a/11010869
            return '%.*f' % (precision, amount if not float_is_zero(amount, precision_digits=precision) else 0.0)

        session = self.mapped('session_id')
        invoice_obj = self.env['account.move']
        currency_precision = session.currency_id.l10n_mx_edi_decimal_places
        company_id = session.config_id.company_id

        invoice = {
            'record': self,
            'invoice': invoice_obj,
            'currency': session.currency_id.name,
            'supplier': company_id,
            'folio': session.name,
            'serie': 'NA',
            'format_float': _format_float_cfdi,
            'currency_precision': currency_precision,
        }
        invoice['subtotal_wo_discount'] = _format_float_cfdi(sum([
            self._get_subtotal_wo_discount(currency_precision, line) for line in
            self.mapped('lines')]), currency_precision)
        invoice['amount_untaxed'] = abs(float_round(sum(
            [self._get_subtotal_wo_discount(currency_precision, p) for p in
             self.mapped('lines')]), 2))
        invoice['amount_discount'] = _format_float_cfdi(sum([
            float(self._get_discount(currency_precision, p)) for p in
            self.mapped('lines')]), currency_precision)

        invoice['tax_name'] = lambda t: {
            'ISR': '001', 'IVA': '002', 'IEPS': '003'}.get(t, False)
        invoice['taxes'] = self._l10n_mx_edi_create_taxes_cfdi_values()

        invoice['amount_total'] = abs(float_round(float(
            invoice['amount_untaxed']), 2) - round(float(
                invoice['amount_discount'] or 0), 2) + (round(
                    invoice['taxes']['total_transferred'] or 0, 2)) - (round(
                        invoice['taxes']['total_withhold'] or 0, 2)))
        invoice['document_type'] = 'I' if self.filtered(
            lambda r: r.amount_total > 0) else 'E'
        payment_ids = self.mapped('payment_ids').filtered(
            lambda st: st.amount > 0)

        # Get highest amount payment
        payments = payment_ids.read_group(
            [('id', 'in', payment_ids.ids)],
            ['amount'],
            'payment_method_id'
        )
        payments = sorted(payments, key=lambda i: i['amount'], reverse=True)
        payment_id = payments[0]['payment_method_id'][0] if payments else False
        invoice['payment_method'] = self.env['pos.payment.method'].browse(
            payment_id).l10n_mx_edi_payment_method_id.code if payment_id else '99'

        return invoice

    def get_cfdi_related(self):
        """To node CfdiRelacionados get documents related with that order
        Considered:
            - Order Refund
            - Order Cancelled"""
        cfdi_related = []
        refund = self.filtered(
            lambda a: a.amount_total < 0 and not a.l10n_mx_edi_uuid)
        relation_type = '04' if self[0].l10n_mx_edi_uuid else (
            '01' if refund else '')
        for order in refund:
            origin = self.search(
                [('pos_reference', '=', order.pos_reference),
                 ('id', '!=', order.id),
                 ('partner_id', '=', order.partner_id.id),
                 ('date_order', '<=', order.date_order)], limit=1)
            cfdi_related += [origin.l10n_mx_edi_uuid] if origin else ()
        cfdi_related += [i.l10n_mx_edi_uuid for i in self if i.l10n_mx_edi_uuid]
        if not cfdi_related:
            return {}
        return {
            'type': relation_type,
            'related': list(set(cfdi_related)),
            }

    def _l10n_mx_edi_create_cfdi(self):
        """Creates and returns a dictionary containing 'cfdi' if the cfdi is
        well created, 'error' otherwise."""
        if not self:
            return {}
        qweb = self.env['ir.qweb']
        invoice_obj = self.env['account.move']
        company = self.mapped('company_id')
        error_log = []
        pac_name = company.l10n_mx_edi_pac

        values = self._l10n_mx_edi_create_cfdi_values()

        # -Check certificate
        certificate = company.l10n_mx_edi_certificate_ids.sudo().get_valid_certificate()
        if not certificate:
            error_log.append(_('No valid certificate found'))

        # TODO: Check why this PAC check is not being performed in the three cases
        # -Check PAC
        if pac_name:
            pac_test_env = company.sudo().l10n_mx_edi_pac_test_env
            pac_password = company.sudo().l10n_mx_edi_pac_password
            if not pac_test_env and not pac_password:
                error_log.append(_('No PAC credentials specified.'))
        else:
            error_log.append(_('No PAC specified.'))

        if error_log:
            return {'error': _('Please check your configuration: ') +
                    create_list_html(error_log)}

        tz = invoice_obj._l10n_mx_edi_get_cfdi_partner_timezone(values['supplier'])
        values['certificate_number'] = certificate.serial_number
        values['certificate'] = certificate.sudo().get_data()[0].decode('utf-8')
        values['date'] = fields.datetime.now(tz).strftime('%Y-%m-%dT%H:%M:%S')

        template = CFDI_TEMPLATE_40
        xslt = CFDI_XSLT_CADENA_40
        attachment = self.sudo().env.ref('l10n_mx_edi.xsd_cached_cfdv40_xsd', False)
        if self.l10n_mx_edi_get_pac_version() == '3.3':
            template = CFDI_TEMPLATE_33
            xslt = CFDI_XSLT_CADENA
            attachment = self.sudo().env.ref('l10n_mx_edi.xsd_cached_cfdv33_xsd', False)
        cfdi = qweb._render(template, values=values)
        xsd_datas = base64.b64decode(attachment.datas) if attachment else b''
        # -Compute cadena
        tree = objectify.fromstring(cfdi)
        cadena_root = etree.parse(tools.file_open(xslt))
        cadena = str(etree.XSLT(cadena_root)(tree))
        tree.attrib['Sello'] = certificate.sudo().get_encrypted_cadena(cadena)

        # Check with xsd
        if xsd_datas:
            try:
                with BytesIO(xsd_datas) as xsd:
                    _check_with_xsd(tree, xsd)
            except (IOError, ValueError):
                _logger.info(_('The xsd file to validate the XML structure was not found'))
            except BaseException as e:
                return {'error': (_('The cfdi generated is not valid') + create_list_html(str(e).split('\\n')))}

        return {'cfdi': etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')}

    def _l10n_mx_edi_create_taxes_cfdi_values(self):
        """Create the taxes values to fill the CFDI template.
        """
        values = {
            'total_withhold': 0,
            'total_transferred': 0,
            'withholding': [],
            'transferred': [],
        }
        taxes = {}
        for line in self.mapped('lines').filtered('price_subtotal'):
            price = line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)
            tax_line = {tax['id']: tax for
                        tax in line.tax_ids_after_fiscal_position.compute_all(
                            price, line.order_id.pricelist_id.currency_id,
                            abs(line.qty), line.product_id, line.order_id.partner_id)['taxes']}
            for tax in line.tax_ids_after_fiscal_position.filtered(lambda r: r.l10n_mx_tax_type != 'Exento'):
                tax_dict = tax_line.get(tax.id, {})
                amount = abs(tax_dict.get('amount', tax.amount / 100 * line.price_subtotal))
                rate = round(abs(tax.amount), 2)
                base = float(amount) / float(rate) if \
                    tax.amount_type == 'fixed' else tax_dict.get('base', line.price_subtotal)
                tags = tax.invoice_repartition_line_ids.tag_ids
                tag = (tags and tags[0] and tags.name or tax.name).upper()
                tax_key = '%s%s' % (tag or 'NA', str(tax.amount))
                if tax_key not in taxes:
                    taxes.update({tax_key: {
                        'name': tag,
                        'amount': base * (rate if tax.amount_type == 'fixed' else rate / 100.0),
                        'rate': (rate if tax.amount_type == 'fixed' else rate / 100.0),
                        'type': tax.l10n_mx_tax_type,
                        'tax_amount': tax_dict.get('amount', tax.amount),
                        'base': base,
                    }})
                else:
                    taxes[tax_key].update({
                        'amount': taxes[tax_key]['amount'] + (
                            base * (rate if tax.amount_type == 'fixed' else rate / 100.0)),
                        'base': taxes[tax_key]['base'] + base,
                    })
                if tax.amount >= 0:
                    values['total_transferred'] += base * (rate if tax.amount_type == 'fixed' else rate / 100.0)
                else:
                    values['total_withhold'] += base * (rate if tax.amount_type == 'fixed' else rate / 100.0)
        values['transferred'] = [tax for tax in taxes.values() if tax['tax_amount'] >= 0]
        values['withholding'] = [tax for tax in taxes.values() if tax['tax_amount'] < 0]
        return values

    def action_create_invoice(self):
        """When is created a new register, verify that partner have VAT, and
        create automatically the invoice."""
        orders_to_invoice = self.filtered(lambda ord: ord.partner_id.vat and not ord.account_move)
        orders_to_invoice.write({'to_invoice': True})
        orders_to_invoice._generate_pos_order_invoice()

    def action_validate_invoice(self):
        """Validate the invoice after of opened."""
        self.mapped('account_move').filtered(lambda inv: inv.state == 'draft').action_post()

    def action_pos_order_paid(self):
        """Create Invoice if have partner with VAT"""
        res = super().action_pos_order_paid()
        self.action_create_invoice()
        self.filtered(lambda r: r.account_move.state == 'draft').action_validate_invoice()
        return res

    def _get_main_order(self):
        """Used to get the main order that generated the return that you want
        to generate the invoice
        :return: The possible order that generated the return
        :rtype: pos.order()
        """
        self.ensure_one()
        return self.search([
            ('partner_id', '=', self.partner_id.id),
            ('sale_journal', '=', self.sale_journal.id),
            ('account_move', 'not in', [False, self.account_move.id]),
            ('pos_reference', '=', self.pos_reference),
        ], order='date_order DESC', limit=1)

    def prepare_credit_note(self):
        """Prepare the main values needed to create the credit note
        :return: The values of the new invoice
        :rtype: dict
        """
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Please provide a partner for the sale.'))
        return {
            'name': self.name,
            'origin': self.name,
            'account_id': self.partner_id.property_account_receivable_id.id,
            'journal_id': self.sale_journal.id or None,
            'type': 'out_refund',
            'reference': self.name,
            'partner_id': self.partner_id.id,
            'comment': self.note or '',
            'currency_id': self.pricelist_id.currency_id.id,
            'company_id': self.company_id.id,
        }

    def add_payment_for_credit_note(self):
        """Generate a payment for a credit note
        :return: boolean
        :rtype: dict
        TODO - Could be removed the method?
        """
        self.ensure_one()
        main_order = self._get_main_order()
        if main_order.account_move and main_order.account_move.state != 'posted':
            return self.account_move.action_post()
        invoice = main_order.account_move
        if invoice.l10n_mx_edi_cfdi_uuid:
            self.account_move.l10n_mx_edi_origin = '%s|%s' % ('01', invoice.l10n_mx_edi_cfdi_uuid)
        if self.account_move.state != 'posted':
            self.account_move.action_post()
        if invoice.state == 'paid':
            journals = invoice.line_ids.filtered("reconciled")
            journals.remove_move_reconcile()
        return True

    def action_pos_order_invoice(self):
        """Create a credit note if the order is a return of products"""
        res_invoice = super().action_pos_order_invoice()
        refunds = self.filtered(lambda r: r.amount_total < 0)
        if refunds:
            refunds.add_payment_for_credit_note()
        return res_invoice

    def _prepare_invoice(self):
        res = super()._prepare_invoice()
        statement_ids = self.mapped('statement_ids').filtered(lambda st: st.amount > 0)
        journal_ids = statement_ids.read_group([('id', 'in', statement_ids.ids)], ['journal_id'], 'journal_id')
        max_count = 0
        journal_id = False
        for journal in journal_ids:
            if journal.get('journal_id_count') > max_count:
                max_count = journal.get('journal_id_count')
                journal_id = journal.get('journal_id')[0]
        journal = self.env['account.journal'].browse(journal_id) if journal_id else False
        if journal and journal.l10n_mx_edi_payment_method_id:
            res['l10n_mx_edi_payment_method_id'] = journal.l10n_mx_edi_payment_method_id.id
            context = self.env.context.copy()
            context['force_payment_method'] = res['l10n_mx_edi_payment_method_id']
            self.env.context = context
        return res

    @api.model
    def l10n_mx_edi_get_pac_version(self):
        """Returns the CFDI version to generate the CFDI."""
        return self.env["ir.config_parameter"].sudo().get_param("l10n_mx_edi_pos_version", "4.0")
