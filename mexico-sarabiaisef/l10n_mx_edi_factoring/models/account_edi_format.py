from odoo import models


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _l10n_mx_edi_get_payment_cfdi_values(self, move):
        # OVERRIDE
        vals = super()._l10n_mx_edi_get_payment_cfdi_values(move)
        if not move.l10n_mx_edi_factoring_id:
            return vals
        vals['customer_name'] = self._l10n_mx_edi_clean_to_legal_name(
            move.l10n_mx_edi_factoring_id.commercial_partner_id.name)
        return vals
