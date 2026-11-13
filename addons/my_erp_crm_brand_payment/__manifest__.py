{
    "name": "my-erp-crm: marchio nei metodi di pagamento",
    "summary": "Elenco dei metodi di pagamento senza quelli della versione a pagamento di Odoo.",
    "description": """
L'elenco dei metodi di pagamento mostrava anche quelli che esistono solo nella versione a pagamento
di Odoo (es. «Addebito diretto SEPA»), con il badge «Enterprise» e il pulsante «Aggiorna» verso il
listino di odoo.com: non si possono installare. Questo modulo li toglie dall'elenco, come
my_erp_crm_brand fa per le App. Si installa da solo insieme ai pagamenti.
""",
    "version": "1.0",
    "category": "Hidden",
    "author": "my-erp-crm",
    "website": "https://github.com/sergiodarpa-bit/my-erp-crm",
    "license": "LGPL-3",
    "depends": ["payment", "my_erp_crm_brand"],
    "data": [
        "data/ir_actions.xml",
    ],
    "auto_install": True,
}
