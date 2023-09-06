from odoo import SUPERUSER_ID, api


def fix_action_window(cr, env):
    views = {
        'tree': env.ref('hr_expense.view_my_expenses_tree').id,
        'kanban': env.ref('hr_expense.hr_expense_kanban_view_header').id,
        'form': env.ref('l10n_mx_edi_hr_expense.hr_expense_view_form_mx').id,
    }
    modules = {
        'tree': 'hr_expense',
        'kanban': 'hr_expense',
        'form': 'l10n_mx_edi_hr_expense',
    }
    xml_act_win_views = {
        'tree': 'hr_expense_actions_my_unsubmitted_tree',
        'kanban': 'hr_expense_actions_my_unsubmitted_kanban',
        'form': 'hr_expense_actions_my_unsubmitted_form_mx',
    }
    act_window_id = env.ref('hr_expense.hr_expense_actions_my_unsubmitted').id
    act_views = env['ir.actions.act_window.view'].search([('act_window_id', '=', act_window_id)])
    for act_view in act_views:
        cr.execute("""UPDATE ir_act_window_view set view_id=%s WHERE view_mode=%s AND act_window_id=%s""", [
            views[act_view.view_mode], act_view.view_mode, act_window_id])
        cr.execute("""
                   SELECT
                       id
                   FROM
                       ir_model_data
                   WHERE
                       model = 'ir.actions.act_window.view'
                   AND name=%s AND module=%s""",
                   [xml_act_win_views[act_view.view_mode],  modules[act_view.view_mode]])
        if cr.fetchall():
            continue
        cr.execute("""
            INSERT INTO ir_model_data (name, module, model, res_id)
               VALUES (%s, %s, 'ir.actions.act_window.view', %s)
           """, [xml_act_win_views[act_view.view_mode], modules[act_view.view_mode], act_view.id])


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    fix_action_window(cr, env)
