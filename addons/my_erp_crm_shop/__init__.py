from . import controllers, models


def configura_negozio(env):
    """Impostazioni del negozio, una volta sola all'installazione (poi si cambiano dalle
    Impostazioni). I metodi di pagamento restano spenti: il lancio lo decide chi gestisce il
    negozio, dopo il controllo di lancio."""
    Listino = env["product.pricelist"]
    for sito in env["website"].search([]):
        # Listino pubblico (quello in euro di configura_azienda.py, il primo per sequenza)
        # disponibile sul sito: senza, il negozio mostra i prezzi interni nella valuta contabile.
        # I listini interni di configura_azienda.py («Internal prices (GBP)») non vanno sul sito.
        Listino.search([("company_id", "in", (False, sito.company_id.id)),
                        ("name", "=like", "Internal prices%")]).write({"selectable": False, "website_id": False})
        if not Listino.search_count(Listino._get_website_pricelists_domain(sito), limit=1):
            pubblico = Listino.search([("company_id", "in", (False, sito.company_id.id)),
                                       ("website_id", "=", False),
                                       ("name", "not =like", "Internal prices%")], order="sequence, id", limit=1)
            pubblico.selectable = True
        # Ordine pagato online: fattura emessa e inviata da sola.
        sito.company_id.sale_automatic_invoice = True

    # Paese del cliente sempre richiesto, anche per i soli servizi: senza paese la fattura non
    # si emette (my_erp_crm_iva).
    env["ir.config_parameter"].sudo().set_bool("website_sale.require_billing_details_for_services", True)

    riepilogo = env.ref("digest.digest_digest_default", raise_if_not_found=False)
    if riepilogo:
        riepilogo.kpi_website_sale_total = True
