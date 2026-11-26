import csv
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from core.models import Currency
from core.exchange_rates import base_currency_code
from users.models import UserRole
from .forms import InventoryMovementForm, TransferForm, active_locations
from .models import InventoryMovements, MovementType, Stock
from . import services


def get_inventory_permission(user):
    """Nivel de permiso máximo del usuario en el módulo de inventario (0, 1 o 2)."""
    return UserRole.objects.filter(user_id=user).aggregate(
        max_permission=Max('role__inventory')
    )['max_permission'] or 0


def csv_response(filename):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('﻿'.encode('utf-8'))
    return response, csv.writer(response)


def parse_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date() if value else None
    except ValueError:
        return None


@login_required
def stock_list(request):

    max_permission = get_inventory_permission(request.user)
    if max_permission == 0:
        return redirect('dashboard')

    movements = InventoryMovements.objects.all()

    location = request.GET.get('location')
    material = request.GET.get('material', '').strip()
    show_zero = request.GET.get('show_zero') == '1'

    if location:
        movements = movements.filter(id_location__pk=location)
    if material:
        movements = movements.filter(
            Q(id_material__id_material__icontains=material) | Q(id_material__name__icontains=material)
        )

    # Filtro por fecha (video 17): hoy = existencias en vivo; fecha pasada = foto diaria
    today = timezone.localdate()
    selected_date = parse_date(request.GET.get('date')) or today
    if selected_date > today:
        selected_date = today
    is_snapshot = selected_date < today

    if is_snapshot:
        snapshot = Stock.objects.filter(date=selected_date).select_related('id_location', 'id_material', 'unit_type')
        if location:
            snapshot = snapshot.filter(id_location__pk=location)
        if material:
            snapshot = snapshot.filter(
                Q(id_material__id_material__icontains=material) | Q(id_material__name__icontains=material)
            )
        if not show_zero:
            snapshot = snapshot.exclude(quantity=0)
        rows = [{
            'id_location': s.id_location_id, 'id_location__code': s.id_location.code, 'id_location__name': s.id_location.name,
            'id_material': s.id_material_id, 'id_material__id_material': s.id_material.id_material,
            'id_material__name': s.id_material.name,
            'id_material__unit__symbol': s.unit_type.symbol if s.unit_type else '',
            'stock': s.quantity, 'reserved': s.reserved_quantity, 'available': s.quantity - s.reserved_quantity,
            'avg_cost': None, 'value': None, 'value_base': s.total_value_usd,
        } for s in snapshot.order_by('id_location__code', 'id_material__id_material')]
        total_value = None
        total_value_base = sum((row['value_base'] for row in rows), 0)
        snapshot_date = selected_date
    else:
        rows = services.stock_by_location(movements)
        if not show_zero:
            rows = rows.exclude(stock=0)

        rows = list(rows)
        costs = services.average_costs({row['id_material'] for row in rows})
        base_values, snapshot_date = services.latest_stock_values()
        total_value = 0
        total_value_base = 0
        try:
            from sales.services import reserved_map
            reserved = reserved_map()
        except ImportError:
            reserved = {}
        for row in rows:
            row['reserved'] = reserved.get((row['id_material'], row['id_location']), 0)
            row['available'] = row['stock'] - row['reserved']
            row['avg_cost'] = costs.get(row['id_material'], 0)
            row['value'] = row['stock'] * row['avg_cost']
            row['value_base'] = base_values.get((row['id_material'], row['id_location']))
            total_value += row['value']
            total_value_base += row['value_base'] or 0

    currency = Currency.objects.order_by('pk').first()
    currency_symbol = currency.symbol if currency else ''
    base_currency = base_currency_code()

    if request.GET.get('export') == 'csv':
        response, writer = csv_response(f'inventory_stock_{selected_date.isoformat()}.csv')
        writer.writerow(['Location Code', 'Location', 'Material ID', 'Material', 'Unit', 'Stock', 'Reserved', 'Available', 'Average Cost', 'Value', 'Currency', f'Value {base_currency}'])
        for row in rows:
            writer.writerow([
                row['id_location__code'], row['id_location__name'],
                row['id_material__id_material'], row['id_material__name'], row['id_material__unit__symbol'],
                row['stock'], row['reserved'], row['available'],
                round(row['avg_cost'], 2) if row['avg_cost'] is not None else '',
                round(row['value'], 2) if row['value'] is not None else '',
                currency_symbol if row['value'] is not None else '',
                round(row['value_base'], 2) if row['value_base'] is not None else '',
            ])
        return response

    page_obj = Paginator(rows, 20).get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'locations': active_locations(),
        'total_value': total_value,
        'total_value_base': total_value_base,
        'base_currency': base_currency,
        'snapshot_date': snapshot_date,
        'selected_date': selected_date,
        'is_snapshot': is_snapshot,
        'today': today,
        'total_rows': len(rows),
        'currency_symbol': currency_symbol,
        'show_zero': show_zero,
        'can_edit': max_permission >= 2,
        'active_tab': 'stock',
    }
    return render(request, 'inventory/stock_list.html', context)


