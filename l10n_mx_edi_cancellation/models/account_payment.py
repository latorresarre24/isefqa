# Copyright 2019 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_mx_edi_cancellation_date = fields.Date(
        'Cancellation Date', readonly=True, copy=False,
        help='Save the cancellation date of the CFDI in the SAT')
    l10n_mx_edi_cancellation_time = fields.Char(
        'Cancellation Time', readonly=True, copy=False,
        help='Save the cancellation time of the CFDI in the SAT')
    l10n_mx_edi_cancellation = fields.Char(
        string='Cancellation Case', copy=False,
        help='The SAT has 4 cases in which an invoice could be cancelled, please fill this field based on your case:\n'
        'Case 1: The invoice was generated with errors and must be re-invoiced, the format must be:\n'
        '"01" The UUID will be take from the new invoice related to the record.\n'
        'Case 2: The invoice has an error on the customer, this will be cancelled and replaced by a new with the '
        'customer fixed. The format must be:\n "02", only is required the case number.\n'
        'Case 3: The invoice was generated but the operation was cancelled, this will be cancelled and not must be '
        'generated a new invoice. The format must be:\n "03", only is required the case number.\n'
        'Case 4: Global invoice. The format must be:\n "04", only is required the case number.')
