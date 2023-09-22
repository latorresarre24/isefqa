from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    property_discount_account_id = fields.Many2one(
        "account.account",
        company_dependent=True,
        string="Discount Account",
        domain=[["internal_type", "=", "other"], ["deprecated", "=", False]],
    )
