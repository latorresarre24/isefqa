from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    l10n_mx_edi_is_tax_withholding = fields.Boolean(
        "Generate Tax Withholding?", tracking=True, help="If True, the CFDI with tax withholding will be generated."
    )
    l10n_mx_edi_tax_withholding_id = fields.Many2one(
        "account.tax",
        "Tax Withholding",
        tracking=True,
        domain=[("type_tax_use", "=", "purchase")],
        help="Tax to be used in the tax withholding.",
    )
    l10n_mx_edi_tax_withholding_amount = fields.Float(
        "Tax Withholding Amount", tracking=True, help="Based on the amount and the tax, set the Withholding amount."
    )
    l10n_mx_edi_tax_withholding_type = fields.Selection(
        [("provisional", "Pago provisional"), ("definitivo", "Pago definitivo")],
        "Tax Withholding Type",
        tracking=True,
        help="Indicate the tax withholding type to set in the CFDI.",
    )
    l10n_mx_edi_tax_withholding_concept = fields.Char(
        "Tax Withholding Concept", tracking=True, help="Concept for tax withholding complement."
    )
    l10n_mx_edi_tax_withholding_rate = fields.Float(
        "Rate Tax Withholding",
        digits=(12, 4),
        compute="_compute_tax_withholding_rate",
        inverse="_inverse_tax_withholding_rate",
        store=True,
        help="Rate accorded for this operation. If this payment is in USD, set the rate "
        "accorded. The payment total and taxes will be multiplied for this value in the XML.",
    )

    @api.depends("date", "currency_id", "company_id")
    def _compute_tax_withholding_rate(self):
        for record in self:
            record.l10n_mx_edi_tax_withholding_rate = (
                record.currency_id._convert(1, record.company_id.currency_id, record.company_id, record.date)
                if record.company_id.currency_id and record.company_id.currency_id != record.currency_id
                else 1
            )

    def _inverse_tax_withholding_rate(self):
        pass

    @api.onchange("amount", "l10n_mx_edi_tax_withholding_id")
    def _onchange_tax_withholding(self):
        for record in self.filtered("l10n_mx_edi_tax_withholding_id"):
            tax = record.l10n_mx_edi_tax_withholding_id.compute_all(record.amount)
            record.l10n_mx_edi_tax_withholding_amount = tax["taxes"][0].get("amount")

    def action_post(self):
        result = super().action_post()
        edi_document_vals_list = []
        for payment in self.filtered(
            lambda p: p.country_code == "MX" and p.payment_type == "outbound" and p.l10n_mx_edi_is_tax_withholding
        ).mapped("move_id"):
            edi_format = self.env.ref("l10n_mx_edi.edi_cfdi_3_3")
            existing_edi_document = payment.edi_document_ids.filtered(lambda x: x.edi_format_id == edi_format)

            if edi_format._is_required_for_payment(payment):
                if existing_edi_document:
                    existing_edi_document.write(
                        {
                            "state": "to_send",
                            "error": False,
                            "blocking_level": False,
                        }
                    )
                else:
                    edi_document_vals_list.append(
                        {
                            "edi_format_id": edi_format.id,
                            "move_id": payment.id,
                            "state": "to_send",
                        }
                    )
            elif existing_edi_document:
                existing_edi_document.write(
                    {
                        "state": False,
                        "error": False,
                        "blocking_level": False,
                    }
                )

        self.env["account.edi.document"].create(edi_document_vals_list)
        self.edi_document_ids._process_documents_no_web_services()
        return result
