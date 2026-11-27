import re

from . import controllers, models

# «Gemello Digitale · mensile», «Agente AI: Longevità · annuale», «… (monthly)»
RICORRENZA_NEL_NOME = {
    "mese": re.compile(r"[\s·\-–(/]+(mensile|monthly)\)?\s*$", re.IGNORECASE),
    "anno": re.compile(r"[\s·\-–(/]+(annuale|annual|yearly)\)?\s*$", re.IGNORECASE),
}


def prepara_abbonamenti(env):
    """Una volta sola, all'installazione:

    - Stripe salva la carta quando serve (il cliente lo legge sopra il pagamento): senza, gli
      abbonamenti non si potrebbero comprare;
    - i servizi in vendita il cui nome finisce con «mensile» o «annuale» (o monthly, annual,
      yearly, in qualsiasi lingua attiva) diventano abbonamenti mensili o annuali.
    """
    env["payment.provider"].search([("code", "=", "stripe")]).allow_tokenization = True

    lingue = [codice for codice, _nome in env["res.lang"].get_installed()]
    servizi = env["product.template"].search([
        ("sale_ok", "=", True), ("type", "=", "service"), ("abbonamento_ricorrenza", "=", False)])
    for servizio in servizi:
        nomi = {servizio.with_context(lang=lingua).name or "" for lingua in lingue}
        for ricorrenza, schema in RICORRENZA_NEL_NOME.items():
            if any(schema.search(nome) for nome in nomi):
                servizio.abbonamento_ricorrenza = ricorrenza
                break
