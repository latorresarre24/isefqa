# License AGPL-3 or later (http://www.gnu.org/licenses/agpl).

from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.tests.common import TransactionCase


class TestSaleCoupon(TransactionCase):

    def setUp(self):
        super().setUp()
        self.sale_id = self.env.ref('sale.sale_order_1').copy()
        self.sale_id.order_line.mapped('product_id').write({'invoice_policy': 'order'})
        self.coupon_program = self.env['coupon.program']
        self.generate_coupon = self.env['coupon.generate.wizard']
        self.apply_coupon = self.env['sale.coupon.apply.code']

    def test_001_coupon_on_order(self):
        sale = self.sale_id
        program = self.coupon_program.create({
            'name': 'Buena Onda',
            'discount_type': 'percentage',
            'discount_percentage': 10.0,
        })

        self.generate_coupon.with_context(active_id=program.id).create({'nbr_coupons': 1}).generate_coupon()
        coupon = program.coupon_ids
        self.apply_coupon.create({'coupon_code': coupon.code}).with_context(active_id=sale.id).process_coupon()

        sale.action_confirm()
        sale._create_invoices()
        self.assertEqual(sale.invoice_status, 'invoiced', 'The lines in the sale are not invoiced')

        total_sale = round(sale.amount_total, 0)
        total_inv = round(sale.order_line.mapped('invoice_lines.move_id').amount_total, 0)
        self.assertTrue(float_is_zero(float_compare(total_inv, total_sale, 2), 2),
                        'The invoice total is different to the sale order. %s != %s' % (total_inv, total_sale))

        reward_line = sale.invoice_ids.invoice_line_ids.filtered(lambda l: not l.price_total)
        invoice_lines = sale.invoice_ids.invoice_line_ids - reward_line
        self.assertTrue(reward_line, 'The reward line amount must be 0')
        # Remove the reward line and check that all lines have amount_discount
        self.assertTrue(all(invoice_lines.mapped('l10n_mx_edi_amount_discount')),
                        'All normal invoice lines must have discount')

    def test_002_coupon_on_order_tax_included(self):
        program = self.coupon_program.create({
            'name': 'Buena Onda',
            'discount_type': 'percentage',
            'discount_percentage': 10.0,
        })
        self.generate_coupon.with_context(active_id=program.id).create({'nbr_coupons': 1}).generate_coupon()
        coupon = program.coupon_ids
        sale = self.sale_id
        tax16 = self.env['account.tax'].create({
            'name': 'IVA(16%) VENTAS INC',
            'description': 'IVA(16%)',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include': True,
        })
        program.discount_line_product_id.taxes_id = [(6, 0, tax16.ids)]
        for line in sale.order_line:
            line.tax_id = [(6, 0, tax16.ids)]

        self.apply_coupon.create({'coupon_code': coupon.code}).with_context(active_id=sale.id).process_coupon()
        sale.order_line.filtered('is_reward_line').tax_id = False
        sale.action_confirm()
        sale._create_invoices()
        self.assertEqual(sale.invoice_status, 'invoiced', 'The lines in the sale are not invoiced')

        total_sale = round(sale.amount_total, 0)
        total_inv = round(sale.order_line.mapped('invoice_lines.move_id').amount_total, 0)
        self.assertTrue(float_is_zero(float_compare(total_inv, total_sale, 2), 2),
                        'The invoice total is different to the sale order. %s != %s' % (total_inv, total_sale))

        reward_line = sale.invoice_ids.invoice_line_ids.filtered(lambda l: not l.price_total)
        invoice_lines = sale.invoice_ids.invoice_line_ids - reward_line
        self.assertTrue(reward_line, 'The reward line amount must be 0')
        # Remove the reward line and check that all lines have amount_discount
        self.assertTrue(all(invoice_lines.mapped('l10n_mx_edi_amount_discount')),
                        'All normal invoice lines must have discount')

    def test_003_promotion_on_order(self):
        """Test an Immediate Promo Program"""
        sale = self.sale_id
        self.coupon_program.create({
            'name': 'Buena Onda',
            'discount_type': 'percentage',
            'discount_percentage': 10.0,
            'discount_apply_on': 'on_order',
            'rule_minimum_amount': 1000,
            'promo_code_usage': 'no_code_needed',
            'program_type': 'promotion_program',
        })
        sale.recompute_coupon_lines()
        sale.action_confirm()
        sale._create_invoices()

        self.assertEqual(sale.invoice_status, 'invoiced', 'The lines in the sale are not invoiced')

        total_sale = round(sale.amount_total, 0)
        total_inv = round(sale.order_line.mapped('invoice_lines.move_id').amount_total, 0)
        self.assertTrue(float_is_zero(float_compare(total_inv, total_sale, 2), 2),
                        'The invoice total is different to the sale order. %s != %s' % (total_inv, total_sale))

        reward_line = sale.invoice_ids.invoice_line_ids.filtered(lambda l: not l.price_total)
        invoice_lines = sale.invoice_ids.invoice_line_ids - reward_line
        self.assertTrue(reward_line, 'The reward line amount must be 0')
        # Remove the reward line and check that all lines have amount_discount
        self.assertTrue(all(invoice_lines.mapped('l10n_mx_edi_amount_discount')),
                        'All normal invoice lines must have discount')

    def test_004_promotion_on_specific_products(self):
        """Test a promotion on specific product"""
        sale = self.sale_id
        order_lines = self.sale_id.order_line
        self.coupon_program.create({
            'name': 'Buena Onda',
            'discount_type': 'percentage',
            'discount_percentage': 10.0,
            'discount_apply_on': 'specific_products',
            'promo_code_usage': 'no_code_needed',
            'program_type': 'promotion_program',
            'discount_specific_product_ids': [(6, 0, (order_lines - order_lines[2]).mapped('product_id').ids)],
        })
        self.coupon_program.create({
            'name': 'Buena Onda',
            'discount_type': 'percentage',
            'discount_percentage': 10.0,
            'discount_apply_on': 'specific_products',
            'promo_code_usage': 'no_code_needed',
            'program_type': 'promotion_program',
            'discount_specific_product_ids': [(6, 0, order_lines[2].product_id.ids)],
        })
        sale.recompute_coupon_lines()
        sale.action_confirm()
        sale._create_invoices()

        self.assertEqual(sale.invoice_status, 'invoiced', 'The lines in the sale are not invoiced')

        self.assertFalse(sale.order_line.mapped('invoice_lines').filtered(lambda l: l.price_total < 0),
                         'Any line must be less than 0.')

        total_sale = round(sale.amount_total, 0)
        total_inv = round(sale.order_line.mapped('invoice_lines.move_id').amount_total, 0)
        self.assertTrue(float_is_zero(float_compare(total_inv, total_sale, 2), 2),
                        'The invoice total is different to the sale order. %s != %s' % (total_inv, total_sale))

    def test_005_fixed_amount_promotions(self):
        """Test fixed promotions: 1. More than one 2. with taxes 3. Discount in its specific line"""
        sale = self.sale_id
        sale.currency_id = self.env.ref('base.MXN')
        product_1 = sale.order_line[0].product_id
        product_2 = sale.order_line[1].product_id
        product_3 = sale.order_line[2].product_id
        promotions = self.coupon_program.create({
            'name': 'Buena Onda Fijo 1',
            'discount_type': 'fixed_amount',
            'discount_fixed_amount': 539.66,
            'promo_code_usage': 'no_code_needed',
            'program_type': 'promotion_program',
            'rule_products_domain': '["&",["sale_ok","=",True],["default_code","=","%s"]]' % product_1.default_code,
        })
        promotions |= self.coupon_program.create({
            'name': 'Buena Onda Fijo 2',
            'discount_type': 'fixed_amount',
            'discount_fixed_amount': 150,
            'promo_code_usage': 'no_code_needed',
            'program_type': 'promotion_program',
            'rule_products_domain': '["&",["sale_ok","=",True],["default_code","=","%s"]]' % product_2.default_code,
        })
        tax16 = self.env['account.tax'].create({
            'name': 'IVA(16%) VENTAS INC',
            'description': 'IVA(16%)',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include': True,
            'tax_group_id': self.env['account.tax.group'].create({'name': 'IVA 16%'}).id,
        })
        for line in sale.order_line:
            line.tax_id = [(6, 0, tax16.ids)]
        sale.recompute_coupon_lines()
        sale.action_confirm()
        sale._create_invoices()
        self.assertEqual(sale.invoice_status, 'invoiced', 'The lines in the sale are not invoiced')
        self.assertFalse(sale.order_line.mapped('invoice_lines').filtered(lambda l: l.price_total < 0),
                         'Any line must be less than 0.')
        total_sale = round(sale.amount_total, 0)
        total_inv = round(sale.order_line.mapped('invoice_lines.move_id').amount_total, 0)
        self.assertTrue(float_is_zero(total_inv - total_sale, 2),
                        'The invoice total is different to the sale order. %s != %s' % (total_inv, total_sale))
        # check the promotion 1
        promotion = promotions[0]
        line = sale.order_line.mapped('invoice_lines').filtered(lambda l, p1=product_1: l.product_id == p1)
        self.assertTrue(
            float_is_zero(line.l10n_mx_edi_total_discount - promotion.discount_fixed_amount, precision_rounding=2))
        # check the promotion 2
        promotion = promotions[1]
        line = sale.order_line.mapped('invoice_lines').filtered(lambda l, p2=product_2: l.product_id == p2)
        self.assertTrue(
            float_is_zero(line.l10n_mx_edi_total_discount - promotion.discount_fixed_amount, precision_rounding=2))
        # Check the the third line that must not have discount
        line = sale.order_line.mapped('invoice_lines').filtered(
            lambda l: not l.l10n_mx_edi_total_discount and l.product_id == product_3)
        self.assertTrue(len(line) == 1, 'A line and just one line is expected to have no discount')

    def test_006_multi_percentages_promotions_different_apply_on(self):
        """Test a combination of general percentage promotion and specific products in just one order."""
        sale = self.sale_id
        self.coupon_program.create({
            'name': 'Buena Onda General',
            'discount_type': 'percentage',
            'discount_percentage': 10.0,
            'discount_apply_on': 'on_order',
            'rule_minimum_amount': 1000,
            'promo_code_usage': 'no_code_needed',
            'program_type': 'promotion_program',
        })
        self.coupon_program.create({
            'name': 'Buena Onda',
            'discount_type': 'percentage',
            'discount_percentage': 50.0,
            'discount_apply_on': 'specific_products',
            'promo_code_usage': 'no_code_needed',
            'program_type': 'promotion_program',
            'discount_specific_product_ids': [(6, 0, self.sale_id.order_line[0].product_id.ids)],
        })
        self.coupon_program.create({
            'name': 'Buena Onda',
            'discount_type': 'percentage',
            'discount_percentage': 20.0,
            'discount_apply_on': 'specific_products',
            'promo_code_usage': 'no_code_needed',
            'program_type': 'promotion_program',
            'discount_specific_product_ids': [(6, 0, self.sale_id.order_line[1].product_id.ids)],
        })
        tax16 = self.env['account.tax'].create({
            'name': 'IVA(16%) VENTAS INC',
            'description': 'IVA(16%)',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
        })
        sale.order_line[0].tax_id = tax16
        sale.recompute_coupon_lines()
        sale.action_confirm()
        sale._create_invoices()

        self.assertEqual(sale.invoice_status, 'invoiced', 'The lines in the sale are not invoiced')

        self.assertFalse(sale.order_line.mapped('invoice_lines').filtered(lambda l: l.price_total < 0),
                         'Any line must be less than 0.')

        total_sale = round(sale.amount_total, 0)
        total_inv = round(sale.order_line.mapped('invoice_lines.move_id').amount_total, 0)
        self.assertTrue(float_is_zero(float_compare(total_inv, total_sale, 2), 2),
                        'The invoice total is different to the sale order. %s != %s' % (total_inv, total_sale))

    def test_007_order_without_coupon_promotions(self):
        """When a Coupon is used it requirers to force calculate the percentage from the fixed amount.
           But this made to calculates the discount percentage from the fixed discount even if the fixed discount
           was calculated originally using the percentage
           Here check if the this calculation is not happening if it is not necessary"""
        sale = self.sale_id
        product = sale.order_line[0].product_id
        sale.order_line.unlink()
        sale.order_line.create({
            'order_id': sale.id,
            'product_id': product.id,
            'product_uom_qty': 29000,
            'price_unit': 0.12,
            'discount': 10.0,
        })
        sale.action_confirm()
        sale._create_invoices()

        self.assertEqual(sale.invoice_status, 'invoiced', 'The lines in the sale are not invoiced')
        total_sale = round(sale.amount_total, 0)
        total_inv = round(sale.order_line.mapped('invoice_lines.move_id').amount_total, 0)
        self.assertTrue(float_is_zero(float_compare(total_inv, total_sale, 2), 2),
                        'The invoice total is different to the sale order. %s != %s' % (total_inv, total_sale))
