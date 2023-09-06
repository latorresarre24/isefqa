# Copyright 2018 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, _


def create_list_html(array):
    """Convert an array of string to a html list."""
    if not array:
        return ''
    msg = ''
    for item in array:
        msg += '<li>' + item + '</li>'
    return '<ul>' + msg + '</ul>'


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        """Inherit to create the advance when is necessary"""
        res = super().action_post()
        for rec in self:
            amount = rec.amount * (1 if rec.payment_type == 'outbound' else -1)
            is_required = rec.l10n_mx_edi_advance_is_required(amount)
            if is_required:
                rec._l10n_mx_edi_generate_advance(is_required)
        return res

    l10n_mx_edi_generate_advance = fields.Boolean(
        'Generate Advance?', default=False,
        help='This payment has a difference in customer favor, then, if this option is marked, in the payment '
        'validation will try to generate an advance. To generate the advance, first will to ensure that the customer '
        'do not have credit pending, in that case, although you mark this option the advance will not be generated.')

    def _create_payment_entry(self, amount):
        is_required = self.l10n_mx_edi_advance_is_required(amount)
        if is_required:
            self._l10n_mx_edi_generate_advance(is_required)
        return super()._create_payment_entry(amount)

    def l10n_mx_edi_advance_is_required(self, amount):
        """Verify that the configuration necessary to create the advance
        invoice is complete."""
        self.ensure_one()
        avoid_advance = self.env['ir.config_parameter'].sudo().get_param(
            'l10n_mx_edi_advance_avoid_advance_on_payment')
        if any([not self.l10n_mx_edi_generate_advance, avoid_advance, not self.partner_id,
                self.payment_type != 'inbound', self.reconciled_invoice_ids, self.is_reconciled,
                self.company_id.country_id != self.env.ref('base.mx')]):
            return False
        messages = []
        company = self.company_id
        if not company.l10n_mx_edi_product_advance_id:
            messages.append(_(
                'The product that must be used in the advance invoice line '
                'is not configured in the accounting settings.'))

        # if self.writeoff_account_id and company.l10n_mx_edi_product_advance_id.property_account_income_id != self.writeoff_account_id:  # noqa
        #     messages.append(_('The write off account is not the same that the account in the product for advances.'))

        aml = self.env['account.move.line'].with_context(check_move_validity=False, date=self.date)
        debit, credit, _amount_currency, _currency_id = aml._compute_amount_fields(
            amount, self.currency_id, self.company_id.currency_id)
        partner = self.partner_id._find_accounting_partner(self.partner_id)
        lines = self.env['account.move.line'].read_group([
            ('partner_id', '=', partner.id),
            ('account_id', '=', partner.property_account_receivable_id.id),
            ('move_id.state', '=', 'posted'),
            ('move_id.id', '!=', self.move_id.id)],
            ['debit', 'credit'], 'partner_id')
        debt = company.currency_id.round(
            lines[0]['debit'] + debit -
            (lines[0]['credit'] + credit)) if lines else 0.0
        amount_debt = company.currency_id.round(
            lines[0]['debit'] - (lines[0]['credit'])) if lines else 0.0
        if amount_debt == amount * -1:
            return False
        if debt > 0:
            messages.append(_(
                'This payment do not generate advance because the customer '
                'has invoices with pending payment.'))
        if not messages:
            return self._context.get('payment_difference') or debt or amount
        self.message_post(body=_(
            'This record cannot create the advance document automatically for the next reason: %sFor this record, you '
            'need create the invoice manually and reconcile it with this payment or cancel and validate again after '
            'that the data was completed.') % (create_list_html(messages)))
        return False

    def _l10n_mx_edi_generate_advance(self, amount):
        """Return if with the payment must be created the invoice for the
        advance"""
        advance = self.env['account.move'].advance(
            self.env['res.partner']._find_accounting_partner(self.partner_id), abs(amount), self.currency_id)
        advance.invoice_date = self.date
        advance.action_post()
        advance.message_post_with_view(
            'mail.message_origin_link',
            values={'self': advance, 'origin': self},
            subtype_id=self.env.ref('mail.mt_note').id)
        self.message_post_with_view(
            'l10n_mx_edi_advance.l10n_mx_edi_message_advance_created',
            values={'self': self, 'origin': advance},
            subtype_id=self.env.ref('mail.mt_note').id)
        advance.edi_document_ids._process_documents_web_services()
        cfdi_v33 = self.env.ref('l10n_mx_edi.edi_cfdi_3_3')
        edi_document = advance.edi_document_ids.filtered(
            lambda d: d.edi_format_id == cfdi_v33)
        if edi_document and edi_document.state == 'sent':
            domain = [('account_internal_type', 'in', ('receivable', 'payable')), ('reconciled', '=', False)]
            lines = self.line_ids.filtered_domain(domain)
            lines |= advance.line_ids.filtered_domain(domain)
            lines.reconcile()
            advance._compute_cfdi_values()  # avoid inv signed with uuid false
            return advance
        self.message_post_with_view(
            'l10n_mx_edi_advance.l10n_mx_edi_message_advance',
            values={'self': self, 'origin': advance},
            subtype_id=self.env.ref('mail.mt_note').id)
        advance.button_cancel()
        advance.button_draft()
        return advance
