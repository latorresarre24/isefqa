# Copyright 2019 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from os.path import join
import base64
from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.tools import misc
from odoo.tests.common import Form
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestAttachmentZip(TestMxEdiCommon):

    def test_attachment_zip(self):
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
            'country_id': self.env.ref('base.mx').id,
            'state_id': self.env.ref('base.state_mx_son').id,
            'l10n_mx_edi_pac': 'finkok',
            'l10n_mx_edi_pac_test_env': True,
            'l10n_mx_edi_fiscal_regime': '601',
            'l10n_mx_edi_certificate_ids': [(6, 0, certificate.ids)],
            'name': 'ESCUELA KEMPER URGATE',
        })
        invoice = self.invoice
        invoice.invoice_date = False
        invoice.invoice_line_ids.product_uom_id = invoice.invoice_line_ids.product_id.uom_id
        invoice.currency_id = self.env.ref('base.MXN')
        isr = self.env['account.account.tag'].search([('name', '=', 'ISR')])
        iva = isr.search([('name', '=', 'IVA')])
        invoice.invoice_line_ids.tax_ids.filtered(lambda t: t.amount <= 0).invoice_repartition_line_ids.tag_ids |= isr
        invoice.invoice_line_ids.tax_ids.filtered(lambda t: t.amount > 0).invoice_repartition_line_ids.tag_ids |= iva
        invoice.action_post()
        self._process_documents_web_services(invoice, {'cfdi_3_3'})
        attach_zip = self.env['ir.attachment.zip'].create({
            'attachment_ids': [(6, 0, invoice.edi_document_ids.mapped('attachment_id').ids)],
            'zip_name': 'test01.zip',
        })
        attach_zip._set_zip_file()
        # action = attach_zip._get_action_download()
        # TODO: add asserts reading zip content

        # Register the payment
        ctx = {'active_model': 'account.move', 'active_ids': invoice.ids, 'force_ref': True}
        bank_journal = self.env['account.journal'].search([('type', '=', 'bank'),
                                                           ('company_id', '=', invoice.company_id.id)], limit=1)
        payment = Form(self.env['account.payment.register'].with_context(**ctx))
        payment.payment_date = invoice.date
        payment.l10n_mx_edi_payment_method_id = self.env.ref('l10n_mx_edi.payment_method_efectivo')
        payment.journal_id = bank_journal
        payment.amount = invoice.amount_total
        payment.save().action_create_payments()
        payment = invoice._get_reconciled_payments()
        messages = payment.message_ids
        payment._l10n_mx_edi_uuid_zip_post()
        self.assertNotEqual(messages, payment.message_ids, 'Message with ZIP not added.')
