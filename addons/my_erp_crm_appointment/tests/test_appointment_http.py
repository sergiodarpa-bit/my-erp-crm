import json
from datetime import date, timedelta

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestAppointmentHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env.ref("base.user_admin")
        cls.apt_type = cls.env["appointment.type"].create({
            "name": "Demo pubblica",
            "user_ids": [Command.set([cls.user.id])],
            "assign_method": "auto",
            "duration_minutes": 30,
            "min_notice_hours": 0,
            "tz": "Europe/Rome",
            "is_published": True,
            "slot_ids": [Command.create({"weekday": str(d), "hour_from": 9.0, "hour_to": 12.0}) for d in range(7)],
        })
        cls.hidden_type = cls.env["appointment.type"].create({
            "name": "Non pubblicato",
            "user_ids": [Command.set([cls.user.id])],
            "is_published": False,
            "slot_ids": [Command.create({"weekday": "0", "hour_from": 9.0, "hour_to": 12.0})],
        })

    def test_public_pages(self):
        response = self.url_open(self.apt_type.website_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Demo pubblica", response.text)
        self.assertIn("o_appointment_calendar", response.text)
        response = self.url_open(self.hidden_type.website_url)
        self.assertEqual(response.status_code, 404, "un tipo non pubblicato non e' raggiungibile")

    def test_slots_rpc_and_booking(self):
        today = date.today()
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"type_id": self.apt_type.id, "year": today.year, "month": today.month, "tz": "Europe/Rome"},
        }
        response = self.url_open("/appointment/%s/slots" % self.apt_type.id, data=json.dumps(payload),
                                 headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 200)
        result = response.json()["result"]
        self.assertEqual(result["tz"], "Europe/Rome")
        slots = [slot for day in sorted(result["slots"]) for slot in result["slots"][day]]
        if not slots:
            # A fine mese puo' non restare nessun orario: si guarda il mese dopo.
            nxt = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
            payload["params"].update({"year": nxt.year, "month": nxt.month})
            response = self.url_open("/appointment/%s/slots" % self.apt_type.id, data=json.dumps(payload),
                                     headers={"Content-Type": "application/json"})
            result = response.json()["result"]
            slots = [slot for day in sorted(result["slots"]) for slot in result["slots"][day]]
        self.assertTrue(slots, "ci sono orari liberi")
        start = slots[0]["start"]
        form_url = "%s/book?start=%s&tz=Europe/Rome" % (self.apt_type.website_url, start)
        response = self.url_open(form_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("o_appointment_form", response.text)
        csrf = response.text.split('name="csrf_token" value="')[1].split('"')[0]
        response = self.url_open(form_url, data={
            "csrf_token": csrf,
            "name": "Mario Rossi",
            "email": "mario.rossi@example.com",
            "phone": "+39 333 1234567",
            "company_name": "Acme",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("/appointment/view/", response.url, response.text[:3000])
        event = self.env["calendar.event"].search([("appointment_type_id", "=", self.apt_type.id)], limit=1)
        self.assertTrue(event)
        self.assertEqual(event.appointment_booker_id.email, "mario.rossi@example.com")
        self.assertIn("Prenotazione confermata", response.text)
        # Pagina di gestione raggiungibile con il token, non senza.
        response = self.url_open("/appointment/view/%s" % event.appointment_token)
        self.assertEqual(response.status_code, 200)
        response = self.url_open("/appointment/view/token-sbagliato")
        self.assertEqual(response.status_code, 404)


@tagged("post_install", "-at_install")
class TestAppointmentBrowser(HttpCase):
    """Il calendario pubblico si disegna davvero nel browser: giorni con orari e orari del giorno."""

    def test_calendar_renders(self):
        apt_type = self.env["appointment.type"].create({
            "name": "Prova browser",
            "user_ids": [Command.set([self.env.ref("base.user_admin").id])],
            "assign_method": "auto",
            "duration_minutes": 30,
            "min_notice_hours": 0,
            "max_days_ahead": 60,
            "tz": "Europe/Rome",
            "is_published": True,
            "slot_ids": [Command.create({"weekday": str(d), "hour_from": 9.0, "hour_to": 12.0}) for d in range(7)],
        })
        # Il calendario si disegna dopo il caricamento dei bundle "lazy": si attende fino a 30 secondi.
        self.browser_js(
            apt_type.website_url + "?tz=Europe/Rome",
            """
            let attempts = 0;
            const timer = setInterval(() => {
                attempts += 1;
                const days = document.querySelectorAll(".o_appointment_day_available");
                const slots = document.querySelectorAll(".o_appointment_slot");
                const title = document.querySelector(".o_appointment_month_title").textContent.trim();
                if (days.length && slots.length && title) {
                    clearInterval(timer);
                    console.log("test successful");
                } else if (attempts >= 60) {
                    clearInterval(timer);
                    console.error("calendario non disegnato: giorni=" + days.length + " orari=" + slots.length + " titolo=" + title);
                }
            }, 500);
            """,
            ready="true",
            timeout=90,
        )
