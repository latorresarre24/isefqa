import base64

from lxml.objectify import fromstring

from odoo import models


class AccountInvoice(models.Model):
    _inherit = "account.move"

    def l10n_edi_get_extra_values(self):
        result = super().l10n_edi_get_extra_values()
        signed_edi = self._get_l10n_mx_edi_signed_edi_document()
        if not signed_edi:
            return result
        cfdi = fromstring(base64.decodebytes(signed_edi.attachment_id.with_context(bin_size=False).datas))
        result.update(
            {
                "invoice_date": cfdi.get("Fecha", "").split("T")[0],
                "ref": "%s%s" % (cfdi.get("Serie", ""), cfdi.get("Folio", "")),
            }
        )
        return result
