from django.conf import settings


def site_settings(request):
    """Make company/site settings available in all templates."""
    return {
        'COMPANY_NAME': getattr(settings, 'COMPANY_NAME', ''),
        'COMPANY_EMAIL': getattr(settings, 'COMPANY_EMAIL', ''),
        'COMPANY_LOCATION': getattr(settings, 'COMPANY_LOCATION', ''),
        'COMPANY_POSTAL_ADDRESS': getattr(settings, 'COMPANY_POSTAL_ADDRESS', ''),
        'COMPANY_PHONE': getattr(settings, 'COMPANY_PHONE', ''),
        'FOOTER_WHATSAPP': getattr(settings, 'FOOTER_WHATSAPP', ''),
        'FOOTER_SOCIALS': {
            'twitter': getattr(settings, 'FOOTER_TWITTER', ''),
            'facebook': getattr(settings, 'FOOTER_FACEBOOK', ''),
            'linkedin': getattr(settings, 'FOOTER_LINKEDIN', ''),
            'youtube': getattr(settings, 'FOOTER_YOUTUBE', ''),
            'instagram': getattr(settings, 'FOOTER_INSTAGRAM', ''),
        },
        'FOOTER_OFFICE_HOURS': getattr(settings, 'FOOTER_OFFICE_HOURS', ''),
    }
