{
    'name': 'EDI Purchase Documents',
    'summary': '''
    Main module to allow create EDI documents on Odoo from purchase orders
    ''',
    'author': 'Vauxoo',
    'website': 'https://www.vauxoo.com',
    'license': 'LGPL-3',
    'category': 'Operations/Documents/Accounting',
    'version': '15.0.1.0.0',
    'depends': [
        'l10n_edi_document',
        'purchase',
    ],
    'test': [
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/attach_xmls_wizard_view.xml',
        'views/purchase_order_views.xml',
    ],
    'demo': [
    ],
    'qweb': [
        'static/src/xml/*.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/l10n_edi_purchase_document/static/src/css/style.css',
            '/l10n_edi_purchase_document/static/src/js/attach_xmls.js',
        ],
        'web.assets_qweb': [
            '/l10n_edi_purchase_document/static/src/xml/attach_xmls_template.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
