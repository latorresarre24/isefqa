import logging
import csv

from odoo import tools

_logger = logging.getLogger(__name__)


MODELS_TO_DELETE = (
    'ir.actions.act_window',
    'ir.actions.act_window.view',
    'ir.actions.report.xml',
    'ir.actions.todo',
    'ir.actions.url',
    'ir.actions.wizard',
    'ir.cron',
    'ir.model',
    'ir.model.access',
    'ir.model.fields',
    'ir.module.repository',
    'ir.property',
    'ir.report.custom',
    'ir.report.custom.fields',
    'ir.rule',
    'ir.sequence',
    'ir.sequence.type',
    'ir.ui.menu',
    'ir.ui.view',
    'ir.ui.view_sc',
    'ir.values',
    'res.groups',
)


MODULES_TO_CLEAN = [
    'l10n_mx_edi_vendor_bills',
    'account_cancel',
    'company_country',
    'l10n_mx_edi_bank',
    'l10n_mx_edi_reports',
    'l10n_mx_edi_customer_bills',
    'website_order',
]


def model_to_table(model):
    """ Get a table name according to a model name In case the table name is set on
    an specific model manually instead the replacement, then you need to add it
    in the mapped dictionary.
    """
    model_table_map = {
        'ir.actions.client': 'ir_act_client',
        'ir.actions.actions': 'ir_actions',
        'ir.actions.report.custom': 'ir_act_report_custom',
        'ir.actions.report.xml': 'ir_act_report_xml',
        'ir.actions.act_window': 'ir_act_window',
        'ir.actions.act_window.view': 'ir_act_window_view',
        'ir.actions.url': 'ir_act_url',
        'ir.actions.act_url': 'ir_act_url',
        'ir.actions.server': 'ir_act_server',
    }
    name = model_table_map.get(model)
    if name is not None:
        return name.replace('.', '_')
    if model is not None:
        return model.replace('.', '_')
    return ''


def remove_deprecated(cr):
    for module in MODULES_TO_CLEAN:
        cr.execute("UPDATE ir_module_module SET state = 'uninstalled' WHERE name = %s", (module,))
        _logger.info("deleting module %s", (module))


def rename_fields(cr):
    fields_to_rename = [
        ('product_template', 'x_studio_field_isef_isbn', 'isbn'),
    ]

    # Rename columns
    for (model, old_name, new_name) in fields_to_rename:
        # Delete if the new column already exists
        cr.execute("ALTER TABLE %s DROP COLUMN IF EXISTS %s" % (model, new_name))
        # Rename old columns
        if tools.column_exists(cr, model, old_name):
            _logger.info("Model %s: renaming column %s -> %s", model, old_name, new_name)
            tools.rename_column(cr, model, old_name, new_name)
            # Delete old fields from ir_model_fields
            cr.execute("DELETE FROM ir_model_fields WHERE name=%s and model=%s", [old_name, model])


def delete_deprecated_fields(cr):
    fields_to_remove = [
        ('account_invoice_line', 'x_studio_uuid'),
        ('account_invoice', 'x_studio_uuid'),
        ('product_product', 'x_studio_field_klk81'),
        ('product_product', 'x_studio_isbn'),
        ('product_product', 'x_studio_field_isef_isbd')
    ]

    for (model, column_name) in fields_to_remove:
        # Delete if the new column already exists
        _logger.info("Model %s: droping column %s ", model, column_name)
        cr.execute("ALTER TABLE %s DROP COLUMN IF EXISTS %s" % (model, column_name))


def delete_deprecated_models(cr):
    models_to_remove = [
        'x_avance_prod'
    ]

    for model in models_to_remove:
        _logger.info("Model %s: deleting deprecated", model)
        # Delete data
        cr.execute("DROP TABLE IF EXISTS %s" % (model,))
        # Delete model
        cr.execute("DELETE FROM ir_model WHERE model='%s'" % (model,))
        cr.execute("DELETE FROM ir_model_fields WHERE model='%s'" % (model,))


