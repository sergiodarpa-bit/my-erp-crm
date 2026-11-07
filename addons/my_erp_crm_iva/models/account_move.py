from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    oss_location_proof_1 = fields.Char(
        string="Prova di localizzazione 1", copy=False,
        help="Es. indirizzo di fatturazione, paese della carta di pagamento, indirizzo IP.")
    oss_location_proof_2 = fields.Char(string="Prova di localizzazione 2", copy=False)
    vat_treatment_proof = fields.Text(
        string="Prove del trattamento IVA", readonly=True, copy=False,
        help="Registrate alla conferma della fattura (INV-IVA-09).")

    def _post(self, soft=True):
        for move in self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund")):
            move._check_vat_treatment()
        return super()._post(soft=soft)

    def _check_vat_treatment(self):
        """Invarianti dello studio IVA: niente fattura senza trattamento determinato."""
        self.ensure_one()
        partner = self.commercial_partner_id
        if not partner.country_id:
            raise UserError(_(
                "Fattura %(name)s: manca il paese del cliente %(partner)s. Senza paese il "
                "trattamento IVA non è determinabile e la fattura non si emette.",
                name=self.name or "", partner=partner.display_name))
        missing = self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product" and not line.tax_ids)
        if missing:
            raise UserError(_(
                "Fattura %(name)s: le righe %(lines)s non hanno un'imposta. Ogni riga deve avere "
                "un trattamento IVA esplicito (anche esente o 0%%).",
                name=self.name or "",
                lines=", ".join(line.name or line.product_id.display_name or "?" for line in missing)))

        proofs = []
        fpos = self.fiscal_position_id
        if fpos.vies_required:
            if not (partner.vat and partner.vies_valid and partner.vies_check_result == "valid"):
                raise UserError(_(
                    "Fattura %(name)s: l'inversione contabile richiede la partita IVA del cliente "
                    "verificata in VIES. Verifica la partita IVA di %(partner)s (pulsante "
                    "\"Verifica VIES\" sul contatto) o tratta il cliente come privato.",
                    name=self.name or "", partner=partner.display_name))
            proofs.append(_(
                "VIES: %(vat)s valida, verificata il %(date)s%(registered)s",
                vat=partner.vat,
                date=fields.Datetime.to_string(partner.vies_check_date),
                registered=f" ({partner.vies_check_name})" if partner.vies_check_name else ""))
        if fpos.oss_location_proofs_required:
            if not (self.oss_location_proof_1 and self.oss_location_proof_2):
                raise UserError(_(
                    "Fattura %(name)s: le vendite OSS a privati UE richiedono due prove di "
                    "localizzazione del cliente (scheda Altre informazioni).",
                    name=self.name or ""))
            proofs.append(_(
                "OSS %(country)s: prove di localizzazione «%(p1)s» e «%(p2)s»",
                country=partner.country_id.code, p1=self.oss_location_proof_1, p2=self.oss_location_proof_2))
        if fpos:
            proofs.insert(0, _("Posizione fiscale: %s", fpos.name))
        self.vat_treatment_proof = "\n".join(proofs) or False
