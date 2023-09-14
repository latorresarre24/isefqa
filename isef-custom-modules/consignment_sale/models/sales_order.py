from os.path import splitext
from odoo import _, models, fields


class SalesOrder(models.Model):
    _inherit = 'sale.order'

    location_route_id = fields.Many2one('stock.location.route', string="Ruta de Inventario")