def module_delete(cr, module_name):
    _logger.info("deleting module %s", (module_name))

    def table_exists(table_name):
        cr.execute("SELECT count(1) "
                   "FROM information_schema.tables "
                   "WHERE table_name = %s and table_schema='public'",
                   [table_name])
        return cr.fetchone()[0]
    cr.execute("SELECT res_id, model FROM ir_model_data WHERE module=%s and model in %s order by res_id desc",
               (module_name, MODELS_TO_DELETE))
    data_to_delete = cr.fetchall()
    for rec in data_to_delete:
        table = model_to_table(rec[1])
        cr.execute("SELECT count(*) FROM ir_model_data WHERE model = %s and res_id = %s", [rec[1], rec[0]])
        count1 = cr.dictfetchone()['count']

        if count1 > 1:
            continue

        # ir_ui_view
        if table == 'ir_ui_view':
            cr.execute('SELECT model FROM ir_ui_view WHERE id = %s', (rec[0],))
            t_name = cr.fetchone()
            table_name = model_to_table(t_name[0])
            cr.execute("SELECT viewname FROM pg_catalog.pg_views WHERE viewname = %s", [table_name])

            if cr.fetchall():
                cr.execute('drop view %s CASCADE', (table_name))

            cr.execute('DELETE FROM ir_model_constraint WHERE model=%s', (rec[0],))
            cr.execute('DELETE FROM %s WHERE inherit_id=%s', (table, rec[0],))
            view_exists = cr.fetchone()

            if bool(view_exists):
                cr.execute('DELETE FROM %s WHERE id=%s', (table, rec[0],))

        # ir_act_window:
        if table == 'ir_act_window' and table_exists('board_board_line'):
            cr.execute('SELECT count(1) FROM board_board_line WHERE action_id = %s', (rec[0],))
            count = cr.fetchone()[0]

            if not count:  # yes, there is a bug here. The line is not
                # correctly indented, but fixing the bug creates some
                # problems after.
                cr.execute('DELETE FROM ' + table + ' WHERE id=%s', (rec[0],))

        elif table == 'ir_model':
            if table_exists('ir_model_constraint'):
                cr.execute('DELETE FROM ir_model_constraint WHERE model=%s', (rec[0],))
            if table_exists('ir_model_relation'):
                cr.execute('DELETE FROM ir_model_relation WHERE model=%s', (rec[0],))
            cr.execute('DELETE FROM ' + table + ' WHERE id=%s', (rec[0],))
        else:
            cr.execute('DELETE FROM ' + table + ' WHERE id=%s', (rec[0],))

        # also DELETE dependencies:
        cr.execute('DELETE FROM ir_module_module_dependency WHERE module_id = %s', (rec[0],))

    cr.execute("DELETE FROM ir_model_data WHERE module=%s", (module_name,))
    cr.execute('UPDATE ir_module_module set state=%s WHERE name=%s', ('uninstalled', module_name))


def asset_from_old_version(cr):
    """ In old versions the asset are in views of web.asset but in v15 they was move to setup in the manifest
    during the migration process of the BD, odoo take all the paths of assets and store inside the model ir_asset
    then if in the back version has assets of modules than are been deprecated in V15, it will result in problem
    for call the asset of they modules. For that reason the best option is delete all record of ir_asset
    """
    cr.execute("delete from ir_asset;")


def update_city_codes(cr):
    with tools.file_open("l10n_mx_edi_extended/data/res.city.csv", "r") as csv_file:
        for row in csv.DictReader(csv_file, delimiter='|', fieldnames=['l10n_mx_edi_code', 'name', 'state_xml_id']):
            cr.execute(
                """
                UPDATE 
                    res_city
                SET 
                    l10n_mx_edi_code = %(l10n_mx_edi_code)s
                WHERE 
                    name = %(name)s
                    AND l10n_mx_edi_code IS NULL
                """,
                row,
            )


def create_missing_edi_payments(cr):
    """Create EDI documents (account.edi.document) for payments

    Odoo doesn't create EDI documents when migrating payments, which makes CFDI-related fields
    (e.g. CFDI UUID) to don't be accessible.

    Issue reported to Odoo:
    https://www.odoo.com/my/task/2679440
    """
    _logger.info("Creating missing EDI documents for payments")
    cr.execute(
        """
        WITH payment_cfdi AS (
            SELECT
                MAX(id) AS id,
                res_id AS payment_id
            FROM
                ir_attachment
            WHERE
                res_model = 'account.payment'
                AND name ilike '%.xml'
            GROUP BY
                res_id
        ),
        payment_wo_edi AS (
            SELECT
                payment.id,
                payment.move_id
            FROM
                account_payment AS payment
            LEFT OUTER JOIN
                account_edi_document AS edi
                ON edi.move_id = payment.move_id
            WHERE
                edi.id IS NULL
        ),
        edi_format AS (
            SELECT
                id
            FROM
                account_edi_format
            WHERE
                code = 'cfdi_3_3'
            LIMIT 1
        )
        INSERT INTO account_edi_document (
            move_id,
            edi_format_id,
            attachment_id,
            state,
            create_uid,
            create_date,
            write_uid,
            write_date
        )
        SELECT
            payment.move_id,
            edi_format.id AS edi_format_id,
            cfdi.id AS attachment_id,
            CASE
                WHEN l10n_mx_edi_sat_status = 'cancelled' THEN 'cancelled'
                ELSE 'sent'
                END AS state,
            1 AS create_uid,
            NOW() at time zone 'UTC' AS create_date,
            1 AS write_uid,
            NOW() at time zone 'UTC' AS write_date
        FROM
            payment_wo_edi AS payment
        INNER JOIN
            account_move AS move
            ON move.id = payment.move_id
        INNER JOIN
            payment_cfdi AS cfdi
            ON cfdi.payment_id = payment.id
        CROSS JOIN
            edi_format
        WHERE
            move.state = 'posted';
        """
    )
    _logger.info("Created %d documents", cr.rowcount)


def migrate(cr, version):
    if not version:
        return
    remove_deprecated(cr)
    rename_fields(cr)
    delete_deprecated_fields(cr)
    delete_deprecated_models(cr)
    asset_from_old_version(cr)
    update_city_codes(cr)
    create_missing_edi_payments(cr)
