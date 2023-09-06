from odoo.tools import float_compare
from odoo.tests import Form, tagged

from .common import AdvanceTransactionCase


@tagged('mexico_advance_b', 'post_install', '-at_install')
class TestMxEdiAdvanceInvoice(AdvanceTransactionCase):

    def setUp(self):
        super().setUp()
        self.tax_py = self.tax_16.copy({
            'amount_type': 'code',
            'python_compute': 'result = base_amount * 0.16'
        })
        self.advance_national.taxes_id = [(6, 0, self.tax_16.ids)]
        self.invoice.company_id.sudo().l10n_mx_edi_advance = 'B'
        move_form = Form(self.invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.discount = 0
        move_form.save()

    def test_01_case_b_sat(self):
        # Take advance case from partner
        self.invoice.company_id.sudo().l10n_mx_edi_advance = 'A'
        self.invoice.partner_id.sudo().l10n_mx_edi_advance = 'B'

        invoice = self.invoice.copy()
        invoice.currency_id = self.env.ref('base.MXN')

        move_form = Form(invoice)
        with move_form.invoice_line_ids.new() as line_form:
            line_form.name = invoice.invoice_line_ids.name
            line_form.price_unit = invoice.invoice_line_ids.price_unit
            line_form.quantity = invoice.invoice_line_ids.quantity
            line_form.account_id = invoice.invoice_line_ids.account_id
            line_form.product_id = invoice.invoice_line_ids.product_id
            line_form.product_uom_id = invoice.invoice_line_ids.product_uom_id
            line_form.tax_ids.clear()
            line_form.tax_ids.add(self.tax_py)
        with move_form.invoice_line_ids.new() as line_form:
            line_form.name = invoice.invoice_line_ids.name
            line_form.price_unit = invoice.invoice_line_ids.price_unit
            line_form.quantity = invoice.invoice_line_ids.quantity
            line_form.account_id = invoice.invoice_line_ids.account_id
            line_form.product_id = invoice.invoice_line_ids.product_id
            line_form.product_uom_id = invoice.invoice_line_ids.product_uom_id
            line_form.tax_ids.clear()
            line_form.tax_ids.add(self.tax_py)
        move_form.invoice_line_ids.remove(0)
        move_form.save()
        advance = self._create_advance_and_apply(invoice, self.mxn, invoice.amount_total / 2)
        invoice.refresh()
        self.assertTrue(invoice.l10n_mx_edi_total_discount, 'Discount not applied on the invoice.')
        self.assertFalse(
            float_compare(invoice.l10n_mx_edi_total_discount, advance.amount_untaxed, precision_digits=0),
            'The amount in the advance is different to the discount applied.')

    def test_02_case_b_multicurrency(self):
        """Ensure that multi-currency advance is applied correctly"""
        invoice = self.invoice.copy({'currency_id': self.usd.id})
        move_form = Form(invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.tax_ids.clear()
            line_form.tax_ids.add(self.tax_py)
        move_form.save()
        self._create_advance_and_apply(invoice, self.usd, invoice.amount_total / 2)
        invoice.refresh()
        self.assertTrue(invoice.l10n_mx_edi_total_discount, 'Discount not applied on the invoice.')
        invoice.action_post()
        invoice2 = invoice.copy()
        self.assertFalse(invoice2.invoice_has_outstanding, 'The invoice has advances, but is not correct.')

    def test_03_multi_advances_sat(self):
        """Ensure that allows apply many advances"""
        advance = self.env['account.move'].advance(self.partner_a.commercial_partner_id, 1160.00, self.mxn)
        advance.action_post()
        advance.action_process_edi_web_services()
        self.register_payment(advance)
        advance = self.env['account.move'].advance(self.partner_a.commercial_partner_id, 11600.00, self.mxn)
        advance.action_post()
        advance.action_process_edi_web_services()
        self.register_payment(advance)

        self._process_documents_web_services(advance, {'cfdi_3_3'})

        invoice = self.invoice.copy({'currency_id': self.mxn.id})
        move_form = Form(invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.quantity = 2
            line_form.price_unit = 11000.00
            line_form.tax_ids.clear()
            line_form.tax_ids.add(self.tax_py)
        move_form.save()
        self._apply_advances(invoice)
        invoice.action_post()
        self.assertTrue(invoice.l10n_mx_edi_total_discount, 'Discount not applied on the invoice.')
        self.assertFalse(
            float_compare(invoice.l10n_mx_edi_total_discount, 11000.00, precision_digits=0),
            'Invoice total is different to the amount in the advance.')

    def test_04_partial_advance(self):
        advance = self.env['account.move'].advance(self.partner_a.commercial_partner_id, 1000.00, self.mxn)
        advance.action_post()
        self.register_payment(advance)
        invoice = self.invoice.copy({'currency_id': self.mxn.id})
        move_form = Form(invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.price_unit = 1000.00
            line_form.tax_ids.clear()
            line_form.tax_ids.add(self.tax_py)
        move_form.save()
        self._apply_advances(invoice, advance_amount=advance.amount_total / 2)
        invoice.action_post()
        self.assertTrue(invoice.l10n_mx_edi_total_discount, 'Discount not applied on the invoice.')
        self.assertFalse(
            float_compare(invoice.l10n_mx_edi_total_discount, advance.amount_untaxed / 2, precision_digits=0),
            'Invoice total is different to the amount in the advance.')

    def test_005_multi_advance_partial(self):
        """Apply 2 advances, a full and a partial"""
        advance = self.env['account.move'].advance(self.partner_a.commercial_partner_id, 580.00, self.mxn)
        advance.action_post()
        self.register_payment(advance)
        advance = self.env['account.move'].advance(self.partner_a.commercial_partner_id, 1160.00, self.mxn)
        advance.action_post()
        self.register_payment(advance)

        invoice = self.invoice.copy()
        invoice.currency_id = self.mxn
        move_form = Form(invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.quantity = 1
            line_form.price_unit = 1500.00
            line_form.tax_ids.clear()
            line_form.tax_ids.add(self.tax_py)
        move_form.save()

        invoice_form = Form(self.env['invoice.apply.advances'].with_context(active_ids=invoice.ids))
        wizard = invoice_form.save()
        wizard.advance_ids.filtered(lambda l: l.amount != 1160).write({'amount': 464})
        wizard.apply_advances()

        invoice.action_post()
        self.assertTrue(invoice.l10n_mx_edi_total_discount, 'Discount not applied on the invoice.')
        self.assertFalse(
            float_compare(invoice.l10n_mx_edi_total_discount, advance.amount_untaxed + 400, precision_digits=0),
            'Invoice total is different to the amount in the advance.')

        invoice = self.invoice.copy({'currency_id': self.mxn.id})
        move_form = Form(invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.quantity = 1
            line_form.price_unit = 500.00
            line_form.tax_ids.clear()
            line_form.tax_ids.add(self.tax_py)
        move_form.save()

        advance_form = Form(self.env['invoice.apply.advances'].with_context(active_ids=invoice.ids))
        wizard = advance_form.save()
        wizard.advance_ids.filtered(lambda l: l.amount_available == 580).write({'amount': 116})
        wizard.apply_advances()
        invoice.action_post()
        self.assertTrue(invoice.l10n_mx_edi_total_discount, 'Discount not applied on the invoice.')
        self.assertFalse(
            float_compare(invoice.l10n_mx_edi_total_discount, 100, precision_digits=0),
            'Invoice total is different to the amount in the advance.')
