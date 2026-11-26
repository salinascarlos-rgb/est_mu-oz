"""
Lógica de ventas (video 18).

Una orden de venta CONFIRMED (o PARTIAL_SENT) reserva stock: no lo saca de
la bodega, pero ya no está disponible para otra venta.
    disponible = existencia física - reservado
"""
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum, Max, IntegerField
from django.db.models.functions import Cast, Substr

from core.exchange_rates import get_rate
from core.models import Currency
from inventory import services as inventory_services
from .models import SalesOrder, LinesSalesOrder, SalesOrderStatus

# Estados que comprometen (reservan) stock
OPEN_STATUSES = ['CONFIRMED', 'PARTIAL_SENT']
INITIAL_STATUS = 'CONFIRMED'
ORDER_ID_PREFIX = 'SO-'
ORDER_ID_WIDTH = 5          # SO-00001 -> 8 caracteres


def _open_lines():
    return LinesSalesOrder.objects.filter(id_sales_order__status__symbol__in=OPEN_STATUSES)


def reserved_quantity(material, location):
    """Cantidad pendiente de despacho en órdenes abiertas."""
    result = _open_lines().filter(id_material=material, id_location=location).aggregate(
        reserved=Sum(F('quantity') - F('shipped_quantity'))
    )['reserved'] or 0
    return max(result, 0)


def reserved_map():
    """{(material_pk, location_pk): reservado} para todas las órdenes abiertas."""
    rows = _open_lines().values('id_material', 'id_location').annotate(
        reserved=Sum(F('quantity') - F('shipped_quantity'))
    )
    return {(r['id_material'], r['id_location']): max(r['reserved'] or 0, 0) for r in rows}


def available_quantity(material, location):
    return inventory_services.get_stock(material, location) - reserved_quantity(material, location)


def default_currency():
    return Currency.objects.order_by('pk').first()


def currency_for_customer(customer):
    """La moneda del cliente es texto libre; si coincide con un símbolo se usa, si no la moneda local."""
    code = (customer.currency or '').strip().upper()
    return Currency.objects.filter(symbol__iexact=code).first() or default_currency()


def cost_in_currency(material, currency):
    """
    Costo promedio del material expresado en `currency`.
    El curso guarda el costo en USD y el precio en la moneda de la venta, y así
    el margen sale mal (compara pesos contra dólares). Aquí se convierten.
    """
    local = default_currency()
    cost = Decimal(str(inventory_services.average_costs([material.pk]).get(material.pk, 0)))
    if not cost or currency is None or local is None or currency.pk == local.pk:
        return float(cost)
    local_rate = get_rate(local)
    target_rate = get_rate(currency)
    if not local_rate or not target_rate:
        return float(cost)
    return float(cost / local_rate * target_rate)


def next_sales_order_id():
    last = (
        SalesOrder.objects
        .filter(id_sales_order__regex=rf'^{ORDER_ID_PREFIX}[0-9]+$')
        .aggregate(last=Max(Cast(Substr('id_sales_order', len(ORDER_ID_PREFIX) + 1), IntegerField())))
    )['last'] or 0
    return f"{ORDER_ID_PREFIX}{str(last + 1).zfill(ORDER_ID_WIDTH)}"


@transaction.atomic
def create_sales_order(*, customer, estimated_delivery_date, lines, user):
    """
    Crea una orden de venta y reserva el stock.
    `lines`: lista de dicts con material, location, quantity, price y currency (opcional).
    Valida el disponible sumando las líneas repetidas del mismo material y bodega
    (el curso validaba cada línea por separado y se podía vender de más).
    """
    if not lines:
        raise ValueError("The order must have at least one line.")

    try:
        status = SalesOrderStatus.objects.get(symbol=INITIAL_STATUS)
    except SalesOrderStatus.DoesNotExist:
        raise ValueError("Sales order statuses not found. Run 'python manage.py seed_data'.")

    requested = defaultdict(int)
    for i, line in enumerate(lines, start=1):
        if line['quantity'] <= 0:
            raise ValueError(f"Line {i}: quantity must be greater than zero.")
        if line['price'] <= 0:
            raise ValueError(f"Line {i}: price must be greater than zero.")
        requested[(line['material'], line['location'])] += line['quantity']

    for (material, location), quantity in requested.items():
        available = available_quantity(material, location)
        if quantity > available:
            raise ValueError(
                f"Not enough stock of {material.id_material} in {location.code}. "
                f"Available: {available}, requested: {quantity}."
            )

    order = SalesOrder.objects.create(
        id_sales_order=next_sales_order_id(),
        id_customer=customer,
        estimated_delivery_date=estimated_delivery_date,
        status=status,
        created_by=user,
    )

    order_currency = currency_for_customer(customer)
    number = int(order.id_sales_order[len(ORDER_ID_PREFIX):])
    for position, line in enumerate(lines, start=1):
        currency = line.get('currency') or order_currency
        LinesSalesOrder.objects.create(
            id_sales_order_line=f"{number}-{str(position).zfill(3)}",
            id_sales_order=order,
            id_material=line['material'],
            id_location=line['location'],
            quantity=line['quantity'],
            unit_material=line['material'].unit,
            price=line['price'],
            wac=round(cost_in_currency(line['material'], currency), 4),
            currency=currency,
            created_by=user,
        )
    return order
