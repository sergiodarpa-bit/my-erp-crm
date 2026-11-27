from unittest.mock import patch

from odoo.tests import HttpCase, TransactionCase, tagged

from .common import VIES_VALIDA, NegozioIvaCommon, RispostaVies


@tagged("post_install", "-at_install")
class TestCheckoutIva(NegozioIvaCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._imposta_iva()

    def test_servizio_digitale_a_privato_ue_non_si_paga(self):
        carrello = self._carrello(self.privato_de, self.app)
        self.assertEqual(carrello.fiscal_position_id, self.privati_ue)
        self.assertFalse(carrello._is_cart_ready_for_payment())
        self.assertTrue(carrello._has_blocking_alerts())
        self.assertTrue(carrello.order_line.alerts, "la riga bloccata ha il suo avviso")

    def test_servizio_generale_a_privato_ue_si_paga(self):
        carrello = self._carrello(self.privato_de, self.servizio)
        self.assertTrue(carrello._is_cart_ready_for_payment())
        self.assertFalse(carrello._has_blocking_alerts())
        self.assertEqual(carrello.order_line.tax_ids, self.fuori_campo)

    def test_impresa_verificata_vies_compra_in_reverse_charge(self):
        carrello = self._carrello(self._impresa_de(), self.app)
        self.assertEqual(carrello.fiscal_position_id, self.imprese_ue)
        self.assertTrue(carrello._is_cart_ready_for_payment())
        self.assertEqual(carrello.order_line.tax_ids, self.reverse_charge)

    def test_partita_iva_aggiunta_dopo_l_indirizzo(self):
        # Il cliente sceglie l'indirizzo da privato e poi aggiunge la partita IVA: il negozio
        # non ricalcola la posizione fiscale, il controllo prima del pagamento sì.
        cliente = self.privato_de.copy({"name": "Cliente che diventa impresa"})
        carrello = self._carrello(cliente, self.app)
        self.assertEqual(carrello.fiscal_position_id, self.privati_ue)
        with patch("odoo.addons.my_erp_crm_iva.models.res_partner.requests.get",
                   return_value=RispostaVies(VIES_VALIDA)):
            cliente.write({"vat": "DE123456788", "is_company": True})
            cliente.flush_recordset()
        self.assertTrue(carrello._is_cart_ready_for_payment())
        self.assertEqual(carrello.fiscal_position_id, self.imprese_ue)
        self.assertEqual(carrello.order_line.tax_ids, self.reverse_charge)

    def test_riga_senza_imposta_e_senza_posizione_non_si_paga(self):
        # Solo le posizioni UE: un cliente americano resta senza posizione fiscale.
        self.env["account.fiscal.position"].search(
            [("id", "not in", (self.imprese_ue | self.privati_ue).ids)]).active = False
        cliente = self.privato_de.copy({"name": "Cliente USA", "country_id": self.env.ref("base.us").id})
        prodotto = self.servizio.copy({"name": "Servizio senza imposta", "taxes_id": False})
        carrello = self._carrello(cliente, prodotto)
        self.assertFalse(carrello.fiscal_position_id)
        self.assertFalse(carrello._is_cart_ready_for_payment())
        self.assertIn("cannot be purchased online at the moment", carrello._join_alert_messages())
        # Con l'imposta il carrello torna pagabile.
        carrello._clear_alerts()
        carrello.order_line.tax_ids = self.generale
        self.assertTrue(carrello._is_cart_ready_for_payment())

    def test_prove_oss(self):
        oss_de = self.env["account.fiscal.position"].create({
            "name": "EU consumers - Germany (OSS)", "auto_apply": True, "sequence": 4,
            "country_id": self.de.id, "oss_location_proofs_required": True})
        carrello = self._carrello(self.privato_de, self.app)
        self.assertEqual(carrello.fiscal_position_id, oss_de)

        carrello._my_erp_crm_registra_prove_oss(None)
        self.assertFalse(carrello._is_cart_ready_for_payment(), "senza paese della connessione")
        carrello._clear_alerts()

        carrello._my_erp_crm_registra_prove_oss("ch")
        self.assertFalse(carrello._is_cart_ready_for_payment(), "paesi diversi")
        self.assertIn("(CH)", carrello._join_alert_messages())
        carrello._clear_alerts()

        carrello._my_erp_crm_registra_prove_oss("DE")
        self.assertTrue(carrello._is_cart_ready_for_payment())
        self.assertEqual(carrello.oss_location_proof_1, "Indirizzo di fatturazione: DE")
        self.assertEqual(carrello.oss_location_proof_2, "Connessione del cliente (IP): DE")

        # Le prove passano nella fattura, che così si emette.
        carrello.action_confirm()
        fattura = carrello._create_invoices()
        self.assertEqual(fattura.oss_location_proof_2, "Connessione del cliente (IP): DE")
        fattura.action_post()
        self.assertIn("OSS DE", fattura.vat_treatment_proof)


@tagged("post_install", "-at_install")
class TestCheckoutIvaHttp(NegozioIvaCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._imposta_iva()

    def test_transazione_rifiutata_prima_del_pagamento(self):
        # Il blocco vale anche lato server: senza passare dalla pagina di pagamento, la
        # transazione non si crea.
        sito = self.env["website"].search([], limit=1)
        carrello = self._carrello(self.privato_de, self.app, sito)
        risposta = self.make_jsonrpc_request(
            f"/shop/payment/transaction/{carrello.id}",
            {"access_token": carrello._portal_ensure_token(), "amount": carrello.amount_total},
        )
        self.assertEqual(risposta["state"], "error")
        self.assertEqual(risposta["redirect"], "/shop/checkout")
        self.assertIn("cannot be sold online to private customers", risposta["state_message"])
        self.assertFalse(carrello.transaction_ids)
