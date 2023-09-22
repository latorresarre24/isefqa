from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _reverse_move_vals(self, default_values, cancel=True):
        vals = super()._reverse_move_vals(default_values=default_values, cancel=cancel)
        if self.move_type not in ['out_refund', 'out_invoice', 'in_refund', 'in_invoice']:
            return vals
        for line in vals.get('line_ids', []):
            if not line[2].get('product_id'):
                continue
            n_line = self.env['account.move.line'].new({
                'move_id': line[2].get('move_id'),
                'product_id': line[2].get('product_id'),
            })
            n_line.with_context(l10n_mx_force_move_type=self.move_type.replace(
                'invoice', 'refund'))._onchange_product_id()
            line[2]['account_id'] = n_line.account_id.id or line[2]['account_id']
        return vals


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_computed_account(self):
        move_type = self._context.get('l10n_mx_force_move_type') or self.move_id.move_type
        if move_type not in ('out_refund', 'in_refund') or not self.product_id:
            return super()._get_computed_account()
        fpos = self.move_id.fiscal_position_id
        accounts = self.product_id.product_tmpl_id.get_product_accounts(fpos)
        account_map = {
            'out_refund': 'income_refund',
            'in_refund': 'expense_refund',
        }
        return accounts[account_map[move_type]]
