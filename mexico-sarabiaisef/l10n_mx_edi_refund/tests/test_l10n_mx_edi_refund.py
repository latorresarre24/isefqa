from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestL10nMxEdiRefund(TestMxEdiCommon):

    def setUp(self):
        super().setUp()
        self.certificate._check_credentials()
        self.refund_model = self.env['account.move.reversal']
        self.payment_inmediate = self.env.ref('account.account_payment_term_immediate')
        self.payment_method = self.env.ref('l10n_mx_edi.payment_method_transferencia')

    def test_l10n_mx_edi_invoice_refund(self):
        # -----------------------
        # Testing move reversal to verify value selected from wizard of
        # credit note
        # -----------------------
        self.invoice.action_post()

        self.invoice.l10n_mx_edi_cfdi_uuid = '123456789'
        refund = self.refund_model.with_context(
            active_model="account.move",
            active_ids=self.invoice.ids).create({
                'refund_method': 'modify',
                'date': self.invoice.invoice_date,
                'l10n_mx_edi_payment_method_id': self.payment_method.id,
                'l10n_mx_edi_usage': 'G02',
                'l10n_mx_edi_origin_type': '03',
                'journal_id': self.invoice.journal_id.id,
            })
        result = refund.reverse_moves()
        refund_id = result['res_id']
        refund = self.env['account.move'].browse(refund_id)
        refund_type = refund.l10n_mx_edi_origin.split('|')[0]
        self.assertEqual(self.payment_inmediate, refund.invoice_payment_term_id,
                         'Payment Term in refund is different to selected from the wizard of credit note')
        self.assertEqual(self.payment_method, refund.l10n_mx_edi_payment_method_id,
                         'Payment Method in refund is different to selected from the wizard of credit note')
        self.assertEqual('G02', refund.l10n_mx_edi_usage,
                         'Use in refund is different to selected from the wizard of credit note')
        self.assertEqual('03', refund_type,
                         'Invoice origin type is different to selected from the wizard of credit note')
