import base64
from os.path import join

from odoo.tests.common import TransactionCase
from odoo.tools import misc


class TestPurchase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.rule = self.env.ref("l10n_edi_document.edi_document_rule")
        self.invoice_xml = misc.file_open(join("l10n_mx_edi_document", "tests", "invoice.xml")).read().encode("UTF-8")
        self.partner_purchase = self.env.ref("base.res_partner_2")
        self.partner_purchase.vat = "EKU9003173C9"
        self.product = self.env.ref("product.product_product_5")
        self.env.company.vat = "XAXX010101000"

    def test_check_wizard_attach_xml_in_purchase(self):
        journal = self.env["account.journal"].search([("type", "=", "purchase")], limit=1)
        account = journal.default_account_id.copy({})
        journal = journal.copy()
        purchase = self.env["purchase.order"].create(
            {
                "partner_id": self.partner_purchase.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "name": self.product.name,
                            "product_id": self.product.id,
                            "product_qty": 1,
                            "product_uom": self.product.uom_id.id,
                            "price_unit": self.product.list_price,
                        },
                    )
                ],
            }
        )
        purchase.button_confirm()
        self.assertEqual(len(purchase.invoice_ids), 0)
        ctx = {"active_model": purchase._name, "active_id": purchase.id}
        wizard = self.env["attach.xmls.wizard"].with_context(**ctx).create({})
        wizard.journal_id = journal
        wizard.account_id = account
        files = {"invoice.xml": (b"data:text/xml;base64," + base64.b64encode(self.invoice_xml)).decode()}
        wizard_result = wizard.check_xml(files)
        last_invoice = self.env["account.move"].search([], order="id DESC", limit=1)
        self.assertEqual(wizard_result, {"wrongfiles": {}, "invoices": {"invoice.xml": last_invoice.id}})
        self.assertEqual(len(purchase.invoice_ids), 1)
        self.assertEqual(
            purchase.invoice_ids.invoice_line_ids.mapped("account_id"), account, "Account not assigned correctly."
        )
