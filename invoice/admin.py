from django.contrib import admin
from .models import SellerProfile, Buyer, Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 3


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['buyer', 'seller', 'date', 'current_balance', 'created_at']
    list_filter = ['buyer', 'seller', 'date']
    inlines = [InvoiceItemInline]


@admin.register(Buyer)
class BuyerAdmin(admin.ModelAdmin):
    list_display = ['name', 'has_delivery_fee', 'has_deduction', 'created_at']


@admin.register(SellerProfile)
class SellerAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'phone', 'bank_account', 'is_default']


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ['product_name', 'invoice', 'quantity', 'unit_price', 'amount']