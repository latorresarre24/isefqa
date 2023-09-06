# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Website Invoice Tickets",
    "summary": """
        Adds the ability of downloading, generating your e-invoices
        using your ticket number.
    """,
    "version": "15.0.1.0.1",
    "author": "Vauxoo",
    "category": "Website",
    "website": "http://www.vauxoo.com/",
    "license": "OEEL-1",
    "depends": [
        "l10n_mx_edi_pos",
        "l10n_mx_edi_40",
        "portal",
    ],
    "demo": [
        "demo/pos_order_demo.xml",
    ],
    "data": [
        "views/pos_order_view.xml",
        "views/templates.xml",
    ],
    "assets": {
        "point_of_sale.assets": [
            "l10n_mx_edi_website/static/src/js/pos_ticket_number.js",
        ],
        "web.assets_qweb": [
            "l10n_mx_edi_website/static/src/xml/**/*",
        ],
    },
    "installable": True,
    "auto_install": False,
}
