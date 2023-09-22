# Part of Odoo. See LICENSE file for full copyright and licensing details.

from os import path

from lxml import objectify
from odoo.tools import misc
from odoo.tests.common import Form

from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestMxEdiFactoring(TestMxEdiCommon):

    def setUp(self):
        super().setUp()
        self.certificate._check_credentials()
        self.invoice.invoice_date = False
        self.invoice.invoice_line_ids.product_uom_id = self.invoice.invoice_line_ids.product_id.uom_id
        self.invoice.currency_id = self.env.ref('base.MXN')

        isr = self.env['account.account.tag'].search([('name', '=', 'ISR')])
        iva = self.env['account.account.tag'].search([('name', '=', 'IVA')])
        self.invoice.invoice_line_ids.tax_ids.filtered(
            lambda t: t.amount <= 0).invoice_repartition_line_ids.tag_ids |= isr
        self.invoice.invoice_line_ids.tax_ids.filtered(
            lambda t: t.amount > 0).invoice_repartition_line_ids.tag_ids |= iva

    def test_factoring(self):
        invoice = self.invoice
        invoice.company_id.sudo().name = 'YourCompany Factoring'
        invoice.action_post()
        generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files, invoice.edi_error_message)
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))
        factoring = invoice.partner_id.sudo().create({
            'name': 'Financial Factoring',
            'country_id': self.env.ref('base.mx').id,
            'type': 'invoice',
            'zip': invoice.company_id.zip,
        })
        invoice.partner_id.sudo().commercial_partner_id.l10n_mx_edi_factoring_id = factoring
        invoice.l10n_mx_edi_factoring_id = factoring
        # Register the payment
        ctx = {'active_model': 'account.move', 'active_ids': invoice.ids, 'force_ref': True}
        bank_journal = self.env['account.journal'].search([('type', '=', 'bank'),
                                                           ('company_id', '=', invoice.company_id.id)], limit=1)
        payment = Form(self.env['account.payment.register'].with_context(**ctx))
        payment.payment_date = invoice.date
        payment.journal_id = bank_journal
        payment.amount = invoice.amount_total
        payment.l10n_mx_edi_payment_method_id = self.env.ref('l10n_mx_edi.payment_method_efectivo')
        payment.save().action_create_payments()
        payment = invoice._get_reconciled_payments()

        self.assertTrue(invoice.l10n_mx_edi_factoring_id, 'Financial Factor not assigned')
        payment.action_l10n_mx_edi_force_generate_cfdi()
        generated_files = self._process_documents_web_services(payment, {'cfdi_3_3'})
        xml_expected_str = misc.file_open(path.join(
            'l10n_mx_edi_factoring', 'tests', 'expected_payment.xml')).read().encode('UTF-8')
        xml_expected = objectify.fromstring(xml_expected_str)
        self.assertTrue(generated_files, payment.edi_error_message)
        xml = objectify.fromstring(generated_files[0])
        xml_expected.Complemento = xml.Complemento
        self.assertXmlTreeEqual(xml, xml_expected)
