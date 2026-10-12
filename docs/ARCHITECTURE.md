# How the invoice system works

A developer's walkthrough of `meshtirop1/invoice_generator` — the reasoning
behind the design, not just what the files contain.

---

## The shape

Django 6, function-based views, **no forms layer** — views read `request.POST`
directly. Four models, ~370 lines of views, everything server-rendered. No DRF,
no JS framework, no build step. Two vendored JS libraries in `public/vendor/`,
served by WhiteNoise at the site root.

Two ideas drive the whole design:

1. **The printed artifact is the input surface.** There is no "form page" that
   later becomes an invoice.
2. **An invoice's total is a derived value, not a stored fact** — even though
   it is stored.

Everything else falls out of those two.

```
inv/settings.py          Environment-aware config, VPS + reverse proxy
invoice/models.py        4 models + balance recalculation + signals
invoice/views.py         16 views, all function-based
templates/_paper_css.html   Shared paper styling  (sheet = print = PNG)
templates/_paper.html       Shared read-only paper markup
templates/invoice_sheet.html  The editable A4 sheet (create + edit)
templates/invoice_share.html  Phone page: PNG + native share sheet
public/vendor/           html-to-image, qrcode.js (vendored, no CDN)
```

---

## 1. Balances — invoices are independent

Each invoice stands alone:

```
current_balance = Σ(qty × boxes × unit_price)
                + delivery_fee − deduction − payment_received
```

Nothing carries between invoices.

### History, because the code still carries its shape

The app originally ran a **running tab**: `Invoice.save()` snapshotted
`previous_balance` from the buyer's last invoice, so each invoice opened with
what was still owed. That was deliberate — wholesale shops pay on credit, and
the paper form has a 전 잔 액 row for exactly this.

It was dropped on request: the owner wanted every invoice to read as its own
sale, and the carry-forward made each new invoice look inflated.

Two artefacts of that history remain, both on purpose:

- **`previous_balance` is still a column**, always written as `0`. Keeping it
  means the decision reverses without a migration, and the 전 잔 액 row renders
  blank while it is zero, which is what the reference form looks like anyway.
- **`recalculate_balances(buyer)`** still walks every invoice for a buyer rather
  than just the one that changed. It no longer carries a running total, but an
  invoice's own figure still has to be recomputed whenever its items change, and
  a per-buyer sweep is cheap (two queries) and impossible to get wrong.

### How it stays correct: signals, not discipline

`models.py` hooks `post_save` / `post_delete` on both `Invoice` and
`InvoiceItem`. Any write anywhere — a view, the admin, `manage.py shell`, a data
migration — recomputes the affected invoices.

Two things make that safe:

- **`bulk_update` does not emit signals.** That is the entire reason
  recalculation cannot recurse into itself.
- **`suppress_recalc()`** is a `threading.local` flag. Writing 15 items would
  otherwise fire 15 full recalcs, so bulk paths suppress and call
  `recalculate_balances` once at the end.

### The admin was the sneakiest case

Django's `ModelAdmin` saves the `Invoice` row **first**, then inline
`InvoiceItem`s. The old `save()` forced `current_balance = 0` on create and
nothing ran afterwards — so **every invoice created through `/admin` was
permanently zero**. The signal fixes it generically; `InvoiceAdmin.save_related()`
also calls it explicitly, and the balance fields are `readonly_fields`, since
typing into them would be a lie.

`_item_changed` guards `Invoice.DoesNotExist` — during a cascading invoice
delete, the item's parent row may already be gone.

### The one thing independence costs

Nothing tracks a cumulative debt. If a shop has three unpaid invoices, no
invoice shows the combined figure. `Buyer.get_current_balance()` compensates by
summing `current_balance` across the buyer's invoices, and that total is what
the dashboard and buyer list display — but it appears nowhere on the printed
sheet.

## 2. The sheet — how the paper became the form

`templates/invoice_sheet.html`. It is a **standalone page**, deliberately not
extending `base.html` — no nav, no cards. The whole premise is that the user does
not navigate.

The mechanism is unglamorous: `<input>` elements inside the real print table,
styled to be invisible.

```css
.f { background: transparent; border: none; outline: none;
     font: inherit; text-align: center; width: 100%; }
.f:hover { background: #eef3ff; }
.f:focus { background: #d8e6ff; box-shadow: inset 0 0 0 2px #2f6fd0; }
```

The cell borders you see are the **table's** borders — the same ones that print.
Nothing is faked.

