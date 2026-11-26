from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.stock_list, name='stock_list'),
    path('movements/', views.movements_list, name='movements_list'),
    path('adjustment/', views.adjustment_create, name='adjustment_create'),
    path('transfer/', views.transfer_create, name='transfer_create'),
]
