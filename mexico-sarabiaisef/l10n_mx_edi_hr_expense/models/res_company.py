# Copyright 2018, Vauxoo, S.A. de C.V.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from lxml import etree

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    accountant_company_currency_id = fields.Many2one(
        "res.users",
        string="Accountant MXN",
        help="This user will be the accountant assigned in the expense sheets "
        "generated for generic suppliers in MXN.",
    )
    accountant_foreign_currency_id = fields.Many2one(
        "res.users",
        string="Accountant Other Currency",
        help="This user will be the accountant assigned in the expense sheets "
        "generated for generic suppliers in other currency.",
    )
    l10n_mx_expenses_amount = fields.Float(
        "Limit amount for expenses", help="After of this amount will be notified to the employees indicated."
    )
    l10n_mx_edi_employee_ids = fields.Many2many(
        "hr.employee",
        string="Employees",
        help='When the amount in an expense is bigger than the "Limit amount '
        'for expenses" will be notified this employees.',
    )
    l10n_mx_edi_fuel_code_sat_ids = fields.Many2many(
        "product.unspsc.code", string="SAT fuel codes", domain=[("applies_to", "=", "product")]
    )

    @api.model
    def _load_xsd_complements(self, content):
        content = super()._load_xsd_complements(content)
        complements = [
            [
                "http://www.sat.gob.mx/CartaPorte20",
                "http://www.sat.gob.mx/sitio_internet/cfd/CartaPorte/CartaPorte20.xsd",
            ]
        ]
        for complement in complements:
            xsd = {"namespace": complement[0], "schemaLocation": complement[1]}
            node = etree.Element("{http://www.w3.org/2001/XMLSchema}import", xsd)
            content.insert(0, node)
        return content
