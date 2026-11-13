from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .appointment_type import WEEKDAYS


class AppointmentSlot(models.Model):
    """Una fascia oraria settimanale in cui un tipo di appuntamento e' prenotabile."""

    _name = "appointment.slot"
    _description = "Fascia oraria di prenotazione"
    _order = "weekday, hour_from, id"

    type_id = fields.Many2one("appointment.type", string="Tipo di appuntamento", required=True, ondelete="cascade")
    weekday = fields.Selection(WEEKDAYS, string="Giorno", required=True, default="0")
    hour_from = fields.Float("Dalle", required=True, default=9.0)
    hour_to = fields.Float("Alle", required=True, default=13.0)

    _hours_in_day = models.Constraint(
        "CHECK (hour_from >= 0 AND hour_to <= 24 AND hour_from < hour_to)",
        "La fascia oraria deve iniziare prima di finire, dentro le 24 ore.")

    @api.constrains("hour_from", "hour_to", "weekday", "type_id")
    def _check_overlap(self):
        for slot in self:
            others = slot.type_id.slot_ids.filtered(
                lambda s: s != slot and s.weekday == slot.weekday
                and s.hour_from < slot.hour_to and s.hour_to > slot.hour_from)
            if others:
                raise ValidationError(self.env._(
                    "Due fasce orarie dello stesso giorno si sovrappongono (%s).", dict(WEEKDAYS)[slot.weekday]))
