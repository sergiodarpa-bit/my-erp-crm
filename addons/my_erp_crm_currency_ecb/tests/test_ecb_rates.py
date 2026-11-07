from datetime import date

from odoo.tests import TransactionCase, tagged

from ..models.res_company import parse_ecb_rates

SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <gesmes:subject>Reference rates</gesmes:subject>
  <Cube><Cube time="2026-11-06">
    <Cube currency="USD" rate="1.0800"/>
    <Cube currency="GBP" rate="0.8400"/>
    <Cube currency="CHF" rate="0.9400"/>
  </Cube></Cube>
</gesmes:Envelope>"""


@tagged("post_install", "-at_install")
class TestEcbRates(TransactionCase):

    def test_parse(self):
        day, rates = parse_ecb_rates(SAMPLE)
        self.assertEqual(day, date(2026, 11, 6))
        self.assertEqual(rates["EUR"], 1.0)
        self.assertEqual(rates["GBP"], 0.84)

    def test_rates_relative_to_company_currency(self):
        gbp = self.env.ref("base.GBP")
        eur = self.env.ref("base.EUR")
        eur.active = True
        company = self.env["res.company"].create({"name": "UK Test Ltd", "currency_id": gbp.id})
        day, rates = parse_ecb_rates(SAMPLE)
        company._ecb_apply_rates(day, rates)
        rate = self.env["res.currency.rate"].search([
            ("currency_id", "=", eur.id), ("company_id", "=", company.id), ("name", "=", day)])
        # 1 GBP = 1 / 0.84 EUR
        self.assertAlmostEqual(rate.rate, 1 / 0.84, places=6)
        converted = gbp._convert(84.0, eur, company, day)
        self.assertAlmostEqual(converted, 100.0, places=2)
