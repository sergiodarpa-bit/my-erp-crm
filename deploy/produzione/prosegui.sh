#!/usr/bin/env bash
# Dopo la prima installazione: attiva il backup orario e accende l'HTTPS solo quando il
# dominio (DOMAIN in .env) punta davvero a questo server. Ripetibile: si lancia quante
# volte serve e fa solo ciò che manca. Non legge né stampa password.
#
# Finché il dominio punta altrove Caddy resta spento: i tentativi falliti di avere il
# certificato farebbero scattare i limiti di Let's Encrypt.
set -uo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo "Manca .env: prima l'installazione."; exit 1; }
DOMINIO="$(sed -n 's/^DOMAIN=//p' .env)"
[ -n "$DOMINIO" ] || { echo "DOMAIN vuoto in .env."; exit 1; }
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

echo "== HTTPS su $DOMINIO"
TOK=$(curl -sf -m 3 -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')
IPPUB=$(printf 'X-aws-ec2-metadata-token: %s\n' "$TOK" | curl -sf -m 3 -H @- http://169.254.169.254/latest/meta-data/public-ipv4)
[ -n "$IPPUB" ] || IPPUB=$(curl -sf -m 5 https://checkip.amazonaws.com)
D() { dig +short +time=3 +tries=2 "$@" @1.1.1.1; }
ORA_A=$(D A "$DOMINIO" | tail -1)
ORA_MX=$(D MX "$DOMINIO" | grep -E '^[0-9]+ ' | tr '\n' ' ')
ORA_TXT=$(D TXT "$DOMINIO" | grep -E '^"' | tr '\n' ' ')
# La posta del dominio com'era prima dello spostamento (la scrive anche il blocco d'installazione).
if [ ! -f dns-erp-prima.txt ] && [ -n "$ORA_MX" ]; then
  printf 'MX=%s\nTXT=%s\n' "$ORA_MX" "$ORA_TXT" > dns-erp-prima.txt
fi
MX_PRIMA="$(sed -n 's/^MX=//p' dns-erp-prima.txt 2>/dev/null)"
TXT_PRIMA="$(sed -n 's/^TXT=//p' dns-erp-prima.txt 2>/dev/null)"
# "10 eupp.example.com. " → "eupp.example.com, priorità 10" (come lo chiede il modulo di Cloudflare)
leggibile_mx() { awk '{for (i = 1; i < NF; i += 2) { h = $(i + 1); sub(/\.$/, "", h); printf "%s%s, priorità %s", (i > 1 ? " · " : ""), h, $i }}' <<< "$1"; }
TXT_PULITO="${TXT_PRIMA//\"/}"
echo "IP di questo server: ${IPPUB:-?} · $DOMINIO punta a: ${ORA_A:-?} · MX: ${ORA_MX:-nessuno}"

if [ -n "$ORA_A" ] && [ "$ORA_A" = "$IPPUB" ]; then
  if [ -z "$ORA_MX" ] && [ -n "$MX_PRIMA" ]; then
    echo "ATTENZIONE: $DOMINIO non ha più l'MX. In Cloudflare aggiungi MX ${DOMINIO%%.*} → $(leggibile_mx "$MX_PRIMA") (senza, le email a questo dominio non arrivano)."
  fi
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
  echo "$DOMINIO non punta ancora qui: Caddy resta spento. In Cloudflare:"
  echo "  - record ${DOMINIO%%.*}: da CNAME a A → ${IPPUB}, solo DNS (nuvola grigia);"
  [ -n "$MX_PRIMA" ] && echo "  - aggiungi MX ${DOMINIO%%.*} → $(leggibile_mx "$MX_PRIMA") (per le email a questo dominio);"
  case "$TXT_PULITO" in *v=spf1*) echo "  - aggiungi TXT ${DOMINIO%%.*} → ${TXT_PULITO% }";; esac
  echo "Poi, dopo 2-3 minuti, rilancia la stessa riga."
fi
echo "=== FATTO ==="
