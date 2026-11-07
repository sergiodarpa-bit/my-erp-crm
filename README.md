# my-erp-crm

![my-erp-crm](addons/my_erp_crm_brand/static/img/logo.svg)

**my-erp-crm** è un gestionale ERP e CRM open source: contatti, opportunità commerciali,
preventivi e ordini, fatturazione, calendario, email e, quando servono, contabilità,
magazzino, progetti e tutte le altre applicazioni incluse.

- **Gratuito** e con **codice sorgente pubblico**
- Licenza **GNU LGPL v3** (vedi [LICENSE](LICENSE))
- Basato su **Odoo Community Edition 20.0** (vedi [NOTICE.md](NOTICE.md))
- Interfaccia in italiano e inglese

| Accesso | CRM |
|---|---|
| ![Pagina di accesso](addons/my_erp_crm_brand/static/description/screenshot_login.png) | ![Flusso CRM](addons/my_erp_crm_brand/static/description/screenshot_crm.png) |

## Messa online (produzione)

Il server di produzione è **https://erp.kliniksanktmoritz.ch**. A ogni modifica del ramo
`main`, GitHub Actions ([`.github/workflows/pubblica.yml`](.github/workflows/pubblica.yml)):

1. costruisce l'immagine Docker e la pubblica su `ghcr.io/sergiodarpa-bit/my-erp-crm`;
2. se il server è configurato, copia i file di [`deploy/produzione`](deploy/produzione) in
   `/opt/my-erp-crm` ed esegue `aggiorna.sh`: al primo avvio crea il database e configura
   l'azienda; le volte successive fa un **backup del database** e aggiorna i moduli.
   I dati non vengono mai cancellati.

