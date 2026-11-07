#!/usr/bin/env bash
# Applica il marchio my-erp-crm a un sorgente di Odoo Community appena importato
# (passaggio a una versione nuova): nomi nei testi, nome del prodotto, loghi.
# Si può rieseguire: non cambia nulla se il marchio è già applicato.
set -euo pipefail
cd "$(dirname "$0")/.."

# 1. "Odoo" -> "my-erp-crm" nei testi del codice e delle traduzioni
python3 scripts/rebrand.py --tree

# 2. Nome del prodotto (odoo/release.py è fuori dal perimetro di rebrand.py)
python3 - <<'PY'
import re
p = "odoo/release.py"
s = open(p, encoding="utf-8").read()
s = s.replace("product_name = 'Odoo'", "product_name = 'my-erp-crm'")
s = s.replace("description = 'Odoo Server'", "description = 'my-erp-crm Server'")
s = s.replace("url = 'https://www.odoo.com'", "url = 'https://github.com/sergiodarpa-bit/my-erp-crm'")
s = re.sub(r"long_desc = '''Odoo is a complete ERP and CRM\. ",
           "long_desc = '''my-erp-crm is a complete ERP and CRM based on Odoo Community Edition.\n", s)
open(p, "w", encoding="utf-8").write(s)
PY

# 3. Loghi, icone e favicon
cp addons/my_erp_crm_brand/static/img/core/* addons/web/static/img/

# 4. Comando di avvio con il nostro nome
cp odoo-bin my-erp-crm && chmod +x my-erp-crm

echo "Marchio applicato."
