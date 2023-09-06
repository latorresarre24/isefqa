def update_l10n_mx_edi_invoice_broker_id_field(cr):
    # /!\ NOTE: This migration is to undo the previous migration. XD
    cr.execute("""
        UPDATE account_move_line aml
            SET l10n_mx_edi_invoice_broker_id = x_l10n_mx_edi_invoice_broker_id
        WHERE x_l10n_mx_edi_invoice_broker_id IS NOT NULL;
        """)


def migrate(cr, version):
    if not version:
        return
    update_l10n_mx_edi_invoice_broker_id_field(cr)
