from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import (
    Buyer,
    Invoice,
    InvoiceItem,
    SellerProfile,
    recalculate_chain,
    suppress_recalc,
)

# Item rows drawn on the paper by default — matches the printed A4 grid.
SHEET_MIN_ROWS = 14


# ─── Parsing helpers ─────────────────────────────────────────
def to_int(value, default=0):
    """POST string → whole number. Tolerates '1,000' and '1000.00'."""
    try:
        text = str(value).replace(',', '').strip()
        return int(Decimal(text)) if text else default
    except (InvalidOperation, ValueError, TypeError):
        return default


def to_decimal(value, default=Decimal('0')):
    """POST string → Decimal, keeping fractional quantities like '2.5'."""
    try:
        text = str(value).replace(',', '').strip()
        return Decimal(text) if text else default
    except (InvalidOperation, ValueError, TypeError):
        return default


def _lookup(model, raw_pk):
    """Fetch by pk from raw POST input; a blank or junk id is simply 'not found'."""
    try:
        return model.objects.filter(pk=int(raw_pk)).first()
    except (TypeError, ValueError):
        return None


def _at(values, index, default=''):
    """Index into a POST list without exploding when the lists differ in length."""
    return values[index] if index < len(values) else default


def _parse_items(request):
    """Build item dicts from the parallel product_name[]/quantity[]/... lists."""
    names = request.POST.getlist('product_name[]')
    quantities = request.POST.getlist('quantity[]')
    boxes_list = request.POST.getlist('boxes[]')
    unit_prices = request.POST.getlist('unit_price[]')

    rows = []
    for i, raw_name in enumerate(names):
        name = (raw_name or '').strip()
        if not name:
            continue
        rows.append({
            'product_name': name[:100],
            'quantity': to_decimal(_at(quantities, i)),
            'boxes': to_decimal(_at(boxes_list, i)),
            'unit_price': to_int(_at(unit_prices, i)),
            'order': len(rows),
        })
    return rows


@transaction.atomic
def _persist_invoice(invoice, seller, buyer, date, fees, rows, seller_details):
    """
    Create or update an invoice and replace its items, as one transaction.

    Balance recalculation is suppressed while the rows churn and runs once at
    the end — for the old buyer too, when an invoice moves between buyers.
    """
    previous_buyer = invoice.buyer if invoice is not None and invoice.pk else None

    with suppress_recalc():
        if invoice is None:
            invoice = Invoice()
        invoice.seller = seller
        invoice.buyer = buyer
        invoice.date = date
        invoice.delivery_fee = fees['delivery_fee']
        invoice.deduction = fees['deduction']
        invoice.payment_received = fees['payment_received']
        for field, value in seller_details.items():
            setattr(invoice, field, value)
        invoice.save()

        invoice.invoiceitem_set.all().delete()
        for row in rows:
            InvoiceItem.objects.create(invoice=invoice, **row)

    recalculate_chain(buyer)
    if previous_buyer is not None and previous_buyer.pk != buyer.pk:
        recalculate_chain(previous_buyer)

    invoice.refresh_from_db()
    return invoice


# ─── Dashboard ───────────────────────────────────────────────
def dashboard(request):
    recent_invoices = Invoice.objects.select_related('buyer', 'seller').order_by('-date', '-created_at')[:10]
    buyers = Buyer.objects.all().order_by('name')
    context = {
        'recent_invoices': recent_invoices,
        'buyers': buyers,
    }
    return render(request, 'dashboard.html', context)


# ─── The sheet: create + edit directly on the printed layout ──
def _render_sheet(request, invoice=None):
    sellers = list(SellerProfile.objects.all())
    buyers = list(Buyer.objects.all().order_by('name'))
    default_seller = next((s for s in sellers if s.is_default), None)

    if invoice is not None:
        items = list(invoice.invoiceitem_set.all())
        selected_buyer = invoice.buyer
        selected_seller = invoice.seller
        date_value = invoice.date
        previous_balance = invoice.previous_balance
    else:
        items = []
        preset = request.GET.get('buyer')
        selected_buyer = next((b for b in buyers if str(b.pk) == str(preset)), None)
        selected_seller = default_seller
        date_value = timezone.localdate()
        previous_balance = selected_buyer.get_current_balance() if selected_buyer else 0
        # A blank sheet starts from the default profile, then is freely typed over.
        invoice = Invoice()
        invoice.fill_seller_from_profile(default_seller)
        invoice.date = date_value

    context = {
        'invoice': invoice,
        'is_saved': invoice is not None and invoice.pk is not None,
        'items': items,
        'blank_rows': range(max(0, SHEET_MIN_ROWS - len(items))),
        'sellers': sellers,
        'buyers': buyers,
        'selected_buyer': selected_buyer,
        'selected_seller': selected_seller,
        'date_value': date_value,
        'previous_balance': previous_balance,
    }
    return render(request, 'invoice_sheet.html', context)


