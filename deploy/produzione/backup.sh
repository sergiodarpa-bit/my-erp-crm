#!/usr/bin/env bash
# Backup operativo: database (pg_dump, formato custom) e allegati (filestore), con rotazione.
# Da eseguire sul server, nella cartella di installazione; lo lancia ogni ora il timer
# my-erp-crm-backup.timer. Ogni backup è una cartella backups/orari/AAAAMMGG-HHMMSS con:
#   database.dump   (si ripristina con pg_restore)
#   filestore.tgz   (allegati, loghi e PDF salvati)
# Tiene le ultime TENERE cartelle (48 = due giorni). Non legge né stampa password.
set -euo pipefail
cd "$(dirname "$0")"

TENERE="${TENERE:-48}"
COMPOSE="docker compose"
UTENTE="$(sed -n 's/^POSTGRES_USER=//p' .env)"
UTENTE="${UTENTE:-myerp}"

mkdir -p backups/orari
chmod 700 backups backups/orari
ORA="$(date +%Y%m%d-%H%M%S)"
PARZIALE="backups/orari/.in-corso-$ORA"
# Un backup interrotto non deve sembrare buono: la cartella prende il nome vero solo alla fine.
trap 'rm -rf -- "$PARZIALE"' EXIT
mkdir "$PARZIALE"

$COMPOSE exec -T db pg_dump -U "$UTENTE" -Fc my-erp-crm > "$PARZIALE/database.dump"
$COMPOSE exec -T app tar -C /var/lib/my-erp-crm -czf - filestore > "$PARZIALE/filestore.tgz"
# Un dump vuoto o troncato non passa: pg_restore deve saperne leggere l'indice.
$COMPOSE exec -T db pg_restore --list < "$PARZIALE/database.dump" > /dev/null

mv "$PARZIALE" "backups/orari/$ORA"
trap - EXIT

# Rotazione senza pipe: l'elenco in un array, si tolgono le più vecchie.
shopt -s nullglob
TUTTI=(backups/orari/2*)
if (( ${#TUTTI[@]} > TENERE )); then
  rm -rf -- "${TUTTI[@]:0:${#TUTTI[@]}-TENERE}"
fi
echo "Backup pronto: backups/orari/$ORA ($(du -sh "backups/orari/$ORA" | cut -f1)); copie tenute: $(( ${#TUTTI[@]} > TENERE ? TENERE : ${#TUTTI[@]} ))"
