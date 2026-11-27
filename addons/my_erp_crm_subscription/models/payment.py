from odoo import models


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    def _is_tokenization_required(self, **kwargs):
        """Un ordine con abbonamenti si paga solo salvando la carta: servirà per i rinnovi."""
        sale_order_id = kwargs.get("sale_order_id")
        if sale_order_id:
            ordine = self.env["sale.order"].sudo().browse(int(sale_order_id)).exists()
            if ordine and ordine._my_erp_crm_righe_ricorrenti():
                return True
        return super()._is_tokenization_required(**kwargs)

    def _find_available_payment_methods(self, partner_id, *, force_tokenization=False, **kwargs):
        # Odoo toglie i fornitori che non salvano la carta, ma non i loro metodi che non la
        # salvano (per esempio alcuni portafogli): senza carta salvata non c'è rinnovo.
        force_tokenization = force_tokenization or self.env["payment.provider"]._is_tokenization_required(**kwargs)
        return super()._find_available_payment_methods(partner_id, force_tokenization=force_tokenization, **kwargs)


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _post_process(self):
        super()._post_process()
        for tx in self.filtered(lambda t: t.state in ("error", "cancel") and t.operation == "offline"):
            for ordine in tx.sale_order_ids.filtered("abbonamento_id"):
                abbonamento = ordine.abbonamento_id
                if abbonamento.ordine_in_corso_id == ordine and abbonamento.stato in ("attivo", "insoluto"):
                    abbonamento._addebito_fallito(tx)
