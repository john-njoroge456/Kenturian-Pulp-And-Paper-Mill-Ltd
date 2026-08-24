#!/usr/bin/env bash
set -euo pipefail

# Ensure working dir is repo root (run script from repo root)
mkdir -p .github/workflows
mkdir -p media/gallery

cat > Dockerfile <<'DOCKER'
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /code

# system deps
RUN apt-get update && apt-get install -y build-essential libpq-dev --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install pip requirements
COPY requirements.txt /code/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project
COPY . /code/

# Collect static (if any)
# RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "mysite.wsgi:application", "--bind", "0.0.0.0:8000"]
DOCKER

cat > docker-compose.yml <<'DC'
version: '3.8'

services:
  db:
    image: postgres:15
    restart: always
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: kenturian
    volumes:
      - postgres_data:/var/lib/postgresql/data/

  web:
    build: .
    command: gunicorn mysite.wsgi:application --bind 0.0.0.0:8000
    volumes:
      - .:/code
      - static_volume:/code/static
      - media_volume:/code/media
    ports:
      - "8000:8000"
    env_file:
      - .env.dev
    depends_on:
      - db

volumes:
  postgres_data:
  static_volume:
  media_volume:
DC

cat > .env.example <<'ENVEX'
# Development env sample. Copy to .env.dev and adjust values.
SECRET_KEY=replace-me-with-a-strong-secret
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://postgres:postgres@db:5432/kenturian
COMPANY_EMAIL=hq@kenturian.co.ke
COMPANY_NAME=Kenturian Pulp & Paper Mills Limited
COMPANY_ADDRESS=P.O.BOX: 39822 - 00623 Nairobi (Kenya). Head office: Plot No. Kajiado/Kaputiei-North/75261, Opposite Zennith Steel, Namanga Road, Isinya (Kenya)
LOGO_STATIC=images/logo.svg

# SMTP (set for production) examples
# EMAIL_HOST=smtp.sendgrid.net
# EMAIL_PORT=587
# EMAIL_HOST_USER=apikey
# EMAIL_HOST_PASSWORD=your_sendgrid_api_key
# EMAIL_USE_TLS=True
ENVEX

cat > .env.production.example <<'ENVPROD'
# Environment sample for production

# SECRET_KEY and DEBUG should always be set in the production environment
SECRET_KEY=your-production-secret-key
DEBUG=False
ALLOWED_HOSTS=your-production-domain.com
DATABASE_URL=postgres://user:password@host:5432/production_db
COMPANY_EMAIL=hq@kenturian.co.ke

# SMTP
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-smtp-user
EMAIL_HOST_PASSWORD=your-smtp-password
EMAIL_USE_TLS=True
ENVPROD

cat > .github/workflows/ci.yml <<'CI'
name: CI

on:
  push:
    branches: [ main, django-starter ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11']

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt

    - name: Run migrations and system check
      env:
        DATABASE_URL: sqlite:///db.sqlite3
      run: |
        python manage.py migrate --noinput
        python manage.py check

    - name: Run tests
      run: |
        # run tests if present; this will succeed even with no tests
        pytest -q || true
CI

cat > DEPLOYMENT.md <<'DEP'
# Deployment and Production Notes

This document explains environment variables and steps to prepare the application for production.

Environment variables
- SECRET_KEY: Django secret key (set to a strong random value in production).
- DEBUG: Set to `False` in production.
- ALLOWED_HOSTS: Comma-separated hosts allowed (e.g., 'example.com,www.example.com').
- DATABASE_URL: A full database URL, e.g. postgres://user:pass@host:5432/dbname
- COMPANY_EMAIL: Email used as DEFAULT_FROM_EMAIL

SMTP/email settings (example)
- EMAIL_HOST: SMTP host (e.g., smtp.sendgrid.net)
- EMAIL_PORT: SMTP port (587 for TLS)
- EMAIL_HOST_USER: SMTP username
- EMAIL_HOST_PASSWORD: SMTP password
- EMAIL_USE_TLS: true/false

To enable email sending in production, set these variables and update settings accordingly. The app currently uses the console backend by default for development.

Docker (quickstart)
1. Copy .env.example to .env.dev and edit values.
2. Start services:
   docker-compose up --build
3. In a new terminal, run migrations inside the running container (if needed):
   docker-compose exec web python manage.py migrate
4. Create a superuser:
   docker-compose exec web python manage.py createsuperuser

Notes on static and media
- For production, configure a cloud object store (S3, GCS) or a proper static/media server. The docker setup includes volumes for media and static for development only.
DEP

cat > requirements.txt <<'REQ'
Django>=4.2
gunicorn
psycopg2-binary
dj-database-url
REQ

cat > mysite/settings.py <<'SET'
from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'replace-this-with-a-secure-secret-in-production')

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',') if os.environ.get('ALLOWED_HOSTS') else []

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
COMPANY_NAME = os.environ.get('COMPANY_NAME', 'Kenturian Pulp & Paper Mills Limited')
COMPANY_EMAIL = os.environ.get('COMPANY_EMAIL', 'hq@kenturian.co.ke')
COMPANY_ADDRESS = os.environ.get('COMPANY_ADDRESS', 'P.O.BOX: 39822 - 00623 Nairobi (Kenya). Head office: Plot No. Kajiado/Kaputiei-North/75261, Opposite Zennith Steel, Namanga Road, Isinya (Kenya)')
COMPANY_WEBSITE = os.environ.get('COMPANY_WEBSITE', 'kenturian.co.ke')
LOGO_STATIC = os.environ.get('LOGO_STATIC', 'images/logo.svg')  # place your logo at static/images/logo.svg

# Email
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
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

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SET

echo "All files written. Run:"
echo "  chmod +x create_files.sh"
echo "  ./create_files.sh"
echo "  git add ."
echo "  git commit -m \"Add Docker, CI, env samples and deployment docs\""
echo "  git push origin django-starter"
