import logging
from datetime import date

import requests
from lxml import etree

from odoo import api, models

_logger = logging.getLogger(__name__)

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
ECB_NS = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}


def parse_ecb_rates(xml_bytes):
    """Legge il file giornaliero BCE: restituisce (data, {codice valuta: unità per 1 EUR})."""
    root = etree.fromstring(xml_bytes)
    day = root.find(".//e:Cube[@time]", ECB_NS)
    rates = {"EUR": 1.0}
    for cube in day.findall("e:Cube[@currency]", ECB_NS):
        rates[cube.get("currency")] = float(cube.get("rate"))
    return date.fromisoformat(day.get("time")), rates


class ResCompany(models.Model):
    _inherit = "res.company"

    def _ecb_apply_rates(self, rate_date, ecb_rates):
        """Scrive i tassi delle valute attive, espressi rispetto alla valuta dell'azienda."""
        Rate = self.env["res.currency.rate"].sudo()
        currencies = self.env["res.currency"].search([])
        for company in self.filtered(lambda c: not c.parent_id):
            base = company.currency_id.name
            if base not in ecb_rates:
                _logger.warning("Valuta %s non presente nei tassi BCE: azienda %s saltata", base, company.name)
                continue
            for currency in currencies - company.currency_id:
                if currency.name not in ecb_rates:
                    continue
                value = ecb_rates[currency.name] / ecb_rates[base]
                existing = Rate.search([
                    ("currency_id", "=", currency.id),
                    ("company_id", "=", company.id),
                    ("name", "=", rate_date),
                ], limit=1)
                if existing:
                    existing.rate = value
                else:
                    Rate.create({
                        "currency_id": currency.id,
                        "company_id": company.id,
                        "name": rate_date,
                        "rate": value,
                    })

    @api.model
    def _cron_update_ecb_rates(self):
        try:
            response = requests.get(ECB_URL, timeout=30)
            response.raise_for_status()
            rate_date, ecb_rates = parse_ecb_rates(response.content)
        except Exception:
            _logger.exception("Impossibile scaricare i tassi di cambio BCE")
            return False
        self.search([])._ecb_apply_rates(rate_date, ecb_rates)
        _logger.info("Tassi di cambio BCE del %s aggiornati", rate_date)
        return True
