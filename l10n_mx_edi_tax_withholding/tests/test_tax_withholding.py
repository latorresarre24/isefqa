import base64
from os.path import join

from lxml.objectify import fromstring

from odoo.tests import tagged
from odoo.tools import misc

from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon


@tagged("post_install", "-at_install")
class TestTaxWithholding(TestMxEdiCommon):
    def test_tax_withholding(self):
        """Ensure that XML is generated correctly"""
        payment = self.prepare_payment(11929208.33)
        payment._onchange_tax_withholding()
        payment.action_post()
        payment.move_id.action_process_edi_web_services()
        self.assertEqual(payment.move_id.edi_state, "sent", payment.move_id.message_ids.mapped("body"))
        xml = fromstring(
            base64.decodebytes(
                payment.move_id._get_l10n_mx_edi_signed_edi_document().attachment_id.with_context(bin_size=False).datas
            )
        )
        xml_expected = fromstring(
            misc.file_open(join("l10n_mx_edi_tax_withholding", "tests", "expected.xml")).read().encode("UTF-8")
        )
        xml_expected.attrib["FechaExp"] = xml.attrib["FechaExp"]
        xml_expected.attrib["Sello"] = xml.attrib["Sello"]
        xml_expected.Complemento = xml.Complemento
        self.assertXmlTreeEqual(xml, xml_expected)

    def test_tax_withholding_usd(self):
        """Ensure that XML is generated correctly in usd"""
        payment = self.prepare_payment(497172.85)
        payment.currency_id = self.env["res.currency"].search([("name", "=", "USD")])
        payment.l10n_mx_edi_tax_withholding_rate = 19.8145
        payment._onchange_tax_withholding()
        payment.action_post()
        payment.move_id.action_process_edi_web_services()
        self.assertEqual(payment.move_id.edi_state, "sent", payment.edi_document_ids.mapped("error"))
        xml = fromstring(
            base64.decodebytes(
                payment.move_id._get_l10n_mx_edi_signed_edi_document().attachment_id.with_context(bin_size=False).datas
            )
        )
        xml_expected = fromstring(
            misc.file_open(join("l10n_mx_edi_tax_withholding", "tests", "expected_usd.xml")).read().encode("UTF-8")
        )
        xml_expected.attrib["FechaExp"] = xml.attrib["FechaExp"]
        xml_expected.attrib["Sello"] = xml.attrib["Sello"]
        xml_expected.Complemento = xml.Complemento
        self.assertXmlTreeEqual(xml, xml_expected)

    def prepare_payment(self, amount):
        self.certificate._check_credentials()
        self.partner_a.country_id = self.env.ref("base.us")
        self.partner_a.name = "Google LLC"
        self.env.user.tz = "America/Mexico_City"
        tax = self.env.ref("l10n_mx_edi_tax_withholding.tax_withholding")
        tax.sudo().company_id = self.invoice.company_id
        return self.payment.create(
            {
                "date": "2021-04-15",
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.partner_a.id,
                "payment_method_id": self.env.ref("account.account_payment_method_manual_out").id,
                "journal_id": self.company_data["default_journal_bank"].id,
                "amount": amount,
                "l10n_mx_edi_is_tax_withholding": True,
                "l10n_mx_edi_tax_withholding_id": tax.id,
                "l10n_mx_edi_tax_withholding_amount": 1.00,
                "l10n_mx_edi_tax_withholding_type": "definitivo",
                "l10n_mx_edi_tax_withholding_concept": "Pago de regalias",
            }
        )
