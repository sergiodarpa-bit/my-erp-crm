import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

const MONTHS = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
];
const WEEKDAYS_LONG = ["domenica", "lunedi'", "martedi'", "mercoledi'", "giovedi'", "venerdi'", "sabato"];

/**
 * Calendario pubblico di prenotazione: mostra i giorni del mese con orari liberi,
 * gli orari del giorno scelto e, al click, porta al modulo (o invia la riprogrammazione).
 */
export class AppointmentCalendar extends Interaction {
    static selector = ".o_appointment_calendar";
    dynamicContent = {
        ".o_appointment_prev": { "t-on-click": () => this.changeMonth(-1) },
        ".o_appointment_next": { "t-on-click": () => this.changeMonth(1) },
        ".o_appointment_tz": { "t-on-change": (ev) => this.changeTz(ev) },
        ".o_appointment_days": { "t-on-click": (ev) => this.onDayClick(ev) },
        ".o_appointment_slots": { "t-on-click": (ev) => this.onSlotClick(ev) },
    };

    setup() {
        const data = this.el.dataset;
        this.typeId = parseInt(data.typeId);
        this.hostId = data.hostId || "";
        this.tz = data.tz;
        this.bookUrl = data.bookUrl;
        this.rescheduleToken = data.rescheduleToken || "";
        const today = new Date(data.today + "T00:00:00");
        this.year = today.getFullYear();
        this.month = today.getMonth() + 1;
        this.todayIso = data.today;
        this.slots = {};
        this.selectedDay = null;
        this.monthTitleEl = this.el.querySelector(".o_appointment_month_title");
        this.daysEl = this.el.querySelector(".o_appointment_days");
        this.slotsEl = this.el.querySelector(".o_appointment_slots");
        this.dayTitleEl = this.el.querySelector(".o_appointment_day_title");
        this.loadingEl = this.el.querySelector(".o_appointment_loading");
        this.emptyEl = this.el.querySelector(".o_appointment_empty");
        this.prevEl = this.el.querySelector(".o_appointment_prev");
    }

    async willStart() {
        await this.loadMonth();
    }

    async loadMonth() {
        this.loadingEl.classList.remove("d-none");
        this.emptyEl.classList.add("d-none");
        const params = { type_id: this.typeId, year: this.year, month: this.month, tz: this.tz };
        if (this.rescheduleToken) {
            params.token = this.rescheduleToken;
        } else if (this.hostId && this.hostId !== "any") {
            params.host_id = parseInt(this.hostId);
        }
        const result = await this.waitFor(rpc(`/appointment/${this.typeId}/slots`, params));
        this.slots = result.slots || {};
        this.loadingEl.classList.add("d-none");
        const days = Object.keys(this.slots).sort();
        this.selectedDay = days.length ? days[0] : null;
        this.emptyEl.classList.toggle("d-none", days.length > 0);
        this.renderMonth();
        this.renderSlots();
    }

    renderMonth() {
        this.monthTitleEl.textContent = `${MONTHS[this.month - 1]} ${this.year}`;
        const isCurrentMonth = this.todayIso.startsWith(`${this.year}-${String(this.month).padStart(2, "0")}`);
        this.prevEl.disabled = isCurrentMonth;
        this.removeChildren(this.daysEl, false);
        const first = new Date(this.year, this.month - 1, 1);
        const offset = (first.getDay() + 6) % 7; // il lunedi' e' la prima colonna
        const daysInMonth = new Date(this.year, this.month, 0).getDate();
        const fragment = document.createElement("div");
        fragment.className = "o_appointment_contents";
        for (let i = 0; i < offset; i++) {
            const filler = document.createElement("span");
            filler.className = "o_appointment_day o_appointment_day_filler";
            filler.setAttribute("aria-hidden", "true");
            fragment.appendChild(filler);
        }
        for (let day = 1; day <= daysInMonth; day++) {
            const iso = `${this.year}-${String(this.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
            const available = (this.slots[iso] || []).length;
            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn o_appointment_day";
            button.dataset.day = iso;
            button.textContent = String(day);
            button.setAttribute("role", "gridcell");
            if (available) {
                button.classList.add("o_appointment_day_available");
                button.setAttribute("aria-label", `${day} ${MONTHS[this.month - 1]}, ${available} orari liberi`);
            } else {
                button.disabled = true;
                button.setAttribute("aria-label", `${day} ${MONTHS[this.month - 1]}, nessun orario`);
            }
            if (iso === this.selectedDay) {
                button.classList.add("active");
                button.setAttribute("aria-pressed", "true");
            }
            fragment.appendChild(button);
        }
        this.insert(fragment, this.daysEl);
    }

    renderSlots() {
        this.removeChildren(this.slotsEl, false);
        if (!this.selectedDay) {
            this.dayTitleEl.textContent = "Scegli un giorno";
            return;
        }
        const date = new Date(this.selectedDay + "T00:00:00");
        this.dayTitleEl.textContent =
            `${WEEKDAYS_LONG[date.getDay()]} ${date.getDate()} ${MONTHS[date.getMonth()]}`;
        const fragment = document.createElement("div");
        fragment.className = "o_appointment_contents";
        for (const slot of this.slots[this.selectedDay] || []) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn btn-outline-primary o_appointment_slot";
            button.dataset.start = slot.start;
            button.textContent = slot.label;
            button.setAttribute("role", "listitem");
            fragment.appendChild(button);
        }
        this.insert(fragment, this.slotsEl);
    }

    changeMonth(delta) {
        let month = this.month + delta;
        let year = this.year;
        if (month < 1) {
            month = 12;
            year -= 1;
        } else if (month > 12) {
            month = 1;
            year += 1;
        }
        this.month = month;
        this.year = year;
        this.loadMonth();
    }

    changeTz(ev) {
        const url = new URL(window.location.href);
        url.searchParams.set("tz", ev.currentTarget.value);
        window.location.assign(url.toString());
    }

    onDayClick(ev) {
        const button = ev.target.closest(".o_appointment_day_available");
        if (!button) {
            return;
        }
        this.selectedDay = button.dataset.day;
        for (const el of this.daysEl.querySelectorAll(".o_appointment_day")) {
            const active = el.dataset.day === this.selectedDay;
            el.classList.toggle("active", active);
            el.setAttribute("aria-pressed", active ? "true" : "false");
        }
        this.renderSlots();
    }

    onSlotClick(ev) {
        const button = ev.target.closest(".o_appointment_slot");
        if (!button) {
            return;
        }
        const start = button.dataset.start;
        if (this.rescheduleToken) {
            const form = this.el.querySelector(".o_appointment_reschedule_form");
            form.querySelector("input[name='start']").value = start;
            form.querySelector("input[name='tz']").value = this.tz;
            form.submit();
            return;
        }
        const url = new URL(this.bookUrl, window.location.origin);
        url.searchParams.set("start", start);
        url.searchParams.set("tz", this.tz);
        if (this.hostId) {
            url.searchParams.set("host", this.hostId);
        }
        window.location.assign(url.toString());
    }
}

registry.category("public.interactions").add("my_erp_crm_appointment.calendar", AppointmentCalendar);
