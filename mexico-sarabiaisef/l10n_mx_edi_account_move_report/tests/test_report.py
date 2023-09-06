from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.tests.common import Form
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestReport(TestMxEdiCommon):

    def test_01_render_report(self):
        invoice = self.invoice.copy()
        report = self.env['ir.actions.report']._get_report_from_name(
            'l10n_mx_edi_account_move_report.account_entries_report')
        self.assertEqual(len(report._render(invoice.id)), 2)

        payment = self.payment.copy()
        self.assertEqual(len(report._render(payment.move_id.id)), 2)

    def test_02_render_report_invoice_signed(self):
        self.certificate._check_credentials()
        invoice = self.invoice.copy()
        invoice.currency_id = self.env.ref('base.MXN')
        move_form = Form(invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.product_uom_id = line_form.product_id.uom_id
            line_form.tax_ids.clear()
        move_form.save()
        invoice.action_post()
        invoice.action_process_edi_web_services()
        self.assertEqual(invoice.edi_state, 'sent', invoice.edi_document_ids.mapped('error'))
        report = self.env['ir.actions.report']._get_report_from_name(
            'l10n_mx_edi_account_move_report.account_entries_report')
        self.assertEqual(len(report._render(invoice.id)), 2)

        purchase_journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'), ('company_id', '=', invoice.journal_id.company_id.id)])
        invoice2 = invoice.copy({'journal_id': purchase_journal.id, 'move_type': 'in_invoice'})
        invoice.edi_document_ids.write({'move_id': invoice2.id})
        self.assertEqual(len(report._render(invoice2.id)), 2)
