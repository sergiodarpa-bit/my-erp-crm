import { registry } from "@web/core/registry";

// Dopo l'accesso si apre la Panoramica; la tessera del CRM porta il numero delle opportunità
// aperte, il clic sul numero apre l'elenco, il clic sulla tessera apre l'app.
registry.category("web_tour.tours").add("my_erp_crm_panoramica", {
    steps: () => [
        {
            content: "La pagina dopo l'accesso è la Panoramica",
            trigger: ".o_my_erp_crm_panoramica .o_panoramica_testa h1",
        },
        {
            content: "Nessuna tessera per la Panoramica stessa",
            trigger: ".o_my_erp_crm_panoramica:not(:has([data-menu-xmlid='my_erp_crm_home.menu_panoramica']))",
        },
        {
            content: "Il numero delle opportunità aperte",
            trigger: ".o_panoramica_app[data-menu-xmlid='crm.crm_menu_root'] .o_panoramica_valore:contains(1)",
        },
        {
            content: "Il clic sul numero apre l'elenco",
            trigger: ".o_panoramica_app[data-menu-xmlid='crm.crm_menu_root'] .o_panoramica_numero",
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_cell:contains(Opportunità della prova Panoramica)",
        },
        {
            content: "Si torna alla Panoramica dalle briciole di pane",
            trigger: ".o_breadcrumb .breadcrumb-item a:contains(Panoramica)",
            run: "click",
        },
        {
            content: "Il clic sulla tessera apre l'app",
            trigger: ".o_panoramica_app[data-menu-xmlid='crm.crm_menu_root']",
            run: "click",
        },
        {
            trigger: ".o_main_navbar .o_menu_brand:contains(CRM)",
        },
    ],
});
