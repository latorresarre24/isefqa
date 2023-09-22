import base64

from lxml.objectify import fromstring

from odoo import api, models


class AttachXmlsWizard(models.TransientModel):
    _inherit = "attach.xmls.wizard"

    @api.model
    def l10n_edi_document_validation(self, record, attachment):
        result = super().l10n_edi_document_validation(record, attachment)
        cfdi = fromstring(base64.decodebytes(attachment.with_context(bin_size=False).datas))
        filename = attachment.name
        if cfdi is None:
            msg = {"invoice_not_found": False, "xml64": False}
            return {"wrongfiles": {filename: msg}, "validate": False}
        xml_vat_emitter = cfdi.Emisor.get("Rfc", "").upper()
        xml_vat_receiver = cfdi.Receptor.get("Rfc", "").upper()
        if record.partner_id.vat != xml_vat_emitter:
            msg = {"rfc_supplier": (xml_vat_emitter, record.partner_id.vat), "xml64": True}
            return {"wrongfiles": {filename: msg}, "validate": False}
        if self.env.company.vat != xml_vat_receiver:
            msg = {"rfc": (xml_vat_receiver, self.env.company.vat), "xml64": True}
            return {"wrongfiles": {filename: msg}, "validate": False}
        result = {"validate": True}
        return result

    def _create_edi_document(self, invoice, attachment):
        if invoice.country_code != "MX":
            return super()._create_edi_document(invoice, attachment)
        return self.env["account.edi.document"].create(
            {
                "edi_format_id": self.env.ref("l10n_mx_edi.edi_cfdi_3_3").id,
                "move_id": invoice.id,
                "state": "sent",
                "attachment_id": attachment.id,
            }
        )

    def _prepare_invoice_document(self, attachment):
        result = super()._prepare_invoice_document(attachment)
        if self.account_id or self._context.get("account_id"):
            result["vendor_account_id"] = self.account_id.id or self._context.get("account_id")
        if self.journal_id or self._context.get("journal_id"):
            result["vendor_journal_id"] = self.journal_id.id or self._context.get("journal_id")
        return result
