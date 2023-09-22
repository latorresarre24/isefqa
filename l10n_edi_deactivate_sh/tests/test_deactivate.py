import os

from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "edi_deactivate")
class TestDeactivateEdi(TransactionCase):
    def setUp(self):
        super().setUp()
        self.invoice_model = self.env['account.move'].with_context(default_type='in_invoice')
        self.partner_cr = self.env.ref('l10n_cr_edi.test_partner')
        self.company = self.env.user.company_id
        self.crc = self.env.ref('base.CRC')
        self.product = self.env.ref("product.product_product_3")
        self.account_income = self.env.ref("l10n_cr.1_account_account_template_0_410001")
        self.cr_uom_unit = self.env.ref("l10n_cr_edi.uom_unidad")
        self.product_cabis = self.env.ref('l10n_cr_edi_product_cabys.prod_cabys_0111100000100')
        self.product.write({
            "l10n_cr_edi_uom_id": self.cr_uom_unit.id,
            "l10n_cr_edi_code_cabys_id": self.product_cabis.id,
        })

    def test_001_activate_test_mode(self):
        invoice = self.create_invoice()
        self.env.company.l10n_cr_edi_test_env = False
        os.environ['ODOO_STAGE'] = 'staging'
        self.assertEqual(self.invoice_model._get_odoo_sh_environment(), 'staging',
                         "The odoo sh environment should be staging")
        invoice.action_post()
        self.assertTrue(self.env.company.l10n_cr_edi_test_env, "The CR invoicing Test Mode must be Activate")

    def create_invoice(self, inv_type='out_invoice'):
        form = Form(self.invoice_model.with_context(default_move_type=inv_type))
        journal = self.env.ref('l10n_cr_edi.account_journal_1')
        journal.edi_format_ids = False

        form.partner_id = self.partner_cr
        form.currency_id = self.crc
        form.journal_id = journal
        invoice = form.save()
        self.create_invoice_line(invoice)
        return invoice

    def create_invoice_line(self, invoice):
        with Form(invoice) as form:
            with form.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = 450
                line.account_id = self.account_income
                line.tax_ids.clear()
