# Copyright 2019 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, exceptions, models
from collections import defaultdict


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def _grouped_orders_create_invoices_job(self, orders):
        new_delay = orders.with_delay(
            priority=self.env.context.get("queue_job_priority", None),
            eta=self.env.context.get("queue_job_eta", None),
            max_retries=self.env.context.get("queue_job_max_retries", None),
            description=self.env.context.get("queue_job_description", None),
            channel=self.env.context.get("queue_job_channel", None),
            identity_key=self.env.context.get("queue_job_identity_key", None),
        ).create_invoices_job(final=self.advance_payment_method == "all")
        if not new_delay:
            return False
        job = self.env["queue.job"].search([("uuid", "=", new_delay.uuid)])
        return job

    def enqueue_invoices(self):
        order_obj = self.env['sale.order']
        context = self.env.context
        if (self.advance_payment_method not in {'delivered', 'all'}):
            # Call standard method in these cases
            return self.create_invoices()
        sale_orders = order_obj.browse(context.get('active_ids', []))
        grouped_orders = defaultdict(lambda: order_obj.browse())
        for order in sale_orders:
            group_key = (order.partner_invoice_id.id, order.currency_id.id)
            if order.invoicing_job_ids.filtered(
                lambda x: x.state in {'pending', 'enqueued', 'started'}
            ):
                raise exceptions.UserError(_(
                    "There's already an enqueued job for invoicing the sales "
                    "order %s. Please wait until it's finished or remove it "
                    "from the selection."
                ) % (order.name, ))
            grouped_orders[group_key] |= order
        for orders in grouped_orders.values():
            job = self._grouped_orders_create_invoices_job(orders)
            if job:
                orders.sudo().write({"invoicing_job_ids": [(4, job.id)]})
