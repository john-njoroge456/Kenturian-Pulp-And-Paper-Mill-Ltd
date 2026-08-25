# Kenturian Pulp And Paper Mill Ltd - Django Starter

This repository has a minimal Django starter scaffold added to help you get started quickly.

What's included
- Django project (mysite) and a starter app (main)
- SQLite database (development)
- Basic Product model, index view, and templates
- requirements.txt, .gitignore, LICENSE

Quick start
1. Create and activate a virtual environment
   - python -m venv .venv
   - macOS/Linux: source .venv/bin/activate
   - Windows (PowerShell): .venv\Scripts\Activate.ps1
2. Install dependencies
   - pip install -r requirements.txt
3. Run migrations
   - python manage.py migrate
4. Create a superuser (to access admin)
   - python manage.py createsuperuser
5. Run the development server
   - python manage.py runserver

Open http://127.0.0.1:8000/ to view the site and http://127.0.0.1:8000/admin/ for the admin.

Notes
- This branch: django-starter
- Database: SQLite (db.sqlite3) — good for development. Switch to PostgreSQL for production.
