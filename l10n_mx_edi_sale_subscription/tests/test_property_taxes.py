from lxml.objectify import fromstring

from odoo.tests import tagged

from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon


@tagged("post_install", "-at_install")
class TestL10nMxEdiSubscription(TestMxEdiCommon):
    def test_property_taxes(self):
        """Ensure that invoice from subscription have property taxes"""
        self.certificate._check_credentials()
        subscription = (
            self.env.ref("sale_subscription.subscription_portal_22")
            .sudo()
            .copy({"company_id": self.env.user.company_id.id})
        )
        subscription.template_id.payment_mode = "draft_invoice"
        subscription.recurring_invoice_line_ids.write({"l10n_mx_edi_property_taxes": "310002291001310002292001"})
        subscription.recurring_invoice_line_ids.mapped("product_id").write(
            {"unspsc_code_id": self.ref("product_unspsc.unspsc_code_01010101")}
        )
        subscription.recurring_invoice_line_ids.mapped("product_id.uom_id").write(
            {"unspsc_code_id": self.ref("product_unspsc.unspsc_code_MON")}
        )
        subscription.generate_recurring_invoice()
        invoice = (
            self.env["account.move"]
            .sudo()
            .search([("invoice_line_ids.subscription_id", "in", subscription.ids)], limit=1)
        )
        self.assertTrue(invoice.invoice_line_ids.mapped("l10n_mx_edi_property_taxes"), "Property taxes not assigned")
        invoice.action_post()
        generated_files = self._process_documents_web_services(invoice, {"cfdi_3_3"})
        self.assertTrue(generated_files, invoice.edi_error_message)
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped("body"))
        xml = fromstring(generated_files[0])
        self.assertEqual(
            xml.Conceptos.Concepto.CuentaPredial.get("Numero"),
            "310002291001310002292001",
            "CuentaPredial is not in the CFDI.",
        )
