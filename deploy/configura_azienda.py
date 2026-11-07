# Configurazione dell'azienda che vende, eseguita dentro la shell di my-erp-crm:
#
#   SETUP_PHASE=azienda   my-erp-crm shell ... < deploy/configura_azienda.py
#   SETUP_PHASE=finanza   my-erp-crm shell ... < deploy/configura_azienda.py
#
# Fase "azienda" (prima di installare la contabilità): dati e paese dell'azienda, così
# viene installata la localizzazione fiscale giusta (Regno Unito -> piano dei conti UK,
# IVA VAT100, valuta GBP).
# Fase "finanza" (dopo): posizioni fiscali B2B/B2C per i clienti esteri e listino
# pubblico in euro. Lo script si può rieseguire: non duplica nulla.
#
# Variabili d'ambiente (vedi .env.example): COMPANY_NAME, COMPANY_COUNTRY, COMPANY_VAT,
# COMPANY_REGISTRY, COMPANY_STREET, COMPANY_CITY, COMPANY_ZIP, COMPANY_EMAIL,
# COMPANY_PHONE, COMPANY_WEBSITE, PUBLIC_CURRENCY, ADMIN_LANG, ADMIN_PASSWORD.
import os

phase = os.environ.get("SETUP_PHASE", "azienda")
company = env.ref("base.main_company")  # noqa: F821  (env è fornito dalla shell)


def setting(name, default=""):
    return (os.environ.get(name) or default).strip()


if phase == "azienda":
    country = env["res.country"].search([("code", "=", setting("COMPANY_COUNTRY", "GB").upper())], limit=1)
    values = {"country_id": country.id}
    for field, var in (
        ("name", "COMPANY_NAME"), ("vat", "COMPANY_VAT"), ("company_registry", "COMPANY_REGISTRY"),
        ("street", "COMPANY_STREET"), ("city", "COMPANY_CITY"), ("zip", "COMPANY_ZIP"),
        ("email", "COMPANY_EMAIL"), ("phone", "COMPANY_PHONE"), ("website", "COMPANY_WEBSITE"),
    ):
        if setting(var):
            values[field] = setting(var)
    company.write(values)
    # Inglese sempre attivo (documenti per i clienti), più la lingua dell'amministratore.
    lang = setting("ADMIN_LANG", "it_IT")
    for code in {"en_US", lang}:
        env["res.lang"]._activate_lang(code)
    admin = env.ref("base.user_admin")
    admin.lang = lang
    if setting("ADMIN_PASSWORD"):
        admin.password = setting("ADMIN_PASSWORD")
    env.cr.commit()
    print(f"Azienda: {company.name} ({company.country_id.name})")

elif phase == "finanza":
    Chart = env["account.chart.template"].with_company(company)

    def ref(xmlid):
        return Chart.ref(xmlid, raise_if_not_found=False)

    # --- IVA per i clienti esteri (solo con la localizzazione Regno Unito) ---------------
    rest_of_world = ref("account_fiscal_position_rest_of_world_b2b")
    if rest_of_world:
        # Clienti esteri con partita IVA / codice fiscale aziendale: servizi fuori campo
        # IVA UK (il cliente applica l'inversione contabile nel suo paese), merci 0% export.
        rest_of_world.write({
            "name": "Rest of the world - businesses (B2B)",
            "vat_required": True,
            "sequence": 4,
        })
        # Clienti esteri privati: regola generale dei servizi B2C -> IVA UK.
        # Le eccezioni (servizi digitali, consulenza/pubblicità a privati extra UK, merci
        # esportate) si gestiscono scegliendo l'imposta "0% EX" sul prodotto o sulla riga.
        Fpos = env["account.fiscal.position"]
        b2c = Fpos.search([("company_id", "=", company.id), ("name", "=", "Rest of the world - consumers (B2C)")], limit=1)
        if not b2c:
            b2c = Fpos.create({
                "name": "Rest of the world - consumers (B2C)",
                "company_id": company.id,
                "auto_apply": True,
                "vat_required": False,
                "sequence": 5,
            })
        # Vendite: restano le imposte UK. Acquisti da fornitori esteri: stesse regole B2B
        # (inversione contabile sui servizi, IVA all'importazione posticipata sulle merci).
        # L'imposta "0% EX" resta selezionabile a mano, ma in B2C non sostituisce quelle UK.
        for xmlid in ("ST11", "ST5", "ST0", "ST2", "PT_20_RCI", "PT_20_PVA", "PT_0_EX"):
            tax = ref(xmlid)
            if tax:
                tax.fiscal_position_ids |= b2c
        print("Posizioni fiscali: UK, estero B2B (0%), estero B2C (IVA UK)")
    else:
        print("Localizzazione Regno Unito non installata: posizioni fiscali non modificate")

    # --- Colori del marchio nei pulsanti delle email automatiche ---------------------------
    if "email_secondary_color" in company._fields:
        company.write({"email_primary_color": "#FFFFFF", "email_secondary_color": "#0F7A73"})

    # --- Listino pubblico in euro ---------------------------------------------------------
    code = setting("PUBLIC_CURRENCY", "EUR").upper()
    public_currency = env["res.currency"].with_context(active_test=False).search([("name", "=", code)], limit=1)
    public_currency.active = True
    settings = env["res.config.settings"].create({"group_product_pricelist": True})
    settings.execute()
    Pricelist = env["product.pricelist"].with_context(active_test=False)
    public = Pricelist.search([("company_id", "in", (company.id, False)), ("currency_id", "=", public_currency.id)], limit=1)
    if not public:
        public = Pricelist.create({
            "name": f"Public prices ({code})",
            "currency_id": public_currency.id,
            "company_id": company.id,
        })
    public.write({"sequence": 1, "active": True})
    for pricelist in Pricelist.search([("company_id", "in", (company.id, False)), ("id", "!=", public.id)]):
        if pricelist.sequence <= 1:
            pricelist.sequence = 10
        if pricelist.name == "Default":
            pricelist.name = f"Internal prices ({pricelist.currency_id.name})"
    env.cr.commit()
    print(f"Listino predefinito: {public.name}; valuta contabile: {company.currency_id.name}")

else:
    raise SystemExit(f"SETUP_PHASE sconosciuta: {phase}")
