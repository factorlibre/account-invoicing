# Copyright 2023 Ecosoft Co., Ltd. (http://ecosoft.co.th)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    manual_currency = fields.Boolean(
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    is_manual = fields.Boolean(compute="_compute_currency")
    type_currency = fields.Selection(
        selection=lambda self: self._get_label_currency_name(),
        default=lambda self: self._get_label_currency_name()[0][0],
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    manual_currency_rate = fields.Float(
        digits="Manual Currency",
        tracking=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
        help="Set new currency rate to apply on the invoice\n."
        "This rate will be taken in order to convert amounts between the "
        "currency on the purchase order and last currency",
    )
    total_company_currency = fields.Monetary(
        compute="_compute_total_company_currency", currency_field="company_currency_id"
    )
    currency_diff = fields.Boolean(
        compute="_compute_currency_diff",
        store=True,
    )

    @api.depends("currency_id")
    def _compute_currency_diff(self):
        for rec in self:
            rec.currency_diff = rec.company_currency_id != rec.currency_id

    @api.depends("line_ids.balance")
    def _compute_total_company_currency(self):
        """Convert total currency to company currency"""
        for rec in self:
            # check manual currency
            if rec.manual_currency:
                rate = (
                    rec.manual_currency_rate
                    if rec.type_currency == "inverse_company_rate"
                    else (1.0 / rec.manual_currency_rate)
                )
                rec.total_company_currency = rec.amount_total * rate
            # default rate currency
            else:
                rec.total_company_currency = rec.currency_id._convert(
                    rec.amount_total,
                    rec.company_currency_id,
                    rec.company_id,
                    rec.date or fields.Date.today(),
                )

    def _get_label_currency_name(self):
        """Get label related currency"""
        names = {
            "company_currency_name": (
                self.env["res.company"].browse(self._context.get("company_id"))
                or self.env.company
            ).currency_id.name,
            "rate_currency_name": _("Currency"),
        }
        return [
            [
                "company_rate",
                _("%(rate_currency_name)s per 1 %(company_currency_name)s", **names),
            ],
            [
                "inverse_company_rate",
                _("%(company_currency_name)s per 1 %(rate_currency_name)s", **names),
            ],
        ]

    @api.onchange("manual_currency", "type_currency", "currency_id", "date")
    def _onchange_currency_change_rate(self):
        today = fields.Date.today()
        company_currency = self.env.company.currency_id
        amount_currency = company_currency._get_conversion_rate(
            company_currency,
            self.currency_id,
            self.company_id,
            self.date or today,
        )
        if self.type_currency == "inverse_company_rate":
            amount_currency = 1.0 / amount_currency
        self.manual_currency_rate = amount_currency

    @api.depends("currency_id")
    def _compute_currency(self):
        for rec in self:
            rec.is_manual = rec.currency_id != rec.company_id.currency_id

    def action_refresh_currency(self):
        self.ensure_one()
        if self.state != "draft":
            raise ValidationError(_("Rate currency can refresh state draft only."))
        self.with_context(check_move_validity=False)._onchange_currency_change_rate()
        return True

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Change string name to company currency"""
        result = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == "form":
            company_currency_name = (
                self.env["res.company"].browse(self._context.get("company_id"))
                or self.env.company
            ).currency_id.name
            doc = etree.XML(result["arch"])
            # Total company currency
            node = doc.xpath("//field[@name='total_company_currency']")
            if node:
                node[0].set("string", "Total ({})".format(company_currency_name))
            result["arch"] = etree.tostring(doc, encoding="unicode")
        return result

    @api.onchange("manual_currency_rate")
    def _onchange_manual_currency_rate(self):
        last_rate = self.env["res.currency.rate"]._get_last_rates_for_companies(
            self.company_id | self.env.company
        )
        for move in self:
            if move.manual_currency and not move.manual_currency_rate:
                move.manual_currency_rate = (
                    last_rate[self.company_id]
                    if move.type_currency == "inverse_company_rate"
                    else (1.0 / last_rate[self.company_id])
                )

    @api.model
    def _update_balance_manual_currency(self, lines):
        for line in lines:
            balance = line.company_id.currency_id.round(
                line.amount_currency / (line.currency_rate or 1)
            )
            line.with_context(
                check_move_validity=False, avoid_currency_write=True
            ).balance = balance

    @api.model_create_multi
    def create(self, vals_list):
        ret = super().create(vals_list)
        lines = ret.filtered(
            lambda rec: rec.manual_currency_rate
            and not rec.is_invoice(include_receipts=True)
        ).mapped("line_ids")
        self._update_balance_manual_currency(lines)
        return ret

    def write(self, vals):
        if "currency_id" in vals:
            if self._context.get("avoid_currency_write"):
                vals.pop("currency_id")
            else:
                self = self.with_context(avoid_currency_write=True)
        ret = super().write(vals)
        if "manual_currency_rate" in vals:
            lines = self.filtered(
                lambda move: not move.is_invoice(include_receipts=True)
            ).mapped("line_ids")
            self._update_balance_manual_currency(lines)
        return ret

    @api.model
    def _cleanup_write_orm_values(self, record, vals):
        if "currency_id" in vals:
            vals.pop("currency_id")
        return super()._cleanup_write_orm_values(record, vals)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.depends(
        "currency_id", "company_id", "move_id.date", "move_id.manual_currency_rate"
    )
    def _compute_currency_rate(self):
        res = super()._compute_currency_rate()
        for line in self:
            if not line.move_id.manual_currency:
                continue
            # Currency Rate on move line use 'company_rate'
            manual_rate = line.move_id._origin.manual_currency_rate or 1
            rate = (
                manual_rate
                if line.move_id.type_currency == "company_rate"
                else (1.0 / manual_rate)
            )
            line.currency_rate = rate
        return res
