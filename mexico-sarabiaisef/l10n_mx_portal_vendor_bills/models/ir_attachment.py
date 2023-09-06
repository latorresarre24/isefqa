# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import base64
from codecs import BOM_UTF8
from lxml import etree, objectify
from odoo import models, api, fields, _
from odoo.tools.float_utils import float_is_zero
from odoo.tools import date_utils, float_round
from odoo.exceptions import UserError


BOM_UTF8U = BOM_UTF8.decode('UTF-8')


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def parse_xml(self, xml_file, purchase):
        """Simple wrapper to the wizard that runs the whole process of the
        importation of documents on the backend, some extra steps are done
        here:
        - Creation of custom filename: rfc-emisor_folio_serie_AnoMesDia
        - Validate if the CFDI is v 3.3

        :param xml_file (string): The filestorage itself.
        :return filename: The new filename which will be used to store the
        attachment.
        :rtype string:
        :return (dict): A dictionary with the following attributes
            - key.- If all is OK return True, else False
            - xml64.- The same CFDI in base64
            - where.- The file on which the process was executed
            - error.- If it's found, return the message
            - invoice_id.- The newly created invoice
        :rtype dict:
        """
        xml_string = xml_file.read()
        data = base64.b64encode(xml_string)
        res = self.sudo().check_xml({xml_file.filename: data}, purchase)
        xml = objectify.fromstring(xml_string)

        # early return if errors found
        if not res.get(xml_file.filename, True):
            return res, xml_file.filename

        # Extract data from xml file
        doc_number = xml.get('Folio', False)
        serial = xml.get('Serie', False)
        date = xml.get('Fecha', False)
        supplier_vat = xml.Emisor.get('Rfc', False)

        # create base filename
        filename = '%s_%s_%s_%s' % (
            supplier_vat, doc_number, serial, date[:10])

        return res, filename

    def _search_invoice(self, exist_supplier, amount, serie_folio, folio, xml_date):
        inv_obj = self.env['account.move']
        domain = ['|', ('partner_id', 'child_of', exist_supplier.id), ('partner_id', '=', exist_supplier.id)]
        force_folio = self.env['ir.config_parameter'].sudo().get_param('l10n_mx_force_only_folio', '')
        if serie_folio and force_folio:
            domain.append('|')
            domain.append(('payment_reference', '=ilike', folio))
        if serie_folio:
            domain.append(('payment_reference', '=ilike', serie_folio))
            return inv_obj.search(domain, limit=1)
        domain.append(('amount_total', '>=', amount - 1))
        domain.append(('amount_total', '<=', amount + 1))
        domain.append(('state', '!=', 'cancel'))
        domain.append(('move_type', 'in', ('in_invoice', 'in_refund')))
        omit_state_in_invoices = self.env['ir.config_parameter'].sudo().get_param('omit_state_in_invoices', '')
        if omit_state_in_invoices:
            omit_state_in_invoices = omit_state_in_invoices.split(",")
            domain.append(('state', 'not in', omit_state_in_invoices))
            domain.append(('invoice_payment_state', 'not in', omit_state_in_invoices))

        date_type = self.env['ir.config_parameter'].sudo().get_param('l10n_mx_edi_vendor_bills_force_use_date')
        xml_date = fields.datetime.strptime(xml_date, '%Y-%m-%dT%H:%M:%S').date()

        if date_type == "day":
            domain.append(('invoice_date', '=', xml_date))
        elif date_type == "month":
            invoice_date = date_utils.get_month(xml_date)
            domain.append(('invoice_date', '>=', invoice_date[0]))
            domain.append(('invoice_date', '<=', invoice_date[1]))

        return inv_obj.search(domain, limit=1)

    @api.model
    def check_xml(self, files, purchase):
        """ Validate that attributes in the xml before create invoice
        or attach xml in it
        :param files: dictionary of CFDIs in b64
        :type files: dict
        :return: the Result of the CFDI validation
        :rtype: dict
        """
        if not isinstance(files, dict):
            raise UserError(_("Something went wrong. The parameter for XML "
                              "files must be a dictionary."))
        wrongfiles = {}
        invoices = {}
        outgoing_docs = {}
        account_id = self._context.get('account_id', False)
        for key, xml64 in files.items():
            try:
                if isinstance(xml64, bytes):
                    xml64 = xml64.decode()
                xml_str = base64.b64decode(xml64.replace('data:text/xml;base64,', ''))
                # Fix the CFDIs emitted by the SAT
                xml_str = xml_str.replace(b'xmlns:schemaLocation', b'xsi:schemaLocation')
                xml = objectify.fromstring(xml_str)
            except (AttributeError, SyntaxError) as exce:
                wrongfiles.update({key: {
                    'xml64': xml64, 'where': 'CheckXML',
                    'error': [exce.__class__.__name__, str(exce)]}})
                continue
            if xml.get('TipoDeComprobante', False) == 'E':
                outgoing_docs.update({key: {'xml': xml, 'xml64': xml64}})
                continue
            if xml.get('TipoDeComprobante', False) != 'I':
                wrongfiles.update({key: {'cfdi_type': True, 'xml64': xml64}})
                continue
            # Check the incoming documents
            validated_documents = self.validate_documents(key, xml, account_id, purchase)
            wrongfiles.update(validated_documents.get('wrongfiles'))
            if wrongfiles.get(key, False) and wrongfiles[key].get('xml64', False):
                wrongfiles[key]['xml64'] = xml64
            invoices.update(validated_documents.get('invoices'))
        # Check the outgoing documents
        for key, value in outgoing_docs.items():
            xml64 = value.get('xml64')
            xml = value.get('xml')
            xml = self._l10n_mx_edi_convert_cfdi32_to_cfdi33(xml)
            validated_documents = self.validate_documents(key, xml, account_id, purchase)
            wrongfiles.update(validated_documents.get('wrongfiles'))
            if wrongfiles.get(key, False) and wrongfiles[key].get('xml64', False):
                wrongfiles[key]['xml64'] = xml64
            invoices.update(validated_documents.get('invoices'))
        return {'wrongfiles': wrongfiles, 'invoices': invoices}

    def validate_documents(self, key, xml, account_idi, purchase):
        """ Validate the incoming or outcoming document before create or
        attach the xml to invoice
        :param key: Name of the document that is being validated
        :type key: str
        :param xml: xml file with the datas of purchase
        :type xml: etree
        :param account_id: The account by default that must be used in the
            lines of the invoice if this is created
        :type account_id: int
        :return: Result of the validation of the CFDI and the invoices created.
        :rtype: dict
        """
        wrongfiles = {}
        invoices = {}
        inv_obj = self.env['account.move']
        partner_obj = self.env['res.partner']
        currency_obj = self.env['res.currency']
        inv = inv_obj
        inv_id = False
        xml_str = etree.tostring(xml, pretty_print=True, encoding='UTF-8')
        xml_vat_emitter, xml_vat_receiver, xml_amount, xml_currency, version,\
            xml_name_supplier, xml_type_of_document, xml_uuid, xml_serie_folio, xml_taxes = self._get_xml_data(xml)
        xml_related_uuid = related_invoice = False
        exist_supplier = partner_obj.search(
            ['&', ('vat', '=', xml_vat_receiver), '|',
             ('company_id', '=', False),
             ('company_id', '=', self.env.company.id)], limit=1)
        xml_folio = xml.get('Folio', '')
        xml_date = xml.get('Fecha', '')
        invoice = self._search_invoice(exist_supplier, xml_amount, xml_serie_folio, xml_folio, xml_date)
        invoice = invoice or purchase.invoice_ids
        exist_reference = invoice if invoice and xml_uuid != invoice.l10n_mx_edi_cfdi_uuid else False
        if exist_reference and not exist_reference.l10n_mx_edi_cfdi_uuid:
            inv = exist_reference
            inv_id = inv.id
            exist_reference = False
            inv.l10n_mx_edi_update_sat_status()
        xml_status = inv.l10n_mx_edi_sat_status
        inv_vat_receiver = (self.env.company.vat or '').upper()
        inv_vat_emitter = (inv and inv.commercial_partner_id.vat or '').upper()
        inv_amount = inv.amount_total
        inv_folio = inv.payment_reference or ''
        # TODO: inv.journal_id.l10n_mx_edi_amount_authorized_diff
        diff = 1
        domain = [('id', 'not in', invoice.ids)] if invoice else []
        if exist_supplier:
            domain += [('partner_id', 'child_of', exist_supplier.id)]
        if xml_type_of_document == 'I':
            domain += [('move_type', '=', 'in_invoice')]
        if xml_type_of_document == 'E':
            domain += [('type', '=', 'in_refund')]
        uuid_dupli = xml_uuid in inv_obj.search(domain).mapped('l10n_mx_edi_cfdi_uuid')
        mxns = ['mxp', 'mxn', 'pesos', 'peso mexicano', 'pesos mexicanos', 'mn', 'nacional']
        xml_currency = 'MXN' if xml_currency.lower() in mxns else xml_currency

        exist_currency = currency_obj.search([('name', '=', xml_currency)], limit=1)
        xml_related_uuid = False
        if xml_type_of_document == 'E' and hasattr(xml, 'CfdiRelacionados'):
            xml_related_uuid = xml.CfdiRelacionados.CfdiRelacionado.get('UUID')
            related_invoice = xml_related_uuid in inv_obj.search([
                ('move_type', '=', 'in_invoice')]).mapped('l10n_mx_edi_cfdi_uuid')
        omit_cfdi_related = self._context.get('omit_cfdi_related')
        force_save = False
        errors = [
            (not xml_uuid, {'signed': True}),
            (xml_status == 'cancelled', {'cancel': True}),
            ((xml_uuid and uuid_dupli), {'uuid_duplicate': xml_uuid}),
            ((inv_vat_receiver != xml_vat_receiver), {'rfc': (xml_vat_receiver, inv_vat_receiver)}),
            ((not inv_id and exist_reference), {'payment_reference': (xml_name_supplier, xml_serie_folio)}),
            (version not in ('3.3', '4.0'), {'version': True}),
            ((not inv_id and not exist_supplier), {'supplier': xml_name_supplier}),
            ((not inv_id and xml_currency and not exist_currency), {'currency': xml_currency}),
            ((not inv_id and xml_taxes.get('wrong_taxes', False)), {'taxes': xml_taxes.get('wrong_taxes', False)}),
            ((not inv_id and xml_taxes.get('withno_account', False)),
             {'taxes_wn_accounts': xml_taxes.get('withno_account', False)}),
            ((inv_id and inv_folio and xml_serie_folio and inv_folio not in [xml_serie_folio, xml_folio]),
             {'folio': (xml_serie_folio, inv_folio)}),
            ((inv_id and inv_vat_emitter != xml_vat_emitter), {'rfc_supplier': (xml_vat_emitter, inv_vat_emitter)}),
            ((inv_id and abs(round(float(inv_amount)-float(xml_amount), 2)) > diff), {
                'amount': (xml_amount, inv_amount)}),
            ((xml_related_uuid and not related_invoice and not force_save), {'invoice_not_found': xml_related_uuid}),
            ((not omit_cfdi_related and xml_type_of_document == 'E' and
              not xml_related_uuid), {'no_xml_related_uuid': True}),
        ]
        msg = {}
        for error in errors:
            if error[0]:
                msg.update(error[1])
        if msg:
            msg.update({'xml64': True})
            wrongfiles.update({key: msg})
            return {'wrongfiles': wrongfiles, 'invoices': invoices}

        if not invoice:
            invoice = purchase.action_create_invoice()
            invoice = self.env['account.move'].browse(invoice.get('res_id', []))
            invoice.payment_reference = xml_serie_folio

            self._l10n_mx_edi_prepare_edi(invoice, xml_str)
            invoice.l10n_mx_edi_update_sat_status()

            invoices.update({key: {'invoice_id': invoice.id}})
            return {'wrongfiles': wrongfiles, 'invoices': invoices}

        self._l10n_mx_edi_prepare_edi(invoice, xml_str)
        invoice.payment_reference = '%s|%s' % (xml_serie_folio, xml_uuid.split('-')[0])
        invoices.update({key: {'invoice_id': invoice.id}})
        if not float_is_zero(float(invoice.amount_total) - float(xml_amount), precision_digits=0):
            invoice.message_post(
                body=_('The XML attached total amount is different to '
                       'the total amount in this invoice. The XML total amount is %s') % xml_amount)
        return {'wrongfiles': wrongfiles, 'invoices': invoices}

    def _l10n_mx_edi_prepare_edi(self, invoice, xml_str):
        edi_format_id = self.env.ref('l10n_mx_edi.edi_cfdi_3_3')
        if invoice.edi_document_ids.filtered(lambda l: l.edi_format_id == edi_format_id):
            return True
        fname = ("%s-%s-MX-Bill-%s.xml" % (invoice.journal_id.code, invoice.payment_reference,
                                           invoice.company_id.partner_id.vat or '')).replace('/', '')
        attachment = self.env['ir.attachment'].with_context({}).create({  # noqa pylint: disable=context-overridden
            'name': fname,
            'datas': base64.b64encode(xml_str),
            'res_model': self._name,
            'res_id': self.id,
        })
        self.env['account.edi.document'].create({
            'edi_format_id': edi_format_id.id,
            'move_id': invoice.id,
            'state': 'sent',
            'attachment_id': attachment.id,
        })
        return True

    def _l10n_mx_edi_get_tfd_etree(self, cfdi_node):
        if hasattr(cfdi_node, 'Complemento'):
            node = cfdi_node.Complemento.xpath(
                'tfd:TimbreFiscalDigital[1]', namespaces={'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'})
            return node[0] if node else None
        return None

    @api.model
    def _get_xml_data(self, xml):
        """Return data from XML"""
        vat_emitter = xml.Emisor.get('Rfc', '').upper()
        vat_receiver = xml.Receptor.get('Rfc', '').upper()
        amount = float(xml.get('Total', 0.0))
        currency = xml.get('Moneda', 'MXN')
        version = xml.get('Version', xml.get('version'))
        name_supplier = xml.Emisor.get('Nombre', '')
        document_type = xml.get('TipoDeComprobante', False)
        tfd = self._l10n_mx_edi_get_tfd_etree(xml)
        uuid = False if tfd is None else tfd.get('UUID', '')
        folio = self.get_xml_folio(xml)
        taxes = self.get_impuestos(xml)
        local_taxes = self.get_local_taxes(xml)
        taxes['wrong_taxes'] = taxes.get('wrong_taxes', []) + local_taxes.get('wrong_taxes', [])
        taxes['withno_account'] = taxes.get('withno_account', []) + local_taxes.get('withno_account', [])
        return vat_emitter, vat_receiver, amount, currency, version, name_supplier, document_type, uuid, folio, taxes

    def get_xml_folio(self, xml):
        return '%s%s' % (xml.get('Serie', ''), xml.get('Folio', ''))

    @staticmethod
    def collect_taxes(taxes_xml):
        """ Get tax data of the Impuesto node of the xml and return
        dictionary with taxes datas
        :param taxes_xml: Impuesto node of xml
        :type taxes_xml: etree
        :return: A list with the taxes data
        :rtype: list
        """
        taxes = []
        tax_codes = {'001': 'ISR', '002': 'IVA', '003': 'IEPS'}
        for rec in taxes_xml:
            tax_xml = rec.get('Impuesto', '')
            tax_xml = tax_codes.get(tax_xml, tax_xml)
            amount_xml = float(rec.get('Importe', '0.0'))
            rate_xml = float_round(
                float(rec.get('TasaOCuota', '0.0')) * 100, 4)
            if 'Retenciones' in rec.getparent().tag:
                amount_xml = amount_xml * -1
                rate_xml = rate_xml * -1

            base = float(rec.get('Base', '0.0'))
            taxes.append({'rate': rate_xml, 'tax': tax_xml,
                          'amount': amount_xml, 'base': base})
        return taxes

    def get_local_taxes(self, xml):
        if not hasattr(xml, 'Complemento'):
            return {}
        type_tax_use = 'purchase' if self._context.get('l10n_mx_edi_invoice_type') == 'in' else 'sale'
        local_taxes = xml.Complemento.xpath(
            'implocal:ImpuestosLocales', namespaces={'implocal': 'http://www.sat.gob.mx/implocal'})
        taxes_list = {'wrong_taxes': [], 'withno_account': [], 'taxes': []}
        if not local_taxes:
            return taxes_list
        local_taxes = local_taxes[0]
        tax_obj = self.env['account.tax']
        taxes_to_omit = self.get_taxes_to_omit()
        if hasattr(local_taxes, 'RetencionesLocales'):
            for local_ret in local_taxes.RetencionesLocales:
                name = local_ret.get('ImpLocRetenido')
                tasa = float(local_ret.get('TasadeRetencion')) * -1
                tax = tax_obj.search([
                    '&',
                    ('type_tax_use', '=', type_tax_use),
                    '|',
                    ('name', '=', name),
                    ('amount', '=', tasa)], limit=1)
                if not tax and name not in taxes_to_omit:
                    taxes_list['wrong_taxes'].append(name)
                    continue
                tax_account = tax.invoice_repartition_line_ids.filtered(lambda rec: rec.repartition_type == 'tax')
                if not tax_account and name not in taxes_to_omit:
                    taxes_list['withno_account'].append(name)
                    continue
                taxes_list['taxes'].append((0, 0, {
                    'tax_id': tax.id,
                    'account_id': tax_account.id,
                    'name': name,
                    'amount': float(local_ret.get('Importe')) * -1,
                    'for_expenses': not bool(tax),
                }))
        if hasattr(local_taxes, 'TrasladosLocales'):
            for local_tras in local_taxes.TrasladosLocales:
                name = local_tras.get('ImpLocTrasladado')
                tasa = float(local_tras.get('TasadeTraslado'))
                tax = tax_obj.search([
                    '&',
                    ('type_tax_use', '=', type_tax_use),
                    '|',
                    ('name', '=', name),
                    ('amount', '=', tasa)], limit=1)
                if not tax and name not in taxes_to_omit:
                    taxes_list['wrong_taxes'].append(name)
                    continue
                tax_account = tax.invoice_repartition_line_ids.filtered(lambda rec: rec.repartition_type == 'tax')
                if not tax_account and name not in taxes_to_omit:
                    taxes_list['withno_account'].append(name)
                    continue
                taxes_list['taxes'].append((0, 0, {
                    'tax_id': tax.id,
                    'account_id': tax_account.id,
                    'name': name,
                    'amount': float(local_tras.get('Importe')),
                    'for_expenses': not bool(tax),
                }))

        return taxes_list

    def get_impuestos(self, xml):
        if not hasattr(xml, 'Impuestos'):
            return {}
        taxes_list = {'wrong_taxes': [], 'taxes_ids': {}, 'withno_account': []}
        taxes = []
        for index, rec in enumerate(xml.Conceptos.Concepto):
            if not hasattr(rec, 'Impuestos'):
                continue
            taxes_list['taxes_ids'][index] = []
            taxes_xml = rec.Impuestos
            if hasattr(taxes_xml, 'Traslados'):
                taxes = self.collect_taxes(taxes_xml.Traslados.Traslado)
            if hasattr(taxes_xml, 'Retenciones'):
                taxes += self.collect_taxes(taxes_xml.Retenciones.Retencion)

            for tax in taxes:
                tax_group_id = self.env['account.tax.group'].search(
                    [('name', 'ilike', tax['tax'])])
                domain = [('tax_group_id', 'in', tax_group_id.ids),
                          ('type_tax_use', '=', 'purchase'), ]
                if -10.67 <= tax['rate'] <= -10.66:
                    domain.append(('amount', '<=', -10.66))
                    domain.append(('amount', '>=', -10.67))
                else:
                    domain.append(('amount', '=', tax['rate']))

                name = '%s(%s%%)' % (tax['tax'], tax['rate'])

                tax_get = self.env['account.tax'].search(domain, limit=1)
                taxes_to_omit = self.get_taxes_to_omit()

                if (not tax_group_id or not tax_get) and tax.get('tax', False) not in taxes_to_omit:
                    taxes_list['wrong_taxes'].append(name)
                    continue
                # TODO review if this validation of account in taxes is correct
                tax_account = tax_get.invoice_repartition_line_ids.filtered(
                    lambda rec: rec.repartition_type == 'tax')
                if not tax_account and tax.get('tax', '') not in taxes_to_omit:
                    taxes_list['withno_account'].append(
                        name if name else tax['tax'])
                else:
                    tax['id'] = tax_get.id
                    tax['account'] = tax_account.id
                    tax['name'] = name if name else tax['tax']
                    tax['for_expenses'] = not bool(tax_get)
                    taxes_list['taxes_ids'][index].append(tax)
        return taxes_list

    def get_taxes_to_omit(self):
        """Some taxes are not found in the system, but is correct, because that
        taxes should be adds in the invoice like expenses.
        To make dynamic this, could be add an system parameter with the name:
            l10n_mx_taxes_for_expense, and un the value set the taxes name,
        and if are many taxes, split the names by ','"""
        taxes = self.env['ir.config_parameter'].sudo().get_param('l10n_mx_taxes_for_expense', '')
        return taxes.split(',')

    @api.model
    def _get_fuel_codes(self):
        """Return the codes that could be used in FUEL"""
        fuel_codes = [str(r) for r in range(15101500, 15101516)]
        return fuel_codes

    def get_default_analytic(self, product, supplier, account_id):
        try:
            analytic_default = self.env['account.analytic.default']
        except BaseException:
            return False
        default_analytic = (analytic_default.account_get(
            product_id=product.id, partner_id=supplier.id, account_id=account_id,
            user_id=self.env.user.id, date=fields.Date.today(), company_id=self.env.user.company_id.id) or False)
        return default_analytic
