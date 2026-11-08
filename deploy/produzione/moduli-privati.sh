#!/usr/bin/env bash
# Moduli aggiuntivi da un repository privato, letto con una chiave di sola lettura
# (deploy key) che nasce qui e non esce mai dal server.
#
# Variabili in .env: MODULI_REPO (indirizzo SSH, es. git@github.com:org/repo.git),
# MODULI_RAMO, MODULI_CARTELLA (la cartella dei moduli nel repository), MODULI (quelli da
# installare, separati da virgole), facoltativa SELF_BILLING_FLAG_FIELD (campo booleano
# della posizione fiscale che accende un documento di autofatturazione).
#
# Primo giro: crea la chiave, ne stampa la parte PUBBLICA e si ferma: va aggiunta al
# repository come deploy key di sola lettura. Giri seguenti: scarica il ramo, fa un backup,
# installa i moduli nuovi e aggiorna quelli già presenti, riavvia l'applicazione.
# Ripetibile. Non stampa password né chiavi private.
set -euo pipefail
cd "$(dirname "$0")"
QUI="$PWD"

valore() { sed -n "s/^$1=//p" .env | tail -n 1; }
REPO="$(valore MODULI_REPO)"; RAMO="$(valore MODULI_RAMO)"; CARTELLA="$(valore MODULI_CARTELLA)"
MODULI="$(valore MODULI | tr -d ' ')"; FLAG="$(valore SELF_BILLING_FLAG_FIELD)"
[ -n "$REPO" ] && [ -n "$RAMO" ] && [ -n "$MODULI" ] \
  || { echo "In .env servono MODULI_REPO, MODULI_RAMO e MODULI."; exit 1; }

COMPOSE="docker compose"
BIN="/opt/my-erp-crm/my-erp-crm"
CONF="--config=/etc/my-erp-crm/my-erp-crm.conf"
CHIAVI="$QUI/.chiave-moduli"
SORGENTE="$QUI/sorgente-moduli"

