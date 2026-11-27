from unittest.mock import patch

from odoo import Command


class RispostaVies:
    def __init__(self, dati):
        self.dati = dati

    def raise_for_status(self):
        return None

    def json(self):
        return self.dati


VIES_VALIDA = {"isValid": True, "userError": "VALID", "name": "MUSTER GMBH"}


class NegozioIvaCommon:
    """Imposte e posizioni fiscali come quelle di deploy/configura_azienda.py (società non
    registrata alla VAT, OSS non registrato): servizi generali e servizi digitali senza
    imposta, imprese UE in reverse charge con VIES, privati UE fuori campo e servizi digitali
    bloccati."""

    @classmethod
    def _imposta_iva(cls):
        cls.azienda = cls.env.company
        cls.azienda.vat_check_vies = True
        cls.de = cls.env.ref("base.de")
        europa = cls.env.ref("base.europe")
        Imposta = cls.env["account.tax"]
        cls.generale = Imposta.create({"name": "No UK VAT", "amount": 0, "type_tax_use": "sale"})
        cls.digitale = Imposta.create({"name": "No UK VAT - digital", "amount": 0, "type_tax_use": "sale"})
        Posizione = cls.env["account.fiscal.position"]
        cls.imprese_ue = Posizione.create({
            "name": "EU businesses - reverse charge", "auto_apply": True, "sequence": 1,
            "vat_required": True, "vies_required": True, "country_group_id": europa.id})
        cls.privati_ue = Posizione.create({
            "name": "EU consumers", "auto_apply": True, "sequence": 5, "country_group_id": europa.id,
            "blocked_tax_ids": [Command.set(cls.digitale.ids)]})
        cls.reverse_charge = Imposta.create({
            "name": "Reverse charge (EU)", "amount": 0, "type_tax_use": "sale",
            "original_tax_ids": [Command.set((cls.generale | cls.digitale).ids)],
            "fiscal_position_ids": [Command.set(cls.imprese_ue.ids)]})
        cls.fuori_campo = Imposta.create({
            "name": "Outside scope UK VAT", "amount": 0, "type_tax_use": "sale",
            "original_tax_ids": [Command.set((cls.generale | cls.digitale).ids)],
            "fiscal_position_ids": [Command.set(cls.privati_ue.ids)]})
        Prodotto = cls.env["product.product"]
        cls.servizio = Prodotto.create({
            "name": "Biometric check-up", "type": "service", "list_price": 100,
            "taxes_id": [Command.set(cls.generale.ids)]})
        cls.app = Prodotto.create({
            "name": "App subscription", "type": "service", "list_price": 100,
            "taxes_id": [Command.set(cls.digitale.ids)]})
        cls.privato_de = cls.env["res.partner"].create({
            "name": "Privato DE", "country_id": cls.de.id, "email": "privato@example.com",
            "street": "Hauptstrasse 1", "city": "Berlin", "zip": "10115", "phone": "+49 30 1234567"})

    def _impresa_de(self, **valori):
        with patch("odoo.addons.my_erp_crm_iva.models.res_partner.requests.get",
                   return_value=RispostaVies(VIES_VALIDA)):
            impresa = self.env["res.partner"].create({
                "name": "Muster GmbH", "country_id": self.de.id, "vat": "DE123456788",
                "is_company": True, **valori})
            impresa.flush_recordset()
        return impresa

    def _carrello(self, cliente, prodotto, sito=None):
        return self.env["sale.order"].create({
            "partner_id": cliente.id,
            "website_id": (sito or self.env["website"].search([], limit=1)).id,
            "order_line": [Command.create({"product_id": prodotto.id})],
        })
