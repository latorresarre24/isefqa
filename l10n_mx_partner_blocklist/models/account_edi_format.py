
from odoo import _, api, models


class AccountEdiFormat(models.Model):
    _inherit = "account.edi.format"

    @api.model
    def _l10n_mx_edi_check_configuration(self, move):
        res = super()._l10n_mx_edi_check_configuration(move)
        if move.partner_id.l10n_mx_in_blocklist == 'blocked':
            res.append(
                _('This partner is in the block list.'))
        return res
