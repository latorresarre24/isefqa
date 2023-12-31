from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.tests.common import Form, tagged


@tagged('account_invoice', '-at_install')
class TestInvoice(TestMxEdiCommon):

    def test_01_invoice_partner_fiscal_legends(self):
        self_ctx = self.env['account.move'].with_context(type='out_invoice')

        legend = self.env['l10n_mx_edi.fiscal.legend']
        fiscal_legend_1 = legend.create({'name': 'Demo legend 1'})
        fiscal_legend_2 = legend.create({'name': 'Demo legend 2'})
        fiscal_legend_3 = legend.create({'name': 'Demo legend 3'})
        fiscal_legend_4 = legend.create({'name': 'Demo legend 4'})

        partner_1 = self.env.ref('base.res_partner_1')
        partner_1.write({'l10n_mx_edi_legend_ids': [(6, 0, [fiscal_legend_1.id, fiscal_legend_2.id])]})
        partner_2 = self.env.ref('base.res_partner_2')
        partner_2.write({'l10n_mx_edi_legend_ids': [(6, 0, [fiscal_legend_3.id, fiscal_legend_4.id])]})

        invoice_form = Form(self_ctx, view='account.view_move_form')
        invoice_form.partner_id = partner_1
        product = self.env.ref('product.product_product_7')
        with invoice_form.invoice_line_ids.new() as invoice_line_form:
            invoice_line_form.product_id = product
            invoice_line_form.account_id = product.product_tmpl_id.get_product_accounts()['expense']
        invoice = invoice_form.save()

        self.assertEqual(invoice.l10n_mx_edi_legend_ids, partner_1.l10n_mx_edi_legend_ids)

        invoice_form.partner_id = partner_2
        invoice = invoice_form.save()

        self.assertEqual(invoice.l10n_mx_edi_legend_ids, partner_2.l10n_mx_edi_legend_ids)
