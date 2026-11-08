#!/usr/bin/env bash
# Costruisce sul server l'immagine my-erp-crm dal codice pubblico (in alternativa a ghcr.io).
# Uso: ./costruisci.sh [ramo]   -> immagine locale my-erp-crm:20.0 (poi IMAGE=my-erp-crm:20.0 in .env)
set -euo pipefail
cd "$(dirname "$0")"
RAMO="${1:-main}"
if [ -d sorgente/.git ]; then
  git -C sorgente fetch --depth 1 origin "$RAMO"
  git -C sorgente checkout -q -B "$RAMO" FETCH_HEAD
else
  git clone --depth 1 --branch "$RAMO" https://github.com/sergiodarpa-bit/my-erp-crm.git sorgente
fi
echo "== Costruzione dell'immagine dal commit $(git -C sorgente rev-parse --short HEAD) (qualche minuto)"
docker build -t my-erp-crm:20.0 sorgente
echo "== Pronta: my-erp-crm:20.0"
