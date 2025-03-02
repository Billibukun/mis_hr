from django import template
from django.template.defaultfilters import floatformat
from django.utils.safestring import mark_safe
import re

register = template.Library()

@register.filter(needs_autoescape=True)
def highlight(text, search, autoescape=None):
    if not search:
        return text
    highlighted_text = re.sub(re.compile(re.escape(search), re.IGNORECASE), lambda m: f'<span style="background-color: yellow;">{m.group(0)}</span>', text)
    return mark_safe(highlighted_text)


@register.filter
def dividedby(value, arg):
    """Divides the value by the argument."""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return None
    
@register.filter
def multiply(value, arg):
    """Multiplies the value by the argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return None  # Or a default value like 0