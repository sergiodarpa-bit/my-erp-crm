from odoo import api, models
from odoo.fields import Domain


def _chiede_settori(domain):
    """La pagina Applicazioni chiede i "Settori" (module_type = industries): quell'elenco
    arriva da apps.odoo.com e non va toccato qui."""
    for condition in Domain(domain).iter_conditions():
        if condition.field_expr == "module_type":
            valore = condition.value
            if valore == "industries" or (isinstance(valore, (list, tuple, set)) and "industries" in valore):
                return True
    return False


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        # Niente app della versione a pagamento (to_buy) nella pagina Applicazioni, qualunque
        # sia il dominio salvato sull'azione base.open_module_tree: in produzione (21/11/2026)
        # il filtro sull'azione non c'era più e comparivano Sign, Helpdesk, Quality… con il
        # pulsante verso odoo.com. Vale solo per l'interfaccia: search() resta com'è.
        if not _chiede_settori(domain):
            domain = Domain.AND([domain, [("to_buy", "=", False)]])
        return super().web_search_read(
            domain, specification, offset=offset, limit=limit, order=order, count_limit=count_limit,
        )
