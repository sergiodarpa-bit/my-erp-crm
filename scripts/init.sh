#!/usr/bin/env bash
# Primo avvio in locale: costruisce l'immagine, crea il database "my-erp-crm",
# configura l'azienda (paese, IVA, listino pubblico) e installa le applicazioni.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Manca il file .env: copia .env.example in .env e compilalo." >&2
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

APPS="${APPS:-crm,sale_management,contacts,calendar,account,my_erp_crm_currency_ecb,my_erp_crm_iva}"
BIN="/opt/my-erp-crm/my-erp-crm"
CONF="--config=/etc/my-erp-crm/my-erp-crm.conf"
APP="$BIN $CONF"
ENVVARS=(-e SETUP_PHASE -e ADMIN_PASSWORD -e ADMIN_LANG -e PUBLIC_CURRENCY
         -e COMPANY_NAME -e COMPANY_COUNTRY -e COMPANY_VAT -e COMPANY_REGISTRY -e COMPANY_STREET
         -e COMPANY_CITY -e COMPANY_ZIP -e COMPANY_EMAIL -e COMPANY_PHONE -e COMPANY_WEBSITE
         -e OSS_REGISTERED -e SELF_BILLING_FLAG_FIELD
         -e COMPANY_STREET2 -e COMPANY_IBAN -e COMPANY_BANK_NAME -e COMPANY_BIC -e COMPANY_REPORT_FOOTER
         -e INVOICE_JOURNAL_CODE)

docker compose build app
docker compose up -d db
docker compose run --rm app $APP -i base --load-language="${ADMIN_LANG:-it_IT}" --stop-after-init
SETUP_PHASE=azienda docker compose run --rm -T "${ENVVARS[@]}" app $BIN shell $CONF --no-http < deploy/configura_azienda.py
docker compose run --rm app $APP -i "$APPS" --stop-after-init
SETUP_PHASE=finanza docker compose run --rm -T "${ENVVARS[@]}" app $BIN shell $CONF --no-http < deploy/configura_azienda.py
docker compose up -d app

echo "Pronto: http://localhost:${HTTP_PORT:-8069}  (utente: admin, password: quella di ADMIN_PASSWORD o admin)"
