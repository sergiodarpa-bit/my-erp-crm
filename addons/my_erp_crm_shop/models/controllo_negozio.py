import os
from urllib.parse import urlparse

from odoo import api, fields, models
from odoo.tools import config, html2plaintext

OK, AVVISO, MANCA = "ok", "avviso", "manca"


class MyErpCrmControlloNegozio(models.TransientModel):
    _name = "my_erp_crm.controllo.negozio"
    _description = "Negozio online: controllo di lancio"

    website_id = fields.Many2one(
        "website", string="Sito", required=True,
        default=lambda self: self.env["website"].search([("company_id", "=", self.env.company.id)], limit=1))
    risultato = fields.Html(compute="_compute_risultato", sanitize=False)
    pronto = fields.Boolean(compute="_compute_risultato")

    def _compute_display_name(self):
        for controllo in self:
            controllo.display_name = "Controllo di lancio"

    @api.depends("website_id")
    def _compute_risultato(self):
        for controllo in self:
            voci = controllo._controlli() if controllo.website_id else []
            controllo.pronto = bool(voci) and all(voce["stato"] != MANCA for voce in voci)
            controllo.risultato = self.env["ir.qweb"]._render(
                "my_erp_crm_shop.controllo_negozio_voci", {"voci": voci})

    def action_ricontrolla(self):
        return {"type": "ir.actions.act_window", "res_model": self._name, "view_mode": "form",
                "target": "current", "context": {"default_website_id": self.website_id.id}}

    # --- i controlli ----------------------------------------------------------------------

    def _controlli(self):
        """Elenco di {stato, titolo, dettaglio}: stato «ok», «avviso» (si può aprire, ma va
        saputo) o «manca» (da sistemare prima di aprire il negozio)."""
        self.ensure_one()
        sito = self.website_id.sudo()
        azienda = sito.company_id
        return [
            self._controllo_prodotti(sito),
            self._controllo_listino(sito),
            self._controllo_pagamenti(sito, azienda),
            self._controllo_posta(),
            self._controllo_accesso(sito),
            self._controllo_termini(sito, azienda),
            self._controllo_iva(sito, azienda),
            self._controllo_fattura_automatica(azienda),
            self._controllo_indirizzo(sito),
            self._controllo_riepilogo(),
        ]

    @staticmethod
    def _voce(stato, titolo, dettaglio):
        return {"stato": stato, "titolo": titolo, "dettaglio": dettaglio}

    @staticmethod
    def _nomi(records, quanti=8):
        nomi = records[:quanti].mapped("display_name")
        if len(records) > quanti:
            nomi.append(f"… e altri {len(records) - quanti}")
        return ", ".join(nomi)

    def _listini_attivi(self):
        return self.env["res.groups"]._is_feature_enabled("product.group_product_pricelist")

    def _listino_del_sito(self, sito):
        """Il listino che il negozio usa per un visitatore: vuoto se i listini sono spenti."""
        Listino = self.env["product.pricelist"].sudo()
        if not self._listini_attivi():
            return Listino
        return Listino.search(Listino._get_website_pricelists_domain(sito), order="sequence, id", limit=1)

    def _prodotti_pubblicati(self, sito):
        return self.env["product.template"].sudo().search([
            ("is_published", "=", True), ("sale_ok", "=", True),
            ("website_id", "in", (False, sito.id)), ("company_id", "in", (False, sito.company_id.id)),
        ])

    def _controllo_prodotti(self, sito):
        titolo = "Prodotti in vendita"
        prodotti = self._prodotti_pubblicati(sito)
        if not prodotti:
            return self._voce(MANCA, titolo, "Nessun prodotto pubblicato sul negozio. Pubblica i "
                              "prodotti da Sito web → E-commerce → Prodotti (pulsante "
                              "«Vai al sito web», poi «Pubblicato»).")
        listino = self._listino_del_sito(sito)
        gratis = prodotti.filtered(lambda p: not (
            listino._get_product_price(p, 1.0) if listino else p.list_price))
        if gratis:
            return self._voce(MANCA, titolo, f"Pubblicati {len(prodotti)}, ma senza prezzo (si "
                              f"venderebbero a zero): {self._nomi(gratis)}. Il prezzo si scrive "
                              f"nel listino del negozio ({listino.display_name or 'prezzo di vendita'}).")
        return self._voce(OK, titolo, f"Pubblicati {len(prodotti)}: {self._nomi(prodotti)}.")

    def _controllo_listino(self, sito):
        titolo = "Prezzi pubblici"
        listino = self._listino_del_sito(sito)
        if not self._listini_attivi():
            return self._voce(MANCA, titolo, f"I listini sono spenti: il negozio mostrerebbe i "
                              f"prezzi di vendita in {sito.company_id.currency_id.name}. Accendili in "
                              f"Vendite → Configurazione → Impostazioni → «Listini prezzi».")
        if not listino:
            return self._voce(MANCA, titolo, f"Nessun listino disponibile sul sito: il negozio "
                              f"mostrerebbe i prezzi interni in {sito.company_id.currency_id.name}. "
                              f"Rendi selezionabile il listino pubblico (Vendite → Prodotti → "
                              f"Listini prezzi).")
        return self._voce(OK, titolo, f"Listino del negozio: {listino.display_name} "
                          f"({listino.currency_id.name}).")

    def _controllo_pagamenti(self, sito, azienda):
        titolo = "Pagamenti online"
        # Come li cerca il negozio: modulo installato, pubblicati (visibili ai clienti).
        metodi = self.env["payment.provider"].sudo().search([
            "|", ("module_state", "=", "installed"), ("module_id", "=", False),
            ("is_published", "=", True),
            ("company_id", "=", azienda.id), ("website_id", "in", (False, sito.id)),
        ])
        if not metodi:
            return self._voce(MANCA, titolo, "Nessun metodo di pagamento pubblicato: configura "
                              "Stripe (chiavi del conto Stripe) e/o il bonifico in Sito web → "
                              "Configurazione → E-commerce → Pagamenti, poi «Pubblicato».")
        bonifico = metodi.filtered(lambda m: m.code == "custom" and m.custom_mode == "wire_transfer")
        if bonifico and not bonifico.partner_bank_id:
            return self._voce(MANCA, titolo, "Il bonifico è attivo ma senza conto bancario: il "
                              "cliente non saprebbe dove pagare. Scegli il conto nel metodo «Bonifico».")
        in_prova = metodi.filtered(lambda m: not m.is_live)
        if in_prova:
            return self._voce(AVVISO, titolo, f"In modalità di prova (nessun incasso vero): "
                              f"{self._nomi(in_prova)}. Accendi «Attivo» per il lancio.")
        return self._voce(OK, titolo, f"Pubblicati: {self._nomi(metodi)}.")

    def _controllo_posta(self):
        titolo = "Email ai clienti"
        if self.env["ir.mail_server"].sudo().search_count([("active", "=", True)]):
            return self._voce(OK, titolo, "Server di posta in uscita configurato: conferme d'ordine "
                              "e fatture partono (prova l'invio, vedi doc/posta-in-uscita.md).")
        return self._voce(MANCA, titolo, "Nessun server di posta in uscita: il cliente non riceve "
                          "conferma d'ordine né fattura. Vedi doc/posta-in-uscita.md.")

    def _controllo_accesso(self, sito):
        titolo = "Acquisto senza account"
        registrazione = self.env["ir.config_parameter"].sudo().get_str("auth_signup.invitation_scope")
        if sito.account_on_checkout == "mandatory" and registrazione != "b2c":
            return self._voce(MANCA, titolo, "Il negozio chiede un account per pagare, ma la "
                              "registrazione libera è chiusa: nessun cliente potrebbe comprare. In "
                              "Sito web → Configurazione → Impostazioni metti «Account clienti» su «Facoltativo».")
        return self._voce(OK, titolo, "I clienti comprano anche senza account (gestionale chiuso "
                          "alla registrazione libera).")

    def _controllo_termini(self, sito, azienda):
        titolo = "Termini e condizioni"
        parametri = self.env["ir.config_parameter"].sudo()
        pagina = (parametri.get_bool("account.use_invoice_terms") and azienda.terms_type == "html"
                  and html2plaintext(azienda.invoice_terms_html or "").strip())
        casella = sito.with_context(website_id=sito.id).viewref(
            "website_sale.accept_terms_and_conditions", raise_if_not_found=False)
        if not pagina:
            return self._voce(MANCA, titolo, "Manca la pagina /terms con le condizioni di vendita "
                              "(recesso, rimborsi, foro): Contabilità → Configurazione → "
                              "Impostazioni → «Condizioni Generali», scegli «Come pagina web».")
        if self._termini_di_esempio(azienda, pagina):
            return self._voce(MANCA, titolo, "La pagina /terms contiene ancora il testo di esempio "
                              "(«STANDARD TERMS AND CONDITIONS OF SALE»): vanno scritte le condizioni "
                              "vere in Contabilità → Configurazione → Impostazioni → «Condizioni "
                              "Generali».")
        if not casella.active:
            return self._voce(AVVISO, titolo, "La pagina /terms c'è, ma il cliente non deve "
                              "accettarla: nel negozio, alla pagina di pagamento, «Modifica» → "
                              "accendi «Accetta termini e condizioni».")
        return self._voce(OK, titolo, "Pagina /terms pubblicata e accettata al pagamento.")

    def _termini_di_esempio(self, azienda, testo):
        """Scegliendo «Come pagina web» la pagina si riempie col modello di esempio del modulo
        account: non sono condizioni dell'azienda."""
        def piano(html):
            return " ".join(html2plaintext(html or "").split())

        testo = " ".join(testo.split())
        for codice, _nome in self.env["res.lang"].get_installed():
            esempio = self.env["ir.qweb"].with_context(lang=codice)._render(
                "account.account_default_terms_and_conditions",
                {"company_name": azienda.name, "company_country": azienda.country_id.name},
                raise_if_not_found=False)
            inizio = piano(esempio)[:150]
            if inizio and inizio in testo:
                return True
        return False

    def _controllo_iva(self, sito, azienda):
        titolo = "IVA nel negozio"
        posizioni = self.env["account.fiscal.position"].sudo().search([
            ("company_id", "=", azienda.id), ("blocked_tax_ids", "!=", False)])
        prodotti = self._prodotti_pubblicati(sito)
        avvisi = []
        for posizione in posizioni:
            esclusi = prodotti.filtered(lambda p, pos=posizione: p.taxes_id & pos.blocked_tax_ids)
            if esclusi:
                avvisi.append(f"«{posizione.name}» non possono comprare {self._nomi(esclusi)} "
                              f"(il pagamento non si apre)")
        oss = self.env["account.fiscal.position"].sudo().search_count([
            ("company_id", "=", azienda.id), ("oss_location_proofs_required", "=", True)])
        if oss and not any(os.path.exists(config[db] or "") for db in ("geoip_country_db", "geoip_city_db")):
            avvisi.append("l'OSS chiede il paese della connessione, ma sul server manca il database "
                          "GeoIP: le vendite ai privati UE si fermano prima del pagamento")
        if avvisi:
            return self._voce(AVVISO, titolo, "Clienti " + "; ".join(avvisi) + ". Vedi "
                              "doc/commercio-elettronico.md.")
        return self._voce(OK, titolo, "Ogni prodotto pubblicato si può fatturare a ogni cliente; il "
                          "controllo si ripete su ogni carrello prima del pagamento.")

    def _controllo_fattura_automatica(self, azienda):
        titolo = "Fattura al pagamento"
        if azienda.sale_automatic_invoice:
            return self._voce(OK, titolo, "Pagamento ricevuto: fattura emessa e inviata da sola.")
        return self._voce(AVVISO, titolo, "Le fatture degli ordini pagati online vanno emesse a "
                          "mano (Vendite → Configurazione → Impostazioni → «Fattura automatica»).")

    def _controllo_indirizzo(self, sito):
        titolo = "Indirizzo del negozio"
        indirizzo = urlparse(sito.domain or "")
        if indirizzo.scheme == "https" and indirizzo.hostname:
            return self._voce(OK, titolo, f"{sito.domain}/shop")
        return self._voce(AVVISO, titolo, "Il sito non ha un dominio https: i link nelle email "
                          "(ordine, pagamento, fattura) userebbero l'indirizzo del gestionale. "
                          "Impostalo in Sito web → Configurazione → Impostazioni → «Dominio».")

    def _controllo_riepilogo(self):
        titolo = "Riepilogo via email"
        riepilogo = self.env.ref("digest.digest_digest_default", raise_if_not_found=False)
        if riepilogo and riepilogo.sudo().state == "activated" and riepilogo.sudo().kpi_website_sale_total:
            return self._voce(OK, titolo, "Le vendite online sono nel riepilogo periodico via email.")
        return self._voce(AVVISO, titolo, "Le vendite online non sono nel riepilogo periodico "
                          "(Impostazioni → «E-mail di riepilogo» → «Vendite e-commerce»).")
