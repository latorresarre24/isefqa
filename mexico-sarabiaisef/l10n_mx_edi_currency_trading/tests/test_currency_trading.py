import base64
from os.path import join
from lxml.objectify import fromstring

from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.exceptions import ValidationError
from odoo.tools import misc
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestCurrencyTrading(TestMxEdiCommon):
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
        self.env.company.sudo().search([
            ('name', '=', 'ESCUELA KEMPER URGATE')]).write({'name': 'ESCUELA KEMPER URGATE TEST'})
        self.env.user.company_id.write({
            'vat': 'EKU9003173C9',
            'zip': '85134',
            'city': 'Ciudad Obregón',
            'state_id': self.env.ref('base.state_mx_son').id,
            'country_id': self.env.ref('base.mx').id,
            'l10n_mx_edi_pac': 'finkok',
            'l10n_mx_edi_pac_test_env': True,
            'l10n_mx_edi_fiscal_regime': '601',
            'l10n_mx_edi_certificate_ids': [(6, 0, certificate.ids)],
            'name': 'ESCUELA KEMPER URGATE',
        })
        self.namespaces = {
            'cfdi': 'http://www.sat.gob.mx/cfd/3',
            'divisas': 'http://www.sat.gob.mx/divisas',
        }
        self.product = self.env.ref('l10n_mx_edi_currency_trading.usd_currency_product_sale')
        self.product2 = self.env.ref('l10n_mx_edi_currency_trading.usd_currency_product_purchase')
        self.journal = self.env.ref('l10n_mx_edi_currency_trading.currency_operations_journal')
        self.journal.sudo().company_id = self.invoice.company_id
        self.invoice.invoice_date = False
        self.invoice.invoice_line_ids.product_uom_id = self.invoice.invoice_line_ids.product_id.uom_id
        self.invoice.currency_id = self.env.ref('base.MXN')
        isr = self.env['account.account.tag'].search([('name', '=', 'ISR')])
        iva = self.env['account.account.tag'].search([('name', '=', 'IVA')])
        self.invoice.invoice_line_ids.tax_ids.filtered(
            lambda t: t.amount <= 0).invoice_repartition_line_ids.tag_ids |= isr
        self.invoice.invoice_line_ids.tax_ids.filtered(
            lambda t: t.amount > 0).invoice_repartition_line_ids.tag_ids |= iva

    def test_xml_node(self):
        """Validates that the XML node ``<divisas:Divisas>`` is included only
            when the field Exchange operation type is specified on a product,
            and that its content is generated correctly
        """
        # First, creates an invoice without any exchange operation type on any
        # of its products. XML node should not be included
        invoice = self.invoice
        invoice.action_post()
        generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files, invoice.edi_error_message)
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))
        xml = fromstring(generated_files[0])
        self.assertFalse(xml.xpath('Divisa', namespaces={
            'divisas:Divisas': 'http://www.sat.gob.mx/divisas'}), 'The Complement not must be present')

        # Then, set the field on the product and create a new invoice to re-sign.
        # This time, the XML node should be included
        xml_expected = fromstring('''
            <divisas:Divisas xmlns:divisas="http://www.sat.gob.mx/divisas" version="1.0" tipoOperacion="venta"/>''')
        invoice = self.invoice.copy({'journal_id': self.journal.id})
        invoice.invoice_line_ids.write({'product_id': self.product.id})
        invoice.action_post()
        generated_files = self._process_documents_web_services(invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files, invoice.edi_error_message)
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))
        xml = fromstring(generated_files[0])
        error_msg = "The node '<divisas:Divisas> should be present"
        self.assertTrue(xml.Complemento.xpath('divisas:Divisas', namespaces=self.namespaces), error_msg)
        xml_divisas = xml.Complemento.xpath('divisas:Divisas', namespaces=self.namespaces)[0]
        self.assertXmlTreeEqual(xml_divisas, xml_expected)

    def test_ct_types_dont_match(self):
        """Validates that, when an invoice are issued for multiple products,
            and the field Exchange operation type are set but they're not the
            same for all products, an exception is raised
        """
        invoice = self.invoice.copy({'journal_id': self.journal.id})
        invoice_line = invoice.invoice_line_ids.read([])[0]
        invoice_line['product_id'] = self.product.id
        line2 = invoice_line.copy()
        line2.update({'product_id': self.product2.id})
        invoice.line_ids.unlink()
        invoice.invoice_line_ids.unlink()
        invoice.invoice_line_ids = [(0, 0, invoice_line), (0, 0, line2)]
        error_msg = ("This invoice contains products with different exchange operation types.")
        with self.assertRaisesRegex(ValidationError, error_msg):
            invoice.action_post()
