{
    'name': 'EDI Payment Split',
    'summary': 'Allow split payments into multi-invoices',
    'author': 'Vauxoo',
    'license': 'LGPL-3',
    'version': '15.0.1.0.0',
    'category': 'Hidden',
    'depends': [
        'l10n_mx_edi',
        'account_payment_split',
    ],
    'data': [
        'views/account_payment_register_views.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
}
