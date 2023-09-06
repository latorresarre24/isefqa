# Copyright 2018 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.depends('l10n_mx_edi_origin', 'amount_total', 'l10n_mx_edi_advance_ids')
    def _compute_amount_advances(self):
        advances_a = self.filtered(lambda i: i._l10n_mx_edi_get_advance_case() == 'A' and
                                   i.move_type == 'out_invoice' and i.l10n_mx_edi_origin and
                                   i.l10n_mx_edi_origin.startswith('07'))
        for record in self - advances_a:
            record.l10n_mx_edi_amount_advances = 0
            record.l10n_mx_edi_amount_residual_advances = 0
        for record in advances_a:
            if record.state == 'draft':
                adv_amount = sum(record.l10n_mx_edi_advance_ids.mapped('amount'))
            else:
                reverse_entries = self.search(
                    [('reversed_entry_id', '=', self.id)])
                credit_note = reverse_entries.filtered(
                    lambda i: i._l10n_mx_edi_get_advance_uuid_related() and
                    i.state not in ('draft', 'cancel'))
                adv_amount = sum(credit_note.mapped('amount_total'))
            record.l10n_mx_edi_amount_advances = adv_amount
            record.l10n_mx_edi_amount_residual_advances = record.amount_total - adv_amount

    l10n_mx_edi_amount_residual_advances = fields.Monetary(
        'Amount residual with advances', compute='_compute_amount_advances',
        help='Save the amount that will be applied as advance when validate '
        'the invoice')
    l10n_mx_edi_amount_advances = fields.Monetary(
        'Amount in advances', compute='_compute_amount_advances',
        help='Save the amount that will be applied as advance when validate '
        'the invoice')
    l10n_mx_edi_advance_ids = fields.One2many('l10n_mx_edi.advance.detail', 'invoice_id', 'Advances applied',
                                              copy=False, help="Detail for the advances applied to this invoice.")
    l10n_mx_edi_has_outstanding_advances = fields.Boolean(
        # 'Has Advances?', compute='_get_outstanding_info_JSON', groups="account.group_account_invoice",
        'Has Advances?', compute='_compute_get_outstanding_info',
        help='This field will be True if the customer in the invoice has advances that could be used on the customer '
        'invoice.')
    # Fields for advances
    l10n_mx_edi_is_advance = fields.Boolean('Is Advance?', compute='_compute_is_advance', store=True,
                                            help='Indicates if this invoice is an advance.')
    l10n_mx_edi_amount_available = fields.Monetary(
        'Amount available', compute='_compute_advance_available', store=True,
        help='If this record is an advance, returns the available amount.')

    @api.depends('move_type', 'invoice_line_ids.product_id')
    def _compute_is_advance(self):
        for record in self:
            record.l10n_mx_edi_is_advance = record._l10n_mx_edi_is_advance()

    @api.depends('l10n_mx_edi_related_document_ids_inverse.payment_state', 'payment_state')
    def _compute_advance_available(self):
        advances = self.filtered(lambda a: a.state == 'posted' and a.payment_state in ('paid', 'in_payment') and
                                 a._l10n_mx_edi_is_advance())
        for record in self - advances:
            record.l10n_mx_edi_amount_available = 0
        for record in advances:
            available = record.amount_total
            for inv in record.reversal_move_id.filtered(lambda inv: inv.state not in ('draft', 'cancel')):
                available -= inv.amount_total if inv.currency_id == record.currency_id else inv.currency_id._convert(
                    inv.amount_total, record.currency_id, record.company_id, inv.invoice_date or fields.date.today())
            for inv in record.l10n_mx_edi_related_document_ids_inverse.filtered(
                lambda inv: inv.state != 'cancel').mapped(
                    'l10n_mx_edi_advance_ids').filtered(lambda a: a.advance_id.name == record.l10n_mx_edi_cfdi_uuid):
                available -= inv.amount if inv.invoice_id.currency_id == record.currency_id else\
                    inv.invoice_id.currency_id._convert(inv.amount, record.currency_id, record.company_id,
                                                        inv.invoice_id.invoice_date or fields.date.today())
            record.l10n_mx_edi_amount_available = available if available >= 0 else 0

    def _get_advance_domain(self):
        self.ensure_one()
        financial_partner = self.partner_id._find_accounting_partner(self.partner_id)
        return ['|', ('partner_historical_id', 'in', [self.partner_id.id, financial_partner.id]),
                ('partner_id', 'in', [self.partner_id.id, financial_partner.id]),
                ('amount_available', '>', 0)]

    def _get_outstanding_advances(self):
        domain = self._get_advance_domain()
        for uuid in self._l10n_mx_edi_get_advance_uuid_related():
            domain.extend([('advance_id.l10n_mx_edi_cfdi_uuid', 'not like', uuid)])
        return self.env['l10n_mx_edi.advance'].search(domain)

    def _compute_get_outstanding_info(self):
        for record in self:
            if record.state != 'draft' or record.move_type != 'out_invoice' or (
                    not record._get_outstanding_advances() and not record.l10n_mx_edi_advance_ids):
                record.l10n_mx_edi_has_outstanding_advances = False
                continue
            record.l10n_mx_edi_has_outstanding_advances = True

    def _l10n_mx_edi_is_advance(self):
        """Check if an invoice is an advance"""
        self.ensure_one()
        if self.move_type != 'out_invoice' or len(self.invoice_line_ids) != 1:
            return False
        advance_product = self.company_id.l10n_mx_edi_product_advance_id
        if self.invoice_line_ids.product_id.id != advance_product.id:
            return False
        return True

    def _l10n_mx_edi_get_advance_uuid_related(self):
        """return the advance's uuid applied"""
        self.ensure_one()
        if not self.l10n_mx_edi_origin:
            return []
        related_docs = self._l10n_mx_edi_read_cfdi_origin(self.l10n_mx_edi_origin)
        if related_docs[0] == '07':
            return related_docs[1]
        return []

    @api.onchange('invoice_line_ids')
    def _onchange_invoice_line_ids(self):
        """Set values when the invoice is an advance"""
        res = super()._onchange_invoice_line_ids()
        if not self._l10n_mx_edi_is_advance():
            return res
        self.update({
            'invoice_payment_term_id': self.env.ref(
                'account.account_payment_term_immediate'),
            'l10n_mx_edi_origin': False,
        })
        self.invoice_line_ids.name = 'Anticipo del bien o servicio'
        return res

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        res = super()._onchange_partner_id()
        # pylint:disable=using-constant-test
        if self._l10n_mx_edi_is_advance:
            self._onchange_invoice_line_ids()
        return res

    def _post(self, soft=True):
        """Create the credit note for advances and reconcile it with
        the invoice (only when this one has advances and it's signed).
        """
        has_advance = self.filtered(lambda r: r.move_type == 'out_invoice' and
                                    r._l10n_mx_edi_get_advance_case() == 'A' and
                                    r._l10n_mx_edi_get_advance_uuid_related())
        res = super()._post(soft)
        # Section to create advance
        for record in self.filtered(lambda i: i._l10n_mx_edi_is_advance()):
            record._l10n_mx_edi_create_advance()

        for inv in has_advance:
            refund = inv._prepare_advance_refund()
            inv.message_post_with_view(
                'l10n_mx_edi_advance.l10n_mx_edi_message_advance_refund',
                values={'self': inv, 'origin': refund},
                subtype_id=self.env.ref('mail.mt_note').id)
            inv._l10n_mx_edi_prepare_advance_cron()
        return res

    def _l10n_mx_edi_prepare_advance(self):
        self.ensure_one()
        return {
            'advance_id': self.id,
            'name': self.l10n_mx_edi_cfdi_uuid,
            'amount_available': self.amount_total,
            'is_historical': False,
        }

    def _l10n_mx_edi_create_advance(self):
        self.ensure_one()
        advance = self.env['l10n_mx_edi.advance'].search([('advance_id', '=', self.id)], limit=1)
        if advance:
            return advance
        advance = advance.create(self._l10n_mx_edi_prepare_advance())
        self.message_post_with_view(
            'l10n_mx_edi_advance.l10n_mx_edi_message_invoice_advance',
            values={'self': self, 'origin': advance},
            subtype_id=self.env.ref('mail.mt_note').id)
        return advance

    def l10n_mx_edi_advance_sign_refund(self):
        """Get the missing data on refund to allow stamp the document if is related to an advance"""
        self.ensure_one()
        if self.state in ('draft', 'cancel'):
            self.message_post(body=_('The document must be valid in the system to be signed in the SAT.'))
            return False
        if not self.reversed_entry_id.l10n_mx_edi_cfdi_uuid:
            self.message_post(body=_('The invoice related is not signed on the SAT system.'))
            return False
        if self.l10n_mx_edi_cfdi_uuid:
            self.message_post(body=_('This record already was signed on the SAT system.'))
            return False
        self.l10n_mx_edi_origin = (self.l10n_mx_edi_origin or '') + self.reversed_entry_id.l10n_mx_edi_cfdi_uuid\
            if self.l10n_mx_edi_origin == '07|' else '07|%s' % self.reversed_entry_id.l10n_mx_edi_cfdi_uuid
        self.action_process_edi_web_services()
        return True

    def _prepare_advance_refund(self):
        self.ensure_one()
        refund = self.env['account.move.reversal'].with_context(
            active_ids=self.ids, active_model='account.move').create({
                'refund_method': 'cancel',
                'reason': 'Aplicación de anticipos',
                'date': self.invoice_date,
                'journal_id': self.journal_id.id,
            })
        refund = refund.reverse_moves()
        if self.l10n_mx_edi_cfdi_uuid:
            self.reversal_move_id.write({'l10n_mx_edi_origin': '07|%s' % self.l10n_mx_edi_cfdi_uuid})
        return self.browse(refund.get('res_id', []))

    def _l10n_mx_edi_prepare_advance_cron(self):
        """To avoid disable the after commit, the credit note will be send to the SAT after of the invoice validation
        """
        # Generate cron to autovalidate the NC
        self.ensure_one()
        cron = self.env['ir.cron'].sudo().create({
            'name': _('Advances: Refund from invoice %s') % self.id,
            'model_id': self.env.ref('account.model_account_move').id,
            'numbercall': 1,
            'interval_type': False,
            'doall': True,
            'code': '''env['%s'].browse(%s).l10n_mx_edi_advance_sign_refund()''' % (
                self._name, self.reversal_move_id.ids)
        })
        # To avoid TZ problems, update the default nextcall + 5 minutes
        cron.nextcall = cron.nextcall + timedelta(minutes=5)

    @api.model
    def _reverse_move_vals(self, default_values, cancel=True):
        """Assign values for a CFDI credit note and advance
            - CFDI origin.
            - Payment method
            - Usage: 'G02' - returns, discounts or bonuses.
        """
        advances = self.l10n_mx_edi_advance_ids
        if advances and self.l10n_mx_edi_cfdi_request in ('on_invoice', 'on_refund'):
            default_values.update({
                'l10n_mx_edi_payment_method_id': self.l10n_mx_edi_payment_method_id.id,
                'l10n_mx_edi_usage': 'G02',
            })
        values = super()._reverse_move_vals(default_values, cancel)
        invoice_line_ids = []
        for advance in advances:
            adv_amount = advance.amount
            reverse_entries = self.search([('reversed_entry_id', '=', self.id)])
            if (reverse_entries or not adv_amount or not self._l10n_mx_edi_get_advance_uuid_related()):
                continue
            self.refresh()
            values['l10n_mx_edi_payment_method_id'] = self.env.ref('l10n_mx_edi.payment_method_anticipos').id
            adv_prod = self.company_id.l10n_mx_edi_product_advance_id
            taxes = adv_prod.taxes_id
            percentage = sum(tax.amount for tax in taxes if not tax.price_include)
            price_unit = adv_amount * 100 / (100 + percentage)
            invoice_line_ids.extend([(0, 0, {
                'name': 'Aplicación de anticipo',
                'price_unit': price_unit,
                'account_id': adv_prod.property_account_income_id.id,
                'product_id': adv_prod.id,
                'product_uom_id': adv_prod.uom_id.id,
                'tax_ids': [(6, 0, taxes.ids)],
            })])
        if invoice_line_ids:
            values.pop('line_ids')
            values['invoice_line_ids'] = invoice_line_ids
        return values

    def _get_values_historical_advance(self):
        adv_prod = self.company_id.l10n_mx_edi_product_advance_id
        return {'invoice_type': 'out_invoice',
                'uom_id': adv_prod.uom_id.id,
                'product_id': adv_prod.id,
                'quantity': 1.0,
                'invoice_line_tax_ids': [(6, 0, adv_prod.taxes_id.ids)],
                'company_id': self.company_id.id,
                }

    @api.returns('self')
    def advance(self, partner, amount, currency):
        """Create an advance"""
        company = self.env.context.get('company_id') or self.env.company.id
        company = self.env['res.company'].browse(company)
        product = company.l10n_mx_edi_product_advance_id
        journal = self._search_default_journal(['sale'])
        prod_accounts = product.product_tmpl_id.get_product_accounts()
        advance = self.new({
            'partner_id': partner.id,
            'currency_id': currency.id,
            'move_type': 'out_invoice',
            'invoice_payment_term_id': self.env.ref('account.account_payment_term_immediate').id,
            'l10n_mx_edi_origin': False,
            'journal_id': journal.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'name': 'Anticipo del bien o servicio',
                'account_id': prod_accounts['income'].id,
                'product_uom_id': product.uom_id.id,
                'quantity': 1,
                'price_unit': 0.0,
            })],
        })
        advance.invoice_line_ids._onchange_account_id()
        # get amount for price unit if there is a tax
        taxes = advance.invoice_line_ids.tax_ids
        percentage = sum(tax.amount for tax in taxes if not tax.price_include)
        price_unit = amount * 100 / (100 + percentage)
        advance.invoice_line_ids.price_unit = price_unit
        advance = self._convert_to_write(advance._cache)
        advance = self.create(advance)
        return advance

    def _l10n_mx_edi_get_advance_case(self):
        self.ensure_one()
        return self.partner_id.l10n_mx_edi_advance or self.company_id.l10n_mx_edi_advance


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model
    def _compute_amount_fields(self, amount, src_currency, company_currency):
        """ Helper function to compute value for fields
        debit/credit/amount_currency based on an amount and the currencies
        given in parameter"""
        # TODO - Remove method
        amount_currency = False
        currency_id = False
        date = self.env.context.get('date') or fields.Date.today()
        company = self.env.context.get('company_id')
        company = self.env['res.company'].browse(
            company) if company else self.env.user.company_id
        if src_currency and src_currency != company_currency:
            amount_currency = amount
            amount = src_currency._convert(
                amount, company_currency, company, date)
            currency_id = src_currency.id
        debit = amount if amount > 0 else 0.0
        credit = -amount if amount < 0 else 0.0
        return debit, credit, amount_currency, currency_id
