import uuid
from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools import email_normalize, html_escape

from odoo.addons.base.models.res_partner import _tz_get

WEEKDAYS = [
    ("0", "Lunedi'"),
    ("1", "Martedi'"),
    ("2", "Mercoledi'"),
    ("3", "Giovedi'"),
    ("4", "Venerdi'"),
    ("5", "Sabato"),
    ("6", "Domenica"),
]


class AppointmentType(models.Model):
    """Un tipo di appuntamento prenotabile dal sito: durata, orari, persone, regole.

    Gli slot liberi nascono dagli orari settimanali meno gli impegni del calendario delle
    persone coinvolte (eventi "occupato" a cui partecipano), con la spaziatura prima e dopo.
    """

    _name = "appointment.type"
    _description = "Tipo di appuntamento"
    _inherit = ["website.published.multi.mixin", "website.seo.metadata"]
    _order = "sequence, id"

    def _default_tz(self):
        return self.env.user.tz or "Europe/Rome"

    def _default_alarm_ids(self):
        alarms = self.env["calendar.alarm"]
        for xmlid in ("calendar.alarm_mail_1_day", "calendar.alarm_mail_1"):
            alarms |= self.env.ref(xmlid, raise_if_not_found=False) or alarms.browse()
        return alarms

    name = fields.Char("Titolo", required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer("Colore")
    user_ids = fields.Many2many(
        "res.users", "appointment_type_res_users_rel", "type_id", "user_id", string="Persone",
        domain=[("share", "=", False)],
        help="Chi riceve gli appuntamenti. Con piu' persone, chi prenota puo' scegliere "
             "oppure l'assegnazione e' automatica tra chi e' libero.")
    assign_method = fields.Selection([
        ("choose", "Chi prenota sceglie la persona, poi l'orario"),
        ("auto", "Chi prenota sceglie l'orario, la persona e' assegnata automaticamente"),
    ], string="Assegnazione", required=True, default="auto")
    duration_minutes = fields.Integer("Durata (minuti)", required=True, default=30)
    slot_step_minutes = fields.Integer(
        "Intervallo tra gli orari proposti (minuti)", required=True, default=30,
        help="Ogni quanti minuti parte un orario proponibile: 30 propone 9:00, 9:30, 10:00...")
    buffer_minutes = fields.Integer(
        "Spaziatura (minuti)", default=10,
        help="Minuti liberi richiesti prima e dopo ogni appuntamento.")
    min_notice_hours = fields.Float(
        "Preavviso minimo (ore)", default=24.0,
        help="Non si puo' prenotare un orario piu' vicino di cosi'.")
    max_days_ahead = fields.Integer(
        "Finestra di prenotazione (giorni)", default=30,
        help="Fino a quanti giorni nel futuro si puo' prenotare.")
    cancel_limit_hours = fields.Float(
        "Cancellazione consentita fino a (ore prima)", default=12.0,
        help="Chi ha prenotato puo' cancellare o riprogrammare da solo fino a questo preavviso; "
             "0 = sempre.")
    tz = fields.Selection(_tz_get, string="Fuso orario degli orari", required=True, default=_default_tz)
    location_type = fields.Selection([
        ("online", "Videochiamata"),
        ("onsite", "Di persona"),
        ("phone", "Telefonata"),
    ], string="Dove", required=True, default="online")
    location = fields.Char("Indirizzo o indicazioni", help="Mostrato a chi prenota e nell'evento.")
    manual_confirmation = fields.Boolean(
        "Conferma manuale",
        help="La prenotazione resta in attesa finche' una persona interna la conferma; "
             "l'orario e' comunque riservato.")
    allow_guests = fields.Boolean("Consenti ospiti", help="Chi prenota puo' aggiungere altri indirizzi email.")
    create_lead = fields.Boolean(
        "Crea opportunita' nel CRM", default=True,
        help="Ogni prenotazione apre un'opportunita' assegnata alla persona che riceve l'appuntamento.")
    alarm_ids = fields.Many2many(
        "calendar.alarm", "appointment_type_calendar_alarm_rel", "type_id", "alarm_id",
        string="Promemoria", default=_default_alarm_ids)
    description = fields.Html("Introduzione", translate=True, sanitize_attributes=False,
                              help="Mostrata nella pagina pubblica sopra il calendario.")
    confirmation_message = fields.Html("Messaggio dopo la prenotazione", translate=True, sanitize_attributes=False,
                                       help="Mostrato nella pagina di conferma e nell'email.")
    slot_ids = fields.One2many("appointment.slot", "type_id", string="Orari", copy=True)
    question_ids = fields.One2many("appointment.question", "type_id", string="Domande", copy=True)
    booking_count = fields.Integer("Prenotazioni", compute="_compute_booking_count")
    pending_count = fields.Integer("In attesa", compute="_compute_booking_count")

    _duration_positive = models.Constraint(
        "CHECK (duration_minutes > 0 AND slot_step_minutes > 0)",
        "La durata e l'intervallo tra gli orari devono essere maggiori di zero.")
    _buffer_not_negative = models.Constraint(
        "CHECK (buffer_minutes >= 0 AND min_notice_hours >= 0 AND max_days_ahead >= 0 AND cancel_limit_hours >= 0)",
        "Spaziatura, preavviso, finestra e limite di cancellazione non possono essere negativi.")

    # ------------------------------------------------------------------
    # Campi calcolati
    # ------------------------------------------------------------------

    def _compute_booking_count(self):
        Event = self.env["calendar.event"]
        totals = {
            type_rec.id: count
            for type_rec, count in Event._read_group(
                [("appointment_type_id", "in", self.ids), ("appointment_state", "!=", "cancelled")],
                ["appointment_type_id"], ["__count"])
        }
        pending = {
            type_rec.id: count
            for type_rec, count in Event._read_group(
                [("appointment_type_id", "in", self.ids), ("appointment_state", "=", "pending")],
                ["appointment_type_id"], ["__count"])
        }
        for record in self:
            record.booking_count = totals.get(record.id, 0)
            record.pending_count = pending.get(record.id, 0)

    def _compute_website_url(self):
        super()._compute_website_url()
        for record in self:
            if record.id:
                record.website_url = "/appointment/%s" % self.env["ir.http"]._slug(record)

    @api.constrains("user_ids", "assign_method")
    def _check_user_ids(self):
        for record in self:
            if not record.user_ids:
                raise ValidationError(self.env._("Il tipo di appuntamento %s deve avere almeno una persona.", record.name))

    # ------------------------------------------------------------------
    # Disponibilita'
    # ------------------------------------------------------------------

    def _get_tzinfo(self):
        self.ensure_one()
        return ZoneInfo(self.tz or "UTC")

    @api.model
    def _to_utc_naive(self, aware_dt):
        return aware_dt.astimezone(UTC).replace(tzinfo=None)

    def _get_booking_window(self, now=None):
        """Primo e ultimo istante (UTC, naive) in cui si puo' iniziare un appuntamento."""
        self.ensure_one()
        now = now or fields.Datetime.now()
        first = now + timedelta(hours=self.min_notice_hours or 0.0)
        tzinfo = self._get_tzinfo()
        today_local = now.replace(tzinfo=UTC).astimezone(tzinfo).date()
        last_day = today_local + timedelta(days=self.max_days_ahead or 0)
        last = self._to_utc_naive(datetime.combine(last_day, time.max).replace(tzinfo=tzinfo))
        return first, last

    def _generate_candidate_slots(self, dt_from, dt_to):
        """Tutti gli orari previsti dalla griglia settimanale nell'intervallo (UTC, naive).

        Si scorrono i giorni nel fuso orario del tipo di appuntamento, con un giorno di
        margine per i fusi lontani, e si tengono solo gli slot che cadono nell'intervallo.
        """
        self.ensure_one()
        tzinfo = self._get_tzinfo()
        duration = timedelta(minutes=self.duration_minutes)
        step = timedelta(minutes=self.slot_step_minutes)
        lines_by_weekday = defaultdict(list)
        for line in self.slot_ids:
            lines_by_weekday[int(line.weekday)].append((line.hour_from, line.hour_to))
        day = dt_from.replace(tzinfo=UTC).astimezone(tzinfo).date() - timedelta(days=1)
        last_day = dt_to.replace(tzinfo=UTC).astimezone(tzinfo).date() + timedelta(days=1)
        slots = []
        while day <= last_day:
            for hour_from, hour_to in lines_by_weekday.get(day.weekday(), ()):
                start_local = datetime.combine(day, time(0)).replace(tzinfo=tzinfo) + timedelta(hours=hour_from)
                end_local = datetime.combine(day, time(0)).replace(tzinfo=tzinfo) + timedelta(hours=hour_to)
                current = start_local
                while current + duration <= end_local:
                    start = self._to_utc_naive(current)
                    if dt_from <= start <= dt_to:
                        slots.append((start, start + duration))
                    current += step
            day += timedelta(days=1)
        return sorted(set(slots))

    def _get_busy_intervals(self, users, dt_from, dt_to, exclude_event=None):
        """Per ogni persona, gli intervalli (UTC, naive) gia' occupati nel calendario, allargati
        della spaziatura. Contano gli eventi "occupato" attivi a cui la persona partecipa senza
        averli rifiutati, e quelli che organizza."""
        self.ensure_one()
        buffer = timedelta(minutes=self.buffer_minutes or 0)
        margin = buffer + timedelta(days=1)
        partners = users.partner_id
        domain = Domain([
            ("active", "=", True),
            ("show_as", "=", "busy"),
            ("start", "<", dt_to + margin),
            ("stop", ">", dt_from - margin),
        ]) & (
            Domain("user_id", "in", users.ids)
            | Domain("attendee_ids", "any", [("partner_id", "in", partners.ids), ("state", "!=", "declined")])
        )
        if exclude_event:
            domain &= Domain("id", "!=", exclude_event.id)
        events = self.env["calendar.event"].sudo().search(domain)
        tzinfo = self._get_tzinfo()
        busy = defaultdict(list)
        partner_to_user = {user.partner_id.id: user for user in users}
        for event in events:
            if event.allday:
                start = self._to_utc_naive(datetime.combine(event.start_date, time(0)).replace(tzinfo=tzinfo))
                stop = self._to_utc_naive(
                    datetime.combine(event.stop_date + timedelta(days=1), time(0)).replace(tzinfo=tzinfo))
            else:
                start, stop = event.start, event.stop
            interval = (start - buffer, stop + buffer)
            involved = set()
            if event.user_id in users:
                involved.add(event.user_id)
            for attendee in event.attendee_ids:
                user = partner_to_user.get(attendee.partner_id.id)
                if user and attendee.state != "declined":
                    involved.add(user)
            for user in involved:
                busy[user.id].append(interval)
        return busy

    def _get_available_slots(self, dt_from, dt_to, users=None, exclude_event=None, now=None):
        """Slot prenotabili tra dt_from e dt_to (UTC, naive): lista di dizionari
        {"start", "stop", "user_ids"} ordinata per inizio."""
        self.ensure_one()
        users = users or self.user_ids
        users = users.filtered(lambda u: u in self.user_ids)
        if not users:
            return []
        first, last = self._get_booking_window(now=now)
        dt_from = max(dt_from, first)
        dt_to = min(dt_to, last)
        if dt_from > dt_to:
            return []
        busy = self._get_busy_intervals(users, dt_from, dt_to, exclude_event=exclude_event)
        result = []
        for start, stop in self._generate_candidate_slots(dt_from, dt_to):
            free_users = [
                user.id for user in users
                if not any(b_start < stop and b_stop > start for b_start, b_stop in busy.get(user.id, ()))
            ]
            if free_users:
                result.append({"start": start, "stop": stop, "user_ids": free_users})
        return result

    def _is_slot_available(self, start, user, exclude_event=None, now=None):
        self.ensure_one()
        if user not in self.user_ids:
            return False
        slots = self._get_available_slots(start, start, users=user, exclude_event=exclude_event, now=now)
        return any(slot["start"] == start for slot in slots)

    def _pick_user(self, start, user_ids):
        """Assegnazione automatica: tra le persone libere, quella con meno prenotazioni nei
        trenta giorni intorno alla data; a parita', la prima nell'ordine del tipo."""
        self.ensure_one()
        candidates = self.user_ids.filtered(lambda u: u.id in user_ids)
        if len(candidates) <= 1:
            return candidates
        counts = {
            user.id: count
            for user, count in self.env["calendar.event"].sudo()._read_group([
                ("appointment_type_id", "=", self.id),
                ("appointment_state", "!=", "cancelled"),
                ("user_id", "in", candidates.ids),
                ("start", ">=", start - timedelta(days=15)),
                ("start", "<=", start + timedelta(days=15)),
            ], ["user_id"], ["__count"])
        }
        return min(candidates, key=lambda u: (counts.get(u.id, 0), self.user_ids.ids.index(u.id)))

    def _get_slots_for_display(self, date_from, date_to, visitor_tz, users=None, exclude_event=None):
        """Slot raggruppati per giorno nel fuso orario di chi prenota:
        {"2026-11-20": [{"start": "2026-11-20T09:00:00", "label": "10:00", "user_ids": [...]}, ...]}."""
        self.ensure_one()
        try:
            tzinfo = ZoneInfo(visitor_tz)
        except (KeyError, ValueError):
            tzinfo = self._get_tzinfo()
        dt_from = self._to_utc_naive(datetime.combine(date_from, time(0)).replace(tzinfo=tzinfo))
        dt_to = self._to_utc_naive(datetime.combine(date_to, time.max).replace(tzinfo=tzinfo))
        grouped = defaultdict(list)
        for slot in self._get_available_slots(dt_from, dt_to, users=users, exclude_event=exclude_event):
            local = slot["start"].replace(tzinfo=UTC).astimezone(tzinfo)
            grouped[local.date().isoformat()].append({
                "start": slot["start"].isoformat(timespec="seconds"),
                "label": local.strftime("%H:%M"),
                "user_ids": slot["user_ids"],
            })
        return grouped

    # ------------------------------------------------------------------
    # Prenotazione
    # ------------------------------------------------------------------

    def _find_or_create_partner(self, name, email, phone=None):
        """Il contatto di chi prenota: cercato per email, altrimenti creato."""
        Partner = self.env["res.partner"].sudo()
        normalized = email_normalize(email)
        partner = Partner.search([("email_normalized", "=", normalized)], limit=1) if normalized else Partner
        if not partner:
            partner = Partner.create({
                "name": name,
                "email": email,
                "phone": phone or False,
            })
        elif phone and not partner.phone:
            partner.phone = phone
        return partner

    def _answers_as_html(self, answers):
        """Le risposte alle domande come elenco HTML per descrizione dell'evento e CRM."""
        if not answers:
            return ""
        rows = "".join(
            "<li><strong>%s</strong>: %s</li>" % (html_escape(question.name), html_escape(value))
            for question, value in answers if value
        )
        return "<ul>%s</ul>" % rows if rows else ""

    def _create_booking(self, start, user, partner, answers=None, guest_emails=None, visitor_tz=None,
                        company_name=None):
        """Crea la prenotazione: evento in calendario, risposte, eventuale opportunita', email.

        :param start: inizio (UTC, naive)
        :param user: res.users che riceve l'appuntamento
        :param partner: res.partner di chi prenota
        :param answers: lista di (appointment.question, valore)
        :param guest_emails: elenco di email ospiti
        :param company_name: azienda o organizzazione dichiarata da chi prenota
        :return: calendar.event creato
        """
        self.ensure_one()
        if not self._is_slot_available(start, user):
            raise ValidationError(self.env._("L'orario scelto non e' piu' disponibile: scegline un altro."))
        stop = start + timedelta(minutes=self.duration_minutes)
        answers = answers or []
        state = "pending" if self.manual_confirmation else "confirmed"
        description = self._answers_as_html(answers)
        if company_name:
            description = "<p><strong>%s</strong>: %s</p>%s" % (
                html_escape(self.env._("Azienda")), html_escape(company_name), description)
        # Niente email standard del calendario (invito, assegnazione): le invia il modulo con i suoi modelli.
        Event = self.env["calendar.event"].sudo().with_context(
            dont_notify=True, mail_create_nolog=True, mail_auto_subscribe_no_notify=True, no_mail_to_attendees=True)
        event = Event.create({
            "name": "%s - %s" % (self.name, partner.name),
            "appointment_type_id": self.id,
            "appointment_state": state,
            "appointment_booker_id": partner.id,
            "appointment_token": uuid.uuid4().hex,
            "appointment_tz": visitor_tz or self.tz,
            "appointment_company_name": company_name or False,
            "appointment_guest_emails": "\n".join(guest_emails or []) or False,
            "start": start,
            "stop": stop,
            "user_id": user.id,
            "partner_ids": [Command.set([user.partner_id.id, partner.id])],
            "alarm_ids": [Command.set(self.alarm_ids.ids)],
            "location": self.location if self.location_type != "online" else False,
            "description": description or False,
            "appointment_answer_ids": [
                Command.create({"question_id": question.id, "value": value}) for question, value in answers if value
            ],
        })
        if self.location_type == "online":
            event._set_discuss_videocall_location()
        event.attendee_ids.filtered(lambda a: a.partner_id == user.partner_id).write({"state": "accepted"})
        if self.create_lead:
            event._appointment_create_lead()
        if state == "confirmed":
            event._appointment_notify("my_erp_crm_appointment.mail_template_booking_confirmed")
        else:
            event._appointment_notify("my_erp_crm_appointment.mail_template_booking_pending")
            event.activity_schedule(
                "mail.mail_activity_data_todo", user_id=user.id,
                summary=self.env._("Confermare la prenotazione di %s", partner.name),
                note=self.env._("Prenotazione in attesa per %(type)s il %(when)s.",
                                type=self.name, when=event._appointment_display_start()))
        return event

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def action_view_bookings(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("my_erp_crm_appointment.calendar_event_action_appointment")
        action["domain"] = [("appointment_type_id", "=", self.id)]
        action["context"] = {"default_appointment_type_id": self.id, "search_default_active": 1}
        return action

    def action_open_public_page(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.website_url,
            "target": "new",
        }
