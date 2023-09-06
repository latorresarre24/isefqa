from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPartnerDefault(TestMxEdiCommon):

    def test_partner_default(self):
        """Ensure that partner defaults are assigned"""
        invoice = self.invoice
        partner = invoice.partner_id.commercial_partner_id.sudo()
        partner.l10n_mx_edi_payment_method_id = self.env.ref('l10n_mx_edi.payment_method_tarjeta_de_credito')
        partner.l10n_mx_edi_usage = 'G03'
        invoice._onchange_partner_id()
        self.assertEqual(
            invoice.l10n_mx_edi_payment_method_id, partner.l10n_mx_edi_payment_method_id,
            'Payment method not assigned correctly')
        self.assertEqual(
            invoice.l10n_mx_edi_usage, partner.l10n_mx_edi_usage, 'Usage not assigned correctly')
