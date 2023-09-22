# Copyright 2020 Vauxoo
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'Ventas en consignación',
    'summary': '''
        Permite cambiar el flujo de facturación de ventas
    ''',
    'author': 'Renier Ferrer',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Operations/Documents/Accounting',
    'version': '15.0.1.0.1',
    'depends': [
        'base',
        'sale',
        'account',
        'stock_picking_batch',
    ],
    'test': [
    ],
    'data': [
        'views/res_partner_views.xml',
        'views/sales_order_views.xml',
        'views/stock_picking_batch_views.xml',
    ],
    'demo': [
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/l10n_edi_document/static/src/sass/widget.scss',
    #         '/l10n_edi_document/static/src/js/checks_widget.js',
    #         '/l10n_edi_document/static/src/js/checklist_animation.js',
    #     ],
    #     'web.assets_qweb': [
    #         '/l10n_edi_document/static/src/xml/checks_widget.xml',
    #     ],
    # },
    'installable': True,
    'auto_install': False,
    'application': False,
}
