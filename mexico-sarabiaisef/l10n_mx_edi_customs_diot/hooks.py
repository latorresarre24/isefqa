def pre_init_hook(cr):
    create_and_fill_computed_fields(cr)


def create_and_fill_computed_fields(cr):
    """Create and fill computed fields on account_move to avoid slow compute when existing many account move records
    """
    # Create fields
    query_add_column = """
        ALTER TABLE account_move
        ADD COLUMN IF NOT EXISTS l10n_mx_edi_customs_total numeric,
        ADD COLUMN IF NOT EXISTS l10n_mx_edi_customs_base numeric,
        ADD COLUMN IF NOT EXISTS l10n_mx_edi_customs_id integer
    """
    cr.execute(query_add_column)

    query_fill = """
        UPDATE
            account_move AS am
        SET
            l10n_mx_edi_customs_total = 0,
            l10n_mx_edi_customs_base = 0
        WHERE
            am.l10n_mx_edi_customs_id IS NULL
    """
    cr.execute(query_fill)
