# Provenienza e licenza

my-erp-crm è un'opera derivata da **Odoo Community Edition 20.0**.

- Codice originale: Copyright (c) 2004 e anni successivi Odoo S.A. e collaboratori
  (vedi [COPYRIGHT](COPYRIGHT)), pubblicato con licenza **GNU LGPL v3** (vedi [LICENSE](LICENSE)).
- Sorgente di partenza: https://github.com/odoo/odoo, ramo `20.0`, commit indicato nel file
  [`UPSTREAM_COMMIT`](UPSTREAM_COMMIT).
- Le modifiche di my-erp-crm sono distribuite con la stessa licenza GNU LGPL v3.

## Modifiche apportate

Dal 7 novembre 2026 il codice è stato modificato da my-erp-crm come segue:

- nome del prodotto cambiato in "my-erp-crm" (`odoo/release.py`, titoli di pagina e finestre);
- il nome "Odoo" nei testi del codice e delle traduzioni sostituito automaticamente con
  "my-erp-crm" da `scripts/rebrand.py`, lasciando intatte le note di copyright e licenza;
- aggiunti i moduli `my_erp_crm_currency_ecb` (tassi di cambio BCE) e `my_erp_crm_iva`
  (regole IVA e verifica VIES diretta) e la configurazione aziendale in `deploy/`;
- logo, icone e favicon sostituiti (`addons/web/static/img`);
- aggiunti i moduli `my_erp_crm_brand`, `my_erp_crm_brand_mail` e `my_erp_crm_brand_portal`
  (nome, colori e diciture dell'interfaccia, delle email e del portale);
- aggiunti il comando `my-erp-crm`, i file di installazione Docker e gli script in `scripts/`;
- aggiunto il modulo `my_erp_crm_shop` (negozio online: regole IVA prima del pagamento,
  controllo di lancio, numeri nella Panoramica);
- rimossi i modelli GitHub del progetto originale; README, CONTRIBUTING e SECURITY riscritti.

L'elenco completo e datato di ogni modifica è nella cronologia git di questo repository.

## Moduli di terze parti

- `addons/sign_oca` (firma dei documenti): dal progetto
  [OCA/sign](https://github.com/OCA/sign) della Odoo Community Association, Copyright Dixmit e
  collaboratori OCA, licenza **GNU AGPL v3 o successiva** (indicata nel suo
  `__manifest__.py`). Questo modulo resta sotto AGPL: chi lo usa in rete ha diritto al suo
  codice sorgente, pubblicato in questo repository. Le modifiche di my-erp-crm sono elencate
  in [doc/firma-documenti.md](doc/firma-documenti.md).
- `addons/my_erp_crm_sale_sign` (firma dei preventivi) è scritto da my-erp-crm ma estende
  `sign_oca`: per questo è distribuito anch'esso con licenza **GNU AGPL v3**.

## Marchi

"Odoo" e il relativo logo sono marchi di Odoo S.A. La licenza LGPL non concede diritti sui
marchi: per questo my-erp-crm usa un nome e un logo propri.
