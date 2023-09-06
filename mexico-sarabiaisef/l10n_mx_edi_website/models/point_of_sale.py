# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import _, api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    l10n_mx_edi_ticket_number = fields.Char(
        string="Ticket Number",
        index=True,
        copy=False,
        help="Unique number used to identify and download this ticket in our site",
    )

    _sql_constraints = [
        ("ticket_number_unique", "unique(l10n_mx_edi_ticket_number,company_id)", "The ticket number must be unique")
    ]

    @api.model
    def _order_fields(self, ui_order):
        """Adding the new ticket_number"""
        res = super()._order_fields(ui_order)
        res["l10n_mx_edi_ticket_number"] = ui_order["ticket_number"]
        return res

    @api.model
    def get_customer_cfdi(self, ticket_number):
        """Three things can happen in this method:

        a) The given ticket number already has an invoice. If this happens,
        a dictionary with an `invoice` key will be returned.

        b) The ticket number has a partner with valid data, but the ticket has
        no invoice. If this happens, the process of generating the invoice of
        the pos ticket will be triggered, and a dictionary with a `invoice` key
        will be returned.

        c) The ticket has no partner and has no invoice. This will return
        a dictionary with a `partner` key set to `No partner`, indicating that
        a partner was not found for that ticket. This will result in triggering
        the process of requiring input data from the user.

        :param ticket_number: the ticket number to invoice.
        :type ticket_number: str

        :return: a dictionary containing the result of the process
        :rtype: Dictionary
        """
        order = self.search(
            [
                ("l10n_mx_edi_ticket_number", "=", ticket_number),
            ],
            limit=1,
        )
        partner = order.partner_id
        # We are gonna use the partner in the order if this has a vat and this
        # is not generic
        valid_partner = partner if (partner.vat and partner.vat != "XEXX010101000") else False
        invoice = order.account_move
        if invoice.edi_state != "sent":
            invoice = valid_partner and self.invoice_sale(ticket_number)
        values = {
            "ticket_number": ticket_number,
            "partner": not partner.vat and _("No partner"),
            "invoice": invoice,
            "email": partner.email,
        }
        return values

    @api.model
    def update_partner(self, ticket_number, vat=None, email=None, zipcode=None, name=None, fiscal_regime=None):
        """Used to parse the data received from the form where the email and
        the VAT are captured.

        Several things can happen here:

        a) If a partner is found with the data provided by the customer in
        the website form with matching VAT and Email, it will link the pos
        order to the user and will invoice it.

        b) If a partner is found with the data provided by the customer in
        the website form with a matching VAT but not matching Email, it will
        create a new contact to the matching partner, link it to the order and
        invoice the order.

        c) If a partner is found with the email provided but the customer has
        no VAT, it will be required to capture the VAT on the input form.

        d) If no customer found with any of the data provided it will create
        a new partner, link it to the order and invoice it.

        :param ticket_number: The ticket to relate to the partner.
        :type ticket_number: str

        :param vat: The VAT captured in the website form on which the
        customer can be created or searched by.
        :type vat: str

        :param email: The email captured in the website form on which the
        customer can be created or seached by.
        :type email: str

        :return: A dictionary with error or the invoice created.
        :rtype: dict
        """
        values = {"ticket_number": ticket_number}
        order = self.search(
            [
                ("l10n_mx_edi_ticket_number", "=", ticket_number),
            ],
            limit=1,
        )
        if not order:
            values["vat"] = _("Required")
            values["error"] = _("The order was not found. Please check the code")
            return values
        self = self.with_company(order.company_id)
        domain = [("vat", "=", vat)] if vat else [("email", "=ilike", email)]
        partner_obj = self.env["res.partner"]
        partner = partner_obj.search(domain, limit=1)
        if partner and order.partner_id.vat and order.partner_id.vat != partner.vat:
            values["error"] = _(
                "The VAT in the order is different to the vat filled out by you. Please check it and try again"
            )
            return values

        if partner and order.partner_id and (order.partner_id != partner):
            order.partner_id.write({"parent_id": partner.id, "email": email})
            values["invoice"] = (
                order.account_move if order.account_move.edi_state == "sent" else self.invoice_sale(ticket_number)
            )
            return values
        if partner:
            contact = partner_obj
            if (partner.email or "").lower() != (email or "").lower() and not partner_obj.search_count(
                [("email", "=ilike", email), ("parent_id", "=", partner.id)]
            ):
                contact = partner_obj.create(
                    {
                        "name": email,
                        "email": email,
                        "parent_id": partner.id,
                    }
                )
            if order.partner_id:
                order.partner_id.write(
                    {
                        "vat": partner.vat or vat,
                        "email": partner.email or email,
                    }
                )
            else:
                order.write(
                    {
                        "partner_id": contact.id or partner.id,
                    }
                )
            values["invoice"] = (
                order.account_move if order.account_move.edi_state == "sent" else self.invoice_sale(ticket_number)
            )
            return values
        if vat:
            new_data = {
                "country_id": self.env.ref("base.mx").id,
                "name": order.partner_id.name or name or email or vat,
                "vat": vat,
                "email": (
                    order.partner_id.email and email and "%s;%s" % (order.partner_id.email, email) or email or ""
                ),
                "zip": zipcode,
                "l10n_mx_edi_fiscal_regime": fiscal_regime,
            }
            new_partner = order.partner_id or partner_obj.create(new_data)
            (order.partner_id or order).write(order.partner_id and new_data or {"partner_id": new_partner.id})
            values["invoice"] = (
                order.account_move if order.account_move.edi_state == "sent" else self.invoice_sale(ticket_number)
            )
            return values
        values["vat"] = _("Required")
        values["error"] = _("You are not registered, VAT is required")
        return values

    def _get_invoice_from_close_session(self):
        """Get the invoice after the session was closed. When this happens it
        is needed to generate a new session to generate a new order with an
        invoice valid to generate the xml signed

        :return: The invoice generated if the order is in a valid range of time
        :rtype: account.move()
        """

        move_vals = self._prepare_invoice_vals()
        new_move = self._create_invoice(move_vals)
        self.write({"account_move": new_move.id, "state": "invoiced"})
        new_move.sudo().with_company(self.company_id)._post()

        # Prepare refund
        refund = (
            self.env["account.move.reversal"]
            .with_context(active_ids=new_move.ids, active_model="account.move")
            .create(
                {
                    "refund_method": "cancel",
                    "reason": _("PoS Refund"),
                    "date": new_move.invoice_date,
                    "journal_id": new_move.journal_id.id,
                }
            )
        )
        refund = refund.reverse_moves()
        if self.l10n_mx_edi_uuid:
            new_move.reversal_move_id.write({"l10n_mx_edi_origin": "07|%s" % self.l10n_mx_edi_uuid})
        return new_move

    @api.model
    def _get_invoice_from_open_session(self):
        """Generate the needed invoice from an order with an open session in a
        valid range of date"""
        self.action_pos_order_invoice()
        return self.account_move

    @api.model
    def invoice_sale(self, ticket_number):
        """Given a ticket_number it will trigger all the invoicing process for
        the given partner on the `pos.order`.

        :param ticket_number: The number of ticket to invoice.
        :type ticket_number: Integer

        :return: The new invoice just created.
        :rtype: account.move()
        """
        order = self.search(
            [
                ("l10n_mx_edi_ticket_number", "=", ticket_number),
            ],
            limit=1,
        )
        invoice = order.account_move
        session = order.session_id
        if invoice.state == "draft":
            invoice.with_context(**{"disable_after_commit": True}).action_post()
        if invoice and invoice.l10n_mx_edi_cfdi_request in ("on_invoice", "on_refund") and invoice.edi_state != "sent":
            invoice.action_process_edi_web_services()
        if invoice:
            return invoice
        if session.state in ("closed", "closing_control"):
            return order._get_invoice_from_close_session()
        return order._get_invoice_from_open_session()
