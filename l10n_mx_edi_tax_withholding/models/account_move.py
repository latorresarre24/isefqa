from lxml.objectify import fromstring

from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.depends("move_type", "company_id", "state")
    def _compute_l10n_mx_edi_cfdi_request(self):
        result = super()._compute_l10n_mx_edi_cfdi_request()
        for move in self.filtered(
            lambda m: m.country_code == "MX"
            and m.payment_id.payment_type == "outbound"
            and m.payment_id.l10n_mx_edi_is_tax_withholding
        ):
            move.l10n_mx_edi_cfdi_request = "on_payment"
        return result

    def _l10n_mx_edi_decode_cfdi(self, cfdi_data=None):
        """If the CFDI was signed, try to adds the schemaLocation correctly"""
        result = super()._l10n_mx_edi_decode_cfdi(cfdi_data=cfdi_data)
        if not cfdi_data:
            return result
        if not isinstance(cfdi_data, bytes):
            cfdi_data = cfdi_data.encode()
        cfdi_data = cfdi_data.replace(b"xmlns__retenciones", b"xmlns:retenciones")
        cfdi = fromstring(cfdi_data)
        if "retenciones" not in cfdi.nsmap:
            return result
        cfdi.attrib["{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"] = "%s %s %s" % (
            cfdi.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"),
            "http://www.sat.gob.mx/esquemas/retencionpago/1",
            "http://www.sat.gob.mx/esquemas/retencionpago/1/retencionpagov1.xsd",
        )
        result["cfdi_node"] = cfdi
        return result
