from odoo import models


class AccountEdiDocument(models.Model):
    _inherit = 'account.edi.document'

    def l10n_mx_edi_reset_edi_state(self, data):
        for document in self:
            record = {}
            for record in data:
                if record['id'] == document.id:
                    break
            document.write({
                'state': record['state'],
                'error': record['error'],
            })
