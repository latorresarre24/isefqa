from odoo import models


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _create_payment(self, add_payment_vals=None):
        # Inherited to set the payment method from an acquirer's journal to the payment
        if add_payment_vals is None:  # to fix lint flake8 B006
            add_payment_vals = {}
        add_payment_vals[
            "l10n_mx_edi_payment_method_id"
        ] = self.acquirer_id.journal_id.l10n_mx_edi_payment_method_id.id
        return super()._create_payment(add_payment_vals)
