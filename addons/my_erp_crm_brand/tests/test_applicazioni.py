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

    def test_colonna_senza_categorie_di_sole_app_a_pagamento(self):
        moduli = self.env["ir.module.module"]
        a_pagamento = moduli.search([("to_buy", "=", True), ("application", "=", True)])
        self.assertTrue(a_pagamento, "mancano i segnaposto da nascondere")
        filtro_app = [("application", "=", True)]
        colonna = moduli.search_panel_select_range("category_id", enable_counters=True, search_domain=filtro_app)
        categorie = self.env["ir.module.category"].browse([v["id"] for v in colonna["values"]])
        for valore in colonna["values"]:
            # Ogni categoria ha almeno un modulo vero, e il contatore non conta le app a pagamento.
            dentro = [("category_id", "child_of", valore["id"])]
            self.assertTrue(moduli.search(dentro + [("to_buy", "=", False)], limit=1), valore["display_name"])
            self.assertEqual(valore["__count"], moduli.search_count(dentro + filtro_app + [("to_buy", "=", False)]))
        # Le categorie che contengono solo app a pagamento non ci sono.
        for modulo in a_pagamento:
            radice = modulo.category_id
            while radice.parent_id:
                radice = radice.parent_id
            if not moduli.search([("category_id", "child_of", radice.id), ("to_buy", "=", False)], limit=1):
                self.assertNotIn(radice, categorie, radice.name)

    def test_settori_non_toccati(self):
        self.assertTrue(_chiede_settori([("module_type", "=", "industries")]))
        self.assertTrue(_chiede_settori([("module_type", "in", ["industries"])]))
        self.assertFalse(_chiede_settori([("module_type", "=", "official"), ("application", "=", True)]))
        self.assertFalse(_chiede_settori([("application", "=", True)]))
