from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPanoramica(TransactionCase):
    def test_prima_voce_del_menu(self):
        # Senza azione iniziale my-erp-crm apre la prima app del menu: deve essere la Panoramica.
        menu = self.env["ir.ui.menu"].load_web_menus(False)
        prima = menu[menu["root"]["children"][0]]
        self.assertEqual(prima["xmlid"], "my_erp_crm_home.menu_panoramica")

    def test_numeri_solo_app_installate(self):
        numeri = self.env["my_erp_crm.panoramica"].numeri()
        for menu_id, numero in numeri.items():
            menu = self.env["ir.ui.menu"].browse(menu_id)
            self.assertFalse(menu.parent_id, "le chiavi sono le app (voci principali del menu)")
            self.assertIn(numero["modello"], self.env)
            self.assertIsInstance(numero["valore"], int)
        crm = self.env.ref("crm.crm_menu_root", raise_if_not_found=False)
        if crm:
            self.assertIn(crm.id, numeri)

    def test_opportunita_aperte(self):
        if "crm.lead" not in self.env:
            self.skipTest("CRM non installato")
        menu = self.env.ref("crm.crm_menu_root").id
        prima = self.env["my_erp_crm.panoramica"].numeri()[menu]["valore"]
        self.env["crm.lead"].create({"name": "Nuova opportunità", "type": "opportunity"})
        self.env["crm.lead"].create({"name": "Solo un contatto", "type": "lead"})
        self.assertEqual(self.env["my_erp_crm.panoramica"].numeri()[menu]["valore"], prima + 1)

    def test_appuntamenti_di_oggi(self):
        if "calendar.event" not in self.env:
            self.skipTest("Calendario non installato")
        menu = self.env.ref("calendar.mail_menu_calendar").id
        prima = self.env["my_erp_crm.panoramica"].numeri()[menu]["valore"]
        io = self.env.user.partner_id
        adesso = fields.Datetime.now()
        evento = {"partner_ids": [(4, io.id)], "user_id": self.env.user.id}
        self.env["calendar.event"].create(dict(evento, name="Oggi", start=adesso, stop=adesso + timedelta(minutes=30)))
        self.env["calendar.event"].create(dict(
            evento, name="Tra tre giorni", start=adesso + timedelta(days=3), stop=adesso + timedelta(days=3, hours=1)))
        self.assertEqual(self.env["my_erp_crm.panoramica"].numeri()[menu]["valore"], prima + 1)

    def test_senza_diritti_niente_numero(self):
        if "crm.lead" not in self.env:
            self.skipTest("CRM non installato")
        senza_crm = self.env["res.users"].create({
            "name": "Utente senza CRM",
            "login": "panoramica_senza_crm",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        numeri = self.env["my_erp_crm.panoramica"].with_user(senza_crm).numeri()
        self.assertNotIn(self.env.ref("crm.crm_menu_root").id, numeri)


@tagged("post_install", "-at_install")
class TestPanoramicaNelBrowser(HttpCase):
    def test_tour(self):
        if "crm.lead" not in self.env:
            self.skipTest("CRM non installato")
        admin = self.env.ref("base.user_admin")
        admin.action_id = False
        self.env["crm.lead"].search([("type", "=", "opportunity")]).action_archive()
        self.env["crm.lead"].create({
            "name": "Opportunità della prova Panoramica", "type": "opportunity", "user_id": admin.id,
        })
        self.start_tour("/odoo", "my_erp_crm_panoramica", login="admin")
