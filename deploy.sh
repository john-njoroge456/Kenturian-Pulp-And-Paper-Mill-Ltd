#!/usr/bin/env bash
# Update the live site: pull the latest code, install packages, migrate,
# collect static files and restart. Stops at the first error.
set -eo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$HOME/virtualenv/kenturian_app/3.13/bin/activate"

cd "$APP_DIR"
source "$VENV"

echo "==> Pulling latest code"
git pull --ff-only origin main

echo "==> Installing packages"
pip install -q -r requirements.txt

echo "==> Checking the project"
python manage.py check

echo "==> Applying database migrations"
python manage.py migrate --noinput

echo "==> Collecting static files"
python manage.py collectstatic --noinput

echo "==> Restarting the site"
mkdir -p tmp && touch tmp/restart.txt

echo "==> Deploy finished: $(git log --oneline -1)"
