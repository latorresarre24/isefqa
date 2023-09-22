from os.path import splitext
from odoo import _, models, fields, api
from odoo.exceptions import AccessError, UserError, ValidationError

class SalesOrder(models.Model):
    _inherit = 'sale.order'

    location_route_id = fields.Many2one('stock.location.route', string="Ruta de Inventario")

    @api.onchange('partner_shipping_id')
    def location_route_id_onchange(self):
        for rec in self:
            if rec.partner_shipping_id and rec.partner_shipping_id.location_route_id:
                rec.location_route_id = rec.partner_shipping_id.location_route_id.id
            else:
                rec.location_route_id = False

    def _create_invoices(self, grouped=False, final=False, date=None):
        if self.location_route_id:

            for line in self.order_line:
                if line.qty_delivered != line.product_uom_qty:
                    raise self._nothing_to_invoice_error()

        return super(SalesOrder, self)._create_invoices(grouped=False, final=False, date=None)