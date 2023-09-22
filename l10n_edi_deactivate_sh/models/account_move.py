# Copyright 2021 Vauxoo
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import os

from odoo import models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        if self._get_odoo_sh_environment() in ['staging', 'dev']:
            self._l10n_edi_deactivate()
        return super()._post(soft=soft)

    @api.model
    def _get_odoo_sh_environment(self):
        """Get the Odoo Sh environment type
        :return: The instance environment type. production | staging | dev
        :rtype: string
        """
        return os.environ.get('ODOO_STAGE', False)

    @api.model
    def _l10n_edi_deactivate(self):
        if self._l10n_edi_is_installed('CR'):
            activated_companies = self.env["res.company"].sudo().search([("l10n_cr_edi_test_env", "=", False)])
            activated_companies.write({"l10n_cr_edi_test_env": True})

    @api.model
    def _l10n_edi_is_installed(self, country_code):
        country_code = country_code.upper()
        if country_code == 'CR':
            return "l10n_cr_edi_test_env" in self.env.company
        return False
