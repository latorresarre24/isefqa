from lxml.objectify import fromstring
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_mx_edi_property = fields.Many2one(
        'res.partner', 'Address Property in Construction',
        help='Use this field when the invoice require the '
        'complement to "Partial construction services". This value will be '
        'used to indicate the information of the property in which are '
        'provided the partial construction services.')

    def _l10n_mx_edi_decode_cfdi(self, cfdi_data=None):
        """If the CFDI was signed, try to adds the schemaLocation correctly"""
        result = super()._l10n_mx_edi_decode_cfdi(cfdi_data=cfdi_data)
        if not cfdi_data:
            return result
        if not isinstance(cfdi_data, bytes):
            cfdi_data = cfdi_data.encode()
        cfdi_data = cfdi_data.replace(b'xmlns__servicioparcial', b'xmlns:servicioparcial')
        cfdi = fromstring(cfdi_data)
        if 'servicioparcial' not in cfdi.nsmap:
            return result
        cfdi.attrib['{http://www.w3.org/2001/XMLSchema-instance}schemaLocation'] = '%s %s %s' % (
            cfdi.get('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation'),
            'http://www.sat.gob.mx/servicioparcialconstruccion',
            'http://www.sat.gob.mx/sitio_internet/cfd/servicioparcialconstruccion/servicioparcialconstruccion.xsd')
        result['cfdi_node'] = cfdi
        return result
