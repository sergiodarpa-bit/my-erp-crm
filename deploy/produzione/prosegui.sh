#!/usr/bin/env bash
# Dopo la prima installazione: attiva il backup orario e accende l'HTTPS solo quando il
# dominio principale (il primo di DOMAIN in .env) punta davvero a questo server.
# DOMAIN può elencare più nomi separati da virgole: Caddy li serve tutti.
# Ripetibile: si lancia quante volte serve e fa solo ciò che manca. Non legge né stampa
# password. Finché il dominio principale punta altrove Caddy resta spento: i tentativi
# falliti di avere il certificato farebbero scattare i limiti di Let's Encrypt.
# Controlla anche che nel DNS non resti nessun record verso servizi Odoo (odoo.com).
set -uo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo "Manca .env: prima l'installazione."; exit 1; }
ELENCO="$(sed -n 's/^DOMAIN=//p' .env)"
DOMINI=()
IFS=',' read -ra PEZZI <<< "$ELENCO"
for p in "${PEZZI[@]}"; do
  p="${p//[[:space:]]/}"
  [ -n "$p" ] && DOMINI+=("$p")
done
[ "${#DOMINI[@]}" -gt 0 ] || { echo "DOMAIN vuoto in .env."; exit 1; }
PRIMO="${DOMINI[0]}"
POSTA="$(sed -n 's/^COMPANY_EMAIL=.*@//p' .env)"

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
# Le zone: quella di ogni dominio servito e quella dell'email aziendale, senza doppioni.
ZONE=()
for z in "${DOMINI[@]#*.}" ${POSTA:+"$POSTA"}; do
  case " ${ZONE[*]} " in *" $z "*) ;; *) ZONE+=("$z") ;; esac
done
VOCI=()
for d in "${DOMINI[@]}"; do VOCI+=("CNAME $d" "MX $d" "TXT $d"); done
for z in "${ZONE[@]}"; do VOCI+=("TXT $z" "MX $z" "TXT _dmarc.$z" "CNAME odoo._domainkey.$z" "TXT odoo._domainkey.$z"); done
RESTI=""
for voce in "${VOCI[@]}"; do
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
  echo "nessun record cita Odoo (zone controllate: ${ZONE[*]})"
fi

echo "== Dove puntano i domini"
TOK=$(curl -sf -m 3 -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')
IPPUB=$(printf 'X-aws-ec2-metadata-token: %s\n' "$TOK" | curl -sf -m 3 -H @- http://169.254.169.254/latest/meta-data/public-ipv4)
[ -n "$IPPUB" ] || IPPUB=$(curl -sf -m 5 https://checkip.amazonaws.com)
echo "IP di questo server: ${IPPUB:-?}"
QUI=(); ALTROVE=()
for d in "${DOMINI[@]}"; do
  A="$(D A "$d" | tail -1)"
  if [ -n "$A" ] && [ "$A" = "$IPPUB" ]; then QUI+=("$d"); echo "  $d → qui"; else ALTROVE+=("$d"); echo "  $d → ${A:-nessun indirizzo}"; fi
done

echo "== HTTPS"
case " ${QUI[*]} " in
  *" $PRIMO "*)
    docker compose up -d --no-deps caddy
    CODICE_PRIMO=000
    for d in "${QUI[@]}"; do
      CODICE=000
      for i in $(seq 1 24); do
        CODICE=$(curl -s -o /dev/null -w '%{http_code}' -m 5 "https://$d/web/login")
        [ "$CODICE" = 200 ] && break
        sleep 5
      done
      echo "  https://$d/web/login → $CODICE"
      [ "$d" = "$PRIMO" ] && CODICE_PRIMO="$CODICE"
    done
    if [ "$CODICE_PRIMO" = 200 ]; then
      echo "PRONTO: apri https://$PRIMO (utente admin; password: sudo grep ADMIN_PASSWORD $PWD/.env)"
    else
      echo "$PRIMO non risponde ancora 200: controlla nel gruppo di sicurezza le porte 80 e 443 aperte a 0.0.0.0/0, poi rilancia tra un minuto."
    fi
    ;;
  *)
    docker compose stop caddy >/dev/null 2>&1
    echo "$PRIMO non punta ancora qui: Caddy resta spento."
    ;;
esac
if [ "${#ALTROVE[@]}" -gt 0 ]; then
  echo "In Cloudflare, per ognuno di questi: elimina il CNAME e crea un record A → ${IPPUB}, solo DNS (nuvola grigia):"
  for d in "${ALTROVE[@]}"; do echo "  - $d"; done
  echo "Nessun MX e nessun TXT verso Odoo. Poi, dopo 2-3 minuti, rilancia la stessa riga."
fi
echo "=== FATTO ==="
