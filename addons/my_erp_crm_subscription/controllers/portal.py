from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class PortalAbbonamenti(CustomerPortal):

    def _dominio_abbonamenti(self):
        # Anche un utente interno vede qui solo i suoi, come cliente.
        return [("partner_id", "child_of", request.env.user.commercial_partner_id.id)]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "subscription_count" in counters:
            Abbonamento = request.env["my_erp_crm.abbonamento"]
            values["subscription_count"] = (
                Abbonamento.search_count(self._dominio_abbonamenti()) if Abbonamento.has_access("read") else 0)
        return values

    @http.route(["/my/subscriptions", "/my/subscriptions/page/<int:page>"], type="http", auth="user", website=True)
    def portal_my_abbonamenti(self, page=1, **_kwargs):
        Abbonamento = request.env["my_erp_crm.abbonamento"]
        dominio = self._dominio_abbonamenti()
        leggibile = Abbonamento.has_access("read")
        pager = portal_pager(
            url="/my/subscriptions",
            total=Abbonamento.search_count(dominio) if leggibile else 0,
            page=page,
            step=self._items_per_page,
        )
        abbonamenti = Abbonamento.search(
            dominio, limit=self._items_per_page, offset=pager["offset"]) if leggibile else Abbonamento
        request.session["my_subscriptions_history"] = abbonamenti.ids[:100]
        values = self._prepare_portal_layout_values()
        values.update({
            "abbonamenti": abbonamenti.sudo(),
            "page_name": "subscriptions",
            "pager": pager,
            "default_url": "/my/subscriptions",
        })
        return request.render("my_erp_crm_subscription.portal_my_abbonamenti", values)

    @http.route("/my/subscriptions/<int:abbonamento_id>", type="http", auth="public", website=True)
    def portal_my_abbonamento(self, abbonamento_id, access_token=None, esito=None, **_kwargs):
        try:
            abbonamento_sudo = self._document_check_access("my_erp_crm.abbonamento", abbonamento_id, access_token)
        except (AccessError, MissingError):
            return request.redirect("/my")
        values = self._get_page_view_values(
            abbonamento_sudo, access_token,
            {"abbonamento": abbonamento_sudo, "page_name": "subscription", "esito": esito},
            "my_subscriptions_history", False)
        return request.render("my_erp_crm_subscription.portal_my_abbonamento", values)

    def _azione_abbonamento(self, abbonamento_id, access_token, azione, esito):
        """Disdetta e riattivazione: dal portale (cliente collegato) o dal link nell'email, che
        porta il codice di accesso dell'abbonamento: i clienti che comprano senza account
        devono poter disdire."""
        try:
            abbonamento_sudo = self._document_check_access("my_erp_crm.abbonamento", abbonamento_id, access_token)
        except (AccessError, MissingError):
            return request.redirect("/my")
        getattr(abbonamento_sudo, azione)()
        return request.redirect(abbonamento_sudo.get_portal_url(query_string=f"&esito={esito}"))

    @http.route("/my/subscriptions/<int:abbonamento_id>/cancel", type="http", auth="public",
                methods=["POST"], website=True)
    def portal_disdici_abbonamento(self, abbonamento_id, access_token=None, **_kwargs):
        return self._azione_abbonamento(abbonamento_id, access_token, "action_disdici", "disdetto")

    @http.route("/my/subscriptions/<int:abbonamento_id>/reactivate", type="http", auth="public",
                methods=["POST"], website=True)
    def portal_riattiva_abbonamento(self, abbonamento_id, access_token=None, **_kwargs):
        return self._azione_abbonamento(abbonamento_id, access_token, "action_riattiva", "riattivato")
