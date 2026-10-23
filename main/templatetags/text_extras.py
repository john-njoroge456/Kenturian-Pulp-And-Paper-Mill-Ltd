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
