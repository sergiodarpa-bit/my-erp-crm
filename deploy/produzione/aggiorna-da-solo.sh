#!/usr/bin/env bash
# Aggiornamento automatico dal server, senza porte in entrata: è il server che chiede a
# ghcr.io se c'è una versione nuova di main. Gira come root dal timer systemd
# my-erp-crm-aggiorna.timer (ogni 15 minuti, ai minuti 07, 22, 37 e 52: lontano dal backup
# delle ore piene).
#
#   ./aggiorna-da-solo.sh            controlla e, se c'è una versione nuova, aggiorna
#   ./aggiorna-da-solo.sh attiva     installa e accende il timer (AGGIORNA_DA_SOLO=1 in .env)
#   ./aggiorna-da-solo.sh spegni     spegne il timer (AGGIORNA_DA_SOLO=0 in .env)
#   ./aggiorna-da-solo.sh stato      versione in uso, prossimo controllo, ultimi aggiornamenti
#
# Il controllo:
#   1. scarica ghcr.io/sergiodarpa-bit/my-erp-crm:20.0 (l'ultima versione di main) e legge il
#      commit da cui è costruita (etichetta org.opencontainers.image.revision);
#   2. se in .env IMAGE è già …:<quel commit>, non fa niente;
#   3. altrimenti prende dall'immagine nuova gli script di produzione (stessa versione del
#      programma), scrive in .env IMAGE=…:<commit> e lancia aggiorna.sh, che fa il backup
#      del database e aggiorna i moduli;
#   4. se aggiorna.sh fallisce rimette in .env la versione di prima, riaccende l'applicazione
#      con quella e non riprova la versione fallita finché non ne esce una nuova (o finché
#      non si cancella .aggiornamento-fallito).
# Ogni aggiornamento lascia una riga in aggiornamenti.log; il dettaglio è in
# journalctl -u my-erp-crm-aggiorna. Con AGGIORNA_DA_SOLO diverso da 1 non fa niente: serve
# per fissare a mano una versione precedente senza che il timer la cambi.
set -euo pipefail

DIR="${MYERP_DIR:-/opt/my-erp-crm}"
REPO="${MYERP_REPO:-ghcr.io/sergiodarpa-bit/my-erp-crm}"
UNITA="${MYERP_UNITA:-/etc/systemd/system}"
LOCK="${MYERP_LOCK:-/run/my-erp-crm-aggiorna.lock}"
CANALE="$REPO:20.0"
# File di produzione presi dall'immagine nuova: gli stessi che copiava la pubblicazione da
# GitHub, più questo script. backup.sh, prosegui.sh e moduli-privati.sh si aggiornano a mano.
FILE_644="docker-compose.yml Caddyfile my-erp-crm.conf.template .env.example configura_azienda.py my-erp-crm-aggiorna.service my-erp-crm-aggiorna.timer"
FILE_755="aggiorna.sh costruisci.sh aggiorna-da-solo.sh"

cd "$DIR"
[ -f .env ] || { echo "Manca $DIR/.env: il primo avvio si prepara a mano (README)."; exit 1; }

valore() { sed -n "s/^$1=//p" .env | tail -n 1; }
scrivi() {  # scrivi CHIAVE VALORE: sostituisce la riga in .env, o la aggiunge
  if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else printf '%s=%s\n' "$1" "$2" >> .env; fi
}
registro() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M')" "$*" | tee -a aggiornamenti.log; }

prendi_file() {  # prendi_file IMMAGINE: copia in $DIR i file di produzione di quell'immagine
  local tmp cid f
  tmp="$(mktemp -d)"
  cid="$(docker create "$1")"
  docker cp "$cid:/opt/my-erp-crm/deploy/produzione/." "$tmp/" >/dev/null
  docker cp "$cid:/opt/my-erp-crm/deploy/configura_azienda.py" "$tmp/" >/dev/null
  docker rm "$cid" >/dev/null
  # install sostituisce il file (nuovo inode): anche questo script, mentre gira, si
  # aggiorna senza effetti sulla copia già in esecuzione.
  for f in $FILE_644; do [ -f "$tmp/$f" ] && install -m 644 "$tmp/$f" "$DIR/$f"; done
  for f in $FILE_755; do [ -f "$tmp/$f" ] && install -m 755 "$tmp/$f" "$DIR/$f"; done
  rm -rf "$tmp"
}

