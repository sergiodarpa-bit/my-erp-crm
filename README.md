# my-erp-crm

![my-erp-crm](addons/my_erp_crm_brand/static/img/logo.svg)

**my-erp-crm** è un gestionale ERP e CRM open source: contatti, opportunità commerciali,
preventivi e ordini, calendario, email e, quando servono, contabilità, magazzino,
progetti e tutte le altre applicazioni incluse.

- **Gratuito** e con **codice sorgente pubblico**
- Licenza **GNU LGPL v3** (vedi [LICENSE](LICENSE))
- Basato su **Odoo Community Edition 19.0** (vedi [NOTICE.md](NOTICE.md))
- Interfaccia in italiano

| Accesso | CRM |
|---|---|
| ![Pagina di accesso](addons/my_erp_crm_brand/static/description/screenshot_login.png) | ![Flusso CRM](addons/my_erp_crm_brand/static/description/screenshot_crm.png) |

## Avvio rapido con Docker

Serve un computer o server con Docker e il plugin Compose.

```bash
git clone https://github.com/sergiodarpa-bit/my-erp-crm.git
```

```bash
cd my-erp-crm
```

```bash
cp .env.example .env
```

Apri `.env` e cambia `POSTGRES_PASSWORD`. Apri `deploy/my-erp-crm.conf` e cambia `admin_passwd`.

```bash
./scripts/init.sh
```

Il primo avvio costruisce l'immagine (qualche minuto), crea il database `my-erp-crm` in
italiano e installa CRM, Vendite, Contatti e Calendario. Poi apri http://localhost:8069,
entra con `admin` / `admin` e **cambia subito la password**.

Per scegliere altre applicazioni al primo avvio:

```bash
APPS=crm,sale_management,contacts,calendar,account,stock ./scripts/init.sh
```

Avvii successivi:

```bash
docker compose up -d
```

## Avvio senza Docker (sviluppo)

Servono Python 3.10–3.13 e PostgreSQL.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python my-erp-crm --addons-path=addons -d my-erp-crm -i crm --load-language=it_IT
```

## Cosa abbiamo cambiato rispetto a Odoo Community

| Dove | Cosa |
|---|---|
| `addons/my_erp_crm_brand` | Nome, colori e logo nell'interfaccia; pagina di accesso; menu utente senza link commerciali a odoo.com; sezione *Informazioni* con note di licenza; titoli delle finestre di errore |
| `addons/my_erp_crm_brand_mail` | "Fornito da my-erp-crm" nelle email; assistente automatico "my-erp-crm Bot" |
| `addons/my_erp_crm_brand_portal` | Collegamento "Fornito da" nel portale clienti |
| `addons/web/static/img` | Logo, icone e favicon sostituiti con quelli di my-erp-crm |
| `odoo/release.py` | Nome del prodotto |
| `my-erp-crm` | Comando di avvio (equivalente a `odoo-bin`) |
| `Dockerfile`, `docker-compose.yml`, `deploy/`, `scripts/` | Installazione |

I moduli del marchio si installano da soli in ogni nuovo database. Il resto del codice è
quello originale, così da poter ricevere le correzioni di sicurezza.

## Aggiornamenti di sicurezza dal progetto originale

Il file `UPSTREAM_COMMIT` indica la versione di Odoo Community da cui partiamo. Per portare
dentro le correzioni pubblicate in seguito sul ramo 19.0:

```bash
./scripts/aggiorna-da-odoo.sh
```

Lo script scarica le differenze, le applica e crea un commit. Se una modifica tocca un file
che abbiamo cambiato anche noi, si ferma e segnala il conflitto da risolvere a mano.

## Marchi

"Odoo" è un marchio registrato di Odoo S.A. my-erp-crm non è affiliato a Odoo S.A. né da
essa approvato; il nome compare solo per indicare la provenienza del codice, come richiesto
dalla licenza.
