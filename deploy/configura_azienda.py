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
    Chart = env["account.chart.template"].with_company(company)

    def ref(xmlid):
        return Chart.ref(xmlid, raise_if_not_found=False)

    # --- IVA (solo con la localizzazione Regno Unito) ---------------------------------------
    #
    # Due tipi di servizio, con regole diverse per i privati esteri:
    # - servizi "generali" (es. check-up): imposta 20% standard. Privati esteri: regola
    #   generale B2C -> IVA UK 20%.
    # - servizi digitali (abbonamenti app, ESS): imposta "20% Digital". Privati UE: IVA del
    #   paese del cliente (regime OSS non-Union); privati extra UE: fuori campo IVA UK.
    # Aziende estere con partita IVA: entrambi fuori campo IVA UK (0% EX, inversione contabile).
    rest_of_world = ref("account_fiscal_position_rest_of_world_b2b")
    st11, st_0_ex = ref("ST11"), ref("ST_0_EX")
    if rest_of_world and st11 and st_0_ex:
        Fpos = env["account.fiscal.position"]
        Tax = env["account.tax"].with_context(active_test=False)
        domestic = ref("account_fiscal_position_domestic")
        rest_of_world.write({"name": "Rest of the world - businesses (B2B)", "vat_required": True, "sequence": 4})

        def fiscal_position(name, sequence, country=None):
            fpos = Fpos.search([("company_id", "=", company.id), ("name", "=", name)], limit=1)
            vals = {"name": name, "company_id": company.id, "auto_apply": True,
                    "vat_required": False, "sequence": sequence,
                    "country_id": country.id if country else False}
            if fpos:
                fpos.write(vals)
                return fpos
            return Fpos.create(vals)

        def tax_by_name(name):
            return Tax.search([("company_id", "=", company.id), ("name", "=", name), ("type_tax_use", "=", "sale")], limit=1)

        # Privati: regole che valgono per tutti i paesi esteri (vendite generali con IVA UK,
        # acquisti da fornitori esteri con inversione contabile / IVA d'importazione posticipata).
        consumer_native = [ref(x) for x in ("ST11", "ST5", "ST0", "ST2", "PT_20_RCI", "PT_20_PVA", "PT_0_EX")]
        consumer_native = [t for t in consumer_native if t]

        # 1. Imposta dei servizi digitali: 20% nel Regno Unito, 0% EX per aziende estere.
        digital = tax_by_name("20% Digital")
        if not digital:
            digital = st11.copy({"name": "20% Digital", "description": "20% Digital",
                                 "invoice_label": "20%", "fiscal_position_ids": [(6, 0, domestic.ids)],
                                 "original_tax_ids": [(5, 0, 0)]})
        st_0_ex.original_tax_ids |= digital

        # 2. Privati extra UE: servizi generali con IVA UK, servizi digitali fuori campo.
        b2c = fiscal_position("Rest of the world - consumers (B2C)", 6)
        for tax in consumer_native:
            tax.fiscal_position_ids |= b2c
        digital_outside = tax_by_name("0% EX Digital")
        if not digital_outside:
            digital_outside = st_0_ex.copy({"name": "0% EX Digital", "description": "0% EX Digital"})
        digital_outside.write({"original_tax_ids": [(6, 0, digital.ids)], "fiscal_position_ids": [(6, 0, b2c.ids)]})

        # 3. Privati UE: servizi digitali con l'IVA del paese del cliente (OSS non-Union).
        tax_map_src = open(file_path("l10n_eu_oss/models/eu_tax_map.py")).read()
        tax_map = ast.literal_eval(tax_map_src[tax_map_src.index("{"):tax_map_src.rindex("}") + 1])
        eu_rates = {"BE": 21.0, **{dest: rate for (orig, orig_rate, dest), rate in tax_map.items()
                                   if orig == "BE" and orig_rate == 21.0}}
        # Conto dell'IVA UE da versare, accanto al conto IVA usato dall'imposta UK al 20%.
        vat_account = st11.invoice_repartition_line_ids.filtered(
            lambda line: line.repartition_type == "tax").account_id[:1].with_company(company)
        Account = env["account.account"].with_company(company)
        oss_account = Account.search([("name", "=", "VAT payable OSS (EU)"), ("company_ids", "in", company.id)], limit=1)
        if not oss_account:
            oss_account = Account.create({
                "name": "VAT payable OSS (EU)",
                "code": Account._search_new_account_code(vat_account.code),
                "account_type": vat_account.account_type,
                "company_ids": [Command.link(company.id)],
            })
        oss_account.account_type = vat_account.account_type
        TaxGroup = env["account.tax.group"]
        for code, rate in sorted(eu_rates.items()):
            country = env["res.country"].search([("code", "=", code)], limit=1)
            fpos = fiscal_position(f"EU consumers - {country.name} (OSS)", 5, country)
            for tax in consumer_native:
                tax.fiscal_position_ids |= fpos
            group_name = f"OSS {rate:g}%"
            group = TaxGroup.search([("company_id", "=", company.id), ("name", "=", group_name)], limit=1) \
                or TaxGroup.create({"name": group_name, "company_id": company.id, "country_id": company.country_id.id,
                                    "tax_payable_account_id": oss_account.id, "tax_receivable_account_id": oss_account.id})
            name = f"{rate:g}% {code} VAT (OSS)"
            oss_tax = tax_by_name(name)
            if not oss_tax:
                lines = {doc: [Command.create({"document_type": doc, "repartition_type": "base"}),
                               Command.create({"document_type": doc, "repartition_type": "tax", "account_id": oss_account.id})]
                         for doc in ("invoice", "refund")}
                oss_tax = Tax.create({
                    "name": name, "amount": rate, "amount_type": "percent", "type_tax_use": "sale",
                    "description": f"{rate:g}% {code}", "invoice_label": f"{rate:g}% {code} VAT",
                    "company_id": company.id, "country_id": company.country_id.id, "tax_group_id": group.id,
                    "sequence": 1000,
                    "invoice_repartition_line_ids": lines["invoice"], "refund_repartition_line_ids": lines["refund"],
                })
            oss_tax.write({"amount": rate, "original_tax_ids": [(6, 0, digital.ids)], "fiscal_position_ids": [(6, 0, fpos.ids)]})

        # 4. Prodotti di partenza (prezzi da completare nel listino in euro).
        Product = env["product.template"]
        for default_code, name, tax in (("APP-SUB", "App subscription", digital),
                                        ("BIO-CHECKUP", "Biometric check-up", st11)):
            if not Product.search([("default_code", "=", default_code)], limit=1):
                Product.create({"name": name, "default_code": default_code, "type": "service",
                                "sale_ok": True, "purchase_ok": False, "list_price": 0.0,
                                "taxes_id": [(6, 0, tax.ids)]})
        print(f"IVA: UK, aziende estere 0%, privati UE con OSS ({len(eu_rates)} paesi), privati extra UE")
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
