EDI Advance Improvements for the Mexican Localization
=====================================================

This module allows managing the advances in an easier way. With this module
you can:

- Create advances from a payment difference when there is not debt or create
  an invoice using one invoice line with the advance product.

- See a notification when there are available advances.

- Add advance to an invoice like add a outstanding credit.

- Apply the corresponding credit note when you validate a invoice with
  advances.

Configure
=========

- Create the account for advance operations. That account must be configured in the product *'Application of advance'* in this way:

  .. image:: l10n_mx_edi_advance/static/src/img/product_accounting.png
    :width: 400pt
    :alt: product accounting

  * The Income Account: Must be a Current Liabilities account, sub-account of *'206 Anticipo de cliente'* (206.XX.XX).

    .. image:: l10n_mx_edi_advance/static/src/img/income_account.png
      :width: 400pt
      :alt: Income Account

- In accounting settings assign the process that will be used to apply the
  advances on the invoices.

  Note: If is used the process B is necessary a python tax with the next
  code on the invoice by the amount total:
  ``result = base_amount * 0.16``

- In accounting settings assign the product *'Application of advance'* that
  will be used to indicate that an document is an advance.

  .. image:: l10n_mx_edi_advance/static/src/img/accounting_settings.png
    :width: 500pt
    :alt: Accounting settings

- If you don't want to automatically create an advance invoice from a payment you need to create a system parameter
  with name *'l10n_mx_edi_advance_avoid_advance_on_payment'* and value *'True'*.

  .. image:: l10n_mx_edi_advance/static/src/img/avoid_payment_paramenter.png
    :width: 500pt
    :alt: System Parameter Avoid Payment

Usage
=====

- **Create** an advance.

  * Option 1 (manual): Create and pay a customer invoice by selecting the product **Application of Advance** and
    setting the correct amount.

    The invoice must have only one invoice line with quantity 1, and the amount total must be equal to the amount received.

    .. image:: l10n_mx_edi_advance/static/src/img/manual_advance_creation.png
      :width: 400pt
      :alt: Create Advance, option 1 (manual)

  * Option 2 (Automatically): From a **payment** or **payment difference** when there is **no debt**.

    When a new payment is posted or exist a payment difference, and the customer has no debt, a new advance invoice is created automatically for the outstanding credit.

    .. image:: l10n_mx_edi_advance/static/src/img/payment_difference_creation.png
      :width: 400pt
      :alt: Create Advance, option 2 (payment difference)

    .. image:: l10n_mx_edi_advance/static/src/img/payment_difference_creation_2.png
      :width: 400pt
      :alt: Create Advance, option 2.2 (payment difference)

    .. image:: l10n_mx_edi_advance/static/src/img/payment_difference_creation_3.png
      :width: 400pt
      :alt: Create Advance, option 2.3 (payment difference)

- Advance **application**:

  When the sale was concreted and the invoice is made, it's possible to add the **available advances** when the
  invoice is still in the draft state.

  * When there are available advances, a **notification** is visible for that customer and allow to add/edit advances.

    .. image:: l10n_mx_edi_advance/static/src/img/advance_notification.png
      :width: 400pt
      :alt: Advance Notification

  * In the wizard for advances, you can set the advances and the amount to use from each advance.

    .. image:: l10n_mx_edi_advance/static/src/img/add_advance.png
      :width: 400pt
      :alt: Add Advance

  * The uuid of the advance will be added in the CFDI **origin** and will be related the invoice with the advance.

    .. image:: l10n_mx_edi_advance/static/src/img/add_advance_2.png
      :width: 400pt
      :alt: Add Advance 2

  * At this point, you can **remove**, **edit** or **add** advance(s) if you consider it necessary in the same
    wizard in the last point.

- Validate **(sign)** the invoice. A new **credit note** is created and reconciled with the invoice. Applying the advance(s) amount.

  .. image:: l10n_mx_edi_advance/static/src/img/validate_invoice_with_advance.png
    :width: 400pt
    :alt: Credit Note


For more information, you can read the `Guia de llenado Anexo20 (Apéndice 6)
<https://www.sat.gob.mx/consultas/35025/formato-de-factura-electronica-(anexo-20)>`_ or the `Use case of advances
<http://omawww.sat.gob.mx/informacion_fiscal/factura_electronica/Documents/Complementoscfdi/Caso_uso_Anticipo.pdf>`_.


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

* Nhomar Hernandez <nhomar@vauxoo.com> (Designer)
* Gabriela Mogollón <gmogollon@vauxoo.com> (Developer)
* Luis Torres <luis_t@vauxoo.com> (Developer)

Maintainer
==========

.. image:: https://s3.amazonaws.com/s3.vauxoo.com/description_logo.png
   :alt: Vauxoo
   :target: https://vauxoo.com
