from django import template

register = template.Library()


@register.filter
def rupiah(value):
    return "Rp{:,.0f}".format(value or 0).replace(",", ".")


@register.filter
def masked_phone(value):
    return f"+62 ••• •••• {value[-4:]}" if value else ""
