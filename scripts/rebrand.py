#!/usr/bin/env python3
"""Sostituisce il nome "Odoo" con "my-erp-crm" nei testi del codice e delle traduzioni.

Due modi d'uso:

    python3 scripts/rebrand.py --tree          # applica il cambio a tutto il repository
    git diff A B | python3 scripts/rebrand.py --patch | git apply   # adatta una patch

La sostituzione lavora riga per riga con le stesse regole in entrambi i casi: per questo
una patch del progetto originale, passata da --patch, si applica pulita sul nostro codice
(vedi scripts/aggiorna-da-odoo.sh).

Non vengono toccati:
- note di copyright e licenza ("Odoo S.A.", commenti "Part of Odoo...");
- indirizzi web (odoo.com, odoo.sh) e nomi tecnici (OdooBot, X-Odoo-..., @odoo/...);
- i moduli che dialogano con servizi esterni o con le autorità fiscali (vedi SKIP_MODULES),
  tranne il loro __manifest__.py (descrizione mostrata nell'elenco delle applicazioni);
- i nostri moduli my_erp_crm_* e le librerie di terze parti (static/lib).
"""
import argparse
import os
import re
import sys

BRAND = "my-erp-crm"
ROOTS = ("addons", "odoo/addons")
EXTENSIONS = (".py", ".js", ".xml", ".html", ".po", ".pot")

PATTERN = re.compile(
    r"(?<![\w\-./@])Odoo"            # parola intera, non dentro X-Odoo, odoo.Odoo, @Odoo
    r"(?![\w\-]"                     # non OdooBot, Odoo-xxx
    r"|\.(?:com|sh)\b"               # non odoo.com / odoo.sh
    r"|\s+S\.?\s?A\b"                # non "Odoo S.A." (copyright)
    r"|\s+Unicode\s+Support)"         # nome tecnico del font "Odoo Unicode Support Noto"
)

SKIP_MODULES = re.compile(
    r"^(?:my_erp_crm.*"
    r"|l10n_.*|payment_.*|.*_edi(?:_.*)?|account_edi.*|account_peppol.*|.*peppol.*"
    r"|iot.*|pos_iot.*|iap.*|.*_iap|mail_plugin|crm_mail_plugin|google_.*|microsoft_.*"
    r"|spreadsheet.*|cloud_storage.*|base_geolocalize|snailmail.*|sms.*|partner_autocomplete)$"
)


def module_of(path):
    """Restituisce (nome modulo, percorso interno al modulo) oppure (None, None)."""
    path = path.replace(os.sep, "/")
    for root in sorted(ROOTS, key=len, reverse=True):
        if path.startswith(root + "/"):
            rest = path[len(root) + 1:]
            module, _, inner = rest.partition("/")
            return module, inner
    return None, None


def file_in_scope(path):
    if not path.endswith(EXTENSIONS):
        return False
    module, inner = module_of(path)
    if not module or not inner or "/static/lib/" in "/" + inner:
        return False
    if SKIP_MODULES.match(module):
        return inner == "__manifest__.py"
    return True


def transform_line(path, line):
    """Applica il cambio a una singola riga del file `path` (riga senza prefisso di patch)."""
    if "Odoo" not in line:
        return line
    stripped = line.lstrip()
    if path.endswith((".po", ".pot")):
        if not stripped.startswith(("msgid", "msgstr", '"')):
            return line
    elif path.endswith(".py"):
        if stripped.startswith("#"):
            return line
    elif path.endswith(".js"):
        if stripped.startswith(("//", "*", "/*")):
            return line
    elif path.endswith((".xml", ".html")):
        if "<!--" in line:
            return line
    return PATTERN.sub(BRAND, line)


def run_tree(base):
    changed_files = replaced = 0
    for root in ROOTS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(base, root)):
            dirnames[:] = [d for d in dirnames if d != "lib"]
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, base)
                if not file_in_scope(rel):
                    continue
                try:
                    with open(full, encoding="utf-8", newline="") as f:
                        text = f.read()
                except UnicodeDecodeError:
                    continue
                if "Odoo" not in text:
                    continue
                lines = text.splitlines(keepends=True)
                new_lines = [transform_line(rel, l) for l in lines]
                if new_lines != lines:
                    n = sum(len(PATTERN.findall(a)) - len(PATTERN.findall(b))
                            for a, b in zip(lines, new_lines))
                    with open(full, "w", encoding="utf-8", newline="") as f:
                        f.write("".join(new_lines))
                    changed_files += 1
                    replaced += n
    print(f"{replaced} sostituzioni in {changed_files} file", file=sys.stderr)


def run_patch(stream_in, stream_out):
    path = None
    in_hunk = False
    for raw in stream_in:
        line = raw
        if raw.startswith("diff --git "):
            in_hunk = False
            parts = raw.rstrip("\n").split(" b/", 1)
            path = parts[1] if len(parts) == 2 else None
        elif raw.startswith("+++ "):
            target = raw[4:].rstrip("\n")
            if target.startswith("b/"):
                path = target[2:]
        elif raw.startswith("@@"):
            in_hunk = True
        elif raw.startswith("GIT binary patch"):
            in_hunk = False
        elif in_hunk and path and raw[:1] in (" ", "+", "-") and file_in_scope(path):
            line = raw[0] + transform_line(path, raw[1:])
        stream_out.write(line)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tree", action="store_true", help="modifica i file del repository")
    group.add_argument("--patch", action="store_true", help="adatta una patch letta da stdin")
    args = parser.parse_args()
    if args.tree:
        run_tree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    else:
        sys.stdin.reconfigure(encoding="utf-8", errors="surrogateescape", newline="")
        sys.stdout.reconfigure(encoding="utf-8", errors="surrogateescape", newline="")
        run_patch(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
