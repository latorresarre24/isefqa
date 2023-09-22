from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for record in res:
            if record.partner_id:
                record.message_subscribe(
                    [p.id for p in [record.partner_id] if p not in record.sudo().message_partner_ids]
                )
        return res