HTTPS è automatico (Caddy con certificato Let's Encrypt).

**Cosa serve sul server:** Linux con Docker e il plugin Compose, porte 80 e 443 libere, e il
record DNS di `erp.kliniksanktmoritz.ch` che punta al suo indirizzo IP.

**Cosa serve su GitHub** (Settings → Secrets and variables → Actions):

| Tipo | Nome | Valore |
|---|---|---|
| Variable | `DEPLOY_HOST` | indirizzo IP o nome del server |
| Variable | `DEPLOY_USER` | utente SSH (predefinito `root`) |
| Secret | `DEPLOY_SSH_KEY` | chiave privata SSH con accesso al server |
| Secret | `DEPLOY_KNOWN_HOSTS` | risultato di `ssh-keyscan <server>` |

Prima del primo avvio, sul server: crea `/opt/my-erp-crm/.env` partendo da
[`deploy/produzione/.env.example`](deploy/produzione/.env.example) (password, dati
dell'azienda). Il file `.env` resta solo sul server.

## Azienda, IVA e prezzi

Lo script [`deploy/configura_azienda.py`](deploy/configura_azienda.py) viene eseguito al primo
avvio con i dati di `.env`:

- **Azienda nel Regno Unito** (`COMPANY_COUNTRY=GB`): piano dei conti britannico e
  contabilità in **sterline (GBP)**. La configurazione IVA preparata è quella di una società
  britannica **non registrata alla VAT** che vende servizi in Europa, in Svizzera e nel resto
  del mondo; se `COMPANY_VAT` è valorizzata lo script si ferma, perché per una società
  registrata le scelte vanno fatte col commercialista.
- **IVA sulle vendite**, scelta automaticamente in base al cliente:

  | Cliente | IVA in fattura | Dicitura in fattura |
  |---|---|---|
  | Regno Unito | nessuna | *No VAT charged: the supplier is not registered for UK VAT.* |
  | Impresa UE con numero IVA **verificato VIES** | nessuna | *Outside the scope of UK VAT. Reverse charge: the customer accounts for any VAT due in its own country.* |
  | Impresa svizzera con numero IVA | nessuna | *Outside the scope of UK VAT. Swiss acquisition tax (Bezugsteuer) may be due by the recipient in Switzerland.* |
  | Impresa o privato del resto del mondo | nessuna | *Outside the scope of UK VAT: place of supply outside the United Kingdom.* |
  | Privato UE (o impresa UE senza VIES valido) | servizi generali: nessuna; **servizi digitali: fattura fermata** finché non c'è la registrazione **OSS non-UE** (`OSS_REGISTERED=1`, poi l'IVA del paese del cliente) | — |

  Le diciture sono in inglese, con la traduzione italiana per i clienti di lingua italiana.
  Il modulo `my_erp_crm_iva` rende i controlli automatici:

  - **VIES** verificato direttamente sul servizio della Commissione europea (pulsante
    *Verifica VIES* sul contatto); se il servizio non risponde l'esito si può impostare a mano
    e resta nella cronologia del contatto;
  - il reverse charge si applica **solo** con VIES valido, altrimenti il cliente è trattato
    come privato;
  - una fattura **non si emette** senza paese del cliente, con righe senza imposta e senza
    posizione fiscale, in reverse charge senza VIES valido, per vendite non ancora ammesse
    (es. servizi digitali a privati UE senza OSS) o in OSS senza due prove di localizzazione;
  - ogni fattura conserva le **prove** del suo trattamento (*Altre informazioni*).

  **Clienti B2B e autofatturazione.** Per le imprese UE e svizzere la fattura è senza IVA e
  porta la dicitura; la **fattura elettronica UBL/Peppol** marca le righe come reverse charge
  (codice `AE`), così il gestionale del cliente la importa. Un modulo esterno di
  autofatturazione (per esempio uno che prepari il TD17 italiano) si collega indicando in
  `SELF_BILLING_FLAG_FIELD` il campo con cui si accende sulle posizioni fiscali.
- **Prezzi pubblici in euro**: il listino predefinito è *Public prices (EUR)*. Il prezzo in
  euro di ogni prodotto si imposta nel listino (regola "prezzo fisso"); la contabilità
  converte in sterline.
- **Tassi di cambio** aggiornati ogni giorno con i tassi di riferimento della Banca Centrale
  Europea (modulo `my_erp_crm_currency_ecb`).

## Avvio in locale con Docker

```bash
cp .env.example .env
```

Compila `.env` (password, nome dell'azienda), poi:

```bash
./scripts/init.sh
```

Apri http://localhost:8069 ed entra con `admin` e la password di `ADMIN_PASSWORD`.

## Avvio senza Docker (sviluppo)

Servono Python 3.12–3.14 e PostgreSQL.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python my-erp-crm --addons-path=addons -d my-erp-crm -i crm --load-language=it_IT
```

## Cosa abbiamo cambiato rispetto a Odoo Community

| Dove | Cosa |
|---|---|
| tutto il codice e le traduzioni | il nome "Odoo" nei testi diventa "my-erp-crm" ([`scripts/rebrand.py`](scripts/rebrand.py)) |
| `addons/my_erp_crm_brand` | colori e logo; pagina di accesso; menu utente senza link commerciali; sezione *Informazioni* con le note di licenza; niente app e opzioni della versione a pagamento |
| `addons/my_erp_crm_brand_mail` | "Fornito da my-erp-crm" nelle email; assistente "my-erp-crm Bot" |
| `addons/my_erp_crm_brand_portal` | collegamento "Fornito da" nel portale clienti |
| `addons/my_erp_crm_currency_ecb` | tassi di cambio BCE giornalieri |
| `addons/my_erp_crm_iva` | regole IVA: VIES, inversione contabile, OSS, prove in fattura |
| `addons/web/static/img` | logo, icone e favicon |
| `my-erp-crm` | comando di avvio (equivalente a `odoo-bin`) |
| `Dockerfile`, `docker-compose.yml`, `deploy/`, `scripts/`, `.github/` | installazione e pubblicazione |

Il cambio di nome non tocca le note di copyright ("Odoo S.A."), gli indirizzi odoo.com e i
moduli che dialogano con servizi esterni o autorità fiscali (localizzazioni, pagamenti,
fatturazione elettronica), dove i nomi possono avere valore tecnico o legale.

## Aggiornamenti di sicurezza dal progetto originale

Il file `UPSTREAM_COMMIT` indica la versione di Odoo Community da cui partiamo. Per portare
dentro le correzioni pubblicate in seguito sul ramo 20.0:

```bash
./scripts/aggiorna-da-odoo.sh
```

Le modifiche originali passano dallo stesso cambio di nome automatico, così si applicano
senza conflitti; lo script crea un commit e la pubblicazione parte da sola.

## Marchi

"Odoo" è un marchio registrato di Odoo S.A. my-erp-crm non è affiliato a Odoo S.A. né da
essa approvato; il nome compare solo per indicare la provenienza del codice, come richiesto
dalla licenza.
