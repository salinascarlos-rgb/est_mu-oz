from django.contrib import admin
from .models import MovementType, LocationInventory, InventoryMovements, Stock

@admin.register(MovementType)
class MovementTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'symbol', 'direction')

@admin.register(LocationInventory)
class LocationInventoryAdmin(admin.ModelAdmin):
    list_display = ('id_location', 'name', 'code', 'status', 'main_location', 'location')

@admin.register(InventoryMovements)
class InventoryMovementsAdmin(admin.ModelAdmin):
    list_display = ('id_inventory_movement', 'id_location', 'id_material', 'quantity', 'unit_type', 'price', 'currency', 'exchange_rate', 'movement_type', 'reference')

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('date', 'id_location', 'id_material', 'quantity', 'avg_price_usd', 'total_value_usd')
    list_filter = ('id_location',)
    date_hierarchy = 'date'

