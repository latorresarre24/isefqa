# Copyright 2018 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': "EDI Cancellation for Mexican Localization (Complement)",
    'author': "Vauxoo",
    'website': "http://www.vauxoo.com",
    'license': 'LGPL-3',
    'category': 'Hidden',
    'version': '14.0.1.0.1',
    'depends': [
        'l10n_mx_edi',
    ],
    'data': [
        'security/res_groups.xml',
        'views/account_move_view.xml',
        'views/account_payment_view.xml',
    ],
    'demo': [
    ],
    'external_dependencies': {
        'python': [
            'zeep',
            'zeep.transports',
        ],
    },
    'installable': True,
    'auto_install': False,
}
