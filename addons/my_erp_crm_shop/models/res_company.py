from odoo import models
from odoo.tools import SQL, html2plaintext


class ResCompany(models.Model):
    _inherit = "res.company"

    def _compute_invoice_terms_html(self):
        """Scegliendo «Come pagina web» Odoo riempie la pagina /terms con il suo modello di esempio
        («STANDARD TERMS AND CONDITIONS OF SALE … doesn't engage Odoo S.A. responsibility»), che
        finirebbe pubblicato come condizioni dell'azienda. my-erp-crm lascia la pagina vuota: le
        condizioni le scrive l'azienda."""
        return

    def _my_erp_crm_termini_di_esempio(self, testo=None):
        """Se le condizioni (testo semplice, o quelle dell'azienda in ogni lingua attiva) sono
        ancora il modello di esempio di Odoo. Il confronto è sull'inizio del modello, che non
        contiene il nome dell'azienda."""
        self.ensure_one()

        def piano(html):
            return " ".join(html2plaintext(html or "").split())

        lingue = [codice for codice, _nome in self.env["res.lang"].get_installed()]
        testi = [" ".join(testo.split())] if testo is not None else [
            piano(self.with_context(lang=codice).invoice_terms_html) for codice in lingue]
        for codice in lingue:
            esempio = self.env["ir.qweb"].with_context(lang=codice)._render(
                "account.account_default_terms_and_conditions",
                {"company_name": self.name, "company_country": self.country_id.name},
                raise_if_not_found=False)
            inizio = piano(esempio)[:150]
            if inizio and any(inizio in t for t in testi):
                return True
        return False

    def _my_erp_crm_togli_termini_di_esempio(self):
        """Toglie il modello di esempio di Odoo dalle condizioni, in tutte le lingue."""
        da_pulire = self.filtered(lambda azienda: azienda._my_erp_crm_termini_di_esempio())
        if da_pulire:
            # Il campo è tradotto: una scrittura ORM toglierebbe solo la lingua corrente. Prima
            # si salvano le scritture in sospeso, che altrimenti rimetterebbero il testo.
            da_pulire.flush_recordset(["invoice_terms_html"])
            self.env.cr.execute(SQL("UPDATE res_company SET invoice_terms_html = NULL WHERE id IN %s",
                                    tuple(da_pulire.ids)))
            da_pulire.invalidate_recordset(["invoice_terms_html"])
        return da_pulire