@login_required
def movements_list(request):

    max_permission = get_inventory_permission(request.user)
    if max_permission == 0:
        return redirect('dashboard')

    movements = InventoryMovements.objects.select_related(
        'id_location', 'id_material', 'unit_type', 'movement_type', 'currency', 'created_by'
    ).order_by('-created_at')

    location = request.GET.get('location')
    material = request.GET.get('material', '').strip()
    movement_type = request.GET.get('movement_type')
    date_from = parse_date(request.GET.get('date_from'))
    date_to = parse_date(request.GET.get('date_to'))

    if location:
        movements = movements.filter(id_location__pk=location)
    if material:
        movements = movements.filter(
            Q(id_material__id_material__icontains=material) | Q(id_material__name__icontains=material)
        )
    if movement_type:
        movements = movements.filter(movement_type__symbol=movement_type)
    if date_from:
        movements = movements.filter(created_at__date__gte=date_from)
    if date_to:
        movements = movements.filter(created_at__date__lte=date_to)

    if request.GET.get('export') == 'csv':
        response, writer = csv_response('inventory_movements.csv')
        writer.writerow(['Movement ID', 'Date', 'Type', 'Location', 'Material ID', 'Material', 'Quantity', 'Unit', 'Price', 'Currency', 'Reference', 'User'])
        for mv in movements:
            writer.writerow([
                mv.id_inventory_movement, mv.created_at.strftime('%Y-%m-%d %H:%M'), mv.movement_type.symbol,
                mv.id_location.code, mv.id_material.id_material, mv.id_material.name,
                mv.quantity * mv.movement_type.direction, mv.unit_type.symbol,
                round(mv.price, 2), mv.currency.symbol, mv.reference,
                mv.created_by.username if mv.created_by else 'N/A',
            ])
        return response

    page_obj = Paginator(movements, 20).get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'locations': active_locations(),
        'movement_types': MovementType.objects.order_by('symbol'),
        'can_edit': max_permission >= 2,
        'active_tab': 'movements',
    }
    return render(request, 'inventory/movements_list.html', context)


@login_required
def create_movement(request):
    """New Movement Entry (video 17): pérdida, uso interno y ajustes."""

    max_permission = get_inventory_permission(request.user)
    if max_permission == 0:
        return redirect('dashboard')
    if max_permission < 2:
        return redirect('inventory:stock_list')

    form = InventoryMovementForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        try:
            movement = services.register_movement(
                material=data['material'], location=data['location'], movement_type=data['movement_type'],
                quantity=data['quantity'], cost_center=data['cost_center'], description=data['description'],
                user=request.user,
            )
        except ValueError as e:
            form.add_error(None, f"Process error: {e}")
        else:
            messages.success(request, f"Movement {movement.id_inventory_movement} registered.")
            return redirect('inventory:movements_list')

    context = {
        'form': form, 'title': 'New Movement Entry', 'submit_label': 'Create Movement',
        'active_tab': 'create', 'can_edit': True,
        'cost_center_required': ['INT_USE'],
    }
    return render(request, 'inventory/movement_form.html', context)


@login_required
def adjustment_create(request):
    """Ruta antigua: los ajustes ahora están en New Movement."""
    return redirect('inventory:create_movement')


@login_required
def transfer_create(request):

    max_permission = get_inventory_permission(request.user)
    if max_permission == 0:
        return redirect('dashboard')
    if max_permission < 2:
        return redirect('inventory:stock_list')

    form = TransferForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        try:
            movement_out, movement_in = services.register_transfer(
                material=data['material'], origin=data['origin'], destination=data['destination'],
                quantity=data['quantity'], notes=data['notes'], user=request.user,
            )
        except ValueError as e:
            form.add_error(None, str(e))
        else:
            messages.success(
                request,
                f"Transfer registered ({movement_out.id_inventory_movement} / {movement_in.id_inventory_movement})."
            )
            return redirect('inventory:movements_list')

    context = {'form': form, 'title': 'Transfer Between Locations', 'submit_label': 'Register Transfer', 'active_tab': 'transfer', 'can_edit': True}
    return render(request, 'inventory/movement_form.html', context)


def sync_daily_stock_background():
    """Mismo nombre que en el curso. La lógica está en inventory/services.py."""
    return services.sync_daily_stock()

