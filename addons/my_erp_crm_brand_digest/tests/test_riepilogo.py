from odoo.tests import TransactionCase, tagged

# Indirizzi che nel riepilogo non devono più comparire: odoo.com (anche nei «Sent by»/«Powered by»),
# le immagini su download.odoocdn.com, i negozi delle app.
VIETATI = ("odoo.com", "odoocdn.com", "play.google.com", "itunes.apple.com", "apps.apple.com")


@tagged("post_install", "-at_install")
class TestRiepilogo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.utente = cls.env.ref("base.user_admin")
        # con due indicatori accesi: ognuno porta la sua icona
        cls.riepilogo = cls.env["digest.digest"].create({
            "name": "Riepilogo di prova", "user_ids": [(4, cls.utente.id)],
            "kpi_res_users_connected": True, "kpi_mail_message_total": True})
        Consiglio = cls.env["digest.tip"]
        # i consigli già nel database restano fuori dalla prova: li ha già «ricevuti» l'utente
        Consiglio.search([]).user_ids += cls.utente
        cls.consiglio_odoo = Consiglio.create({
            "name": "Consiglio con immagine di Odoo", "sequence": 1,
            "tip_description": '<p>Prova</p><img src="https://download.odoocdn.com/digests/x.gif"/>'})
        cls.consiglio_pulito = Consiglio.create({
            "name": "Consiglio pulito", "sequence": 2,
            "tip_description": "<p>CONSIGLIO-SENZA-SERVER-ESTERNI</p>"})

    def _email(self):
        self.riepilogo._action_send_to_user(self.utente, tips_count=1, consume_tips=False)
        return self.env["mail.mail"].search([("email_to", "ilike", self.utente.email)], order="id desc", limit=1)

    def test_niente_pubblicita_ne_server_di_odoo(self):
        corpo = str(self._email().body_html)
        for indirizzo in VIETATI:
            self.assertNotIn(indirizzo, corpo, "il riepilogo non porta più %s" % indirizzo)
        self.assertIn("github.com/sergiodarpa-bit/my-erp-crm", corpo, "«Powered by» porta a my-erp-crm")
        self.assertIn('src="%s/' % self.riepilogo.get_base_url(), corpo, "le icone le serve il server stesso")

    def test_il_consiglio_e_quello_senza_server_di_odoo(self):
        corpo = str(self._email().body_html)
        self.assertIn("CONSIGLIO-SENZA-SERVER-ESTERNI", corpo,
                      "il consiglio con l'immagine di Odoo viene prima, ma si salta")

    def test_la_ricerca_normale_dei_consigli_non_cambia(self):
        # il filtro vale solo dentro il riepilogo: dall'interfaccia si vedono tutti i consigli
        self.assertIn(self.consiglio_odoo, self.env["digest.tip"].search([]))
