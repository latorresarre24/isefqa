from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.tests import Form


class AdvanceTransactionCase(TestMxEdiCommon):

    def setUp(self):
        super().setUp()
        self.payment = self.env['account.payment']

        # Prepare CFDI data
        self.certificate._check_credentials()
        self.iva_tag = self.env['account.account.tag'].search([('name', '=', 'IVA')])
        self.tax_16.invoice_repartition_line_ids.write({'tag_ids': [(6, 0, [self.iva_tag.id])]})
        self.tax_16.refund_repartition_line_ids.write({'tag_ids': [(6, 0, [self.iva_tag.id])]})
        self.tax_10_negative.invoice_repartition_line_ids.write({'tag_ids': [(6, 0, [self.iva_tag.id])]})
        self.tax_10_negative.refund_repartition_line_ids.write({'tag_ids': [(6, 0, [self.iva_tag.id])]})
        taxes = self.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'), ('company_id', '=', self.invoice.company_id.id)])
        taxes.write({
            'cash_basis_transition_account_id':  self.env['account.account'].search([
                ('code', '=', '209.01.01'), ('company_id', '=', self.invoice.company_id.id)]).id,
        })

        self.cash = self.env.ref('l10n_mx_edi.payment_method_efectivo')
        self.payment_method_id = self.env.ref('account.account_payment_method_manual_in')
        self.bank_journal = self.env['account.journal'].search([
            ('type', '=', 'bank'), ('company_id', '=', self.invoice.company_id.id)], limit=1)
        self.advance_national = self.env.ref('l10n_mx_edi_advance.product_product_advance')
        self.invoice.company_id.sudo().write({
            'l10n_mx_edi_product_advance_id': self.advance_national.id,
        })

        self.mxn = self.env.ref('base.MXN')
        self.usd = self.env['res.currency'].search([('name', '=', 'USD')])

        # set account in product
        self._prepare_accounts()

        self.journal = self.env.ref('l10n_mx_edi_advance.extra_advance_journal')
        # set taxes in product
        self.advance_national.taxes_id = [self.tax_16.id, self.tax_10_negative.id]
        self.adv_amount = 150.0
        self.set_currency_rates(1, 0.052890)
        self.today_mx = (self.env['l10n_mx_edi.certificate'].sudo().get_mx_current_datetime().date())
        self.invoice.currency_id = self.usd
        move_form = Form(self.invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.product_uom_id = self.invoice.invoice_line_ids.product_id.uom_id
            line_form.tax_ids.clear()
        move_form.save()
        self.invoice.journal_id.edi_format_ids = self.env.ref('l10n_mx_edi.edi_cfdi_3_3')

    def register_payment(self, invoice):
        statement = self.env['account.bank.statement'].with_context(edi_test_mode=True).create({
            'name': 'test_statement',
            'date': invoice.invoice_date,
            'journal_id': self.bank_journal.id,
            'currency_id': invoice.currency_id,
            'line_ids': [
                (0, 0, {
                    'payment_ref': 'mx_st_line',
                    'partner_id': self.partner_a.id,
                    'amount': invoice.amount_total,
                    'l10n_mx_edi_payment_method_id': self.env.ref('l10n_mx_edi.payment_method_efectivo').id,
                }),
            ],
        })
        statement.button_post()
        receivable_line = invoice.line_ids.filtered(lambda line: line.account_internal_type == 'receivable')
        statement.line_ids.reconcile([{'id': receivable_line.id}])
        return statement.line_ids.move_id

    def _prepare_accounts(self):
        account_obj = self.env['account.account']
        tag_obj = self.env['account.account.tag']
        expense = account_obj.create({
            'name': 'Anticipo de clientes (Por cobrar)',
            'code': '206.01.02',
            'user_type_id': self.ref('account.data_account_type_current_liabilities'),
            'tag_ids': [(6, 0, tag_obj.search([('name', '=', '206.01 Anticipo de cliente nacional')]).ids)],
            'reconcile': True,
        })
        self.advance_national.property_account_income_id = expense

    def _create_advance_and_apply(self, invoice, adv_currency, adv_amount, apply=True):
        advance = self.env['account.move'].advance(invoice.partner_id, adv_amount, adv_currency)
        advance.action_post()
        advance.action_process_edi_web_services()
        self.assertEqual(advance.edi_state, "sent", advance.edi_document_ids.mapped('error'))
        self.register_payment(advance)
        # add advance
        if apply:
            self._apply_advances(invoice)
        return advance

    def _apply_advances(self, invoice, advance_amount=False):
        invoice_form = Form(self.env['invoice.apply.advances'].with_context(active_ids=invoice.ids))
        wizard = invoice_form.save()
        if advance_amount:
            wizard.advance_ids.filtered('amount').write({'amount': advance_amount})
        for line in wizard.advance_ids.filtered(lambda a: not a.amount):
            line.amount = line.amount_available
        wizard.apply_advances()

    def set_currency_rates(self, mxn_rate, usd_rate):
        date = (self.env['l10n_mx_edi.certificate'].sudo().get_mx_current_datetime().date())
        self.mxn.rate_ids.filtered(lambda r: r.name == date).unlink()
        self.mxn.rate_ids = self.env['res.currency.rate'].create(
            {'rate': mxn_rate, 'name': date, 'currency_id': self.mxn.id})
        self.usd.rate_ids.filtered(lambda r: r.name == date).unlink()
        self.usd.rate_ids = self.env['res.currency.rate'].create({
            'rate': usd_rate, 'name': date, 'currency_id': self.usd.id})
