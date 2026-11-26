import json
import csv
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import transaction, models
from django.db.models import Max, IntegerField
from django.db.models.functions import Cast
from django.core.paginator import Paginator
from django.contrib import messages
from django.urls import reverse
from .models import PurchaseOrder, LinesPurchaseOrder, OrderStatus, GoodsReceipt, GoodsReceiptStatus, LinesGoodsReceipt, PurchaseInvoice, InvoiceStatus, LinesPurchaseInvoice
from suppliers.models import Supplier
from materials.models import Material, Unit
from core.models import Currency
from users.models import UserRole
from inventory.models import LocationInventory, MovementType, InventoryMovements
from inventory.services import rate_for
from accounting.models import AccountAccount, Journal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Estado con el que nace una orden de compra nueva
INITIAL_PO_STATUS = 'CONFIRMED'

# Cuentas contables usadas al contabilizar una factura de compra
PURCHASES_ACCOUNT_CODE = '1200'   # Inventario / Compras (débito)
BANK_ACCOUNT_CODE = '1001'        # Bancos (crédito)


def get_purchases_permission(user):
    """Nivel de permiso máximo del usuario en el módulo de compras (0, 1 o 2)."""
    return UserRole.objects.filter(user_id=user).aggregate(
        max_permission=Max('role__purchases')
    )['max_permission'] or 0


def next_sequence(model, field, width=0):
    """
    Siguiente número consecutivo para un campo de texto que guarda números.
    Se convierte a entero antes de calcular el máximo, porque como texto
    '9' > '10' y eso generaba IDs repetidos.
    """
    numeric_values = model.objects.filter(**{f'{field}__regex': r'^[0-9]+$'})
    last = numeric_values.aggregate(max_id=Max(Cast(field, IntegerField())))['max_id'] or 0
    return str(last + 1).zfill(width)


def get_by_symbol(model, symbol, label):
    """Busca un registro de catálogo por su símbolo con un mensaje de error claro."""
    try:
        return model.objects.get(symbol=symbol)
    except model.DoesNotExist:
        raise ValueError(f"{label} '{symbol}' not found. Run 'python manage.py seed_data' to load base data.")


def json_permission_denied():
    return JsonResponse({'error': 'You do not have permission to perform this action.'}, status=403)


# ---------------------------------------------------------------------------
# Purchase orders
# ---------------------------------------------------------------------------

