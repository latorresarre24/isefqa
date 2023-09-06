import logging
from openupgradelib import openupgrade
from odoo import api, SUPERUSER_ID
from odoo.tools import column_exists

_logger = logging.getLogger(__name__)


def migrate_property_fields(cr):
    fields_to_migrate = [
        ('product.category', 'x_studio_field_discount_account_categ_id', 'property_discount_account_id'),
        ('product.category', 'x_studio_field_return_account_categ_id', 'property_account_income_refund_id')
    ]
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model, old_column, new_column in fields_to_migrate:
        table_name = model.replace(".", "_")
        if not column_exists(cr, table_name, old_column):
            continue
        _logger.info("Model %s: migrating column %s -> %s", model, old_column, new_column)
        openupgrade.convert_to_company_dependent(env, model, old_column, new_column)


def migrate(cr, version):
    if not version:
        return
    migrate_property_fields(cr)
