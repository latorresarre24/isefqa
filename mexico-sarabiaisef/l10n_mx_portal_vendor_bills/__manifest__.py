# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Portal for purchase documents",
    "summary": """
        Allows suppliers to upload documents related to Purchase Orders
        such as:

        - Invoice's XML file
        - Invoice's PDF file
        - Purchase order
        - Acknowledgment of receipt
    """,
    "version": "15.0.1.0.0",
    "author": "Vauxoo",
    "category": "Localization/Mexico",
    "website": "http://www.vauxoo.com/",
    "license": "LGPL-3",
    "depends": [
        'purchase',
    ],
    "demo": [
    ],
    "data": [
        'security/ir.model.access.csv',
        'security/purchase_security.xml',
        'views/portal_templates.xml',
        'views/partner_view.xml',
    ],
    'web.assets_frontend': [
        '/static/src/js/attachments_form.js',
    ],
    "installable": True,
    "auto_install": False,
}
