{
    "name": "my-erp-crm: panoramica",
    "summary": "Pagina iniziale con le app attive e un numero chiave per ciascuna.",
    "description": """
Dopo l'accesso my-erp-crm apriva la prima app del menu (per esempio il Commercio
elettronico). Questo modulo aggiunge la «Panoramica», in cima al menu, che diventa la
pagina iniziale: una tessera per ogni app installata e, dove ha senso, un numero da
guardare subito (opportunità aperte, preventivi da confermare, prenotazioni di oggi,
documenti da firmare, fatture da incassare). Clic sulla tessera: apre l'app; clic sul
numero: apre l'elenco di quei record.
""",
    "version": "1.0",
    "category": "Hidden",
    "author": "my-erp-crm",
    "website": "https://github.com/sergiodarpa-bit/my-erp-crm",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [
        "views/panoramica.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "my_erp_crm_home/static/src/**/*",
        ],
        "web.assets_tests": [
            "my_erp_crm_home/static/tests/tours/*.js",
        ],
    },
    "auto_install": True,
}
