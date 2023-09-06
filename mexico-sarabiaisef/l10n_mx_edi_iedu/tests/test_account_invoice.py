from os.path import join
import base64
from lxml.objectify import fromstring

from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.tools import misc
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestL10nMxEdiInvoiceIEDU(TestMxEdiCommon):

    def test_l10n_mx_edi_invoice_iedu(self):
        self.env['l10n_mx_edi.certificate'].search([]).unlink()
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
            'country_id': self.env.ref('base.mx').id,
            'state_id': self.env.ref('base.state_mx_son').id,
            'l10n_mx_edi_pac': 'finkok',
            'l10n_mx_edi_pac_test_env': True,
            'l10n_mx_edi_fiscal_regime': '601',
            'l10n_mx_edi_certificate_ids': [(6, 0, certificate.ids)],
            'name': 'ESCUELA KEMPER URGATE',
        })
        self.invoice.company_id.company_registry = '5152'  # set institution code
        # set curp because group account invoice can't modify partners
        self.partner_a.write({
            'l10n_mx_edi_curp': 'ROGC001031HJCDRR07',
            'category_id': [(4, self.ref('l10n_mx_edi_iedu.iedu_level_4'))],
        })
        invoice = self.invoice
        isr = self.env['account.account.tag'].search([('name', '=', 'ISR')])
        iva = self.env['account.account.tag'].search([('name', '=', 'IVA')])
        invoice.invoice_line_ids.tax_ids.filtered(lambda t: t.amount <= 0).invoice_repartition_line_ids.tag_ids |= isr
        invoice.invoice_line_ids.tax_ids.filtered(lambda t: t.amount > 0).invoice_repartition_line_ids.tag_ids |= iva

        invoice.invoice_date = False
        invoice.invoice_line_ids.product_uom_id = invoice.invoice_line_ids.product_id.uom_id
        invoice.currency_id = self.env.ref('base.MXN')
        self.env['l10n_mx_edi_iedu.codes'].create({
            'journal_id': invoice.journal_id.id,
            'l10n_mx_edi_iedu_education_level_id': self.ref('l10n_mx_edi_iedu.iedu_level_4'),
            'l10n_mx_edi_iedu_code': 'ES4-728L-3018'
        })
        invoice.invoice_line_ids.write({
            'l10n_mx_edi_iedu_id': self.partner_a.id,
        })
        invoice.action_post()
        generated_files = self._process_documents_web_services(invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files, invoice.edi_error_message)
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))
        xml = fromstring(generated_files[0])
        namespaces = {
            'iedu': "http://www.sat.gob.mx/iedu"
        }
        iedu = xml.Conceptos.Concepto.ComplementoConcepto.xpath('//iedu:instEducativas', namespaces=namespaces)
        self.assertTrue(iedu, 'Iedu complement was not added correctly')

    def test_l10n_mx_edi_xsd(self):
        """Verify that xsd file is downloaded"""
        self.invoice.company_id._load_xsd_attachments()
        xsd_file = self.ref('l10n_mx_edi.xsd_cached_iedu_xsd')
        self.assertTrue(xsd_file, 'XSD file not load')
