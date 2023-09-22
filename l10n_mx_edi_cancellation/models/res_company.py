from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_mx_edi_reversal_customer_journal_id = fields.Many2one(
        'account.journal', domain=[('type', '=', 'sale')], help='If set, this journal will be used on reversals for '
        'customer invoices out of period.')
    l10n_mx_edi_reversal_supplier_journal_id = fields.Many2one(
        'account.journal', domain=[('type', '=', 'purchase')], help='If set, this journal will be used on reversals '
        'for vendo bills out of period.')
