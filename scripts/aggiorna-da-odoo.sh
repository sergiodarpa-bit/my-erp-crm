#!/usr/bin/env bash
# Porta in my-erp-crm le correzioni pubblicate da Odoo Community sul ramo indicato
# (predefinito 19.0), partendo dalla versione scritta in UPSTREAM_COMMIT.
set -euo pipefail
cd "$(dirname "$0")/.."

UPSTREAM_URL="https://github.com/odoo/odoo.git"
BRANCH="${1:-19.0}"
BASE="$(tr -d '[:space:]' < UPSTREAM_COMMIT)"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Ci sono modifiche non salvate: fai prima un commit." >&2
  exit 1
fi

echo "Scarico la versione di partenza ${BASE:0:12} e l'ultima del ramo $BRANCH..."
git fetch --quiet --no-tags --depth 1 "$UPSTREAM_URL" "$BASE"
git fetch --quiet --no-tags --depth 1 "$UPSTREAM_URL" "$BRANCH"
NEW="$(git rev-parse FETCH_HEAD)"

if [ "$NEW" = "$BASE" ]; then
  echo "Già aggiornato: nessuna novità sul ramo $BRANCH."
  exit 0
fi

# File che nel nostro repository sono stati riscritti o rimossi: non li tocchiamo.
EXCLUDE=(':!.github' ':!README.md' ':!CONTRIBUTING.md' ':!SECURITY.md')

if ! git diff --binary "$BASE" "$NEW" -- . "${EXCLUDE[@]}" | git apply --3way --index; then
  echo "Alcune modifiche vanno in conflitto con le nostre: risolvi i file segnalati," >&2
  echo "poi aggiorna UPSTREAM_COMMIT con $NEW e fai il commit." >&2
  exit 1
fi

echo "$NEW" > UPSTREAM_COMMIT
git add UPSTREAM_COMMIT
git commit --quiet -m "Aggiorna dal sorgente Odoo Community $BRANCH (${NEW:0:12})"
echo "Aggiornato a ${NEW:0:12}. Riavvia e aggiorna i moduli: docker compose build app && docker compose up -d"
