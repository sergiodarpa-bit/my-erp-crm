from odoo.tests import TransactionCase, tagged
from odoo.tools import html2plaintext

from .common import NegozioIvaCommon
from odoo.addons.my_erp_crm_shop import configura_negozio


@tagged("post_install", "-at_install")
class TestControlloNegozio(NegozioIvaCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._imposta_iva()
        cls.sito = cls.env["website"].search([], limit=1)
        cls.env["product.template"].search([("is_published", "=", True)]).is_published = False

    def _controllo(self):
        controllo = self.env["my_erp_crm.controllo.negozio"].create({"website_id": self.sito.id})
        return controllo, {voce["titolo"]: voce for voce in controllo._controlli()}

    def test_negozio_vuoto_non_e_pronto(self):
        controllo, voci = self._controllo()
        self.assertFalse(controllo.pronto)
        self.assertEqual(voci["Prodotti in vendita"]["stato"], "manca")
        self.assertIn("Prodotti in vendita", controllo.risultato)
        self.assertIn("Manca", controllo.risultato)

    def test_prodotti_senza_prezzo(self):
        gratis = self.servizio.product_tmpl_id.copy({"name": "Senza prezzo", "list_price": 0})
        gratis.is_published = True
        _controllo, voci = self._controllo()
        self.assertEqual(voci["Prodotti in vendita"]["stato"], "manca")
        self.assertIn("Senza prezzo", voci["Prodotti in vendita"]["dettaglio"])
        gratis.list_price = 80
        _controllo, voci = self._controllo()
        self.assertEqual(voci["Prodotti in vendita"]["stato"], "ok")

    def test_servizi_digitali_bloccati_per_i_privati_ue(self):
        self.app.product_tmpl_id.is_published = True
        _controllo, voci = self._controllo()
        self.assertEqual(voci["IVA nel negozio"]["stato"], "avviso")
        self.assertIn("EU consumers", voci["IVA nel negozio"]["dettaglio"])
        self.assertIn("App subscription", voci["IVA nel negozio"]["dettaglio"])

    def test_bonifico_senza_conto(self):
        bonifico = self.env.ref("payment.payment_provider_transfer")
        bonifico.write({"is_live": True, "is_published": True, "partner_bank_id": False,
                        "company_id": self.env.company.id})
        _controllo, voci = self._controllo()
        self.assertEqual(voci["Pagamenti online"]["stato"], "manca")
        self.assertIn("conto bancario", voci["Pagamenti online"]["dettaglio"])

    def test_configurazione_all_installazione(self):
        # Come in produzione dopo configura_azienda.py: listini accesi, listino pubblico in
        # euro per primo, non ancora disponibile sul sito.
        self.env["res.config.settings"].create({"group_product_pricelist": True}).execute()
        euro = self.env.ref("base.EUR")
        euro.active = True
        Listino = self.env["product.pricelist"]
        Listino.search([]).write({"selectable": False, "website_id": False})
        # Creato da configura_azienda.py prima del negozio: senza sito.
        pubblico = Listino.create({"name": "Public prices (EUR)", "currency_id": euro.id, "sequence": 1,
                                   "website_id": False})
        # Il listino interno, arrivato sul sito quando il negozio è stato installato dopo.
        interno = Listino.create({"name": "Internal prices (USD)", "sequence": 10,
                                  "website_id": self.sito.id, "selectable": True})
        self.env.company.sale_automatic_invoice = False
        _controllo, voci = self._controllo()
        self.assertIn("Internal prices (USD)", voci["Prezzi pubblici"]["dettaglio"], "prezzi interni ai clienti")
        self.assertEqual(voci["Fattura al pagamento"]["stato"], "avviso")

        configura_negozio(self.env)
        _controllo, voci = self._controllo()
        self.assertTrue(pubblico.selectable)
        self.assertFalse(interno.selectable or interno.website_id)
        self.assertEqual(voci["Prezzi pubblici"]["stato"], "ok")
        self.assertIn("Public prices (EUR)", voci["Prezzi pubblici"]["dettaglio"])
        self.assertEqual(voci["Fattura al pagamento"]["stato"], "ok")
        self.assertEqual(voci["Riepilogo via email"]["stato"], "ok")

    def test_termini_di_esempio_non_bastano(self):
        self.env["ir.config_parameter"].set_bool("account.use_invoice_terms", True)
        azienda = self.env.company
        azienda.terms_type = "html"
        azienda.invoice_terms_html = self.env["ir.qweb"]._render(
            "account.account_default_terms_and_conditions",
            {"company_name": azienda.name, "company_country": azienda.country_id.name})
        _controllo, voci = self._controllo()
        self.assertEqual(voci["Termini e condizioni"]["stato"], "manca")
        self.assertIn("testo di esempio", voci["Termini e condizioni"]["dettaglio"])

        azienda.invoice_terms_html = "<p>Condizioni di vendita dei servizi della clinica: recesso entro 14 giorni.</p>"
        _controllo, voci = self._controllo()
        self.assertNotEqual(voci["Termini e condizioni"]["stato"], "manca")

    def test_niente_testo_di_odoo_nei_termini(self):
        azienda = self.env.company
        # Scegliendo «Come pagina web» la pagina resta vuota, invece del modello di Odoo.
        azienda.write({"terms_type": "plain", "invoice_terms_html": False})
        azienda.terms_type = "html"
        self.assertFalse(html2plaintext(azienda.invoice_terms_html or "").strip())

        # Il modello già presente (anche tradotto) si toglie in tutte le lingue.
        esempio = self.env["ir.qweb"]._render(
            "account.account_default_terms_and_conditions",
            {"company_name": azienda.name, "company_country": azienda.country_id.name})
        azienda.invoice_terms_html = esempio
        self.env["res.lang"]._activate_lang("it_IT")
        azienda.with_context(lang="it_IT").invoice_terms_html = esempio
        self.assertEqual(azienda._my_erp_crm_togli_termini_di_esempio(), azienda)
        for lingua in ("en_US", "it_IT"):
            self.assertFalse(azienda.with_context(lang=lingua).invoice_terms_html)

        # Le condizioni vere restano.
        azienda.invoice_terms_html = "<p>Condizioni di vendita della clinica.</p>"
        self.assertFalse(azienda._my_erp_crm_togli_termini_di_esempio())
        self.assertIn("clinica", azienda.invoice_terms_html)

    def test_chiavi_stripe(self):
        stripe = self.env["payment.provider"].search([("code", "=", "stripe")], limit=1)
        stripe.write({"stripe_publishable_key": False, "stripe_secret_key": False,
                      "stripe_webhook_secret": False, "is_published": False, "is_live": False})

        def voce():
            return self._controllo()[1]["Chiavi Stripe"]

        self.assertEqual(voce()["stato"], "avviso")
        self.assertIn("«Connetti» non le porta da solo", voce()["dettaglio"])

        stripe.write({"stripe_publishable_key": "pk_test_abc", "stripe_secret_key": "sk_live_xyz"})
        self.assertEqual(voce()["stato"], "manca", "chiavi di modalità diverse")

        stripe.write({"stripe_secret_key": "sk_test_xyz", "is_live": True})
        self.assertEqual(voce()["stato"], "manca", "attivo con chiavi di prova")

        stripe.write({"stripe_publishable_key": "pk_live_abc", "stripe_secret_key": "sk_live_xyz"})
        self.assertEqual(voce()["stato"], "avviso", "manca il webhook")
        self.assertNotIn("sk_live_xyz", voce()["dettaglio"], "le chiavi non si mostrano")

        stripe.stripe_webhook_secret = "whsec_123"
        self.assertEqual(voce()["stato"], "ok")
