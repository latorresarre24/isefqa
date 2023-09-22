# Copyright 2019 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_mx_edi_cancellation_date = fields.Date(
        'Cancellation Date', readonly=True, copy=False,
        help='Save the cancellation date of the CFDI in the SAT')
    l10n_mx_edi_cancellation_time = fields.Char(
        'Cancellation Time', readonly=True, copy=False,
        help='Save the cancellation time of the CFDI in the SAT')
    date_cancel = fields.Date(
        'Cancel Date', readonly=True, copy=False,
        help='Save the moment when the invoice state change to "cancel" in Odoo.')
    l10n_mx_edi_cancellation = fields.Char(
        string='Cancellation Case', copy=False, tracking=True,
        help='The SAT has 4 cases in which an invoice could be cancelled, please fill this field based on your case:\n'
        'Case 1: The invoice was generated with errors and must be re-invoiced, the format must be:\n'
        '"01" The UUID will be take from the new invoice related to the record.\n'
        'Case 2: The invoice has an error on the customer, this will be cancelled and replaced by a new with the '
        'customer fixed. The format must be:\n "02", only is required the case number.\n'
        'Case 3: The invoice was generated but the operation was cancelled, this will be cancelled and not must be '
        'generated a new invoice. The format must be:\n "03", only is required the case number.\n'
        'Case 4: Global invoice. The format must be:\n "04", only is required the case number.')

    @api.depends(
        'state',
        'edi_document_ids.state',
        'l10n_mx_edi_cancellation')
    def _compute_show_reset_to_draft_button(self):
        # OVERRIDE
        res = super()._compute_show_reset_to_draft_button()

        for move in self:
            for doc in move.edi_document_ids:
                check = (doc.edi_format_id._needs_web_services() and doc.attachment_id and
                         doc.state in ('sent', 'to_cancel') and move.is_invoice(include_receipts=True) and
                         doc.edi_format_id._is_required_for_invoice(move) and move.l10n_mx_edi_cancellation == '01')
                if check:
                    move.show_reset_to_draft_button = True
                    break
        return res

    def button_draft(self):
        self.write({'date_cancel': False})
        inv_mx = self.filtered(lambda inv: inv.company_id.country_id == self.env.ref('base.mx'))
        if not inv_mx:
            return super().button_draft()
        # Avoid reset the EDI values if cancellation is 01
        cfdi_format = self.env.ref('l10n_mx_edi.edi_cfdi_3_3')
        cfdi_documents = self.edi_document_ids.filtered(lambda d: d.edi_format_id == cfdi_format)
        data = cfdi_documents.read(['state', 'error'])
        res = super().button_draft()
        cfdi_documents.l10n_mx_edi_reset_edi_state(data)
        return res

    def button_cancel(self):
        """Mexican customer invoices/refunds are considered."""
        # Ignore draft records
        draft_records = self.filtered(lambda i: not i.posted_before)
        records = self - draft_records

        records.write({'date_cancel': fields.Date.today()})
        inv_mx = records.filtered(lambda inv: inv.move_type in (
            'out_invoice', 'out_refund') and inv.company_id.country_id == self.env.ref('base.mx'))
        # Not Mexican customer/refund invoices
        result = super(AccountMove, self - inv_mx).button_cancel()
        if not inv_mx:
            return result

        # Avoid reset the EDI values if cancellation is 01
        cfdi_format = self.env.ref('l10n_mx_edi.edi_cfdi_3_3')
        edi_documents = self.edi_document_ids.filtered(lambda d: d.edi_format_id == cfdi_format)
        data = edi_documents.read(['state', 'error'])

        invoices = inv_mx._l10n_mx_edi_action_cancel_checks()

        inv_no_mx = self - inv_mx
        to_cancel = inv_no_mx + invoices

        # Case 02, 03 and 04 must be cancelled first in the SAT
        to_request = to_cancel.filtered(lambda i: i.l10n_mx_edi_cancellation in ('02', '03', '04'))
        super(AccountMove, to_request).button_cancel()

        # To avoid the Odoo message that not allow cancel an invoice if is not cancelled in the SAT, force the
        # context that is used when is called from the cron
        result = super(AccountMove, (to_cancel - to_request).with_context(called_from_cron=True)).button_cancel()

        edi_documents.l10n_mx_edi_reset_edi_state(data)
        return result

    def _l10n_mx_edi_action_cancel_checks(self):
        # Ensure that cancellation case is defined
        if self.filtered(lambda i: i.edi_state in ('sent', 'to_cancel') and not i.l10n_mx_edi_cancellation):
            raise UserError(_('In order to allow cancel, please define the cancellation case.'))
        if self.filtered(lambda i: i.edi_state in ('sent', 'to_cancel') and
                         i.l10n_mx_edi_cancellation.split('|')[0] not in ['01', '02', '03', '04']):
            raise UserError(_('In order to allow cancel, please define a correct cancellation case.'))

        # Ensure that invoices are not paid
        inv_paid = self.filtered(lambda inv: inv.payment_state in ['in_payment', 'paid'])
        for inv in inv_paid:
            inv.message_post(body=_('Invoice must be in draft or open state in order to be cancelled.'))

        return self - inv_paid

    def button_cancel_with_reversal(self):
        """Used on posted invoices in a closed period.
        This action will to mark the invoice to be cancelled with reversal when the customer accept the cancellation"""
        self._l10n_mx_edi_action_cancel_checks()
        if self.filtered(lambda i: i.state != "posted"):
            raise UserError(_("This option only could be used on posted invoices."))
        # Cancellation case 01 must be pass, because is necessary revert the invoice to allow cancel
        if self.filtered(
            lambda i: i.l10n_mx_edi_sat_status != "cancelled"
            and not i.company_id.l10n_mx_edi_pac_test_env
            and i.l10n_mx_edi_cancellation != "01"
        ):
            raise UserError(
                _(
                    "In order to use this option, the SAT status must be cancelled (for cancellation cases "
                    "02, 03 and 04)."
                )
            )

        company = self[0].company_id
        lock_date = max(company.period_lock_date, company.fiscalyear_lock_date) if\
            company.period_lock_date and company.fiscalyear_lock_date else\
            company.period_lock_date or company.fiscalyear_lock_date
        if self.user_has_groups('account.group_account_manager'):
            lock_date = company.fiscalyear_lock_date
        if self._context.get('force_cancellation_date'):
            lock_date = fields.Datetime.from_string(self._context['force_cancellation_date']).date()
        if not lock_date:
            raise UserError(_('This option only could be used on invoices out of period.'))

        invoices = self.filtered(lambda inv: inv.invoice_date and inv.invoice_date <= lock_date)

        for inv in invoices:
            default_values_list = [{"date": fields.Date.today()}]
            inv.button_mx_cancel_posted_moves()
            if inv.move_type == "out_invoice" and inv.company_id.l10n_mx_edi_reversal_customer_journal_id:
                default_values_list[0]["journal_id"] = inv.company_id.l10n_mx_edi_reversal_customer_journal_id.id
            elif inv.move_type == "in_invoice" and inv.company_id.l10n_mx_edi_reversal_supplier_journal_id:
                default_values_list[0]["journal_id"] = inv.company_id.l10n_mx_edi_reversal_supplier_journal_id.id
            reversal = inv.sudo()._reverse_moves(default_values_list=default_values_list, cancel=True)
            reversal.edi_document_ids.unlink()
            reversal.l10n_mx_edi_origin = ""
            inv.edi_document_ids.write({"state": "cancelled"})

    def button_mx_cancel_posted_moves(self):
        """Mark the edi.document related to this move to be canceled. Duplicated from button_cancel_posted_moves to
        avoid check_fiscalyear_lock_date on this module"""
        to_cancel_documents = self.env["account.edi.document"]
        for move in self:
            is_move_marked = False
            for doc in move.edi_document_ids:
                if (
                    doc.edi_format_id._needs_web_services()
                    and doc.attachment_id
                    and doc.state == "sent"
                    and move.is_invoice(include_receipts=True)
                    and doc.edi_format_id._is_required_for_invoice(move)
                ):
                    to_cancel_documents |= doc
                    is_move_marked = True
            if is_move_marked:
                move.message_post(body=_("A cancellation of the EDI has been requested."))

        to_cancel_documents.write({"state": "to_cancel", "error": False, "blocking_level": False})
