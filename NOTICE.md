# Provenienza e licenza

my-erp-crm è un'opera derivata da **Odoo Community Edition 19.0**.

- Codice originale: Copyright (c) 2004 e anni successivi Odoo S.A. e collaboratori
  (vedi [COPYRIGHT](COPYRIGHT)), pubblicato con licenza **GNU LGPL v3** (vedi [LICENSE](LICENSE)).
- Sorgente di partenza: https://github.com/odoo/odoo, ramo `19.0`, commit indicato nel file
  [`UPSTREAM_COMMIT`](UPSTREAM_COMMIT).
- Le modifiche di my-erp-crm sono distribuite con la stessa licenza GNU LGPL v3.

## Modifiche apportate

Dal 7 novembre 2026 il codice è stato modificato da my-erp-crm come segue:

- nome del prodotto cambiato in "my-erp-crm" (`odoo/release.py`, titoli di pagina e finestre);
- il nome "Odoo" nei testi del codice e delle traduzioni sostituito automaticamente con
  "my-erp-crm" da `scripts/rebrand.py`, lasciando intatte le note di copyright e licenza;
- aggiunto il modulo `my_erp_crm_currency_ecb` (tassi di cambio BCE) e la configurazione
  aziendale in `deploy/`;
- logo, icone e favicon sostituiti (`addons/web/static/img`);
- aggiunti i moduli `my_erp_crm_brand`, `my_erp_crm_brand_mail` e `my_erp_crm_brand_portal`
  (nome, colori e diciture dell'interfaccia, delle email e del portale);
- aggiunti il comando `my-erp-crm`, i file di installazione Docker e gli script in `scripts/`;
- rimossi i modelli GitHub del progetto originale; README, CONTRIBUTING e SECURITY riscritti.

L'elenco completo e datato di ogni modifica è nella cronologia git di questo repository.

## Marchi

"Odoo" e il relativo logo sono marchi di Odoo S.A. La licenza LGPL non concede diritti sui
marchi: per questo my-erp-crm usa un nome e un logo propri.
