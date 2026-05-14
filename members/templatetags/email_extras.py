from django import template

register = template.Library()

@register.filter(name='mask_email')
def mask_email(value):
    if not value or '@' not in value:
        return value
    try:
        user_part, domain_part = value.split('@')
        # Masking: first 4 chars of user + **** @ *** + last 4 of domain
        return f"{user_part[:4]}****@***{domain_part[-8:]}"
    except Exception:
        return value