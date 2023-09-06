from odoo.tests import Form, TransactionCase, tagged


@tagged("invoice")
class TestInvoice(TransactionCase):
    def setUp(self):
        super().setUp()
        self.customer = self.env.ref("base.res_partner_3")
        self.product1 = self.env.ref("product.product_product_5")
        self.start_date = "2022-05-20"
        self.end_date = "2022-06-01"

    def create_invoice(self, invoice_date=None, partner=None, **line_kwargs):
        if partner is None:
            partner = self.customer
        invoice = Form(self.env["account.move"].with_context(default_move_type="out_invoice"))
        invoice.partner_id = partner
        if invoice_date:
            invoice.invoice_date = invoice_date
        invoice = invoice.save()
        self.create_inv_line(invoice, **line_kwargs)
        return invoice

    def create_inv_line(self, invoice, product=None, quantity=1, price=150):
        if product is None:
            product = self.product1
        with Form(invoice) as inv:
            with inv.invoice_line_ids.new() as line:
                line.product_id = product
                line.quantity = quantity
                line.price_unit = price

    def create_invoice_report(self):
        invoice_report_print = Form(self.env["invoice.report"].sudo())
        invoice_report_print.partner_id = self.customer
        invoice_report_print.start_date = self.start_date
        invoice_report_print.end_date = self.end_date
        invoice_report_print = invoice_report_print.save()
        return invoice_report_print

    def test_01_create(self):
        invoice = self.create_invoice()
        self.assertIn(self.customer, invoice.message_partner_ids)

    def test_02_line_get(self):
        invoice_report = self.env["report.edicionesfiscales.report_my_invoices"]
        invoice = self.create_invoice("2022-05-30")
        invoice_report_print = self.create_invoice_report()
        data = invoice_report_print.check_report()
        invoice_dict = invoice_report._get_report_values(invoice, data=data["data"])
        self.assertTrue(data)
        self.assertTrue(invoice_dict)
