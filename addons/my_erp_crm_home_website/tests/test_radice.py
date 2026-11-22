from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.my_erp_crm_home_website import imposta_sito_gestionale


@tagged("post_install", "-at_install")
class TestRadice(HttpCase):
    def _imposta(self, valore):
        self.env["website"].search([]).my_erp_crm_apri_gestionale = valore
        self.env.flush_all()

    def test_radice_apre_il_gestionale(self):
        self._imposta(True)
        risposta = self.url_open("/", allow_redirects=False)
        self.assertIn(risposta.status_code, (302, 303))
        self.assertTrue(risposta.headers["Location"].endswith("/odoo"), risposta.headers["Location"])

    def test_altre_pagine_del_sito_non_cambiano(self):
        self._imposta(True)
        risposta = self.url_open("/contactus", allow_redirects=False)
        self.assertEqual(risposta.status_code, 200)

    def test_senza_opzione_la_radice_e_il_sito(self):
        self._imposta(False)
        risposta = self.url_open("/", allow_redirects=False)
        self.assertEqual(risposta.status_code, 200)


@tagged("post_install", "-at_install")
class TestSitoGestionale(TransactionCase):
    def test_sito_con_dominio_erp(self):
        siti = self.env["website"].search([])
        siti.my_erp_crm_apri_gestionale = False
        erp = self.env["website"].create({"name": "Gestionale", "domain": "https://erp.esempio.invalid"})
        cal = self.env["website"].create({"name": "Calendari", "domain": "https://cal.esempio.invalid"})
        imposta_sito_gestionale(self.env)
        self.assertTrue(erp.my_erp_crm_apri_gestionale)
        self.assertFalse(cal.my_erp_crm_apri_gestionale)
        self.assertFalse(any((siti - erp).mapped("my_erp_crm_apri_gestionale")))

    def test_senza_dominio_erp_il_sito_predefinito(self):
        siti = self.env["website"].search([])
        siti.write({"my_erp_crm_apri_gestionale": False, "domain": False})
        cal = self.env["website"].create({"name": "Calendari", "domain": "https://cal.esempio.invalid"})
        imposta_sito_gestionale(self.env)
        predefinito = self.env["website"].search([("domain", "=", False)], limit=1)
        self.assertTrue(predefinito.my_erp_crm_apri_gestionale)
        self.assertFalse(cal.my_erp_crm_apri_gestionale)
        self.assertEqual(len(self.env["website"].search([("my_erp_crm_apri_gestionale", "=", True)])), 1)
