from odoo import models

# Ordini del sito che chiedono un intervento: in attesa di un pagamento non immediato (bonifico)
# oppure confermati e non ancora fatturati (fattura automatica spenta o sospesa per l'IVA).
ORDINI_ONLINE_DA_GESTIRE = [
    ("website_id", "!=", False),
    "|",
    ("state", "=", "sent"),
    "&", ("state", "=", "sale"), ("invoice_status", "=", "to invoice"),
]


class MyErpCrmPanoramica(models.AbstractModel):
    _inherit = "my_erp_crm.panoramica"

    def _indicatori(self):
        indicatori = []
        for xmlid, modello, etichetta, titolo, dominio in super()._indicatori():
            if xmlid == "sale.sale_menu_root":
                # Ogni visita al negozio con qualcosa nel carrello è un ordine in bozza: non
                # sono preventivi da confermare. Gli ordini del sito hanno la loro tessera.
                dominio = [*dominio, ("website_id", "=", False)]
            indicatori.append((xmlid, modello, etichetta, titolo, dominio))
        indicatori.append((
            "website.menu_website_configuration", "sale.order", "ordini online da gestire",
            "Ordini online da gestire (pagamenti attesi, fatture da emettere)",
            ORDINI_ONLINE_DA_GESTIRE,
        ))
        return indicatori
