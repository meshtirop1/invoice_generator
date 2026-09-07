from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    # PWA
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),

    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Invoices
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/new/', views.invoice_new, name='invoice_new'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/edit/', views.invoice_edit, name='invoice_edit'),
    path('invoices/<int:pk>/print/', views.invoice_print, name='invoice_print'),
    path('invoices/<int:pk>/share/', views.invoice_share, name='invoice_share'),
    path('invoices/<int:pk>/delete/', views.invoice_delete, name='invoice_delete'),

    # Buyers
    path('buyers/', views.buyer_list, name='buyer_list'),
    path('buyers/new/', views.buyer_new, name='buyer_new'),
    path('buyers/<int:pk>/edit/', views.buyer_edit, name='buyer_edit'),

    # Seller settings
    path('settings/', views.settings_view, name='settings'),
    path('settings/seller/new/', views.seller_new, name='seller_new'),
    path('settings/seller/<int:pk>/edit/', views.seller_edit, name='seller_edit'),

    # AJAX
    path('api/buyer/<int:pk>/balance/', views.buyer_balance, name='buyer_balance'),
]