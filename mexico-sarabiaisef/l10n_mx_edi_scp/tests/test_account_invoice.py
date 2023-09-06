from lxml.objectify import fromstring
from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestL10nMxEdiInvoiceSCP(TestMxEdiCommon):

    def test_l10n_mx_edi_invoice_scp(self):
        self.certificate._check_credentials()
        invoice = self.invoice
        isr = self.env['account.account.tag'].search([('name', '=', 'ISR')])
        iva = self.env['account.account.tag'].search([('name', '=', 'IVA')])
        invoice.invoice_line_ids.tax_ids.filtered(lambda t: t.amount <= 0).invoice_repartition_line_ids.tag_ids |= isr
        invoice.invoice_line_ids.tax_ids.filtered(lambda t: t.amount > 0).invoice_repartition_line_ids.tag_ids |= iva

        invoice.invoice_date = False
        invoice.invoice_line_ids.product_uom_id = invoice.invoice_line_ids.product_id.uom_id
        invoice.currency_id = self.env.ref('base.MXN')
        invoice.l10n_mx_edi_property = self.partner_a

        self.partner_a.write({
            'zip': '37440',
            'street_name': 'Street',
            'city': 'Leon',
            'state_id': self.env.ref('base.state_mx_jal').id,
            'l10n_mx_edi_property_licence': '1234567',
        })
        invoice.action_post()
        generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files, invoice.edi_error_message)
        self.assertEqual(invoice.edi_state, 'sent', invoice.edi_error_message)
        xml = fromstring(generated_files[0])
        namespaces = {'servicioparcial': 'http://www.sat.gob.mx/servicioparcialconstruccion'}
        scp = xml.Complemento.xpath('//servicioparcial:parcialesconstruccion', namespaces=namespaces)
        self.assertTrue(scp, 'Complement to SCP not added correctly')
