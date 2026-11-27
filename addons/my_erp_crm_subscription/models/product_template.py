from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    abbonamento_ricorrenza = fields.Selection(
        [("mese", "Ogni mese"), ("anno", "Ogni anno")], "Abbonamento",
        help="Venduto come abbonamento: al pagamento la carta si salva in Stripe e il servizio si "
             "rinnova con addebito automatico, finché il cliente non disdice. Vuoto: si paga una "
             "volta sola.")
