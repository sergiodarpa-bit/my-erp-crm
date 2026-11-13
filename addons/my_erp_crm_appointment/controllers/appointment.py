import logging
from datetime import date, datetime, timedelta

import werkzeug.exceptions
import werkzeug.urls

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
from odoo.http import request
from odoo.tools import email_normalize
from odoo.tools.misc import format_datetime

_logger = logging.getLogger(__name__)


class AppointmentController(http.Controller):
    """Pagine pubbliche di prenotazione: elenco, scelta della persona, calendario, modulo,
    pagina di gestione con cancellazione e riprogrammazione."""

    # ------------------------------------------------------------------
    # Utilita'
    # ------------------------------------------------------------------

    def _get_published_types(self):
        website = request.env.website
        domain = Domain("is_published", "=", True) & website.website_domain()
        return request.env["appointment.type"].sudo().search(domain)

    def _check_type(self, apt_type):
        """Il tipo deve essere pubblicato sul sito corrente (gli interni lo vedono comunque)."""
        apt_type = apt_type.sudo()
        if not apt_type.exists() or not apt_type.active:
            raise werkzeug.exceptions.NotFound()
        if apt_type.website_id and apt_type.website_id != request.env.website:
            raise werkzeug.exceptions.NotFound()
        if not apt_type.is_published and not request.env.user._is_internal():
            raise werkzeug.exceptions.NotFound()
        return apt_type

    def _get_visitor_tz(self, apt_type, requested=None):
        """Il fuso orario per mostrare gli orari: quello chiesto, poi quello dell'utente, poi
        quello del tipo di appuntamento."""
        candidates = [requested, request.env.user.tz if not request.env.user._is_public() else None, apt_type.tz]
        valid = dict(request.env["appointment.type"]._fields["tz"]._description_selection(request.env))
        for candidate in candidates:
            if candidate and candidate in valid:
                return candidate
        return "UTC"

    def _get_host(self, apt_type, host_id):
        if not host_id:
            # Con una sola persona non c'e' nulla da scegliere.
            return apt_type.user_ids if len(apt_type.user_ids) == 1 else request.env["res.users"]
        try:
            host = request.env["res.users"].sudo().browse(int(host_id)).exists()
        except (TypeError, ValueError):
            return request.env["res.users"]
        return host if host in apt_type.user_ids else request.env["res.users"]

    def _parse_start(self, value):
        try:
            return datetime.fromisoformat(value).replace(tzinfo=None)
        except (TypeError, ValueError):
            return None

    def _get_booking(self, token):
        if not token:
            raise werkzeug.exceptions.NotFound()
        event = request.env["calendar.event"].sudo().with_context(active_test=False).search([
            ("appointment_token", "=", token),
        ], limit=1)
        if not event or not event.appointment_type_id:
            raise werkzeug.exceptions.NotFound()
        return event

    def _verify_captcha(self):
        """Turnstile o reCAPTCHA se un modulo li fornisce; altrimenti niente da verificare."""
        ir_http = request.env["ir.http"]
        if hasattr(ir_http, "_verify_request_recaptcha_token"):
            ir_http._verify_request_recaptcha_token("appointment")

    def _common_values(self, apt_type, host=None, visitor_tz=None):
        return {
            "apt_type": apt_type,
            "host": host or request.env["res.users"],
            "hosts": apt_type.user_ids,
            "visitor_tz": visitor_tz or self._get_visitor_tz(apt_type),
            "timezones": request.env["appointment.type"]._fields["tz"]._description_selection(request.env),
            "today": date.today().isoformat(),
            "main_object": apt_type,
        }

    # ------------------------------------------------------------------
    # Elenco e pagina del tipo
    # ------------------------------------------------------------------

    def sitemap_appointment_types(env, rule, qs):
        """Nella mappa del sito solo i tipi pubblicati sul sito corrente."""
        slug = env["ir.http"]._slug
        domain = Domain("website_published", "=", True)
        apt_types = env["appointment.type"].sudo().search(domain, order="id")
        for apt_type in apt_types:
            loc = "/appointment/%s" % slug(apt_type)
            if not qs or qs.lower() in loc.lower():
                yield {"loc": loc}

    @http.route("/appointment", type="http", auth="public", website=True, sitemap=True, readonly=True)
    def appointment_index(self, **kwargs):
        apt_types = self._get_published_types()
        if len(apt_types) == 1 and not request.env.user._is_internal():
            return request.redirect(apt_types.website_url)
        return request.render("my_erp_crm_appointment.index", {"apt_types": apt_types})

    @http.route('/appointment/<model("appointment.type"):apt_type>', type="http", auth="public", website=True,
                sitemap=sitemap_appointment_types, readonly=True)
    def appointment_type_page(self, apt_type, host=None, tz=None, error=None, **kwargs):
        apt_type = self._check_type(apt_type)
        host_rec = self._get_host(apt_type, host)
        visitor_tz = self._get_visitor_tz(apt_type, tz)
        values = self._common_values(apt_type, host_rec, visitor_tz)
        values["error"] = error
        values["host_any"] = host == "any"
        if apt_type.assign_method == "choose" and len(apt_type.user_ids) > 1 and not host_rec and host != "any":
            return request.render("my_erp_crm_appointment.choose_host", values)
        return request.render("my_erp_crm_appointment.calendar_page", values)

    @http.route("/appointment/<int:type_id>/slots", type="jsonrpc", auth="public", website=True, readonly=True)
    def appointment_slots(self, type_id, year, month, tz=None, host_id=None, token=None):
        """Gli slot liberi di un mese, raggruppati per giorno nel fuso orario di chi guarda."""
        apt_type = self._check_type(request.env["appointment.type"].browse(type_id))
        visitor_tz = self._get_visitor_tz(apt_type, tz)
        exclude_event = None
        host = self._get_host(apt_type, host_id)
        if token:
            event = self._get_booking(token)
            if event.appointment_type_id != apt_type:
                raise werkzeug.exceptions.NotFound()
            exclude_event = event
            host = event.user_id
        try:
            first_day = date(int(year), int(month), 1)
        except (TypeError, ValueError):
            raise werkzeug.exceptions.BadRequest()
        last_day = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        users = host if host else None
        slots = apt_type._get_slots_for_display(first_day, last_day, visitor_tz, users=users, exclude_event=exclude_event)
        first, last = apt_type._get_booking_window()
        return {
            "slots": slots,
            "tz": visitor_tz,
            "window_first": first.isoformat(timespec="seconds"),
            "window_last": last.isoformat(timespec="seconds"),
        }

    # ------------------------------------------------------------------
    # Modulo e creazione della prenotazione
    # ------------------------------------------------------------------

    @http.route('/appointment/<model("appointment.type"):apt_type>/book', type="http", auth="public", website=True,
                methods=["GET"], sitemap=False, readonly=True)
    def appointment_book_form(self, apt_type, start=None, host=None, tz=None, **kwargs):
        apt_type = self._check_type(apt_type)
        start_dt = self._parse_start(start)
        visitor_tz = self._get_visitor_tz(apt_type, tz)
        host_rec = self._get_host(apt_type, host)
        if not start_dt:
            return request.redirect(apt_type.website_url)
        host_rec = self._resolve_host(apt_type, host, host_rec, start_dt)
        if not host_rec:
            return request.redirect(self._slot_error_url(apt_type, visitor_tz, host))
        values = self._common_values(apt_type, host_rec, visitor_tz)
        values.update({
            "start": start_dt,
            "start_display": self._display_start(apt_type, start_dt, visitor_tz),
            "host_param": host,
            "form_values": {},
            "form_errors": {},
            "partner": request.env.user.partner_id if not request.env.user._is_public() else None,
        })
        return request.render("my_erp_crm_appointment.booking_form", values)

    def _resolve_host(self, apt_type, host_param, host_rec, start_dt):
        """La persona che ricevera' l'appuntamento: scelta da chi prenota (se libera) oppure
        assegnata tra quelle libere; vuoto se l'orario non e' disponibile."""
        if apt_type.assign_method == "auto" or host_param == "any" or not host_rec:
            slots = apt_type._get_available_slots(start_dt, start_dt)
            free_ids = [s["user_ids"] for s in slots if s["start"] == start_dt]
            return apt_type._pick_user(start_dt, free_ids[0]) if free_ids else request.env["res.users"]
        if apt_type._is_slot_available(start_dt, host_rec):
            return host_rec
        return request.env["res.users"]

    def _slot_error_url(self, apt_type, visitor_tz, host_param):
        url = "%s?error=slot&tz=%s" % (apt_type.website_url, visitor_tz)
        if host_param and apt_type.assign_method == "choose":
            url += "&host=%s" % werkzeug.urls.url_quote(str(host_param))
        return url

    def _display_start(self, apt_type, start_dt, visitor_tz):
        return format_datetime(request.env, start_dt, tz=visitor_tz, dt_format="EEEE d MMMM y, HH:mm")

    def _validate_booking_form(self, apt_type, post):
        """Controlla i campi del modulo; restituisce (valori puliti, errori, risposte)."""
        errors = {}
        values = {
            "name": (post.get("name") or "").strip(),
            "email": (post.get("email") or "").strip(),
            "phone": (post.get("phone") or "").strip(),
            "company_name": (post.get("company_name") or "").strip(),
            "guests": (post.get("guests") or "").strip(),
        }
        if not values["name"]:
            errors["name"] = request.env._("Inserisci il tuo nome.")
        if not email_normalize(values["email"]):
            errors["email"] = request.env._("Inserisci un indirizzo email valido.")
        if not values["phone"]:
            errors["phone"] = request.env._("Inserisci un numero di telefono.")
        guest_emails = []
        if apt_type.allow_guests and values["guests"]:
            for raw in values["guests"].replace(";", ",").replace("\n", ",").split(","):
                raw = raw.strip()
                if not raw:
                    continue
                if not email_normalize(raw):
                    errors["guests"] = request.env._("Un indirizzo degli ospiti non e' valido: %s", raw)
                    break
                guest_emails.append(raw)
            if len(guest_emails) > 10:
                errors["guests"] = request.env._("Al massimo dieci ospiti.")
        answers = []
        for question in apt_type.question_ids:
            key = "question_%s" % question.id
            raw = post.get(key)
            if question.question_type == "checkbox":
                value = request.env._("Si'") if raw else ""
            elif question.question_type == "select":
                value = (raw or "").strip()
                if value and value not in question._get_options():
                    errors[key] = request.env._("Scegli una delle opzioni.")
            else:
                value = (raw or "").strip()[:2000]
            if question.required and not value:
                errors[key] = request.env._("Questa risposta e' obbligatoria.")
            values[key] = raw if question.question_type == "checkbox" else value
            answers.append((question, value))
        return values, errors, answers, guest_emails

    @http.route('/appointment/<model("appointment.type"):apt_type>/book', type="http", auth="public", website=True,
                methods=["POST"], sitemap=False, csrf=True)
    def appointment_book_submit(self, apt_type, start=None, host=None, tz=None, **post):
        apt_type = self._check_type(apt_type)
        start_dt = self._parse_start(start)
        visitor_tz = self._get_visitor_tz(apt_type, tz)
        host_rec = self._get_host(apt_type, host)
        if not start_dt:
            return request.redirect(apt_type.website_url)
        if post.get("website_hp"):
            # Campo nascosto compilato: un automatismo, non una persona.
            _logger.info("Prenotazione scartata (honeypot) per il tipo %s", apt_type.id)
            return request.redirect(apt_type.website_url)
        try:
            self._verify_captcha()
        except (UserError, ValidationError) as error:
            return self._render_form_with_error(apt_type, host_rec, start_dt, visitor_tz, post, {"captcha": str(error)})
        values, errors, answers, guest_emails = self._validate_booking_form(apt_type, post)
        if errors:
            return self._render_form_with_error(apt_type, host_rec, start_dt, visitor_tz, post, errors)
        host_rec = self._resolve_host(apt_type, host, host_rec, start_dt)
        if not host_rec:
            return request.redirect(self._slot_error_url(apt_type, visitor_tz, host))
        partner = apt_type._find_or_create_partner(values["name"], values["email"], phone=values["phone"])
        try:
            event = apt_type._create_booking(
                start_dt, host_rec, partner, answers=answers, guest_emails=guest_emails, visitor_tz=visitor_tz,
                company_name=values["company_name"])
        except ValidationError:
            return request.redirect(self._slot_error_url(apt_type, visitor_tz, host))
        return request.redirect("/appointment/view/%s?new=1" % event.appointment_token)

    def _render_form_with_error(self, apt_type, host_rec, start_dt, visitor_tz, post, errors):
        values = self._common_values(apt_type, host_rec, visitor_tz)
        values.update({
            "start": start_dt,
            "start_display": self._display_start(apt_type, start_dt, visitor_tz),
            "host_param": request.params.get("host"),
            "form_values": post,
            "form_errors": errors,
            "partner": None,
        })
        return request.render("my_erp_crm_appointment.booking_form", values)

    # ------------------------------------------------------------------
    # Pagina di gestione: dettagli, cancellazione, riprogrammazione
    # ------------------------------------------------------------------

    @http.route("/appointment/view/<string:token>", type="http", auth="public", website=True, sitemap=False, readonly=True)
    def appointment_view(self, token, new=None, rescheduled=None, **kwargs):
        event = self._get_booking(token)
        apt_type = event.appointment_type_id
        visitor_tz = self._get_visitor_tz(apt_type, event.appointment_tz)
        return request.render("my_erp_crm_appointment.manage_page", {
            "event": event,
            "apt_type": apt_type,
            "visitor_tz": visitor_tz,
            "start_display": self._display_start(apt_type, event.start, visitor_tz),
            "is_new": bool(new),
            "is_rescheduled": bool(rescheduled),
            "main_object": apt_type,
        })

    @http.route("/appointment/view/<string:token>/cancel", type="http", auth="public", website=True,
                methods=["POST"], sitemap=False, csrf=True)
    def appointment_cancel(self, token, reason=None, **kwargs):
        event = self._get_booking(token)
        if not event.appointment_can_self_manage:
            return request.redirect("/appointment/view/%s" % token)
        event.action_appointment_cancel(reason=(reason or "").strip()[:500] or None, cancelled_by="customer")
        return request.redirect("/appointment/view/%s" % token)

    @http.route("/appointment/view/<string:token>/reschedule", type="http", auth="public", website=True,
                methods=["GET"], sitemap=False, readonly=True)
    def appointment_reschedule_page(self, token, tz=None, error=None, **kwargs):
        event = self._get_booking(token)
        if not event.appointment_can_self_manage:
            return request.redirect("/appointment/view/%s" % token)
        apt_type = event.appointment_type_id
        visitor_tz = self._get_visitor_tz(apt_type, tz or event.appointment_tz)
        values = self._common_values(apt_type, event.user_id, visitor_tz)
        values.update({"event": event, "reschedule_token": token, "error": error})
        return request.render("my_erp_crm_appointment.calendar_page", values)

    @http.route("/appointment/view/<string:token>/reschedule", type="http", auth="public", website=True,
                methods=["POST"], sitemap=False, csrf=True)
    def appointment_reschedule_submit(self, token, start=None, tz=None, **kwargs):
        event = self._get_booking(token)
        if not event.appointment_can_self_manage:
            return request.redirect("/appointment/view/%s" % token)
        start_dt = self._parse_start(start)
        if not start_dt:
            return request.redirect("/appointment/view/%s/reschedule?error=slot" % token)
        try:
            event._appointment_reschedule(start_dt)
        except ValidationError:
            return request.redirect("/appointment/view/%s/reschedule?error=slot&tz=%s" % (token, tz or ""))
        if tz and tz != event.appointment_tz:
            event.appointment_tz = self._get_visitor_tz(event.appointment_type_id, tz)
        return request.redirect("/appointment/view/%s?rescheduled=1" % token)
