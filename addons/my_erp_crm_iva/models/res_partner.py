import logging

import requests

from odoo import fields, models

_logger = logging.getLogger(__name__)

VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{country}/vat/{number}"


class ResPartner(models.Model):
    _inherit = "res.partner"

    vies_check_result = fields.Selection(
        [("valid", "Valida"), ("invalid", "Non valida"), ("fault", "Servizio non raggiungibile")],
        string="Esito VIES", readonly=True, copy=False, tracking=True)
    vies_check_date = fields.Datetime(string="Data verifica VIES", readonly=True, copy=False)
    vies_check_name = fields.Char(string="Nome registrato in VIES", readonly=True, copy=False)

    # --- verifica diretta sul servizio VIES della Commissione europea -------------------
    def _check_vies_validity_iap(self):
        """Sostituisce la verifica tramite il servizio di Odoo S.A. (vies.api.odoo.com) con la
        chiamata diretta al servizio pubblico VIES. Restituisce 'valid', 'invalid' o 'fault'."""
        self.ensure_one()
        prefix, number = self._vies_split(self.vat or "")
        country = {"GR": "EL"}.get(prefix, prefix)
        result, name = "fault", False
        if country and number:
            try:
                response = requests.get(VIES_URL.format(country=country, number=number), timeout=20)
                response.raise_for_status()
                data = response.json()
                outcome = (data.get("userError") or "").upper()
                if data.get("isValid") is True or data.get("valid") is True:
                    result = "valid"
                elif outcome == "INVALID" or data.get("isValid") is False and outcome in ("", "VALID"):
                    result = "invalid"
                name = (data.get("name") or "").strip() or False
            except (requests.exceptions.RequestException, ValueError):
                _logger.exception("Verifica VIES non riuscita per %s", self.vat)
        self.write({
            "vies_check_result": result,
            "vies_check_date": fields.Datetime.now(),
            "vies_check_name": name if name and name != "---" else False,
        })
        return result

    def action_check_vies(self):
        for partner in self.filtered("vat"):
            partner._update_vies_status(partner._check_vies_validity_iap())
        return True

    # --- inversione contabile solo con VIES valido, anche per aziende extra UE ---------
    def _get_vat_required_valid(self, company=None):
        valid = super()._get_vat_required_valid(company=company)
        if valid and company and company.vat_check_vies and self._is_eu_partner():
            # Vale l'esito VIES: quello della verifica automatica o, se il servizio non
            # risponde, quello impostato a mano e tracciato nel chatter.
            valid = self.vies_valid
        return valid

    @staticmethod
    def _vies_split(vat):
        """'DE 123 456 788' -> ('DE', '123456788'); senza prefisso -> ('', numero)."""
        vat = (vat or "").replace(" ", "").replace(".", "").replace("-", "").upper()
        if len(vat) > 2 and vat[:2].isalpha():
            return vat[:2], vat[2:]
        return "", vat

    def _is_eu_partner(self):
        self.ensure_one()
        return self.country_id in self.env.ref("base.europe").country_ids
