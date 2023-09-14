# Copyright 2020 Vauxoo
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    location_route_id = fields.Many2one('stock.location.route', string="Ruta de Inventario")
