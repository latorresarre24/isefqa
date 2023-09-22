# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "EDI Complement Retailer",
    "version": "15.0.1.0.1",
    "author": "Vauxoo",
    "license": "LGPL-3",
    "category": "Hidden",
    "summary": "Mexican Localization for EDI documents",
    "depends": [
        "l10n_mx_edi_extended",
    ],
    "data": [
        "data/ir_config_parameter_data.xml",
        "data/retailer1_3_1.xml",
        "wizards/retailer_invoice_wizard.xml",
        "views/account_invoice_view.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "auto_install": False,
}
