from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


@tagged("post_install", "-at_install")
class TestVatRules(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.vat_check_vies = True
        cls.de = cls.env.ref("base.de")
        Fpos = cls.env["account.fiscal.position"]
        cls.fp_rc = Fpos.create({"name": "EU B2B RC", "auto_apply": True, "vat_required": True,
                                 "vies_required": True, "country_group_id": cls.env.ref("base.europe").id,
                                 "sequence": 1})
        cls.fp_oss = Fpos.create({"name": "EU B2C DE", "auto_apply": True, "country_id": cls.de.id,
                                  "oss_location_proofs_required": True, "sequence": 2})
        cls.tax = cls.env["account.tax"].create({"name": "Test 20%", "amount": 20, "type_tax_use": "sale"})
        cls.product = cls.env["product.product"].create({"name": "Servizio", "list_price": 100,
                                                          "taxes_id": [Command.set(cls.tax.ids)]})

    def _partner(self, vat, payload):
        with patch("odoo.addons.my_erp_crm_iva.models.res_partner.requests.get",
                   return_value=FakeResponse(payload)) as mocked:
            partner = self.env["res.partner"].create({"name": "Cliente DE", "country_id": self.de.id, "vat": vat})
            partner.flush_recordset()
        return partner, mocked

    def _invoice(self, partner, **extra):
        return self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": partner.id,
            "invoice_line_ids": [Command.create({"product_id": self.product.id, "quantity": 1})],
            **extra,
        })

    def test_vies_valid_gives_reverse_charge_with_proof(self):
        partner, mocked = self._partner("DE123456788", {"isValid": True, "userError": "VALID", "name": "MUSTER GMBH"})
        self.assertIn("/ms/DE/vat/123456788", mocked.call_args.args[0])
        self.assertTrue(partner.vies_valid)
        self.assertEqual(partner.vies_check_result, "valid")
        self.assertEqual(partner.vies_check_name, "MUSTER GMBH")
        invoice = self._invoice(partner)
        self.assertEqual(invoice.fiscal_position_id, self.fp_rc)
        invoice.action_post()
        self.assertIn("VIES: DE123456788 valida", invoice.vat_treatment_proof)
        self.assertIn("MUSTER GMBH", invoice.vat_treatment_proof)

    def test_vies_invalid_falls_back_to_consumer(self):
        partner, _mocked = self._partner("DE123456788", {"isValid": False, "userError": "INVALID"})
        self.assertFalse(partner.vies_valid)
        self.assertEqual(partner.vies_check_result, "invalid")
        invoice = self._invoice(partner)
        self.assertEqual(invoice.fiscal_position_id, self.fp_oss)

    def test_vies_unreachable_is_not_valid(self):
        partner, _mocked = self._partner("DE123456788", {"isValid": False, "userError": "MS_UNAVAILABLE"})
        self.assertEqual(partner.vies_check_result, "fault")
        self.assertEqual(self._invoice(partner).fiscal_position_id, self.fp_oss)

    def test_oss_requires_two_location_proofs(self):
        partner = self.env["res.partner"].create({"name": "Privato DE", "country_id": self.de.id})
        invoice = self._invoice(partner)
        self.assertEqual(invoice.fiscal_position_id, self.fp_oss)
        with self.assertRaises(UserError):
            invoice.action_post()
        invoice.write({"oss_location_proof_1": "Indirizzo: Berlino", "oss_location_proof_2": "Carta emessa in DE"})
        invoice.action_post()
        self.assertIn("OSS DE", invoice.vat_treatment_proof)

    def test_reverse_charge_forced_without_vies_is_blocked(self):
        partner = self.env["res.partner"].create({"name": "Azienda DE", "country_id": self.de.id})
        invoice = self._invoice(partner, fiscal_position_id=self.fp_rc.id)
        with self.assertRaises(UserError):
            invoice.action_post()

    def test_no_country_no_invoice(self):
        partner = self.env["res.partner"].create({"name": "Senza paese"})
        with self.assertRaises(UserError):
            self._invoice(partner).action_post()

    def test_line_without_tax_is_blocked(self):
        partner = self.env["res.partner"].create({"name": "Cliente UK", "country_id": self.env.ref("base.uk").id})
        invoice = self._invoice(partner)
        invoice.invoice_line_ids.tax_ids = False
        with self.assertRaises(UserError):
            invoice.action_post()
