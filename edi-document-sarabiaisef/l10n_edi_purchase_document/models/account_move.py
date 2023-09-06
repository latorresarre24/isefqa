from odoo import models
from odoo.tests.common import Form


class AccountInvoice(models.Model):
    _inherit = 'account.move'

    def xml2record(self):
        """Use the last attachment in the vendor bill (xml) and fill the invoice data"""
        purchase_id = self._context.get('active_id', False)
        if not (self._context.get('active_model', False) == 'purchase.order' and purchase_id):
            return super().xml2record()
        purchase = self.env['purchase.order'].browse(purchase_id)
        with Form(self.with_context(default_type=self.move_type)) as move_form:
            move_form.purchase_id = purchase
        return self.with_context(**{'xml2record': True})

    def l10n_edi_get_extra_values(self):
        """Method to be overwritten from localization to get the invoice date with country format"""
        self.ensure_one()
        return {
            'edi_state': 'sent',
            'invoice_date': self.date,
        }
