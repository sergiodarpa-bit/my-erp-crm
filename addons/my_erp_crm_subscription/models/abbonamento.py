import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date, formatLang

_logger = logging.getLogger(__name__)

# Dopo un addebito non riuscito si riprova a distanza di qualche giorno; al terzo tentativo
# fallito l'abbonamento si sospende e decide una persona.
GIORNI_TRA_TENTATIVI = 3
TENTATIVI_MASSIMI = 3

PERIODO = {"mese": relativedelta(months=1), "anno": relativedelta(years=1)}


class MyErpCrmAbbonamento(models.Model):
    _name = "my_erp_crm.abbonamento"
    _description = "Abbonamento"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "id desc"

    name = fields.Char("Numero", readonly=True, copy=False, default="/")
    partner_id = fields.Many2one("res.partner", "Cliente", required=True, index=True, tracking=True)
    partner_invoice_id = fields.Many2one("res.partner", "Indirizzo di fatturazione")
    company_id = fields.Many2one("res.company", "Azienda", required=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", "Valuta", required=True)
    pricelist_id = fields.Many2one("product.pricelist", "Listino")
    website_id = fields.Many2one("website", "Sito")
    user_id = fields.Many2one("res.users", "Venditore", tracking=True)
    team_id = fields.Many2one("crm.team", "Team di vendita")

    ricorrenza = fields.Selection(
        [("mese", "Ogni mese"), ("anno", "Ogni anno")], "Ricorrenza", required=True, default="mese")
    stato = fields.Selection([
        ("attivo", "Attivo"),
        ("insoluto", "Pagamento non riuscito"),
        ("disdetto", "Disdetto (fino a fine periodo)"),
        ("sospeso", "Sospeso"),
        ("chiuso", "Chiuso"),
    ], "Stato", required=True, default="attivo", index=True, tracking=True, copy=False)
    riga_ids = fields.One2many("my_erp_crm.abbonamento.riga", "abbonamento_id", "Servizi", copy=True)

    data_inizio = fields.Date("Inizio", required=True, default=fields.Date.context_today, tracking=True)
    periodi_pagati = fields.Integer("Periodi pagati", default=1, copy=False,
                                    help="Il primo è quello dell'ordine che ha attivato l'abbonamento.")
    prossimo_addebito = fields.Date(
        "Prossimo addebito", compute="_compute_prossimo_addebito", store=True, index=True,
        help="Fine del periodo pagato: il giorno del rinnovo, o della chiusura se disdetto.")
    prossimo_tentativo = fields.Date("Nuovo tentativo", copy=False,
                                     help="Dopo un addebito non riuscito: il giorno in cui si riprova.")
    tentativi = fields.Integer("Tentativi non riusciti", copy=False)
    data_fine = fields.Date("Fine", copy=False, tracking=True)

    token_id = fields.Many2one(
        "payment.token", "Carta per i rinnovi", tracking=True, copy=False,
        domain="[('partner_id', 'child_of', partner_id)]",
        help="Il metodo di pagamento salvato in Stripe al primo acquisto (o all'ultimo pagamento "
             "fatto dal cliente). Senza, il rinnovo si manda al cliente da pagare.")
    ordine_origine_id = fields.Many2one("sale.order", "Ordine di attivazione", copy=False, index=True)
    ordine_ids = fields.One2many("sale.order", "abbonamento_id", "Ordini di rinnovo")
    ordine_in_corso_id = fields.Many2one(
        "sale.order", "Rinnovo in attesa", copy=False,
        help="L'ordine del periodo successivo, finché non è pagato.")
    oss_location_proof_1 = fields.Char("Prova di localizzazione 1", copy=False)
    oss_location_proof_2 = fields.Char("Prova di localizzazione 2", copy=False)

    importo = fields.Monetary("Importo per periodo", compute="_compute_importo", store=True,
                              help="Totale per periodo, imposte comprese, ai prezzi bloccati all'attivazione.")
    importo_mensile = fields.Monetary(
        "Ricavo mensile (MRR)", compute="_compute_importo", store=True,
        help="Imponibile riportato al mese: un abbonamento annuale conta un dodicesimo. Solo per "
             "gli abbonamenti che si rinnovano (attivi o con pagamento in sospeso).")
    ordini_count = fields.Integer("Ordini", compute="_compute_ordini_count")
    servizi = fields.Char("Elenco dei servizi", compute="_compute_servizi")

    # --- calcoli ---------------------------------------------------------------------------

    @api.depends("data_inizio", "ricorrenza", "periodi_pagati")
    def _compute_prossimo_addebito(self):
        # Sempre dalla data di inizio: il 31 gennaio porta al 28 febbraio e poi al 31 marzo,
        # senza scivolare di mese in mese.
        for abbonamento in self:
            passo = PERIODO.get(abbonamento.ricorrenza)
            abbonamento.prossimo_addebito = abbonamento.data_inizio and passo and (
                abbonamento.data_inizio + passo * abbonamento.periodi_pagati)

    @api.depends("riga_ids.prezzo_totale", "riga_ids.prezzo_imponibile", "ricorrenza", "stato")
    def _compute_importo(self):
        for abbonamento in self:
            abbonamento.importo = sum(abbonamento.riga_ids.mapped("prezzo_totale"))
            imponibile = sum(abbonamento.riga_ids.mapped("prezzo_imponibile"))
            if abbonamento.stato not in ("attivo", "insoluto"):
                imponibile = 0.0
            abbonamento.importo_mensile = imponibile / 12 if abbonamento.ricorrenza == "anno" else imponibile

    @api.depends("riga_ids.product_id")
    def _compute_servizi(self):
        for abbonamento in self:
            abbonamento.servizi = ", ".join(abbonamento.riga_ids.product_id.mapped("display_name"))

    def _compute_ordini_count(self):
        for abbonamento in self:
            abbonamento.ordini_count = len(abbonamento.ordine_ids)

    def _compute_access_url(self):
        super()._compute_access_url()
        for abbonamento in self:
            abbonamento.access_url = f"/my/subscriptions/{abbonamento.id}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("my_erp_crm.abbonamento") or "/"
        return super().create(vals_list)

    def _periodo(self, inizio):
        """(inizio, fine) del periodo che comincia il giorno dato."""
        self.ensure_one()
        return inizio, inizio + PERIODO[self.ricorrenza] - timedelta(days=1)

    # --- testi per il cliente (inglese nel codice, tradotti in i18n) -----------------------

    def _testo_ricorrenza(self):
        self.ensure_one()
        return {"mese": self.env._("every month"), "anno": self.env._("every year")}[self.ricorrenza]

    def _testo_stato(self):
        self.ensure_one()
        return {
            "attivo": self.env._("Active"),
            "insoluto": self.env._("Payment failed"),
            "disdetto": self.env._("Cancelled, active until the end of the period"),
            "sospeso": self.env._("Suspended"),
            "chiuso": self.env._("Ended"),
        }[self.stato]

    # --- rinnovo ---------------------------------------------------------------------------

    @api.model
    def _cron_rinnova(self):
        """Ogni giorno: rinnova gli abbonamenti arrivati a scadenza, riprova gli addebiti non
        riusciti, chiude quelli disdetti a fine periodo."""
        oggi = fields.Date.context_today(self)
        da_fare = self.search([
            "|",
            "&", ("stato", "in", ("attivo", "disdetto")), ("prossimo_addebito", "<=", oggi),
            "&", ("stato", "=", "insoluto"), ("prossimo_tentativo", "<=", oggi),
        ])
        IrCron = self.env["ir.cron"]
        IrCron._commit_progress(remaining=len(da_fare))
        for abbonamento in da_fare:
            tx = None
            try:
                with self.env.cr.savepoint():
                    tx = abbonamento._prepara_rinnovo()
            except (UserError, ValidationError) as errore:
                abbonamento.message_post(body=self.env._("Rinnovo non eseguito: %s", errore.args[0]))
            if tx:
                # La transazione deve essere nel database prima di chiamare Stripe: se dopo
                # l'addebito qualcosa annullasse il lavoro, il rinnovo successivo addebiterebbe
                # di nuovo senza sapere del primo.
                IrCron._commit_progress()
                tx._charge_with_token()
            if not IrCron._commit_progress(processed=1):
                break

    def _rinnova(self):
        """Un rinnovo subito (dal gestionale): prepara e addebita."""
        self.ensure_one()
        tx = self._prepara_rinnovo()
        if tx:
            tx._charge_with_token()

    def _prepara_rinnovo(self):
        """Un passo del rinnovo, fino alla transazione da addebitare (se c'è una carta).
        L'esito dell'addebito arriva dopo, dall'elaborazione del pagamento: ordine confermato
        (_periodo_pagato) o pagamento fallito (_addebito_fallito)."""
        self.ensure_one()
        if self.stato == "disdetto":
            self._chiudi()
            return None
        if self.stato not in ("attivo", "insoluto"):
            return None
        ordine = self.ordine_in_corso_id
        if not ordine or ordine.state == "cancel":
            ordine = self._crea_ordine_rinnovo()
            self.ordine_in_corso_id = ordine
        if ordine.state == "sale":  # pagato in altro modo (bonifico, portale)
            self._periodo_pagato(ordine)
            return None
        if ordine.transaction_ids.filtered(lambda tx: tx.state in ("pending", "authorized")
                                           or (tx.state == "done" and not tx.is_post_processed)):
            return None  # l'esito di un addebito è ancora in arrivo
        if not (self.token_id and self.token_id.active):
            self._chiedi_pagamento(ordine)
            return None
        # Una transazione rimasta in bozza (lavoro interrotto dopo il salvataggio) si riprova
        # identica: stesso riferimento, stessa chiave di idempotenza, e Stripe non addebita due
        # volte la stessa richiesta.
        bozza = ordine.transaction_ids.filtered(
            lambda tx: tx.state == "draft" and tx.operation == "offline" and tx.token_id == self.token_id)
        return bozza[-1:] or self._crea_transazione(ordine)

    def _crea_ordine_rinnovo(self):
        self.ensure_one()
        inizio, fine = self._periodo(self.prossimo_addebito)
        env_cliente = self.with_context(lang=self.partner_id.lang).env
        periodo = env_cliente._("%(start)s to %(end)s",
                                start=format_date(env_cliente, inizio), end=format_date(env_cliente, fine))
        valori = {
            "partner_id": self.partner_id.id,
            "partner_invoice_id": (self.partner_invoice_id or self.partner_id).id,
            "company_id": self.company_id.id,
            "pricelist_id": self.pricelist_id.id,
            "user_id": self.user_id.id,
            "team_id": self.team_id.id,
            "website_id": self.website_id.id,
            "origin": self.name,
            "abbonamento_id": self.id,
            "prepayment_percent": 1.0,
            "oss_location_proof_1": self.oss_location_proof_1,
            "oss_location_proof_2": self.oss_location_proof_2,
            "order_line": [Command.create({
                "product_id": riga.product_id.id,
                "name": f"{riga.name}\n{periodo}",
                "product_uom_qty": riga.quantita,
                "price_unit": riga.prezzo_unitario,
                "discount": riga.sconto,
            }) for riga in self.riga_ids],
        }
        if "cart_recovery_email_sent" in self.env["sale.order"]._fields:
            valori["cart_recovery_email_sent"] = True  # non è un carrello abbandonato
        Ordine = self.env["sale.order"].sudo().with_company(self.company_id)
        return Ordine.with_context(lang=self.partner_id.lang).create(valori)

    def _crea_transazione(self, ordine):
        self.ensure_one()
        token = self.token_id
        Transazione = self.env["payment.transaction"].sudo()
        return Transazione.create({
            "provider_id": token.provider_id.id,
            "payment_method_id": token.payment_method_id.id,
            "reference": Transazione._compute_reference(
                token.provider_id.code, sale_order_ids=[Command.set(ordine.ids)]),
            "amount": ordine.amount_total,
            "currency_id": ordine.currency_id.id,
            "partner_id": ordine.partner_invoice_id.id,
            "token_id": token.id,
            "operation": "offline",
            "sale_order_ids": [Command.set(ordine.ids)],
        })

    def _periodo_pagato(self, ordine):
        """Il rinnovo è pagato: il periodo successivo è coperto."""
        self.ensure_one()
        valori = {"periodi_pagati": self.periodi_pagati + 1, "tentativi": 0, "prossimo_tentativo": False}
        if self.ordine_in_corso_id == ordine:
            valori["ordine_in_corso_id"] = False
        if self.stato in ("insoluto", "sospeso"):
            valori["stato"] = "attivo"
            # Il pagamento è arrivato: l'attività aperta per la sospensione non serve più.
            self.activity_ids.filtered(
                lambda attivita: (attivita.summary or "").startswith("Abbonamento sospeso"),
            ).action_feedback(feedback=self.env._("Rinnovo pagato: %s", ordine.name))
        # Pagato dal portale con una carta nuova: i rinnovi successivi usano quella.
        token = ordine.transaction_ids.filtered(lambda tx: tx.state == "done" and tx.token_id).token_id[-1:]
        if token and token != self.token_id:
            valori["token_id"] = token.id
        self.write(valori)

    def _addebito_fallito(self, tx):
        self.ensure_one()
        tentativi = self.tentativi + 1
        ordine = self.ordine_in_corso_id
        if ordine.state == "draft":
            ordine.state = "sent"  # in attesa di pagamento: fra gli ordini online da gestire
        if tentativi >= TENTATIVI_MASSIMI:
            self.write({"tentativi": tentativi, "stato": "sospeso", "prossimo_tentativo": False})
            self._avvisa_responsabile(tx)
        else:
            self.write({"tentativi": tentativi, "stato": "insoluto",
                        "prossimo_tentativo": fields.Date.context_today(self) + timedelta(days=GIORNI_TRA_TENTATIVI)})
        self._scrivi_al_cliente("pagamento_fallito")

    def _chiedi_pagamento(self, ordine):
        """Senza carta salvata il rinnovo si manda al cliente da pagare."""
        self.ensure_one()
        if ordine.state == "draft":
            ordine.state = "sent"
        tentativi = self.tentativi + 1
        if tentativi >= TENTATIVI_MASSIMI:
            self.write({"tentativi": tentativi, "stato": "sospeso", "prossimo_tentativo": False})
            self._avvisa_responsabile(None)
        else:
            self.write({"tentativi": tentativi, "stato": "insoluto",
                        "prossimo_tentativo": fields.Date.context_today(self) + timedelta(days=GIORNI_TRA_TENTATIVI)})
        self._scrivi_al_cliente("da_pagare")

    def _chiudi(self):
        self.ensure_one()
        if self.ordine_in_corso_id and self.ordine_in_corso_id.state in ("draft", "sent"):
            self.ordine_in_corso_id._action_cancel()
        self.write({"stato": "chiuso", "data_fine": self.data_fine or fields.Date.context_today(self),
                    "ordine_in_corso_id": False, "prossimo_tentativo": False})

    def _avvisa_responsabile(self, tx):
        self.ensure_one()
        responsabile = self.user_id or self.team_id.user_id or self.env.ref("base.user_admin")
        motivo = tx.state_message if tx else self.env._("nessuna carta salvata")
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            summary=self.env._("Abbonamento sospeso: pagamento non riuscito"),
            note=Markup("<p>%s</p>") % self.env._(
                "Dopo %(n)s tentativi il rinnovo non è stato pagato (%(motivo)s). Contatta il "
                "cliente: può pagare l'ordine %(ordine)s dal portale o cambiare carta; poi "
                "«Riprova l'addebito» o chiudi l'abbonamento.",
                n=TENTATIVI_MASSIMI, motivo=motivo or "-", ordine=self.ordine_in_corso_id.name or "-"),
            user_id=responsabile.id,
        )

    def _scrivi_al_cliente(self, caso):
        """Email al cliente, nella sua lingua, con il link all'abbonamento nel portale."""
        self.ensure_one()
        abbonamento = self.with_context(lang=self.partner_id.lang)
        _ = abbonamento.env._
        ordine = self.ordine_in_corso_id
        link_ordine = ordine and ordine.get_base_url() + ordine.get_portal_url()
        link_carta = self.get_base_url() + "/my/payment_method"
        testi = {
            "pagamento_fallito": (
                _("Payment for your subscription %s did not go through", self.name),
                [_("We could not charge your card for the renewal of your subscription %(name)s "
                   "(%(amount)s %(recurrence)s).", name=self.name,
                   amount=abbonamento._importo_formattato(), recurrence=abbonamento._testo_ricorrenza()),
                 _("You can pay the renewal online, also with another card, here: %s", link_ordine),
                 _("To change the card used for the next renewals: %s", link_carta)]),
            "da_pagare": (
                _("Your subscription %s is due for renewal", self.name),
                [_("The renewal of your subscription %(name)s (%(amount)s %(recurrence)s) is ready "
                   "to be paid.", name=self.name, amount=abbonamento._importo_formattato(),
                   recurrence=abbonamento._testo_ricorrenza()),
                 _("You can pay it online here: %s", link_ordine)]),
            "disdetto": (
                _("Your subscription %s has been cancelled", self.name),
                [_("Your subscription %(name)s has been cancelled. It stays active until %(date)s "
                   "and will not be renewed.", name=self.name,
                   date=format_date(abbonamento.env, self.data_fine))]),
        }
        oggetto, paragrafi = testi[caso]
        corpo = Markup("").join(Markup("<p>%s</p>") % paragrafo for paragrafo in paragrafi)
        abbonamento.message_post(
            subject=oggetto, body=corpo, partner_ids=self.partner_id.ids,
            subtype_xmlid="mail.mt_comment", message_type="comment")

    def _importo_formattato(self):
        self.ensure_one()
        return formatLang(self.env, self.importo, currency_obj=self.currency_id)

    # --- azioni (gestionale e portale) ------------------------------------------------------

    def action_disdici(self):
        """Il cliente non vuole il rinnovo: resta attivo fino alla fine del periodo pagato. Se il
        rinnovo era già scaduto e non pagato, si chiude subito."""
        for abbonamento in self.filtered(lambda a: a.stato in ("attivo", "insoluto", "sospeso")):
            if abbonamento.stato == "attivo":
                abbonamento.write({"stato": "disdetto", "data_fine": abbonamento.prossimo_addebito})
            else:
                abbonamento.data_fine = fields.Date.context_today(abbonamento)
                abbonamento._chiudi()
            abbonamento._scrivi_al_cliente("disdetto")
        return True

    def action_riattiva(self):
        for abbonamento in self.filtered(lambda a: a.stato == "disdetto"):
            abbonamento.write({"stato": "attivo", "data_fine": False})
        return True

    def action_chiudi(self):
        for abbonamento in self.filtered(lambda a: a.stato != "chiuso"):
            abbonamento._chiudi()
        return True

    def action_riprova(self):
        """Riprova subito l'addebito del rinnovo (per esempio dopo che il cliente ha cambiato carta)."""
        for abbonamento in self.filtered(lambda a: a.stato in ("insoluto", "sospeso")):
            abbonamento.stato = "insoluto"
            abbonamento._rinnova()
        return True

    def action_vedi_ordini(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Ordini dell'abbonamento"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": ["|", ("abbonamento_id", "=", self.id), ("id", "=", self.ordine_origine_id.id)],
        }


class MyErpCrmAbbonamentoRiga(models.Model):
    _name = "my_erp_crm.abbonamento.riga"
    _description = "Servizio di un abbonamento"
    _order = "abbonamento_id, id"

    abbonamento_id = fields.Many2one("my_erp_crm.abbonamento", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one(related="abbonamento_id.currency_id")
    product_id = fields.Many2one("product.product", "Servizio", required=True)
    name = fields.Text("Descrizione", required=True)
    quantita = fields.Float("Quantità", default=1.0, digits="Product Unit")
    prezzo_unitario = fields.Float("Prezzo unitario", digits="Product Price")
    sconto = fields.Float("Sconto (%)", digits="Discount")
    prezzo_imponibile = fields.Monetary("Imponibile")
    prezzo_totale = fields.Monetary("Totale", help="Imposte comprese, come all'attivazione.")
