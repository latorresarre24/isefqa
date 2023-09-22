# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import base64
from os.path import join

from odoo import fields
from odoo.tests import tagged
from odoo.tools import misc

from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon


@tagged("post_install", "-at_install")
class TestTicketInvoicing(TestMxEdiCommon):
    def setUp(self):
        super().setUp()
        self.iva_tag = self.env["account.account.tag"].search([("name", "=", "IVA")])
        self.tax_16.invoice_repartition_line_ids.write({"tag_ids": [(6, 0, [self.iva_tag.id])]})
        certificate = self.env["l10n_mx_edi.certificate"].create(
            {
                "content": base64.encodebytes(
                    misc.file_open(join("l10n_mx_edi", "demo", "pac_credentials", "certificate.cer"), "rb").read()
                ),
                "key": base64.encodebytes(
                    misc.file_open(join("l10n_mx_edi", "demo", "pac_credentials", "certificate.key"), "rb").read()
                ),
                "password": "12345678a",
            }
        )
        certificate._check_credentials()
        self.env.company.sudo().search([("name", "=", "ESCUELA KEMPER URGATE")]).write(
            {"name": "ESCUELA KEMPER URGATE TEST"}
        )
        self.env.user.company_id.write(
            {
                "vat": "EKU9003173C9",
                "zip": "85134",
                "city": "Ciudad Obregón",
                "state_id": self.env.ref("base.state_mx_son").id,
                "country_id": self.env.ref("base.mx").id,
                "l10n_mx_edi_pac": "finkok",
                "l10n_mx_edi_pac_test_env": True,
                "l10n_mx_edi_fiscal_regime": "601",
                "l10n_mx_edi_certificate_ids": [(6, 0, certificate.ids)],
                "name": "ESCUELA KEMPER URGATE",
            }
        )
        self.order_obj = self.env["pos.order"]
        self.partner = self.env["res.partner"]
        self.cash_payment_method = self.env["pos.payment.method"].create(
            {
                "name": "Cash",
                "receivable_account_id": self.company_data["default_account_receivable"].id,
                "journal_id": self.company_data["default_journal_cash"].id,
                "company_id": self.env.company.id,
            }
        )
        self.pos_config = self.env["pos.config"].create(
            {
                "name": "Main",
                "journal_id": self.company_data["default_journal_sale"].id,
                "invoice_journal_id": self.company_data["default_journal_sale"].id,
                "payment_method_ids": [(4, self.cash_payment_method.id)],
            }
        )
        self.led_lamp = self.env["product.product"].create(
            {
                "name": "LED Lamp",
                "available_in_pos": True,
                "list_price": 90,
                "unspsc_code_id": self.ref("product_unspsc.unspsc_code_39112102"),
                "taxes_id": [(6, 0, self.tax_16.ids)],
            }
        )
        self.vat_valid = "VA&111017CG9"
        self.partner1 = self.env["res.partner"].create({"name": "Partner 1"})
        self.partner4 = self.partner.create(
            {
                "name": "Partner 4",
                "vat": self.vat_valid,
            }
        )
        self.known_email = "info(at)vauxoo.com"
        self.unknown_email = "somebody@vauxoo.com"
        self.vat_new = "ACI010425FU7"
        self.unregistered_email = "somebody-not@vauxoo.com"
        self.create_orders()

    def create_orders(self):
        """Simulation of sales coming from the interface,
        even after closing the session
        """
        fromproduct = object()

        def compute_tax(product, price, taxes=fromproduct, qty=1):
            if taxes is fromproduct:
                taxes = product.taxes_id
            currency = self.pos_config.pricelist_id.currency_id
            taxes = taxes.compute_all(price, currency, qty, product=product)["taxes"]
            untax = price * qty
            return untax, sum(tax.get("amount", 0.0) for tax in taxes)

        # I click on create a new session button
        self.pos_config.open_session_cb()

        current_session = self.pos_config.current_session_id

        untax, atax = compute_tax(self.led_lamp, 9)
        without_partner_order = {
            "data": {
                "amount_paid": untax + atax,
                "amount_return": 0,
                "amount_tax": atax,
                "amount_total": untax + atax,
                "creation_date": fields.Datetime.to_string(fields.Datetime.now()),
                "fiscal_position_id": False,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "discount": 0,
                            "id": 42,
                            "pack_lot_ids": [],
                            "price_unit": 9,
                            "price_subtotal": 9,
                            "price_subtotal_incl": 9,
                            "product_id": self.led_lamp.id,
                            "qty": 1,
                            "tax_ids": [(6, 0, self.led_lamp.taxes_id.ids)],
                        },
                    ]
                ],
                "name": "Order 10042-003-0014",
                "partner_id": False,
                "pricelist_id": self.partner1.property_product_pricelist.id,
                "pos_session_id": current_session.id,
                "sequence_number": 2,
                "ticket_number": "22345",
                "statement_ids": [
                    [
                        0,
                        0,
                        {
                            "account_id": (self.env.user.partner_id.property_account_receivable_id.id),
                            "amount": untax + atax,
                            "payment_method_id": self.pos_config.payment_method_ids[0].id,  # noqa
                            "name": fields.Datetime.now(),
                            "statement_id": current_session.statement_ids[0].id,
                        },
                    ]
                ],
                "uid": "10042-003-0014",
                "user_id": self.env.uid,
            },
            "id": "10042-003-0014",
            "to_invoice": False,
        }

        # I create an order on an open session
        without_ids = self.order_obj.create_from_ui([without_partner_order])
        self.ticket_no_partner = self.order_obj.browse([pos["id"] for pos in without_ids])

        without_partner_order["id"] = "10042-003-0015"
        without_partner_order["data"].update(
            {"partner_id": self.partner4.id, "ticket_number": "223456", "name": "Order 10042-003-0015"}
        )
        with_ids = self.order_obj.create_from_ui([without_partner_order])
        self.not_invoiced_valid_partner = self.order_obj.browse([pos["id"] for pos in with_ids])

        without_partner_order.update(
            {
                "id": "10042-003-0016",
                "to_invoice": True,
            }
        )
        without_partner_order["data"].update({"ticket_number": "223457", "name": "Order 10042-003-0016"})

        invoiced_ids = self.order_obj.create_from_ui([without_partner_order])
        self.invoiced_ticket = self.order_obj.browse([pos["id"] for pos in invoiced_ids])

    def test_001_invoiced_ticket(self):
        """Tests case: a ticket has already an invoice."""
        res = self.order_obj.get_customer_cfdi(self.invoiced_ticket.l10n_mx_edi_ticket_number)
        self.assertEqual(res.get("invoice"), self.invoiced_ticket.account_move)

    def test_002_not_invoiced_valid_partner(self):
        """Test case: A ticket has partner and the data of the partner is
        correctly set, so an invoice is created and returned.
        """
        res = self.order_obj.get_customer_cfdi(self.not_invoiced_valid_partner.l10n_mx_edi_ticket_number)
        invoice = res.get("invoice")
        self.assertEqual(invoice, self.not_invoiced_valid_partner.account_move)

    def test_003_no_partner(self):
        """Test case: A ticket has no partner, an error must be returned on the
        partner key.
        """
        res = self.order_obj.get_customer_cfdi(self.ticket_no_partner.l10n_mx_edi_ticket_number)
        self.assertEqual(res.get("partner"), "No partner")

    def test_004_invoice_by_vat(self):
        """Test case: A ticket has no partner but customer data already in the
        system.
        """
        res = self.order_obj.update_partner(
            self.ticket_no_partner.l10n_mx_edi_ticket_number, self.vat_valid, self.known_email
        )
        self.assertEqual(res.get("invoice"), self.ticket_no_partner.account_move)

    def test_005_invoice_by_vat(self):
        """Test case: A ticket has no partner but customer data already in the
        system but email provided is different from the one found in the
        database.
        """
        res = self.order_obj.update_partner(
            self.ticket_no_partner.l10n_mx_edi_ticket_number, self.vat_valid, self.unknown_email
        )
        self.assertEqual(res.get("invoice"), self.ticket_no_partner.account_move)

    def test_006_invoice_new_customer(self):
        """Test case: A ticket has no partner and there is no data matching
        on any partner with the one given on the form.
        """
        res = self.order_obj.update_partner(
            self.ticket_no_partner.l10n_mx_edi_ticket_number, self.vat_new, self.unregistered_email
        )
        new_invoice = res.get("invoice")
        new_partner = self.partner.search([("email", "=", "somebody-not@vauxoo.com"), ("vat", "=", "ACI010425FU7")])
        self.assertEqual(new_invoice.partner_id, new_partner)

    def test_007_invoice_incomplete_data(self):
        """Test case: A ticket has no partner but the data supplied on the form
        is incomplete and there is no matching record on the database.
        """
        res = self.order_obj.update_partner(
            self.ticket_no_partner.l10n_mx_edi_ticket_number, email=self.unregistered_email
        )
        self.assertEqual(res.get("vat"), "Required")
        self.assertTrue(res.get("error"))

    def test_008_invoice_sale(self):
        """Test case: a ticket number is given and the customer data on the
        order is valid to be invoiced.
        """
        ticket_number = self.not_invoiced_valid_partner.l10n_mx_edi_ticket_number
        res = self.order_obj.invoice_sale(ticket_number)
        self.assertTrue(res)

    def test_009_invoice_session_closed(self):
        """Test case: a ticket number is given, but the customer completes the
        form after the session has been closed
        """
        ticket_number = self.ticket_no_partner.l10n_mx_edi_ticket_number
        session = self.pos_config.current_session_id
        session.action_pos_session_closing_control()
        self.assertEqual(session.l10n_mx_edi_pac_status, "signed", session.message_ids.mapped("body"))
        self.order_obj.update_partner(
            self.ticket_no_partner.l10n_mx_edi_ticket_number,
            email="felix@vauxoo.com",
            vat="AABF800614HI0",
            zipcode="86400",
            name="FELIX MANUEL ANDRADE BALLADO",
            fiscal_regime="616",
        )
        invoice = self.order_obj.invoice_sale(ticket_number)
        generated_files = self._process_documents_web_services(invoice, {"cfdi_3_3"})
        self.assertTrue(generated_files, invoice.edi_error_message)
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped("body"))
        self.assertEqual(invoice.state, "posted", "Invoice should be posted")

    def test_010_misconfigured_and_retry(self):
        """Test case: The instance is misconfigured when closing the session,
        then configuration is fixed and the session is re-signed
        """
        # Misconfigure the instance and close, so SAT signing process fails
        session = self.pos_config.current_session_id
        vat = session.company_id.vat
        session.company_id.vat = False
        session.action_pos_session_closing_control()
        self.assertEqual(session.l10n_mx_edi_pac_status, "retry", session.message_ids.mapped("body"))

        # Re-configure instance and retry the signing process
        session.company_id.vat = vat
        session._l10n_mx_edi_retry()
        self.assertEqual(session.l10n_mx_edi_pac_status, "signed", session.message_ids.mapped("body"))
