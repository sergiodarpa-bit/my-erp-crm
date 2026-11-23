from collections import Counter

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    firma_count = fields.Integer(
        string="Firme",
        compute="_compute_firma_count",
        groups="sign_oca.sign_oca_group_user",
    )

    def _richieste_firma(self):
        """Richieste di Firma collegate a questi preventivi (campo «Record» della richiesta)."""
        riferimenti = [f"{self._name},{ordine_id}" for ordine_id in self.ids]
        if not riferimenti:
            return self.env["sign.oca.request"]
        return self.env["sign.oca.request"].search([("record_ref", "in", riferimenti)])

    def _compute_firma_count(self):
        conteggio = Counter(richiesta.record_ref.id for richiesta in self._richieste_firma())
        for ordine in self:
            ordine.firma_count = conteggio.get(ordine.id, 0)

    def action_invia_alla_firma(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Invia alla firma"),
            "res_model": "my_erp_crm.firma.preventivo",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {
                "default_order_id": self.id,
                "default_partner_id": self.partner_id.id,
            },
        }

    def action_view_firme(self):
        self.ensure_one()
        richieste = self._richieste_firma()
        azione = self.env["ir.actions.act_window"]._for_xml_id("sign_oca.sign_oca_request_act_window")
        azione["domain"] = [("id", "in", richieste.ids)]
        azione["context"] = {"create": False}
        if len(richieste) == 1:
            azione.update(view_mode="form", views=[(False, "form")], res_id=richieste.id)
        return azione
