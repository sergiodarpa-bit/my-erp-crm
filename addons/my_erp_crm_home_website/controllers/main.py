from odoo import http
from odoo.http import request

from odoo.addons.website.controllers.main import Website


class WebsiteGestionale(Website):
    @http.route()
    def index(self, **kw):
        # Il sito che serve il gestionale: la radice porta a /odoo (accesso, poi la Panoramica)
        # invece della pagina iniziale del sito, che era il negozio. Un vero reindirizzamento:
        # la «Homepage» del sito impostata su /odoo dà errore 500.
        if self.env.website.my_erp_crm_apri_gestionale:
            return request.redirect("/odoo")
        return super().index(**kw)
