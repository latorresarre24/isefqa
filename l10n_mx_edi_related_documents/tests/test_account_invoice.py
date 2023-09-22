# Copyright 2020 Vauxoo
# # License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.tests import tagged
from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon


@tagged('edi_related_documents', 'post_install', '-at_install')
class TestL10nMxEdiRelatedDocuments(TestMxEdiCommon):

    def setUp(self):
        super().setUp()
        self.certificate._check_credentials()

    def test_01_get_related_documents(self):
        """Testing that when creating an invoice and it refund, and checking that the invoice id is on the field
        l10n_mx_edi_related_document_ids' of the refund, and the refund id is on the field
        'l10n_mx_edi_related_document_ids_inverse' of the invoice.
        """
        invoice = self._prepare_invoice()
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        invoice.action_process_edi_web_services()
        self.assertEqual(invoice.edi_state, "sent", invoice.edi_document_ids.mapped('error'))
        invoice.refresh()

        refund = self.env['account.move.reversal'].with_context(
            active_ids=invoice.ids, active_model='account.move').create({
                'refund_method': 'refund',
                'reason': 'Testing',
                'date': invoice.invoice_date,
                'journal_id': self.invoice.journal_id.id,
            })
        result = refund.reverse_moves()
        refund = self.env['account.move'].browse(result['res_id'])
        refund.action_post()
        refund.l10n_mx_edi_get_related_documents()

        self.assertIn(invoice.id, refund.l10n_mx_edi_related_document_ids.ids)
        self.assertIn(refund.id, invoice.l10n_mx_edi_related_document_ids_inverse.ids)

    def test_02_get_related_documents_error(self):
        """Testing that when a record has on it field 'l10n_mx_edi_origin' a CDFI with a wrong pattern it will raise
        an error.
        """
        invoice = self._prepare_invoice()
        invoice.action_post()
        invoice.refresh()
        self.assertEqual(invoice.state, "posted")
        invoice.action_process_edi_web_services()
        self.assertEqual(invoice.edi_state, "sent", invoice.edi_document_ids.mapped('error'))

        invoice.write({
            'l10n_mx_edi_origin': '01|Testing',
        })
        invoice.l10n_mx_edi_get_related_documents()
        message = ("The number: Testing doesn't match the pattern of a CFDI we are unable to look for this related "
                   "document.")
        self.assertIn(message, invoice.message_ids[0].body)

    def _prepare_invoice(self):
        invoice = self.invoice
        invoice.currency_id = self.env.ref('base.MXN')
        invoice.invoice_date = False
        invoice.line_ids.unlink()
        invoice.invoice_line_ids.unlink()
        invoice_line = invoice.invoice_line_ids.new({
            'product_id': self.product.id,
            'quantity': 1,
            'move_id': invoice.id,
        })
        invoice_line._onchange_product_id()
        invoice_line_dict = invoice_line._convert_to_write(invoice_line._cache)
        invoice_line_dict['price_unit'] = 450
        invoice.invoice_line_ids = [(0, 0, invoice_line_dict)]
        return invoice