if [[ "$REPO" == git@* || "$REPO" == ssh://* ]]; then
  echo "== Chiave di sola lettura"
  mkdir -p "$CHIAVI" && chmod 700 "$CHIAVI"
  if [ ! -f "$CHIAVI/id_ed25519" ]; then
    ssh-keygen -q -t ed25519 -N "" -C "my-erp-crm $(hostname -s) sola lettura" -f "$CHIAVI/id_ed25519"
  fi
  chmod 600 "$CHIAVI/id_ed25519"
  # L'impronta della chiave di GitHub è quella pubblicata da GitHub: niente fiducia al primo colpo.
  if [[ "$REPO" == git@github.com:* ]] && [ ! -s "$CHIAVI/known_hosts" ]; then
    ssh-keyscan -t ed25519 github.com 2>/dev/null > "$CHIAVI/known_hosts.nuovo"
    IMPRONTA="$(ssh-keygen -lf "$CHIAVI/known_hosts.nuovo" | awk '{print $2}')"
    [ "$IMPRONTA" = "SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU" ] \
      || { echo "STOP: l'impronta di github.com ($IMPRONTA) non è quella pubblicata da GitHub."; exit 1; }
    mv "$CHIAVI/known_hosts.nuovo" "$CHIAVI/known_hosts"
  fi
  export GIT_SSH_COMMAND="ssh -i $CHIAVI/id_ed25519 -o IdentitiesOnly=yes -o UserKnownHostsFile=$CHIAVI/known_hosts -o StrictHostKeyChecking=yes"
fi

echo "== Repository $REPO, ramo $RAMO"
set +e
if [ -d "$SORGENTE/.git" ]; then
  git -C "$SORGENTE" fetch -q --depth 1 origin "$RAMO" 2> "$QUI/.git-errore" && git -C "$SORGENTE" reset -q --hard FETCH_HEAD
else
  git clone -q --depth 1 --branch "$RAMO" "$REPO" "$SORGENTE" 2> "$QUI/.git-errore"
fi
ESITO=$?
set -e
if [ "$ESITO" -ne 0 ]; then
  if grep -qiE "permission denied|could not read from remote|repository not found" "$QUI/.git-errore"; then
    echo "STOP: il repository non accetta ancora la chiave. Aggiungila come deploy key di SOLA LETTURA"
    echo "(GitHub → repository → Settings → Deploy keys → Add deploy key, senza «Allow write access»):"
    echo
    cat "$CHIAVI/id_ed25519.pub"
    echo
    echo "Poi rilancia la stessa riga."
  else
    echo "STOP: git non è riuscito:"; tail -5 "$QUI/.git-errore"
  fi
  rm -f "$QUI/.git-errore"; exit 3
fi
rm -f "$QUI/.git-errore"
echo "scaricato: $(git -C "$SORGENTE" log -1 --format='%h %ci')"

DESTINO="./sorgente-moduli${CARTELLA:+/$CARTELLA}"
[ -d "$QUI/$DESTINO" ] || { echo "STOP: nel repository non c'è la cartella «$CARTELLA»."; exit 1; }
if grep -q '^EXTRA_ADDONS=' .env; then sed -i "s|^EXTRA_ADDONS=.*|EXTRA_ADDONS=$DESTINO|" .env; else echo "EXTRA_ADDONS=$DESTINO" >> .env; fi

echo "== Configurazione con la cartella dei moduli aggiuntivi"
# Dal modello, con sostituzioni della shell: la password non passa per la riga di comando.
MODELLO="$(< my-erp-crm.conf.template)"
MASTER="$(valore MASTER_PASSWORD)"
[ -n "$MASTER" ] || { echo "STOP: MASTER_PASSWORD vuota in .env."; exit 1; }
printf '%s\n' "${MODELLO//__MASTER_PASSWORD__/$MASTER}" > my-erp-crm.conf.nuovo
chmod 644 my-erp-crm.conf.nuovo && mv my-erp-crm.conf.nuovo my-erp-crm.conf
unset MASTER MODELLO
grep -q "/mnt/extra-addons" my-erp-crm.conf || { echo "STOP: la configurazione non ha la cartella dei moduli: scarica il modello nuovo."; exit 1; }

echo "== Backup prima di toccare i moduli"
./backup.sh

echo "== Moduli: $MODULI"
UTENTE="$(valore POSTGRES_USER)"; UTENTE="${UTENTE:-myerp}"
NOMI="'$(echo "$MODULI" | sed "s/,/','/g")'"
PRESENTI="$($COMPOSE exec -T db psql -U "$UTENTE" -d my-erp-crm -tAc "SELECT string_agg(name, ',') FROM ir_module_module WHERE state = 'installed' AND name IN ($NOMI)")"
NUOVI=""
for m in ${MODULI//,/ }; do
  case ",$PRESENTI," in *",$m,"*) ;; *) NUOVI="${NUOVI:+$NUOVI,}$m" ;; esac
done
echo "da installare: ${NUOVI:-nessuno} · da aggiornare: ${PRESENTI:-nessuno}"
$COMPOSE stop app >/dev/null
ARGOMENTI=()
[ -n "$NUOVI" ] && ARGOMENTI+=(-i "$NUOVI")
[ -n "$PRESENTI" ] && ARGOMENTI+=(-u "$PRESENTI")
$COMPOSE run --rm -T app "$BIN" "$CONF" "${ARGOMENTI[@]}" --stop-after-init > "$QUI/moduli.log" 2>&1 \
  || { echo "STOP: installazione dei moduli fallita. Ultime righe:"; tail -20 "$QUI/moduli.log"; $COMPOSE up -d --no-deps app >/dev/null; exit 1; }

# Dopo i moduli: gestionale chiuso (solo inviti, niente tour) e, se indicato, il campo che accende
# il documento di autofatturazione sulle posizioni fiscali delle imprese UE e svizzere.
$COMPOSE run --rm -T -e FLAG="$FLAG" app "$BIN" shell "$CONF" --no-http 2>/dev/null <<'PY' | grep -E '^(KIT|IMPOSTAZIONI)' || true
import os
env["ir.config_parameter"].sudo().set_str("auth_signup.invitation_scope", "b2b")
interni = env["res.users"].search([("share", "=", False)])
if "tour_enabled" in interni._fields:
    interni.write({"tour_enabled": False})
print("IMPOSTAZIONI: registrazione solo su invito, tour guidato spento")
f = os.environ.get("FLAG", "")
F = env["account.fiscal.position"].with_context(lang="en_US", active_test=False)
if f and f in F._fields:
    pos = F.search([("name", "in", ["EU businesses - reverse charge", "Swiss businesses"])])
    pos.write({f: True})
    print("KIT autofattura acceso su:", ", ".join(pos.mapped("name")))
elif f:
    print("KIT: il campo", f, "non esiste: nessuna posizione toccata")
env.cr.commit()
PY

$COMPOSE up -d --no-deps app >/dev/null
echo "installati: $($COMPOSE exec -T db psql -U "$UTENTE" -d my-erp-crm -tAc "SELECT string_agg(name || ' ' || coalesce(latest_version, ''), ', ' ORDER BY name) FROM ir_module_module WHERE state = 'installed' AND name IN ($NOMI)")"
echo "=== FATTO ==="
