from odoo import SUPERUSER_ID, http
from odoo.http import request
from odoo.tools.misc import file_path

from odoo.addons.web.controllers.binary import Binary

BRAND_LOGO = "my_erp_crm_brand/static/img/company_logo.png"


class Binary(Binary):

    @http.route()
    def company_logo(self, dbname=None, **kw):
        """Finché l'azienda non carica il proprio logo, mostra quello di my-erp-crm
        al posto del segnaposto "Your logo" (pagina di accesso, portale...)."""
        if request.db:
            try:
                if kw.get("company"):
                    company = request.env["res.company"].sudo().browse(int(kw["company"]))
                else:
                    uid = request.session.uid or SUPERUSER_ID
                    company = request.env["res.users"].sudo().browse(uid).company_id
                if company.exists() and company.uses_default_logo:
                    return http.Stream.from_path(file_path(BRAND_LOGO)).get_response()
            except Exception:  # noqa: BLE001 - in caso di dubbio si torna al comportamento standard
                pass
        return super().company_logo(dbname=dbname, **kw)
