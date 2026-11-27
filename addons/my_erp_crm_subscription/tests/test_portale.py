from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestPortaleAbbonamenti(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cliente = cls.env["res.partner"].create({"name": "Cliente del portale", "email": "cliente@example.com"})
        prodotto = cls.env["product.product"].create({
            "name": "Gemello Digitale · mensile", "type": "service", "list_price": 50,
            "abbonamento_ricorrenza": "mese"})
        cls.abbonamento = cls.env["my_erp_crm.abbonamento"].create({
            "partner_id": cls.cliente.id,
            "currency_id": cls.env.company.currency_id.id,
            "ricorrenza": "mese",
            "riga_ids": [Command.create({"product_id": prodotto.id, "name": prodotto.name,
                                         "prezzo_unitario": 50, "prezzo_imponibile": 50, "prezzo_totale": 50})],
        })
        cls.token = cls.abbonamento._portal_ensure_token()

    def _pagina(self, prefisso=""):
        risposta = self.url_open(f"{prefisso}/my/subscriptions/{self.abbonamento.id}?access_token={self.token}")
        self.assertEqual(risposta.status_code, 200)
        return risposta.text

    def test_pagina_e_disdetta_dal_link_dell_email(self):
        # Chi compra senza account disdice dal link dell'email, che porta il codice di accesso.
        self.authenticate(None, None)
        pagina = self._pagina()
        self.assertIn(self.abbonamento.name, pagina)
        self.assertIn("Cancel subscription", pagina)

        self.url_open(f"/my/subscriptions/{self.abbonamento.id}/cancel",
                      data={"csrf_token": self.csrf_token(), "access_token": self.token})
        self.assertEqual(self.abbonamento.stato, "disdetto")
        self.assertIn("Reactivate subscription", self._pagina())

    def test_senza_codice_niente_disdetta(self):
        self.authenticate(None, None)
        self.url_open(f"/my/subscriptions/{self.abbonamento.id}/cancel",
                      data={"csrf_token": self.csrf_token(), "access_token": "sbagliato"})
        self.assertEqual(self.abbonamento.stato, "attivo")

    def test_in_italiano(self):
        italiano = self.env["res.lang"]._activate_lang("it_IT")
        self.env["website"].search([]).language_ids |= italiano
        pagina = self._pagina("/it")
        self.assertIn("Disdici l'abbonamento", pagina)
        self.assertIn("ogni mese", pagina)
        avviso = self.env.ref("my_erp_crm_subscription.avviso_abbonamento_pagamento").with_context(lang="it_IT")
        self.assertIn("Abbonamento con rinnovo automatico", avviso.arch_db)
        # Nel piè di pagina niente pubblicità di Odoo.
        self.assertNotIn("odoo.com/app/ecommerce", pagina)
