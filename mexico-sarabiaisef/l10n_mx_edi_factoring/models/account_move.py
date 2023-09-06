from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_mx_edi_factoring_id = fields.Many2one(
        "res.partner", "Financial Factor", copy=False, readonly=True,
        states={'posted': [('readonly', False)]}, tracking=True,
        help="This invoice will be paid by this Financial factoring agent.")
