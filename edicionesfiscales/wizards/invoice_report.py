from odoo import api, fields, models


class InvoiceReport(models.AbstractModel):
    _name = "report.edicionesfiscales.report_my_invoices"
    _description = "ISEF Invoice Report"

    @api.model
    def _get_report_values(self, docids, data=None):

        start_date = data["form"].get("start_date", "date")
        end_date = data["form"].get("end_date", "date")
        partner = data["form"].get("partner_id", "all")

        today = fields.Date.today()
        currency_id = self.env.company.currency_id

        self._cr.execute(
            """
            WITH receivable_account AS (
                SELECT
                    id AS account_id
                FROM
                    account_account
                WHERE
                    internal_type = 'receivable'
            )
            SELECT
                aml.id,
                SUM(aml.balance) AS balance,
                SUM(GREATEST(aml.balance, 0)) AS invoicing,
                SUM(LEAST(aml.balance, 0)) AS payment,
                COALESCE(SUM(apr_debit.amount), 0) AS debit,
                COALESCE(SUM(apr_credit.amount), 0) AS credit,
                aml.date_maturity,
                invoice.state IN ('in_payment', 'paid') AS is_paid
            FROM
                account_move AS invoice
            INNER JOIN
                account_move_line AS aml
                ON aml.move_id = invoice.id
            INNER JOIN
                receivable_account
                USING(account_id)
            LEFT OUTER JOIN
                account_partial_reconcile AS apr_debit
                ON apr_debit.debit_move_id = aml.id
            LEFT OUTER JOIN
                account_partial_reconcile AS apr_credit
                ON apr_credit.credit_move_id = aml.id
            WHERE
                aml.partner_id = %(partner_id)s
                AND invoice.date >= %(start_date)s
                AND invoice.date <= %(end_date)s
                AND aml.company_id = %(company_id)s
            GROUP BY
                aml.id,
                aml.date_maturity,
                invoice.state;""",
            {
                "partner_id": partner[0],
                "start_date": start_date,
                "end_date": end_date,
                "company_id": self.env.company.id,
            },
        )

        result = self._cr.dictfetchall()

        paid_ids = [a["id"] for a in result if a["is_paid"]]
        unpaid_ids = [a["id"] for a in result if not a["is_paid"]]

        docs = self.env["account.move.line"].browse(paid_ids)
        unpaid_amls = self.env["account.move.line"].browse(unpaid_ids)

        initial_balance = invoicing = payment = 0
        unpaid_amount = lapsed_amount = 0
        for line in result:
            initial_balance += line["balance"]
            invoicing += line["invoicing"]
            payment += line["payment"]

            if not line["is_paid"]:
                line_amount = initial_balance
                if line_amount:
                    unpaid_amount += line_amount
                    if line["date_maturity"] < today:
                        lapsed_amount += line_amount

        return {
            "doc_model": self.env["account.move.line"],
            "data": data,
            "docs": docs,
            "start_date": start_date,
            "end_date": end_date,
            "partner": partner[1],
            "currency_id": currency_id,
            "initial_balance": initial_balance,
            "total_invoicing": invoicing,
            "total_payment": payment,
            "balance": initial_balance + invoicing + payment,
            "unpaid_aml": unpaid_amls,
            "unpaid_amount": unpaid_amount,
            "lapsed_amount": lapsed_amount,
            "today": today,
        }
