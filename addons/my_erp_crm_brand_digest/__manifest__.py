{
    "name": "my-erp-crm: marchio nelle email di riepilogo",
    "summary": "Riepiloghi periodici senza pubblicità dell'app Odoo e senza nulla scaricato dai server di Odoo.",
    "description": """
Il riepilogo periodico (l'email con gli indicatori che parte da sola verso gli utenti interni)
portava i badge «scarica l'app Odoo» per Google Play e App Store, i collegamenti «Sent by» e
«Powered by» verso odoo.com, le icone degli indicatori scaricate dai server di Odoo S.A.
(download.odoocdn.com) e un consiglio d'uso preso da un elenco in cui quasi ogni consiglio carica
immagini da lì, compreso quello che pubblicizza i plugin di posta. Questo modulo:

- toglie il riquadro dell'app mobile (vale anche per le email con le statistiche delle campagne);
- manda «Sent by» e «Powered by» a my-erp-crm;
- fa servire le icone degli indicatori dal server stesso;
- sceglie i consigli solo fra quelli che non caricano nulla dai server di Odoo.

Si installa da solo insieme al modulo dei riepiloghi.
""",
    "version": "1.0",
    "category": "Hidden",
    "author": "my-erp-crm",
    "website": "https://github.com/sergiodarpa-bit/my-erp-crm",
    "license": "LGPL-3",
    "depends": ["digest", "my_erp_crm_brand"],
    "data": [
        "views/digest_templates.xml",
    ],
    "auto_install": True,
}
