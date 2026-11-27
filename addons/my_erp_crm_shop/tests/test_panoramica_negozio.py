from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPanoramicaNegozio(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sito = cls.env["website"].search([], limit=1)
        cls.cliente = cls.env["res.partner"].create({"name": "Cliente del negozio"})
        cls.prodotto = cls.env["product.product"].create({"name": "Check-up", "type": "service", "list_price": 50})

    def _numero(self, xmlid):
        return self.env["my_erp_crm.panoramica"].numeri()[self.env.ref(xmlid).id]["valore"]

    def _ordine(self, **valori):
        return self.env["sale.order"].create({
            "partner_id": self.cliente.id,
            "order_line": [Command.create({"product_id": self.prodotto.id})],
            **valori,
        })

    def test_carrelli_non_sono_preventivi(self):
        prima = self._numero("sale.sale_menu_root")
        self._ordine(website_id=self.sito.id)  # un carrello del sito
        self.assertEqual(self._numero("sale.sale_menu_root"), prima)
        self._ordine()  # un preventivo vero
        self.assertEqual(self._numero("sale.sale_menu_root"), prima + 1)

    def test_ordini_online_da_gestire(self):
        prima = self._numero("website.menu_website_configuration")
        self._ordine(website_id=self.sito.id)  # carrello: non si gestisce ancora nulla
        attesa_bonifico = self._ordine(website_id=self.sito.id)
        attesa_bonifico.state = "sent"
        confermato = self._ordine(website_id=self.sito.id)
        confermato.action_confirm()  # pagato, fattura non ancora emessa
        self.assertEqual(self._numero("website.menu_website_configuration"), prima + 2)
        titolo = self.env["my_erp_crm.panoramica"].numeri()[
            self.env.ref("website.menu_website_configuration").id]["etichetta"]
        self.assertEqual(titolo, "ordini online da gestire")
