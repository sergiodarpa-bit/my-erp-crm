from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import NegozioIvaCommon
from odoo.addons.account_payment.tests.common import AccountPaymentCommon
from odoo.addons.sale.tests.common import SaleCommon


@tagged("post_install", "-at_install")
class TestPagamentoMaiPerso(NegozioIvaCommon, AccountPaymentCommon, SaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._imposta_iva()
        cls.env.company.sale_automatic_invoice = True

    def _paga(self, prodotto):
        ordine = self._create_so(partner_id=self.privato_de.id, order_line=[(0, 0, {"product_id": prodotto.id})])
        self.amount = ordine.amount_total
        self.currency = ordine.currency_id
        tx = self._create_transaction(flow="redirect", sale_order_ids=[ordine.id], state="done",
                                      partner_id=self.privato_de.id)
        with mute_logger("odoo.addons.sale.models.payment_transaction"):
            self._run_post_processing()
        return ordine, tx

    def test_fattura_bloccata_dall_iva_non_blocca_il_pagamento(self):
        # Un ordine pagato che le regole IVA non lasciano fatturare (servizio digitale a un
        # privato UE senza OSS, per esempio da un preventivo pagato dal portale).
        ordine, tx = self._paga(self.app)
        self.assertTrue(tx.is_post_processed, "l'elaborazione del pagamento non si ferma")
        self.assertEqual(ordine.state, "sale")
        self.assertTrue(tx.payment_id, "il pagamento è registrato")
        self.assertNotEqual(tx.payment_id.state, "draft")
        fattura = ordine.invoice_ids
        self.assertEqual(fattura.state, "draft")
        self.assertFalse(tx.invoice_ids, "la fattura sospesa esce dalla transazione")
        self.assertTrue(fattura.activity_ids, "qualcuno deve sistemare la fattura")
        self.assertIn(tx.reference, fattura.activity_ids.note)

    def test_fattura_creata_prima_del_pagamento(self):
        # Fattura preparata a mano mentre il pagamento era in attesa (per esempio un addebito
        # diretto): se l'IVA non la lascia emettere, esce dalla transazione invece di fermarla.
        ordine = self._create_so(partner_id=self.privato_de.id, order_line=[(0, 0, {"product_id": self.app.id})])
        self.amount = ordine.amount_total
        self.currency = ordine.currency_id
        tx = self._create_transaction(flow="redirect", sale_order_ids=[ordine.id], state="pending",
                                      partner_id=self.privato_de.id)
        ordine.action_confirm()
        fattura = ordine._create_invoices()
        self.assertEqual(tx.invoice_ids, fattura)
        self._update_transaction(tx, state="done")
        tx._invoice_sale_orders()
        self.assertFalse(tx.invoice_ids)
        self.assertEqual(fattura.state, "draft")
        self.assertTrue(fattura.activity_ids)

    def test_fattura_regolare_si_emette(self):
        ordine, tx = self._paga(self.servizio)
        self.assertEqual(ordine.state, "sale")
        self.assertEqual(ordine.invoice_ids.state, "posted")
        self.assertEqual(tx.invoice_ids, ordine.invoice_ids)
        self.assertFalse(ordine.invoice_ids.activity_ids)
