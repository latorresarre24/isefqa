from lxml import etree
from lxml.objectify import fromstring
from pytz import timezone

from odoo import fields, models, tools

XSLT_CADENA = "l10n_mx_edi_tax_withholding/data/xslt/retenciones.xslt"


class AccountEdiFormat(models.Model):
    _inherit = "account.edi.format"

    def _is_required_for_payment(self, move):
        # OVERRIDE
        self.ensure_one()
        if move.payment_id.l10n_mx_edi_is_tax_withholding:
            return True
        return super()._is_required_for_payment(move)

    def _l10n_mx_edi_export_payment_cfdi(self, move):
        if not move.payment_id.l10n_mx_edi_is_tax_withholding:
            return super()._l10n_mx_edi_export_payment_cfdi(move)

        def get_cadena(cfdi_node, template):
            if cfdi_node is None:
                return None
            cadena_root = etree.parse(tools.file_open(template))
            return str(etree.XSLT(cadena_root)(cfdi_node))

        if move.payment_id:
            total_amount = move.payment_id.amount
        else:
            if move.statement_line_id.foreign_currency_id:
                total_amount = move.statement_line_id.amount_currency
            else:
                total_amount = move.statement_line_id.amount

        # Get FechaExp according xsd, must follow yyyy-mm-ddThh:mm:ssTZD-6
        time_payslip = move.l10n_mx_edi_post_time.time()
        tz = timezone(self.env.user.tz)
        date = fields.Datetime.from_string(move.l10n_mx_edi_post_time)
        date = fields.datetime.combine(date, time_payslip, tz)
        date = date.strftime("%Y-%m-%dT%H:%M:%S%z")
        # Cleaning possible dirty time zone designator and adding : (%z does not allow it)
        date = date[:-2] + ":00"

        tags = move.payment_id.l10n_mx_edi_tax_withholding_id.invoice_repartition_line_ids.tag_ids
        tax_name = {"ISR": "01", "IVA": "02", "IEPS": "03"}.get(tags.name) if len(tags) == 1 else None
        payment = move.payment_id
        factor = (
            payment.l10n_mx_edi_tax_withholding_rate if payment.currency_id != payment.company_id.currency_id else 1
        )
        cfdi_values = {
            **self._l10n_mx_edi_get_common_cfdi_values(move),
            "amount": total_amount * factor,
            "cfdi_date": date,
            "desc_withholding": move.payment_id.ref,
            "cve_withholding": 18,  # TODO - Consider more cases
            "tax_withholding_type": dict(
                move.payment_id._fields["l10n_mx_edi_tax_withholding_type"]._description_selection(self.env)
            ).get(str(move.payment_id.l10n_mx_edi_tax_withholding_type), ""),
            "tax_withholding_amount": payment.l10n_mx_edi_tax_withholding_amount * factor,
            "tax_withholding": tax_name,
            "withholding_concept": move.payment_id.l10n_mx_edi_tax_withholding_concept,
        }

        cfdi = self.env.ref("l10n_mx_edi_tax_withholding.tax_withholding_template")._render(cfdi_values)
        decoded_cfdi_values = move._l10n_mx_edi_decode_cfdi(cfdi_data=cfdi)
        cfdi_cadena_crypted = (
            cfdi_values["certificate"].sudo().get_encrypted_cadena(get_cadena(fromstring(cfdi), XSLT_CADENA), "sha1")
        )
        decoded_cfdi_values["cfdi_node"].attrib["Sello"] = cfdi_cadena_crypted

        return {
            "cfdi_str": etree.tostring(
                decoded_cfdi_values["cfdi_node"], pretty_print=True, xml_declaration=True, encoding="UTF-8"
            ),
        }

    def _l10n_mx_edi_get_finkok_credentials(self, move):
        credentials = super()._l10n_mx_edi_get_finkok_credentials(move)
        if not move.payment_id.l10n_mx_edi_is_tax_withholding:
            return credentials
        if move.company_id.l10n_mx_edi_pac_test_env:
            credentials["sign_url"] = "http://demo-facturacion.finkok.com/servicios/soap/retentions.wsdl"
            credentials["cancel_url"] = "http://demo-facturacion.finkok.com/servicios/soap/retentions.wsdl"
        else:
            credentials["sign_url"] = "http://facturacion.finkok.com/servicios/soap/retentions.wsdl"
            credentials["cancel_url"] = "http://facturacion.finkok.com/servicios/soap/retentions.wsdl"
        return credentials
