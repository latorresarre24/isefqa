from os.path import join
import base64

from odoo.tests.common import TransactionCase, Form
from odoo.tools import misc


class TestProductRefundAccounts(TransactionCase):
    """Test cases for l10n_mx_edi_product_refund_account module"""

    def setUp(self):
        super().setUp()
        certificate = self.env['l10n_mx_edi.certificate'].create({
            'content': base64.encodebytes(
                misc.file_open(join('l10n_mx_edi', 'demo', 'pac_credentials', 'certificate.cer'), 'rb').read()),
            'key': base64.encodebytes(
                misc.file_open(join('l10n_mx_edi', 'demo', 'pac_credentials', 'certificate.key'), 'rb').read()),
            'password': '12345678a',
        })
        certificate._check_credentials()
        self.env.user.company_id.write({
            'vat': 'EKU9003173C9',
            'zip': '85134',
            'city': 'Ciudad Obregón',
            'country_id': self.env.ref('base.mx').id,
            'state_id': self.env.ref('base.state_mx_son').id,
            'l10n_mx_edi_pac': 'finkok',
            'l10n_mx_edi_pac_test_env': True,
            'l10n_mx_edi_fiscal_regime': '601',
            'l10n_mx_edi_certificate_ids': [(6, 0, certificate.ids)],
        })
        self.invoice = self.env['account.move'].create({
            'partner_id': self.env.ref('base.res_partner_12').id,
            'journal_id': self.env['account.journal'].search([('code', '=', 'INV')], limit=1).id,
        })
        accounts = self.env['account.account']
        self.income_account = accounts.create({
            'code': '101.01.999',
            'name': 'Account Test Income',
            'deprecated': False,
            'user_type_id': self.env.ref(
                'account.data_account_type_other_income').id,
        })
        self.expense_account = accounts.create({
            'code': '101.02.999',
            'name': 'Account Test Expense',
            'deprecated': False,
            'user_type_id': self.env.ref(
                'account.data_account_type_expenses').id,
        })
        self.product_w_account = self.env['product.product'].create({
            'name': 'Product with account',
            'type': 'consu',
            'property_account_income_refund_id': self.expense_account.id,
            'property_account_expense_refund_id': self.income_account.id,
        })
        self.product_w_category = self.env['product.product'].create({
            'name': 'Product with category',
            'type': 'consu',
            'categ_id': self.env['product.category'].create({
                'name': 'Category with account',
                'property_account_income_refund_id': self.expense_account.id,
                'property_account_expense_refund_id': self.income_account.id,
            }).id,
        })
        self.product_default = self.env['product.product'].create({
            'name': 'Product with category',
            'type': 'consu',
            'categ_id': self.env['product.category'].create({
                'name': 'Category without account',
                'property_account_income_categ_id': self.income_account.id,
                'property_account_expense_categ_id': self.expense_account.id,
            }).id
        })

    def test_001_out_refund(self):
        self.invoice.write({
            'move_type': 'out_refund',
        })
        line = self.env['account.move.line'].new({
            'move_id': self.invoice.id,
            'product_id': self.product_w_account.id,
        })
        line._onchange_product_id()
        self.assertEqual(line.account_id, self.expense_account)
        line = self.env['account.move.line'].new({
            'move_id': self.invoice.id,
            'product_id': self.product_w_category.id,
        })
        line._onchange_product_id()
        self.assertEqual(line.account_id, self.expense_account)
        line = self.env['account.move.line'].new({
            'move_id': self.invoice.id,
            'product_id': self.product_default.id,
        })
        line._onchange_product_id()
        self.assertEqual(line.account_id, self.income_account)

    def test_002_in_refund(self):
        invoice = self.invoice.copy({
            'move_type': 'in_refund',
            'journal_id': self.env['account.journal'].search([
                ('type', '=', 'purchase')], limit=1).id,
        })
        line = self.env['account.move.line'].new({
            'move_id': invoice.id,
            'product_id': self.product_w_account.id,
        })
        line._onchange_product_id()
        self.assertEqual(line.account_id, self.income_account)
        line = self.env['account.move.line'].new({
            'move_id': invoice.id,
            'product_id': self.product_w_category.id,
        })
        line._onchange_product_id()
        self.assertEqual(line.account_id, self.income_account)
        line = self.env['account.move.line'].new({
            'move_id': invoice.id,
            'product_id': self.product_default.id,
        })
        line._onchange_product_id()
        self.assertEqual(line.account_id, self.expense_account)

    def test_003_product_refund(self):
        """Ensure that product in refund is the same that assigned in the product."""
        invoice = self.invoice.copy({
            'move_type': 'out_refund',
        })
        invoice.partner_id = self.env.ref('base.res_partner_12')
        self.product_w_account.unspsc_code_id = self.env.ref('product_unspsc.unspsc_code_01010101')
        move_form = Form(invoice)
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product_w_account
            line_form.name = self.product_w_account.name
            line_form.price_unit = 100.00
            line_form.quantity = 1
            line_form.account_id = self.product_w_account.product_tmpl_id.get_product_accounts()['expense']
            line_form.product_uom_id = self.product_w_account.uom_id
        move_form.save()
        invoice.action_post()
        refund = self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({
                'refund_method': 'refund',
                'journal_id': self.env['account.journal'].search(
                    [('code', '=', 'INV')], limit=1).id,
            })
        result = refund.reverse_moves()
        refund = self.env['account.move'].browse(result['res_id'])
        self.assertEqual(self.expense_account, refund.invoice_line_ids.account_id, 'Account not assigned correctly')
