# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Odoo Mexico Localization for Expenses",
    "version": "15.0.1.1.1",
    "author": "Vauxoo",
    "category": "Accounting",
    "license": "OEEL-1",
    "depends": [
        "account_accountant",
        "l10n_mx_edi",
        "base_automation",
        "hr_expense",
    ],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "views/account_view.xml",
        "views/account_invoice_view.xml",
        "views/account_payment_view.xml",
        "views/hr_employee_views.xml",
        "wizard/merge_expenses_view.xml",
        "views/hr_expense_views.xml",
        "views/mail_templates.xml",
        "views/res_config_settings_views.xml",
        "views/res_partner_view.xml",
        "views/templates.xml",
        "data/actions.xml",
        "data/account_tag_data.xml",
        "data/mail_templates.xml",
        "data/partner_tags.xml",
        "data/product_data.xml",
        "wizard/reclassify_journal_entries_view.xml",
    ],
    "demo": [
        "demo/hr_expense.xml",
    ],
    "external_dependencies": {"python": ["json2html"]},
    "assets": {
        "web.assets_backend": [
            "l10n_mx_edi_hr_expense/static/src/js/*",
        ],
        "web.assets_qweb": [
            "l10n_mx_edi_hr_expense/static/src/xml/checks_widget.xml",
        ],
    },
    "installable": True,
    "pre_init_hook": "pre_init_hook",
}
