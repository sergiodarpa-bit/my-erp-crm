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
sed "s|__MASTER_PASSWORD__|${MASTER_PASSWORD}|" my-erp-crm.conf.template > my-erp-crm.conf
chmod 644 my-erp-crm.conf

COMPOSE="docker compose"
RUN="$COMPOSE run --rm -T"
BIN="/opt/my-erp-crm/my-erp-crm"
CONF="--config=/etc/my-erp-crm/my-erp-crm.conf"
APP="$BIN $CONF"

$COMPOSE pull --quiet
$COMPOSE up -d db

db_exists() {
  $COMPOSE exec -T db psql -U "${POSTGRES_USER:-myerp}" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname = 'my-erp-crm'" | grep -q 1
}

for i in $(seq 1 30); do
  $COMPOSE exec -T db pg_isready -U "${POSTGRES_USER:-myerp}" >/dev/null 2>&1 && break
  sleep 2
done

ENVVARS=(-e SETUP_PHASE -e ADMIN_PASSWORD -e ADMIN_LANG -e PUBLIC_CURRENCY
         -e COMPANY_NAME -e COMPANY_COUNTRY -e COMPANY_VAT -e COMPANY_REGISTRY -e COMPANY_STREET
         -e COMPANY_CITY -e COMPANY_ZIP -e COMPANY_EMAIL -e COMPANY_PHONE -e COMPANY_WEBSITE
         -e OSS_REGISTERED -e SELF_BILLING_FLAG_FIELD)

if db_exists; then
  echo "== Backup del database"
  mkdir -p backups
  $COMPOSE exec -T db pg_dump -U "${POSTGRES_USER:-myerp}" -Fc my-erp-crm > "backups/my-erp-crm-$(date +%Y%m%d-%H%M%S).dump"
  ls -1t backups/*.dump | tail -n +15 | xargs -r rm --
  echo "== Aggiornamento dei moduli"
  $COMPOSE stop app || true
  $RUN app $APP -u all --stop-after-init
else
  echo "== Primo avvio: creazione del database"
  : "${ADMIN_PASSWORD:?ADMIN_PASSWORD vuota in .env}"
  $RUN app $APP -i base --load-language="${ADMIN_LANG:-it_IT}" --stop-after-init
  SETUP_PHASE=azienda $RUN "${ENVVARS[@]}" app $BIN shell $CONF --no-http < configura_azienda.py
  $RUN app $APP -i "${APPS:-crm,sale_management,contacts,calendar,account,my_erp_crm_currency_ecb,my_erp_crm_iva}" --stop-after-init
  SETUP_PHASE=finanza $RUN "${ENVVARS[@]}" app $BIN shell $CONF --no-http < configura_azienda.py
fi

$COMPOSE up -d --remove-orphans
echo "== Pronto: https://${DOMAIN}"
