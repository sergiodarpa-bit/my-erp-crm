import { registry } from "@web/core/registry";

// Voci del menu utente che portano ai servizi commerciali di odoo.com.
const userMenuItems = registry.category("user_menuitems");
for (const key of ["support", "odoo_account"]) {
    if (userMenuItems.contains(key)) {
        userMenuItems.remove(key);
    }
}
