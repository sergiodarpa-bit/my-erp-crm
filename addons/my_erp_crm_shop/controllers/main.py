from odoo.http import request, route

from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website_sale.controllers.payment import PaymentPortal


def registra_prove_oss(order_id=None):
    """Prove del paese del cliente sul carrello della sessione, prima dei controlli del
    pagamento: il paese della connessione si conosce solo qui, nella richiesta."""
    carrello = request.cart
    if carrello and (order_id is None or carrello.id == order_id):
        # Solo il paese: country_code ripiega sul continente («EU»), che non prova nulla.
        carrello._my_erp_crm_registra_prove_oss(request.geoip.country.iso_code)


class NegozioIva(WebsiteSale):
    @route()
    def shop_payment(self, **post):
        registra_prove_oss()
        return super().shop_payment(**post)


class PagamentoNegozioIva(PaymentPortal):
    @route()
    def shop_payment_transaction(self, order_id, access_token, amount=None, **kwargs):
        # Di solito le prove sono già quelle della pagina di pagamento e non si scrive nulla;
        # servono qui per il pagamento rapido (Apple Pay, Google Pay) che salta quella pagina.
        registra_prove_oss(order_id)
        return super().shop_payment_transaction(order_id, access_token, amount=amount, **kwargs)
