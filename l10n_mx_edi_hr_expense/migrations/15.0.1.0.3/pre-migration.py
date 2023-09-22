from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    view = env.ref(
        'l10n_mx_edi_hr_expense.account_reports_journal_dashboard_kanban_view_account_manager',
        raise_if_not_found=False,
    )
    if view:
        view.unlink()
