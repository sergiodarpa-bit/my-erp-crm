from odoo import fields, models


class AppointmentAnswer(models.Model):
    """La risposta di chi ha prenotato a una domanda, legata all'evento in calendario."""

    _name = "appointment.answer"
    _description = "Risposta di prenotazione"
    _order = "id"

    event_id = fields.Many2one("calendar.event", string="Prenotazione", required=True, ondelete="cascade", index=True)
    question_id = fields.Many2one("appointment.question", string="Domanda", required=True, ondelete="cascade")
    question_name = fields.Char("Testo della domanda", related="question_id.name")
    value = fields.Text("Risposta")
