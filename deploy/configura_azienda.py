# Configurazione dell'azienda che vende, eseguita dentro la shell di my-erp-crm:
#
#   SETUP_PHASE=azienda   my-erp-crm shell ... < deploy/configura_azienda.py
#   SETUP_PHASE=finanza   my-erp-crm shell ... < deploy/configura_azienda.py
#
# Fase "azienda" (prima di installare la contabilità): dati e paese dell'azienda, così
# viene installata la localizzazione giusta (Regno Unito -> piano dei conti UK, GBP).
# Fase "finanza" (dopo): imposte e posizioni fiscali della LTD non registrata alla VAT,
# e listino pubblico in euro. Lo script si può rieseguire: non duplica nulla.
#
# Variabili d'ambiente (vedi .env.example): COMPANY_NAME, COMPANY_COUNTRY, COMPANY_VAT,
# COMPANY_REGISTRY, COMPANY_STREET, COMPANY_CITY, COMPANY_ZIP, COMPANY_EMAIL,
# COMPANY_PHONE, COMPANY_WEBSITE, PUBLIC_CURRENCY, ADMIN_LANG, ADMIN_PASSWORD, OSS_REGISTERED,
# SELF_BILLING_FLAG_FIELD.
import ast
import os

from odoo import Command
from odoo.tools.misc import file_path

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
    # --- IVA: società britannica NON registrata alla VAT --------------------------------
    #
    # Nessuna VAT britannica in fattura; il trattamento dipende dal cliente:
    #   Regno Unito ............................ nessuna VAT (fornitore non registrato)
    #   imprese UE con numero IVA verificato VIES  fuori campo UK, reverse charge del cliente
    #   imprese svizzere con numero IVA ........ fuori campo UK, imposta sull'acquisto del cliente
    #   imprese del resto del mondo ............ fuori campo UK, regole locali del cliente
    #   privati fuori dal Regno Unito .......... fuori campo UK; i servizi DIGITALI a privati UE
    #                                            richiedono l'OSS non-UE dal primo euro: finché
    #                                            non c'è la registrazione (OSS_REGISTERED) la
    #                                            fattura si ferma invece di indovinare.
    # Con SELF_BILLING_FLAG_FIELD si indica il campo booleano della posizione fiscale con cui
    # un modulo esterno prepara per il cliente il documento di autofatturazione: si accende
    # sulle posizioni delle imprese UE e svizzere.
    # Se la società è registrata alla VAT (COMPANY_VAT valorizzata) questa configurazione non
    # vale: lo script si ferma e le scelte si fanno col commercialista.
    if company.vat:
        raise SystemExit(
            "COMPANY_VAT è valorizzata: per una società registrata alla VAT la configurazione IVA va "
            "decisa col commercialista. Nessuna imposta modificata.")
    Fpos = env["account.fiscal.position"]
    Tax = env["account.tax"].with_context(active_test=False)
    vat_rules = "vies_required" in Fpos._fields          # modulo my_erp_crm_iva
    kit_field = setting("SELF_BILLING_FLAG_FIELD")
    kit_field = kit_field if kit_field in Fpos._fields else ""
    if vat_rules:
        company.vat_check_vies = True

    def legal_note(tax, en, it):
        # Dicitura in fattura: inglese (testo base) e italiano, frase per frase.
        tax.with_context(lang="en_US").invoice_legal_notes = f"<p>{en}</p>"
        if env["res.lang"]._lang_get("it_IT"):
            tax.update_field_translations("invoice_legal_notes", {"it_IT": {en: it}})

    def ubl_codes(tax, category, reason):
        # Fattura elettronica UBL/Peppol leggibile dal gestionale del cliente B2B.
        if "ubl_cii_tax_category_code" in tax._fields:
            tax.write({"ubl_cii_tax_category_code": category, "ubl_cii_tax_exemption_reason_code": reason})

    group = env["account.tax.group"].search([("company_id", "=", company.id), ("name", "=", "No UK VAT")], limit=1) \
        or env["account.tax.group"].create({"name": "No UK VAT", "company_id": company.id,
                                            "country_id": company.country_id.id})

    def zero_tax(name, label):
        tax = Tax.search([("company_id", "=", company.id), ("name", "=", name), ("type_tax_use", "=", "sale")], limit=1)
        if not tax:
            lines = {doc: [Command.create({"document_type": doc, "repartition_type": "base"}),
                           Command.create({"document_type": doc, "repartition_type": "tax"})]
                     for doc in ("invoice", "refund")}
            tax = Tax.create({"name": name, "amount": 0.0, "amount_type": "percent", "type_tax_use": "sale",
                              "description": label, "invoice_label": label, "company_id": company.id,
                              "country_id": company.country_id.id, "tax_group_id": group.id,
                              "invoice_repartition_line_ids": lines["invoice"],
                              "refund_repartition_line_ids": lines["refund"]})
        tax.active = True
        return tax

    def fiscal_position(name, sequence, **vals):
        fpos = Fpos.with_context(active_test=False).search([("company_id", "=", company.id), ("name", "=", name)], limit=1)
        vals = {"name": name, "company_id": company.id, "auto_apply": True, "sequence": sequence,
                "vat_required": False, "country_id": False, "country_group_id": False, "active": True, **vals}
        if fpos:
            fpos.write(vals)
            return fpos
        return Fpos.create(vals)

    # Le posizioni estere della localizzazione (pensate per una società registrata) lasciano
    # il posto alle nostre; resta solo «United Kingdom».
    chart = env["account.chart.template"].with_company(company)
    for xmlid in ("account_fiscal_position_rest_of_world_b2b", "account_fiscal_position_ni_to_eu_b2b"):
        localization_fpos = chart.ref(xmlid, raise_if_not_found=False)
        if localization_fpos:
            localization_fpos.active = False

    europe = env.ref("base.europe")
    NOT_REGISTERED = ("No VAT charged: the supplier is not registered for UK VAT.",
                      "Nessuna IVA addebitata: il fornitore non è registrato ai fini VAT nel Regno Unito.")
    OUTSIDE = ("Outside the scope of UK VAT: place of supply outside the United Kingdom.",
               "Operazione fuori campo VAT britannica: luogo della prestazione fuori dal Regno Unito.")

    # 1. Imposte di partenza dei prodotti (nessuna VAT): servizi generali e servizi digitali.
    general = zero_tax("No UK VAT", "No VAT")
    digital = zero_tax("No UK VAT - digital", "No VAT")
    for tax in (general, digital):
        legal_note(tax, *NOT_REGISTERED)
        tax.write({"original_tax_ids": [(5, 0, 0)], "fiscal_position_ids": [(5, 0, 0)]})
    company.account_sale_tax_id = general
    # Le imposte VAT della localizzazione non si usano finché la LTD non è registrata.
    uk_vat = Tax.search([("company_id", "=", company.id), ("type_tax_use", "in", ("sale", "purchase")),
                         ("tax_group_id", "!=", group.id)])
    uk_vat.active = False
    company.account_purchase_tax_id = False

    # 2. Imprese dell'Unione europea: reverse charge del cliente, solo con VIES valido.
    eu_b2b = fiscal_position("EU businesses - reverse charge", 3, country_group_id=europe.id, vat_required=True)
    if vat_rules:
        eu_b2b.vies_required = True
    rc = zero_tax("Reverse charge (EU)", "Reverse charge")
    legal_note(rc, "Outside the scope of UK VAT. Reverse charge: the customer accounts for any VAT due in its own country.",
               "Operazione fuori campo VAT britannica. Reverse charge: l'IVA eventualmente dovuta la assolve il cliente nel proprio paese.")
    ubl_codes(rc, "AE", "VATEX-EU-AE")

    # 3. Imprese svizzere: imposta sull'acquisto (Bezugsteuer) del cliente.
    ch_b2b = fiscal_position("Swiss businesses", 3, country_id=env.ref("base.ch").id, vat_required=True)
    ch = zero_tax("Swiss acquisition tax", "Bezugsteuer")
    legal_note(ch, "Outside the scope of UK VAT. Swiss acquisition tax (Bezugsteuer) may be due by the recipient in Switzerland.",
               "Operazione fuori campo VAT britannica. L'imposta sull'acquisto svizzera (Bezugsteuer) può essere dovuta dal destinatario in Svizzera.")
    ubl_codes(ch, "O", "VATEX-EU-O")
    if kit_field:
        (eu_b2b | ch_b2b).write({kit_field: True})

    # 4. Imprese e privati del resto del mondo, privati UE: fuori campo VAT britannica.
    row_b2b = fiscal_position("Rest of the world - businesses", 4, vat_required=True)
    eu_b2c = fiscal_position("EU consumers", 5, country_group_id=europe.id)
    row_b2c = fiscal_position("Rest of the world - consumers", 6)
    outside = zero_tax("Outside scope UK VAT", "Outside scope")
    legal_note(outside, *OUTSIDE)
    ubl_codes(outside, "O", "VATEX-EU-O")

    rc.write({"original_tax_ids": [(6, 0, (general | digital).ids)], "fiscal_position_ids": [(6, 0, eu_b2b.ids)]})
    ch.write({"original_tax_ids": [(6, 0, (general | digital).ids)], "fiscal_position_ids": [(6, 0, ch_b2b.ids)]})
    outside.write({"original_tax_ids": [(6, 0, (general | digital).ids)],
                   "fiscal_position_ids": [(6, 0, (row_b2b | eu_b2c | row_b2c).ids)]})

    # 5. Servizi digitali a privati UE: OSS non-UE dal primo euro. Senza la registrazione la
    #    vendita si ferma; con OSS_REGISTERED=1 si applica l'aliquota del paese del cliente,
    #    con due prove di localizzazione.
    oss_registered = setting("OSS_REGISTERED") in ("1", "true", "yes", "si", "sì")
    if vat_rules:
        eu_b2c.write({"blocked_tax_ids": [(5, 0, 0)] if oss_registered else [(6, 0, digital.ids)],
                      "oss_location_proofs_required": oss_registered})
    oss_note = ("VAT of the consumer's country at the local rate, paid via the non-Union OSS scheme.",
                "IVA del Paese del consumatore ad aliquota locale, assolta via OSS regime non-UE.")
    tax_map_src = open(file_path("l10n_eu_oss/models/eu_tax_map.py")).read()
    tax_map = ast.literal_eval(tax_map_src[tax_map_src.index("{"):tax_map_src.rindex("}") + 1])
    eu_rates = {"BE": 21.0, **{dest: rate for (orig, orig_rate, dest), rate in tax_map.items()
                               if orig == "BE" and orig_rate == 21.0}}
    for code, rate in sorted(eu_rates.items()):
        country = env["res.country"].search([("code", "=", code)], limit=1)
        name = f"{rate:g}% {code} VAT (OSS)"
        existing = Tax.search([("company_id", "=", company.id), ("name", "=", name), ("type_tax_use", "=", "sale")], limit=1)
        if not oss_registered:
            existing.active = False
            continue
        fpos = fiscal_position(f"EU consumers - {country.name} (OSS)", 5, country_id=country.id)
        if vat_rules:
            fpos.oss_location_proofs_required = True
        oss_tax = existing or zero_tax(name, f"{rate:g}% {code} VAT")
        oss_tax.write({"amount": rate, "original_tax_ids": [(6, 0, digital.ids)], "fiscal_position_ids": [(6, 0, fpos.ids)]})
        outside.fiscal_position_ids |= fpos  # i servizi generali restano fuori campo
        legal_note(oss_tax, *oss_note)
    if not oss_registered:
        Fpos.search([("company_id", "=", company.id), ("name", "like", "EU consumers - %(OSS)")]).active = False

    # 6. Prodotti di partenza (prezzi da completare nel listino in euro).
    Product = env["product.template"]
    for default_code, name, tax in (("APP-SUB", "App subscription", digital),
                                    ("BIO-CHECKUP", "Biometric check-up", general)):
        product = Product.search([("default_code", "=", default_code)], limit=1)
        if product:
            product.taxes_id = tax
        else:
            Product.create({"name": name, "default_code": default_code, "type": "service",
                            "sale_ok": True, "purchase_ok": False, "list_price": 0.0,
                            "taxes_id": [(6, 0, tax.ids)]})
    print("IVA: società non registrata VAT; imprese UE reverse charge (VIES), imprese svizzere Bezugsteuer, "
          f"resto del mondo fuori campo; servizi digitali a privati UE: {'OSS attivo' if oss_registered else 'BLOCCATI finché manca la registrazione OSS'}")

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
