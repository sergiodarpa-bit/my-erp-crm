from markupsafe import Markup

from odoo import models


class SignOcaRequest(models.Model):
    _inherit = "sign.oca.request"

    def _check_signed(self):
        era_in_attesa = self.state == "0_sent"
        risultato = super()._check_signed()
        if era_in_attesa and self.state == "2_signed":
            self._allega_al_preventivo()
        return risultato

    def _allega_al_preventivo(self):
        """Quando tutti hanno firmato, il PDF firmato va anche sul preventivo collegato, con una
        nota. La firma arriva dal portale: si lavora come superutente, a nome di chi ha firmato
        per ultimo."""
        self.ensure_one()
        ordine = self.record_ref
        if not ordine or ordine._name != "sale.order" or not ordine.exists():
            return
        ordine = ordine.sudo()
        allegato = self.env["ir.attachment"].sudo().create({
            "name": self.env._("%s (firmato).pdf", self.name),
            "raw": self.data.content,
            "mimetype": "application/pdf",
            "res_model": ordine._name,
            "res_id": ordine.id,
        })
        ultimo = self.signer_ids.sorted("signed_on")[-1:]
        ordine.message_post(
            body=Markup("%s %s") % (
                self.env._("Documento firmato da %s:", ", ".join(self.signer_ids.partner_id.mapped("name"))),
                self._get_html_link(),
            ),
            author_id=ultimo.partner_id.id,
            attachment_ids=allegato.ids,
            subtype_xmlid="mail.mt_note",
        )
