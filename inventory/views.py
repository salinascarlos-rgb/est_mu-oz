import csv
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect

from core.models import Currency
from users.models import UserRole
from .forms import AdjustmentForm, TransferForm, active_locations
from .models import InventoryMovements, MovementType
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

    rows = services.stock_by_location(movements)
    if not show_zero:
        rows = rows.exclude(stock=0)

    rows = list(rows)
    costs = services.average_costs({row['id_material'] for row in rows})
    total_value = 0
    for row in rows:
        row['avg_cost'] = costs.get(row['id_material'], 0)
        row['value'] = row['stock'] * row['avg_cost']
        total_value += row['value']

    currency = Currency.objects.order_by('pk').first()
    currency_symbol = currency.symbol if currency else ''

    if request.GET.get('export') == 'csv':
        response, writer = csv_response('inventory_stock.csv')
        writer.writerow(['Location Code', 'Location', 'Material ID', 'Material', 'Unit', 'Stock', 'Average Cost', 'Value', 'Currency'])
        for row in rows:
            writer.writerow([
                row['id_location__code'], row['id_location__name'],
                row['id_material__id_material'], row['id_material__name'], row['id_material__unit__symbol'],
                row['stock'], round(row['avg_cost'], 2), round(row['value'], 2), currency_symbol,
            ])
        return response

    page_obj = Paginator(rows, 20).get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'locations': active_locations(),
        'total_value': total_value,
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
def adjustment_create(request):

    max_permission = get_inventory_permission(request.user)
    if max_permission == 0:
        return redirect('dashboard')
    if max_permission < 2:
        return redirect('inventory:stock_list')

    form = AdjustmentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        try:
            movement = services.register_adjustment(
                material=data['material'], location=data['location'], quantity=data['quantity'],
                direction=data['direction'], reason=data['reason'], user=request.user,
            )
        except ValueError as e:
            form.add_error(None, str(e))
        else:
            messages.success(request, f"Adjustment {movement.id_inventory_movement} registered.")
            return redirect('inventory:movements_list')

    context = {'form': form, 'title': 'Inventory Adjustment', 'submit_label': 'Register Adjustment', 'active_tab': 'adjustment', 'can_edit': True}
    return render(request, 'inventory/movement_form.html', context)


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
