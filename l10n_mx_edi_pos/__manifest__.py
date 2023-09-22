# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Mexican POS Management System",
    "version": "15.0.1.0.0",
    "author": "Vauxoo",
    "category": "Point of Sale",
    "website": "http://www.vauxoo.com",
    "license": "OEEL-1",
    "depends": [
        "point_of_sale",
        "l10n_mx_edi",
        "l10n_mx_edi_partner_defaults",
    ],
    "demo": [
        "demo/point_of_sale_demo.xml",
        "demo/product_product_demo.xml",
        "demo/res_company_demo.xml",
    ],
    "data": [
        "data/3.3/cfdi.xml",
        "data/4.0/cfdi.xml",
        "views/pos_order_views.xml",
        "views/account_view.xml",
        "views/point_of_sale_view.xml",
        "views/pos_config_view.xml",
        "views/pos_payment_method_views.xml",
        "views/report_xml_session.xml",
    ],
    'external_dependencies': {
        'python': [
            'zeep',
            'zeep.transports',
        ],
    },
    "installable": True,
    "auto_install": False,
    'images': [
        'images/main_screenshot.png'
    ],
    'assets': {
        'point_of_sale.assets': [
            'l10n_mx_edi_pos/static/src/js/models.js',
            'l10n_mx_edi_pos/static/src/js/CFDIUsageLine.js',
            'l10n_mx_edi_pos/static/src/js/CFDIUsageScreen.js',
            'l10n_mx_edi_pos/static/src/js/PaymentScreen.js',
        ],
        'web.assets_qweb': [
            'l10n_mx_edi_pos/static/src/xml/CFDIUsageLine.xml',
            'l10n_mx_edi_pos/static/src/xml/CFDIUsageScreen.xml',
            'l10n_mx_edi_pos/static/src/xml/PaymentScreen.xml',
        ],
        'web.assets_tests': [
            'l10n_mx_edi_pos/static/src/js/tours/pos_invoice_order.js',
        ],
    }
}
