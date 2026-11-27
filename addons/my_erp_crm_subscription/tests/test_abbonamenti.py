from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.account_payment.tests.common import AccountPaymentCommon
from odoo.addons.my_erp_crm_shop.tests.common import NegozioIvaCommon
from odoo.addons.my_erp_crm_subscription import prepara_abbonamenti
from odoo.addons.sale.tests.common import SaleCommon


@tagged("post_install", "-at_install")
class TestAbbonamenti(NegozioIvaCommon, AccountPaymentCommon, SaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._imposta_iva()
        cls.env.company.sale_automatic_invoice = True
        cls.servizio.write({"abbonamento_ricorrenza": "mese", "name": "Gemello Digitale · mensile"})
        cls.oggi = fields.Date.context_today(cls.env["my_erp_crm.abbonamento"])

    @contextmanager
    def _stripe_finto(self):
        """L'addebito sulla carta: la richiesta a Stripe non parte, l'esito lo decide il test."""
        with patch.object(type(self.env["payment.transaction"]), "_send_payment_request", lambda tx: None):
            yield

    def _rinnova_oggi(self):
        with self._stripe_finto(), mute_logger("odoo.addons.base.models.ir_cron"):
            self._run_cron_job("my_erp_crm_subscription.cron_rinnovo_abbonamenti")

    def _esito(self, abbonamento, stato):
        tx = abbonamento.ordine_in_corso_id.transaction_ids.filtered(lambda t: t.state == "draft")[-1:]
        self.assertTrue(tx, "il rinnovo ha preparato l'addebito sulla carta")
        self.assertEqual(tx.operation, "offline")
        self.assertEqual(tx.token_id, abbonamento.token_id)
        self._update_transaction(tx, state=stato)
        with mute_logger("odoo.addons.sale.models.payment_transaction"):
            self._run_post_processing()
        return tx

    def _primo_acquisto(self, prezzo=None):
        ordine = self._create_so(partner_id=self.privato_de.id, order_line=[Command.create({
            "product_id": self.servizio.id, **({"price_unit": prezzo} if prezzo else {})})])
        carta = self._create_token(partner_id=self.privato_de.id)
        self.amount = ordine.amount_total
        self.currency = ordine.currency_id
        self._create_transaction(flow="direct", sale_order_ids=[ordine.id], state="done",
                                 token_id=carta.id, partner_id=self.privato_de.id)
        with mute_logger("odoo.addons.sale.models.payment_transaction"):
            self._run_post_processing()
        return ordine, carta

    # --- checkout ---------------------------------------------------------------------------

    def test_carta_salvata_obbligatoria(self):
        Fornitore = self.env["payment.provider"]
        con_abbonamento = self._create_so(partner_id=self.privato_de.id,
                                          order_line=[Command.create({"product_id": self.servizio.id})])
        senza = self._create_so(partner_id=self.privato_de.id,
                                order_line=[Command.create({"product_id": self.app.id})])
        self.assertTrue(Fornitore._is_tokenization_required(sale_order_id=con_abbonamento.id))
        self.assertFalse(Fornitore._is_tokenization_required(sale_order_id=senza.id))
        testi = con_abbonamento._my_erp_crm_riepilogo_ricorrenze()
        self.assertEqual(len(testi), 1)
        self.assertIn("Gemello Digitale · mensile", testi[0])
        self.assertIn("every month", testi[0])

    # --- ciclo di vita ----------------------------------------------------------------------

    def test_primo_acquisto_attiva_l_abbonamento(self):
        ordine, carta = self._primo_acquisto(prezzo=37.5)
        self.assertEqual(ordine.state, "sale")
        abbonamento = ordine.abbonamento_attivato_ids
        self.assertEqual(len(abbonamento), 1)
        self.assertEqual(abbonamento.stato, "attivo")
        self.assertEqual(abbonamento.token_id, carta)
        self.assertEqual(abbonamento.prossimo_addebito, self.oggi + relativedelta(months=1))
        self.assertEqual(abbonamento.riga_ids.prezzo_unitario, 37.5)
        self.assertEqual(abbonamento.importo_mensile, 37.5)
        self.assertTrue(abbonamento.name.startswith("ABB/"))

    def test_rinnovo_addebitato_e_fatturato(self):
        ordine, _carta = self._primo_acquisto(prezzo=37.5)
        abbonamento = ordine.abbonamento_attivato_ids
        abbonamento.data_inizio = self.oggi - relativedelta(months=1)  # il periodo pagato finisce oggi
        self._rinnova_oggi()
        rinnovo = abbonamento.ordine_in_corso_id
        self.assertTrue(rinnovo)
        self.assertEqual(rinnovo.abbonamento_id, abbonamento)
        self.assertEqual(rinnovo.order_line.price_unit, 37.5, "prezzo bloccato all'attivazione")
        self.assertIn(" to ", rinnovo.order_line.name, "la riga dice il periodo")

        self._esito(abbonamento, "done")
        self.assertEqual(rinnovo.state, "sale")
        self.assertEqual(rinnovo.invoice_ids.state, "posted", "fattura automatica del rinnovo")
        self.assertEqual(abbonamento.periodi_pagati, 2)
        self.assertFalse(abbonamento.ordine_in_corso_id)
        self.assertEqual(abbonamento.prossimo_addebito, self.oggi + relativedelta(months=1))

        # Il giorno dopo non si rinnova di nuovo.
        self._rinnova_oggi()
        self.assertFalse(abbonamento.ordine_in_corso_id)

    def test_addebito_non_riuscito_tre_volte(self):
        ordine, _carta = self._primo_acquisto()
        abbonamento = ordine.abbonamento_attivato_ids
        abbonamento.data_inizio = self.oggi - relativedelta(months=1)

        self._rinnova_oggi()
        self._esito(abbonamento, "error")
        self.assertEqual(abbonamento.stato, "insoluto")
        self.assertEqual(abbonamento.tentativi, 1)
        self.assertEqual(abbonamento.prossimo_tentativo, self.oggi + timedelta(days=3))
        self.assertEqual(abbonamento.ordine_in_corso_id.state, "sent", "fra gli ordini online da gestire")
        avviso = abbonamento.message_ids.filtered(lambda m: m.subject and "did not go through" in m.subject)
        self.assertTrue(avviso, "il cliente riceve l'email")
        self.assertIn(self.privato_de, avviso.partner_ids)
        self.assertIn("/my/orders/", avviso.body, "con il link per pagare")

        for tentativo in (2, 3):
            abbonamento.prossimo_tentativo = self.oggi
            self._rinnova_oggi()
            self._esito(abbonamento, "error")
            self.assertEqual(abbonamento.tentativi, tentativo)
        self.assertEqual(abbonamento.stato, "sospeso")
        self.assertTrue(abbonamento.activity_ids, "decide una persona")

        # Il cliente paga il rinnovo dal portale con un'altra carta: torna attivo con quella.
        nuova = self._create_token(partner_id=self.privato_de.id, payment_details="9999")
        rinnovo = abbonamento.ordine_in_corso_id
        self._create_transaction(flow="direct", sale_order_ids=[rinnovo.id], state="done",
                                 token_id=nuova.id, partner_id=self.privato_de.id,
                                 reference="rinnovo-dal-portale", amount=rinnovo.amount_total)
        with mute_logger("odoo.addons.sale.models.payment_transaction"):
            self._run_post_processing()
        self.assertEqual(abbonamento.stato, "attivo")
        self.assertEqual(abbonamento.token_id, nuova)
        self.assertEqual(abbonamento.tentativi, 0)
        self.assertFalse(abbonamento.activity_ids, "l'attività della sospensione si chiude")

    def test_disdetta_a_fine_periodo(self):
        ordine, _carta = self._primo_acquisto()
        abbonamento = ordine.abbonamento_attivato_ids
        abbonamento.action_disdici()
        self.assertEqual(abbonamento.stato, "disdetto")
        self.assertEqual(abbonamento.data_fine, abbonamento.prossimo_addebito)
        self.assertEqual(abbonamento.importo_mensile, 0, "fuori dal ricavo ricorrente")
        self.assertTrue(abbonamento.message_ids.filtered(lambda m: m.subject and "cancelled" in m.subject))

        abbonamento.action_riattiva()
        self.assertEqual(abbonamento.stato, "attivo")
        abbonamento.action_disdici()

        abbonamento.data_inizio = self.oggi - relativedelta(months=1)  # fine del periodo pagato
        self._rinnova_oggi()
        self.assertEqual(abbonamento.stato, "chiuso")
        self.assertFalse(abbonamento.ordine_ids, "nessun addebito dopo la disdetta")

    def test_senza_carta_il_rinnovo_si_manda_da_pagare(self):
        ordine, carta = self._primo_acquisto()
        abbonamento = ordine.abbonamento_attivato_ids
        carta.active = False  # il cliente ha tolto la carta
        abbonamento.data_inizio = self.oggi - relativedelta(months=1)
        self._rinnova_oggi()
        self.assertEqual(abbonamento.stato, "insoluto")
        self.assertEqual(abbonamento.ordine_in_corso_id.state, "sent")
        self.assertFalse(abbonamento.ordine_in_corso_id.transaction_ids)
        self.assertTrue(abbonamento.message_ids.filtered(lambda m: m.subject and "due for renewal" in m.subject))

    # --- installazione e controllo di lancio -----------------------------------------------

    def test_prodotti_riconosciuti_all_installazione(self):
        Prodotto = self.env["product.template"]
        mensile = Prodotto.create({"name": "Agente AI: Sonno · mensile", "type": "service"})
        annuale = Prodotto.create({"name": "Agente AI: Sonno · annuale", "type": "service"})
        consulenza = Prodotto.create({"name": "Consulenza annuale di gruppo", "type": "service"})
        prepara_abbonamenti(self.env)
        self.assertEqual(mensile.abbonamento_ricorrenza, "mese")
        self.assertEqual(annuale.abbonamento_ricorrenza, "anno")
        self.assertFalse(consulenza.abbonamento_ricorrenza, "«annuale» non è la fine del nome")

    def test_controllo_di_lancio(self):
        # Le classi di test di Odoo lavorano in un'azienda nuova: un sito suo.
        sito = self.env["website"].create({"name": "Negozio di prova", "company_id": self.env.company.id})
        self.env["product.template"].search([("is_published", "=", True)]).is_published = False
        self.servizio.product_tmpl_id.is_published = True
        self.env["payment.provider"].search([]).write({"is_published": False})

        def voce():
            controllo = self.env["my_erp_crm.controllo.negozio"].create({"website_id": sito.id})
            return {v["titolo"]: v for v in controllo._controlli()}["Abbonamenti"]

        self.assertEqual(voce()["stato"], "manca", "nessun metodo pubblicato salva la carta")
        self.provider.write({"is_published": True, "allow_tokenization": True,
                             "company_id": self.env.company.id, "website_id": False})
        self.assertEqual(voce()["stato"], "ok", voce()["dettaglio"])
        self.assertIn("Gemello Digitale", voce()["dettaglio"])
