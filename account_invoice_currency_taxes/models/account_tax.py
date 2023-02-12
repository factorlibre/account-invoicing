# © 2023 FactorLibre - Javier Iniesta <javier.iniesta@factorlibre.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, models
from odoo.tools.misc import formatLang


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _prepare_tax_totals(self, base_lines, currency, tax_lines=None):
        res = super()._prepare_tax_totals(base_lines, currency, tax_lines)
        if not base_lines:
            return res
        record = base_lines[0]["record"]
        line_currency = record.currency_id
        company = record.company_id
        currency = company.currency_id
        if (
            record._name != "account.move.line"
            or not record.move_id.invoice_date
            or line_currency == currency
        ):
            return res
        res["display_company_currency_taxes"] = True
        for data_list in res["groups_by_subtotal"].values():
            for group in data_list:
                base_amount_company_currency = line_currency._convert(
                    group["tax_group_base_amount"],
                    currency,
                    company,
                    record.move_id.invoice_date,
                )
                amount_company_currency = line_currency._convert(
                    group["tax_group_amount"],
                    currency,
                    company,
                    record.move_id.invoice_date,
                )
                group.update(
                    {
                        "tax_group_base_amount_company_currency": base_amount_company_currency,
                        "tax_group_amount_company_currency": amount_company_currency,
                        "formatted_tax_group_base_amount_company_currency": formatLang(
                            self.env,
                            base_amount_company_currency,
                            currency_obj=currency,
                        ),
                        "formatted_tax_group_amount_company_currency": formatLang(
                            self.env, amount_company_currency, currency_obj=currency
                        ),
                    }
                )
        return res
