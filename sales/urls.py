from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.sales_order_list, name='sales_order_list'),
    path('create/', views.sales_order_form, name='sales_order_form'),
    path('<int:pk>/detail/', views.sales_order_detail, name='sales_order_detail'),
    path('api/customer/details/<str:customer_id>/', views.get_customer_details, name='api_customer_details'),
    path('api/stock/', views.get_stock_data, name='api_stock_data'),
]
