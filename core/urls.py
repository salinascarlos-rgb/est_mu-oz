from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False), name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
]
