import { patch } from "@web/core/utils/patch";
import { LeadGenerationDropdown } from "@crm/components/lead_generation_dropdown/lead_generation_dropdown";

// «Genera contatti»: fuori le voci che vendono servizi di Odoo S.A.
// - crm_iap_mine: «Lead Sourcing», ricerca di aziende pagata con i crediti IAP di Odoo;
// - «Mail Plugins»: apre una finestra con il video promozionale dei plugin di posta.
const VOCI_COMMERCIALI = new Set(["crm_iap_mine", "Mail Plugins"]);

patch(LeadGenerationDropdown.prototype, {
    setup() {
        super.setup();
        this.state.dropdownContentElements = this.state.dropdownContentElements.filter(
            (voce) => !VOCI_COMMERCIALI.has(voce.moduleName)
        );
    },
});
