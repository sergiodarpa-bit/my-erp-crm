{
    "name": "my-erp-crm: marchio nelle Vendite",
    "summary": "Elenco dei preventivi vuoto senza il video promozionale di Odoo.",
    "description": """
Quando l'elenco dei preventivi è vuoto, il modulo Vendite mostra la miniatura di un video su
YouTube (la presentazione di Odoo S.A., con i dati di un'azienda di esempio). Questo modulo la
toglie: resta il testo di aiuto. Si installa da solo insieme alle Vendite.
""",
    "version": "1.0",
    "category": "Hidden",
    "author": "my-erp-crm",
    "website": "https://github.com/sergiodarpa-bit/my-erp-crm",
    "license": "LGPL-3",
    "depends": ["sale", "my_erp_crm_brand"],
    "assets": {
        "web.assets_backend": [
            "my_erp_crm_brand_sale/static/src/**/*",
        ],
    },
    "auto_install": True,
}
