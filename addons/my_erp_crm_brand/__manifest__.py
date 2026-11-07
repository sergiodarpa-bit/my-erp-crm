{
    "name": "my-erp-crm: marchio",
    "summary": "Nome, logo e diciture di my-erp-crm nell'interfaccia web.",
    "description": """
Applica il marchio my-erp-crm all'interfaccia: pagina di accesso, piè di pagina
"Powered by", menu utente, sezione Informazioni nelle Impostazioni, titoli delle
finestre di errore e logo mostrato quando l'azienda non ha ancora caricato il proprio.
Si installa automaticamente con ogni nuovo database.
""",
    "version": "1.0",
    "category": "Hidden",
    "author": "my-erp-crm",
    "website": "https://github.com/sergiodarpa-bit/my-erp-crm",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [
        "views/webclient_templates.xml",
    ],
    "assets": {
        "web._assets_primary_variables": [
            ("prepend", "my_erp_crm_brand/static/scss/primary_variables.scss"),
        ],
        "web.assets_backend": [
            "my_erp_crm_brand/static/src/**/*",
        ],
    },
    "auto_install": True,
}
