import base64
from os.path import join
from odoo.tools import misc
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestAttachPurchaseDocument(TransactionCase):

    def setUp(self):
        super().setUp()
        self.invoice_xml = misc.file_open(join(
            'l10n_edi_purchase_document', 'tests', 'invoice.xml')).read().encode('UTF-8')
        self.partner_purchase = self.env.ref('base.res_partner_2')
        self.product = self.env.ref('product.product_product_5')

    def test_01_check_wizard_attach_xml_in_purchase(self):
        journal = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)
        account = journal.default_account_id.copy({})
        journal = journal.copy({'name': 'Test'})
        purchase = self.env['purchase.order'].create({
            'partner_id': self.partner_purchase.id,
            'order_line': [
                (0, 0, {
                    'name': self.product.name,
                    'product_id': self.product.id,
                    'product_qty': 1,
                    'product_uom': self.product.uom_id.id,
                    'price_unit': self.product.list_price,
                })
            ],
        })
        purchase.button_confirm()
        ctx = {'active_model': purchase._name, 'active_id': purchase.id}
        wizard = self.env['attach.xmls.wizard'].with_context(**ctx).create({})
        wizard.journal_id = journal
        wizard.account_id = account
        files = {'invoice.xml': 'data:text/xml;base64,' + str(base64.b64encode(self.invoice_xml))}
        wizard_result = wizard.check_xml(files)
        self.assertNotEqual(wizard_result, {'wrongfiles': {}, 'invoices': {}})
        self.assertEqual(len(wizard_result['invoices']), 1)
        self.assertEqual(purchase.invoice_ids.journal_id, journal, 'Journal not assigned correctly.')
        self.assertEqual(purchase.invoice_ids.invoice_line_ids.mapped('account_id'), account,
                         'Account not assigned correctly.')
