# finance/templatetags/finance_filters.py
from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key"""
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        if value is None or arg is None:
            return 0
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, arg):
    """Divide the value by the argument"""
    try:
        if value is None or arg is None:
            return 0
        if arg == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter
def percentage(value, arg):
    """Calculate percentage of value / arg * 100"""
    try:
        if value is None or arg is None or arg == 0:
            return 0
        return (float(value) / float(arg)) * 100
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter
def subtract(value, arg):
    """Subtract arg from value"""
    try:
        if value is None or arg is None:
            return 0
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add(value, arg):
    """Add arg to value"""
    try:
        if value is None or arg is None:
            return 0
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def floatformat(value, arg=0):
    """Format a float with specified decimal places"""
    try:
        if value is None:
            return '0'
        return f"{float(value):,.{int(arg)}f}"
    except (ValueError, TypeError):
        return str(value)

@register.filter
def intcomma(value):
    """Add commas to a number"""
    try:
        if value is None:
            return '0'
        return f"{int(float(value)):,}"
    except (ValueError, TypeError):
        return str(value)

@register.filter
def default(value, default_value):
    """Return default value if value is None or empty"""
    if value is None or value == '':
        return default_value
    return value