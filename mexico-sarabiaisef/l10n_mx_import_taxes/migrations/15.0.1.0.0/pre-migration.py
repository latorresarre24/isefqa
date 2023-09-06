def update_x_l10n_mx_edi_invoice_broker_id_model_data(cr):
    cr.execute("""
        INSERT INTO
            ir_model_data (name, module, model, res_id)
        SELECT
            'field_account_invoice_l10n_mx_edi_invoice_broker_id' AS name,
            'l10n_mx_import_taxes' AS module,
            'ir.model.fields' AS model,
            id AS res_id
        FROM ir_model_fields
        WHERE name='x_l10n_mx_edi_invoice_broker_id'
        AND model='account.move.line'
        LIMIT 1
        """)


def migrate(cr, version):
    if not version:
        return
    update_x_l10n_mx_edi_invoice_broker_id_model_data(cr)
