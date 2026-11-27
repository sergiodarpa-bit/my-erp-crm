from markupsafe import Markup

from odoo import Command, fields, models
from odoo.tools import formatLang


class SaleOrder(models.Model):
    _inherit = "sale.order"

    abbonamento_id = fields.Many2one(
        "my_erp_crm.abbonamento", "Rinnovo dell'abbonamento", index="btree_not_null", copy=False,
        readonly=True)
    abbonamento_attivato_ids = fields.One2many(
        "my_erp_crm.abbonamento", "ordine_origine_id", "Abbonamenti attivati")

    def _my_erp_crm_righe_ricorrenti(self):
        return self.order_line.filtered(
            lambda line: not line.display_type and line.product_id.abbonamento_ricorrenza)

    def action_confirm(self):
        risultato = super().action_confirm()
        for ordine in self.filtered(lambda o: o.state == "sale"):
            abbonamento = ordine.abbonamento_id
            if abbonamento:
                if abbonamento.ordine_in_corso_id == ordine:
                    abbonamento._periodo_pagato(ordine)
            elif ordine._my_erp_crm_righe_ricorrenti() and not ordine.abbonamento_attivato_ids:
                ordine._my_erp_crm_attiva_abbonamenti()
        return risultato

    def _my_erp_crm_attiva_abbonamenti(self):
        """Un abbonamento per ricorrenza (mensile, annuale) con le righe ricorrenti dell'ordine,
        ai prezzi pagati ora. La carta è quella salvata con il pagamento dell'ordine."""
        self.ensure_one()
        token = self.transaction_ids.filtered(
            lambda tx: tx.state in ("done", "authorized") and tx.token_id).token_id[-1:]
        Abbonamento = self.env["my_erp_crm.abbonamento"].sudo()
        abbonamenti = Abbonamento
        for ricorrenza in ("mese", "anno"):
            righe = self._my_erp_crm_righe_ricorrenti().filtered(
                lambda line, r=ricorrenza: line.product_id.abbonamento_ricorrenza == r)
            if not righe:
                continue
            abbonamenti |= Abbonamento.create({
                "partner_id": self.partner_id.id,
                "partner_invoice_id": self.partner_invoice_id.id,
                "company_id": self.company_id.id,
                "currency_id": self.currency_id.id,
                "pricelist_id": self.pricelist_id.id,
                "website_id": self.website_id.id if "website_id" in self._fields else False,
                "user_id": self.user_id.id,
                "team_id": self.team_id.id,
                "ricorrenza": ricorrenza,
                "data_inizio": fields.Date.context_today(self),
                "token_id": token.id,
                "ordine_origine_id": self.id,
                "oss_location_proof_1": self.oss_location_proof_1,
                "oss_location_proof_2": self.oss_location_proof_2,
                "riga_ids": [Command.create({
                    "product_id": riga.product_id.id,
                    "name": riga.name,
                    "quantita": riga.product_uom_qty,
                    "prezzo_unitario": riga.price_unit,
                    "sconto": riga.discount,
                    "prezzo_imponibile": riga.price_subtotal,
                    "prezzo_totale": riga.price_total,
                }) for riga in righe],
            })
        for abbonamento in abbonamenti:
            self.message_post(body=Markup("%s %s") % (
                self.env._("Abbonamento attivato:"), abbonamento._get_html_link()))
        return abbonamenti

    def _my_erp_crm_riepilogo_ricorrenze(self):
        """Per l'avviso sopra il pagamento: un testo per ricorrenza, nella lingua del cliente."""
        self.ensure_one()
        testi = []
        for ricorrenza, ogni in (("mese", self.env._("every month")), ("anno", self.env._("every year"))):
            righe = self._my_erp_crm_righe_ricorrenti().filtered(
                lambda line, r=ricorrenza: line.product_id.abbonamento_ricorrenza == r)
            if righe:
                testi.append(self.env._(
                    "%(products)s: %(amount)s %(recurrence)s",
                    products=", ".join(righe.mapped("product_id.display_name")),
                    amount=formatLang(self.env, sum(righe.mapped("price_total")), currency_obj=self.currency_id),
                    recurrence=ogni))
        return testi
