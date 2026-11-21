import { Component, onWillStart, proxy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

const MENU_PANORAMICA = "my_erp_crm_home.menu_panoramica";
const ICONA_PREDEFINITA = "/web/static/img/default_icon_app.png";

/**
 * Pagina iniziale: una tessera per ogni app del menu (quelle che l'utente vede) e, dove c'è,
 * un numero chiave calcolato dal server (my_erp_crm.panoramica.numeri).
 */
export class Panoramica extends Component {
    static template = "my_erp_crm_home.Panoramica";

    setup() {
        this.menu = useService("menu");
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = proxy({ numeri: {} });
        onWillStart(async () => {
            this.state.numeri = await this.orm.call("my_erp_crm.panoramica", "numeri", []);
        });
    }

    get saluto() {
        const ora = new Date().getHours();
        const parola = ora < 13 ? "Buongiorno" : ora < 18 ? "Buon pomeriggio" : "Buonasera";
        return `${parola}, ${user.name}`;
    }

    get oggi() {
        const lingua = (user.lang || "it_IT").replace("_", "-");
        return new Date().toLocaleDateString(lingua, {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
        });
    }

    get app() {
        return this.menu.getApps().filter((app) => app.xmlid !== MENU_PANORAMICA);
    }

    numero(app) {
        return this.state.numeri[app.id];
    }

    icona(app) {
        return app.webIconData || ICONA_PREDEFINITA;
    }

    apriApp(app) {
        this.menu.selectMenu(app);
    }

    alTasto(ev, app) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.apriApp(app);
        }
    }

    apriNumero(app) {
        const numero = this.numero(app);
        this.action.doAction({
            type: "ir.actions.act_window",
            name: numero.titolo,
            res_model: numero.modello,
            domain: numero.dominio,
            views: [
                [false, "list"],
                [false, "form"],
            ],
        });
    }
}

registry.category("actions").add("my_erp_crm_home.panoramica", Panoramica);
