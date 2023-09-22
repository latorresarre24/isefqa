from odoo import models


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _l10n_mx_edi_get_invoice_cfdi_values(self, invoice):
        cfdi_values = super()._l10n_mx_edi_get_invoice_cfdi_values(invoice)
        # Avoid affect the transfer module
        invoice_line_vals_list = []
        diff_partner = invoice.company_id.partner_id.commercial_partner_id != invoice.partner_id.commercial_partner_id
        for vals in cfdi_values['invoice_line_vals_list']:
            move_line = vals['line']
            if move_line.display_type or (diff_partner and not move_line.price_unit):
                continue
            invoice_line_vals_list.append(vals)

        cfdi_values['invoice_line_vals_list'] = invoice_line_vals_list
        return cfdi_values
