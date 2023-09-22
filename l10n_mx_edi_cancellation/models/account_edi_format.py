import json
from zeep import Client
from zeep.transports import Transport

from odoo import models, _


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _l10n_mx_edi_finkok_cancel(self, move, credentials, cfdi):
        """Overwrite the cancel method to:
            - Get the cancellation date from the acuse
            - Show the fiscal folios related to an invoice
            - Adapt to the new SAT changes where is required the cancellation type"""
        company = move.company_id
        certificates = company.l10n_mx_edi_certificate_ids
        certificate = certificates.sudo().get_valid_certificate()
        cer_pem = certificate.get_pem_cer(certificate.content)
        key_pem = certificate.get_pem_key(certificate.key, certificate.password)
        uuid = move.l10n_mx_edi_cfdi_uuid
        cancellation_data = (
            move.l10n_mx_edi_cancellation or move.payment_id.l10n_mx_edi_cancellation or '').split('|')
        try:
            transport = Transport(timeout=20)
            client = Client(credentials['cancel_url'], transport=transport)
            factory = client.type_factory('apps.services.soap.core.views')
            uuid_type = factory.UUID()
            uuid_type.UUID = uuid or ''
            uuid_type.Motivo = cancellation_data[0]
            if cancellation_data[0] == '01' and move.l10n_mx_edi_cancel_invoice_id and \
                    move.l10n_mx_edi_cancel_invoice_id != move:
                uuid_type.FolioSustitucion = move.l10n_mx_edi_cancel_invoice_id.l10n_mx_edi_cfdi_uuid
            docs_list = factory.UUIDArray(uuid_type)
            response = client.service.cancel(
                docs_list,
                credentials['username'],
                credentials['password'],
                company.vat,
                cer_pem,
                key_pem,
            )
        except Exception as e:
            return {
                'errors': [_("The Finkok service failed to cancel with the following error: %s", str(e))],
            }

        related = False
        if move.l10n_mx_edi_cancellation != '01':
            related = self._l10n_mx_edi_finkok_get_documents_related(move, credentials['username'],
                                                                     credentials['password'], uuid, cer_pem, key_pem)
        if related:
            return {
                'errors': [_('The next fiscal folios are related with this document:')] + related,
            }

        if not getattr(response, 'Folios', None):
            code = getattr(response, 'CodEstatus', None)
            msg = _(
                "Cancelling got an error") if code else _('A delay of 2 hours has to be respected before to cancel')
        else:
            code = getattr(response.Folios.Folio[0], 'EstatusUUID', None)
            cancelled = code in ('201', '202')  # cancelled or previously cancelled
            # no show code and response message if cancel was success
            code = '' if cancelled else code
            msg = '' if cancelled else _("Cancelling got an error")

        errors = []
        if code:
            errors.append(_("Code : %s") % code)
        if msg:
            errors.append(_("Message : %s") % msg)
        if errors:
            return {'errors': errors}

        # section to ensure that the SAT has received the cancel request
        sat_status = self._l10n_mx_edi_finkok_get_status(move, credentials['username'], credentials['password'],
                                                         move.l10n_mx_edi_cfdi_supplier_rfc,
                                                         move.l10n_mx_edi_cfdi_customer_rfc, uuid, move.amount_total)
        status = sat_status and getattr(sat_status, 'sat', None) and getattr(
            sat_status['sat'], 'EstatusCancelacion', None)
        if not status or status == 'None':
            return {'errors': [_(
                'The PAC has sent this document to cancel, but the SAT has not processed it yet. Please try again in '
                'a few minutes or wait for the automatic action. SAT status for cancellation: %s') % getattr(
                    sat_status, 'EsCancelable', _('Not defined'))]}

        # Get the cancellation data from finkok
        response = self._l10n_mx_edi_finkok_get_receipt(
            move, credentials['username'], credentials['password'], company.vat, uuid)
        if not response or not getattr(response, 'date', None):
            return {'success': True}
        date = response.date
        move.l10n_mx_edi_cancellation_date = date.split('T')[0]
        move.l10n_mx_edi_cancellation_time = date.split('T')[1][:8]

        return {'success': True}

    def _l10n_mx_edi_finkok_get_status(self, move, username, password, supplier_rfc, customer_rfc, uuid, total):
        """Check the possible form of cancellation and the status of the CFDI.

        It allows to identify if the CFDI is cancellable.
        :param username: The username provided by the Finkok platform.
        :type str
        :param password: The password provided by the Finkok platform.
        :type str
        :param supplier_rfc: Taxpayer id - The RFC issuer of the invoices to consult.
        :type str
        :param customer_rfc: Rtaxpayer_id - The RFC receiver of the CFDI to consult.
        :type str
        :param uuid: The UUID of the CFDI to consult.
        :type str
        :param total:The value of the total attribute of the CFDI.
        :type float
        :returns: AcuseSatEstatus statusResponse  https://wiki.finkok.com/doku.php?id=get_sat_status
        :rtype: suds.sudsobject
        """
        url = self._l10n_mx_edi_get_finkok_credentials_company(move.company_id)['cancel_url']
        try:
            transport = Transport(timeout=20)
            client = Client(url, transport=transport)
            return client.service.get_sat_status(
                username, password, supplier_rfc, customer_rfc, uuid=uuid, total=total)
        except Exception:
            return False

    def _l10n_mx_edi_finkok_get_documents_related(self, move, username, password, uuid, cer, key):
        # Verify if document can be cancelled
        supplier_rfc = move.l10n_mx_edi_cfdi_supplier_rfc
        sat_status = self._l10n_mx_edi_finkok_get_status(move, username, password, supplier_rfc,
                                                         move.l10n_mx_edi_cfdi_customer_rfc, uuid, move.amount_total)
        if not sat_status or sat_status.sat and sat_status.sat.EsCancelable != 'No Cancelable':
            return []

        url = self._l10n_mx_edi_get_finkok_credentials_company(move.company_id)['cancel_url']
        try:
            transport = Transport(timeout=20)
            client = Client(url, transport=transport)
            documents = client.service.get_related(username, password, supplier_rfc, uuid=uuid, cer=cer, key=key)
        except Exception:
            return []

        if getattr(documents, 'Padres', None) is None:
            return []

        # Get the documents related to the invoice to cancel
        uuids = []
        for padre in documents.Padres.Padre:
            uuids.append(getattr(padre, 'uuid', ''))

        return uuids

    def _l10n_mx_edi_finkok_get_receipt(self, move, username, password, vat, uuid, client=False):
        """get_receipt from finkok"""
        if not client:
            url = self._l10n_mx_edi_get_finkok_credentials(move)['cancel_url']
            transport = Transport(timeout=20)
            client = Client(url, transport=transport)
        try:
            return client.service.get_receipt(username, password, vat, uuid)
        except Exception as e:
            self.l10n_mx_edi_log_error(str(e))
        return False

    def _l10n_mx_edi_sw_cancel(self, move, credentials, cfdi):
        """Overwrite the cancel method to:
            - Adapt to the new SAT changes where is required the cancellation type"""

        uuid_replace = move.l10n_mx_edi_cancel_invoice_id.l10n_mx_edi_cfdi_uuid
        headers = {
            'Authorization': "bearer " + credentials['token'],
            'Content-Type': "application/json"
        }
        certificates = move.company_id.l10n_mx_edi_certificate_ids
        certificate = certificates.sudo().get_valid_certificate()
        cancellation_data = (move.l10n_mx_edi_cancellation or '').split('|')
        payload_dict = {
            'rfc': move.company_id.vat,
            'b64Cer': certificate.content.decode('UTF-8'),
            'b64Key': certificate.key.decode('UTF-8'),
            'password': certificate.password,
            'uuid': move.l10n_mx_edi_cfdi_uuid,
            'motivo': cancellation_data[0],
        }
        if uuid_replace:
            payload_dict['folioSustitucion'] = uuid_replace
        payload = json.dumps(payload_dict)

        response_json = self._l10n_mx_edi_sw_call(credentials['cancel_url'], headers, payload=payload.encode('UTF-8'))

        cancelled = response_json['status'] == 'success'
        if cancelled:
            return {
                'success': cancelled
            }

        code = response_json.get('message')
        msg = response_json.get('messageDetail')
        errors = []
        if code:
            errors.append(_("Code : %s") % code)
        if msg:
            errors.append(_("Message : %s") % msg)
        return {'errors': errors}
