#!/usr/bin/env bash
# Primo avvio: costruisce l'immagine, crea il database "my-erp-crm" in italiano
# con CRM, Vendite, Contatti e Calendario, poi avvia il servizio.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Manca il file .env: copia .env.example in .env e imposta la password." >&2
  exit 1
fi
set -a; . ./.env; set +a

APPS="${APPS:-crm,sale_management,contacts,calendar}"

docker compose build app
docker compose up -d db
docker compose run --rm app /opt/my-erp-crm/my-erp-crm --config=/etc/my-erp-crm/my-erp-crm.conf \
  -i "$APPS" --load-language=it_IT --stop-after-init
echo "env.ref('base.user_admin').lang = 'it_IT'; env.cr.commit()" | \
  docker compose run --rm -T app /opt/my-erp-crm/my-erp-crm shell --config=/etc/my-erp-crm/my-erp-crm.conf --no-http
docker compose up -d app

echo "Pronto: http://localhost:${HTTP_PORT:-8069}  (utente: admin / password: admin, da cambiare subito)"
