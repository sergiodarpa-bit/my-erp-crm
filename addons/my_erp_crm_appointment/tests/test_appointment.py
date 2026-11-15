from datetime import datetime, timedelta

from freezegun import freeze_time

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from odoo.addons.base.tests.common import BaseCommon

# Lunedi' 16 novembre 2026: gli orari dei test sono in Europe/Rome (UTC+1 a novembre).
MONDAY = "2026-11-16"


def utc(hour, minute=0, day=MONDAY):
    """Istante UTC (naive) corrispondente alle ore locali di Roma indicate."""
    return datetime.fromisoformat(day) + timedelta(hours=hour - 1, minutes=minute)


@tagged("post_install", "-at_install")
class TestAppointment(BaseCommon):
    # I test girano come un utente "Prenotazioni / Responsabile", non come amministratore.
    _test_user_groups = ("base.group_user", "my_erp_crm_appointment.group_appointment_manager")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_a = new_test_user(cls.env, login="apt_a", name="Anna", email="anna@example.com",
                                   groups="base.group_user,my_erp_crm_appointment.group_appointment_user", tz="Europe/Rome")
        cls.user_b = new_test_user(cls.env, login="apt_b", name="Bruno", email="bruno@example.com",
                                   groups="base.group_user,my_erp_crm_appointment.group_appointment_user", tz="Europe/Rome")
        cls.apt_type = cls.env["appointment.type"].create({
            "name": "Call conoscitiva",
            "user_ids": [Command.set([cls.user_a.id, cls.user_b.id])],
            "assign_method": "auto",
            "duration_minutes": 30,
            "slot_step_minutes": 30,
            "buffer_minutes": 0,
            "min_notice_hours": 0,
            "max_days_ahead": 30,
            "cancel_limit_hours": 0,
            "tz": "Europe/Rome",
            "create_lead": True,
            "is_published": True,
            "slot_ids": [Command.create({"weekday": str(d), "hour_from": 9.0, "hour_to": 12.0}) for d in range(5)],
            "question_ids": [
                Command.create({"name": "Argomento", "question_type": "char", "required": True}),
                Command.create({"name": "Accetto l'informativa", "question_type": "checkbox", "required": True}),
            ],
        })
        cls.customer = cls.env["res.partner"].create({"name": "Carla Cliente", "email": "carla@example.com", "phone": "+39 333 0000000"})

    def _slots_on(self, day=MONDAY, users=None):
        start = datetime.fromisoformat("%sT00:00:00" % day)
        end = datetime.fromisoformat("%sT23:59:59" % day)
        with freeze_time("%s 06:00:00" % MONDAY):
            return self.apt_type._get_available_slots(start, end, users=users)

    def test_slots_follow_schedule(self):
        slots = self._slots_on()
        starts = [slot["start"] for slot in slots]
        self.assertEqual(starts[0], utc(9), "il primo orario e' le 9:00 di Roma")
        self.assertEqual(starts[-1], utc(11, 30), "l'ultimo orario finisce alle 12:00")
        self.assertEqual(len(starts), 6)
        self.assertEqual(set(slots[0]["user_ids"]), {self.user_a.id, self.user_b.id})
        self.assertFalse(self._slots_on(day="2026-11-21"), "il sabato non ha fasce")

    def test_busy_event_blocks_only_that_user(self):
        self.env["calendar.event"].create({
            "name": "Riunione interna",
            "start": utc(10),
            "stop": utc(11),
            "user_id": self.user_a.id,
            "partner_ids": [Command.set([self.user_a.partner_id.id])],
        })
        by_start = {slot["start"]: slot["user_ids"] for slot in self._slots_on()}
        self.assertEqual(by_start[utc(10)], [self.user_b.id])
        self.assertEqual(by_start[utc(10, 30)], [self.user_b.id])
        self.assertEqual(set(by_start[utc(9)]), {self.user_a.id, self.user_b.id})

    def test_buffer_and_declined_event(self):
        self.apt_type.buffer_minutes = 15
        event = self.env["calendar.event"].create({
            "name": "Occupato",
            "start": utc(10),
            "stop": utc(11),
            "user_id": self.user_b.id,
            "partner_ids": [Command.set([self.user_a.partner_id.id, self.user_b.partner_id.id])],
        })
        by_start = {slot["start"]: slot["user_ids"] for slot in self._slots_on()}
        # Le 9:30 finiscono alle 10:00: con 15 minuti di spaziatura toccano l'evento.
        self.assertNotIn(utc(9, 30), by_start)
        self.assertNotIn(utc(10, 30), by_start)
        self.assertIn(utc(9), by_start)
        self.assertIn(utc(11, 30), by_start)
        # Anna rifiuta l'invito: per lei lo slot torna libero.
        event.attendee_ids.filtered(lambda a: a.partner_id == self.user_a.partner_id).write({"state": "declined"})
        by_start = {slot["start"]: slot["user_ids"] for slot in self._slots_on()}
        self.assertEqual(by_start[utc(10, 30)], [self.user_a.id])

    def test_min_notice_and_window(self):
        self.apt_type.write({"min_notice_hours": 4, "max_days_ahead": 1})
        with freeze_time("%s 08:00:00" % MONDAY):  # 9:00 di Roma
            slots = self.apt_type._get_available_slots(utc(0), utc(23, 59, day="2026-11-18"))
        starts = [slot["start"] for slot in slots]
        self.assertEqual(starts[0], utc(9, day="2026-11-17"),
                         "lunedi' e' tutto sotto il preavviso di 4 ore, si parte da martedi'")
        self.assertTrue(all(slot["start"] < utc(0, day="2026-11-18") for slot in slots), "mercoledi' e' oltre la finestra")

    def test_booking_creates_event_and_lead(self):
        with freeze_time("%s 06:00:00" % MONDAY):
            event = self.apt_type._create_booking(
                utc(9), self.user_a, self.customer,
                answers=[(self.apt_type.question_ids[0], "Gemello Digitale"), (self.apt_type.question_ids[1], "Si'")],
                visitor_tz="Europe/Rome")
        self.assertEqual(event.appointment_state, "confirmed")
        self.assertEqual(event.appointment_type_id, self.apt_type)
        self.assertEqual(event.user_id, self.user_a)
        self.assertEqual(event.stop, utc(9, 30))
        self.assertTrue(event.appointment_token)
        self.assertIn("/appointment/view/%s" % event.appointment_token, event.appointment_manage_url)
        self.assertEqual(set(event.partner_ids.ids), {self.user_a.partner_id.id, self.customer.id})
        host_attendee = event.attendee_ids.filtered(lambda a: a.partner_id == self.user_a.partner_id)
        self.assertEqual(host_attendee.state, "accepted")
        self.assertEqual(len(event.appointment_answer_ids), 2)
        self.assertTrue(event.videocall_location, "appuntamento online: link di videochiamata")
        self.assertTrue(event.opportunity_id)
        self.assertEqual(event.opportunity_id.partner_id, self.customer)
        self.assertEqual(event.opportunity_id.user_id, self.user_a)
        # Lo stesso orario con la stessa persona non e' piu' prenotabile; Bruno resta libero.
        with freeze_time("%s 06:00:00" % MONDAY):
            with self.assertRaises(ValidationError):
                self.apt_type._create_booking(utc(9), self.user_a, self.customer)
            by_start = {slot["start"]: slot["user_ids"] for slot in self._slots_on()}
            self.assertEqual(by_start[utc(9)], [self.user_b.id])
            self.assertEqual(self.apt_type._pick_user(utc(9), by_start[utc(9)]), self.user_b)

    def test_auto_assignment_balances_bookings(self):
        with freeze_time("%s 06:00:00" % MONDAY):
            free = {slot["start"]: slot["user_ids"] for slot in self._slots_on()}
            first = self.apt_type._pick_user(utc(9), free[utc(9)])
            self.apt_type._create_booking(utc(9), first, self.customer)
            second = self.apt_type._pick_user(utc(10), free[utc(10)])
        self.assertNotEqual(first, second, "la seconda prenotazione va all'altra persona")

    def test_cancel_and_reschedule(self):
        with freeze_time("%s 06:00:00" % MONDAY):
            event = self.apt_type._create_booking(utc(9), self.user_a, self.customer)
            self.assertTrue(event.appointment_can_self_manage)
            event._appointment_reschedule(utc(11))
            self.assertEqual(event.start, utc(11))
            self.assertEqual(event.stop, utc(11, 30))
            by_start = {slot["start"]: slot["user_ids"] for slot in self._slots_on()}
            self.assertEqual(set(by_start[utc(9)]), {self.user_a.id, self.user_b.id}, "il vecchio orario e' tornato libero")
            self.assertEqual(by_start[utc(11)], [self.user_b.id])
            with self.assertRaises(ValidationError):
                event._appointment_reschedule(utc(12))
            event.action_appointment_cancel(reason="Impegno sopraggiunto", cancelled_by="customer")
        self.assertEqual(event.appointment_state, "cancelled")
        self.assertFalse(event.active)
        self.assertEqual(event.appointment_cancelled_by, "customer")
        with freeze_time("%s 06:00:00" % MONDAY):
            by_start = {slot["start"]: slot["user_ids"] for slot in self._slots_on()}
        self.assertEqual(set(by_start[utc(11)]), {self.user_a.id, self.user_b.id}, "cancellata: l'orario e' libero")

    def test_cancel_limit(self):
        self.apt_type.cancel_limit_hours = 12
        with freeze_time("%s 06:00:00" % MONDAY):
            event = self.apt_type._create_booking(utc(9), self.user_a, self.customer)
            self.assertFalse(event.appointment_can_self_manage, "mancano meno di 12 ore")
            event_later = self.apt_type._create_booking(utc(9, day="2026-11-17"), self.user_a, self.customer)
            self.assertTrue(event_later.appointment_can_self_manage)

    def test_manual_confirmation(self):
        self.apt_type.manual_confirmation = True
        with freeze_time("%s 06:00:00" % MONDAY):
            event = self.apt_type._create_booking(utc(9), self.user_a, self.customer)
            self.assertEqual(event.appointment_state, "pending")
            self.assertTrue(event.activity_ids, "la persona ha un'attivita' da fare")
            by_start = {slot["start"]: slot["user_ids"] for slot in self._slots_on()}
            self.assertEqual(by_start[utc(9)], [self.user_b.id], "in attesa, ma l'orario e' riservato")
            event.action_appointment_confirm()
        self.assertEqual(event.appointment_state, "confirmed")
        self.assertFalse(event.activity_ids)

    def test_partner_reuse(self):
        partner = self.apt_type._find_or_create_partner("Carla Cliente", "CARLA@example.com", phone="+39 1")
        self.assertEqual(partner, self.customer, "stessa email, stesso contatto")
        new = self.apt_type._find_or_create_partner("Dario", "dario@example.com", phone="+39 2")
        self.assertEqual(new.email, "dario@example.com")
        self.assertEqual(new.phone, "+39 2")

    def test_display_slots_in_visitor_tz(self):
        with freeze_time("%s 06:00:00" % MONDAY):
            grouped = self.apt_type._get_slots_for_display(
                datetime.fromisoformat(MONDAY).date(), datetime.fromisoformat(MONDAY).date(), "Europe/London")
        self.assertEqual(grouped[MONDAY][0]["label"], "08:00", "le 9:00 di Roma sono le 8:00 di Londra")
