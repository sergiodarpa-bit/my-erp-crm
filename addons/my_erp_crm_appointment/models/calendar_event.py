from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_datetime


class CalendarEvent(models.Model):
    """Un evento in calendario nato da una prenotazione pubblica porta con se' il tipo di
    appuntamento, lo stato, chi ha prenotato, le risposte e il link di gestione."""

    _inherit = "calendar.event"

    appointment_type_id = fields.Many2one(
        "appointment.type", string="Tipo di appuntamento", index="btree_not_null", ondelete="set null")
    appointment_state = fields.Selection([
        ("pending", "In attesa di conferma"),
        ("confirmed", "Confermata"),
        ("cancelled", "Cancellata"),
    ], string="Stato prenotazione", copy=False, tracking=True)
    appointment_booker_id = fields.Many2one("res.partner", string="Prenotato da", index="btree_not_null")
    appointment_token = fields.Char("Token di gestione", copy=False, index="btree_not_null")
    appointment_tz = fields.Char("Fuso orario di chi ha prenotato")
    appointment_company_name = fields.Char("Azienda o organizzazione")
    appointment_guest_emails = fields.Text("Ospiti")
    appointment_answer_ids = fields.One2many("appointment.answer", "event_id", string="Risposte")
    appointment_cancel_reason = fields.Text("Motivo della cancellazione")
    appointment_cancelled_by = fields.Selection([
        ("customer", "Chi ha prenotato"),
        ("staff", "Personale"),
    ], string="Cancellata da")
    appointment_manage_url = fields.Char("Link di gestione", compute="_compute_appointment_manage_url")
    appointment_can_self_manage = fields.Boolean(compute="_compute_appointment_can_self_manage")

    @api.depends("appointment_token")
    def _compute_appointment_manage_url(self):
        for event in self:
            event.appointment_manage_url = (
                "%s/appointment/view/%s" % (event.get_base_url(), event.appointment_token)
                if event.appointment_token else False)

    @api.depends("appointment_state", "start", "appointment_type_id.cancel_limit_hours")
    def _compute_appointment_can_self_manage(self):
        now = fields.Datetime.now()
        for event in self:
            limit = event.appointment_type_id.cancel_limit_hours or 0.0
            event.appointment_can_self_manage = bool(
                event.appointment_state in ("pending", "confirmed")
                and event.start
                and now < event.start - timedelta(hours=limit))

    # ------------------------------------------------------------------
    # Utilita'
    # ------------------------------------------------------------------

    def _appointment_display_start(self, tz=None):
        """Inizio formattato nel fuso orario di chi ha prenotato (o in quello indicato)."""
        self.ensure_one()
        tz = tz or self.appointment_tz or self.appointment_type_id.tz or "UTC"
        return format_datetime(self.env, self.start, tz=tz, dt_format="EEEE d MMMM y, HH:mm")

    def _appointment_customer_attendees(self):
        self.ensure_one()
        return self.attendee_ids.filtered(lambda a: a.partner_id == self.appointment_booker_id)

    def _appointment_notify(self, template_xmlid, customer_only=False):
        """Email a chi partecipa (con invito .ics) usando il modello indicato."""
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            return False
        for event in self:
            attendees = event._appointment_customer_attendees() if customer_only else event.attendee_ids
            attendees.sudo().with_context(no_mail_to_attendees=False)._notify_attendees(
                template, notify_author=True, force_send=True)
        return True

    def _appointment_create_lead(self):
        """Un'opportunita' nel CRM per ogni prenotazione, assegnata a chi riceve l'appuntamento."""
        Lead = self.env["crm.lead"].sudo()
        for event in self:
            if event.opportunity_id or not event.appointment_type_id:
                continue
            partner = event.appointment_booker_id
            lead = Lead.create({
                "name": "%s - %s" % (event.appointment_type_id.name, partner.name),
                "type": "opportunity",
                "partner_id": partner.id,
                "user_id": event.user_id.id,
                "email_from": partner.email,
                "phone": partner.phone,
                "partner_name": event.appointment_company_name or False,
                "description": self.env._("Prenotazione dal sito per il %s.", event._appointment_display_start())
                + (event.description or ""),
            })
            event.opportunity_id = lead

    # ------------------------------------------------------------------
    # Azioni sulla prenotazione
    # ------------------------------------------------------------------

    def action_appointment_confirm(self):
        for event in self:
            if event.appointment_state != "pending":
                raise UserError(self.env._("Solo una prenotazione in attesa puo' essere confermata."))
            event.appointment_state = "confirmed"
            event.activity_feedback(["mail.mail_activity_data_todo"])
            event._appointment_notify("my_erp_crm_appointment.mail_template_booking_confirmed")
        return True

    def action_appointment_cancel(self, reason=None, cancelled_by="staff"):
        for event in self:
            if event.appointment_state == "cancelled":
                continue
            event.write({
                "appointment_state": "cancelled",
                "appointment_cancel_reason": reason or False,
                "appointment_cancelled_by": cancelled_by,
            })
            event.activity_unlink(["mail.mail_activity_data_todo"])
            event._appointment_notify("my_erp_crm_appointment.mail_template_booking_cancelled")
            # Archiviato: non occupa piu' il calendario e non blocca nuovi slot.
            event.active = False
        return True

    def action_appointment_cancel_from_form(self):
        self.ensure_one()
        return self.action_appointment_cancel(cancelled_by="staff")

    def _appointment_reschedule(self, start, cancelled_by="customer"):
        """Sposta la prenotazione a un nuovo orario libero della stessa persona."""
        self.ensure_one()
        if self.appointment_state not in ("pending", "confirmed"):
            raise ValidationError(self.env._("Questa prenotazione non puo' essere riprogrammata."))
        apt_type = self.appointment_type_id
        if not apt_type._is_slot_available(start, self.user_id, exclude_event=self):
            raise ValidationError(self.env._("L'orario scelto non e' piu' disponibile: scegline un altro."))
        self.with_context(dont_notify=True, skip_attendee_notification=True).write({
            "start": start,
            "stop": start + timedelta(minutes=apt_type.duration_minutes),
        })
        self.attendee_ids.filtered(lambda a: a.partner_id == self.user_id.partner_id).write({"state": "accepted"})
        self._appointment_notify("my_erp_crm_appointment.mail_template_booking_rescheduled")
        return True

    def action_open_manage_page(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": self.appointment_manage_url, "target": "new"}