def _seller_profile_for(invoice, typed):
    """
    The sheet types seller details rather than picking a profile, but the FK
    still needs a row. Reuse the invoice's own seller, else the default, else
    seed a profile from what was typed.
    """
    if invoice is not None and invoice.pk:
        return invoice.seller
    profile = (SellerProfile.objects.filter(is_default=True).first()
               or SellerProfile.objects.first())
    if profile is not None:
        return profile
    return SellerProfile.objects.create(
        company_name=typed['seller_name'] or '판매자',
        address=typed['seller_address'],
        phone=typed['seller_phone'],
        bank_account=typed['seller_bank_account'],
        fax=typed['seller_fax'],
        is_default=True,
    )


def _handle_sheet_post(request, invoice=None):
    """Shared POST handling for the create and edit sheets."""
    buyer = _lookup(Buyer, request.POST.get('buyer'))

    typed = {
        'seller_name': request.POST.get('seller_name', '').strip()[:100],
        'seller_address': request.POST.get('seller_address', '').strip()[:255],
        'seller_phone': request.POST.get('seller_phone', '').strip()[:50],
        'seller_bank_account': request.POST.get('seller_bank_account', '').strip()[:100],
        'seller_fax': request.POST.get('seller_fax', '').strip()[:50],
    }
    seller = _seller_profile_for(invoice, typed)

    if buyer is None:
        messages.error(request, '거래처를 선택해주세요.')
        return None

    date = parse_date(request.POST.get('date') or '') or timezone.localdate()
    fees = {
        'delivery_fee': to_int(request.POST.get('delivery_fee')),
        'deduction': to_int(request.POST.get('deduction')),
        'payment_received': to_int(request.POST.get('payment_received')),
    }
    rows = _parse_items(request)

    return _persist_invoice(invoice, seller, buyer, date, fees, rows, typed)


def invoice_new(request):
    if request.method == 'POST':
        invoice = _handle_sheet_post(request)
        if invoice is not None:
            messages.success(request, '계산서가 저장되었습니다.')
            return redirect('invoice_edit', pk=invoice.pk)
    return _render_sheet(request)


