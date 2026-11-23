import base64
from io import BytesIO
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import misc
from odoo.tools.pdf import PdfReader

from odoo.addons.base.models.ir_actions_report import IrActionsReport

# Firma tracciata (PNG 1x1), come la manda il portale.
FIRMA = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


@tagged("post_install", "-at_install")
class TestFirmaPreventivi(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(misc.file_path("sign_oca/tests/empty.pdf"), "rb") as pdf:
            cls.pdf_preventivo = pdf.read()
        cls.cliente = cls.env["res.partner"].create({"name": "Maria Rossi", "email": "maria.rossi@example.com"})
        cls.clinica = cls.env["res.partner"].create({"name": "Dr. Anna Weber", "email": "anna.weber@example.com"})
        prodotto = cls.env["product.product"].create({"name": "Check-up biometrico", "list_price": 1200.0})
        cls.ordine = cls.env["sale.order"].create({
            "partner_id": cls.cliente.id,
            "order_line": [(0, 0, {"product_id": prodotto.id, "product_uom_qty": 1})],
        })

    def _invia(self, **valori):
        azione = self.ordine.action_invia_alla_firma()
        modulo = Form(self.env[azione["res_model"]].with_context(**azione["context"]))
        for campo, valore in valori.items():
            setattr(modulo, campo, valore)
        wizard = modulo.save()
        # Senza wkhtmltopdf nei test il report esce in HTML: al suo posto un PDF di una pagina.
        with patch.object(IrActionsReport, "_render_qweb_pdf", return_value=(self.pdf_preventivo, "pdf")):
            wizard.invia()
        return self.ordine._richieste_firma()

    def _firma(self, firmatario):
        dati = {}
        for chiave, campo in firmatario.request_id.signatory_data.items():
            valore = FIRMA if campo["field_type"] == "signature" else "Maria Rossi, St. Moritz, 23.11.2026"
            dati[chiave] = dict(campo, value=valore)
        firmatario.action_sign(dati)

    def test_invia_il_preventivo_con_la_pagina_delle_firme(self):
        richiesta = self._invia(firma_clinica=True, firmatario_clinica_id=self.clinica)
        self.assertEqual(len(richiesta), 1)
        self.assertEqual(richiesta.state, "0_sent")
        self.assertEqual(richiesta.record_ref, self.ordine)
        self.assertEqual(richiesta.signer_ids.partner_id, self.cliente | self.clinica)
        # Il preventivo (1 pagina) più la pagina delle firme, dove stanno tutti i campi.
        pagine = PdfReader(BytesIO(richiesta.data.content)).pages
        self.assertEqual(len(pagine), 2)
        campi = list(richiesta.signatory_data.values())
        self.assertEqual(len(campi), 6)
        for campo in campi:
            self.assertEqual(campo["page"], 2)
            self.assertTrue(campo["position_x"] >= 0 and campo["position_x"] + campo["width"] <= 100)
            self.assertTrue(campo["position_y"] >= 0 and campo["position_y"] + campo["height"] <= 100)
        per_ruolo = {r: [c["field_type"] for c in campi if c["role_id"] == r.id] for r in richiesta.signer_ids.role_id}
        for tipi in per_ruolo.values():
            self.assertEqual(sorted(tipi), ["signature", "text", "text"])
        self.assertEqual(self.ordine.state, "sent")
        self.assertEqual(self.ordine.firma_count, 1)
        self.assertIn("Inviato alla firma", self.ordine.message_ids[0].body)

    def test_firmato_il_pdf_va_sul_preventivo(self):
        richiesta = self._invia()
        self.assertEqual(richiesta.signer_ids.partner_id, self.cliente)
        self._firma(richiesta.signer_ids)
        self.assertEqual(richiesta.state, "2_signed")
        nota = self.ordine.message_ids[0]
        self.assertIn("Documento firmato da Maria Rossi", nota.body)
        self.assertEqual(nota.author_id, self.cliente)
        self.assertEqual(nota.attachment_ids.name, f"{richiesta.name} (firmato).pdf")
        self.assertEqual(nota.attachment_ids.res_model, "sale.order")
        self.assertEqual(nota.attachment_ids.raw.content, richiesta.data.content)

    def test_con_la_controfirma_si_allega_solo_alla_fine(self):
        richiesta = self._invia(firma_clinica=True, firmatario_clinica_id=self.clinica)
        cliente, clinica = richiesta.signer_ids.sorted(lambda s: s.partner_id != self.cliente)
        self._firma(cliente)
        self.assertEqual(richiesta.state, "0_sent")
        self.assertFalse(self.ordine.message_ids.attachment_ids)
        self._firma(clinica)
        self.assertEqual(richiesta.state, "2_signed")
        self.assertEqual(len(self.ordine.message_ids.attachment_ids), 1)

    def test_modello_collegato_ai_preventivi(self):
        ruolo = self.env["sign.oca.role"].create({
            "name": "Cliente del preventivo",
            "partner_selection_policy": "expression",
            "expression_partner": "{{object.partner_id.id}}",
        })
        modello = self.env["sign.oca.template"].create({
            "name": "Contratto di servizio",
            "data": base64.b64encode(self.pdf_preventivo).decode(),
            "model_id": self.env["ir.model"]._get_id("sale.order"),
            "item_ids": [(0, 0, {
                "field_id": self.env.ref("sign_oca.sign_field_signature").id,
                "role_id": ruolo.id,
                "page": 1, "position_x": 10, "position_y": 80, "width": 30, "height": 8,
            })],
        })
        azione = self.ordine.action_invia_alla_firma()
        wizard = Form(self.env[azione["res_model"]].with_context(**azione["context"]))
        # C'è un modello per i preventivi: viene proposto lui.
        self.assertEqual(wizard.documento, "modello")
        self.assertEqual(wizard.template_id, modello)
        wizard.save().invia()
        richiesta = self.ordine._richieste_firma()
        self.assertEqual(richiesta.template_id, modello)
        self.assertEqual(richiesta.name, f"Contratto di servizio - {self.ordine.name}")
        self.assertEqual(richiesta.signer_ids.partner_id, self.cliente)
        self.assertEqual(richiesta.state, "0_sent")

    def test_senza_email_non_parte(self):
        self.cliente.email = False
        with self.assertRaisesRegex(UserError, "non ha un indirizzo email"):
            self._invia()
        self.assertFalse(self.ordine._richieste_firma())
        self.assertEqual(self.ordine.state, "draft")

    def test_utente_interno_senza_email_puo_controfirmare(self):
        # Riceve la richiesta nella posta del gestionale e firma da Firma → Richieste.
        interno = self.env.ref("base.user_admin").partner_id
        interno.email = False
        richiesta = self._invia(firma_clinica=True, firmatario_clinica_id=interno)
        self.assertEqual(richiesta.signer_ids.partner_id, self.cliente | interno)

    def test_pulsante_firme(self):
        self.assertEqual(self.ordine.firma_count, 0)
        richiesta = self._invia()
        azione = self.ordine.action_view_firme()
        self.assertEqual(azione["res_model"], "sign.oca.request")
        self.assertEqual(azione["res_id"], richiesta.id)
        # Le richieste di un altro preventivo non contano.
        altro = self.ordine.copy()
        self.assertEqual(altro.firma_count, 0)
