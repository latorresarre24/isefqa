import re

from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_mx_edi_property_taxes = fields.Char(
        "Property Taxes Account",
        copy=False,
        help="If this product is a lease, specifies the property taxes account which the property was registered "
        "in the cadastral system of the state.\nIf this field is set, the concept in the CFDI will to have this "
        "information in the Concept.",
    )

    def get_parsed_l10n_mx_edi_property_taxes(self, for_pdf=False):
        """Parse property Taxes to be set on the CFDI"""
        self.ensure_one()
        if for_pdf:
            return self.l10n_mx_edi_property_taxes.replace(" ", "").split(",")
        code = self.l10n_mx_edi_property_taxes.replace(",", "").replace(" ", "")
        code = re.sub("[a-zA-Z]", "0", code)
        return code
