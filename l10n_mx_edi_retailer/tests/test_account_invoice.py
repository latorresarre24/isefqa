from lxml.objectify import fromstring

from odoo.tests import tagged
from odoo.tests.common import Form

from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon


@tagged("post_install", "-at_install")
class TestL10nMxEdiInvoiceAirline(TestMxEdiCommon):
    def setUp(self):
        super().setUp()
        self.certificate._check_credentials()
        self.invoice.invoice_date = False
        self.invoice.invoice_line_ids.product_uom_id = self.invoice.invoice_line_ids.product_id.uom_id
        self.invoice.currency_id = self.env.ref("base.MXN")

        isr = self.env["account.account.tag"].search([("name", "=", "ISR")])
        iva = self.env["account.account.tag"].search([("name", "=", "IVA")])
        self.invoice.invoice_line_ids.tax_ids.filtered(
            lambda t: t.amount <= 0
        ).invoice_repartition_line_ids.tag_ids |= isr
        self.invoice.invoice_line_ids.tax_ids.filtered(
            lambda t: t.amount > 0
        ).invoice_repartition_line_ids.tag_ids |= iva

    def test_invoice_retailer(self):
        """Basic invoice flow for an invoice retailer"""
        date_mx = self.certificate.sudo().get_mx_current_datetime().date()
        retailer_wizard = (
            self.env["x_l10n_mx_edi.retailer.wizard"].with_context(default_x_invoice_id=self.invoice.id).create({})
        )
        retailer_wizard = Form(retailer_wizard)
        retailer_wizard.x_status = "original"
        retailer_wizard.x_purchase_order_date = date_mx
        retailer_wizard.x_purchase_contact_name = "Azure Interior"
        retailer_wizard.x_special_service_type = "off_invoice"
        retailer_wizard.x_delivery = "P00011"
        retailer_wizard.x_delivery_date = date_mx
        retailer_wizard = retailer_wizard.save()
        retailer_set_action = self.env.ref("l10n_mx_edi_retailer.set_wizard_l10n_mx_edi_retailer_values")
        retailer_set_action.with_context(active_id=retailer_wizard.id).run()
        self.invoice.action_post()
        generated_files = self._process_documents_web_services(self.invoice, {"cfdi_3_3"})
        self.assertTrue(generated_files, self.invoice.edi_error_message)
        self.assertEqual(self.invoice.edi_state, "sent", self.invoice.message_ids.mapped("body"))
        xml = fromstring(generated_files[0])
        namespaces = {"detallista": "http://www.sat.gob.mx/detallista"}
        comp = xml.Complemento.xpath("//detallista:detallista", namespaces=namespaces)
        self.assertTrue(comp, "Complement to detallista not added correctly")

    def test_invoice_retailer_incomplete(self):
        """Case without contact name"""
        self.certificate._check_credentials()
        date_mx = self.certificate.sudo().get_mx_current_datetime().date()
        retailer_wizard = (
            self.env["x_l10n_mx_edi.retailer.wizard"].with_context(default_x_invoice_id=self.invoice.id).create({})
        )
        retailer_wizard = Form(retailer_wizard)
        retailer_wizard.x_status = "original"
        retailer_wizard.x_purchase_order_date = date_mx
        retailer_wizard.x_special_service_type = "off_invoice"
        retailer_wizard.x_delivery = "P00011"
        retailer_wizard.x_delivery_date = date_mx
        retailer_wizard = retailer_wizard.save()
        retailer_set_action = self.env.ref("l10n_mx_edi_retailer.set_wizard_l10n_mx_edi_retailer_values")
        retailer_set_action.with_context(active_id=retailer_wizard.id).run()
        self.invoice.action_post()
        generated_files = self._process_documents_web_services(self.invoice, {"cfdi_3_3"})
        self.assertTrue(generated_files)
        self.assertEqual(self.invoice.edi_state, "sent", self.invoice.message_ids.mapped("body"))
        xml = fromstring(generated_files[0])
        namespaces = {"detallista": "http://www.sat.gob.mx/detallista"}
        comp = xml.Complemento.xpath("//detallista:detallista", namespaces=namespaces)
        self.assertTrue(comp, "Complement to detallista not added correctly")
