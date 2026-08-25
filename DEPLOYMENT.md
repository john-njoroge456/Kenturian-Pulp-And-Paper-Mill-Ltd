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

Production notes (static files)
- Install requirements and set environment variables (SECRET_KEY, DEBUG=False, DATABASE_URL, COMPANY_EMAIL, EMAIL_*).
- Run: python manage.py collectstatic --noinput
  This collects static files into STATIC_ROOT (staticfiles) which WhiteNoise serves.

Using WhiteNoise
- We added whitenoise to requirements and settings to allow static serving in simple deployments.
- For more robust production, front the app with a CDN or object storage (S3) for static + media.

Example Render/Heroku checklist
- Use gunicorn in Procfile: web: gunicorn mysite.wsgi
- Ensure DATABASE_URL, SECRET_KEY, ALLOWED_HOSTS, and EMAIL_* variables are set in the host.
- Run migrations and collectstatic as part of deploy:
  python manage.py migrate
  python manage.py collectstatic --noinput
