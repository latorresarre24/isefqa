import json

from odoo import api, models


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    @api.model
    def _l10n_mx_edi_get_serie_and_folio(self, move):
        self.ensure_one()
        res = super()._l10n_mx_edi_get_serie_and_folio(move)
        res.update(**self._l10n_mx_edi_get_values_for_cdfi_from_invoice(move))
        return res

    def _l10n_mx_edi_get_values_for_cdfi_from_invoice(self, invoice):
        self.ensure_one()

        if self.env['ir.config_parameter'].sudo().get_param('skip_sign_with_l10n_mx_edi_payment_split'):
            return {}

        values = {}

        move = self._context.get('l10n_mx_edi_payment_split')

        if not move or not move.payment_id.payment_split_data:
            return values

        res = json.loads(invoice.invoice_payments_widget)
        if not res:
            return values
        content = res.get('content', [])
        if not content:
            return values

        invoice_line = invoice.line_ids.filtered(lambda line: line.account_internal_type in ('receivable', 'payable'))
        exchange_move = invoice_line.full_reconcile_id.exchange_move_id

        # Let us exclude the FX Journal Entry from the content
        # content gives us how many installments have been made to this invoice
        content = [line for line in content if line.get('move_id') != exchange_move.id]
        previous = [line for line in content if line.get('move_id') != move.id]
        this_payment = [line for line in content if line.get('move_id') == move.id]
        previous_payments = sum([x.get('amount') for x in previous])
        amount_before_paid = invoice.amount_total - previous_payments
        amount_paid = sum([x.get('amount') for x in this_payment])

        values = {
            'payment_policy': invoice.l10n_mx_edi_payment_policy,
            'number_of_payments': len(content),
            'amount_paid': amount_paid,
            'amount_before_paid': amount_before_paid,
        }
        if move.currency_id == invoice.currency_id:
            return values

        try:
            # NOTE: We have all the data on how the this payment was computed by
            # the user saved at `payment_split_data` field
            payment_split_data = json.loads(move.payment_id.payment_split_data)
            payment_invoice_ids = payment_split_data['payment_invoice_ids']
            pline = [x for x in payment_invoice_ids if x.get('invoice_id') == invoice.id]
            values['exchange_rate'] = pline[0]['payment_amount'] / pline[0]['payment_currency_amount']
        except json.decoder.JSONDecodeError:
            values = {}
        except KeyError:
            values = {}
        except IndexError:
            values = {}
        except TypeError:
            values = {}
        except ZeroDivisionError:
            values = {}

        return values

    def _l10n_mx_edi_export_payment_cfdi(self, move):
        # NOTE: This method is done this way to avoid tampering with the
        # signing process for the payments that are created through the core
        # functionality. Only our payments coming from Payment Split will be
        # using our way of signing. As an afterthought: Maybe this code get ridden?
        if not move.payment_id or not move.payment_id.payment_split_data:
            return super()._l10n_mx_edi_export_payment_cfdi(move)
        # Let us pass the move (payment) as a context in order to cache it later
        return (
            super(AccountEdiFormat, self.with_context(l10n_mx_edi_payment_split=move))
            ._l10n_mx_edi_export_payment_cfdi(move))
