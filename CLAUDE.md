# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The Django website for Kenturian Pulp & Paper Mills Limited (kenturian.co.ke): public marketing pages plus order requests, contact messages and job applications. Orders are not a checkout. They are enquiries that Sales follow up in the Django admin, which is the staff back office.

There is one app, `main`, in the `mysite` project. `README.md` and `DEPLOYMENT.md` are left over from the starter scaffold and do not describe production (see Deployment).

## Commands

Use `.venv313` (Python 3.13, matching CI and the server). Ruff is only installed in `.venv`, and the repo has no ruff config.

```bash
.venv313/bin/python manage.py runserver
.venv313/bin/python manage.py makemigrations
.venv313/bin/python manage.py migrate
.venv/bin/ruff check .

# Run all tests, or a single one
.venv313/bin/python manage.py test
.venv313/bin/python manage.py test main.tests.TestClass.test_name
```

The tests are in `main/tests.py`, and CI runs them too (`manage.py test`). Run them with:

```bash
.venv313/bin/python manage.py test main
```

They catch mail in `mail.outbox` and write CVs to a temporary folder, never to `private_media/`. Coverage:

- Resubmit protection (FX-25, FX-32): Back-then-Submit and simultaneous submits on the order, contact and both careers forms create one record and one set of emails. The pages are served `no-store`, and the forms have `autocomplete="off"`.
- Contact email length (FX-24): 254 characters are accepted and 255 rejected, and the input has `maxlength="254"`.
- Honeypots (FX-16): a filled `fax_number` or `website` redirects to `?sent=1`. It saves nothing, sends no email, stores no CV and never shows the value back.
- Order honeypot (FX-35): a filled `kp_hp_check` redirects to `/order/?sent=1`, which shows a generic card with no reference or order details. It saves no order or items, sends no email, stores no LPO and leaves `placed_orders` alone. The field is named so autofill won't fill it. The multi-item formset and the no-JS note are unaffected.
- Contact spam (FX-37):
  - The visitor's confirmation email (contact, order and careers) carries no visitor text except a first-name greeting, so the forms can't be used to send someone's text to any address. A typed "Other" colour shows as "Other (as specified)".
  - `count_links()` counts bare domains like `indexdomain.live` as well as `http(s)://` and `www.`. It skips email addresses, file names, `kenturian.co.ke`, decimals and abbreviations. Going over `MAX_LINKS` still shows a visible form error.
  - A sender domain containing "kenturian" that isn't exactly `kenturian.co.ke` is dropped like a honeypot on all four forms: redirect to `?sent=1`, nothing kept, one log line with no submitted values.

Not covered: the order-form business rules (colours, limits, phone rules), the admin report and Excel exports, the upload signature checks, and JS behaviour. The separate Selenium suite covers the browser.

Ruff is not part of CI, and `ruff check .` currently reports 111 existing errors. Check the files you changed rather than expecting a clean run.

