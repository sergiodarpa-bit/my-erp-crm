#!/usr/bin/env bash
# Da eseguire sul server, nella cartella /opt/my-erp-crm.
# - primo avvio: crea il database, configura l'azienda e installa le applicazioni;
# - avvii successivi: backup del database, nuova immagine, aggiornamento dei moduli.
# Non cancella mai i dati: i volumi Docker restano dove sono.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "Manca .env: copia .env.example in .env e compilalo." >&2
  exit 1
fi
# Legge .env riga per riga (i valori possono contenere spazi, con o senza virgolette).
load_env() {
  local key value
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    [[ -z "${line// }" || "$line" =~ ^[[:space:]]*# ]] && continue
    key="${line%%=*}"; value="${line#*=}"
    key="${key//[[:space:]]/}"
    if [[ "$value" =~ ^\"(.*)\"$ || "$value" =~ ^\'(.*)\'$ ]]; then value="${BASH_REMATCH[1]}"; fi
    export "$key=$value"
  done < "$1"
}
load_env .env
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD vuota in .env}"
: "${MASTER_PASSWORD:?MASTER_PASSWORD vuota in .env}"

# Configurazione con la password principale presa da .env
# La cartella è riservata (750) e .env leggibile solo dal proprietario; il file di
# configurazione deve restare leggibile dall'utente senza privilegi del container.
chmod 750 . && chmod 600 .env
# Sostituzione della shell: la password non passa per la riga di comando (regola 6).
MODELLO="$(< my-erp-crm.conf.template)"
printf '%s\n' "${MODELLO//__MASTER_PASSWORD__/$MASTER_PASSWORD}" > my-erp-crm.conf
unset MODELLO
mkdir -p addons-extra
chmod 644 my-erp-crm.conf

COMPOSE="docker compose"
RUN="$COMPOSE run --rm -T"
BIN="/opt/my-erp-crm/my-erp-crm"
CONF="--config=/etc/my-erp-crm/my-erp-crm.conf"
APP="$BIN $CONF"

# Database e Caddy: se Docker Hub rifiuta (limite di richieste anonime) si usano le
# immagini già presenti; se mancano, "up" più sotto si ferma con l'errore.
# L'applicazione invece è ciò che si aggiorna: se non si scarica, ci si ferma qui.
# Un'immagine costruita qui (IMAGE senza "/") non si scarica.
# HTTPS_LOCALE=0: l'HTTPS lo fa un proxy su un altro server, il Caddy di qui non serve.
if [ "${HTTPS_LOCALE:-1}" = 0 ]; then SERVIZI="db app"; else SERVIZI="db app caddy"; fi
# shellcheck disable=SC2086
$COMPOSE pull --quiet ${SERVIZI/app/} || echo "Avviso: Docker Hub non risponde, uso le immagini già presenti"
if [[ "${IMAGE:-ghcr.io/}" == */* ]]; then $COMPOSE pull --quiet app; fi
$COMPOSE up -d db

# Pronto solo quando accetta connessioni TCP: al primo avvio l'immagine di Postgres
# accende un server temporaneo, solo sul socket locale, per inizializzarsi e poi lo
# spegne; chiedere sul socket in quel momento dà "pronto" e subito dopo "shutting down".
PRONTO=0
for i in $(seq 1 60); do
  if $COMPOSE exec -T db pg_isready -h 127.0.0.1 -U "${POSTGRES_USER:-myerp}" >/dev/null 2>&1; then PRONTO=1; break; fi
  sleep 2
done
if [ "$PRONTO" != 1 ]; then echo "Il database non risponde dopo 2 minuti: mi fermo." >&2; exit 1; fi

# Il database c'è già? La domanda sta fuori da ogni "if" e senza pipe: se psql
# fallisce, set -e ferma tutto invece di far credere assente un database che c'è
# (e rifare la prima installazione sopra i dati).
DB_PRESENTE=$($COMPOSE exec -T db psql -U "${POSTGRES_USER:-myerp}" -d postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname = 'my-erp-crm'")

ENVVARS=(-e SETUP_PHASE -e ADMIN_PASSWORD -e ADMIN_LANG -e PUBLIC_CURRENCY
         -e COMPANY_NAME -e COMPANY_COUNTRY -e COMPANY_VAT -e COMPANY_REGISTRY -e COMPANY_STREET
         -e COMPANY_CITY -e COMPANY_ZIP -e COMPANY_EMAIL -e COMPANY_PHONE -e COMPANY_WEBSITE
         -e OSS_REGISTERED -e SELF_BILLING_FLAG_FIELD
         -e COMPANY_STREET2 -e COMPANY_IBAN -e COMPANY_BANK_NAME -e COMPANY_BIC -e COMPANY_REPORT_FOOTER
         -e INVOICE_JOURNAL_CODE)

if [ "$DB_PRESENTE" = "1" ]; then
  echo "== Backup del database"
  mkdir -p backups
  $COMPOSE exec -T db pg_dump -U "${POSTGRES_USER:-myerp}" -Fc my-erp-crm > "backups/my-erp-crm-$(date +%Y%m%d-%H%M%S).dump"
  ls -1t backups/*.dump | tail -n +15 | xargs -r rm --
  echo "== Aggiornamento dei moduli"
  $COMPOSE stop app || true
  $RUN app $APP -u all --stop-after-init
  # I moduli nuovi di my-erp-crm che si installano da soli (i ponti del marchio, es.
  # my_erp_crm_brand_sale): in un database che c'è già «-u all» non li installa, perché Odoo
  # installa un modulo automatico solo insieme a una delle sue dipendenze. Si installano qui
  # quelli che hanno già installate tutte le dipendenze che li accendono.
  NUOVI_AUTO=$($COMPOSE exec -T db psql -U "${POSTGRES_USER:-myerp}" -d my-erp-crm -tAc "
    SELECT string_agg(m.name, ',' ORDER BY m.name) FROM ir_module_module m
     WHERE m.state = 'uninstalled' AND m.auto_install AND m.name LIKE 'my\_erp\_crm\_%'
       AND NOT EXISTS (SELECT 1 FROM ir_module_module_dependency d
                         LEFT JOIN ir_module_module x ON x.name = d.name
                        WHERE d.module_id = m.id AND d.auto_install_required
                          AND x.state IS DISTINCT FROM 'installed')")
  if [ -n "$NUOVI_AUTO" ]; then
    echo "== Moduli nuovi di my-erp-crm: $NUOVI_AUTO"
    $RUN app $APP -i "$NUOVI_AUTO" --stop-after-init
  fi
else
  echo "== Primo avvio: creazione del database"
  : "${ADMIN_PASSWORD:?ADMIN_PASSWORD vuota in .env}"
  $RUN app $APP -i base --load-language="${ADMIN_LANG:-it_IT}" --stop-after-init
  SETUP_PHASE=azienda $RUN "${ENVVARS[@]}" app $BIN shell $CONF --no-http < configura_azienda.py
  $RUN app $APP -i "${APPS:-crm,sale_management,contacts,calendar,account,my_erp_crm_currency_ecb,my_erp_crm_iva}" --stop-after-init
  SETUP_PHASE=finanza $RUN "${ENVVARS[@]}" app $BIN shell $CONF --no-http < configura_azienda.py
fi

# shellcheck disable=SC2086
$COMPOSE up -d --no-deps $SERVIZI
if [ "${HTTPS_LOCALE:-1}" = 0 ]; then $COMPOSE stop caddy >/dev/null 2>&1 || true; fi
echo "== Pronto: https://${DOMAIN%%,*}"
