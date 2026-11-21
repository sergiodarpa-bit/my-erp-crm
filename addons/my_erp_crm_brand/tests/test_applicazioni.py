from odoo.tests import TransactionCase, tagged

from odoo.addons.my_erp_crm_brand.models.ir_module_module import _chiede_settori


@tagged("post_install", "-at_install")
class TestApplicazioni(TransactionCase):
    def test_niente_app_a_pagamento_anche_senza_filtro_sull_azione(self):
        # Come in produzione il 21/11/2026: il dominio sull'azione non c'è più.
        self.env.ref("base.open_module_tree").domain = "[]"
        moduli = self.env["ir.module.module"]
        self.assertTrue(moduli.search([("to_buy", "=", True)], limit=1), "mancano i segnaposto da nascondere")
        risultato = moduli.web_search_read([("application", "=", True)], {"name": {}, "to_buy": {}}, limit=1000)
        nomi = [r["name"] for r in risultato["records"]]
        self.assertFalse([r["name"] for r in risultato["records"] if r["to_buy"]])
        self.assertNotIn("sign", nomi)
        self.assertNotIn("helpdesk", nomi)
        self.assertEqual(risultato["length"], len(nomi))

    def test_settori_non_toccati(self):
        self.assertTrue(_chiede_settori([("module_type", "=", "industries")]))
        self.assertTrue(_chiede_settori([("module_type", "in", ["industries"])]))
        self.assertFalse(_chiede_settori([("module_type", "=", "official"), ("application", "=", True)]))
        self.assertFalse(_chiede_settori([("application", "=", True)]))
