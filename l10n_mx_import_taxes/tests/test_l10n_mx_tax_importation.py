from odoo import fields
from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.tests import tagged
from odoo.tests.common import Form


@tagged('post_install', '-at_install')
class TestL10nMxInvoiceTaxImportation(TestMxEdiCommon):

    def setUp(self):
        super().setUp()
        company = self.invoice.company_id
        self.imp_product = self.env.ref('l10n_mx_import_taxes.product_tax_importation')
        imp_tax = self.env.ref('l10n_mx_import_taxes.tax_importation')
        account = imp_tax.sudo().cash_basis_transition_account_id.copy({'company_id': company.id})
        self.imp_tax = imp_tax.sudo().copy({
            'company_id': company.id,
            'cash_basis_transition_account_id': account.id,
        })
        self.journal_payment = self.env['account.journal'].search([
            ('type', '=', 'cash'),
            ('company_id', '=', company.id)], limit=1)
        self.invoice_journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', company.id)], limit=1)

    def test_case_with_tax_importation(self):
        self.invoice.line_ids.unlink()
        foreign_invoice = self.invoice.copy({
            'move_type': 'in_invoice',
            'journal_id': self.invoice_journal.id,
            'currency_id': self.env.ref('base.MXN').id,
            'partner_id': self.partner_a.id,
            'invoice_date': fields.Date.context_today(self.invoice),
        })
        move_form = Form(foreign_invoice)
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product
            line_form.quantity = 1.0
            line_form.price_unit = 450.00
            line_form.tax_ids.clear()
        move_form.save()
        self._validate_invoice(foreign_invoice, False)

        # Import invoice Taxes
        self.partner_b.write({
            'country_id': self.env.ref('base.mx').id,
            'vat': 'VAU111017CG9',
        })
        invoice = foreign_invoice.copy({
            'invoice_date': fields.Date.context_today(self.invoice),
        })
        move_form = Form(invoice)
        move_form.partner_id = self.partner_b
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.imp_product
            line_form.tax_ids.clear()
            line_form.tax_ids.add(self.imp_tax)
            line_form.quantity = 0.0
            line_form.price_unit = 450
            line_form.l10n_mx_edi_invoice_broker_id = foreign_invoice
        move_form.save()
        invoice.invoice_line_ids.price_unit = 450
        self._validate_invoice(invoice)
        # Get DIOT report
        self.partner_a.l10n_mx_type_of_operation = '85'
        self.partner_b.l10n_mx_type_of_operation = '85'
        self.diot_report = self.env['l10n_mx.account.diot']
        options = self.diot_report._get_options()
        options.get('date', {})['date_from'] = invoice.invoice_date
        options.get('date', {})['date_to'] = invoice.invoice_date
        data = self.diot_report.get_txt(options)
        self.assertEqual(
            data, '05|85||123456789|partnera|US|American|||||||||450|||||||||\n'.encode(),
            "Error with tax importation DIOT")

    def _validate_invoice(self, invoice, pay=True):
        invoice.action_post()
        if pay:
            statement = self.env['account.bank.statement'].with_context(edi_test_mode=True).create({
                'name': 'test_statement',
                'date': invoice.invoice_date,
                'journal_id': self.journal_payment.id,
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
            payable_lines = invoice.line_ids.filtered(lambda line: line.account_internal_type == 'payable')
            payable_lines = [{'id': line.id} for line in payable_lines]
            statement.line_ids[0].reconcile(payable_lines)
            return statement.line_ids.move_id
        return invoice
