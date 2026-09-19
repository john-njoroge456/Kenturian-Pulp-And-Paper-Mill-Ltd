from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    'SECRET_KEY', 'replace-this-with-a-secure-secret-in-production')

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(
    ',') if os.environ.get('ALLOWED_HOSTS') else []

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

# Database
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
COMPANY_EMAIL = os.environ.get('COMPANY_EMAIL', 'kenturianpaper@gmail.com')

# E.164 without the + for wa.me links
FOOTER_WHATSAPP = os.environ.get('FOOTER_WHATSAPP', '254795979982')

# Email
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
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

TIME_ZONE = 'UTC'

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
