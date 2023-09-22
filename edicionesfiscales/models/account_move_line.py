from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    cfdi_uuid = fields.Char(string="UUID")
