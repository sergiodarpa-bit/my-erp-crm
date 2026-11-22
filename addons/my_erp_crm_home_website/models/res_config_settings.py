from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    my_erp_crm_apri_gestionale = fields.Boolean(related="website_id.my_erp_crm_apri_gestionale", readonly=False)
