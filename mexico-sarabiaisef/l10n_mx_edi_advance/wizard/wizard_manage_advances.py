from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round
from odoo.tests.common import Form


class InvoiceApplyAdvances(models.TransientModel):
    _name = 'invoice.apply.advances'
    _description = 'Wizard to allow manage advances amount.'

    @api.model
    def default_get(self, fields_values):
        res = super().default_get(fields_values)
        invoice = self.env['account.move'].browse(self._context.get('active_ids'))
        advances = [(0, 0, {
            'advance_id': adv.advance_id.id,
            'amount': adv.amount,
            'amount_available': (adv.invoice_id.l10n_mx_edi_amount_available if
                                 adv.invoice_id.currency_id == invoice.currency_id else
                                 adv.invoice_id.currency_id._convert(abs(
                                     adv.invoice_id.l10n_mx_edi_amount_available), invoice.currency_id,
                                     invoice.company_id, adv.invoice_date or fields.Date.today())) + adv.amount,
            'partner_id': invoice.partner_id.id}) for adv in invoice.l10n_mx_edi_advance_ids]
        amount_in_advances = 0
        for adv in invoice._get_outstanding_advances():
            if adv in invoice.l10n_mx_edi_advance_ids.mapped('advance_id'):
                continue
            available = adv.amount_available if adv.currency_id == invoice.currency_id else (
                adv.currency_id._convert(abs(adv.amount_available), invoice.currency_id,
                                         invoice.company_id, adv.date or fields.Date.today()))
            advances.extend([(0, 0, {
                'advance_id': adv.id,
                'amount': 0 if invoice.l10n_mx_edi_advance_ids else available if
                amount_in_advances + available <= invoice.amount_total else max(
                    0, invoice.amount_total - amount_in_advances),
                'amount_available': available,
                'partner_id': invoice.partner_id.id})])
            amount_in_advances += available
        res['advance_ids'] = advances
        return res

    advance_ids = fields.One2many('invoice.apply.advances.detail', 'wizard_id')

    def apply_advances(self):
        invoice = self.env['account.move'].browse(self._context.get('active_ids'))
        advances_total = sum(self.advance_ids.mapped('amount'))
        if float_compare(advances_total, invoice.amount_total, precision_digits=2) == 1:
            raise UserError(_('The advances amount cannot be bigger than invoice total.'))
        discount_digits = self.env['decimal.precision'].precision_get('Discount')
        for advance in self.advance_ids:
            advance_line = invoice.l10n_mx_edi_advance_ids.filtered(lambda a: a.advance_id == advance.advance_id)
            if advance.amount > advance.amount_available + advance_line.amount:
                raise UserError(_('The amount cannot be bigger than available amount. %s > %s') % (
                    round(advance.amount, 2), round(advance.amount_available + advance_line.amount, 2)
                ))
            if advance_line:
                advance_line.update({'amount': advance.amount})
                continue
            if not advance.amount:
                continue
            invoice.l10n_mx_edi_advance_ids = [(0, 0, {'advance_id': advance.advance_id.id,
                                                       'amount': advance.amount})]
            if invoice._l10n_mx_edi_get_advance_case() != 'B':
                continue
            adv_text = ' - CFDI por remanente de un anticipo'
            invoice_total = invoice.amount_untaxed
            move_form = Form(invoice)
            for line in range(0, len(invoice.invoice_line_ids)):
                with move_form.invoice_line_ids.edit(line) as line_form:
                    advance_amount_line = advance.amount
                    for tax in line_form.tax_ids:
                        advance_amount_line -= advance.amount - (advance.amount / (1 + tax.amount / 100))
                    total_discount = advance_amount_line / invoice_total * line_form.price_subtotal
                    total_discount += line_form.l10n_mx_edi_total_discount
                    line_form.l10n_mx_edi_total_discount = total_discount
                    discount = float_round(
                        float_round(total_discount, precision_digits=discount_digits) /
                        float_round(line_form.quantity, precision_digits=discount_digits),
                        precision_digits=discount_digits)
                    percentage = float_round(discount / line_form.price_unit * 100, precision_digits=discount_digits)

                    line_form.discount = percentage
                    line_form.name = '%s%s' % (line_form.name.replace(adv_text, ''), adv_text)
            move_form.save()
        origin = invoice._l10n_mx_edi_write_cfdi_origin(
            '07', self.advance_ids.filtered(lambda a: a.amount and a.advance_id.name).mapped('advance_id.name'))
        origin = list(set(origin.split('|')[1].split(','))) if len(origin.split('|')) > 1 else []
        invoice.l10n_mx_edi_origin = '07|%s' % ','.join(origin)
        invoice.l10n_mx_edi_get_related_documents()


class InvoiceApplyAdvancesDetail(models.TransientModel):
    _name = 'invoice.apply.advances.detail'
    _description = 'Detail to advances on each invoice.'

    def _get_partner_default(self):
        return self.env['account.move'].browse(self._context.get('active_ids')).partner_id

    advance_id = fields.Many2one('l10n_mx_edi.advance', help='Record where will be take the amount for advance.')
    amount_available = fields.Float(compute='_compute_amount_available', help='Amount available in the advance.')
    amount = fields.Float(help='Amount to use in the invoice where is applied the advance.')
    wizard_id = fields.Many2one('invoice.apply.advances')
    partner_id = fields.Many2one('res.partner', default=_get_partner_default)

    @api.depends('advance_id')
    def _compute_amount_available(self):
        invoice = self.env['account.move'].browse(self._context.get('active_ids'))
        for line in self.filtered('advance_id'):
            amount_available = line.advance_id.amount_available + invoice.l10n_mx_edi_advance_ids.filtered(
                lambda a: a.advance_id == line.advance_id).amount
            line.amount_available = amount_available if (
                line.advance_id.currency_id == invoice.currency_id) else line.advance_id.currency_id._convert(
                    abs(amount_available), invoice.currency_id, invoice.company_id,
                    line.advance_id.date or fields.date.today())
