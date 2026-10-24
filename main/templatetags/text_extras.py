from django import template

register = template.Library()


@register.filter
def truncate_smart(value, length=100):
    """Shorten text to about `length` characters without cutting a word in half."""
    text = str(value or "").strip()
    if len(text) <= length:
        return text
    cut = text[:length].rsplit(" ", 1)[0].rstrip(",.;:-–— ")
    return cut + "…"


@register.filter
def phone_display(value):
    """Show a Kenyan number as +254 7XX XXX XXX. Links should keep the raw value."""
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    if digits.startswith("254") and len(digits) == 12:
        return f"+254 {digits[3:6]} {digits[6:9]} {digits[9:]}"
    return value
