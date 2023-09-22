# Copyright 2018 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    l10n_mx_edi_generate_advance = fields.Boolean(
        'Generate Advance?', default=False,
        help='This payment has a difference in customer favor, then, if this option is marked, in the payment '
        'validation will try to generate an advance. To generate the advance, first will to ensure that the customer '
        'do not have credit pending, in that case, although you mark this option the advance will not be generated.')

    def action_create_payments(self):
        if self.payment_difference:
            context = self._context.copy()
            context['payment_difference'] = self.payment_difference
            new_self = self.with_context(**context)
            return super(
                AccountPaymentRegister, new_self).action_create_payments()
        return super().action_create_payments()
