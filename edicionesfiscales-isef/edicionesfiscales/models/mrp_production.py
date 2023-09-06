from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    stock_move_pt = fields.Integer(string="Stock Move PT", compute="_compute_stock_move_pt")

    def _compute_stock_move_pt(self):
        lines = {}

        results = self.env["stock.move"].read_group(
            domain=[("production_id", "in", self.ids)],
            fields=["production_id"],
            groupby=["production_id"],
        )

        lines = {move["production_id"][0]: move["production_id_count"] for move in results}

        for record in self:
            record.stock_move_pt = lines.get(record.id, 0)
