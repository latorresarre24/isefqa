# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class SessionXmlReport(models.AbstractModel):
    _name = "report.l10n_mx_edi_pos.report_xml_session"
    _description = "XML report for POS session"

    @api.model
    def _get_report_values(self, docids, data=None):
        sessions = self.env['pos.session'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'pos.session',
            'docs': sessions,
            'cfdi': data.get('cfdi', ''),
        }
