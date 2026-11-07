from odoo import fields, models


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    oss_location_proofs_required = fields.Boolean(
        string="Richiede due prove di localizzazione (OSS)",
        help="Vendite digitali a privati UE: la fattura si emette solo con due prove "
             "non contraddittorie del paese del cliente.")
    vies_required = fields.Boolean(
        string="Richiede partita IVA verificata VIES",
        help="Inversione contabile B2B UE: la fattura si emette solo se la partita IVA "
             "del cliente risulta valida in VIES.")
    blocked_tax_ids = fields.Many2many(
        "account.tax", "my_erp_crm_fpos_blocked_tax_rel", "fiscal_position_id", "tax_id",
        string="Vendite non ammesse",
        help="Righe con queste imposte non si fatturano con questa posizione fiscale: il "
             "trattamento IVA per questo mercato non è ancora qualificato. Esempio: "
             "servizi digitali a privati UE senza registrazione OSS non-UE.")
