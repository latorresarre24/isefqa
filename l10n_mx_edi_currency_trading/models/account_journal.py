from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_mx_edi_currency_trading = fields.Boolean(
        'Currency Trading?', help='Mark this option if the operations for this journal will be for currency trading, '
        'if this field is False will not allow operations for currency products.')
