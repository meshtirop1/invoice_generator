from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages

from .models import SellerProfile, Buyer, Invoice, InvoiceItem


def to_int(value, default=0):
    """Safely convert POST string to int."""
    try:
        return int(str(value).replace(',', '').strip()) if value else default
    except (ValueError, TypeError):
        return default


# ─── Dashboard ───────────────────────────────────────────────
def dashboard(request):
    recent_invoices = Invoice.objects.select_related('buyer', 'seller').order_by('-date', '-created_at')[:10]
    buyers = Buyer.objects.all().order_by('name')
    context = {
        'recent_invoices': recent_invoices,
        'buyers': buyers,
    }
    return render(request, 'dashboard.html', context)


# ─── Invoice ─────────────────────────────────────────────────
def invoice_new(request):
    sellers = SellerProfile.objects.all()
    buyers = Buyer.objects.all().order_by('name')
    default_seller = SellerProfile.objects.filter(is_default=True).first()

    if request.method == 'POST':
        try:
            seller_id = request.POST.get('seller')
            buyer_id = request.POST.get('buyer')
            date = request.POST.get('date')
            delivery_fee = to_int(request.POST.get('delivery_fee'))
            deduction = to_int(request.POST.get('deduction'))
            payment_received = to_int(request.POST.get('payment_received'))

            seller = get_object_or_404(SellerProfile, pk=seller_id)
            buyer = get_object_or_404(Buyer, pk=buyer_id)

            # Get previous balance BEFORE creating invoice
            last_invoice = buyer.get_last_invoice()
            previous_balance = last_invoice.current_balance if last_invoice else 0

            # Step 1: Save invoice to get a PK
            invoice = Invoice.objects.create(
                seller=seller,
                buyer=buyer,
                date=date,
                delivery_fee=delivery_fee,
                deduction=deduction,
                payment_received=payment_received,
                previous_balance=previous_balance,
                current_balance=0,
            )

            # Step 2: Save items — cast strings to numbers
            product_names = request.POST.getlist('product_name[]')
            quantities    = request.POST.getlist('quantity[]')
            boxes_list    = request.POST.getlist('boxes[]')
            unit_prices   = request.POST.getlist('unit_price[]')

            for i, name in enumerate(product_names):
                if name.strip():
                    qty   = to_int(quantities[i])
                    boxes = to_int(boxes_list[i])
                    price = to_int(unit_prices[i])
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        product_name=name.strip(),
                        quantity=qty,
                        boxes=boxes,
                        unit_price=price,
                        order=i,
                    )

            # Step 3: Recalculate current_balance now that items exist
            invoice.current_balance = invoice.calculate_current_balance()
            invoice.save()

            messages.success(request, '계산서가 저장되었습니다.')
            return redirect('invoice_detail', pk=invoice.pk)

        except Exception as e:
            messages.error(request, f'오류가 발생했습니다: {str(e)}')

    context = {
        'sellers': sellers,
        'buyers': buyers,
        'default_seller': default_seller,
    }
    return render(request, 'invoice_form.html', context)


def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    items = invoice.invoiceitem_set.all()
    context = {'invoice': invoice, 'items': items}
    return render(request, 'invoice_detail.html', context)


def invoice_print(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    items = invoice.invoiceitem_set.all()
    empty_rows = max(0, 12 - items.count())
    context = {
        'invoice': invoice,
        'items': items,
        'empty_rows': range(empty_rows),
    }
    return render(request, 'invoice_print.html', context)


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
        invoice.delete()
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
        buyer.name = request.POST.get('name', '').strip()
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
    buyer = get_object_or_404(Buyer, pk=pk)
    last = buyer.get_last_invoice()
    balance = last.current_balance if last else 0
    return JsonResponse({'previous_balance': int(balance)})