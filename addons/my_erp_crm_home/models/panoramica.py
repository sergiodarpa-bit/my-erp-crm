from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models


class MyErpCrmPanoramica(models.AbstractModel):
    _name = "my_erp_crm.panoramica"
    _description = "Panoramica: numeri delle app attive"

    def _oggi(self):
        """Inizio e fine di oggi nel fuso dell'utente, in UTC come le date nel database."""
        fuso = pytz.timezone(self.env.user.tz or "UTC")
        oggi = datetime.now(fuso).date()

        def in_utc(giorno):
            return fuso.localize(datetime.combine(giorno, time.min)).astimezone(pytz.utc).replace(tzinfo=None)

        return fields.Datetime.to_string(in_utc(oggi)), fields.Datetime.to_string(in_utc(oggi + timedelta(days=1)))

    def _indicatori(self):
        """(menu dell'app, modello, etichetta breve, titolo dell'elenco, dominio).

        Un indicatore compare solo se l'app è installata e l'utente può leggerne i record; le
        regole di accesso valgono anche per il conteggio.
        """
        inizio, fine = self._oggi()
        io = self.env.user.partner_id.id
        return [
            ("crm.crm_menu_root", "crm.lead", "opportunità aperte", "Opportunità aperte",
             [("type", "=", "opportunity"), ("won_status", "=", "pending")]),
            ("sale.sale_menu_root", "sale.order", "preventivi da confermare", "Preventivi da confermare",
             [("state", "in", ["draft", "sent"])]),
            ("my_erp_crm_appointment.appointment_menu_root", "calendar.event", "prenotazioni oggi",
             "Prenotazioni di oggi",
             [("appointment_type_id", "!=", False), ("appointment_state", "in", ["pending", "confirmed"]),
              ("start", ">=", inizio), ("start", "<", fine)]),
            ("calendar.mail_menu_calendar", "calendar.event", "tuoi appuntamenti oggi", "I tuoi appuntamenti di oggi",
             [("partner_ids", "in", [io]), ("start", "<", fine), ("stop", ">=", inizio)]),
            ("sign_oca.sign_oca_root_menu", "sign.oca.request", "documenti da firmare", "Documenti in attesa di firma",
             [("state", "=", "0_sent")]),
            ("account.menu_finance", "account.move", "fatture da incassare", "Fatture da incassare",
             [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
              ("payment_state", "in", ["not_paid", "partial"])]),
        ]

    @api.model
    def numeri(self):
        """{id del menu dell'app: {valore, etichetta, titolo, modello, dominio}} per la Panoramica."""
        risultato = {}
        for xmlid, modello, etichetta, titolo, dominio in self._indicatori():
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if not menu or modello not in self.env or not self.env[modello].has_access("read"):
                continue
            risultato[menu.id] = {
                "valore": self.env[modello].search_count(dominio),
                "etichetta": etichetta,
                "titolo": titolo,
                "modello": modello,
                "dominio": dominio,
            }
        return risultato
