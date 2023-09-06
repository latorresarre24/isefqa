from odoo import _, models
from odoo.tests.common import Form


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _create_invoices(self, grouped=False, final=False, date=None):
        moves = super()._create_invoices(grouped=grouped, final=final, date=date)

        if not (self.mapped('applied_coupon_ids') or self.mapped('no_code_promo_program_ids') or
                self.mapped('code_promo_program_id')):
            return moves

        for move in moves:
            move_form = Form(move)
            for line in range(0, len(move.invoice_line_ids)):
                with move_form.invoice_line_ids.edit(line) as line_form:
                    line_form.l10n_mx_edi_amount_discount = line_form.l10n_mx_edi_amount_discount
            move_form.save()
        return moves


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_invoice_line(self, **optional_values):
        """Coupons for the order are considered.
        The price unit in te coupon line is updated to 0, and the discount is
        applied in the other lines."""
        res = super()._prepare_invoice_line(**optional_values)
        order = self.order_id
        program = order.applied_coupon_ids.mapped('program_id')
        program += order.no_code_promo_program_ids + order.code_promo_program_id
        avoid_delivery = order.company_id.l10n_mx_edi_not_delivery_discount

        if self.is_reward_line and program.filtered(
                lambda p: p.discount_apply_on in ('on_order', 'specific_products') or
                p.discount_type == 'fixed_amount'):
            res.update({
                'name': _('%s\nTotal Discount:%s\nCoupon:%s') % (
                    res.get('name'),
                    res.get('price_unit', 0),
                    order.applied_coupon_ids.display_name or ''),
                'price_unit': 0,
            })
            return res

        if not self.is_reward_line and program and \
           program == program.filtered(lambda p: p.discount_type == 'fixed_amount'):
            # if all programs are fixed_amount
            discount = 0
            tax_group_id = self.env['account.tax.group'].search([('name', 'ilike', 'IVA')])
            for fixed_program in program.filtered(lambda p: p._get_valid_products(self.product_id)):
                lines = order.order_line.filtered(lambda l: fixed_program._get_valid_products(l.product_id))
                total = sum(lines.mapped('price_total'))
                factor = self.price_total / total if total else 1
                amount = fixed_program.discount_fixed_amount
                tax = self.tax_id.filtered(lambda t, tax_group_id=tax_group_id: t.type_tax_use == 'sale'
                                           and t.amount_type == 'percent' and t.tax_group_id in tax_group_id)
                if tax:
                    amount = amount if tax[0].price_include else amount / (tax[0].amount / 100 + 1)
                discount += amount * factor
            res.update({
                'l10n_mx_edi_total_discount': discount,
            })

        elif not self.is_reward_line and program.filtered(lambda p: p.discount_apply_on == 'on_order' or
                                                          p.discount_type == 'fixed_amount'):
            if 'is_delivery' in self._fields and self.is_delivery and avoid_delivery:
                return res
            delivery_product = order.order_line.filtered('is_delivery') if 'is_delivery' in self._fields else False
            delivery_amount = delivery_product.price_total if delivery_product and avoid_delivery else 0
            reward = order.order_line.filtered('is_reward_line')
            total = sum((order.order_line - reward).mapped('price_total')) - delivery_amount
            factor = abs(sum(reward.mapped('price_total'))) / total if total else 1
            res.update({
                'l10n_mx_edi_amount_discount': factor * self.price_unit,
            })
        elif not self.is_reward_line and program.filtered(lambda p: p.discount_apply_on == 'specific_products' and
                                                          self.product_id in p.discount_specific_product_ids):
            program_line = program.filtered(lambda p: self.product_id in p.discount_specific_product_ids)
            lines = order.order_line.filtered(
                lambda l: l.product_id in program_line.mapped('discount_specific_product_ids'))
            reward = order.order_line.filtered(
                lambda l: l.is_reward_line and l.product_id == program_line.discount_line_product_id)
            factor = abs(sum(reward.mapped('price_total'))) / sum(
                lines.mapped('price_total')) if self.price_total else 1
            res.update({
                'l10n_mx_edi_amount_discount': factor * self.price_unit,
            })
        return res
