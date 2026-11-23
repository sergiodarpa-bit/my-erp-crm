{
    "name": "my-erp-crm: firma dei preventivi",
    "summary": "Invia un preventivo alla firma, vedi le firme dal preventivo e ritrova lì il PDF firmato.",
    "description": """
Collega Firma (sign_oca) alle Vendite:

- pulsante «Invia alla firma» sul preventivo: firma il PDF del preventivo stesso, con una pagina
  in fondo per le firme del cliente (e, se serve, della clinica), oppure un modello di Firma
  collegato ai preventivi (per esempio il contratto);
- pulsante «Firme» sul preventivo, con le richieste di firma che lo riguardano;
- quando tutti hanno firmato, il PDF firmato viene allegato al preventivo, con una nota.

Si installa da solo dove ci sono le Vendite e Firma.
""",
    "version": "1.0",
    "category": "Hidden",
    "author": "my-erp-crm",
    "website": "https://github.com/sergiodarpa-bit/my-erp-crm",
    # Estende sign_oca (AGPL-3): resta sotto la stessa licenza.
    "license": "AGPL-3",
    "depends": ["sale", "sign_oca"],
    "data": [
        "security/ir.access.csv",
        "wizards/firma_preventivo_views.xml",
        "views/sale_order_views.xml",
    ],
    "auto_install": True,
}
