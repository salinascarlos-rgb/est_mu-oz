import csv
import json
import logging
from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from core.models import Currency
from customers.models import Customer
from inventory.forms import active_locations, active_materials
from inventory.models import LocationInventory
from materials.models import Material
from users.models import UserRole
from .models import SalesOrder, SalesOrderStatus
from . import services

logger = logging.getLogger(__name__)


def get_sales_permission(user):
    """Nivel de permiso máximo del usuario en ventas (0, 1 o 2)."""
    return UserRole.objects.filter(user_id=user).aggregate(
        max_permission=Max('role__sales')
    )['max_permission'] or 0


def json_error(message, status=400):
    return JsonResponse({'success': False, 'error': message}, status=status)


@login_required
def sales_order_list(request):

    max_permission = get_sales_permission(request.user)
    if max_permission == 0:
        return redirect('dashboard')

    orders = SalesOrder.objects.select_related('id_customer', 'status', 'created_by').prefetch_related('lines')

    id_sales_order = request.GET.get('id_sales_order', '').strip()
    customer = request.GET.get('customer', '').strip()
    status_symbol = request.GET.get('status__symbol', '')

    if id_sales_order:
        orders = orders.filter(id_sales_order__icontains=id_sales_order)
    if customer:
        orders = orders.filter(id_customer__id_customer__icontains=customer) | orders.filter(id_customer__name__icontains=customer)
    if status_symbol:
        orders = orders.filter(status__symbol__iexact=status_symbol)

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="sales_orders.csv"'
        response.write('﻿'.encode('utf-8'))
        writer = csv.writer(response)
        writer.writerow(['ID SO', 'Customer ID', 'Customer', 'Issue Date', 'Est. Delivery', 'Status', 'Total', 'Created By'])
        for so in orders:
            writer.writerow([
                so.id_sales_order, so.id_customer.id_customer, so.id_customer.name,
                so.issue_date.strftime('%Y-%m-%d'), so.estimated_delivery_date.strftime('%Y-%m-%d'),
                so.status.symbol, round(so.total_amount, 2),
                so.created_by.username if so.created_by else 'N/A',
            ])
        return response

    page_obj = Paginator(orders, 10).get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'all_statuses_so': SalesOrderStatus.objects.all().order_by('symbol'),
        'can_edit': max_permission >= 2,
    }
    return render(request, 'sales/sales_order_list.html', context)


@login_required
def sales_order_detail(request, pk):

    if get_sales_permission(request.user) == 0:
        return redirect('dashboard')

    order = get_object_or_404(SalesOrder.objects.select_related('id_customer', 'status'), pk=pk)
    lines = order.lines.select_related('id_material', 'id_location', 'unit_material', 'currency').order_by('pk')
    return render(request, 'sales/sales_order_detail.html', {'order': order, 'lines': lines})


@login_required
def get_customer_details(request, customer_id):

    if get_sales_permission(request.user) == 0:
        return json_error('You do not have permission.', status=403)

    customer = get_object_or_404(Customer, id_customer=customer_id)
    currency = services.currency_for_customer(customer)
    return JsonResponse({
        'id_customer': customer.id_customer,
        'name': customer.name,
        'city': customer.city,
        'address': customer.address,
        'country': str(customer.country),
        'currency': currency.symbol if currency else '',
    })


@login_required
def get_stock_data(request):
    """Disponible, costo promedio y unidad de un material en una bodega."""

    if get_sales_permission(request.user) == 0:
        return json_error('You do not have permission.', status=403)

    material = Material.objects.filter(pk=request.GET.get('material_id')).select_related('unit').first()
    location = LocationInventory.objects.filter(pk=request.GET.get('location_id')).first()
    if material is None or location is None:
        return JsonResponse({'available': 0, 'physical': 0, 'reserved': 0, 'wac': 0.0, 'unit': 'N/A'})

    currency = Currency.objects.filter(symbol__iexact=request.GET.get('currency', '')).first() or services.default_currency()
    physical = services.inventory_services.get_stock(material, location)
    reserved = services.reserved_quantity(material, location)
    return JsonResponse({
        'physical': physical,
        'reserved': reserved,
        'available': physical - reserved,
        'wac': round(services.cost_in_currency(material, currency), 2),
        'unit': material.unit.symbol if material.unit else 'N/A',
    })


@login_required
def sales_order_form(request):
    """Crear orden de venta: GET muestra el formulario, POST recibe JSON."""

    max_permission = get_sales_permission(request.user)
    if max_permission == 0:
        return redirect('dashboard') if request.method == 'GET' else json_error('You do not have permission.', 403)
    if max_permission < 2:
        return redirect('sales:sales_order_list') if request.method == 'GET' else json_error('You do not have permission.', 403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('id_customer')
            est_delivery = data.get('estimated_delivery_date')
            lines_data = data.get('lines', [])

            if not customer_id or not est_delivery or not lines_data:
                return json_error('Missing required fields (customer, delivery date or lines).')

            customer = Customer.objects.filter(id_customer=customer_id).first()
            if customer is None:
                return json_error(f"Customer '{customer_id}' not found.")
            try:
                est_delivery_date = date.fromisoformat(est_delivery)
            except ValueError:
                return json_error('Invalid delivery date.')
            if est_delivery_date < date.today():
                return json_error('The delivery date cannot be in the past.')

            lines = []
            for i, line in enumerate(lines_data, start=1):
                material = Material.objects.filter(pk=line.get('material_id')).select_related('unit').first()
                location = LocationInventory.objects.filter(pk=line.get('location_id')).first()
                if material is None or location is None:
                    return json_error(f"Line {i}: select a material and a location.")
                try:
                    quantity = int(float(line.get('quantity')))
                    price = float(line.get('price'))
                except (TypeError, ValueError):
                    return json_error(f"Line {i}: invalid quantity or price.")
                lines.append({'material': material, 'location': location, 'quantity': quantity, 'price': price})

            order = services.create_sales_order(
                customer=customer, estimated_delivery_date=est_delivery_date, lines=lines, user=request.user,
            )
            return JsonResponse({
                'success': True,
                'id': order.id_sales_order,
                'message': f"Order {order.id_sales_order} created and stock reserved.",
                'redirect_url': reverse('sales:sales_order_detail', kwargs={'pk': order.pk}),
            }, status=201)

        except ValueError as e:
            return json_error(str(e))
        except Exception as e:
            logger.exception("Error in sales_order_create")
            return json_error(f'Unexpected error: {e}', status=500)

    context = {
        'materials': active_materials().select_related('unit'),
        'locations': active_locations(),
        'title': 'Create New Sales Order',
    }
    return render(request, 'sales/sales_order_form.html', context)
