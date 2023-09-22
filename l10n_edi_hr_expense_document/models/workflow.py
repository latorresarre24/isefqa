from odoo import _, fields, models


class WorkflowActionRuleAccount(models.Model):
    _inherit = ["documents.workflow.rule"]

    create_model = fields.Selection(selection_add=[("l10n_edi_hr_expense.document", "EDI Document")])

    def create_record(self, documents=None):
        rv = super().create_record(documents=documents)
        if not documents or self.create_model != "l10n_edi_hr_expense.document":
            return rv
        document_ids = []
        documents.read(["res_id"])
        for document in documents.filtered(lambda doc: not doc.res_id or doc.res_model == "documents.document"):
            result = self._get_expense_record(document.attachment_id)
            document.toggle_active()
            document_ids.append(result.id)
        if not document_ids:
            return rv
        action = {
            "type": "ir.actions.act_window",
            "res_model": "hr.expense",
            "name": "HR Expense Documents",
            "view_id": False,
            "view_type": "list",
            "view_mode": "tree",
            "views": [(False, "list"), (False, "form")],
            "domain": [("id", "in", document_ids)],
            "context": self._context,
        }
        if len(documents) == 1 and result:
            view_id = result.get_formview_id() if result else False
            action.update(
                {
                    "view_type": "form",
                    "view_mode": "form",
                    "views": [(view_id, "form")],
                    "res_id": result.id if result else False,
                    "view_id": view_id,
                }
            )
        return action

    def _get_expense_record(self, attachment):
        """Return the record generated from the document"""
        attachment = attachment.copy(
            {
                "res_model": "hr.expense",
                "res_id": False,
            }
        )

        self.env["hr.expense"].create_expense_from_attachments(attachment.ids)

        expense = self.env["hr.expense"].browse(attachment.res_id)
        expense.l10n_edi_created_with_dms = True
        expense.message_post(body=_("<p>created with DMS</p>"))

        return expense
