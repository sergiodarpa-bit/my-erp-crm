from odoo import models
from odoo.tools import formatLang

from odoo.addons.my_erp_crm_shop.models.controllo_negozio import MANCA, OK


class MyErpCrmControlloNegozio(models.TransientModel):
    _inherit = "my_erp_crm.controllo.negozio"

    def _controlli(self):
        voci = super()._controlli()
        sito = self.website_id.sudo()
        voci.append(self._controllo_abbonamenti(sito, sito.company_id))
        return voci

    def _controllo_abbonamenti(self, sito, azienda):
        titolo = "Abbonamenti"
        ricorrenti = self._prodotti_pubblicati(sito).filtered("abbonamento_ricorrenza")
        if not ricorrenti:
            return self._voce(OK, titolo, "Nessun prodotto pubblicato è un abbonamento: tutto si paga "
                              "una volta sola. La ricorrenza si sceglie sul prodotto (scheda Vendite).")
        salvano = self.env["payment.provider"].sudo().search([
            "|", ("module_state", "=", "installed"), ("module_id", "=", False),
            ("is_published", "=", True), ("allow_tokenization", "=", True),
            ("company_id", "=", azienda.id), ("website_id", "in", (False, sito.id)),
        ])
        if not salvano:
            return self._voce(MANCA, titolo, f"In abbonamento: {self._nomi(ricorrenti)}. Nessun metodo di "
                              f"pagamento pubblicato salva la carta per i rinnovi, quindi i clienti non "
                              f"potrebbero comprarli: nel metodo Stripe accendi «Permetti di salvare metodi "
                              f"di pagamento».")
        Abbonamento = self.env["my_erp_crm.abbonamento"].sudo()
        attivi = Abbonamento.search([("company_id", "=", azienda.id), ("stato", "in", ("attivo", "insoluto"))])
        mrr = " + ".join(
            formatLang(self.env, sum(attivi.filtered(lambda a, v=valuta: a.currency_id == v).mapped("importo_mensile")),
                       currency_obj=valuta)
            for valuta in attivi.currency_id) or "0"
        return self._voce(OK, titolo, f"In abbonamento: {self._nomi(ricorrenti)}. Rinnovi addebitati con "
                          f"{self._nomi(salvano)}. Abbonamenti che si rinnovano: {len(attivi)} "
                          f"(ricavo mensile ricorrente, imponibile: {mrr}).")
