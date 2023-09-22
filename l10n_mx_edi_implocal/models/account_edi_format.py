from odoo import models


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _l10n_mx_edi_get_invoice_cfdi_values(self, invoice):
        result = super()._l10n_mx_edi_get_invoice_cfdi_values(invoice)
        # TODO - Avoid this if not local taxes
        if not invoice.invoice_line_ids.mapped('tax_ids.invoice_repartition_line_ids').filtered(
                lambda r: r. tag_ids and r.tag_ids[0].name.lower() == 'local'):
            return result
        # Taxes
        tax_details_transferred = result['tax_details_transferred']
        tax_details = {}
        tax_details_local = {}
        for tax in tax_details_transferred['tax_details']:
            if 'Local' in tax_details_transferred['tax_details'][tax]['tax'].mapped(
                    'invoice_repartition_line_ids.tag_ids.name'):
                tax_details_local.update({tax: tax_details_transferred['tax_details'][tax]})
                continue
            tax_details.update({tax: tax_details_transferred['tax_details'][tax]})
        tax_details_transferred['tax_details'] = tax_details
        # Withholding
        tax_details_withholding = result['tax_details_withholding']
        tax_details = {}
        withholding_details_local = {}
        for tax in tax_details_withholding['tax_details']:
            if 'Local' in tax_details_withholding['tax_details'][tax]['tax'].mapped(
                    'invoice_repartition_line_ids.tag_ids.name'):
                withholding_details_local.update({tax: tax_details_withholding['tax_details'][tax]})
                continue
            tax_details.update({tax: tax_details_withholding['tax_details'][tax]})
        tax_details_withholding['tax_details'] = tax_details
        # Section for lines
        for line_vals in result['invoice_line_vals_list']:
            line = line_vals['line']
            tax_detail_transferred = tax_details_transferred['invoice_line_tax_details'][line]
            tax_detail_withholding = tax_details_withholding['invoice_line_tax_details'][line]
            tax_details = {}
            withholding_details = {}
            for tax in tax_detail_transferred['tax_details']:
                if 'Local' in tax_detail_transferred['tax_details'][tax]['tax'].mapped(
                        'invoice_repartition_line_ids.tag_ids.name'):
                    continue
                tax_details.update({tax: tax_detail_transferred['tax_details'][tax]})
            for tax in tax_detail_withholding['tax_details']:
                if 'Local' in tax_detail_withholding['tax_details'][tax]['tax'].mapped(
                        'invoice_repartition_line_ids.tag_ids.name'):
                    continue
                withholding_details.update({tax: tax_detail_withholding['tax_details'][tax]})

            tax_detail_transferred['tax_details'] = tax_details
            tax_detail_withholding['tax_details'] = withholding_details
        result['tax_details_transferred'] = tax_details_transferred
        result['tax_details_withholding'] = tax_details_withholding
        # Rest the local tax amount
        tax_details_transferred['tax_amount_currency'] = tax_details_transferred['tax_amount_currency'] - (
            sum([t['tax_amount_currency'] for t in tax_details_local.values()]))
        tax_details_withholding['tax_amount_currency'] = tax_details_withholding['tax_amount_currency'] - (
            sum([t['tax_amount_currency'] for t in withholding_details_local.values()]))
        balance_multiplicator = result['balance_multiplicator']
        # Totals for implocal
        result['tax_details_transferred_local'] = {
            'total': sum([t['tax_amount_currency'] for t in tax_details_local.values()]) * balance_multiplicator,
            'tax_details_local': tax_details_local,
        }
        result['tax_details_withholding_local'] = {
            'total': sum(
                [t['tax_amount_currency'] for t in withholding_details_local.values()]) * balance_multiplicator,
            'withholding_details_local': withholding_details_local,
        }
        return result
