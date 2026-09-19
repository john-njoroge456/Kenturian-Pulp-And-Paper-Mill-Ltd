from pathlib import Path
import os
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path):
    """Load KEY=VALUE lines from a local .env file.
    Real environment variables (e.g. set on the server) always win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(BASE_DIR / '.env')


def env_list(name):
    return [v.strip() for v in os.environ.get(name, '').split(',') if v.strip()]


# Off unless the environment explicitly turns it on
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'dev-only-insecure-key-do-not-use-in-production'
    else:
        raise ImproperlyConfigured(
            'Set the SECRET_KEY environment variable (DEBUG is off).')

# Comma-separated, e.g. kenturian.co.ke,www.kenturian.co.ke
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS')
# Include the scheme, e.g. https://kenturian.co.ke,https://www.kenturian.co.ke
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'main',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mysite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'main.context_processors.site_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'mysite.wsgi.application'

# Database: uses DATABASE_URL if set (e.g. PostgreSQL on the server), otherwise local SQLite
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Site/company defaults (can be edited later via a SiteSettings model or by changing these values)
COMPANY_NAME = os.environ.get(
    'COMPANY_NAME', 'Kenturian Pulp & Paper Mills Limited')
COMPANY_EMAIL = os.environ.get('COMPANY_EMAIL', 'kenturianpaper@gmail.com')
COMPANY_LOCATION = os.environ.get(
    'COMPANY_LOCATION', 'Off Namanga Road, Kisaju, Kajiado County, Kenya.')
COMPANY_POSTAL_ADDRESS = os.environ.get(
    'COMPANY_POSTAL_ADDRESS', 'P.O. Box 39822-00623, Nairobi, Kenya.')
COMPANY_WEBSITE = os.environ.get('COMPANY_WEBSITE', 'kenturian.co.ke')
# place your logo at static/images/logo.svg
LOGO_STATIC = os.environ.get('LOGO_STATIC', 'images/logo.svg')
COMPANY_PHONE = os.environ.get('COMPANY_PHONE', '+254720044513')

# E.164 without the + for wa.me links
FOOTER_WHATSAPP = os.environ.get('FOOTER_WHATSAPP', '254795979982')

# Email: sends through SMTP when a password is provided, otherwise prints to the console
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')  # change for another provider
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend' if EMAIL_HOST_PASSWORD
    else 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = COMPANY_EMAIL

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Nairobi'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Where collectstatic will copy files for production
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

FOOTER_TWITTER = os.environ.get(
    'FOOTER_TWITTER', 'https://twitter.com/kenturian')
FOOTER_FACEBOOK = os.environ.get(
    'FOOTER_FACEBOOK', 'https://facebook.com/kenturian')
FOOTER_LINKEDIN = os.environ.get(
    'FOOTER_LINKEDIN', 'https://linkedin.com/company/kenturian')
FOOTER_YOUTUBE = os.environ.get('FOOTER_YOUTUBE', '')
FOOTER_INSTAGRAM = os.environ.get(
    'FOOTER_INSTAGRAM', 'https://instagram.com/kenturian')

# Static files served by WhiteNoise (the non-manifest version won't crash a page
# if a template points at a missing static file)
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

# HTTPS hardening. Turn on with SECURE_SSL=True only once the site is served over
# HTTPS; enabling it earlier can cause redirect loops.
if os.environ.get('SECURE_SSL', 'False') == 'True':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600  # raise to 31536000 once everything works
