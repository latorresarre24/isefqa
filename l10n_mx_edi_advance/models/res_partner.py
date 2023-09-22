from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_mx_advance_selection(self):
        return self.env['res.company'].fields_get().get('l10n_mx_edi_advance').get('selection')

    l10n_mx_edi_advance = fields.Selection(
        _get_mx_advance_selection, 'Process for Advances',
        help='Use this option if you want to force to use a specific advance process for this customer.')
