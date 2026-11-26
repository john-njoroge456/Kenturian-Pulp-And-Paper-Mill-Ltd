import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

_BLANK_LINE = re.compile(r"\n\s*\n")
_LIST_PREFIX = "- "


@register.filter
def format_job_description(value):
    """Format a plain-text job description as headings, lists and paragraphs.

    Blocks are separated by blank lines. Within a block, a line ending in ":"
    becomes an <h3>, consecutive lines starting with "- " become a <ul>, and
    other consecutive lines become a <p> (single line breaks kept as <br>).
    The text is escaped first, so no HTML in the input reaches the page.
    """
    text = escape(str(value or "")).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    parts = []
    for block in _BLANK_LINE.split(text):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith(_LIST_PREFIX):
                items = []
                while i < len(lines) and lines[i].startswith(_LIST_PREFIX):
                    items.append(lines[i][len(_LIST_PREFIX):].strip())
                    i += 1
                parts.append("<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>")
            elif line.endswith(":"):
                parts.append(f"<h3>{line[:-1].rstrip()}</h3>")
                i += 1
            else:
                para = []
                while (i < len(lines) and not lines[i].startswith(_LIST_PREFIX)
                       and not lines[i].endswith(":")):
                    para.append(lines[i])
                    i += 1
                parts.append("<p>" + "<br>".join(para) + "</p>")
    return mark_safe("\n".join(parts))


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
