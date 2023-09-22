from odoo.tests import TransactionCase, tagged


@tagged("mrp")
class TestMrpProduction(TransactionCase):
    def setUp(self):
        super().setUp()
        self.mrp_production = self.env.ref("mrp.mrp_production_4")

    def test_01_compute_stock_move_amount(self):
        amount = self.mrp_production.stock_move_pt
        self.assertEqual(amount, 1)
