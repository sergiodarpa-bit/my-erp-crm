from odoo import fields, models


class AppointmentQuestion(models.Model):
    """Una domanda posta a chi prenota, nel modulo di prenotazione."""

    _name = "appointment.question"
    _description = "Domanda di prenotazione"
    _order = "sequence, id"

    type_id = fields.Many2one("appointment.type", string="Tipo di appuntamento", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char("Domanda", required=True, translate=True)
    question_type = fields.Selection([
        ("char", "Risposta breve"),
        ("text", "Risposta lunga"),
        ("select", "Scelta da un elenco"),
        ("checkbox", "Casella da spuntare"),
    ], string="Tipo", required=True, default="char")
    options = fields.Text(
        "Opzioni", translate=True,
        help="Per la scelta da un elenco: una opzione per riga.")
    required = fields.Boolean("Obbligatoria")
    placeholder = fields.Char("Suggerimento", translate=True, help="Testo di esempio nel campo.")

    def _get_options(self):
        self.ensure_one()
        return [line.strip() for line in (self.options or "").splitlines() if line.strip()]
