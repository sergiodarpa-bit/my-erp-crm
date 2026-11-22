from odoo import fields, models


class Website(models.Model):
    _inherit = "website"

    my_erp_crm_apri_gestionale = fields.Boolean(
        "La radice apre il gestionale",
        help="L'indirizzo principale del sito (/) porta al gestionale (/odoo: accesso, poi la "
        "Panoramica) invece della pagina iniziale del sito. Le altre pagine del sito restano "
        "raggiungibili.",
    )
