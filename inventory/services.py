"""
Lógica de negocio del inventario.

Regla principal: las cantidades de los movimientos se guardan siempre
positivas y el signo lo da el tipo de movimiento (MovementType.direction):
    existencia = suma(cantidad * dirección)
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, F, Max, Min, IntegerField
from django.db.models.functions import Cast, Substr
from django.utils import timezone

from core.models import Currency
from core.exchange_rates import get_rate, base_currency_code
from .models import InventoryMovements, MovementType, Stock

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
        raise ValueError(f"No existe el tipo de movimiento '{symbol}'. Ejecute 'python manage.py seed_data'.")


def _default_currency():
    currency = Currency.objects.order_by('pk').first()
    if currency is None:
        raise ValueError("No hay moneda configurada. Ejecute 'python manage.py seed_data'.")
    return currency


def rate_for(currency, on_date=None):
    """Tasa para guardar en un movimiento. Si aún no hay tasas se guarda 1 y
    fill_missing_exchange_rates() la corrige cuando se descarguen."""
    return get_rate(currency, on_date) or Decimal('1')


def _check_stock(material, location, quantity):
    available = get_stock(material, location)
    if quantity > available:
        raise InsufficientStock(
            f"No hay suficiente existencia de {material.id_material} en {location.code}. "
            f"Disponible: {available}, solicitado: {quantity}."
        )


# Tipos de movimiento que se registran desde "New Movement" (video 17)
LOSS = 'LOSS'
INTERNAL_USE = 'INT_USE'
MANUAL_MOVEMENT_TYPES = [LOSS, INTERNAL_USE, ADJUSTMENT_IN, ADJUSTMENT_OUT]

# Asiento automático por tipo: (cuenta débito, texto). El crédito va a inventario.
ACCOUNTING_MAP = {
    INTERNAL_USE: ('6020', 'Uso interno'),
    LOSS: ('6590', 'Pérdida de inventario'),
}
INVENTORY_ACCOUNT_CODE = '1200'
COST_CENTER_REQUIRED = {INTERNAL_USE}


def post_inventory_journal(movement, user):
    """
    Asiento contable de una salida de inventario (video 17):
        Débito  6020 Uso interno  /  6590 Pérdida de inventario
        Crédito 1200 Inventario
    Se registra en la moneda del movimiento (COP), igual que las facturas de
    compra, para que la cuenta 1200 no mezcle monedas. El curso usa USD.
    """
    from accounting.models import AccountAccount, Journal

    debit_code, text = ACCOUNTING_MAP[movement.movement_type.symbol]
    value = round(float(movement.quantity) * float(movement.price), 2)
    if value <= 0:
        return []

    accounts = {a.code: a for a in AccountAccount.objects.filter(code__in=[debit_code, INVENTORY_ACCOUNT_CODE])}
    missing = {debit_code, INVENTORY_ACCOUNT_CODE} - set(accounts)
    if missing:
        raise ValueError(f"Contabilidad: faltan las cuentas {', '.join(sorted(missing))}. Ejecute 'python manage.py seed_data'.")

    number = int(movement.id_inventory_movement[len(MOVEMENT_ID_PREFIX):])
    group = f"IM{number}"
    detail = (movement.description or '')[:50]
    entries = [
        (debit_code, value, 0.0, f"{text}: {detail}" if detail else text, 'D'),
        (INVENTORY_ACCOUNT_CODE, 0.0, value, f"Salida de inventario - {movement.id_inventory_movement}", 'C'),
    ]
    return [
        Journal.objects.create(
            id_journal=f"{group}{suffix}",
            group_journal=group,
            reference=reference[:100],
            id_account=accounts[code],
            debit=debit, credit=credit,
            currency=movement.currency,
            cost_center=movement.cost_center,
            description=movement.description,
            created_by=user,
        )
        for code, debit, credit, reference, suffix in entries
    ]


@transaction.atomic
def register_movement(*, material, location, movement_type, quantity, user, cost_center=None, description=''):
    """
    Movimiento manual: pérdida, uso interno o ajuste de entrada/salida.
    Las salidas validan existencia; pérdida y uso interno generan asiento.
    """
    if isinstance(movement_type, str):
        movement_type = _movement_type(movement_type)
    if movement_type.symbol not in MANUAL_MOVEMENT_TYPES:
        raise ValueError(f"El tipo de movimiento {movement_type.symbol} no se puede registrar manualmente.")
    if quantity <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    if movement_type.symbol in COST_CENTER_REQUIRED and cost_center is None:
        raise ValueError("El centro de costo es obligatorio para uso interno.")

    if movement_type.direction == MovementType.DIRECTION_OUT:
        _check_stock(material, location, quantity)

    cost = average_costs([material.pk]).get(material.pk, 0)
    currency = _default_currency()

    movement = InventoryMovements.objects.create(
        id_inventory_movement=next_movement_id(),
        id_location=location,
        id_material=material,
        quantity=quantity,
        unit_type=material.unit,
        price=cost,
        currency=currency,
        exchange_rate=rate_for(currency),
        movement_type=movement_type,
        cost_center=cost_center,
        description=description,
        reference=(description or movement_type.name)[:100],
        created_by=user,
    )

    if movement_type.symbol in ACCOUNTING_MAP:
        post_inventory_journal(movement, user)

    return movement


def register_adjustment(*, material, location, quantity, direction, reason, user):
    """Ajuste de entrada o salida (se mantiene por compatibilidad)."""
    symbol = ADJUSTMENT_OUT if direction == MovementType.DIRECTION_OUT else ADJUSTMENT_IN
    return register_movement(material=material, location=location, movement_type=symbol,
                             quantity=quantity, description=reason, user=user)


@transaction.atomic
def register_transfer(*, material, origin, destination, quantity, notes, user):
    """Traslado entre bodegas: una salida en el origen y una entrada en el destino."""
    if quantity <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    if origin == destination:
        raise ValueError("La bodega de origen y la de destino deben ser distintas.")

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
        price=cost, currency=currency, exchange_rate=rate_for(currency),
        reference=reference, created_by=user,
    )
    movement_out = InventoryMovements.objects.create(
        id_inventory_movement=out_id, id_location=origin, movement_type=_movement_type(TRANSFER_OUT), **common
    )
    movement_in = InventoryMovements.objects.create(
        id_inventory_movement=in_id, id_location=destination, movement_type=_movement_type(TRANSFER_IN), **common
    )
    return movement_out, movement_in


# ---------------------------------------------------------------------------
# Tasas en movimientos y foto diaria de stock (video 16 del curso)
# ---------------------------------------------------------------------------

def fill_missing_exchange_rates():
    """
    Los movimientos en una moneda distinta a la base que quedaron con tasa 1
    (porque no había tasas descargadas) toman la tasa de su fecha.
    Devuelve cuántos movimientos se corrigieron.
    """
    base = base_currency_code()
    pending = (
        InventoryMovements.objects
        .filter(exchange_rate=Decimal('1'))
        .exclude(currency__symbol__iexact=base)
        .select_related('currency')
    )
    fixed = 0
    for movement in pending:
        rate = get_rate(movement.currency, timezone.localdate(movement.created_at))
        if rate and rate != Decimal('1'):
            movement.exchange_rate = rate
            movement.save(update_fields=['exchange_rate'])
            fixed += 1
    return fixed


def _price_in_base(movement):
    rate = Decimal(str(movement.exchange_rate or 1)) or Decimal('1')
    return Decimal(str(movement.price)) / rate


@transaction.atomic
def sync_daily_stock(today=None, full=False):
    """
    Llena la tabla Stock con una foto por día, bodega y material, valorizada
    en la moneda base con costo promedio ponderado.

    Diferencias con el video 16:
      - Las salidas (ventas, ajustes de salida, traslados) RESTAN cantidad,
        usando MovementType.direction. El costo promedio no cambia al salir.
      - Es incremental: solo recalcula desde la última foto guardada, en vez de
        rehacer todo desde el primer movimiento cada vez.
    Devuelve cuántas filas de Stock se escribieron.
    """
    today = today or timezone.localdate()

    first = InventoryMovements.objects.aggregate(first=Min('created_at'))['first']
    if first is None:
        return 0

    last_snapshot = None if full else Stock.objects.aggregate(last=Max('date'))['last']
    if last_snapshot:
        # Se rehace el último día guardado porque pudo tener movimientos después
        start = min(last_snapshot, today)
        previous_day = Stock.objects.filter(date__lt=start).aggregate(d=Max('date'))['d']
        balances = {
            (row.id_material_id, row.id_location_id): (row.quantity, row.avg_price_usd)
            for row in Stock.objects.filter(date=previous_day)
        } if previous_day else {}
    else:
        start = timezone.localdate(first)
        balances = {}

    Stock.objects.filter(date__gte=start).delete()

    # Movimientos agrupados por día local
    by_day = defaultdict(list)
    movements = (
        InventoryMovements.objects
        .filter(created_at__date__gte=start)
        .select_related('movement_type')
        .order_by('created_at')
    )
    for movement in movements:
        by_day[timezone.localdate(movement.created_at)].append(movement)

    from materials.models import Material
    units = dict(Material.objects.values_list('pk', 'unit_id'))
    # Reservas de ventas abiertas (video 18): solo aplican a la foto de hoy
    try:
        from sales.services import reserved_map
        reserved_today = reserved_map()
    except ImportError:
        reserved_today = {}

    rows = []
    day = start
    while day <= today:
        day_movements = defaultdict(list)
        for movement in by_day.get(day, []):
            day_movements[(movement.id_material_id, movement.id_location_id)].append(movement)

        for key in set(balances) | set(day_movements):
            qty, avg = balances.get(key, (0, Decimal('0')))
            avg = Decimal(str(avg))
            total_cost = Decimal(qty) * avg

            for movement in day_movements.get(key, []):
                if movement.movement_type.direction > 0:
                    total_cost += Decimal(movement.quantity) * _price_in_base(movement)
                    qty += movement.quantity
                else:
                    total_cost -= Decimal(movement.quantity) * avg
                    qty -= movement.quantity
                avg = (total_cost / Decimal(qty)) if qty > 0 else Decimal('0')
                if qty <= 0:
                    total_cost = Decimal('0')

            avg = avg.quantize(Decimal('0.000001'))
            balances[key] = (qty, avg)
            rows.append(Stock(
                date=day, id_material_id=key[0], id_location_id=key[1], quantity=qty, avg_price_usd=avg,
                unit_type_id=units.get(key[0]),
                reserved_quantity=reserved_today.get(key, 0) if day == today else 0,
                total_value_usd=(Decimal(qty) * avg).quantize(Decimal('0.0001')),
            ))
        day += timedelta(days=1)

    # bulk_create no llama a save(), por eso total_value_usd se calcula arriba
    Stock.objects.bulk_create(rows, batch_size=500)
    return len(rows)


def latest_stock_values():
    """{(material_pk, location_pk): total_value_usd} de la foto más reciente."""
    last = Stock.objects.aggregate(last=Max('date'))['last']
    if last is None:
        return {}, None
    values = {
        (row['id_material'], row['id_location']): row['total_value_usd']
        for row in Stock.objects.filter(date=last).values('id_material', 'id_location', 'total_value_usd')
    }
    return values, last
