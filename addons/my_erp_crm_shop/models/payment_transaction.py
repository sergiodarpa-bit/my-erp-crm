from markupsafe import Markup

from odoo import Command, models
from odoo.exceptions import UserError


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _invoice_sale_orders(self):
        """Fattura automatica al pagamento: una fattura che le regole IVA non lasciano emettere
        non deve far fallire l'elaborazione del pagamento. Senza questo l'errore annulla tutto:
        il cliente ha pagato, ma l'ordine non risulta confermato e il pagamento non registrato
        (il controllo si ripete per un giorno, poi si ferma). La fattura resta in bozza, fuori
        dalla transazione, con un'attività per chi la deve sistemare; il pagamento si registra
        come acconto del cliente, da abbinare alla fattura quando sarà confermata."""
        super()._invoice_sale_orders()
        for tx in self:
            for fattura in tx.invoice_ids.filtered(lambda move: move.state == "draft"):
                try:
                    with self.env.cr.savepoint():
                        fattura._check_vat_treatment()
                except UserError as errore:
                    # Solo un legame nel database, rifatto uguale se si ripete l'elaborazione:
                    # nessuna chiamata al fornitore di pagamento, si può annullare senza danni.
                    tx.with_context(payment_safe_write=True).invoice_ids = [Command.unlink(fattura.id)]
                    fattura._my_erp_crm_segnala_fattura_sospesa(tx, errore.args[0])


class AccountMove(models.Model):
    _inherit = "account.move"

    def _my_erp_crm_segnala_fattura_sospesa(self, tx, motivo):
        self.ensure_one()
        ordini = self.invoice_line_ids.sale_line_ids.order_id
        responsabile = (self.invoice_user_id or ordini.user_id[:1] or ordini.team_id.user_id[:1]
                        or self.env.ref("base.user_admin"))
        nota = Markup("<p>%s</p><p>%s</p>") % (
            self.env._("Pagamento online %(ref)s ricevuto, ma la fattura non si può emettere:",
                       ref=tx.reference),
            motivo,
        )
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            summary=self.env._("Fattura da completare (IVA)"),
            note=nota + Markup("<p>%s</p>") % self.env._(
                "Sistema il trattamento IVA, conferma la fattura e abbinala al pagamento, che è già "
                "registrato come acconto del cliente."),
            user_id=responsabile.id,
        )
        for ordine in ordini:
            ordine.message_post(body=nota)
