{
    "name": "my-erp-crm: prenotazioni",
    "summary": "Calendari pubblici di prenotazione sul sito: orari, slot liberi, scelta della persona o "
               "assegnazione automatica, domande, promemoria, cancellazione e riprogrammazione, lead CRM.",
    "description": """
Pagine pubbliche di prenotazione (stile Calendly) costruite sul calendario interno.

Ogni tipo di appuntamento ha durata, orari settimanali, preavviso minimo, finestra di
prenotazione, spaziatura, domande per chi prenota, promemoria e un sito web di
pubblicazione. Gli slot liberi si calcolano sottraendo agli orari gli impegni del
calendario delle persone coinvolte: cio' che si pianifica in privato non e' prenotabile
dal pubblico. La persona puo' essere scelta da chi prenota oppure assegnata
automaticamente tra quelle disponibili (round-robin). Ogni prenotazione crea un evento
nel calendario, invia la conferma con invito .ics, i promemoria, un link per cancellare o
riprogrammare e, se richiesto, un'opportunita' nel CRM.
""",
    "version": "1.0.0",
    "category": "Website/Website",
    "author": "my-erp-crm",
    "website": "https://github.com/sergiodarpa-bit/my-erp-crm",
    "license": "LGPL-3",
    "depends": ["calendar", "website", "crm"],
    "data": [
        "security/my_erp_crm_appointment_security.xml",
        "security/ir.access.csv",
        "data/mail_template_data.xml",
        "views/appointment_type_views.xml",
        "views/calendar_event_views.xml",
        "views/appointment_menus.xml",
        "views/appointment_templates.xml",
    ],
    "demo": [
        "data/appointment_demo.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "my_erp_crm_appointment/static/src/scss/appointment.scss",
            "my_erp_crm_appointment/static/src/interactions/*.js",
        ],
    },
    "application": True,
}
