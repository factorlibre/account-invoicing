# Copyright 2017 Eficent Business and IT Consulting Services S.L.
# Copyright 2017 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).


def pre_init_hook(cr):
    cr.execute(
        """
ALTER TABLE
    account_invoice
ADD COLUMN IF NOT EXISTS
    max_line_sequence integer
        """
    )
    cr.execute(
        """
ALTER TABLE
    account_invoice_line
ADD COLUMN IF NOT EXISTS
    sequence integer
        """
    )
    cr.execute(
        """
ALTER TABLE
    account_invoice_line
ADD COLUMN IF NOT EXISTS
    sequence2 integer
        """
    )