### Spreadsheet navigation

A small matrix walk. `matrix()` builds a 2-D array of `.cell` inputs per row;
`locate(input)` finds `{r, c}`; `focusCell(r, c)` moves.

| Key | Behaviour |
|---|---|
| `Tab` / `Shift+Tab` | Free — DOM order already runs left-to-right |
| `Enter`, `↓` | Same column, next row (appends a row past the end) |
| `↑` | Same column, previous row |
| `←` / `→` | Jump cells **only** when the caret is already at the edge of the text |

That last rule is what makes it feel like a spreadsheet rather than a form.
Typing in the last row appends a new one — `isLastRow()` plus `addRow()`, which
clones the first row, clears it, and re-wires listeners.

### The date field is a trick worth knowing

`<input type="date">` renders in the **browser's** locale — `08/20/2026` on a
US-locale machine, with a calendar glyph. Unacceptable on a Korean invoice. So:

```html
<div class="date-line">
  <span id="dateDisplay">2026년 09월 07일</span>
  <input type="date" id="dateField">   <!-- position:absolute; inset:0; opacity:0 -->
</div>
```

The span is what renders and exports; the real input sits invisibly on top so
clicking still opens the native picker. `renderDate()` syncs the span on
`change`.

### Money formatting

Grouped (`12,000`) on blur, plain on focus. The server strips separators anyway
(`to_int`), so nothing depends on the client. Zero renders as an **empty cell**,
matching the paper convention.

---

## 3. The save path

`invoice_new` and `invoice_edit` both funnel into `_handle_sheet_post`
(`views.py:184`) → `_persist_invoice` (`views.py:78`).

Parsing is defensive because the payload is four **parallel arrays**
(`product_name[]`, `quantity[]`, `boxes[]`, `unit_price[]`):

- `_at(values, i)` returns `''` past the end. The original `quantities[i]` raised
  `IndexError` on a ragged POST — *after* the invoice row was already committed.
- `to_decimal` for qty/boxes (the model is `DecimalField(decimal_places=2)`; the
  old `int()` turned `"2.5"` into `0`), `to_int` for money
  (`decimal_places=0`).
- `_lookup` coerces the pk itself — `Buyer.objects.filter(pk='')` raises
  `ValueError`, it does not return empty.

Then:

```python
@transaction.atomic
def _persist_invoice(invoice, seller, buyer, date, fees, rows, seller_details):
    previous_buyer = invoice.buyer if invoice is not None and invoice.pk else None

    with suppress_recalc():
        ...
        invoice.save()
        invoice.invoiceitem_set.all().delete()
        for row in rows:
            InvoiceItem.objects.create(invoice=invoice, **row)

    recalculate_balances(buyer)
    if previous_buyer is not None and previous_buyer.pk != buyer.pk:
        recalculate_chain(previous_buyer)   # invoice moved between buyers
```

Items are **replaced wholesale, not diffed** — the sheet posts the full grid
every time, so reconciling adds/edits/deletes would be pure complexity.
Consequence: `InvoiceItem` primary keys churn on every save. Fine here, but it
means there is no per-item history.

The two-chain recalc handles reassigning an invoice to a different buyer — both
ledgers shift.

Saving redirects back to `invoice_edit`, not to a detail page. The user stays on
the paper.

---

## 4. Seller details are snapshotted per invoice

`SellerProfile` still exists, but the printed values live **on the invoice**:
`seller_name`, `seller_address`, `seller_phone`, `seller_bank_account`,
`seller_fax` (migration `0003`, with a backfill from the FK).

This is not gold-plating. If the sheet wrote back to `SellerProfile`, fixing a
typo on today's invoice would retroactively rewrite the seller on every invoice
already sent. An issued document has to keep the details it was issued with.

So `SellerProfile` is now only *defaults for a blank sheet*:

- `fill_seller_from_profile()` seeds an unsaved `Invoice()` in `_render_sheet`
- `_seller_profile_for()` resolves the FK silently — reuse the invoice's own,
  else the default, else create one from what was typed, so a fresh database
  cannot deadlock on a required FK

---

## 5. The image pipeline, and the gotcha that will bite you

`html-to-image` serialises the DOM into an SVG `foreignObject` and rasterises it
to canvas. It reads the **HTML**, not live DOM state.

A value the user typed lives in the input's `.value` **property**. The `value`
**attribute** still holds whatever was server-rendered. Serialise naively and you
export a blank invoice.

