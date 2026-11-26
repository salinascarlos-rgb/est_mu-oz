from django.contrib import admin
from .models import Status, Currency, Country, ExchangeRate

@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'symbol')

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('currency', 'date', 'rate')
    list_filter = ('currency',)
    date_hierarchy = 'date'

# Títulos del admin
admin.site.site_header = 'EST MUÑOZ - Administración'
admin.site.site_title = 'EST MUÑOZ'
admin.site.index_title = 'Panel de administración'
