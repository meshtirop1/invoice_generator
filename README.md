# 계산서 시스템 — Invoice Management System

A professional invoice management web application built with Django, designed for Korean small businesses. Manage buyers, generate invoices, track balances, and print clean A4 invoices — all from the browser.

---

## Live

> `https://inv.mtirop.com` — self-hosted on a VPS behind nginx.

---

## Features

- **Edit on the paper** — The A4 invoice *is* the form. Click any cell and type,
  like a spreadsheet. Tab moves across, Enter moves down, the last row grows by
  itself. No site navigation needed.
- **Seller details are typed per invoice** — 상호 / 주소 / 전화번호 / 계좌번호 are
  edited straight on the sheet and snapshotted onto that invoice, so correcting
  one invoice never rewrites the seller shown on past ones.
- **Send to phone** — One button turns the invoice into a PNG and shows a QR
  code. Scan it with a phone camera and the image opens there, ready to share
  into KakaoTalk. Replaces print → photograph → send.
- **Independent invoices** — Each invoice stands alone. Nothing carries between
  them, so editing or deleting one never disturbs another.
- **Invoice Management** — Create, edit, print, and delete invoices
- **Buyer Management** — Maintain a full list of buyers/clients
- **Seller Profiles** — Support multiple seller profiles with a default selection
- **Per-buyer total** — The dashboard sums what each buyer still owes across
  their unpaid invoices
- **Print-Ready Invoices** — Clean single-page A4 print layout, no URL headers/footers
- **PWA Support** — Install as an app on desktop or mobile (works offline)
- **Korean UI** — Fully localised interface in Korean (한국어)
- **Admin Panel** — Django admin for full database control at `/admin`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6.0.5 |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Static Files | WhiteNoise |
| Server | Gunicorn |
| Hosting | Self-hosted VPS (nginx + gunicorn) |
| CI | GitHub Actions |
| Container | Docker |
| Language | Python 3.12 |

---

## Project Structure

```
invoice_generator/
├── inv/                        # Django project config
│   ├── settings.py             # Environment-aware settings
│   ├── urls.py
│   └── wsgi.py
│
├── invoice/                    # Main application
│   ├── models.py               # SellerProfile, Buyer, Invoice, InvoiceItem
│   ├── views.py                # All views + AJAX endpoints
│   ├── urls.py                 # URL routing
│   ├── tests.py                # 69 tests
│   └── management/
│       └── commands/
│           ├── create_default_superuser.py
│           └── seed_buyers.py  # Seeds 44 buyers from old system
│
├── templates/                  # HTML templates
│   ├── _paper_css.html         # Shared paper styling (sheet = print = PNG)
│   ├── _paper.html             # Shared read-only paper markup
│   ├── base.html               # Nav, PWA meta, install banner
│   ├── dashboard.html
│   ├── invoice_sheet.html      # The editable A4 sheet (create + edit)
│   ├── invoice_share.html      # Phone page: PNG + native share sheet
│   ├── invoice_print.html      # Print-optimised A4 layout
│   └── ...
│
├── public/                     # Served at site root via WhiteNoise
│   ├── manifest.json           # PWA manifest
│   ├── sw.js                   # Service worker
│   ├── vendor/                 # html-to-image + qrcode.js (vendored, no CDN)
│   └── icons/                  # PNG app icons (any + maskable) & SVG source
│
├── scripts/
│   └── make_icons.py           # Regenerates the PNG icon set
│
├── .github/workflows/
│   └── ci.yml                  # Run tests on every push
│
├── Dockerfile
├── docker-compose.yml
├── startup.sh                  # migrate → seed → gunicorn
└── requirements.txt
```

---

## The two main workflows

### Writing an invoice (desktop)

1. Open **새 계산서**, or click **열기** on an existing one — either lands on the
   A4 sheet at `/invoices/new/` or `/invoices/<pk>/edit/`.