def invoice_edit(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        saved = _handle_sheet_post(request, invoice=invoice)
        if saved is not None:
            messages.success(request, '계산서가 저장되었습니다.')
            return redirect('invoice_edit', pk=saved.pk)
        invoice.refresh_from_db()
    return _render_sheet(request, invoice=invoice)


def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    items = invoice.invoiceitem_set.all()
    context = {'invoice': invoice, 'items': items}
    return render(request, 'invoice_detail.html', context)


def invoice_print(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    items = invoice.invoiceitem_set.all()
    context = {
        'invoice': invoice,
        'items': items,
        'empty_rows': range(max(0, SHEET_MIN_ROWS - items.count())),
    }
    return render(request, 'invoice_print.html', context)


def invoice_share(request, pk):
    """Phone-facing page: renders the invoice to a PNG and offers the share sheet."""
    invoice = get_object_or_404(Invoice, pk=pk)
    items = invoice.invoiceitem_set.all()
    context = {
        'invoice': invoice,
        'items': items,
        'empty_rows': range(max(0, SHEET_MIN_ROWS - items.count())),
    }
    return render(request, 'invoice_share.html', context)


def invoice_list(request):
    buyer_id = request.GET.get('buyer')
    invoices = Invoice.objects.select_related('buyer', 'seller').order_by('-date', '-created_at')
    selected_buyer = None
    if buyer_id:
        invoices = invoices.filter(buyer_id=buyer_id)
        selected_buyer = get_object_or_404(Buyer, pk=buyer_id)
    buyers = Buyer.objects.all().order_by('name')
    context = {
        'invoices': invoices,
        'buyers': buyers,
        'selected_buyer': selected_buyer,
    }
    return render(request, 'invoice_list.html', context)


def invoice_delete(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        buyer = invoice.buyer
        with suppress_recalc():
            invoice.delete()
        recalculate_chain(buyer)
        messages.success(request, '계산서가 삭제되었습니다.')
        return redirect('invoice_list')
    return render(request, 'invoice_confirm_delete.html', {'invoice': invoice})


# ─── Buyer ───────────────────────────────────────────────────
def buyer_list(request):
    buyers = Buyer.objects.all().order_by('name')
    return render(request, 'buyer_list.html', {'buyers': buyers})


def buyer_new(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        has_delivery_fee = request.POST.get('has_delivery_fee') == 'on'
        has_deduction = request.POST.get('has_deduction') == 'on'
        notes = request.POST.get('notes', '')
        if name:
            Buyer.objects.create(
                name=name,
                has_delivery_fee=has_delivery_fee,
                has_deduction=has_deduction,
                notes=notes,
            )
            messages.success(request, f'{name} 거래처가 추가되었습니다.')
            return redirect('buyer_list')
        else:
            messages.error(request, '거래처명을 입력해주세요.')
    return render(request, 'buyer_form.html', {'buyer': None})


def buyer_edit(request, pk):
    buyer = get_object_or_404(Buyer, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, '거래처명을 입력해주세요.')
            return render(request, 'buyer_form.html', {'buyer': buyer})
        buyer.name = name
        buyer.has_delivery_fee = request.POST.get('has_delivery_fee') == 'on'
        buyer.has_deduction = request.POST.get('has_deduction') == 'on'
        buyer.notes = request.POST.get('notes', '')
        buyer.save()
        messages.success(request, '거래처 정보가 수정되었습니다.')
        return redirect('buyer_list')
    return render(request, 'buyer_form.html', {'buyer': buyer})


# ─── Seller Settings ─────────────────────────────────────────
def settings_view(request):
    sellers = SellerProfile.objects.all()
    return render(request, 'settings.html', {'sellers': sellers})


def seller_new(request):
    if request.method == 'POST':
        SellerProfile.objects.create(
            company_name=request.POST.get('company_name', '').strip(),
            address=request.POST.get('address', '').strip(),
            phone=request.POST.get('phone', '').strip(),
            bank_account=request.POST.get('bank_account', '').strip(),
            fax=request.POST.get('fax', '').strip(),
            is_default=request.POST.get('is_default') == 'on',
        )
        messages.success(request, '판매자 정보가 추가되었습니다.')
        return redirect('settings')
    return render(request, 'seller_form.html', {'seller': None})


def seller_edit(request, pk):
    seller = get_object_or_404(SellerProfile, pk=pk)
    if request.method == 'POST':
        seller.company_name = request.POST.get('company_name', '').strip()
        seller.address = request.POST.get('address', '').strip()
        seller.phone = request.POST.get('phone', '').strip()
        seller.bank_account = request.POST.get('bank_account', '').strip()
        seller.fax = request.POST.get('fax', '').strip()
        seller.is_default = request.POST.get('is_default') == 'on'
        seller.save()
        messages.success(request, '판매자 정보가 수정되었습니다.')
        return redirect('settings')
    return render(request, 'seller_form.html', {'seller': seller})


# ─── AJAX ────────────────────────────────────────────────────
def buyer_balance(request, pk):
    """Previous balance for a buyer, optionally excluding the invoice being edited."""
    buyer = get_object_or_404(Buyer, pk=pk)
    exclude_pk = request.GET.get('exclude')

    invoices = buyer.invoice_set.all()
    if exclude_pk:
        invoices = invoices.exclude(pk=exclude_pk)
    last = invoices.order_by('-date', '-created_at').first()

    balance = last.current_balance if last else 0
    return JsonResponse({
        'previous_balance': int(balance),
        'has_delivery_fee': buyer.has_delivery_fee,
        'has_deduction': buyer.has_deduction,
    })
