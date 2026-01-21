from openupgradelib import openupgrade

from odoo import tools


@openupgrade.migrate()
def migrate(env, version):
    column_exists = tools.sql.column_exists
    create_column = tools.sql.create_column

    if not column_exists(env.cr, "account_move", "currency_rate_amount"):
        create_column(env.cr, "account_move", "currency_rate_amount", "numeric")
