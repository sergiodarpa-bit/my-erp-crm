from io import BytesIO
from xml.sax.saxutils import escape

from markupsafe import Markup
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import BinaryBytes
from odoo.tools.misc import format_date, formatLang
from odoo.tools.pdf import PdfReader, merge_pdf

# Pagina delle firme, in punti PDF (1/72 di pollice).
MARGINE = 56
SPAZIO_COLONNE = 28
RIENTRO = 4
# Per ogni firmatario: etichetta, campo di Firma, altezza del riquadro, obbligatorio.
CAMPI_FIRMATARIO = (
    ("Nome e cognome", "sign_oca.sign_field_name", 22, True),
    ("Luogo e data", "sign_oca.sign_field_text", 22, False),
    ("Firma", "sign_oca.sign_field_signature", 70, True),
)


class FirmaPreventivo(models.TransientModel):
    _name = "my_erp_crm.firma.preventivo"
    _description = "Invia un preventivo alla firma"

    order_id = fields.Many2one("sale.order", string="Preventivo", required=True, readonly=True)
    documento = fields.Selection(
        [
            ("preventivo", "Il preventivo, con una pagina per le firme"),
            ("modello", "Un modello di Firma (per esempio il contratto)"),
        ],
        string="Cosa firmare",
        required=True,
        default=lambda self: self._default_documento(),
    )
    template_id = fields.Many2one(
        "sign.oca.template",
        string="Modello",
        domain=[("model", "=", "sale.order")],
        default=lambda self: self._modelli_preventivi()[:1],
    )
    ha_modelli = fields.Boolean(compute="_compute_ha_modelli")
    partner_id = fields.Many2one("res.partner", string="Firma il cliente")
    firma_clinica = fields.Boolean(
        string="Firma anche la clinica",
        help="Aggiunge alla pagina delle firme lo spazio per la firma di chi rappresenta la clinica.",
    )
    firmatario_clinica_id = fields.Many2one(
        "res.partner",
        string="Firma per la clinica",
        default=lambda self: self.env.user.partner_id,
    )
    message = fields.Html(string="Messaggio")

    @api.model
    def _modelli_preventivi(self):
        return self.env["sign.oca.template"].search([("model", "=", "sale.order")])

    @api.model
    def _default_documento(self):
        return "modello" if self._modelli_preventivi() else "preventivo"

    def _compute_ha_modelli(self):
        ha_modelli = bool(self._modelli_preventivi())
        for wizard in self:
            wizard.ha_modelli = ha_modelli

    def invia(self):
        self.ensure_one()
        ordine = self.order_id
        if ordine.state == "cancel":
            raise UserError(self.env._("Il preventivo %s è annullato.", ordine.name))
        if self.documento == "modello":
            vals = self._prepara_richiesta_modello()
        else:
            vals = self._prepara_richiesta_preventivo()
        self._controlla_firmatari(vals["signer_ids"])
        richiesta = self.env["sign.oca.request"].create(vals)
        richiesta.action_send(message=self.message or "")
        if ordine.state == "draft":
            ordine.action_quotation_sent()
        ordine.message_post(
            body=Markup("%s %s") % (
                self.env._("Inviato alla firma di %s:", ", ".join(richiesta.signer_ids.partner_id.mapped("name"))),
                richiesta._get_html_link(),
            ),
            subtype_xmlid="mail.mt_note",
        )
        return {"type": "ir.actions.act_window_close"}

    def _prepara_richiesta_modello(self):
        if not self.template_id:
            raise UserError(self.env._("Scegli il modello di Firma da usare."))
        vals = self.template_id._prepare_sign_oca_request_vals_from_record(self.order_id)
        vals["name"] = f"{self.template_id.name} - {self.order_id.name}"
        if not vals["signer_ids"]:
            raise UserError(self.env._(
                "Il modello «%s» non ha firmatari: in Firma → Impostazioni → Ruoli scegli per il ruolo "
                "del cliente la politica «Espressione» con {{object.partner_id.id}}.",
                self.template_id.name,
            ))
        return vals

    def _prepara_richiesta_preventivo(self):
        ordine = self.order_id
        if not self.partner_id:
            raise UserError(self.env._("Scegli chi firma per il cliente."))
        firmatari = [(self.env.ref("sign_oca.sign_role_customer"), self.partner_id, self.env._("Il cliente"))]
        if self.firma_clinica:
            if not self.firmatario_clinica_id:
                raise UserError(self.env._("Scegli chi firma per la clinica."))
            firmatari.append((
                self.env.ref("sign_oca.sign_role_employee"),
                self.firmatario_clinica_id,
                self.env._("Per %s", ordine.company_id.name),
            ))
        preventivo, tipo = self.env["ir.actions.report"]._render_qweb_pdf("sale.action_report_saleorder", ordine.ids)
        if tipo != "pdf":
            raise UserError(self.env._("Non è stato possibile creare il PDF del preventivo %s.", ordine.name))
        pagine = PdfReader(BytesIO(preventivo)).pages
        pagina, campi = self._pagina_firme(pagine[-1].mediabox, firmatari)
        signatory_data = {}
        for numero, campo in enumerate(campi, start=1):
            campo.update(id=numero, tabindex=numero, page=len(pagine) + 1)
            signatory_data[str(numero)] = campo
        return {
            "name": f"{ordine.name} - {self.partner_id.name}",
            "record_ref": f"{ordine._name},{ordine.id}",
            "data": BinaryBytes(merge_pdf([preventivo, pagina])),
            "filename": f"{ordine.name}.pdf",
            "signatory_data": signatory_data,
            "signer_ids": [
                Command.create({"partner_id": partner.id, "role_id": ruolo.id})
                for ruolo, partner, _titolo in firmatari
            ],
        }

    def _pagina_firme(self, mediabox, firmatari):
        """Pagina da aggiungere in fondo al preventivo, grande come la sua ultima pagina, con un
        riquadro per firmatario. Restituisce il PDF della pagina e i campi di Firma, con le
        posizioni in percentuale della pagina misurate dall'angolo in alto a sinistra."""
        ordine = self.order_id
        # Date e importi come nel preventivo, nella lingua del cliente.
        env_cliente = self.with_context(lang=ordine.partner_id.lang or self.env.lang).env
        larghezza, altezza = float(mediabox.width), float(mediabox.height)
        colonna = (larghezza - 2 * MARGINE - SPAZIO_COLONNE) / 2
        grigio, bordo = HexColor("#6c757d"), HexColor("#adb5bd")
        buffer = BytesIO()
        tela = canvas.Canvas(buffer, pagesize=(larghezza, altezza))
        tela.setTitle(ordine.name)

        y = altezza - MARGINE - 16
        tela.setFont("Helvetica-Bold", 16)
        tela.drawString(MARGINE, y, self.env._("Accettazione del preventivo %s", ordine.name))
        testo = self.env._(
            "Con la firma qui sotto, %(cliente)s accetta il preventivo %(numero)s del %(data)s di "
            "%(azienda)s, per un totale di %(totale)s, alle condizioni indicate nelle pagine precedenti.",
            cliente=ordine.partner_id.name,
            numero=ordine.name,
            data=format_date(env_cliente, ordine.date_order),
            azienda=ordine.company_id.name,
            totale=formatLang(env_cliente, ordine.amount_total, currency_obj=ordine.currency_id),
        )
        paragrafo = Paragraph(escape(testo), ParagraphStyle("testo", fontName="Helvetica", fontSize=11, leading=15))
        _larghezza, altezza_testo = paragrafo.wrap(larghezza - 2 * MARGINE, altezza)
        y -= 24 + altezza_testo
        paragrafo.drawOn(tela, MARGINE, y)

        campi = []
        for indice, (ruolo, _partner, titolo) in enumerate(firmatari):
            x = MARGINE + indice * (colonna + SPAZIO_COLONNE)
            yy = y - 48
            tela.setFillColor(HexColor("#212529"))
            tela.setFont("Helvetica-Bold", 11)
            tela.drawString(x, yy, titolo)
            for etichetta, xmlid, altezza_campo, obbligatorio in CAMPI_FIRMATARIO:
                campo = self.env.ref(xmlid)
                yy -= 20
                tela.setFillColor(grigio)
                tela.setFont("Helvetica", 8)
                tela.drawString(x, yy, etichetta)
                yy -= 4 + altezza_campo
                tela.setStrokeColor(bordo)
                tela.setLineWidth(0.6)
                tela.rect(x, yy, colonna, altezza_campo)
                # Il campo sta dentro il riquadro, staccato dai bordi: Firma scrive il testo
                # e mette l'immagine della firma a filo dell'area del campo.
                campo_x, campo_y = x + RIENTRO, yy + RIENTRO
                campo_largo, campo_alto = colonna - 2 * RIENTRO, altezza_campo - 2 * RIENTRO
                campi.append({
                    "field_id": campo.id,
                    "field_type": campo.field_type,
                    "name": campo.name,
                    "role_id": ruolo.id,
                    "required": obbligatorio,
                    "placeholder": etichetta,
                    "position_x": campo_x / larghezza * 100,
                    "position_y": (altezza - campo_y - campo_alto) / altezza * 100,
                    "width": campo_largo / larghezza * 100,
                    "height": campo_alto / altezza * 100,
                    "value": False,
                    "default_value": campo.default_value,
                })
        tela.showPage()
        tela.save()
        return buffer.getvalue(), campi

    def _controlla_firmatari(self, comandi):
        senza_email = []
        for comando in comandi:
            partner = self.env["res.partner"].browse(comando[2].get("partner_id"))
            if not partner:
                raise UserError(self.env._(
                    "Manca un firmatario: controlla il cliente del preventivo e i ruoli del modello "
                    "(Firma → Impostazioni → Ruoli).",
                ))
            # Gli utenti interni ricevono la richiesta anche nella posta del gestionale e firmano
            # da Firma → Richieste; agli altri il link arriva solo per email.
            interno = any(not utente.share for utente in partner.user_ids)
            if not partner.email and not interno:
                senza_email.append(partner.name)
        if senza_email:
            raise UserError(self.env._(
                "Il link per firmare arriva per email, ma %s non ha un indirizzo email: aggiungilo nel contatto.",
                ", ".join(senza_email),
            ))
