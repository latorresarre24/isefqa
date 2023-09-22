from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import get_lang


class InvoiceReportPrint(models.TransientModel):
    _name = "invoice.report"
    _description = "Invoice Report Print"

    start_date = fields.Date()
    end_date = fields.Date()
    partner_id = fields.Many2one("res.partner")

    def _build_contexts(self, data):
        if not data["form"]["partner_id"]:
            raise ValidationError(_("Please select a partner"))
        result = {
            "start_date": data["form"]["start_date"] or False,
            "end_date": data["form"]["end_date"] or False,
            "partner": data["form"]["partner_id"][0] or False,
        }
        return result

    def _print_report(self, data):
        return self.env.ref("edicionesfiscales.my_invoices_report_pdf").report_action(self, data=data)

    def check_report(self):
        self.ensure_one()
        data = {
            "ids": self.env.context.get("active_ids", []),
            "model": self.env.context.get("active_model", "ir.ui.menu"),
            "form": self.read(["start_date", "end_date", "partner_id"])[0],
        }
        used_context = self._build_contexts(data)
        data["form"]["used_context"] = dict(used_context, lang=get_lang(self.env).code)
        return self.with_context(discard_logo_check=True)._print_report(data)
