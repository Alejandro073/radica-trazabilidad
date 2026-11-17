from django import template

register = template.Library()


@register.filter
def cop(valor):
    """Formatea un valor como pesos colombianos: $1.234.567."""
    try:
        return "$" + f"{int(valor):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


@register.filter
def pct(valor):
    """Porcentaje con coma decimal: 12,8 %."""
    try:
        return f"{float(valor):.1f}".replace(".", ",") + " %"
    except (TypeError, ValueError):
        return "—"
