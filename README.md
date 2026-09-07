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
- **Self-repairing balances** — Editing or deleting any invoice recalculates
  every later invoice for that buyer automatically.
- **Invoice Management** — Create, edit, print, and delete invoices
- **Buyer Management** — Maintain a full list of buyers/clients
- **Seller Profiles** — Support multiple seller profiles with a default selection
- **Balance Tracking** — Automatically carries over previous balance to next invoice
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

### Balance chain

`previous_balance` is no longer a one-time snapshot. `recalculate_chain(buyer)`
walks that buyer's invoices oldest-first and rewrites both balance fields, and
it runs automatically on every invoice/item save and delete — including from the
Django admin. Bulk operations wrap themselves in `suppress_recalc()` and call it
once at the end.

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
  ├── previous_balance (auto-carried from last invoice)
  └── current_balance  (auto-calculated)

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
- Balance-chain repair after editing, deleting or re-assigning an invoice
- The admin path (items written after the invoice row)
- Decimal quantities, comma-formatted money, ragged POST arrays
- Print output no longer dropping items past row 12
- Seller snapshots: saved from the sheet, isolated per invoice, profile untouched

---

## Deploying to the VPS

The server runs gunicorn behind nginx. Deploying is a pull, a migrate, a
collectstatic and a restart:

```bash
cd /path/to/invoice_generator
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo systemctl restart invoice        # whatever the gunicorn unit is called
```

`startup.sh` does the same sequence for a container start.

### Required environment

Set these for the service (systemd `Environment=`, an `.env`, or the container):

```bash
SECRET_KEY='<a long random string>'
DEBUG=False
ALLOWED_HOSTS=inv.mtirop.com
DATABASE_URL=postgres://user:pass@localhost:5432/invoice   # omit for SQLite
```

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

---

## Admin User

There is no default superuser and no built-in password. Create one with
`python manage.py createsuperuser`, or set `DJANGO_SUPERUSER_USERNAME` /
`DJANGO_SUPERUSER_PASSWORD` and run `python manage.py create_default_superuser`.

> ⚠️ **The app itself has no authentication.** Every view — including creating,
> editing and deleting invoices — is reachable by anyone who knows the URL.
> `/admin` is protected, the rest of the site is not. Put HTTP basic auth in
> nginx in front of it, or add `login_required`, before treating the deployment
> as private.

## CI

Every push to any branch:
1. GitHub Actions runs all 69 tests
2. Checks for missing migrations
3. Builds the Docker image to verify it compiles

Deployment is manual — see **Deploying to the VPS** above.

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
