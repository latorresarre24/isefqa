# Copyright 2020 Vauxoo
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, fields


class StockMove(models.Model):
    _inherit = 'stock.move'

    # picking_reference = fields.Char(string="Referencia", related="picking_id.name")
    scheduled_date = fields.Datetime(string="Fecha programada", related="picking_id.scheduled_date")
    backorder = fields.Char(string="Orden parcial de", related="picking_id.backorder_id.name")
