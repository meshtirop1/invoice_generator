# 계산서 시스템 — Invoice Management System

A professional invoice management web application built with Django, designed for Korean small businesses. Manage buyers, generate invoices, track balances, and print clean A4 invoices — all from the browser.

---

## Live Demo

> Hosted on PythonAnywhere:
> `https://ahirn.pythonanywhere.com`

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
| Hosting | PythonAnywhere |
| CI/CD | GitHub Actions |
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
│   ├── ci.yml                  # Run tests on every push
│   └── deploy.yml              # Deploy to Railway on main
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

## Deploying to PythonAnywhere

### 1. Open a Bash console and clone

```bash
git clone https://github.com/meshtirop1/invoice_generator.git
cd invoice_generator
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py create_default_superuser
python manage.py seed_buyers
python manage.py collectstatic --noinput
```

### 2. Create Web App

- Go to **Web** tab → **Add a new web app**
- Choose **Manual configuration** → **Python 3.12**

### 3. Set the WSGI file

Click the WSGI config file link and replace all contents with:

```python
import os, sys

path = '/home/YOUR_USERNAME/invoice_generator'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'inv.settings'
os.environ['PYTHONANYWHERE_USERNAME'] = 'YOUR_USERNAME'
os.environ['SECRET_KEY'] = 'your-strong-secret-key-here'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### 4. Set virtualenv path

```
/home/YOUR_USERNAME/invoice_generator/.venv
```

### 5. Add static files mapping

| URL | Directory |
|---|---|
| `/static/` | `/home/YOUR_USERNAME/invoice_generator/staticfiles` |

### 6. Reload the web app

Visit `https://YOUR_USERNAME.pythonanywhere.com`

---

## Updating a Live Deployment

```bash
cd invoice_generator
git pull origin main
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

Then reload the web app from the PythonAnywhere **Web** tab.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | Yes | insecure dev key | Django secret key |
| `DEBUG` | No | `False` | Enable debug mode |
| `ALLOWED_HOSTS` | No | `*` | Comma-separated allowed hosts |
| `DATABASE_URL` | No | SQLite | PostgreSQL connection string |
| `PYTHONANYWHERE_USERNAME` | No | — | Auto-adds PA domain to ALLOWED_HOSTS |

---

## Default Superuser

| Field | Value |
|---|---|
| Username | `mtirop` |
| Password | `12345678` |
| Admin URL | `/admin` |

> ⚠️ Change the password after first login at `/admin/auth/user/mtirop/password/`

---

## CI/CD Pipeline

Every push to any branch:
1. GitHub Actions runs all 69 tests
2. Builds the Docker image to verify it compiles

Every push to `main`:
1. Tests pass → Railway auto-deploy triggered (if configured)

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