2. Pick the buyer from the top-left of the paper. The previous balance loads
   automatically; 택배료 / 공제 rows appear only for buyers configured for them.
3. Type into the grid. Amounts, the total and 현잔액 update as you type.
   - `Tab` / `Shift+Tab` — next / previous cell
   - `Enter` or `↓` — same column, next row
   - `←` / `→` — jump cells from the edge of the text
   - Typing in the last row appends a new one
4. **저장**. You stay on the sheet — an unsaved-changes marker appears in the
   toolbar until you do.

### Getting it to the customer

| Button | What happens |
|---|---|
| **🖼 PNG 저장** | Downloads the sheet as a PNG (2× resolution) |
| **📱 폰으로 보내기** | Shows a QR code for `/invoices/<pk>/share/` |
| **🖨 인쇄** | Normal A4 print |

Scanning the QR opens the share page on the phone, which renders the invoice to
a PNG and offers the **native share sheet** (`navigator.share`) — KakaoTalk, SMS,
email, whatever is installed. Where the browser cannot share files it falls back
to a download button and says so.

> The QR encodes an absolute URL. On `localhost` the page warns that a phone
> cannot reach it — use the deployed address, or the PC's LAN IP on the same
> Wi-Fi.

### Seller details

The seller block is typed on the paper, not picked from a dropdown. Each invoice
carries its own `seller_name` / `seller_address` / `seller_phone` /
`seller_bank_account` / `seller_fax`, seeded from the default `SellerProfile`
when the sheet is blank and then freely overwritten.

`SellerProfile` and the 판매자 설정 page are now only the **defaults for new
invoices** — editing a sheet never writes back to the profile, and never touches
another invoice. Migration `0003` backfills existing invoices from their FK.

The `seller` FK is retained for existing data; the printed and exported sheet
reads the snapshot fields.

### Balances

Invoices are **independent**. Each one shows only its own amount:

```
current_balance = Σ(qty × boxes × unit_price)
                + delivery_fee − deduction − payment_received
```

Nothing carries between invoices. `previous_balance` is kept as a column but is
always `0`, so the 전 잔 액 row on the paper renders blank — which matches the
reference form. Keeping the column means the decision can be reversed without a
migration.

`recalculate_balances(buyer)` still exists and still runs on every invoice/item
save and delete, including from the Django admin, because an invoice's own total
changes whenever its items do. Bulk operations wrap themselves in
`suppress_recalc()` and call it once at the end.

`Buyer.get_current_balance()` returns the **sum of what that buyer still owes
across all their invoices** — the only per-buyer figure that still means
anything once invoices stand alone. That is what the dashboard and buyer list
show.

---

## Data Models

```
SellerProfile
  └── company_name, address, phone, bank_account, fax, is_default

Buyer
  └── name, has_delivery_fee, has_deduction, notes

Invoice
  ├── seller (FK → SellerProfile)
  ├── buyer  (FK → Buyer)
  ├── date, delivery_fee, deduction, payment_received
  ├── previous_balance (always 0 — invoices are independent)
  └── current_balance  (auto-calculated: this invoice alone)

InvoiceItem
  ├── invoice (FK → Invoice)
  ├── product_name, quantity, boxes, unit_price
  └── amount  (auto = quantity × boxes × unit_price)
```

---

## Getting Started (Local)

### 1. Clone the repo

```bash
git clone https://github.com/meshtirop1/invoice_generator.git
cd invoice_generator
```

### 2. Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set environment variables

```bash
export DEBUG=True
export SECRET_KEY=your-local-secret-key
export ALLOWED_HOSTS=localhost,127.0.0.1
```

### 4. Run migrations & seed data

```bash
python manage.py migrate
python manage.py create_default_superuser
python manage.py seed_buyers
python manage.py collectstatic --noinput
```

### 5. Start the server

```bash
python manage.py runserver
```

Visit `http://localhost:8000`

---

## Running with Docker

```bash
docker-compose up --build
```

