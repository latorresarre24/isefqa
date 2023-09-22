Tax withholding CFDI
====================

This module allows generate a tax withholding CFDI from a supplier payment.

Usage
=====

**Create** a vendor payment.

  Indicate that must be generated a tax withholding and assign the required values for
  the CFDI file.

  - Tax Withholding: Indicate the Tax for withholding.
  - Tax Withholding Amount: Assign the Tax amount
  - Tax Withholding Type:  Indicate if the payment is provisional or definitively.
  - Tax Withholding Concept: Concept to be used in the complement for Withholding.
  - Tax Withholding Rate: Rate accorded for the operation if is in USD.

    .. image:: l10n_mx_edi_tax_withholding/static/src/img/tax_withholding.png
      :width: 400pt
      :alt: Tax Withholding

Validate the payment
The cron process that validate the EDI documents will to process the CFDI.


Bug Tracker
===========

Bugs are tracked on
`GitLab Issues <https://git.vauxoo.com/Vauxoo/mexico/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us smashing it by providing a detailed and
welcomed feedback.

Credits
=======

**Contributors**

* Luis Torres <luis_t@vauxoo.com> (Designer/Developer)

Maintainer
==========

.. image:: https://s3.amazonaws.com/s3.vauxoo.com/description_logo.png
   :alt: Vauxoo
   :target: https://vauxoo.com
