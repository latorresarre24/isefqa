# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import base64
from odoo import models, api, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def insert_attachment(self, files, filename):
        attachment = self.env['ir.attachment'].sudo()
        # if asuffix is required add to this dict the input name and
        # the suffix to add to the file name
        suffixes = {
            'purchase_order': 'PO',
            'receipt': 'AC',
        }
        for fname, xml_file in files.items():
            if not xml_file:
                continue
            suffix = suffixes.get(fname, '')
            new_name = filename if not suffix else '%s_%s' % (filename, suffix)
            attachment |= attachment.create({
                'name': '%s.%s' % (new_name, xml_file.mimetype.split('/')[1]),
                'datas': base64.b64encode(xml_file.getvalue()),
                'res_model': self._name,
                'res_id': self.id,
            })
        return attachment

    @api.model
    def process_errors(self, wrongfiles):  # pylint:disable=too-complex
        errors = []
        for cfdi in wrongfiles:
            errors.append(_('\nErrors on file: %s') % cfdi)
            for error in wrongfiles[cfdi]:
                if error == 'xml64':
                    continue

                data = wrongfiles[cfdi][error]
                if error == 'signed':
                    errors.append(_('The invoice is not signed, UUID missing'))
                    continue
                if error == 'cancel':
                    errors.append(_('The CFDI invoice is cancelled'))
                    continue
                if error == 'uuid_duplicate':
                    errors.append(_('The invoice UUID is duplicated, the UUID is already in our system %s') % data)
                    continue
                if error == 'rfc':
                    errors.append(_('The RFC does not match with our RFC: %s - %s') % data)
                    continue
                if error == 'payment_reference':
                    errors.append(_('The reference is already on the system: %s - %s') % data)
                    continue
                if error == 'version':
                    errors.append(_('The CFDI version is not valid. Valid versions: 4.0 or 3.3'))
                    continue
                if error == 'supplier':
                    errors.append(_('The invoice has not supplier RFC: %s') % data)
                    continue
                if error == 'currency':
                    errors.append(_('Invalid currency: %s') % data)
                    continue
                if error == 'wrong_taxes':
                    errors.append(_('We were unable to identify the taxes in the invoice: %s') % data)
                    continue
                if error == 'withno_account':
                    errors.append(_('Taxes without account: %s') % data)
                    continue
                if error == 'folio':
                    errors.append(_('The folios: %s, %s do not match.') % data)
                    continue
                if error == 'rfc_supplier':
                    errors.append(_('The emitter RFC does not match with the supplier. %s != %s') % data)
                    continue
                if error == 'amount':
                    errors.append(
                        _('The total in the invoice does not match with the CFDI Total. %s != %s') % data)
                    continue
                if error == 'invoice_not_found':
                    errors.append(_('Invoice not Found: %s') % data)
                    continue
                if error == 'no_xml_related_uuid':
                    errors.append(_('The CFDI is a substitute CFDI, nut the related UUID is missing'))
                    continue
        return '\n'.join(errors)
