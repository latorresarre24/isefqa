import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class L10nMXEdiAdvance(models.Model):
    _name = 'l10n_mx_edi.advance'
    _inherit = ['mail.thread']
    _description = 'Advances records, to allow create manual advances (for historical).'

    name = fields.Char(compute='_compute_advance_fields', store=True, compute_sudo=True,
                       help='If the advance do not exists in Odoo, save here the fiscal folio, else, get the value '
                       'from the advance.')
    uuid = fields.Char('UUID',
                       help='If the advance do not exists in Odoo, set here the UUID to be set in the invoice.')
    advance_id = fields.Many2one('account.move', ondelete='cascade', tracking=True,
                                 domain=[('l10n_mx_edi_amount_available', '>', 0)],
                                 help='Invoice with advance data.')
    partner_id = fields.Many2one('res.partner', compute='_compute_advance_fields', store=True, compute_sudo=True,
                                 help='Partner in the advance.')
    state = fields.Selection(related='advance_id.state', help='Advance state.')
    advance_subtotal = fields.Monetary(
        related='advance_id.amount_untaxed', help='Amount subtotal in the advance related.')
    advance_taxes_amount = fields.Monetary(
        related='advance_id.amount_tax', string='Amount Tax', help='Amount for taxes in the advance related.')
    advance_total = fields.Monetary(compute='_compute_advance_fields', compute_sudo=True,
                                    help='Amount total in the advance related.')
    amount_available = fields.Monetary(compute='_compute_amount_total', store=True,
                                       help='Advance available for this advance.')
    currency_id = fields.Many2one('res.currency', compute='_compute_advance_fields', store=True, compute_sudo=True,
                                  help='Currency in the advance.')
    is_historical = fields.Boolean('Is Historical?', default=True, tracking=True,
                                   help='Mark this option if the advance invoice is not in Odoo.')
    partner_historical_id = fields.Many2one('res.partner', help='Partner in the advance.')
    advance_historical_total = fields.Monetary(help='Amount total in the advance related.')
    currency_historical_id = fields.Many2one('res.currency', help='Currency in the advance.')
    invoice_ids = fields.One2many('l10n_mx_edi.advance.detail', 'advance_id', help='Use for this advance.')
    date = fields.Date(compute='_compute_advance_fields', store=True, compute_sudo=True,
                       help='Save the date when the advance was received/generated.')
    advance_date = fields.Date(help='Save the date when the advance was received.')

    @api.constrains('uuid')
    def check_l10n_mx_edi_uuid_format(self):
        pattern = r'[a-f0-9A-F]{8}-[a-f0-9A-F]{4}-[a-f0-9A-F]{4}-[a-f0-9A-F]{4}-[a-f0-9A-F]{12}'
        for rec in self.filtered('uuid'):
            if not len(rec.uuid) == 36 or not re.match(pattern, rec.uuid):
                raise ValidationError(_("The number: %s doesn't match the pattern of a CFDI we are unable to look "
                                        "for this related document.") % (rec.uuid))

    @api.depends('uuid', 'state', 'advance_historical_total', 'partner_historical_id', 'currency_historical_id',
                 'advance_subtotal')
    def _compute_advance_fields(self):
        for record in self.filtered('advance_id'):
            record.update({
                'name': record.advance_id.l10n_mx_edi_cfdi_uuid,
                'date': record.advance_id.invoice_date,
                'advance_total': record.advance_id.amount_total,
                'partner_id': record.advance_id.partner_id.id,
                'currency_id': record.advance_id.currency_id.id,
            })
        for record in self.filtered('uuid'):
            record.update({
                'name': record.uuid,
                'date': record.advance_date,
                'advance_total': record.advance_historical_total,
                'partner_id': record.partner_historical_id.id,
                'currency_id': record.currency_historical_id.id,
            })

    @api.depends('advance_id.l10n_mx_edi_amount_available', 'invoice_ids', 'invoice_ids.invoice_id.state',
                 'advance_historical_total')
    def _compute_amount_total(self):
        for record in self.filtered('advance_id'):
            record.amount_available = record.advance_id.l10n_mx_edi_amount_available
        for record in self.filtered('is_historical'):
            available = record.advance_historical_total
            for inv in record.invoice_ids.filtered(lambda l: l.invoice_id and l.invoice_id.state != 'cancel'):
                available -= inv.invoice_id.currency_id._convert(
                    inv.amount, record.currency_id, inv.invoice_id.company_id,
                    inv.invoice_id.invoice_date or fields.date.today())
            record.amount_available = available if available >= 0 else 0

    @api.onchange('advance_id')
    def _onchange_advance(self):
        for record in self:
            record.name = record.advance_id.l10n_mx_edi_cfdi_uuid


class L10nMXEdiAdvanceDetail(models.Model):
    _name = 'l10n_mx_edi.advance.detail'
    _description = 'Advances and how is used.'

    advance_id = fields.Many2one('l10n_mx_edi.advance', help='Invoice where will be take the amount for advance.')
    invoice_id = fields.Many2one('account.move', help='Invoice where is used the advance.')
    amount = fields.Float(help='Amount to use in the invoice where is applied the advance.')
