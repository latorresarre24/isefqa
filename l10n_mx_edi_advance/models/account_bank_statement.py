
from odoo import models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def reconcile(self, lines_vals_list, to_check=False, allow_partial=False):
        res = super(AccountBankStatementLine, self.with_context(l10n_mx_edi_manual_reconciliation=False)).reconcile(
            lines_vals_list=lines_vals_list,
            to_check=to_check, allow_partial=allow_partial)

        if self.l10n_mx_edi_cfdi_request not in ('on_invoice', 'on_refund'):
            return res

        for payment in res.mapped('line_ids.payment_id'):
            if payment.company_id.l10n_mx_edi_product_advance_id.property_account_income_id in payment.move_line_ids.mapped('account_id'):  # noqa
                payment.l10n_mx_edi_generate_advance = True
            is_required = payment.l10n_mx_edi_advance_is_required(payment.amount)
            if is_required:
                payment._l10n_mx_edi_generate_advance(is_required)
        return res
