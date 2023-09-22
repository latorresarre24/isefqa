import base64
from os.path import join

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import misc


@tagged("post_install", "-at_install")
class TestL10EdiHrExpenseDocument(TransactionCase):
    def test_create_hr_expense_record(self):
        rule = self.env.ref("l10n_edi_hr_expense_document.hr_expense_document_rule")
        invoice_xml = misc.file_open(join("l10n_edi_document", "tests", "invoice.xml")).read().encode("UTF-8")
        finance_folder = self.env.ref("documents.documents_finance_folder")

        attachment = self.env["ir.attachment"].create(
            {
                "name": "invoice.xml",
                "datas": base64.b64encode(invoice_xml),
                "description": "EDI invoice",
            }
        )
        invoice_document = self.env["documents.document"].create(
            {"name": attachment.name, "folder_id": finance_folder.id, "attachment_id": attachment.id}
        )
        expense = rule.create_record(invoice_document)
        self.assertTrue(expense.get("res_id"), "Expense was not created")
