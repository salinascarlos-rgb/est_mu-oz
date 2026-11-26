"""
Carga los datos base (catálogos) que la aplicación necesita para funcionar.

Uso:
    python manage.py seed_data

Se puede ejecutar varias veces: solo crea lo que falta, no duplica ni borra.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Status, Currency, Country
from materials.models import Unit, MaterialType
from inventory.models import MovementType
from purchases.models import OrderStatus, GoodsReceiptStatus, InvoiceStatus
from accounting.models import AccountNature, AccountType, AccountGroup, AccountAccount, CostCenter
from users.models import Role
from sales.models import SalesOrderStatus


ORDER_STATUSES = [
    ('Borrador', 'DRAFT'),
    ('Enviada', 'SENT'),
    ('Confirmada', 'CONFIRMED'),
    ('Recibida parcialmente', 'PARTIAL_RECEIVED'),
    ('Recibida', 'RECEIVED'),
    ('Facturada', 'INVOICED'),
    ('Cerrada', 'CLOSED'),
    ('Cancelada', 'CANCELLED'),
]

GOODS_RECEIPT_STATUSES = [
    ('Recibida parcialmente', 'PARTIAL_RECEIVED'),
    ('Completada', 'COMPLETED'),
    ('Cancelada', 'CANCELLED'),
]

SALES_ORDER_STATUSES = [
    ('Borrador', 'DRAFT'),
    ('Confirmada', 'CONFIRMED'),
    ('Despachada parcialmente', 'PARTIAL_SENT'),
    ('Despachada', 'SENT'),
    ('Facturada', 'INVOICED'),
    ('Cerrada', 'CLOSED'),
    ('Cancelada', 'CANCELLED'),
]

INVOICE_STATUSES = [
    ('Pendiente', 'PENDING'),
    ('Pagada', 'PAID'),
    ('Anulada', 'CANCELLED'),
]

# (nombre, símbolo, dirección): +1 suma al inventario, -1 resta
MOVEMENT_TYPES = [
    ('Compra', 'PUR', 1),
    ('Devolución a proveedor', 'PUR_RET', -1),
    ('Venta', 'SAL', -1),
    ('Devolución de cliente', 'SAL_RET', 1),
    ('Ajuste de entrada', 'ADJ_IN', 1),
    ('Ajuste de salida', 'ADJ_OUT', -1),
    ('Traslado (entrada)', 'TRF_IN', 1),
    ('Traslado (salida)', 'TRF_OUT', -1),
    ('Daño / pérdida', 'LOSS', -1),
    ('Uso interno', 'INT_USE', -1),
]

ACCOUNT_TYPES = [
    ('1', 'Activo', 'Recursos de la empresa'),
    ('2', 'Pasivo', 'Obligaciones y deudas'),
    ('3', 'Patrimonio', 'Capital y utilidades retenidas'),
    ('4', 'Ingreso', 'Ingresos de la operación'),
    ('5', 'Gasto', 'Gastos de la operación'),
]

ACCOUNT_GROUPS = [
    ('1', 'Activo corriente', '1', 'Caja, bancos, inventario, cuentas por cobrar'),
    ('2', 'Activo no corriente', '2', 'Propiedad, planta y equipo'),
    ('3', 'Pasivo corriente', '3', 'Cuentas por pagar, impuestos por pagar'),
    ('4', 'Patrimonio', '4', 'Capital, utilidades retenidas'),
    ('5', 'Ingresos', '5', 'Ventas, servicios'),
    ('6', 'Gastos', '6', 'Costo de ventas, nómina, arriendo'),
]

# (id, código, nombre, tipo, grupo, naturaleza)
ACCOUNTS = [
    ('1001', '1001', 'Bancos', '1', '1', '1'),
    ('1200', '1200', 'Inventario / Compras', '1', '1', '1'),
    ('2200', '2200', 'Cuentas por pagar', '2', '3', '2'),
    ('4100', '4100', 'Ingresos por ventas', '4', '5', '2'),
    ('6100', '6100', 'Costo de ventas', '5', '6', '1'),
    ('6020', '6020', 'Uso interno', '5', '6', '1'),
    ('6590', '6590', 'Pérdida de inventario', '5', '6', '1'),
]

# Unidades y tipos de material (se buscan por símbolo)
UNITS = [
    ('Unidad', 'UN'), ('Kilogramo', 'KG'), ('Gramo', 'G'), ('Miligramo', 'MG'), ('Litro', 'LT'),
    ('Mililitro', 'ML'), ('Metro cúbico', 'M3'), ('Centímetro cúbico', 'CM3'), ('Metro cuadrado', 'M2'),
    ('Centímetro cuadrado', 'CM2'), ('Bulto', 'BTO'),
]

MATERIAL_TYPES = [
    ('Materia prima', 'RM'), ('Mercancía para la venta', 'TG'), ('Producto terminado', 'FG'),
    ('Producto en proceso', 'SG'), ('Insumos de operación', 'OS'), ('Repuestos', 'SP'),
    ('Partes no valorizadas', 'NP'), ('Servicios', 'SR'),
]

# Centros de costo de ejemplo (se pueden editar en el admin)
COST_CENTERS = [
    ('ADM', 'Administración', 'Gastos administrativos y de oficina'),
    ('VEN', 'Ventas', 'Punto de venta y atención a clientes'),
    ('BOD', 'Bodega', 'Almacenamiento y despacho'),
]


class Command(BaseCommand):
    help = 'Carga los datos base (estados, monedas, tipos de movimiento, cuentas, roles).'

    def _by_symbol(self, model, rows):
        """Crea lo que falta y deja el nombre en español en lo que ya existe."""
        created = 0
        for name, symbol in rows:
            obj = model.objects.filter(symbol=symbol).first()
            # Si otro registro ya usa ese nombre (p. ej. 'Unidad' con símbolo UND),
            # se agrega el símbolo para no chocar con la restricción de nombre único
            if model.objects.filter(name=name).exclude(symbol=symbol).exists():
                name = f"{name} ({symbol})"
            if obj is None:
                model.objects.create(symbol=symbol, name=name)
                created += 1
            elif obj.name != name:
                obj.name = name
                obj.save(update_fields=['name'])
        return created

    @transaction.atomic
    def handle(self, *args, **options):
        total = 0

        # Los estados se buscan por is_active para no duplicar si ya existen en inglés
        for name, active in [('Activo', True), ('Inactivo', False)]:
            status = Status.objects.filter(is_active=active).order_by('pk').first()
            if status is None:
                Status.objects.create(name=name, is_active=active)
                total += 1
            elif status.name != name:
                status.name = name
                status.save(update_fields=['name'])

        cop, c = Currency.objects.get_or_create(symbol='COP', defaults={'name': 'Peso Colombiano'})
        total += c
        # Moneda base para valorizar el inventario (settings.BASE_CURRENCY)
        total += Currency.objects.get_or_create(symbol='USD', defaults={'name': 'Dólar estadounidense'})[1]
        colombia, c = Country.objects.get_or_create(name='Colombia')
        total += c

        total += self._by_symbol(Unit, UNITS)
        total += self._by_symbol(MaterialType, MATERIAL_TYPES)

        total += self._by_symbol(OrderStatus, ORDER_STATUSES)
        total += self._by_symbol(GoodsReceiptStatus, GOODS_RECEIPT_STATUSES)
        total += self._by_symbol(InvoiceStatus, INVOICE_STATUSES)
        total += self._by_symbol(SalesOrderStatus, SALES_ORDER_STATUSES)
        for name, symbol, direction in MOVEMENT_TYPES:
            movement_type, was_created = MovementType.objects.get_or_create(
                symbol=symbol, defaults={'name': name, 'direction': direction}
            )
            if not was_created and (movement_type.direction != direction or movement_type.name != name):
                movement_type.direction = direction
                movement_type.name = name
                movement_type.save(update_fields=['direction', 'name'])
            total += was_created

        for pk, name, symbol, effect in [
            ('1', 'Débito', 'DR', 'Aumenta activos y gastos'),
            ('2', 'Crédito', 'CR', 'Aumenta pasivos, patrimonio e ingresos'),
        ]:
            total += AccountNature.objects.update_or_create(
                id_account_nature=pk, defaults={'name': name, 'symbol': symbol, 'effect_on_balance': effect}
            )[1]

        for pk, name, description in ACCOUNT_TYPES:
            total += AccountType.objects.update_or_create(
                id_account_type=pk, defaults={'name': name, 'description': description}
            )[1]

        for pk, name, prefix, description in ACCOUNT_GROUPS:
            total += AccountGroup.objects.update_or_create(
                id_account_group=pk, defaults={'name': name, 'code_prefix': prefix, 'description': description}
            )[1]

        active = Status.objects.filter(is_active=True).order_by('pk').first()
        for pk, code, name, type_id, group_id, nature_id in ACCOUNTS:
            existing = AccountAccount.objects.filter(code=code).first()
            if existing:
                if existing.name != name:
                    existing.name = name
                    existing.save(update_fields=['name'])
                continue
            AccountAccount.objects.create(
                id_account=pk,
                code=code,
                name=name,
                account_type_id=type_id,
                account_group_id=group_id,
                nature_id=nature_id,
                currency_id=cop,
                country_id=colombia,
                status=active,
            )
            total += 1

        for pk, name, description in COST_CENTERS:
            total += CostCenter.objects.get_or_create(
                id_cost_center=pk, defaults={'name': name, 'description': description, 'status': active}
            )[1]

        # role_name es la llave primaria: no se renombra 'Administrator' si ya
        # existe (rompería los usuarios asignados); solo se crea en bases nuevas
        if not Role.objects.filter(role_name='Administrator').exists():
            total += Role.objects.get_or_create(
                role_name='Administrador',
                defaults={m: 2 for m in ['customers', 'suppliers', 'materials', 'purchases',
                                         'sales', 'inventory', 'accounting', 'reporting']},
            )[1]

        self.stdout.write(self.style.SUCCESS(f'Datos base cargados. Registros nuevos: {total}.'))
