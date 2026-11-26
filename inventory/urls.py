from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.stock_list, name='stock_list'),
    path('stock/', views.stock_list, name='stock'),                  # misma ruta del curso
    path('movements/', views.movements_list, name='movements_list'),
    path('movements/create/', views.create_movement, name='create_movement'),
    path('adjustment/', views.adjustment_create, name='adjustment_create'),
    path('transfer/', views.transfer_create, name='transfer_create'),
]
