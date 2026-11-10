#!/usr/bin/env bash
# Monthly log rotation, run by a cPanel cron job: 0 0 1 * * (FX-38).
# Workers use WatchedFileHandler, so they reopen a fresh django.log after the rename.
set -eo pipefail

LOG_DIR="$(cd "$(dirname "$0")/.." && pwd)/logs"
cd "$LOG_DIR"

if [ -s django.log ]; then
    # Run on the 1st, yesterday is the month the lines belong to
    target="django-$(date -d yesterday +%Y-%m).log"
    # Never overwrite an earlier file, e.g. after a manual run in the same month
    if [ -e "$target" ]; then
        target="django-$(date -d yesterday +%Y-%m)-$(date +%s).log"
    fi
    mv django.log "$target"
fi
find . -name 'django-*.log' -mtime +190 -delete   # keep about 6 months
