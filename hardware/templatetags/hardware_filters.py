from django import template

register = template.Library()

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
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        if value is None or arg is None:
            return 0
        return float(value) * float(arg)
    except (ValueError, TypeError):
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