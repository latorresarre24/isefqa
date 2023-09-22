from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_mx_edi_reversal_customer_journal_id = fields.Many2one(
        'account.journal', related='company_id.l10n_mx_edi_reversal_customer_journal_id', readonly=False,
        domain=[('type', '=', 'sale')], string='Customer Journal',
        help='If set, this journal will be used on reversals for customer invoices out of period.')
    l10n_mx_edi_reversal_supplier_journal_id = fields.Many2one(
        'account.journal', related='company_id.l10n_mx_edi_reversal_supplier_journal_id', readonly=False,
        domain=[('type', '=', 'purchase')], string='Vendor Journal',
        help='If set, this journal will be used on reversals for vendo bills out of period.')