Hence `freeze()`:

```js
document.querySelectorAll('#paper input')
  .forEach(i => i.setAttribute('value', i.value));

document.querySelectorAll('#paper select').forEach(s =>
  [...s.options].forEach(o => o.selected
    ? o.setAttribute('selected', 'selected')
    : o.removeAttribute('selected')));

document.body.classList.add('exporting');   // strips hover/focus tints
```

Then `toBlob(node, { pixelRatio: 2, backgroundColor: '#ffffff' })` → a
1588×2246 PNG.

Everything is **client-side**. No headless Chromium, no server-side rendering,
nothing extra to install on the VPS.

---

## 6. The QR handoff — why it is not a share button

`navigator.share({ files })` is a **phone API**. On desktop Chrome it is either
absent or will not offer KakaoTalk, and it fundamentally cannot put a file on a
*different device*. So the desktop cannot share; it can only **hand off**.

The QR encodes `https://<host>/invoices/<pk>/share/`. The phone scans it, and
`invoice_share.html`:

1. Renders `_paper.html` full-size in an off-screen div (`left: -10000px`)
2. `toBlob()` → object URL → shown as an `<img>` scaled to the phone
3. Feature-detects `navigator.canShare({ files: [file] })` → show 공유하기, else
   **hide it** and swap the hint to "save then send"

A share button that throws on tap is worse than no button.

The desktop warns when `location.hostname` is `localhost` / `127.0.0.1` — a QR
pointing at loopback is unscannable in effect, and that failure is otherwise
completely silent.

---

## 7. Why the paper lives in partials

`templates/_paper_css.html` and `templates/_paper.html` are included by the
sheet, the print page **and** the share page.

This is load-bearing. The exported PNG must be byte-for-byte what prints, and
what the user edited. Three copies of that CSS would diverge within a week, and
you would only find out when a customer received a wrong-looking invoice. The
sheet layers editing affordances on top; the geometry comes from one file.

---

## 8. Deployment

Self-hosted VPS, nginx → gunicorn, at `https://inv.mtirop.com`. No PaaS.

```bash
cd /path/to/invoice_generator
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo systemctl restart invoice
```

Two settings details that matter behind a proxy:

- `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` — without it
  Django believes every request is plain HTTP, and `SECURE_SSL_REDIRECT` would
  loop forever. nginx must send `proxy_set_header X-Forwarded-Proto $scheme;`.
- `CSRF_TRUSTED_ORIGINS` is **derived from `ALLOWED_HOSTS`** (`https://<host>`
  for each real host). Otherwise the first HTTPS form post fails with a CSRF
  origin error, which is the usual first surprise when moving behind a domain.

`SECURE_SSL_REDIRECT` and HSTS are left opt-in via environment variables —
enabling the redirect while the proxy header is missing takes the site down, and
HSTS is painful to walk back.

---

## Sharp edges

- **No authentication, anywhere.** All 16 views are open on a public domain.
  Anyone with a URL can create, edit and delete invoices and read every buyer's
  balance. `/admin` is protected; nothing else is. This is the big one.
- **Concurrent writes to one buyer race.** Two simultaneous saves read the same
  chain state. No `select_for_update`. Single-user app, so it is theoretical —
  but it is real.
- **N+1 on dashboard and buyer list.** `buyer.get_current_balance()` runs per
  row — roughly 88 extra queries with 44 buyers.
- **No pagination** on the invoice list.
- **Item primary keys churn** on every save (see §3), so there is no per-item
  audit trail.
- `intcomma` needs `{% load humanize %}` **after** `{% extends %}` — Django
  requires `extends` to be the first tag in the template.
- `[hidden]` loses to any class that sets `display`. `.seller-line { display:
  flex }` silently defeated `hidden` on the FAX row until
  `[hidden] { display: none !important }` was added.

---

## Test suite

69 tests, `python manage.py test invoice`. The ones worth knowing about:

| Class | Covers |
|---|---|
| `IndependentInvoiceTest` | Delete, edit, item change and payment each move only their own invoice; per-buyer outstanding total; the admin write order |
| `InvoiceSheetTest` | Sheet render, item replacement, decimals, ragged POST arrays, comma-formatted money |
| `SellerSnapshotTest` | Seller details saved, isolated per invoice, profile untouched, empty database |
| `InvoiceOutputTest` | Print does not drop items past the grid minimum; share page renders |
