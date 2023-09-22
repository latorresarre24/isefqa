import base64
from odoo import fields, models, api


class AttachXmlsWizard(models.TransientModel):
    _name = 'attach.xmls.wizard'
    _description = 'attach.xmls.wizard'

    @api.model
    def _default_journal(self):
        type_inv = 'in_invoice'
        return self.env['account.move'].with_context(
            default_move_type=type_inv)._get_default_journal()

    @api.model
    def _get_account_domain(self):
        return [('company_id', '=', self.env.company.id)]

    dragndrop = fields.Char()
    account_id = fields.Many2one(
        'account.account',
        help='Optional field to define the account that will be used in all '
        'the lines of the invoice.\nIf the field is not set, the wizard will '
        'take the account by default.',
        domain=_get_account_domain,
    )
    journal_id = fields.Many2one(
        'account.journal', required=True,
        default=_default_journal,
        domain=[('type', '=', 'purchase')],
        help='This journal will be used in the invoices generated with this '
        'wizard.')

    @api.model
    def check_xml(self, files):
        """Method to attach xml file in purchase order and create vendor bills.
            :params: files list of xml files
            :return: dict with two elements:
                wrongfiles: list of error files
                invoices: list of attached invoices
            :rtype: dict
        """
        res = {}
        purchase_id = self._context.get('active_id', False)
        purchase = self.env['purchase.order'].browse(purchase_id)

        rule = self.env.ref('l10n_edi_document.edi_document_rule')

        for xml_file in files:
            xml_code = files.get(xml_file).replace('data:text/xml;base64,', '')
            datas = base64.b64decode(xml_code).replace(b'xmlns:schemaLocation', b'xsi:schemaLocation').replace(
                b'o;?', b'').replace(b'\xef\xbf\xbd', b'')
            attachment = self.env['ir.attachment'].create({
                'name': xml_file,
                'datas': base64.b64encode(datas),
                'description': 'EDI invoice',
                'mimetype': 'application/xml',
            })
            res = self.l10n_edi_document_validation(purchase, attachment)
            if not res['validate']:
                return {'wrongfiles': res['wrongfiles'], 'invoices': {}}
            document_data = self._prepare_invoice_document(attachment)
            invoice_document = self.env['documents.document'].sudo().create(document_data)
            res = rule.create_record(invoice_document)
            # Force mimetype
            attachment.mimetype = 'application/xml'
            if not isinstance(res, dict) or 'res_id' not in res:
                continue
            invoice = self.env['account.move'].browse(res['res_id'])
            self._create_edi_document(invoice, attachment)
            extra_data = invoice.l10n_edi_get_extra_values()
            if self.journal_id or self._context.get('journal_id'):
                extra_data['journal_id'] = self.journal_id.id or self._context.get('journal_id')
            invoice.write(extra_data)
            if self.account_id or self._context.get('account_id'):
                invoice.invoice_line_ids.write({'account_id': self.account_id.id or self._context.get('account_id')})
        invoices = {}
        wrongfiles = {}
        if isinstance(res, dict) and 'res_id' in res:
            invoices = {attachment.name: res['res_id']}
        else:
            wrongfiles = {attachment.name: "Invoice not created"}
        return {'wrongfiles': wrongfiles, 'invoices': invoices}

    def _prepare_invoice_document(self, attachment):
        return {
            'name': attachment.name,
            'folder_id': self.env.ref('documents.documents_finance_folder').id,
            'attachment_id': attachment.id,
        }

    def _create_edi_document(self, invoice, attachment):
        """Method to be overwritten from localization to create EDI document for that country"""
        return self.env['account.edi.document']

    @api.model
    def l10n_edi_document_validation(self, record, attachment):
        """Method to be overwritten from localization to validate document before attach
        :params: record
        :return: dict with two elements:
            record: validated record
            validate: boolean indicating if validation was correct or not
        :rtype: dict
        """
        return {'record': self, 'validate': True}
