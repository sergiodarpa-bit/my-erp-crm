{
    "name": "my-erp-crm: panoramica e sito web",
    "summary": "All'indirizzo del gestionale (erp.…) la radice apre il gestionale, non la pagina del sito.",
    "description": """
Con il Sito web installato, l'indirizzo principale (per esempio https://erp.kliniksanktmoritz.ch)
apriva la pagina iniziale del sito (il negozio). Per il sito che serve il gestionale la radice
«/» porta ora a /odoo: accesso, poi la Panoramica. Le altre pagine del sito (/shop, …) e gli
altri siti (cal.…, flu.…) non cambiano. Si sceglie sito per sito in Sito web → Configurazione
→ Impostazioni («La radice apre il gestionale»); all'installazione è acceso sul sito con
dominio erp.…, o sul sito predefinito senza dominio.
""",
    "version": "1.0",
    "category": "Hidden",
    "author": "my-erp-crm",
    "website": "https://github.com/sergiodarpa-bit/my-erp-crm",
    "license": "LGPL-3",
    "depends": ["my_erp_crm_home", "website"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "post_init_hook": "imposta_sito_gestionale",
    "auto_install": True,
}
