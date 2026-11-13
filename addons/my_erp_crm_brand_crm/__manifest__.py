{
    "name": "my-erp-crm: marchio nel CRM",
    "summary": "Menu «Genera contatti» senza le voci che vendono servizi di Odoo S.A.",
    "description": """
Il menu «Genera contatti» del CRM proponeva due servizi di Odoo S.A.: «Lead Sourcing» (ricerca di
aziende a pagamento, con i crediti IAP comprati da Odoo) e «Mail plugins» (una finestra con un video
promozionale su YouTube). Questo modulo le toglie; restano sito, email, sondaggi e importazione da
file. Si installa da solo insieme al CRM.
""",
    "version": "1.0",
    "category": "Hidden",
    "author": "my-erp-crm",
    "website": "https://github.com/sergiodarpa-bit/my-erp-crm",
    "license": "LGPL-3",
    "depends": ["crm", "my_erp_crm_brand"],
    "assets": {
        "web.assets_backend": [
            "my_erp_crm_brand_crm/static/src/**/*",
        ],
    },
    "auto_install": True,
}
