from odoo import fields, models


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    oss_location_proofs_required = fields.Boolean(
        string="Richiede due prove di localizzazione (OSS)",
        help="Vendite digitali a privati UE: la fattura si emette solo con due prove "
             "non contraddittorie del paese del cliente (INV-IVA-04).")
    vies_required = fields.Boolean(
        string="Richiede partita IVA verificata VIES",
        help="Inversione contabile B2B UE: la fattura si emette solo se la partita IVA "
             "del cliente risulta valida in VIES (INV-IVA-03).")
