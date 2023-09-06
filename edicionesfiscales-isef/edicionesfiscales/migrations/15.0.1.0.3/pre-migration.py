import logging

from odoo import tools

_logger = logging.getLogger(__name__)


def rename_fields(cr):
    fields_to_rename = [
        ('account_move_line', 'x_studio_uuid', 'cfdi_uuid'),
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


def remove_deprecated_fields(cr):
    cr.execute("DELETE FROM ir_model_fields WHERE name LIKE 'x_studio%'")
    _logger.info("Deprecated fields removed")


def migrate(cr, version):
    rename_fields(cr)
    remove_deprecated_fields(cr)
