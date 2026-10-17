from django import template

register = template.Library()

CURRENCY_SYMBOLS = {
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'NGN': '₦',
    'KES': 'KSh',
    'GHS': 'GH₵',
    'ZAR': 'R',
    'CAD': 'C$',
    'AUD': 'A$',
    'INR': '₹'
}

@register.filter
def currency_symbol(currency_code):
    """
    Returns the symbol for a given 3-letter currency code.
    Defaults to the code itself if not found.
    """
    if not currency_code:
        return '₦' # Default fallback
    
    currency_code = str(currency_code).upper()
    return CURRENCY_SYMBOLS.get(currency_code, currency_code)
