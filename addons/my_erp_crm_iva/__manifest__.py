{
    "name": "my-erp-crm: regole IVA",
    "summary": "Inversione contabile solo con VIES verificato, OSS con prove di localizzazione, "
               "nessuna fattura senza trattamento IVA determinato.",
    "description": """
Rende operativi in contabilità gli invarianti dello studio IVA del progetto
(INV-IVA-01…10):

- controllo VIES diretto sul servizio della Commissione europea, con la prova
  (data, nome, esito) conservata sul cliente;
- inversione contabile B2B UE solo con partita IVA verificata VIES, anche per
  aziende con sede fuori dall'UE; senza verifica il cliente è trattato come privato;
- vendite OSS a privati UE solo con due prove di localizzazione;
- nessuna fattura cliente senza paese del cliente o con righe senza imposta;
- ogni fattura conserva le prove del proprio trattamento IVA.
""",
    "version": "1.0",
    "category": "Accounting",
    "author": "my-erp-crm",
    "website": "https://github.com/sergiodarpa-bit/my-erp-crm",
    "license": "LGPL-3",
    "depends": ["account", "base_vat"],
    "data": [
        "views/res_partner_views.xml",
        "views/account_fiscal_position_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
}
