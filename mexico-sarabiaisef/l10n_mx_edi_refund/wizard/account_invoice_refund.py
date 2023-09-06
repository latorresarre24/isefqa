from odoo import models, api, fields


class AccountMoveReversal(models.TransientModel):

    _inherit = "account.move.reversal"

    @api.model
    def default_get(self, fields_list):
        rec = super().default_get(fields_list)
        invoice = self.env['account.move'].browse(self.env.context.get('active_ids'))
        if not invoice:
            return rec
        rec['l10n_mx_edi_payment_method_id'] = invoice.sorted(
            'amount_total_signed')[-1].l10n_mx_edi_payment_method_id.id
        return rec

    l10n_mx_edi_payment_method_id = fields.Many2one(
        'l10n_mx_edi.payment.method',
        string='Payment Way',
        help='Indicates the way the invoice was/will be paid, where the '
        'options could be: Cash, Nominal Check, Credit Card, etc. Leave empty '
        'if unkown and the XML will show "Unidentified".',
        default=lambda self: self.env.ref('l10n_mx_edi.payment_method_otros',
                                          raise_if_not_found=False))

    def _get_usage_selection(self):
        return self.env['account.move'].fields_get().get(
            'l10n_mx_edi_usage').get('selection')

    l10n_mx_edi_usage = fields.Selection(
        _get_usage_selection, 'Usage', default='P01',
        help='Used in CFDI 3.3 to express the key to the usage that will '
        'gives the receiver to this invoice. This value is defined by the '
        'customer. \nNote: It is not cause for cancellation if the key set is '
        'not the usage that will give the receiver of the document.')

    l10n_mx_edi_origin_type = fields.Selection([
        ('01', 'Nota de crédito'),
        ('02', 'Nota de débito de los documentos relacionados'),
        ('03', 'Devolución de mercancía sobre facturas o traslados previos'),
        ('04', 'Sustitución de los CFDI previos'),
        ('07', 'CFDI por aplicación de anticipo'),
    ], 'CFDI Origin Type', default='01',
        help='In some cases like payments, credit notes, debit notes, '
        'invoices re-signed or invoices that are redone due to payment in '
        'advance will need a new origin type.')

    @api.onchange('refund_method')
    def _onchange_refund_method(self):
        method = self.refund_method
        self.l10n_mx_edi_origin_type = '03' if method == 'cancel' else '01'
        self.l10n_mx_edi_usage = 'G02' if method != 'refund' else 'P01'

    def reverse_moves(self):
        result = super().reverse_moves()
        for refund, move in zip(self.new_move_ids, self.move_ids):
            if not move.l10n_mx_edi_cfdi_uuid:
                continue
            payment_inmediate = self.env.ref('account.account_payment_term_immediate', raise_if_not_found=False)
            payment_refund = self.l10n_mx_edi_payment_method_id.id or move.l10n_mx_edi_payment_method_id.id
            usage_refund = self.l10n_mx_edi_usage or 'P01'
            refund.write({
                'invoice_payment_term_id': payment_inmediate.id,
                'l10n_mx_edi_payment_method_id': payment_refund,
                'l10n_mx_edi_usage': usage_refund,
                'l10n_mx_edi_origin': refund._l10n_mx_edi_write_cfdi_origin(
                    self.l10n_mx_edi_origin_type, [move.l10n_mx_edi_cfdi_uuid])
            })
        return result
