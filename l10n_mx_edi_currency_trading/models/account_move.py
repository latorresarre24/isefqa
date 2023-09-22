
from lxml.objectify import fromstring
from odoo import _, api, models
from odoo.exceptions import ValidationError, UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.constrains('state')
    def _check_only_one_ct_type(self):
        for invoice in self.filtered(lambda r: r.state == 'posted'):
            fld = 'invoice_line_ids.product_id.l10n_mx_edi_ct_type'
            ct_types = set(invoice.mapped(fld)) - {False}
            if len(ct_types) > 1:
                raise ValidationError(_(
                    "This invoice contains products with different exchange operation types.\n"
                    "It is not possible to bill currency purchases and sales within the same invoice."))

    def _l10n_mx_edi_decode_cfdi(self, cfdi_data=None):
        """If the CFDI was signed, try to adds the schemaLocation correctly"""
        result = super()._l10n_mx_edi_decode_cfdi(cfdi_data=cfdi_data)
        if not cfdi_data:
            return result
        if not isinstance(cfdi_data, bytes):
            cfdi_data = cfdi_data.encode()
        cfdi_data = cfdi_data.replace(b'xmlns__divisas', b'xmlns:divisas')
        cfdi = fromstring(cfdi_data)
        if 'divisas' not in cfdi.nsmap:
            return result
        cfdi.attrib['{http://www.w3.org/2001/XMLSchema-instance}schemaLocation'] = '%s %s %s' % (
            cfdi.get('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation'),
            'http://www.sat.gob.mx/divisas', 'http://www.sat.gob.mx/sitio_internet/cfd/divisas/divisas.xsd')
        result['cfdi_node'] = cfdi
        return result

    def action_post(self):
        for move in self:
            if move.invoice_line_ids.filtered(
                    lambda l: l.product_id.l10n_mx_edi_ct_type) and not move.journal_id.l10n_mx_edi_currency_trading:
                raise UserError(_('In order to allow validate an invoice for currency trading, is necessary use a '
                                  'journal with that option enabled.'))
        return super().action_post()
