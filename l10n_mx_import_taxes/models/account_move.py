from odoo import fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        # /!\ NOTE: This method needs to be multi-friendly. Just like the override in stock_account.
        # Create additional CABA BASE lines for Supplier Bills.

        # Don't change anything on moves used to cancel another ones.
        if self._context.get('move_reverse_cancel'):
            return super()._post(soft)

        self.env['account.move.line'].with_context(check_move_validity=False, recompute=False).create(
            self._l10n_mx_get_import_tax_base_amount_lines())

        # Post entries.
        res = super()._post()
        return res

    def _retrieve_journal_items_to_delete(self):
        return self.mapped('line_ids').filtered(
            lambda line: line.display_type == 'mx_import_taxes' and
            line.exclude_from_invoice_tab and
            line.partner_id != line.move_id.partner_id)

    def button_draft(self):
        res = super().button_draft()

        # Unlink the CABA BASE lines for Supplier Bills generated during the '_post' method..
        # This must follow the same approach as CoGS in the stock_account for AngloSaxon.
        caba_lines_to_delete = self._retrieve_journal_items_to_delete()
        caba_lines_to_delete.unlink()
        return res

    def button_cancel(self):
        res = super().button_cancel()

        # Unlink the CABA BASE lines for Supplier Bills generated during the '_post' method..
        # In most cases it shouldn't be necessary since they should be unlinked with 'button_draft'.
        # However, since it can be called in RPC, better be safe.
        # This must follow the same approach as CoGS in the stock_account for AngloSaxon.
        caba_lines_to_delete = self._retrieve_journal_items_to_delete()
        caba_lines_to_delete.unlink()
        return res

    def _l10n_mx_get_import_tax_base_amount_lines(self):
        """Appends two lines for each one of the lines where the quantity is
        zero, as the value of the lines added are need in cash basis taxes to
        properly compute the taxes paid"""

        lines_2_create = []
        for line in self.line_ids.filtered(lambda l: not l.quantity and l.tax_ids and l.l10n_mx_edi_invoice_broker_id):
            if line.l10n_mx_edi_invoice_broker_id == self:
                self.message_post(body=_(
                    'The invoice "Overseas Invoice" can not be the same that the invoice related'))
                continue
            tax_ids = self.env['account.tax']
            for tax in line.tax_ids:
                tax_ids |= tax
                for child in tax.children_tax_ids:
                    if child.type_tax_use != 'none':
                        tax_ids |= child

            price = line.price_unit
            partner_id = line.l10n_mx_edi_invoice_broker_id.commercial_partner_id.id or self.commercial_partner_id.id
            move_line_dict = {
                'name': (line.name or '').split('\n')[0][:64],
                'move_id': line.move_id.id,
                'company_id': line.move_id.company_id.id,
                'account_id': line.account_id.id,
                'product_id': line.product_id.id,
                'tax_ids': [(6, 0, tax_ids.ids)],
                'partner_id': partner_id,
                'exclude_from_invoice_tab': True,
                'quantity': 1,
                'price_unit': price if price > 0 else -price,
                'price_total': price if price > 0 else -price,
                'price_subtotal': price if price > 0 else -price,
                'display_type': 'mx_import_taxes',
            }
            lines_2_create.append(move_line_dict)

            price = -price

            ml_dict = dict(
                move_line_dict,
                tax_ids=[],
                price_unit=price if price < 0 else -price,
                price_total=price if price < 0 else -price,
                price_subtotal=price if price < 0 else -price,
            )
            lines_2_create.append(ml_dict)
        return lines_2_create


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_mx_edi_invoice_broker_id = fields.Many2one(
        'account.move', string='Overseas Invoice',
        domain="[('move_type', '=', 'in_invoice'), ('state', '=', 'posted')]",
        help='This is the source invoice upon taxes are included in this line '
        'and that were paid by the broker on behalf of the company')
    display_type = fields.Selection(selection_add=[('mx_import_taxes', 'Import Taxes')])
