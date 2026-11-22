from urllib.parse import urlparse

from . import controllers, models


def imposta_sito_gestionale(env):
    """Accende «La radice apre il gestionale» sul sito che serve l'indirizzo del gestionale:
    quello con dominio erp.…, oppure, se nessuno ce l'ha, il primo sito senza dominio (il
    predefinito, che risponde agli indirizzi non assegnati ad altri siti)."""
    siti = env["website"].search([])
    gestionale = siti.filtered(lambda s: (urlparse(s.domain or "").hostname or "").startswith("erp."))
    if not gestionale:
        gestionale = siti.filtered(lambda s: not s.domain)[:1]
    gestionale.my_erp_crm_apri_gestionale = True
