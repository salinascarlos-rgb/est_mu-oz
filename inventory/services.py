"""
Lógica de negocio del inventario.

Regla principal: las cantidades de los movimientos se guardan siempre
positivas y el signo lo da el tipo de movimiento (MovementType.direction):
    existencia = suma(cantidad * dirección)
"""
from django.db import transaction
from django.db.models import Sum, F, Max, IntegerField, Q
from django.db.models.functions import Cast, Substr

from core.models import Currency
from .models import InventoryMovements, MovementType

MOVEMENT_ID_PREFIX = 'MV'
MOVEMENT_ID_WIDTH = 8          # MV00000001 -> 10 caracteres (max_length del campo)

ADJUSTMENT_IN = 'ADJ_IN'
ADJUSTMENT_OUT = 'ADJ_OUT'
TRANSFER_IN = 'TRF_IN'
TRANSFER_OUT = 'TRF_OUT'


class InsufficientStock(ValueError):
    pass


def signed_quantity():
    """Expresión ORM: cantidad con signo según el tipo de movimiento."""
    return F('quantity') * F('movement_type__direction')


def stock_by_location(movements=None):
    """
    Existencias agrupadas por bodega y material.
    Devuelve un queryset de diccionarios con id_location, id_material y stock.
    """
    movements = movements if movements is not None else InventoryMovements.objects.all()
    return (
        movements
        .values(
            'id_location', 'id_location__code', 'id_location__name',
            'id_material', 'id_material__id_material', 'id_material__name',
            'id_material__unit__symbol',
        )
        .annotate(stock=Sum(signed_quantity()))
        .order_by('id_location__code', 'id_material__id_material')
    )


def get_stock(material, location):
    """Existencia de un material en una bodega."""
    result = InventoryMovements.objects.filter(
        id_material=material, id_location=location
    ).aggregate(stock=Sum(signed_quantity()))
    return result['stock'] or 0


def average_costs(material_ids=None):
    """
    Costo promedio ponderado por material, calculado con los movimientos
    de entrada que tienen precio (compras y ajustes de entrada).
    Devuelve {material_pk: costo}.
    """
    qs = InventoryMovements.objects.filter(movement_type__direction=MovementType.DIRECTION_IN, price__gt=0)
    if material_ids is not None:
        qs = qs.filter(id_material__in=material_ids)
    rows = qs.values('id_material').annotate(
        total_value=Sum(F('price') * F('quantity')),
        total_qty=Sum('quantity'),
    )
    return {
        row['id_material']: (row['total_value'] / row['total_qty']) if row['total_qty'] else 0
        for row in rows
    }


def next_movement_id(offset=0):
    """Siguiente ID de movimiento manual: MV00000001, MV00000002, ..."""
    last = (
        InventoryMovements.objects
        .filter(id_inventory_movement__regex=rf'^{MOVEMENT_ID_PREFIX}[0-9]+$')
        .aggregate(last=Max(Cast(Substr('id_inventory_movement', len(MOVEMENT_ID_PREFIX) + 1), IntegerField())))
    )['last'] or 0
    return f"{MOVEMENT_ID_PREFIX}{str(last + 1 + offset).zfill(MOVEMENT_ID_WIDTH)}"


def _movement_type(symbol):
    try:
        return MovementType.objects.get(symbol=symbol)
    except MovementType.DoesNotExist:
        raise ValueError(f"Movement type '{symbol}' not found. Run 'python manage.py seed_data'.")


def _default_currency():
    currency = Currency.objects.order_by('pk').first()
    if currency is None:
        raise ValueError("No currency configured. Run 'python manage.py seed_data'.")
    return currency


def _check_stock(material, location, quantity):
    available = get_stock(material, location)
    if quantity > available:
        raise InsufficientStock(
            f"Not enough stock of {material.id_material} in {location.code}. "
            f"Available: {available}, requested: {quantity}."
        )


@transaction.atomic
def register_adjustment(*, material, location, quantity, direction, reason, user):
    """Ajuste manual de inventario (conteo físico, daño, pérdida, etc.)."""
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    if direction == MovementType.DIRECTION_OUT:
        _check_stock(material, location, quantity)
        movement_type = _movement_type(ADJUSTMENT_OUT)
    else:
        movement_type = _movement_type(ADJUSTMENT_IN)

    cost = average_costs([material.pk]).get(material.pk, 0)

    return InventoryMovements.objects.create(
        id_inventory_movement=next_movement_id(),
        id_location=location,
        id_material=material,
        quantity=quantity,
        unit_type=material.unit,
        price=cost,
        currency=_default_currency(),
        movement_type=movement_type,
        reference=reason[:100],
        created_by=user,
    )


@transaction.atomic
def register_transfer(*, material, origin, destination, quantity, notes, user):
    """Traslado entre bodegas: una salida en el origen y una entrada en el destino."""
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    if origin == destination:
        raise ValueError("Origin and destination must be different.")

    _check_stock(material, origin, quantity)

    cost = average_costs([material.pk]).get(material.pk, 0)
    currency = _default_currency()
    out_id = next_movement_id()
    in_id = next_movement_id(offset=1)
    reference = f"TRF {origin.code} -> {destination.code}"
    if notes:
        reference = f"{reference} | {notes}"
    reference = reference[:100]

    common = dict(
        id_material=material, quantity=quantity, unit_type=material.unit,
        price=cost, currency=currency, reference=reference, created_by=user,
    )
    movement_out = InventoryMovements.objects.create(
        id_inventory_movement=out_id, id_location=origin, movement_type=_movement_type(TRANSFER_OUT), **common
    )
    movement_in = InventoryMovements.objects.create(
        id_inventory_movement=in_id, id_location=destination, movement_type=_movement_type(TRANSFER_IN), **common
    )
    return movement_out, movement_in
