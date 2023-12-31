.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
    :alt: License: AGPL-3

Mexican Localization Import Taxes for SAAS
==========================================

.. contents::

Usage:
======

This module provides the structure for recording the invoice with the appropriate import taxes that is paid by a broker on behalf of your company.

The first step is to create a new tax that is to be used for import taxes  with the following configuration:

Both for the definition:

     .. figure:: ../l10n_mx_import_taxes/static/src/img/import_tax_definition.png
        :width: 600pt

And the Advanced Options:

     .. figure:: ../l10n_mx_import_taxes/static/src/img/import_tax_options.png
        :width: 600pt

It is recommended to create a new product of `service type` to be used when recording the `Tax Base Amount`.

Create Product Category in this way:

     .. figure:: ../l10n_mx_import_taxes/static/src/img/product_category.png
        :width: 600pt

And set the newly created product following this minimal directions:

     .. figure:: ../l10n_mx_import_taxes/static/src/img/product_general_info.png
        :width: 600pt

     .. figure:: ../l10n_mx_import_taxes/static/src/img/product_invoicing_info.png
        :width: 600pt

As preparations are ready, the next step is to create your first Foreign Partner invoice. Non of the items you have imported from your Foreign Partner bear any taxes whatsoever. They are going to be paid by your Broker on behalf of you. So Foreign Partner invoice should look like this.

     .. figure:: ../l10n_mx_import_taxes/static/src/img/foreign_partner_invoice.png
        :width: 600pt

When your Broker Partner invoice arrives with the import taxes on it you have to record your taxes the way is presented below:

In one line you have to record the `Tax Base Amount` that was used to paid your import taxes. The `Quantity` on the line must be set to zero. `Unit Price` will bear the `Tax Base Amount`. On the `Taxes` columns set the Import Tax. And in the `Overseas Invoice` column fill it with the Invoice from your Foreign Partner.

     .. figure:: ../l10n_mx_import_taxes/static/src/img/invoice_line_import_tax_settings.png
        :width: 600pt

Any other items your Broker Partner is billing you will be recorded in the customary way you have been recording your supplier invoices.

     .. figure:: ../l10n_mx_import_taxes/static/src/img/broker_partner_invoice.png
        :width: 600pt

After validating invoice this module will adjust the Broker's Invoice Journal Entry to accomodate the Entry Lines that will serve as the base for the cash basis taxes whenever the invoice is been paid. By adding two new lines that bear the `Tax Base Amount` paid on behalf of your company.

     .. figure:: ../l10n_mx_import_taxes/static/src/img/broker_partner_journal_entry.png
        :width: 600pt

At Invoice Payment the regarding Journal Items for the `Tax Base Amount` are properly created.

     .. figure:: ../l10n_mx_import_taxes/static/src/img/foreign_partner_recorded_tax_on_paid.png
        :width: 600pt

Thus providing the appropriate information to fetch the DIOT Report on the Foreign Partner.

     .. figure:: ../l10n_mx_import_taxes/static/src/img/diot_report.png
        :width: 600pt

Installation
============

To install this module, you need to:


  - Download this module from `Vauxoo/mexico
    <https://github.com/vauxoo/mexico>`_
  - Add the repository folder into your odoo addons-path.
  - Go to ``Settings > Module list`` search for the current name and click in
    ``Install`` button.

Bug Tracker
===========

Bugs are tracked on
`GitHub Issues <https://github.com/Vauxoo/mexico/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us smashing it by providing a detailed and
welcomed feedback
`here <https://github.com/Vauxoo/mexico/issues/new?body=module:%20
l10n_mx_edi_pos%0Aversion:%20
8.0.2.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_

Credits
=======

**Contributors**

* Nhomar Hernandez <nhomar@vauxoo.com> (Planner/Auditor)
* Humberto Arocha <hbto@vauxoo.com> (Developer)
* Luis Torres <luis_t@vauxoo.com> (Developer)
* Alejandro Santillan <asantillan@vauxoo.com> (Developer)

Maintainer
==========

.. image:: https://s3.amazonaws.com/s3.vauxoo.com/description_logo.png
   :alt: Vauxoo
