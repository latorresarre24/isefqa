# Copyright 2020 Vauxoo
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, fields


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    stock_move_ids = fields.One2many(
        'stock.move', string="Stock moves", related='move_ids')