Visit `http://localhost:8000`

---

## Running Tests

```bash
python manage.py test invoice --verbosity=2
```

**69 tests** covering:
- Model logic (balance calculations, auto-amounts, default seller enforcement)
- All views (GET/POST, redirects, 404s)
- AJAX endpoints
- Edge cases (empty rows, zero quantities, balance carry-over)
- Invoice independence: editing, deleting or paying one never moves another
- The admin path (items written after the invoice row)
- Decimal quantities, comma-formatted money, ragged POST arrays
- Print output no longer dropping items past row 12
- Seller snapshots: saved from the sheet, isolated per invoice, profile untouched

---

## Deploying to the VPS

The site runs from `/home/deploy/sites/invoice` on the shared VPS: gunicorn as the
`invoice` systemd service on `127.0.0.1:8109`, behind nginx for `inv.mtirop.com`.

**Every push to `main` deploys automatically** (`.github/workflows/deploy.yml`): the tests
run first, then the workflow SSHes in as the `deploy` user, resets the checkout to
`origin/main` and runs [`deploy/deploy.sh`](deploy/deploy.sh), which installs requirements,
**backs up the database**, migrates, collects static files and restarts the service. A
failed backup stops the deploy. The workflow then checks that the site answers. It can also
be started by hand from the Actions tab (*Deploy → Run workflow*).

The workflow needs three secrets in the repo's `production` environment: `SSH_HOST`,
`SSH_USER` (`deploy`) and `SSH_KEY` (a key in `/home/deploy/.ssh/authorized_keys`). The server
pulls with a read-only deploy key (SSH alias `github-invoice` in `/home/deploy/.ssh/config`),
and `deploy` may run only `systemctl restart|is-active invoice` through sudo.

To deploy by hand, on the server as `deploy`:

```bash
cd /home/deploy/sites/invoice
git fetch origin main && git reset --hard origin/main
bash deploy/deploy.sh
```

The reset leaves untracked files alone: `env` (settings and secrets), `db.sqlite3`,
`backups/`, `staticfiles/` and `.venv/`. `startup.sh` is for a container start.

### Backups

`python manage.py backup_db` takes a consistent copy of the SQLite database, checks it with
`PRAGMA integrity_check` and gzips it into `backups/` (folder `700`, files `600`). Copies
older than 14 days are deleted, but the newest 5 always stay. It runs before every deploy
(`predeploy`) and every night at 03:05 Korea time through
[`deploy/cron.d/invoice-backup`](deploy/cron.d/invoice-backup), installed as
`/etc/cron.d/invoice-backup`. The nightly run logs to `backups/backup.log`. How to restore a
copy is written at the top of [`deploy/backup.sh`](deploy/backup.sh).

### Required environment

Set these for the service (systemd `Environment=`, an `.env`, or the container):

```bash
DJANGO_SETTINGS_MODULE=inv.prod_settings   # turns on the password gate
SECRET_KEY='<a long random string>'
DEBUG=False
ALLOWED_HOSTS=inv.mtirop.com
GATE_PASSWORD='<the code staff type to get in>'
DATABASE_URL=postgres://user:pass@localhost:5432/invoice   # omit for SQLite
```

On the server these live in `/home/deploy/sites/invoice/env`, which the systemd unit reads
(`EnvironmentFile=`) and which is never committed.

`CSRF_TRUSTED_ORIGINS` is derived from `ALLOWED_HOSTS` automatically
(`https://<host>` for each real host), so a form post over HTTPS works without
extra configuration.

### nginx

Django needs to be told the request arrived over HTTPS, or it treats every
request as plain HTTP:

```nginx
location / {
    proxy_pass         http://127.0.0.1:8000;
    proxy_set_header   Host              $host;
    proxy_set_header   X-Forwarded-Proto $scheme;   # required
    proxy_set_header   X-Real-IP         $remote_addr;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
}
```

