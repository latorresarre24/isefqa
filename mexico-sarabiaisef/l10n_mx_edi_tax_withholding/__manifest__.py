{
    "name": "Tax withholding CFDI",
    "summary": """Allow generate a tax withholding CFDI from a supplier payment.""",
    "version": "15.0.1.0.0",
    "author": "Vauxoo",
    "website": "http://www.vauxoo.com",
    "category": "Uncategorized",
    "license": "LGPL-3",
    "depends": [
        "l10n_mx_edi",
        "l10n_mx_edi_extended",
    ],
    "data": [
        "data/cfdi.xml",
        "views/account_payment_view.xml",
    ],
    "demo": [
        "demo/account_tax.xml",
    ],
    "installable": True,
}
