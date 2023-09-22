# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import base64
import logging

from odoo import SUPERUSER_ID, _, api, http
from odoo.http import Controller, request, route

from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.base.models.ir_mail_server import MailDeliveryException

_logger = logging.getLogger(__name__)


class WebsiteCFDI(Controller):
    @route(["/CFDI/<string:ticket_number>"], type="http", auth="public", website=True)
    def get_customer_cfdi(self, ticket_number=None):
        """Getting the invoice with the ticket_number sent and return the link
        to download pdf attached in the invoice"""
        values = {}
        try:
            with request.env.cr.savepoint():
                values = request.env["pos.order"].sudo().get_customer_cfdi(ticket_number)
        # TODO - Check the correct exception
        except Exception as msg_error:
            _logger.error(msg_error)
            values.update(
                {
                    "pac_error": _("Error at the moment to sign the invoice. Please try again in few minutes"),
                    "ticket_number": ticket_number,
                }
            )
        values["action"] = "/CFDI/report/pdf" if values.get("invoice") else "/CFDI/validate_customer"
        return request.render("l10n_mx_edi_website.website_cfdi", values)

    @route(["/CFDI/validate_customer"], type="http", auth="public", website=True)
    def validate_customer(self, **post):
        """Checking the values given to create or update a valid partner and
        generate the invoice"""
        values = request.params
        msg = ""
        vat = post.get("vat", False)
        email = post.get("email", False)
        if not post.get("email") or not post.get("vat"):
            msg = _("Fill all values on the form")
        valid_vat = request.env["res.partner"].check_vat_mx(post.get("vat"))

        msg = valid_vat is False and not msg and _("Invalid vat. The format expected is ABC123456T1B.")

        ticket_number = post.get("ticket_number", False) or values.get("ticket_number")
        zipcode = post.get("zip", False) or values.get("zip")
        name = post.get("name", False) or values.get("name")
        fiscal_regime = post.get("fiscal_regime", False) or values.get("fiscal_regime")
        try:
            with request.env.cr.savepoint():
                values = (
                    values
                    if values.get("error")
                    else request.env["pos.order"]
                    .sudo()
                    .update_partner(ticket_number, vat, email, zipcode, name, fiscal_regime)
                )
        except Exception as msg_error:
            _logger.error(msg_error)
            values["error"] = _("Error at the moment to sign the invoice. Please try again in few minutes")
        except BaseException as msg_error:
            _logger.error(msg_error)
            values["error"] = _("Error at the moment to create the invoice. Please try again in few minutes")
        values["action"] = "/CFDI/validate_customer" if values.get("error") else "/CFDI/report/pdf"
        return request.render("l10n_mx_edi_website.website_cfdi", values)

    @route(["/CFDI/pdf"], type="http", auth="public", website=True)
    def _get_electronic_document_pdf(self, **post):
        """Downloading the pdf attached to the invoice related with the
        ticket_number if This has one"""
        return self._download_attached_file(request.params.get("ticket_number"), "pdf")

    @route(["/CFDI/xml"], type="http", auth="public", website=True)
    def _get_electronic_document_xml(self, **post):
        """Downloading the XML attached to the invoice related with the
        ticket_number, if This has one"""
        return self._download_attached_file(request.params.get("ticket_number"), "xml")

    def _download_attached_file(self, ticket, ftype="pdf"):
        """Downloads the provided file type (PDF or XML) attached to the
        invoice related with the ticket_number, if This has one
        """
        vals = {"ticket_number": ticket}
        try:
            with request.env.cr.savepoint():
                vals = request.env["pos.order"].sudo().get_customer_cfdi(ticket)
        except Exception:
            vals["pac_error"] = _("Error at the moment to sign the invoice. Please try again in few minutes")
            return request.render("l10n_mx_edi_website.website_cfdi", vals)
        except MailDeliveryException as e:
            _logger.error(e)
        with api.Environment.manage():
            env = api.Environment(request.env.cr, SUPERUSER_ID, {})
            inv = vals.get("invoice")
            attachment = (
                inv._get_l10n_mx_edi_signed_edi_document().attachment_id
                if inv and ftype == "xml"
                else env["ir.attachment"].search(
                    [
                        ("res_model", "=", "account.move"),
                        ("res_id", "=", inv.id),
                        ("name", "=", ("%s.pdf" % inv._get_report_base_filename()).replace("/", "_")),
                    ],
                    limit=1,
                )
                if inv
                else False
            )
            if inv and inv.edi_state == "sent" and not attachment and ftype == "pdf":
                report_info = inv.action_invoice_print()
                report = env["ir.actions.report"]._get_report_from_name(
                    report_info.get("report_name")
                    or report_info.get("context").get("report_action").get("report_name")
                )
                # TODO: @luis_t this pylint disabling is to be check. This unassigned expresion is of no use
                # pylint:disable=expression-not-assigned
                report._render(inv.ids)[0]
                attachment = inv and env["ir.attachment"].search(
                    [
                        ("res_model", "=", "account.move"),
                        ("res_id", "=", inv.id),
                        ("name", "=", ("%s.pdf" % inv._get_report_base_filename()).replace("/", "_")),
                    ],
                    limit=1,
                )

            if attachment:
                status, headers, content = (
                    request.env["ir.http"].sudo().binary_content(id=attachment.id, download=True)
                )
                image_base64 = base64.b64decode(content)
                headers.append(("Content-Length", len(image_base64)))
                response = request.make_response(image_base64, headers)
                response.status_code = status
                return response
        vals.update({"action": "/CFDI/validate_customer", "error": "The invoice selected does not have attachments"})
        return request.render("l10n_mx_edi_website.website_cfdi", vals)


class CAuthSignupHome(AuthSignupHome):
    @http.route("/web/signup", type="http", auth="public", website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        """Overwritten to force an email validation when the new user wants to
        be related with a partner already created with possible orders
        related
        """
        res = super().web_auth_signup(*args, **kw)
        if not res.qcontext.get("vat"):
            return res
        error = res.qcontext.get("error")
        msg = _("We sent you an email to complete the registry.")
        if error:
            msg = "%s %s" % (msg, _("If you have not received this mail probably it is %s", error))
        vals = {"message": msg, "login": res.qcontext.get("login")}
        return request.render("web.login", vals)

    def _signup_with_values(self, token, values):
        """Overwritten to add the vat in values used to create the new user"""
        values["vat"] = request.params.get("vat", "")
        return super()._signup_with_values(token, values)