`SECURE_PROXY_SSL_HEADER` is already set for this. Turn on
`SECURE_SSL_REDIRECT=True` only once that header is confirmed — without it
Django will redirect to HTTPS forever.

### Creating the admin user

There is no default login. Create one explicitly, once:

```bash
python manage.py createsuperuser
```

Or non-interactively, for a container start:

```bash
DJANGO_SUPERUSER_USERNAME=... DJANGO_SUPERUSER_PASSWORD=... \
  python manage.py create_default_superuser
```

The command is a no-op unless both are set, and never overwrites an existing
user.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | Yes | insecure dev key | Django secret key |
| `DEBUG` | No | `False` | Enable debug mode |
| `ALLOWED_HOSTS` | No | `*` | Comma-separated allowed hosts |
| `DATABASE_URL` | No | SQLite | PostgreSQL connection string |
| `CSRF_TRUSTED_ORIGINS` | No | derived | Extra trusted origins, comma-separated |
| `SECURE_SSL_REDIRECT` | No | `False` | Redirect HTTP to HTTPS in Django |
| `SECURE_HSTS_SECONDS` | No | `0` | Enable HSTS (e.g. `31536000`) |
| `DJANGO_SUPERUSER_USERNAME` | No | — | Used by `create_default_superuser` |
| `DJANGO_SUPERUSER_PASSWORD` | No | — | Used by `create_default_superuser` |
| `DJANGO_SETTINGS_MODULE` | Live site | `inv.settings` | `inv.prod_settings` adds the password gate |
| `GATE_PASSWORD` | With the gate | — | The gate's password. No fallback: unset keeps the gate shut |
| `DJANGO_BACKUP_DIR` | No | `backups/` | Where `backup_db` writes copies |

---

## Admin User

There is no default superuser and no built-in password. Create one with
`python manage.py createsuperuser`, or set `DJANGO_SUPERUSER_USERNAME` /
`DJANGO_SUPERUSER_PASSWORD` and run `python manage.py create_default_superuser`.

> The app has no user accounts of its own. On the live site every page except `/admin/`
> sits behind a single shared password (`inv/gate.py`, switched on by
> `inv/prod_settings.py` and set with `GATE_PASSWORD`); once typed it lasts 30 days on that
> device. Running with plain `inv.settings` (local development) has no gate.

## CI

Every push to any branch:
1. GitHub Actions runs all the tests
2. Checks for missing migrations
3. Builds the Docker image to verify it compiles

A push to `main` then deploys — see **Deploying to the VPS** above.

---

## PWA — Install as App

The app is a fully installable Progressive Web App:
- **Offline support** — cached pages available without internet
- **Install prompt** — banner appears in the browser to add to home screen
- **App shortcuts** — "New Invoice" and "Invoice List" shortcuts on the icon
- **Standalone mode** — runs without browser chrome when installed

### Icons

`public/icons/` holds two distinct sets, which are **not** interchangeable:

| File | `purpose` | Notes |
|---|---|---|
| `icon-192.png`, `icon-512.png` | `any` | Full-bleed rounded square |
| `icon-maskable-192.png`, `icon-maskable-512.png` | `maskable` | Artwork inside the centre 72%, so a circular launcher mask cannot clip it |
| `apple-touch-icon.png` | — | 180×180, opaque RGB. **iOS ignores SVG here** |

Regenerate them all with:

```bash
python scripts/make_icons.py     # requires Pillow
```

### Service worker

`public/sw.js` — cache-first for `/static/`, `/icons/`, `/vendor/`;
network-first for pages, falling back to the cache and then `/offline/`.
`/admin` and `/api/` are never cached, and only `200` same-origin responses are
stored, so a redirect or error can't be served back after the server recovers.
Bump `CACHE_NAME` when precached assets change.

> Service worker registration requires a secure context — `https://` or
> `localhost`. It will not register over plain HTTP on a LAN IP.

---

## License

Private — All rights reserved.
