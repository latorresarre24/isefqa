from odoo import models


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def l10n_edi_document_type(self, document=False):
        """Must be implemented by each l10n module to use the specific fields for each business model.

        :return: Array with two elements:
            Array[0] is an string to identify the type of document
            Array[1] the res_model for the attachment.
        :rtype: Array"""
        self.ensure_one()
        return ['vendorI', 'account.move']
