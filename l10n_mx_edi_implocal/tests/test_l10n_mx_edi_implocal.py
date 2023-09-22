import os

from lxml.objectify import fromstring

from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.tools import misc
from odoo.tests.common import Form
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestL10nMxEdiInvoiceImpLocal(TestMxEdiCommon):
    def setUp(self):
        super().setUp()
        self.certificate._check_credentials()
        self.tag_model = self.env['account.account.tag']
        self.tax_local = self.tax_16.copy({
            'name': 'LOCAL(10%) VENTAS',
            'amount': 10.000000,
        })
        for rep_line in self.tax_16.invoice_repartition_line_ids | self.tax_16.refund_repartition_line_ids:
            rep_line.tag_ids |= self.env.ref('l10n_mx.tag_iva')
        for rep_line in self.tax_10_negative.invoice_repartition_line_ids | self.tax_10_negative.refund_repartition_line_ids:  # noqa
            rep_line.tag_ids |= self.env.ref('l10n_mx.tag_isr')
        for rep_line in self.tax_local.invoice_repartition_line_ids | self.tax_local.refund_repartition_line_ids:
            rep_line.tag_ids |= self.env.ref('l10n_mx_edi_implocal.account_tax_local')
        self.product = self.env.ref("product.product_product_2")
        self.product.taxes_id = [self.tax_16.id, self.tax_10_negative.id, self.tax_local.id]
        self.product.default_code = "TEST"
        self.product.unspsc_code_id = self.ref('product_unspsc.unspsc_code_01010101')
        self.xml_expected = misc.file_open(os.path.join(
            'l10n_mx_edi_implocal', 'tests', 'expected.xml')).read().encode('UTF-8')

    def test_l10n_mx_edi_implocal(self):
        """Test local tax for 10%"""
        invoice = self.invoice
        invoice.company_id.sudo().name = 'YourCompany MX'
        invoice.currency_id = self.env.ref('base.MXN')
        invoice.invoice_date = False
        invoice.line_ids.unlink()
        invoice.invoice_line_ids.unlink()
        invoice_line = invoice.invoice_line_ids.new({
            'product_id': self.product.id,
            'quantity': 1,
            'move_id': invoice.id,
        })
        invoice_line._onchange_product_id()
        invoice_line_dict = invoice_line._convert_to_write(invoice_line._cache)
        invoice_line_dict['price_unit'] = 450
        invoice.invoice_line_ids = [(0, 0, invoice_line_dict)]
        invoice.action_post()
        generated_files = self._process_documents_web_services(invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files, invoice.edi_error_message)
        self.assertEqual(invoice.edi_state, "sent", invoice.edi_document_ids.mapped('error'))
        xml = fromstring(generated_files[0])
        namespaces = {'implocal': 'http://www.sat.gob.mx/implocal'}
        comp = xml.Complemento.xpath('//implocal:ImpuestosLocales',
                                     namespaces=namespaces)
        self.assertTrue(comp, 'Complement to implocal not added correctly')
        xml_expected = fromstring(self.xml_expected)
        self.assertXmlTreeEqual(xml, xml_expected)

    def test_l10n_mx_edi_implocal2lines(self):
        """Ensure that module works with 2 lines"""
        invoice = self.invoice
        invoice.company_id.sudo().name = 'YourCompany MX'
        invoice.currency_id = self.env.ref('base.MXN')
        invoice.invoice_date = False
        invoice.line_ids.unlink()
        invoice.invoice_line_ids.unlink()
        invoice_line = invoice.invoice_line_ids.new({
            'product_id': self.product.id,
            'quantity': 1,
            'move_id': invoice.id,
        })
        invoice_line._onchange_product_id()
        invoice_line_dict = invoice_line._convert_to_write(invoice_line._cache)
        invoice_line_dict['price_unit'] = 450
        invoice.invoice_line_ids = [(0, 0, invoice_line_dict)]
        invoice_line = invoice.invoice_line_ids.new({
            'product_id': self.product.id,
            'quantity': 1,
            'move_id': invoice.id,
        })
        invoice_line._onchange_product_id()
        invoice_line_dict = invoice_line._convert_to_write(invoice_line._cache)
        invoice_line_dict['price_unit'] = 450
        invoice.invoice_line_ids = [(0, 0, invoice_line_dict)]
        invoice.action_post()
        self._process_documents_web_services(invoice, {'cfdi_3_3'})
        self.assertEqual(invoice.edi_state, "sent", invoice.edi_document_ids.mapped('error'))

    def test_l10n_mx_edi_withholding_implocal(self):
        """Test local tax for -10%"""
        invoice = self.invoice
        self.tax_local.amount = -10.0
        invoice.company_id.sudo().name = 'YourCompany MX'
        invoice.currency_id = self.env.ref('base.MXN')
        invoice.invoice_date = False
        invoice.line_ids.unlink()
        invoice.invoice_line_ids.unlink()
        invoice_line = invoice.invoice_line_ids.new({
            'product_id': self.product.id,
            'quantity': 1,
            'move_id': invoice.id,
        })
        invoice_line._onchange_product_id()
        invoice_line_dict = invoice_line._convert_to_write(invoice_line._cache)
        invoice_line_dict['price_unit'] = 450
        invoice.invoice_line_ids = [(0, 0, invoice_line_dict)]
        invoice.action_post()
        generated_files = self._process_documents_web_services(invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files, invoice.edi_error_message)
        self.assertEqual(invoice.edi_state, "sent", invoice.edi_document_ids.mapped('error'))

    def test_l10n_mx_edi_implocal_refund(self):
        invoice = self.invoice
        invoice.move_type = 'out_refund'
        invoice.invoice_date = False
        invoice.company_id.sudo().name = 'YourCompany MX'
        invoice.currency_id = self.env.ref('base.MXN')
        invoice.line_ids.unlink()
        invoice.invoice_line_ids.unlink()
        move_form = Form(invoice)
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product
            line_form.quantity = 1
            line_form.price_unit = 1000
            line_form.tax_ids.clear()
            line_form.tax_ids.add(self.tax_16)
            line_form.tax_ids.add(self.tax_local)
        move_form.save()
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product
            line_form.quantity = 1
            line_form.price_unit = 1000
            line_form.tax_ids.clear()
            line_form.tax_ids.add(self.tax_16)
        move_form.save()
        invoice.action_post()
        invoice.action_process_edi_web_services()
        self.assertEqual(invoice.edi_state, "sent", invoice.edi_document_ids.mapped('error'))