@login_required
def purchase_order_list(request):

    max_permission = get_purchases_permission(request.user)

    if max_permission == 0:
        return redirect('dashboard')

    purchase_order_list = PurchaseOrder.objects.select_related('id_supplier', 'status', 'created_by').order_by('-pk')

    id_purchase_order = request.GET.get('id_purchase_order')
    supplier_id = request.GET.get('id_supplier__id_supplier')
    status_symbol = request.GET.get('status__symbol')

    if id_purchase_order:
        purchase_order_list = purchase_order_list.filter(id_purchase_order__icontains=id_purchase_order)
    if supplier_id:
        purchase_order_list = purchase_order_list.filter(id_supplier__id_supplier__icontains=supplier_id)
    if status_symbol:
        purchase_order_list = purchase_order_list.filter(status__symbol__iexact=status_symbol)

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="purchase_orders.csv"'

        response.write('﻿'.encode('utf-8'))
        writer = csv.writer(response)

        # Lista (no conjunto) para que las columnas salgan siempre en el mismo orden
        writer.writerow(['ID PO', 'Supplier ID', 'Supplier Name', 'Issue Date', 'Estimated Delivery Date', 'Status Symbol', 'Status Name', 'Created By', 'Created At'])

        for po in purchase_order_list:
            writer.writerow([
                po.id_purchase_order,
                po.id_supplier.id_supplier,
                po.id_supplier.name,
                po.issue_date.strftime('%Y-%m-%d'),
                po.estimated_delivery_date.strftime('%Y-%m-%d'),
                po.status.symbol,
                po.status.name,
                po.created_by.username if po.created_by else 'N/A',
                po.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            ])
        return response

    paginator = Paginator(purchase_order_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    all_statuses_po = OrderStatus.objects.all().order_by('symbol')

    context = {
        'page_obj': page_obj,
        'all_statuses_po': all_statuses_po,
        'permissions': {'purchase_orders': max_permission},
    }

    return render(request, 'purchases/purchase_order_list.html', context)


@login_required
def get_supplier_details(request, supplier_id):

    if get_purchases_permission(request.user) == 0:
        return json_permission_denied()

    supplier = get_object_or_404(Supplier, id_supplier=supplier_id)

    data = {
        'id_supplier': supplier.id_supplier,
        'name': supplier.name,
        'legal_name': supplier.legal_name,
        'tax_id': supplier.tax_id,
        'address': supplier.address,
        'city': supplier.city,
        'state_province': supplier.state_province,
        'country': supplier.country.name if supplier.country else '',
        'zip_code': supplier.zip_code,
        'phone': supplier.phone,
        'email': supplier.email,
        'contact_name': supplier.contact_name,
        'payment_terms': supplier.payment_terms,
        'currency': supplier.currency.symbol if supplier.currency else '',
    }

    return JsonResponse(data)


@login_required
def get_material_details(request, material_id):

    if get_purchases_permission(request.user) == 0:
        return json_permission_denied()

    material = get_object_or_404(Material, id_material=material_id)

    data = {
        'id_material': material.id_material,
        'unit': material.unit.symbol,
        'description': material.description,
    }

    return JsonResponse(data)


@login_required
def purchase_order_form(request):

    max_permission = get_purchases_permission(request.user)

    if max_permission == 0:
        return redirect('dashboard')
    if max_permission < 2:
        return redirect('purchases:purchase_order_list')

    context = {
        'is_detail': False,
        'title': 'Create New Purchase Order'
    }

    return render(request, 'purchases/purchase_order_form.html', context)


@login_required
def purchase_order_detail(request, pk):

    max_permission = get_purchases_permission(request.user)
    if max_permission == 0:
        return redirect('dashboard')

    purchase_order = get_object_or_404(PurchaseOrder, pk=pk)

    order_lines = LinesPurchaseOrder.objects.filter(id_purchase_order=purchase_order).order_by('position')

    context = {
        'purchase_order': purchase_order,
        'order_lines': order_lines,
        'is_detail': True,
        'is_details': True,
        'can_edit': max_permission >= 2,
        'goods_receipt_url_name': 'purchases:goods_receipt_create',
        'invoice_url_name': 'purchases:purchase_invoice_create',
    }

    return render(request, 'purchases/purchase_order_form.html', context)


@login_required
@require_POST
def create_purchase_order(request):

    if get_purchases_permission(request.user) < 2:
        return json_permission_denied()

    try:
        data = json.loads(request.body)

        supplier_id_str = data.get('id_supplier')
        estimated_delivery_date = data.get('estimated_delivery_date')
        lines_data = data.get('lines', [])

        if not supplier_id_str or not estimated_delivery_date or not lines_data:
            return JsonResponse({'error': 'Missing required fields (Supplier ID, Delivery Date, or Lines Items).'}, status=400)

        # Todo dentro de un atomic: si una línea falla, no queda una OC a medias
        with transaction.atomic():
            supplier = Supplier.objects.filter(id_supplier=supplier_id_str).first()
            if supplier is None:
                raise ValueError(f"Supplier ID '{supplier_id_str}' not found.")

            status = get_by_symbol(OrderStatus, INITIAL_PO_STATUS, 'Order status')

            next_po_id = next_sequence(PurchaseOrder, 'id_purchase_order')

            purchase_order = PurchaseOrder.objects.create(
                id_purchase_order=next_po_id,
                id_supplier=supplier,
                estimated_delivery_date=estimated_delivery_date,
                status=status,
                created_by=request.user,
            )

            for i, line_data in enumerate(lines_data, start=1):
                material_id = line_data.get('id_material')
                unit_symbol = line_data.get('unit_material')
                currency_symbol = line_data.get('currency_supplier')
                position = line_data.get('position', i)

                try:
                    quantity = int(float(line_data.get('quantity')))
                    price = float(line_data.get('price'))
                except (TypeError, ValueError):
                    raise ValueError(f"Invalid quantity or price in line {i}.")
                if quantity <= 0 or price <= 0:
                    raise ValueError(f"Quantity and price must be greater than zero in line {i}.")

                material = Material.objects.filter(id_material=material_id).first()
                if material is None:
                    raise ValueError(f"Material ID '{material_id}' not found for line {i}.")
                unit_obj = Unit.objects.filter(symbol=unit_symbol).first()
                if unit_obj is None:
                    raise ValueError(f"Unit symbol '{unit_symbol}' not found for line {i}.")
                currency_obj = Currency.objects.filter(symbol=currency_symbol).first()
                if currency_obj is None:
                    raise ValueError(f"Currency symbol '{currency_symbol}' not found for line {i}.")

                line_po_id = f"{next_po_id}-{str(position).zfill(3)}"

                LinesPurchaseOrder.objects.create(
                    id_purchase_order_line=line_po_id,
                    id_purchase_order=purchase_order,
                    id_material=material,
                    position=position,
                    quantity=quantity,
                    unit_material=unit_obj,
                    price=price,
                    currency_supplier=currency_obj,
                    received_quantity=0,
                    created_by=request.user
                )

        response_data = {
            'success': True,
            'id_purchase_order': next_po_id,
            'message': f"Purchase Order {next_po_id} created successfully.",
            'redirect_url': reverse('purchases:purchase_order_list'),
        }
        return JsonResponse(response_data, status=201)

    except ValueError as e:
        return JsonResponse({'error': f'Validation Error: {str(e)}'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format in request body.'}, status=400)
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return JsonResponse({'error': f'An unexpected server error occurred: {str(e)}'}, status=500)


# ---------------------------------------------------------------------------
# Goods receipt
# ---------------------------------------------------------------------------

@login_required
def goods_receipt_form(request, po_pk):

    max_permission = get_purchases_permission(request.user)

    if max_permission == 0:
        return redirect('dashboard')
    if max_permission < 2:
        return redirect('purchases:purchase_order_list')

    purchase_order = get_object_or_404(PurchaseOrder, pk=po_pk)

    if purchase_order.status.symbol in ['CLOSED', 'CANCELLED']:
        messages.warning(request, f"The purchase order {purchase_order.id_purchase_order} is {purchase_order.status.name.lower()}. It's not possible to receive goods.")
        return redirect('purchases:purchase_order_detail', pk=po_pk)

    order_lines = LinesPurchaseOrder.objects.filter(
        id_purchase_order=purchase_order
    ).exclude(
        quantity__lte=models.F('received_quantity')
    ).order_by('position')

    if not order_lines.exists():
        messages.info(request, "All lines of this purchase order were already received.")
        return redirect('purchases:purchase_order_detail', pk=po_pk)

    for line in order_lines:
        line.pending_quantity = line.quantity - line.received_quantity

    locations = LocationInventory.objects.filter(status__is_active=True).order_by('code')

    context = {
        'purchase_order': purchase_order,
        'order_lines': order_lines,
        'locations': locations,
    }

    return render(request, 'purchases/goods_receipt_form.html', context)


@login_required
@require_POST
def post_goods_receipt(request):

    if get_purchases_permission(request.user) < 2:
        return json_permission_denied()

    try:
        data = json.loads(request.body)

        po_pk = data.get('po_pk')
        receipt_date = data.get('receipt_date')
        lines_data = data.get('lines', [])

        if not lines_data:
            return JsonResponse({'error': 'Must receive at least 1 quantity.'}, status=400)
        if not receipt_date:
            return JsonResponse({'error': 'Receipt date is required.'}, status=400)

        # El atomic va DENTRO del try: así un error deshace todo lo creado.
        # Antes el try/except estaba dentro del @transaction.atomic, el error
        # se "tragaba" y quedaban recepciones huérfanas en la base de datos.
        with transaction.atomic():
            purchase_order = PurchaseOrder.objects.select_for_update().filter(pk=po_pk).first()
            if purchase_order is None:
                raise ValueError(f"Purchase order '{po_pk}' not found.")
            if purchase_order.status.symbol in ['CLOSED', 'CANCELLED']:
                raise ValueError(f"Purchase order {purchase_order.id_purchase_order} is {purchase_order.status.name.lower()}.")

            gr_status_completed = get_by_symbol(GoodsReceiptStatus, 'COMPLETED', 'Goods receipt status')
            movement_type_pur = get_by_symbol(MovementType, 'PUR', 'Movement type')
            status_received = get_by_symbol(OrderStatus, 'RECEIVED', 'Order status')
            status_partially_received = get_by_symbol(OrderStatus, 'PARTIAL_RECEIVED', 'Order status')
            status_invoiced = get_by_symbol(OrderStatus, 'INVOICED', 'Order status')
            status_closed = get_by_symbol(OrderStatus, 'CLOSED', 'Order status')

            next_gr_id = next_sequence(GoodsReceipt, 'id_goods_receipt', width=10)

            goods_receipt = GoodsReceipt.objects.create(
                id_goods_receipt=next_gr_id,
                id_purchase_order=purchase_order,
                receipt_date=receipt_date,
                status=gr_status_completed,
                created_by=request.user,
            )

            total_received_in_this_gr = 0

            for i, line_data in enumerate(lines_data, start=1):
                try:
                    received_qty = int(float(line_data['received_quantity']))
                except (KeyError, TypeError, ValueError):
                    raise ValueError(f"Invalid received quantity in line {i}.")

                if received_qty <= 0:
                    continue

                po_line = LinesPurchaseOrder.objects.filter(pk=line_data.get('line_pk'), id_purchase_order=purchase_order).first()
                if po_line is None:
                    raise ValueError(f"Line {i} does not belong to purchase order {purchase_order.id_purchase_order}.")
                location = LocationInventory.objects.filter(pk=line_data.get('location_pk')).first()
                if location is None:
                    raise ValueError(f"Storage location not found for line {po_line.position}.")

                available_to_receive = po_line.quantity - po_line.received_quantity
                if received_qty > available_to_receive:
                    raise ValueError(f"Over reception in line {po_line.position}. Order: {po_line.quantity}, Received before: {po_line.received_quantity}, trying to receive: {received_qty}")

                inventory_movement = InventoryMovements.objects.create(
                    id_inventory_movement=f"GR{int(next_gr_id)}-{i}",
                    id_location=location,
                    id_material=po_line.id_material,
                    quantity=received_qty,
                    unit_type=po_line.unit_material,
                    movement_type=movement_type_pur,
                    price=po_line.price,
                    currency=po_line.currency_supplier,
                    # Tasa de la fecha de la orden, como en el video 16
                    exchange_rate=rate_for(po_line.currency_supplier, purchase_order.issue_date),
                    reference=f"GR {next_gr_id} / PO {purchase_order.id_purchase_order}",
                    created_by=request.user,
                )

                line_gr_id = f"{int(next_gr_id)}-{str(i).zfill(3)}"
                LinesGoodsReceipt.objects.create(
                    id_goods_receipt_line=line_gr_id,
                    id_goods_receipt=goods_receipt,
                    id_purchase_order_line=po_line,
                    id_material=po_line.id_material,
                    received_quantity=received_qty,
                    unit_material=po_line.unit_material,
                    id_location=location,
                    inventory_movement_ref=inventory_movement.id_inventory_movement,
                    created_by=request.user,
                )

                po_line.received_quantity += received_qty
                po_line.save()

                total_received_in_this_gr += received_qty

            if total_received_in_this_gr == 0:
                raise ValueError('Must receive at least 1 quantity.')

            totals = purchase_order.linespurchaseorder_set.aggregate(
                ordered=models.Sum('quantity'), received=models.Sum('received_quantity')
            )
            total_ordered_qty = totals['ordered'] or 0
            total_final_received = totals['received'] or 0
            is_invoiced = purchase_order.status.symbol == status_invoiced.symbol

            if total_final_received >= total_ordered_qty:
                purchase_order.status = status_closed if is_invoiced else status_received
            elif not is_invoiced:
                purchase_order.status = status_partially_received

            purchase_order.save()

        response_data = {
            'success': True,
            'id_goods_receipt': next_gr_id,
            'redirect_url': reverse('purchases:purchase_order_detail', kwargs={'pk': purchase_order.pk}),
        }
        return JsonResponse(response_data, status=200)

    except ValueError as e:
        return JsonResponse({'error': f'Validation Error: {str(e)}'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format in request body.'}, status=400)
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return JsonResponse({'error': f'An unexpected server error occurred: {str(e)}'}, status=500)


# ---------------------------------------------------------------------------
# Purchase invoice
# ---------------------------------------------------------------------------

@login_required
def purchase_invoice_form(request, po_pk):

    max_permission = get_purchases_permission(request.user)

    if max_permission == 0:
        return redirect('dashboard')
    if max_permission < 2:
        return redirect('purchases:purchase_order_list')

    purchase_order = get_object_or_404(PurchaseOrder, pk=po_pk)

    if purchase_order.status.symbol in ['CLOSED', 'INVOICED', 'CANCELLED']:
        messages.warning(request, f"The purchase order {purchase_order.id_purchase_order} is already invoiced, closed or cancelled. It's not possible to create a new invoice")
        return redirect('purchases:purchase_order_detail', pk=po_pk)

    order_lines_qs = LinesPurchaseOrder.objects.filter(id_purchase_order=purchase_order).order_by('position')

    currency = purchase_order.id_supplier.currency

    for line in order_lines_qs:
        line.quantity_to_invoice = line.quantity
        line.line_total = line.quantity_to_invoice * line.price

    context = {
        'purchase_order': purchase_order,
        'order_lines': order_lines_qs,
        'currency': currency,
        'total_ordered_amount': sum(line.quantity * line.price for line in order_lines_qs)
    }

    return render(request, 'purchases/purchase_invoice_form.html', context)


@login_required
@require_POST
def post_purchase_invoice(request):

    if get_purchases_permission(request.user) < 2:
        return json_permission_denied()

    try:
        data = json.loads(request.body)

        po_pk = data.get('po_pk')
        due_date = data.get('due_date')
        lines_data = data.get('lines', [])

        if not lines_data or not due_date:
            return JsonResponse({'error': 'Missing lines or due date.'}, status=400)

        with transaction.atomic():
            purchase_order = PurchaseOrder.objects.select_for_update().filter(pk=po_pk).first()
            if purchase_order is None:
                raise ValueError(f"Purchase order '{po_pk}' not found.")

            # Es una API JSON: devolvemos error JSON, no un redirect
            if purchase_order.status.symbol in ['CLOSED', 'INVOICED', 'CANCELLED']:
                raise ValueError(f"The purchase order {purchase_order.id_purchase_order} is already invoiced, closed or cancelled.")

            invoice_currency = purchase_order.id_supplier.currency
            if invoice_currency is None:
                first_line = purchase_order.linespurchaseorder_set.first()
                invoice_currency = first_line.currency_supplier if first_line else None
            if invoice_currency is None:
                raise ValueError("The supplier has no currency configured.")

            invoice_status_paid = get_by_symbol(InvoiceStatus, 'PAID', 'Invoice status')
            status_received = get_by_symbol(OrderStatus, 'RECEIVED', 'Order status')
            status_closed = get_by_symbol(OrderStatus, 'CLOSED', 'Order status')
            status_invoiced = get_by_symbol(OrderStatus, 'INVOICED', 'Order status')

            purchases_account = AccountAccount.objects.filter(code=PURCHASES_ACCOUNT_CODE).first()
            bank_account = AccountAccount.objects.filter(code=BANK_ACCOUNT_CODE).first()
            if purchases_account is None or bank_account is None:
                raise ValueError(f"Accounting: accounts {PURCHASES_ACCOUNT_CODE} and {BANK_ACCOUNT_CODE} are required. Run 'python manage.py seed_data'.")

            next_invoice_id = next_sequence(PurchaseInvoice, 'id_invoice', width=10)

            total_amount = 0
            invoiced_lines = []
            for i, line_data in enumerate(lines_data, start=1):
                po_line = LinesPurchaseOrder.objects.filter(pk=line_data.get('line_pk'), id_purchase_order=purchase_order).first()
                if po_line is None:
                    raise ValueError(f"Line {i} does not belong to purchase order {purchase_order.id_purchase_order}.")
                try:
                    qty_to_invoice = int(float(line_data['quantity_to_invoice']))
                except (KeyError, TypeError, ValueError):
                    raise ValueError(f"Invalid quantity to invoice in line {po_line.position}.")

                if qty_to_invoice <= 0:
                    continue
                if qty_to_invoice > po_line.quantity:
                    raise ValueError(f"Line {po_line.position}: cannot invoice more than the ordered quantity ({po_line.quantity}).")

                line_total = qty_to_invoice * po_line.price
                total_amount += line_total

                line_invoice_id = f"{int(next_invoice_id)}-{str(i).zfill(3)}"
                invoiced_lines.append(LinesPurchaseInvoice(
                    id_invoice_line=line_invoice_id,
                    id_purchase_order_line=po_line,
                    price=po_line.price,
                    quantity=qty_to_invoice,
                    currency_invoice_line=invoice_currency,
                    created_by=request.user
                ))

            if total_amount == 0:
                raise ValueError('Total amount is zero. Check quantities.')

            purchase_invoice = PurchaseInvoice.objects.create(
                id_invoice=next_invoice_id,
                id_purchase_order=purchase_order,
                due_date=due_date,
                total_amount=total_amount,
                currency_invoice=invoice_currency,
                status=invoice_status_paid,
                created_by=request.user,
            )

            for line in invoiced_lines:
                line.id_purchase_invoice = purchase_invoice
                line.save()

            # Asiento contable: débito a compras/inventario, crédito a bancos
            group_id = purchase_invoice.id_invoice
            short_id = int(group_id)

            Journal.objects.create(
                id_journal=f"INV{short_id}D",
                group_journal=str(short_id),
                reference=f"INV-{group_id} - Inventory/Purchases (Paid)",
                id_account=purchases_account,
                credit=0.0,
                debit=total_amount,
                currency=invoice_currency,
                created_by=request.user,
            )

            Journal.objects.create(
                id_journal=f"INV{short_id}C",
                group_journal=str(short_id),
                reference=f"INV-{group_id} - Payment from bank",
                id_account=bank_account,
                credit=total_amount,
                debit=0.0,
                currency=invoice_currency,
                created_by=request.user,
            )

            if purchase_order.status.symbol == status_received.symbol:
                purchase_order.status = status_closed
            else:
                purchase_order.status = status_invoiced

            purchase_order.save()

        response_data = {
            'success': True,
            'id_invoice': next_invoice_id,
            'redirect_url': reverse('purchases:purchase_order_detail', kwargs={'pk': purchase_order.pk}),
        }
        return JsonResponse(response_data, status=200)

    except ValueError as e:
        return JsonResponse({'error': f'Validation Error: {str(e)}'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format in request body.'}, status=400)
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return JsonResponse({'error': f'An unexpected server error occurred: {str(e)}'}, status=500)
