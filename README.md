# 계산서 시스템 — Invoice Management System

A professional invoice management web application built with Django, designed for Korean small businesses. Manage buyers, generate invoices, track balances, and print clean A4 invoices — all from the browser.

---

## Live Demo

> Hosted on PythonAnywhere:
> `https://ahirn.pythonanywhere.com`

---

## Features

- **Invoice Management** — Create, view, print, and delete invoices
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
│   ├── tests.py                # 42 tests
│   └── management/
│       └── commands/
│           ├── create_default_superuser.py
│           └── seed_buyers.py  # Seeds 44 buyers from old system
│
├── templates/                  # HTML templates
│   ├── base.html               # Nav, PWA meta, install banner
│   ├── dashboard.html
│   ├── invoice_print.html      # Print-optimised A4 layout
│   └── ...
│
├── public/                     # Served at site root via WhiteNoise
│   ├── manifest.json           # PWA manifest
│   ├── sw.js                   # Service worker
│   └── icons/                  # SVG app icons (192 & 512)
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

**42 tests** covering:
- Model logic (balance calculations, auto-amounts, default seller enforcement)
- All views (GET/POST, redirects, 404s)
- AJAX endpoints
- Edge cases (empty rows, zero quantities, balance carry-over)

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
1. GitHub Actions runs all 42 tests
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

---

## License

Private — All rights reserved.
