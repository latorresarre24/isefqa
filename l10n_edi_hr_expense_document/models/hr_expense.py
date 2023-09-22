from odoo import fields, models


class HrExpense(models.Model):
    _inherit = "hr.expense"

    l10n_edi_created_with_dms = fields.Boolean(
        "Created with DMS?", copy=False, help="Is market if the document was created with DMS."
    )
