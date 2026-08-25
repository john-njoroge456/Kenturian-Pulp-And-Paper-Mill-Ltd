from django.conf import settings


def site_settings(request):
    """Make company/site settings available in all templates."""
    return {
        'COMPANY_NAME': getattr(settings, 'COMPANY_NAME', ''),
        'COMPANY_EMAIL': getattr(settings, 'COMPANY_EMAIL', ''),
        'COMPANY_ADDRESS': getattr(settings, 'COMPANY_ADDRESS', ''),
        'COMPANY_WEBSITE': getattr(settings, 'COMPANY_WEBSITE', ''),
        'LOGO_STATIC': getattr(settings, 'LOGO_STATIC', ''),
    }
