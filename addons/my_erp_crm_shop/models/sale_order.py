from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    oss_location_proof_1 = fields.Char(
        string="Prova di localizzazione 1", copy=False,
        help="Raccolta dal negozio online al pagamento: paese dell'indirizzo di fatturazione. "
             "Passa nella fattura.")
    oss_location_proof_2 = fields.Char(
        string="Prova di localizzazione 2", copy=False,
        help="Raccolta dal negozio online al pagamento: paese della connessione del cliente "
             "(dall'indirizzo IP, che non viene conservato). Passa nella fattura.")

    # --- prove di localizzazione OSS raccolte al checkout --------------------------------

    def _my_erp_crm_registra_prove_oss(self, paese_ip):
        """Registra sul carrello le due prove del paese del cliente: il paese dell'indirizzo di
        fatturazione e quello della connessione. Si chiama dal controller, che conosce la
        richiesta; senza paese della connessione la seconda prova resta vuota."""
        self.ensure_one()
        fatturazione = self.partner_invoice_id.country_id.code
        valori = {
            "oss_location_proof_1": fatturazione and f"Indirizzo di fatturazione: {fatturazione}",
            "oss_location_proof_2": paese_ip and f"Connessione del cliente (IP): {paese_ip.upper()}",
        }
        if any(self[campo] != valore for campo, valore in valori.items()):
            self.write(valori)

    def _prepare_invoice(self):
        valori = super()._prepare_invoice()
        if self.oss_location_proof_1 or self.oss_location_proof_2:
            valori.update(oss_location_proof_1=self.oss_location_proof_1,
                          oss_location_proof_2=self.oss_location_proof_2)
        return valori

    # --- niente pagamento per un carrello che non si potrebbe fatturare ------------------

    def _is_cart_ready_for_payment(self):
        pronto = super()._is_cart_ready_for_payment()
        return self._my_erp_crm_trattamento_iva_ammesso() and pronto

    def _my_erp_crm_trattamento_iva_ammesso(self):
        """Gli stessi controlli che my_erp_crm_iva fa alla conferma della fattura, fatti sul
        carrello prima del pagamento, con un messaggio per il cliente. Senza questo controllo
        il cliente pagherebbe e la fattura automatica non si potrebbe emettere."""
        self.ensure_one()
        self._my_erp_crm_aggiorna_posizione_fiscale()
        fpos = self.fiscal_position_id
        cliente = self.partner_invoice_id.commercial_partner_id
        ammesso = True

        bloccate = self._my_erp_crm_righe_non_vendibili()
        if bloccate:
            bloccate._add_danger_alert(self.env._(
                "This service cannot be purchased online from your country yet."))
            self._add_blocking_alert(self.env._(
                "Some services in your cart cannot be sold online to private customers in your "
                "country yet. If you are buying for a business, add your VAT number to your "
                "billing address; otherwise, please contact us to complete your order."))
            ammesso = False

        senza_imposta = self._my_erp_crm_righe_senza_imposta()
        if senza_imposta:
            senza_imposta._add_danger_alert(self.env._(
                "This product cannot be purchased online at the moment."))
            self._add_blocking_alert(self.env._(
                "Some products in your cart cannot be purchased online at the moment. Please "
                "contact us to complete your order."))
            ammesso = False

        if fpos.vies_required and not (cliente.vat and cliente.vies_valid):
            self._add_blocking_alert(self.env._(
                "We could not verify your VAT number in the EU VIES register. Please check it in "
                "your billing address or contact us."))
            ammesso = False

        if fpos.oss_location_proofs_required:
            ammesso = self._my_erp_crm_prove_oss_coerenti() and ammesso

        return ammesso

    def _my_erp_crm_aggiorna_posizione_fiscale(self):
        """La posizione fiscale dipende anche dall'esito VIES del cliente, che cambia se la
        partita IVA viene aggiunta o corretta nell'indirizzo già scelto: il negozio in quel
        caso non la ricalcola. Qui si riallinea, con le imposte delle righe."""
        if self.env.cr.readonly or self.state not in ("draft", "sent") or not self.partner_id:
            return
        prevista = self.env["account.fiscal.position"].with_company(self.company_id)._get_fiscal_position(
            self.partner_id, self.partner_shipping_id)
        if prevista != self.fiscal_position_id:
            self.fiscal_position_id = prevista
            self._recompute_taxes()

    def _my_erp_crm_righe_prodotto(self):
        return self.order_line.filtered(lambda line: not line.display_type and line.product_id)

    def _my_erp_crm_righe_non_vendibili(self):
        """Righe con un'imposta che la posizione fiscale non ammette (blocked_tax_ids), come le
        verifica la fattura: l'imposta del prodotto prima della mappatura dice che cosa si vende."""
        self.ensure_one()
        bloccate = self.fiscal_position_id.blocked_tax_ids
        if not bloccate:
            return self.env["sale.order.line"]
        return self._my_erp_crm_righe_prodotto().filtered(
            lambda line: (line.tax_ids | line.product_id.taxes_id) & bloccate)

    def _my_erp_crm_righe_senza_imposta(self):
        """Senza posizione fiscale una riga senza imposta non si fattura (my_erp_crm_iva)."""
        self.ensure_one()
        if self.fiscal_position_id:
            return self.env["sale.order.line"]
        return self._my_erp_crm_righe_prodotto().filtered(lambda line: not line.tax_ids)

    def _my_erp_crm_prove_oss_coerenti(self):
        """Vendite OSS: le due prove devono esserci e indicare lo stesso paese del cliente."""
        paese = self.partner_invoice_id.commercial_partner_id.country_id.code
        # Le prove finiscono con il codice del paese («… (IP): DE»).
        fatturazione = (self.oss_location_proof_1 or "").rpartition(" ")[2]
        connessione = (self.oss_location_proof_2 or "").rpartition(" ")[2]
        if not connessione:
            self._add_blocking_alert(self.env._(
                "We could not confirm your country from your internet connection, which is "
                "required for this purchase. Please contact us to complete your order."))
            return False
        if not (paese and paese == fatturazione == connessione):
            self._add_blocking_alert(self.env._(
                "The country of your billing address (%(billing)s) does not match the country "
                "of your internet connection (%(connection)s). Please check your billing address "
                "or contact us to complete your order.",
                billing=fatturazione or "?", connection=connessione))
            return False
        return True