CI (`.github/workflows/ci.yml`) also runs these, with `DEBUG=False`:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
python manage.py check --deploy --fail-level ERROR   # with SECURE_SSL=True
```

Project management commands:

- `setup_staff_groups` creates or updates the Sales and HR groups. Rerun it after changing `STAFF_GROUPS`.
- `optimize_images [--dry-run]` resizes uploaded images and updates the database.

## Architecture

**Submissions: save first, then email.** The order, contact and application flows all follow the same pattern in `main/views.py`:

1. Save the record, which generates a reference in `save()` (`KPM-`, `CTC-` or `APP-` plus 6 hex characters).
2. Email staff, then send the client a confirmation. Each send is wrapped in `try/except`, so a mail failure never loses a submission or shows the user an error.
3. Set `client_email_sent` only if the client's email went out.

Each email is built twice: a plain-text body inline in the view, and an HTML template in `templates/emails/` rendered with `for_client` True or False. Change both when editing email content. Recipients come from the `*_NOTIFY_EMAILS` and `*_REPLY_TO` settings.

**Order form.** This is the most intricate part of the site, spread across three places:

- `main/forms.py` holds the business rules: `FIXED_COLORS`, `BLOCKED_COLORS`, `LIMITS`, `MAX_ITEMS` and the phone rules. `OrderRequestForm` covers the shared details, and `OrderItemFormSet` (`BaseOrderItemFormSet`) covers 1 to 10 items and rejects duplicates.
- `templates/main/order.html` has inline JS that adds and removes item rows from `formset.empty_form` (rendered through `_order_item_row.html`) and applies the same rules in the browser.
- The rules reach the JS through `data-*` attributes set in `OrderItemForm.__init__` (`data-color-rules`, `data-blocked-colors`, `data-range-message`). Change them in `forms.py` rather than copying values into the JS. The server validation is authoritative.

The form must also work without JavaScript: `base.html` adds a `js` class to `<html>`, and JS-only controls are hidden when it is absent.

`order_success_view` only shows references stored in the visitor's session (`placed_orders`), so references cannot be guessed to view other clients' orders.

**Two kinds of uploads.**

- Public images use `MEDIA_ROOT`.
- CVs and LPOs use `private_storage` (`main/storage.py`) under `PRIVATE_MEDIA_ROOT`. These have no public URL and are only reachable through permission-checked download views in `main/admin.py`, so never link to them directly.

Uploads are checked by extension, size and leading file bytes. LPOs use `validators.validate_upload`; CVs use `JobApplicationForm.clean_cv`, which has its own signature table.

**Admin.** `OrderRequestAdmin` adds a report page and LPO download through `get_urls()`. The report logic and Excel exports are in `main/reports.py`, and the report is gated by the custom `main.view_order_report` permission. The admin path comes from the `ADMIN_URL` setting, so use `reverse("admin:...")` rather than hardcoding `/admin/`.

**Content models.**

- `Product` drives the homepage carousel; `OrderItemOption` drives the order form's item list. They are unrelated.
- There is no product detail page: `product_detail` redirects to the homepage carousel.
- Page banners are `GalleryImage` rows selected by `category`, so a new banner slot needs a new `CATEGORY_CHOICES` entry and a migration.

**Frontend.** Server-rendered templates extending `templates/base.html`, with Bootstrap 5, Bootstrap Icons and AOS loaded from CDNs. Custom styles are in `static/css/theme.css`. `main.context_processors.site_settings` provides the company and footer values to all templates. There is no JS build step.

## Configuration

`mysite/settings.py` loads a local `.env` through its own `load_dotenv`; real environment variables take priority.

- `load_dotenv` does not strip inline comments: everything after `=` becomes the value, so `DEBUG=True    # note` is not exactly `True` and DEBUG stays off. Keep comments on their own line in `.env` and both example files. Since FX-28, `.env.example` follows this and can be copied as is.
- DEBUG is off unless the value is exactly `True`, and `SECRET_KEY` is then required.
- Without `EMAIL_HOST_PASSWORD`, emails print to the console.
- With no `DATABASE_URL`, the site uses SQLite at `db.sqlite3`.
- `EMAIL_USE_TLS` appears in `.env.example` but `settings.py` never reads it; only `EMAIL_USE_SSL` is used.

## Deployment

Production is shared cPanel hosting running Passenger (`passenger_wsgi.py`) with MariaDB, not the Docker or Render setups described in `DEPLOYMENT.md`. Server environment variables are set in cPanel, and `.env.example` notes the production value for each.

`./deploy.sh`, run on the server, pulls `main`, installs requirements, then runs `check`, `migrate` and `collectstatic` and restarts by touching `tmp/restart.txt`.

`mysite/__init__.py` installs PyMySQL as the MySQL driver because `mysqlclient` cannot be compiled on the host. Migrations need to work on both SQLite and MariaDB.

`staticfiles/` is generated. `media/`, `private_media/`, `db.sqlite3`, `content.json`, `orders_backup.json` and `media.zip` are git-ignored local data, and the backups contain real client information.
## Local testing setup

- Local test server: gunicorn on port 9000 (ports 8000 and 8001 are taken by HP printer services). Gunicorn does not auto-reload: restart it after any Python or settings change, and run `collectstatic --noinput` first if CSS changed.
- No-JS fallbacks exist two ways: the `js` class on `<html>` (base.html) and `<noscript>` blocks in `templates/main/order.html`. Check both when changing JS-only controls.
- QA lives in a separate repo (Kenturian-QA-Testing): a Selenium/pytest suite (28 tests) that runs against http://127.0.0.1:9000/ and needs the seed data `Selenium/test_data/qa_seed.json` (job pk 9001), loaded with `manage.py loaddata`. Manual test cases, fix IDs (FX-xx) and regression runs are tracked in its KPPML_MANUAL_TESTING.xlsx.

## Workflow

- Never work on `main`. Fixes go on a branch (e.g. `release/...`), one commit per fix with the fix ID in the message (`FX-05: ...`).
- Release: merge into `main` with `--no-ff`, push, wait for CI to pass, then run `./deploy.sh` on the server and smoke-test the live site.
- Make one change at a time and explain it before applying; the developer retests each change in the browser before moving on.
- Never read, print or edit `.env`, and never commit secrets.