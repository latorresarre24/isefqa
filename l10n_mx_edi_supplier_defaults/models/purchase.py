# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    l10n_mx_edi_payment_method_id = fields.Many2one(
        'l10n_mx_edi.payment.method', string='Payment Way',
        readonly=True, states={'draft': [('readonly', False)]},
        help='Info field to indicate which payment method the supplier will use to invoice the purchase order.')

    def _get_usage_selection(self):
        return self.env['account.move'].fields_get().get('l10n_mx_edi_usage').get('selection')

    l10n_mx_edi_usage = fields.Selection(
        _get_usage_selection, 'Usage',
        help='Info field to indicate which usage the supplier will use to invoice the purchase order.')

    def _get_payment_policy_selection(self):
        return self.env['account.move'].fields_get().get('l10n_mx_edi_payment_policy').get('selection')

    l10n_mx_edi_payment_policy = fields.Selection(
        _get_payment_policy_selection, 'Payment Policy',
        help='Info field to indicate which payment policy the supplier will use to invoice the purchase order.')

    @api.onchange('partner_id', 'company_id')
    def onchange_partner_id(self):
        values = super().onchange_partner_id()
        self.l10n_mx_edi_payment_method_id = self.partner_id.l10n_mx_edi_supplier_payment_method_id
        self.l10n_mx_edi_usage = self.partner_id.l10n_mx_edi_supplier_usage
        self.l10n_mx_edi_payment_policy = self.partner_id.l10n_mx_edi_supplier_payment_policy
        return values
