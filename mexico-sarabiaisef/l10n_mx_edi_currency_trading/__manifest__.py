# Copyright 2017 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'EDI Currency Trading Complement for the Mexican Localization',
    'version': '15.0.1.0.0',
    'author': 'Vauxoo',
    'category': 'Hidden',
    'license': 'LGPL-3',
    'website': 'http://www.vauxoo.com/',
    'depends': [
        'l10n_mx_edi',
        'l10n_mx_edi_extended',
        'point_of_sale',
        'l10n_mx_edi_40',
    ],
    'data': [
        'data/account_data.xml',
        'data/currency_trading_template.xml',
        'data/product_data.xml',
        'views/account_journal_view.xml',
        'views/product_view.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
}
