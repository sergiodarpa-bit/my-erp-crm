#!/usr/bin/env bash
# Dopo la prima installazione: attiva il backup orario e accende l'HTTPS solo quando il
# dominio (DOMAIN in .env) punta davvero a questo server. Ripetibile: si lancia quante
# volte serve e fa solo ciò che manca. Non legge né stampa password.
#
# Finché il dominio punta altrove Caddy resta spento: i tentativi falliti di avere il
# certificato farebbero scattare i limiti di Let's Encrypt.
# Controlla anche che nel DNS non resti nessun record verso servizi Odoo (odoo.com).
set -uo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo "Manca .env: prima l'installazione."; exit 1; }
DOMINIO="$(sed -n 's/^DOMAIN=//p' .env)"
[ -n "$DOMINIO" ] || { echo "DOMAIN vuoto in .env."; exit 1; }
ZONA="${DOMINIO#*.}"
POSTA="$(sed -n 's/^COMPANY_EMAIL=.*@//p' .env)"
URL="https://$DOMINIO"

echo "== Servizi: $(docker compose ps --format '{{.Service}}={{.State}}' | tr '\n' ' ')"

echo "== Backup ogni ora"
set -e
cp my-erp-crm-backup.service my-erp-crm-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now my-erp-crm-backup.timer >/dev/null
./backup.sh
echo "prossimo backup: $(systemctl show my-erp-crm-backup.timer -p NextElapseUSecRealtime --value)"
set +e

D() { dig +short +time=3 +tries=2 "$@" @1.1.1.1; }

echo "== Odoo nel DNS"
RESTI=""
for voce in "CNAME $DOMINIO" "MX $DOMINIO" "TXT $DOMINIO" \
            "TXT $ZONA" "MX $ZONA" "TXT _dmarc.$ZONA" "CNAME odoo._domainkey.$ZONA" \
            ${POSTA:+"TXT $POSTA" "MX $POSTA" "TXT _dmarc.$POSTA" "CNAME odoo._domainkey.$POSTA"}; do
  # shellcheck disable=SC2086
  RISPOSTA="$(D $voce | tr '\n' ' ')"
  case "$RISPOSTA" in
    *[Oo][Dd][Oo][Oo]*) RESTI="${RESTI}  - ${voce}: ${RISPOSTA}"$'\n' ;;
  esac
done
if [ -n "$RESTI" ]; then
  echo "Record che citano ancora Odoo (da togliere o correggere in Cloudflare):"
  printf '%s' "$RESTI"
else
  echo "nessun record cita Odoo"
fi

echo "== HTTPS su $DOMINIO"
TOK=$(curl -sf -m 3 -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')
IPPUB=$(printf 'X-aws-ec2-metadata-token: %s\n' "$TOK" | curl -sf -m 3 -H @- http://169.254.169.254/latest/meta-data/public-ipv4)
[ -n "$IPPUB" ] || IPPUB=$(curl -sf -m 5 https://checkip.amazonaws.com)
ORA_A=$(D A "$DOMINIO" | tail -1)
echo "IP di questo server: ${IPPUB:-?} · $DOMINIO punta a: ${ORA_A:-?}"

if [ -n "$ORA_A" ] && [ "$ORA_A" = "$IPPUB" ]; then
  docker compose up -d --no-deps caddy
  CODICE=000
  for i in $(seq 1 24); do
    CODICE=$(curl -s -o /dev/null -w '%{http_code}' -m 5 "$URL/web/login")
    [ "$CODICE" = 200 ] && break
    sleep 5
  done
  echo "$URL/web/login → $CODICE"
  if [ "$CODICE" = 200 ]; then
    echo "PRONTO: apri $URL (utente admin; password: sudo grep ADMIN_PASSWORD $PWD/.env)"
  else
    echo "Non ancora 200: controlla nel gruppo di sicurezza le porte 80 e 443 aperte a 0.0.0.0/0, poi rilancia tra un minuto."
  fi
else
  docker compose stop caddy >/dev/null 2>&1
  echo "$DOMINIO non punta ancora qui: Caddy resta spento. In Cloudflare, zona $ZONA:"
  echo "  - record ${DOMINIO%%.*}: elimina il CNAME e crea un record A → ${IPPUB}, solo DNS (nuvola grigia);"
  echo "  - nessun MX e nessun TXT verso Odoo."
  echo "Poi, dopo 2-3 minuti, rilancia la stessa riga."
fi
echo "=== FATTO ==="
