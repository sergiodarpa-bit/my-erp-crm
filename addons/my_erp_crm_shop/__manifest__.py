{
    "name": "my-erp-crm: negozio online",
    "summary": "Commercio elettronico pronto al lancio: IVA controllata prima del pagamento, "
               "pagamenti mai persi, controllo di lancio, numeri nella Panoramica.",
    "description": """
Strumenti per aprire il negozio online (Sito web → Commercio elettronico) con le regole IVA
di my-erp-crm:

- il pagamento non si apre per un carrello che non si potrebbe fatturare (servizi digitali a
  privati UE senza registrazione OSS, partita IVA non verificata VIES dove serve, paese del
  cliente non dimostrato per l'OSS): il cliente lo sa prima di pagare;
- prove di localizzazione OSS raccolte al checkout (paese dell'indirizzo di fatturazione e
  paese della connessione) e copiate in fattura;
- se una fattura automatica non si può emettere, il pagamento resta registrato, l'ordine
  confermato e la fattura in bozza con un'attività per chi la deve sistemare;
- Panoramica: i carrelli del sito non contano più fra i preventivi; la tessera del Sito web
  mostra gli ordini online da gestire;
- controllo di lancio (Sito web → Configurazione → Commercio elettronico): che cosa manca
  prima di aprire il negozio.

Vedi doc/commercio-elettronico.md.
""",
    "version": "1.0",
    "category": "Website/Website",
    "author": "my-erp-crm",
    "website": "https://github.com/sergiodarpa-bit/my-erp-crm",
    "license": "LGPL-3",
    "depends": [
        "website_sale",
        "payment_custom",
        "payment_stripe",
        "spreadsheet_dashboard_website_sale",
        "my_erp_crm_iva",
        "my_erp_crm_home",
    ],
    "data": [
        "security/ir.access.csv",
        "views/sale_order_views.xml",
        "views/controllo_negozio_templates.xml",
        "views/controllo_negozio_views.xml",
        "views/website_templates.xml",
    ],
    "post_init_hook": "configura_negozio",
    # Il negozio c'è già in produzione: il modulo arriva da solo al primo aggiornamento.
    "auto_install": ["website_sale", "my_erp_crm_iva"],
}
