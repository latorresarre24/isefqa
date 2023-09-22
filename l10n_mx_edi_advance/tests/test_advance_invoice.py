from odoo.tools import float_compare
from odoo.tests import Form, tagged

from .common import AdvanceTransactionCase


@tagged('mexico_advance_a', 'post_install', '-at_install')
class TestMxEdiAdvanceInvoice(AdvanceTransactionCase):
    def setUp(self):
        super().setUp()
        self.invoice.company_id.sudo().l10n_mx_edi_advance = 'A'

    def test_001_create_advance(self):
        """Create and use advance same currency"""
        # Take advance case from partner
        self.invoice.company_id.sudo().l10n_mx_edi_advance = 'B'
        self.invoice.partner_id.sudo().l10n_mx_edi_advance = 'A'

        # Create an advance with the same currency as the invoice
        advance = self.env['account.move'].advance(self.partner_a.commercial_partner_id, self.adv_amount, self.usd)
        self.assertEqual(advance.amount_total, self.adv_amount,
                         "The amount %s doesn't match with %s" % (advance.amount_total, self.adv_amount))
        advance.action_post()
        advance.action_process_edi_web_services()
        self.assertEqual(advance.edi_state, "sent", advance.message_ids.mapped('body'))
        # pay the advance
        self.register_payment(advance)
        self.assertEqual(advance.state, 'posted', advance.message_ids.mapped('body'))
        self.assertEqual(advance.l10n_mx_edi_amount_available, advance.amount_total, 'Incorrect advance available.')

        # create another invoice to use the advance
        invoice = self.invoice.copy()
        self.assertTrue(invoice.l10n_mx_edi_has_outstanding_advances, "This invoice doesn't have advances")
        # add advance
        self._apply_advances(invoice)
        self.assertTrue(invoice._l10n_mx_edi_get_advance_uuid_related(), "Error adding advance check CFDI origin")

        related = invoice._l10n_mx_edi_read_cfdi_origin(invoice.l10n_mx_edi_origin)
        self.assertEqual(related[0], '07', "Relation type must be 07 for advance")
        self.assertEqual(related[1][0], advance.l10n_mx_edi_cfdi_uuid, "Related uuid is not the same as the advance")

    def test_002_create_advance_multi_currency(self):
        """Create and use advance multi-currency"""
        # Create an advance same currency that the invoice
        advance = self.env['account.move'].advance(self.partner_a.commercial_partner_id, self.adv_amount, self.mxn)
        advance.action_post()
        advance.action_process_edi_web_services()
        advance._compute_cfdi_values()
        self.assertEqual(advance.edi_state, "sent", advance.message_ids.mapped('body'))
        # pay the advance
        self.register_payment(advance)
        self.assertEqual(advance.state, 'posted', advance.message_ids.mapped('body'))

        # create another invoice to use the advance
        invoice = self.invoice.copy()
        self.assertTrue(invoice.l10n_mx_edi_has_outstanding_advances, "This invoice doesn't have advances")
        # add advance
        self._apply_advances(invoice)
        self.assertTrue(invoice._l10n_mx_edi_get_advance_uuid_related(), "Error adding advance check CFDI origin")
        invoice.action_post()
        invoice.action_process_edi_web_services()
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))

        # Review refund
        refund = invoice.reversal_move_id
        self.assertTrue(refund, "Error: credit note was not created.")
        adv_amount = sum(invoice.l10n_mx_edi_advance_ids.mapped('amount'))
        advance_amount_total = advance.currency_id._convert(
            adv_amount, self.usd, invoice.company_id, invoice.date)
        refund_amount_total = advance.currency_id._convert(
            refund.amount_total, self.usd, invoice.company_id, invoice.date)
        self.assertFalse(refund.currency_id.compare_amounts(
            refund_amount_total, advance_amount_total), "The refund amount must be the same as the advance amount")

    def test_003_create_advance_from_payment(self):
        partner = self.partner_a.create({'name': 'ADV', 'l10n_mx_edi_fiscal_regime': '616'})
        payment = self.payment.create({
            'date': self.today_mx,
            'currency_id': self.mxn.id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': partner.id,
            'l10n_mx_edi_payment_method_id': self.cash.id,
            'payment_method_id': self.payment_method_id.id,
            'journal_id': self.bank_journal.id,
            'amount': 200000.00,
            'l10n_mx_edi_generate_advance': True,
        })
        payment.action_post()
        invoice = self.env['account.move'].search([('invoice_line_ids.name', '=', 'Anticipo del bien o servicio')])

        self.assertEqual(invoice.state, 'posted', invoice.message_ids.mapped('body'))
        invoice.action_process_edi_web_services()
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))

        # Now cancel the payment, and must be cancelled the invoice
        payment.action_cancel()
        cus_invoice = self.invoice
        cus_invoice.partner_id = partner
        cus_invoice.refresh()
        # don't have advance
        self.assertFalse(invoice.invoice_has_outstanding)

    def test_004_create_advance_from_payment_with_stamp_errors(self):
        """ Reconcile the advance with the payment and check if it's available """
        partner = self.partner_a.copy({
            'name': 'ADV',
            'parent_id': False})
        # CFDI error
        self.tax_16.write({'l10n_mx_tax_type': False})

        payment = self.payment.create({
            'date': self.today_mx,
            'currency_id': self.mxn.id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': partner.id,
            'l10n_mx_edi_payment_method_id': self.cash.id,
            'payment_method_id': self.payment_method_id.id,
            'journal_id': self.bank_journal.id,
            'amount': 2000.00,
            'l10n_mx_edi_generate_advance': True,
        })
        payment.action_post()
        # search advance created in draft
        advance = self.env['account.move'].search([
            ('partner_id', '=', partner.id), ('move_type', '=', 'out_invoice')], limit=1)
        self.assertTrue(advance, payment.message_ids.mapped('body'))
        advance.refresh()
        self.assertEqual(advance.state, 'draft', advance.message_ids.mapped('body'))
        # resolve error
        self.tax_16.write({'l10n_mx_tax_type': 'Tasa'})
        # stamp cfdi
        advance.action_post()
        advance.action_process_edi_web_services()
        self.assertEqual(advance.edi_state, "sent", advance.message_ids.mapped('body'))
        advance.refresh()
        # reconcile advance and payment
        line_id = payment.move_id.invoice_line_ids.filtered(lambda l: not l.reconciled and l.credit > 0.0)
        advance.js_assign_outstanding_line(line_id.id)
        advance.l10n_mx_edi_get_related_documents()
        self.assertEqual(advance.payment_state, 'in_payment', advance.message_ids.mapped('body'))
        # check if there are advance available
        invoice = self.invoice
        invoice.partner_id = partner
        self.assertTrue(invoice.l10n_mx_edi_has_outstanding_advances, "This invoice doesn't have advances")

    def test_005_advance_amounts_fields(self):
        """Test the compute fields for advance amounts"""
        # TODO: Check this test
        # advance with the same currency and adv amount == inv amount
        invoice = self.invoice.copy()
        invoice.currency_id = self.usd
        adv_amount = invoice.amount_total
        self._create_advance_and_apply(invoice, self.usd, adv_amount)
        self.assertFalse(float_compare(invoice.l10n_mx_edi_amount_advances, adv_amount, precision_digits=0),
                         "Advance amount is failing in draft state")
        self.assertFalse(float_compare(invoice.l10n_mx_edi_amount_residual_advances, invoice.amount_total - adv_amount,
                                       precision_digits=0), "Advance Residual amount is failing in draft state")

        # # multi-advances with the same currency and adv amount > inv amount
        invoice = self.invoice.copy()
        adv_amount = invoice.amount_total
        self._create_advance_and_apply(invoice, self.usd, invoice.amount_total / 2)
        self._create_advance_and_apply(invoice, self.usd, invoice.amount_total - 1, False)
        invoice_form = Form(self.env['invoice.apply.advances'].with_context(active_ids=invoice.ids))
        wizard = invoice_form.save()
        for line in wizard.advance_ids.filtered(lambda a: not a.amount):
            line.amount = invoice.amount_total / 2
        wizard.apply_advances()
        self.assertFalse(
            float_compare(invoice.l10n_mx_edi_amount_advances, invoice.amount_total, precision_digits=0),
            "Advance amount is failing in draft state")

    def test_006_advance_amounts_fields_multicurrency(self):
        # advance with different currency and adv amount < inv amount
        invoice = self.invoice.copy()
        invoice.currency_id = self.env.ref('base.MXN')
        adv_amount = self.mxn._convert(invoice.amount_total / 2, self.usd, invoice.company_id, self.today_mx)
        advance = self._create_advance_and_apply(invoice, self.usd, adv_amount)
        adv_amount = self.usd._convert(advance.amount_total, self.mxn, invoice.company_id, self.today_mx)
        self.assertFalse(invoice.currency_id.compare_amounts(
            round(invoice.l10n_mx_edi_amount_advances, 0), round(adv_amount, 0)),
            "Advance amount is failing in draft state %s != %s" % (invoice.l10n_mx_edi_amount_advances, adv_amount))
        self.assertFalse(invoice.currency_id.compare_amounts(
            int(invoice.l10n_mx_edi_amount_residual_advances), int(invoice.amount_total - adv_amount)),
            "Advance residual amount is failing in draft state %s != %s" % (
                invoice.l10n_mx_edi_amount_residual_advances, invoice.amount_total - adv_amount))
        invoice.action_post()
        self.assertFalse(invoice.currency_id.compare_amounts(
            invoice.l10n_mx_edi_amount_advances,
            invoice.amount_total - invoice.amount_residual),
            "Advance amount is failing in draft state %s != %s" % (
                invoice.l10n_mx_edi_amount_advances, invoice.amount_total - invoice.amount_residual))
        self.assertFalse(invoice.currency_id.compare_amounts(
            invoice.l10n_mx_edi_amount_residual_advances, invoice.amount_residual),
            "Advance residual amount is failing in draft state %s != %s" % (
                invoice.l10n_mx_edi_amount_residual_advances, invoice.amount_residual))

        # multi-advances with different currency and adv amount == inv amount
        invoice = self.invoice.copy()
        invoice.currency_id = self.usd

        # First advance in MXN for 1/3 of the invoice total
        adv_amount = self.usd._convert(invoice.amount_total / 3, self.mxn, invoice.company_id, self.today_mx)
        advance = self._create_advance_and_apply(invoice, self.mxn, adv_amount)

        # Second advance in USD for 2/3 of the invoice total
        adv_amount = self.mxn._convert(advance.amount_total, self.usd, invoice.company_id, self.today_mx)
        self._create_advance_and_apply(invoice, self.usd, invoice.amount_total - adv_amount - 0.01)
        adv_amount += invoice.amount_total - adv_amount
        self.assertFalse(invoice.currency_id.compare_amounts(
            invoice.l10n_mx_edi_amount_advances, adv_amount),
            "Advance amount is failing in draft state %s != %s" % (invoice.l10n_mx_edi_amount_advances, adv_amount))
        self.assertFalse(invoice.currency_id.compare_amounts(
            invoice.l10n_mx_edi_amount_residual_advances,
            invoice.amount_total - adv_amount),
            "Advance residual amount is failing in draft state %s != %s" % (
                invoice.l10n_mx_edi_amount_residual_advances, invoice.amount_total - adv_amount))

    def test_007_apply_advance_partially(self):
        invoice = self.invoice.copy({'currency_id': self.mxn.id})
        # Create advance by invoice total + 5
        advance = self.env['account.move'].advance(invoice.partner_id, invoice.amount_total + 5, self.mxn)
        advance.action_post()
        advance.action_process_edi_web_services()
        self.assertEqual(advance.edi_state, "sent", advance.message_ids.mapped('body'))
        self.register_payment(advance)
        # Apply advance by invoice total
        invoice_form = Form(self.env['invoice.apply.advances'].with_context(active_ids=invoice.ids))
        wizard = invoice_form.save()
        for line in wizard.advance_ids:
            line.amount = invoice.amount_total
        wizard.apply_advances()
        invoice.action_post()
        invoice2 = self.invoice.copy({'currency_id': self.mxn.id})
        invoice2 = invoice.copy()
        self.assertTrue(invoice2.l10n_mx_edi_has_outstanding_advances, "This invoice doesn't have advances to apply")

    def test_008_historical_advance(self):
        """Historical record with advance"""
        advance = self.env['account.move'].advance(self.partner_a.commercial_partner_id, self.adv_amount, self.usd)
        advance.action_post()
        advance.action_process_edi_web_services()
        self.assertEqual(advance.edi_state, "sent", advance.message_ids.mapped('body'))
        # pay the advance
        self.register_payment(advance)
        self.assertEqual(advance.payment_state, 'paid', advance.message_ids.mapped('body'))

        advance = self.env['l10n_mx_edi.advance'].search([('advance_id', '=', advance.id)], limit=1)
        advance.write({
            'is_historical': True,
            'advance_historical_total': self.adv_amount,
            'currency_historical_id': self.usd.id,
        })
        advance.check_l10n_mx_edi_uuid_format()

        # create another invoice to use the advance
        invoice = self.invoice.copy()
        self.assertTrue(invoice.l10n_mx_edi_has_outstanding_advances, "This invoice doesn't have advances")
        # add advance
        self._apply_advances(invoice)
        self.assertTrue(invoice._l10n_mx_edi_get_advance_uuid_related(), "Error adding advance check CFDI origin")
        invoice.action_post()
        invoice.action_process_edi_web_services()
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))

        self.assertFalse(advance.amount_available, 'Amount available not updated in the advance.')
        # Avoid cancellation error with the PAC (Not necessary on this test)
        invoice.edi_state = False
        invoice.sudo().button_cancel()
        self.assertEqual(invoice.state, 'cancel', invoice.message_ids.mapped('body'))
        self.assertEqual(advance.amount_available, advance.advance_historical_total,
                         'Amount available not updated with cancellation.')

    def test_009_multicurrency(self):
        """Ensure that amount available is correct."""
        advance = self.env['account.move'].advance(self.partner_a.commercial_partner_id, self.adv_amount, self.usd)
        advance.action_post()
        advance.action_process_edi_web_services()
        self.assertEqual(advance.edi_state, "sent", advance.message_ids.mapped('body'))
        # pay the advance
        self.register_payment(advance)
        self.assertEqual(advance.payment_state, 'paid', advance.message_ids.mapped('body'))

        # create another invoice to use the advance for the same advance amount but different currency
        invoice = self.invoice.copy({'currency_id': self.mxn.id})
        move_form = Form(invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.price_unit = advance.invoice_line_ids.price_unit
        move_form.save()
        self.assertTrue(invoice.l10n_mx_edi_has_outstanding_advances, "This invoice doesn't have advances")
        # add advance
        self._apply_advances(invoice)
        self.assertTrue(invoice._l10n_mx_edi_get_advance_uuid_related(), "Error adding advance check CFDI origin")
        invoice.action_post()
        invoice.action_process_edi_web_services()
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))
        self.assertTrue(advance.l10n_mx_edi_amount_available, 'Amount available incorrect in the advance.')

    def test_010_advance_refund(self):
        """Ensure that refund is not considered like payment of advances."""
        advance = self.env['account.move'].advance(self.partner_a.commercial_partner_id, self.adv_amount, self.usd)
        advance.action_post()
        advance.action_process_edi_web_services()
        self.assertEqual(advance.edi_state, "sent", advance.message_ids.mapped('body'))

        refund = self.env['account.move.reversal'].with_context(
            active_id=advance.id, active_ids=advance.ids, active_model='account.move').create({
                'refund_method': 'cancel',
                'reason': 'Refund for advance',
                'date': advance.invoice_date,
                'journal_id': advance.journal_id.id,
            })
        refund.reverse_moves()
        self.assertEqual(advance.payment_state, 'reversed', 'Advance not paid.')
        self.assertFalse(advance.l10n_mx_edi_amount_available, 'Advance available.')

    def test_011_advance_rounds(self):
        """Ensure that round do not affect on apply advances wizard"""
        advance = self.env['account.move'].advance(self.partner_a.commercial_partner_id, 227.86, self.mxn)
        advance.action_post()
        advance.action_process_edi_web_services()
        self.assertEqual(advance.edi_state, "sent", advance.message_ids.mapped('body'))
        # pay the advance
        self.register_payment(advance)
        advance = self.env['account.move'].advance(self.partner_a.commercial_partner_id, 227.86, self.mxn)
        advance.action_post()
        advance.action_process_edi_web_services()
        self.assertEqual(advance.edi_state, "sent", advance.message_ids.mapped('body'))
        # pay the advance
        self.register_payment(advance)

        invoice = self.invoice.copy({'currency_id': self.mxn.id})
        move_form = Form(invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.quantity = 1
            line_form.price_unit = 362.8400
        move_form.save()

        invoice_form = Form(self.env['invoice.apply.advances'].with_context(active_ids=invoice.ids))
        wizard = invoice_form.save()
        wizard.apply_advances()

        self.assertFalse(invoice.l10n_mx_edi_amount_residual_advances)
