import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { UpgradeBooleanField } from "@web/webclient/settings_form_view/fields/upgrade_boolean_field";

// Voci del menu utente che portano ai servizi commerciali di odoo.com: «Supporto» e «Account
// Odoo» (modulo web), «My Subscription» (modulo mysubscription, si installa da solo: confronta
// i piani di Odoo e rimanda al listino di odoo.com).
const VOCI_COMMERCIALI = ["support", "odoo_account", "mysubscription_user_menu"];
const userMenuItems = registry.category("user_menuitems");

function togliVociCommerciali() {
    for (const key of VOCI_COMMERCIALI) {
        if (userMenuItems.contains(key)) {
            userMenuItems.remove(key);
        }
    }
}

// Subito, per quelle del modulo web; e all'avvio del client, per quelle dei moduli caricati dopo
// questo (mysubscription viene dopo my_erp_crm_brand nell'ordine dei moduli).
togliVociCommerciali();
registry.category("services").add("my_erp_crm_brand_voci_commerciali", {
    start() {
        togliVociCommerciali();
    },
});

// Opzioni della versione a pagamento: l'interruttore apriva la finestra «passa a Enterprise»,
// con video e link al listino di odoo.com. Ora resta spento e basta. (Le caselle che le
// contengono sono già nascoste da brand.scss: questa è la seconda difesa.)
patch(UpgradeBooleanField.prototype, {
    async onChange(newValue) {
        if (this.isEnterprise) {
            return super.onChange(...arguments);
        }
        this.props.record.update({ [this.props.name]: false });
    },
});
