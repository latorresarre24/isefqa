# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'EDI Complement for Mexico SCP',
    'version': '15.0.1.0.0',
    "author": "Vauxoo",
    "license": "LGPL-3",
    'category': 'Hidden',
    'summary': 'Mexican Localization for EDI documents',
    'depends': [
        'l10n_mx_edi_extended',
    ],
    'data': [
        "data/partial_construction_services.xml",
        "views/account_move_view.xml",
        "views/res_partner_view.xml",
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
}
