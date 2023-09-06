
.. figure:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
    :alt: License: LGPL-3

EDI Payment Split
=================

This module adjust `account_payment_split` module to the l10n_mx localization

.. contents::

Installation
============

To install this module, you need:

- account_payment_split module is required to install this module, just install
  as a regular Odoo module:

  - Download this module from `Vauxoo/account-payment-split
    <https://git.vauxoo.com/vauxoo/account-payment-split>`_
  - Add the repository folder into your odoo addons-path.
  - Go to ``Settings > Module list`` search for the current name and click in
    ``Install`` button.

- l10n_mx_edi_payment_split module, just install as a regular Odoo module:

  - Download this module from `Vauxoo/mexico <https://git.vauxoo.com/vauxoo/mexico>`_
  - Add the repository folder into your odoo addons-path.
  - Go to ``Settings > Module list`` search for the current name and click in
    ``Install`` button.

Usage
=====

- Select one or more invoices using the list view 
  go Action -> Register Payment Split

Important Notice
================

- In case that for any reason Odoo's original way of signing is required
  a System Parameter can be set to skip this module way of signing:
  `skip_sign_with_l10n_mx_edi_payment_split` Set it to any value and the
  Original Odoo signing will apply.

Bug Tracker
===========

Bugs are tracked on
`GitHub Issues <https://github.com/Vauxoo/mexico/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us smashing it by providing a detailed and
welcomed feedback
`here <https://github.com/Vauxoo/mexico/issues/new?body=module:%20
l10n_mx_edi_payment_split%0Aversion:%20
15.0.1.0.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_

Credits
=======

**Contributors**


Maintainer
==========

.. figure:: https://s3.amazonaws.com/s3.vauxoo.com/description_logo.png
   :alt: Vauxoo

