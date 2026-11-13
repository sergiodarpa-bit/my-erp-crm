"""Il riepilogo periodico senza nulla che si scarichi dai server di Odoo S.A.

- Le icone degli indicatori: il modulo originale le prende da download.odoocdn.com; qui le
  serve il server stesso (sono le stesse icone, nei moduli installati).
- I consigli d'uso: quasi tutti mostrano immagini ospitate su download.odoocdn.com (e uno
  pubblicizza i plugin di posta di Odoo); il riepilogo li salta e prende solo quelli senza
  indirizzi di Odoo.

Ogni email aperta, altrimenti, scaricherebbe quelle immagini da lì.
"""

from odoo import api, models
from odoo.addons.digest.models.digest import ODOO_ICONS_CDN_URL
from odoo.fields import Domain

CONTESTO = "my_erp_crm_senza_server_odoo"
SERVER_DI_ODOO = ("odoocdn.com", "odoo.com")


class DigestDigest(models.Model):
    _inherit = "digest.digest"

    def _compute_kpis(self, company, user):
        kpis = super()._compute_kpis(company, user)
        base = self.get_base_url()
        for kpi in kpis:
            icona = kpi.get("kpi_icon") or ""
            if icona.startswith(ODOO_ICONS_CDN_URL):
                kpi["kpi_icon"] = base + icona[len(ODOO_ICONS_CDN_URL):]
        return kpis

    def _compute_tips(self, company, user, tips_count=1, consumed=True):
        return super(DigestDigest, self.with_context(**{CONTESTO: True}))._compute_tips(
            company, user, tips_count=tips_count, consumed=consumed)


class DigestTip(models.Model):
    _inherit = "digest.tip"

    @api.model
    def _search(self, domain, *args, **kwargs):
        if self.env.context.get(CONTESTO):
            domain = Domain.AND([Domain(domain)] + [
                Domain("tip_description", "not ilike", server) for server in SERVER_DI_ODOO])
        return super()._search(domain, *args, **kwargs)
