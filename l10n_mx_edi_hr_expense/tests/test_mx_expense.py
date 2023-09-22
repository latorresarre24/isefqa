# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import os

from odoo.modules.module import get_module_resource
from odoo.tests.common import Form, TransactionCase
from odoo.tools import misc

INVOICE = (
    ' {"invoices": [{"id": 622, "date": "2018-02-19 12:42:39", '
    '"number": "35", "serie": "INV 2018", "address": "37200", '
    '"payment": "PPD", "name": "Your Vendor SA de CV", "fp": "601", '
    '"sent_by": "EKU9003173C9", "received_by": "ULC051129GC0", '
    '"subtotal": 13754.0, "discount": 0.0, "tax": 2200.64, '
    '"withhold": 0.0, "currency": "MXN", "total": 15954.64, '
    '"uuid": "90999ED0-5D15-4991-A82C-B8ED06B3D8C3"}], '
    '"total": 15954.64, "subtotal": 13754.0, "taxes": 2200.64, '
    '"withhold": 2200.64} '
)


class EdiHrExpense(TransactionCase):
    def setUp(self):
        super().setUp()
        self.product = self.env.ref("hr_expense.product_product_fixed_cost")
        self.employee = self.env.ref("hr.employee_admin")
        self.env.ref("base.main_company").vat = "ULC051129GC0"
        self.xml_signed = (
            misc.file_open(os.path.join("l10n_mx_edi_hr_expense", "tests", "INV-INV20180035-MX-3-3.xml"), "r")
            .read()
            .encode("UTF-8")
        )
        self.account = self.env["account.account"].create(
            {
                "code": "201.xx.xx",
                "name": "Pieter Card",
                "user_type_id": self.ref("account.data_account_type_credit_card"),
                "reconcile": True,
            }
        )
        self.journal = self.env["account.journal"].create(
            {
                "name": "Pieter Card",
                "type": "cash",
                "code": "EP",
                "default_account_id": self.account.id,
            }
        )
        self.new_user = self.env["res.users"].create(
            {
                "name": "User expense mx",
                "login": "mx_expense_user",
                "email": "mx_expense_user@yourcompany.com",
                "company_id": self.env.ref("base.main_company").id,
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.ref("hr_expense.group_hr_expense_manager"),
                            self.ref("hr.group_hr_user"),
                            self.ref("hr_expense.group_hr_expense_team_approver"),
                            self.ref("account.group_account_invoice"),
                            self.ref("l10n_mx_edi_hr_expense.allow_to_revert_expenses"),
                        ],
                    )
                ],
            }
        )

    def create_attachment(self, expense_id):
        return (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": "expense.xml",
                    "datas": base64.b64encode(self.xml_signed),
                    "description": "XML signed.",
                    "res_model": "hr.expense",
                    "res_id": expense_id,
                }
            )
        )

    def test_create_sheet(self):
        sheet = self.env["hr.expense.sheet"].with_env(self.env(user=self.new_user))
        res = sheet.create({"name": "Hello", "employee_id": 2})
        self.assertTrue(res.display_name.find("]") > 0, "Name is not what expected for a sheet")
        res.approve_expense_sheets()

    def test_create_expense(self):
        """On this module I am forcing the possibility of write the total then
        test that, and check the proper default value was set as downloaded."""
        expense = (
            self.env["hr.expense"]
            .with_env(self.env(user=self.new_user))
            .create(
                {
                    "name": "Expense demo",
                    "product_id": self.product.id,
                    "employee_id": self.employee.id,
                }
            )
        )
        self.assertTrue(expense.state == "downloaded", "The default value downloaded for expenses failed to be set.")
        expense._compute_is_editable()
        self.assertTrue(expense.is_editable, "Expense must be editable in downloaded state")
        expense.write({"total_amount": 100.0})
        self.assertTrue(expense.total_amount == 100.0, "The inverse method for total_amount on expenses failed")
        expense.write(
            {
                "l10n_mx_edi_analysis": INVOICE,
                "l10n_mx_edi_rfc": "EKU9003173C9",
            }
        )

        self.assertTrue(expense.total_amount == 100.0, "The inverse method for total_amount on expenses failed")

    def test_create_expense_from_cfdi40_basic_flow(self):
        self.env.ref("base.main_company").sudo().vat = "VAU111017CG9"
        expense = (
            self.env["hr.expense"]
            .with_env(self.env(user=self.uid))
            .create(
                {
                    "name": "Expense demo",
                    "product_id": self.product.id,
                    "employee_id": self.employee.id,
                    "payment_mode": "own_account",
                    "state": "draft",
                }
            )
        )
        self.xml_signed = (
            misc.file_open(os.path.join("l10n_mx_edi_hr_expense", "tests", "CFDI400.xml"), "r").read().encode("UTF-8")
        )
        self.create_attachment(expense)
        expense.check_fiscal_status()
        self.employee.create_petty_cash_journal()

        # Check a few data integrity
        self.assertEqual(expense.l10n_mx_edi_rfc, "EKU9003173C9", "The extracted RFC is not the expected EKU9003173C9")
        self.assertEqual(
            expense.l10n_mx_edi_received_rfc,
            "VAU111017CG9",
            "The extracted RFC is not the one I expected VAU111017CG9",
        )
        self.assertEqual(expense.total_amount, 1216.79, "The extracted amount was not set")
        self.assertEqual(expense.l10n_mx_edi_uuid, "48C4C89D-723D-11EC-8FBA-00155D014029", "ID extracted incorrectly")
        self.assertTrue(expense.total_amount == 1216.79, "total_amount extracted is not what expected: 1216.79")
        # Due to the fact that we are using a manually RFC set, then I expect it is not found in SAT.
        self.assertTrue(expense.l10n_mx_edi_sat_status in ("not_found", "undefined"), "UUID extracted incorrectly")
        expense.check_functional()

        # Force Functionally approve, The uuid will be not found never
        groups = self.env.ref("l10n_mx_edi_hr_expense.force_expense", False)
        groups |= self.env.ref("l10n_mx_edi_hr_expense.allow_to_accrue_expenses", False)
        groups.sudo().write({"users": [(4, self.env.user.id)]})
        expense.force_functional()
        data = expense.action_submit_expenses()
        taxes = self.env["account.tax"].search([("type_tax_use", "=", "purchase"), ("amount", "=", 16.0)])
        taxes.sudo().write({"price_include": False})
        taxes.mapped("invoice_repartition_line_ids").sudo().write({"tag_ids": [(4, self.ref("l10n_mx.tag_iva"))]})
        sheet = Form(self.env["hr.expense.sheet"].with_context(**data["context"]))
        sheet.name = expense.name
        sheet = sheet.save()
        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.sudo().l10n_mx_edi_accrue_expenses()
        self.assertTrue(expense.l10n_mx_edi_invoice_id, "The invoice was not created")

    def test_create_partner_from_cfdi(self):
        """Creating vendor from CFDI and compute partner_id."""
        self.env["res.partner"].search([("vat", "=", "EKU9003173C9")]).write({"vat": False})
        expenses = self.env["hr.expense"].with_env(self.env(user=self.new_user))
        expense = expenses.create(
            {
                "name": "Expense demo",
                "product_id": self.product.id,
                "employee_id": self.employee.id,
            }
        )
        expense.write(
            {
                "l10n_mx_edi_analysis": INVOICE,
                "l10n_mx_edi_rfc": "EKU9003173C9",
            }
        )
        expense.create_partner_from_cfdi()
        self.assertTrue(bool(expense.partner_id), "The Partner was not assigned once created from expense")
        self.assertTrue(
            expense.partner_id.name == "Your Vendor SA de CV",
            "Name was incorrectly set on create partner from expense",
        )
        self.assertTrue(
            expense.partner_id.vat == "EKU9003173C9", "Vat was incorrectly set on create partner from expense"
        )
        self.assertTrue(
            expense.partner_id.zip == "37200", "Zip code was incorrectly set on created partner from expense"
        )
        expense.create_partner_from_cfdi()
        self.assertTrue(expense.partner_id.vat == "EKU9003173C9", "Vat the partner was found and is correct")
        expense2 = expenses.create(
            {
                "name": "Expense demo",
                "product_id": self.product.id,
                "employee_id": self.employee.id,
                "l10n_mx_edi_rfc": "EKU9003173C9",
            }
        )
        self.assertTrue(
            bool(expense.partner_id),
            "The Partner was not assigned once expense is created and partner exists with proper rfc on the record",
        )
        self.assertTrue(
            expense2.partner_id.vat == "EKU9003173C9", "Vat the partner was found and is correct with compute"
        )

    def test_force_create_super_employee(self):
        """Testing try creation of the first super employee"""
        expenses = self.env["hr.expense"].with_env(self.env(user=self.new_user))
        super_employee = expenses._force_create_super_employee()
        self.assertTrue(bool(super_employee), "Super employee creation failed")
        super_employee2 = expenses._force_create_super_employee()
        self.assertTrue(super_employee2 == super_employee, "Super employee creation failed")

    def test_demo_check_fiscal_status(self):
        """Force run the check fiscal method and see if the data was extracted
        properly from the xml"""
        expense = self.env.ref("l10n_mx_edi_hr_expense.ciel")
        expense.check_fiscal_status()
        self.assertTrue(
            expense.l10n_mx_edi_rfc == "ECO820331KB5",
            "The extracted RFC is not the one I expected, I expected: ECO820331KB5",
        )
        self.assertTrue(
            expense.l10n_mx_edi_received_rfc == "EKU9003173C9",
            "The extracted RFC is not the one I expected, I expected: EKU9003173C9",
        )
        self.assertEqual(expense.total_amount, 124.00, "The extracted amount was not set")
        self.assertTrue(
            expense.l10n_mx_edi_uuid == "F759C51C-42BC-46F6-8349-9C59EB088ABF", "UUID extracted incorrectly"
        )
        # Due to the fact that We are using a manually changed UUID then I
        # expect it is not found in SAT.
        self.assertTrue(expense.l10n_mx_edi_sat_status in ("not_found", "undefined"), "UUID extracted incorrectly")

    def test_demo_duplicated_partner(self):
        """it is pretty common have duplicated partner then anything can fail
        on such case."""
        expense = self.env.ref("l10n_mx_edi_hr_expense.amazon")
        partner = self.env.ref("l10n_mx_edi_hr_expense.amazon_contact")
        partners = self.env["res.partner"].search([("vat", "=", "ANE140618P37")])
        expense.check_fiscal_status()
        self.assertTrue(
            expense.partner_id in partners,
            "It did not pick an existing partner "
            "%s - id: %s and partners are: partner: %s or "
            "all in the BD: %s" % (expense.partner_id.name, expense.partner_id.id, partner.id, partners.ids),
        )

    def test_create_journal(self):
        # Not interested to check if it is done by a normal employee just
        # the logic.
        employee = self.env["hr.employee"].sudo().create({"name": "Test Employee for journal"})
        employee.create_petty_cash_journal()
        self.assertTrue(
            employee.journal_id.name == employee.name,
            "The journal was not created when the action is called from the employee.",
        )

    def test_create_expense_wo_cfdi(self):
        """Case CFE where do not have CFDI but is necessary an invoice."""
        partner = self.env.ref("l10n_mx_edi_hr_expense.amazon_contact")
        partner.sudo().category_id = [(6, 0, self.env.ref("l10n_mx_edi_hr_expense.tag_force_invoice_generation").ids)]
        expense = (
            self.env["hr.expense"]
            .with_env(self.env(user=self.new_user))
            .create(
                {
                    "name": "Expense CFDE",
                    "product_id": self.product.id,
                    "employee_id": self.employee.id,
                    "partner_id": partner.id,
                    "quantity": 2,
                    "unit_amount": 100,
                    "state": "draft",
                    "l10n_mx_edi_functionally_approved": True,
                    "l10n_mx_edi_fiscally_approved": True,
                }
            )
        )
        data = expense.action_submit_expenses()
        sheet = Form(self.env["hr.expense.sheet"].with_context(**data["context"]))
        sheet.name = expense.name
        sheet = sheet.save()
        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.l10n_mx_edi_accrue_expenses()
        self.assertTrue(expense.l10n_mx_edi_invoice_id, "The invoice was not created")
        self.assertTrue(sheet.l10n_mx_edi_expenses_count, "Expense count incorrect.")

    def test_accountant_to_supplier_mxn(self):
        """Check that the accountant is assigned from the supplier"""
        expense = self.env.ref("l10n_mx_edi_hr_expense.ciel")
        expense.check_fiscal_status()
        expense.write(
            {
                "l10n_mx_edi_functionally_approved": True,
                "l10n_mx_edi_fiscally_approved": True,
                "state": "draft",
            }
        )
        expense.partner_id.sudo().category_id = [(6, 0, self.env.ref("l10n_mx_edi_hr_expense.tag_vendors").ids)]
        accountant = self.env.user.copy({"name": "Accountant"})
        expense.partner_id.sudo().accountant_company_currency_id = accountant
        data = expense.action_submit_expenses()
        sheet = Form(self.env["hr.expense.sheet"].with_context(**data["context"]))
        sheet.name = expense.name
        sheet.save()
        self.assertEqual(sheet.l10n_mx_edi_accountant, accountant, "Accountant not assigned correctly.")

    def test_expense_state(self):
        """Generate an expense with CFDI, and pay the invoice, after unreconcile the payment"""
        expense = self.env.ref("l10n_mx_edi_hr_expense.ciel")
        expense.check_fiscal_status()
        expense.write(
            {
                "l10n_mx_edi_functionally_approved": True,
                "l10n_mx_edi_fiscally_approved": True,
                "state": "draft",
            }
        )
        taxes = self.env["account.tax"].sudo().search([("type_tax_use", "=", "purchase"), ("amount", "=", 0.0)])
        taxes.mapped("invoice_repartition_line_ids").write({"tag_ids": [(4, self.ref("l10n_mx.tag_iva"))]})
        expense.partner_id.sudo().category_id = [(6, 0, self.env.ref("l10n_mx_edi_hr_expense.tag_vendors").ids)]
        accountant = self.env.user.copy({"name": "Accountant"})
        expense.partner_id.sudo().accountant_company_currency_id = accountant
        data = expense.action_submit_expenses()
        sheet = Form(self.env["hr.expense.sheet"].with_context(**data["context"]))
        sheet.name = expense.name
        sheet = sheet.save()
        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.sudo().l10n_mx_edi_accrue_expenses()
        invoice = expense.l10n_mx_edi_invoice_id
        bank_journal = self.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", invoice.company_id.id)], limit=1
        )
        statement = (
            self.env["account.bank.statement"]
            .sudo()
            .with_context(edi_test_mode=True)
            .create(
                {
                    "name": "test_statement",
                    "date": invoice.date,
                    "journal_id": bank_journal.id,
                    "currency_id": invoice.currency_id,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "payment_ref": "mx_st_line",
                                "partner_id": invoice.partner_id.id,
                                "amount": -(invoice.amount_total),
                            },
                        ),
                    ],
                }
            )
        )
        statement.button_post()
        receivable_line = (
            invoice.sudo()
            .line_ids.search([("move_id", "=", invoice.id)])
            .filtered(lambda line: line.account_internal_type == "payable")
        )
        statement.line_ids.reconcile([{"id": receivable_line.id}])
        self.assertEqual("done", expense.state, "The expense was not marked like paid")
        expense.with_env(self.env(user=self.new_user)).l10n_mx_edi_revert_expense()
        self.assertEqual("approved", expense.state, "The expense was not unpaid")

    def test_expense_employee(self):
        """Generate an expense with CFDI, that was paid by the employee."""
        expense = self.env.ref("l10n_mx_edi_hr_expense.ciel")
        expense.check_fiscal_status()
        expense.write(
            {
                "l10n_mx_edi_functionally_approved": True,
                "l10n_mx_edi_fiscally_approved": True,
                "state": "draft",
                "payment_mode": "own_account",
            }
        )
        expense.employee_id.sudo().create_petty_cash_journal()
        taxes = self.env["account.tax"].sudo().search([("type_tax_use", "=", "purchase"), ("amount", "=", 0.0)])
        taxes.mapped("invoice_repartition_line_ids").write({"tag_ids": [(4, self.ref("l10n_mx.tag_iva"))]})
        expense.partner_id.sudo().category_id = [(6, 0, self.env.ref("l10n_mx_edi_hr_expense.tag_vendors").ids)]
        accountant = self.env.user.copy({"name": "Accountant"})
        expense.partner_id.sudo().accountant_company_currency_id = accountant
        data = expense.action_submit_expenses()
        sheet = Form(self.env["hr.expense.sheet"].with_context(**data["context"]))
        sheet.name = expense.name
        sheet = sheet.save()
        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.sudo().l10n_mx_edi_accrue_expenses()
        self.assertEqual("done", expense.state, "The expense was not marked like paid")
        self.assertEqual(sheet.l10n_mx_edi_paid_invoices_count, 1, "Bad count for paid invoices")
        self.assertEqual(sheet.l10n_mx_edi_invoices_count, 0, "Bad count for not paid invoices")

    def test_expense_local_taxes(self):
        """Generate an expense with CFDI with Local taxes."""
        expense = (
            self.env["hr.expense"]
            .with_env(self.env(user=self.new_user))
            .create(
                {
                    "name": "Expense local tax",
                    "product_id": self.product.id,
                    "employee_id": self.employee.id,
                }
            )
        )
        self.xml_signed = (
            misc.file_open(os.path.join("l10n_mx_edi_hr_expense", "tests", "LocalTaxes.xml"), "r")
            .read()
            .encode("UTF-8")
        )
        self.create_attachment(expense.id)
        taxes = (
            self.env["account.tax"].sudo().search([("type_tax_use", "=", "purchase"), ("amount", "=", 16.0)], limit=1)
        )
        taxes.write({"amount": 8.0})
        taxes.mapped("invoice_repartition_line_ids").write({"tag_ids": [(4, self.ref("l10n_mx.tag_iva"))]})
        local_tax = taxes.copy(
            {
                "name": "ISH",
                "amount": 5.0,
            }
        )
        local_tax.mapped("invoice_repartition_line_ids").write(
            {"tag_ids": [(4, self.ref("l10n_mx_edi_hr_expense.tag_local"))]}
        )
        expense.check_fiscal_status()
        expense.write(
            {
                "l10n_mx_edi_functionally_approved": True,
                "l10n_mx_edi_fiscally_approved": True,
                "state": "draft",
            }
        )
        data = expense.action_submit_expenses()
        sheet = Form(self.env["hr.expense.sheet"].with_context(**data["context"]))
        sheet.name = expense.name
        sheet = sheet.save()
        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.sudo().l10n_mx_edi_accrue_expenses()
        self.assertTrue(expense.l10n_mx_edi_invoice_id, "Invoice not generated")

    def test_expense_local_taxes_expense(self):
        """Generate an expense with CFDI with Local taxes, but the tax is send to expenses."""
        expense = (
            self.env["hr.expense"]
            .with_env(self.env(user=self.uid))
            .create(
                {
                    "name": "Expense local tax",
                    "product_id": self.product.id,
                    "employee_id": self.employee.id,
                }
            )
        )
        self.env["ir.config_parameter"].sudo().create({"key": "l10n_mx_taxes_for_expense", "value": "ISH"})
        self.xml_signed = (
            misc.file_open(os.path.join("l10n_mx_edi_hr_expense", "tests", "LocalTaxes.xml"), "r")
            .read()
            .encode("UTF-8")
        )
        self.create_attachment(expense.id)
        taxes = (
            self.env["account.tax"].sudo().search([("type_tax_use", "=", "purchase"), ("amount", "=", 16.0)], limit=1)
        )
        taxes.write({"amount": 8.0})
        taxes.mapped("invoice_repartition_line_ids").write({"tag_ids": [(4, self.ref("l10n_mx.tag_iva"))]})
        expense.check_fiscal_status()
        expense.write(
            {
                "l10n_mx_edi_functionally_approved": True,
                "l10n_mx_edi_fiscally_approved": True,
                "state": "draft",
            }
        )
        data = expense.action_submit_expenses()
        sheet = Form(self.env["hr.expense.sheet"].with_context(**data["context"]))
        sheet.name = expense.name
        sheet = sheet.save()
        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.sudo().l10n_mx_edi_accrue_expenses()
        self.assertTrue(expense.l10n_mx_edi_invoice_id, "Invoice not generated")

    def test_expense_ieps(self):
        """Generate an expense with CFDI with IEPS."""
        expense = (
            self.env["hr.expense"]
            .with_env(self.env(user=self.new_user))
            .create(
                {
                    "name": "Expense IEPS",
                    "product_id": self.product.id,
                    "employee_id": self.employee.id,
                }
            )
        )
        self.xml_signed = (
            misc.file_open(os.path.join("l10n_mx_edi_hr_expense", "tests", "IEPS.xml"), "r").read().encode("UTF-8")
        )
        self.create_attachment(expense.id)
        taxes = (
            self.env["account.tax"]
            .sudo()
            .search(
                [
                    ("type_tax_use", "=", "purchase"),
                ]
            )
        )
        taxes.mapped("invoice_repartition_line_ids").write({"tag_ids": [(4, self.ref("l10n_mx.tag_iva"))]})
        expense.check_fiscal_status()
        expense.write(
            {
                "l10n_mx_edi_functionally_approved": True,
                "l10n_mx_edi_fiscally_approved": True,
                "state": "draft",
            }
        )
        data = expense.action_submit_expenses()
        sheet = Form(self.env["hr.expense.sheet"].with_context(**data["context"]))
        sheet.name = expense.name
        sheet = sheet.save()
        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.sudo().l10n_mx_edi_accrue_expenses()
        self.assertTrue(expense.l10n_mx_edi_invoice_id, "Invoice not generated")

    def test_expense_by_email(self):
        config = (
            self.env["res.config.settings"]
            .sudo()
            .create(
                {
                    "expense_alias_prefix": "expenses",
                    "alias_domain": "vauxoo.com",
                }
            )
        )
        config.sudo().execute()

        employee = self.env["hr.employee"].create({"name": "Luis Torres", "work_email": "luis_t@vauxoo.com"})
        employee.address_home_id.sudo().create({"name": "Luis", "email": "luis_t@vauxoo.com"})

        with open(get_module_resource("l10n_mx_edi_hr_expense", "tests", "expense.eml"), "rb") as request_file:
            request_message = request_file.read()
        self.env["mail.thread"].message_process("hr.expense", request_message)

        # Verifies a lead was created with all expected values
        expense = self.env["hr.expense"].search(
            [
                ("name", "=", "Subject Test"),
            ]
        )
        self.assertTrue(expense, "Expense not created.")

        expense.check_fiscal_status()
        expense.check_functional()
        self.assertTrue(expense.l10n_mx_edi_functional_details, "Expense not created.")

    def test_multicompany(self):
        expense = self.env.ref("l10n_mx_edi_hr_expense.amazon")
        partner = expense.partner_id
        company = (
            self.env["res.company"]
            .sudo()
            .create(
                {
                    "name": "Test",
                    "country_id": self.env.ref("base.mx").id,
                }
            )
        )
        partner.company_id = company
        expense.partner_id = False
        expense.check_fiscal_status()
        self.assertNotEqual(partner, expense.partner_id, "Partner assigned from other company.")

    def test_split_2_cfdis(self):
        """Ensure that split the expense if have 2 or more attachments."""
        expenses = self.env["hr.expense"].with_env(self.env(user=self.new_user))
        expense = expenses.create(
            {
                "name": "Expense demo",
                "product_id": self.product.id,
                "employee_id": self.employee.id,
            }
        )
        self.create_attachment(expense.id)
        self.create_attachment(expense.id)
        expense.check_fiscal_status()
        self.assertEqual(expense.l10n_mx_count_cfdi, 1, "Expense not split.")

    def test_ack(self):
        """Ensure that ACK is executed correctly"""
        expense = self.env.ref("l10n_mx_edi_hr_expense.amazon")
        expense.state = "downloaded"
        self.env.ref("l10n_mx_edi_hr_expense.hr_expense_ack").method_direct_trigger()
        self.assertEqual("draft", expense.state, "ACK do not change to draft the expense.")

    def test_expense_odoo_flow(self):
        """Ensure that Odoo flow its correct."""
        partner = self.env.ref("l10n_mx_edi_hr_expense.amazon_contact")
        expense = (
            self.env["hr.expense"]
            .with_env(self.env(user=self.uid))
            .create(
                {
                    "name": "Expense CFDE",
                    "product_id": self.product.id,
                    "employee_id": self.employee.id,
                    "partner_id": partner.id,
                    "quantity": 2,
                    "unit_amount": 100,
                    "state": "draft",
                    "l10n_mx_edi_functionally_approved": True,
                    "l10n_mx_edi_fiscally_approved": True,
                }
            )
        )
        data = expense.action_submit_expenses()
        sheet = Form(self.env["hr.expense.sheet"].with_context(**data["context"]))
        sheet.name = expense.name
        sheet = sheet.save()
        sheet.action_submit_sheet()
        sheet.approve_expense_sheets()
        sheet.l10n_mx_edi_accrue_expenses()
        self.assertTrue(expense.l10n_mx_edi_move_id, "The move was not created")
        expense.with_env(self.env(user=self.new_user)).l10n_mx_edi_revert_expense()
        self.assertEqual("approved", expense.state, "The expense was not unpaid")
