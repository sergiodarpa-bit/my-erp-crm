from odoo import api, fields, models

BRAND_BUTTON = "#0F7A73"
ODOO_BUTTON = "#875A7B"


class ResCompany(models.Model):
    _inherit = "res.company"

    # Colori di serie dei pulsanti (email e, dalla 20, portale e pagina di accesso).
    email_primary_color = fields.Char(default="#FFFFFF")
    email_secondary_color = fields.Char(default=BRAND_BUTTON)

    @api.model
    def _my_erp_crm_apply_brand_colors(self):
        """Le aziende rimaste col viola di serie prendono il colore del marchio
        (eseguito a ogni installazione e aggiornamento del modulo)."""
        companies = self.search([("email_secondary_color", "in", (False, ODOO_BUTTON))])
        companies.write({"email_primary_color": "#FFFFFF", "email_secondary_color": BRAND_BUTTON})
