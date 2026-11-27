{
    "name": "my-erp-crm: abbonamenti",
    "summary": "Abbonamenti mensili e annuali venduti dal negozio, rinnovati con addebito "
               "automatico sulla carta salvata in Stripe.",
    "description": """
Odoo Community non ha la fatturazione ricorrente. Questo modulo la aggiunge appoggiandosi a
Stripe, con le fatture, le regole IVA e i numeri che restano in my-erp-crm:

- sul prodotto si sceglie la ricorrenza (ogni mese, ogni anno);
- al pagamento nel negozio la carta si salva per i rinnovi, con il consenso del cliente
  scritto sopra il pagamento;
- alla conferma dell'ordine nasce l'abbonamento;
- a ogni scadenza un ordine di rinnovo viene addebitato sulla carta (senza il cliente,
  pagamento «off-session» di Stripe) e fatturato;
- se l'addebito non riesce: email al cliente con il link per pagare o cambiare carta, tre
  tentativi a tre giorni, poi l'abbonamento si sospende;
- il cliente vede e disdice i suoi abbonamenti dal portale (Il mio account → Abbonamenti);
- Vendite → Ordini → Abbonamenti: elenco, stati, ricavo mensile ricorrente (MRR).

Vedi doc/commercio-elettronico.md.
""",
    "version": "1.0",
    "category": "Sales/Sales",
    "author": "my-erp-crm",
    "website": "https://github.com/sergiodarpa-bit/my-erp-crm",
    "license": "LGPL-3",
    "depends": ["my_erp_crm_shop"],
    "data": [
        "security/ir.access.csv",
        "data/abbonamento_data.xml",
        "views/abbonamento_views.xml",
        "views/product_template_views.xml",
        "views/portal_templates.xml",
        "views/website_sale_templates.xml",
    ],
    "post_init_hook": "prepara_abbonamenti",
    # Arriva con il negozio, anche in produzione al primo aggiornamento.
    "auto_install": ["my_erp_crm_shop"],
}