pulizia() {  # tiene la versione in uso e le due precedenti, per tornare indietro
  docker images --format '{{.Repository}}:{{.Tag}}' "$REPO" | grep -E ":[0-9a-f]{40}$" \
    | grep -vxF "$1" | tail -n +3 | xargs -r docker rmi >/dev/null 2>&1 || true
  docker image prune -f >/dev/null 2>&1 || true
}

controlla() {
  exec 9> "$LOCK"
  flock -n 9 || { echo "Un altro controllo è in corso."; return 0; }
  if [ "$(valore AGGIORNA_DA_SOLO)" != 1 ]; then
    echo "AGGIORNA_DA_SOLO non è 1 in .env: non faccio niente."; return 0
  fi
  local attuale commit nuova
  attuale="$(valore IMAGE)"
  case "$attuale" in
    "" | */*) ;;
    *) echo "IMAGE=$attuale è costruita su questo server (costruisci.sh): non aggiorno da ghcr.io."; return 0 ;;
  esac
  # Non mentre girano il backup o un altro script di manutenzione: si riprova al giro dopo.
  if systemctl is-active --quiet my-erp-crm-backup.service \
     || pgrep -f "(aggiorna|moduli-privati|prosegui|backup)\.sh" >/dev/null; then
    echo "Backup o manutenzione in corso: riprovo al prossimo controllo."; return 0
  fi

  docker pull -q "$CANALE" >/dev/null || { echo "ghcr.io non risponde: nessuna modifica."; return 1; }
  commit="$(docker image inspect -f '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$CANALE")"
  if ! [[ "$commit" =~ ^[0-9a-f]{40}$ ]]; then
    echo "L'immagine $CANALE non dice da quale commit viene: aggiornamento solo a mano."; return 0
  fi
  nuova="$REPO:$commit"
  if [ "$attuale" = "$nuova" ]; then echo "Già all'ultima versione (${commit:0:8})."; return 0; fi
  if [ "$(cat .aggiornamento-fallito 2>/dev/null)" = "$commit" ]; then
    echo "La versione ${commit:0:8} è già fallita: aspetto la prossima (o cancella .aggiornamento-fallito)."; return 0
  fi
  # Prima di toccare qualcosa, l'immagine esatta deve essere scaricabile.
  docker pull -q "$nuova" >/dev/null || { echo "Non riesco a scaricare $nuova: nessuna modifica."; return 1; }

  # Con IMAGE vuota la versione di prima era :20.0, che ora punta già all'immagine nuova:
  # in quel caso, dopo un errore, tornare indietro va fatto a mano (backup in backups/).
  local prima="${attuale:-$CANALE}"
  echo "== Aggiornamento: $prima → $nuova"
  prendi_file "$nuova"
  scrivi IMAGE "$nuova"
  if ./aggiorna.sh; then
    rm -f .aggiornamento-fallito
    registro "OK ${prima##*:} -> $commit"
    pulizia "$nuova"
  else
    echo "$commit" > .aggiornamento-fallito
    scrivi IMAGE "$attuale"
    docker compose up -d --no-deps app || true
    registro "ERRORE con $commit: rimessa la versione ${prima##*:} (dettagli: journalctl -u my-erp-crm-aggiorna; backup in backups/)"
    return 1
  fi
}

attiva() {
  install -m 644 my-erp-crm-aggiorna.service my-erp-crm-aggiorna.timer "$UNITA/"
  scrivi AGGIORNA_DA_SOLO 1
  systemctl daemon-reload
  systemctl enable --now my-erp-crm-aggiorna.timer
  echo "Aggiornamento automatico acceso. Primo controllo adesso:"
  controlla
}

spegni() {
  scrivi AGGIORNA_DA_SOLO 0
  systemctl disable --now my-erp-crm-aggiorna.timer >/dev/null 2>&1 || true
  echo "Aggiornamento automatico spento. Per riaccenderlo: ./aggiorna-da-solo.sh attiva"
}

stato() {
  echo "Versione in uso: $(valore IMAGE)"
  echo "AGGIORNA_DA_SOLO: $(valore AGGIORNA_DA_SOLO)"
  systemctl list-timers my-erp-crm-aggiorna.timer --no-pager 2>/dev/null || true
  [ -f .aggiornamento-fallito ] && echo "Versione fallita, non riprovata: $(cat .aggiornamento-fallito)"
  echo "Ultimi aggiornamenti:"; tail -n 5 aggiornamenti.log 2>/dev/null || echo "  nessuno"
}

case "${1:-controlla}" in
  controlla) controlla ;;
  attiva) attiva ;;
  spegni) spegni ;;
  stato) stato ;;
  *) echo "uso: $0 [controlla|attiva|spegni|stato]"; exit 2 ;;
esac
