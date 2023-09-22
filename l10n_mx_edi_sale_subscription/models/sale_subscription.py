from odoo import _, fields, models


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    def _prepare_invoice_line(self, line, fiscal_position, date_start=False, date_stop=False):
        result = super()._prepare_invoice_line(line, fiscal_position, date_start=date_start, date_stop=date_stop)
        if not line.l10n_mx_edi_property_taxes:
            return result
        result["l10n_mx_edi_property_taxes"] = line.l10n_mx_edi_property_taxes
        if not any(c.isalpha() for c in line.l10n_mx_edi_property_taxes):
            return result
        result["name"] = _(
            "%(name)s. Property Taxes Account: %(tax)s", name=result.get("name"), tax=line.l10n_mx_edi_property_taxes
        )
        return result


class SaleSubscriptionLine(models.Model):
    _inherit = "sale.subscription.line"

    l10n_mx_edi_property_taxes = fields.Char(
        "Property Taxes Account",
        copy=False,
        help="If this product is a lease, specifies the property taxes account which the property was registered "
        "in the cadastral system of the state.\nIf this field is set, the invoice to generate from this subscription "
        "will to have this information in the Concept.",
    )
