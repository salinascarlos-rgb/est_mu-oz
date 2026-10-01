from django.urls import path
from . import views

app_name = 'purchases'

urlpatterns = [
    path('',views.purchase_order_list, name='purchase_order_list'),
    path('create/', views.purchase_order_form, name='purchase_order_form'),
    path('create_order/', views.create_purchase_order, name='create_purchase_order'),
    path('<int:pk>/detail/', views.purchase_order_detail, name='purchase_order_detail'),
    path('<int:po_pk>/goods-receipt/create/', views.goods_receipt_form, name='goods_receipt_create'),
    path('goods-receipt/post/', views.post_goods_receipt, name='post_goods_receipt'),
    path('<int:po_pk>/invoice/create/', views.purchase_invoice_form, name='purchase_invoice_create'),
    path('api/post_invoice/', views.post_purchase_invoice, name='post_purchase_invoice'),
    path('api/supplier/details/<str:supplier_id>/', views.get_supplier_details, name='api_supplier_details'),
    path('api/material/details/<str:material_id>/', views.get_material_details, name='api_material_details'),
]