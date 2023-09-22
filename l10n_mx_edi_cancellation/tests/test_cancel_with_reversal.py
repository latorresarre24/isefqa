from datetime import timedelta

from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.tests import tagged

from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestAccountPaymentReversal(TestMxEdiCommon):
    def setUp(self):
        super().setUp()
        self.company = self.env.user.company_id
        self.company.sudo().search([
            ('name', '=', 'ESCUELA KEMPER URGATE')]).write({'name': 'ESCUELA KEMPER URGATE TEST'})
        self.company.name = 'ESCUELA KEMPER URGATE'
        self.certificate._check_credentials()

    def _invoice_preparation(self, invoice):
        invoice.invoice_date = False
        invoice.currency_id = self.env.ref('base.MXN')
        invoice.invoice_line_ids.product_uom_id = invoice.invoice_line_ids.product_id.uom_id
        isr = self.env['account.account.tag'].search([('name', '=', 'ISR')])
        iva = self.env['account.account.tag'].search([('name', '=', 'IVA')])
        invoice.invoice_line_ids.tax_ids.filtered(lambda t: t.amount <= 0).invoice_repartition_line_ids.tag_ids |= isr
        invoice.invoice_line_ids.tax_ids.filtered(lambda t: t.amount > 0).invoice_repartition_line_ids.tag_ids |= iva

    def test_cancel_01(self):
        """Try to cancel an invoice with case 01"""
        self.company.l10n_mx_edi_pac = 'finkok'
        invoice = self.invoice
        self._invoice_preparation(invoice)
        invoice.action_post()
        generated_files = self._process_documents_web_services(invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files, invoice.edi_error_message)
        self.assertEqual(invoice.edi_state, "sent", invoice.edi_error_message)
        invoice.l10n_mx_edi_cancellation = '01'
        invoice.button_cancel_posted_moves()
        self._process_documents_web_services(invoice, {'cfdi_3_3'})
        error_message = invoice.edi_error_message
        invoice.button_draft()
        invoice.button_cancel()
        invoice2 = invoice.copy({'l10n_mx_edi_origin': '04|%s' % invoice.l10n_mx_edi_cfdi_uuid})
        invoice2.action_post()
        self._process_documents_web_services(invoice2, {'cfdi_3_3'})
        self.assertEqual(invoice2.edi_state, "sent", invoice2.edi_error_message)
        self._process_documents_web_services(invoice, {'cfdi_3_3'})
        self.assertTrue(invoice.edi_state in ("cancelled", "to_cancel"), invoice.edi_error_message)
        self.assertNotEqual(invoice.edi_error_message, error_message, "Error not updated")

    def _test_cancel_02_sw(self):
        """Try to cancel an invoice with case 02 with Smart Web"""
        self.company.l10n_mx_edi_pac = 'sw'
        self.company.l10n_mx_edi_pac_username = 'luis_t@vauxoo.com'
        self.company.l10n_mx_edi_pac_password = 'VAU.2021.SW'
        invoice = self.invoice
        self._invoice_preparation(invoice)
        invoice.action_post()
        self._process_documents_web_services(invoice, {'cfdi_3_3'})
        self.assertEqual(invoice.edi_state, "sent", invoice.edi_error_message)
        invoice.l10n_mx_edi_cancellation = '02'
        invoice.button_cancel_posted_moves()
        self._process_documents_web_services(invoice, {'cfdi_3_3'})
        self.assertEqual(invoice.edi_state, "cancelled", invoice.edi_error_message)

    def test_cancel_in_draft(self):
        """Ensure that draft invoice is cancelled correctly"""
        invoice = self.invoice
        invoice.button_cancel()
        self.assertEqual(invoice.state, 'cancel', invoice.message_ids.mapped('body'))

    def test_invoice_reversal(self):
        """Ensure that draft invoice is cancelled correctly"""
        date_mx = self.env['l10n_mx_edi.certificate'].sudo().get_mx_current_datetime()
        invoice = self.invoice
        invoice.invoice_date = date_mx - timedelta(days=40)
        invoice.action_post()
        invoice.l10n_mx_edi_cancellation = '03'
        with self.assertRaisesRegex(UserError, 'This option only could be used on invoices out of period.'):
            invoice.button_cancel_with_reversal()

        invoice.search([('state', '=', 'draft')]).unlink()
        invoice.company_id.fiscalyear_lock_date = date_mx.replace(day=1)
        invoice.button_cancel_with_reversal()
        self.assertTrue(invoice.reversal_move_id, invoice.message_ids.mapped('body'))
