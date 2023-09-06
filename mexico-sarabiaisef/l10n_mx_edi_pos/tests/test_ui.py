from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "pos")
class TestPos(HttpCase):
    def setUp(self):
        super().setUp()
        self.uid = self.env.ref("base.user_admin")
        self.pos_config = self.env.ref("point_of_sale.pos_config_main")
        self.customer = self.env.ref("base.res_partner_12")
        self.customer.vat = "VCO120608KR7"
        self.product = self.env.ref("product.product_product_12")

    def test_01_autoinvoice(self):
        """Check that a PoS order is automatically invoiced when made to a partner with VAT"""
        self.pos_config.open_session_cb()
        # Create an order to a partner with VAT
        self.start_tour(
            url_path="/pos/ui?config_id=%d" % self.pos_config.id,
            tour_name="mx_pos_invoice_order",
            login=self.env.user.login,
        )

        # Order should've been automatically invoiced
        pos_order = self.pos_config.current_session_id.order_ids[:1]
        self.assertEqual(pos_order.state, "invoiced")
        invoice = pos_order.account_move
        self.assertRecordValues(
            records=invoice,
            expected_values=[
                {
                    "partner_id": self.customer.id,
                    "state": "posted",
                    "pos_order_ids": pos_order.ids,
                    "invoice_origin": pos_order.name,
                    "amount_total": 241.0,
                },
            ],
        )
        self.assertEqual(invoice.invoice_line_ids.product_id, self.product)
        self.assertEqual(invoice.invoice_line_ids.quantity, 2.0)

        # There should be (only) one picking created
        pickings = pos_order.picking_ids
        self.assertRecordValues(
            records=pickings,
            expected_values=[
                {
                    "origin": pos_order.name,
                    "partner_id": self.customer.id,
                    "picking_type_id": pos_order.picking_type_id.id,
                    "state": "done",
                }
            ],
        )
        self.assertEqual(pickings.move_line_ids.product_id, self.product)
        self.assertEqual(pickings.move_line_ids.qty_done, 2.0)
