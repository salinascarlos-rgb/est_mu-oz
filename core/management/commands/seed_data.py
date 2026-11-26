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
from accounting.models import AccountNature, AccountType, AccountGroup, AccountAccount
from users.models import Role


ORDER_STATUSES = [
    ('Draft', 'DRAFT'),
    ('Sent', 'SENT'),
    ('Confirmed', 'CONFIRMED'),
    ('Partial Received', 'PARTIAL_RECEIVED'),
    ('Received', 'RECEIVED'),
    ('Invoiced', 'INVOICED'),
    ('Closed', 'CLOSED'),
    ('Cancelled', 'CANCELLED'),
]

GOODS_RECEIPT_STATUSES = [
    ('Partially received', 'PARTIAL_RECEIVED'),
    ('Completed', 'COMPLETED'),
    ('Cancelled', 'CANCELLED'),
]

INVOICE_STATUSES = [
    ('Pending', 'PENDING'),
    ('Paid', 'PAID'),
    ('Cancelled', 'CANCELLED'),
]

# (name, symbol, direction): +1 suma al inventario, -1 resta
MOVEMENT_TYPES = [
    ('Purchase', 'PUR', 1),
    ('Purchase Return', 'PUR_RET', -1),
    ('Sale', 'SAL', -1),
    ('Sales Return', 'SAL_RET', 1),
    ('Adjustment In', 'ADJ_IN', 1),
    ('Adjustment Out', 'ADJ_OUT', -1),
    ('Transfer In', 'TRF_IN', 1),
    ('Transfer Out', 'TRF_OUT', -1),
]

ACCOUNT_TYPES = [
    ('1', 'Asset', 'Resources owned by the company'),
    ('2', 'Liability', 'Obligations and debts'),
    ('3', 'Equity', 'Owners capital and retained earnings'),
    ('4', 'Revenue', 'Income from operations'),
    ('5', 'Expense', 'Operational expenses'),
]

ACCOUNT_GROUPS = [
    ('1', 'Current Assets', '1', 'Cash, bank, inventory, accounts receivable'),
    ('2', 'Non-current Assets', '2', 'Property, equipment'),
    ('3', 'Current Liabilities', '3', 'Accounts payable, taxes payable'),
    ('4', 'Equity', '4', 'Capital, retained earnings'),
    ('5', 'Revenue', '5', 'Sales, services'),
    ('6', 'Expenses', '6', 'COGS, salaries, rent'),
]

# (id, code, name, type_id, group_id, nature_id)
ACCOUNTS = [
    ('1001', '1001', 'Bank', '1', '1', '1'),
    ('1200', '1200', 'Inventory / Purchases', '1', '1', '1'),
    ('2200', '2200', 'Accounts Payable', '2', '3', '2'),
    ('4100', '4100', 'Sales Revenue', '4', '5', '2'),
    ('6100', '6100', 'Cost of Goods Sold', '5', '6', '1'),
]


class Command(BaseCommand):
    help = 'Loads base catalog data (statuses, currencies, movement types, accounts, roles).'

    def _by_symbol(self, model, rows):
        created = 0
        for name, symbol in rows:
            _, was_created = model.objects.get_or_create(symbol=symbol, defaults={'name': name})
            created += was_created
        return created

    @transaction.atomic
    def handle(self, *args, **options):
        total = 0

        for name, active in [('Active', True), ('Inactive', False)]:
            total += Status.objects.get_or_create(name=name, defaults={'is_active': active})[1]

        cop, c = Currency.objects.get_or_create(symbol='COP', defaults={'name': 'Peso Colombiano'})
        total += c
        colombia, c = Country.objects.get_or_create(name='Colombia')
        total += c

        total += Unit.objects.get_or_create(symbol='UND', defaults={'name': 'Unidad'})[1]
        total += MaterialType.objects.get_or_create(symbol='MP', defaults={'name': 'Materia prima'})[1]

        total += self._by_symbol(OrderStatus, ORDER_STATUSES)
        total += self._by_symbol(GoodsReceiptStatus, GOODS_RECEIPT_STATUSES)
        total += self._by_symbol(InvoiceStatus, INVOICE_STATUSES)
        for name, symbol, direction in MOVEMENT_TYPES:
            movement_type, was_created = MovementType.objects.get_or_create(
                symbol=symbol, defaults={'name': name, 'direction': direction}
            )
            if not was_created and movement_type.direction != direction:
                movement_type.direction = direction
                movement_type.save(update_fields=['direction'])
            total += was_created

        for pk, name, symbol, effect in [
            ('1', 'Debit', 'DR', 'Increases assets and expenses'),
            ('2', 'Credit', 'CR', 'Increases liabilities, equity and revenue'),
        ]:
            total += AccountNature.objects.get_or_create(
                id_account_nature=pk, defaults={'name': name, 'symbol': symbol, 'effect_on_balance': effect}
            )[1]

        for pk, name, description in ACCOUNT_TYPES:
            total += AccountType.objects.get_or_create(
                id_account_type=pk, defaults={'name': name, 'description': description}
            )[1]

        for pk, name, prefix, description in ACCOUNT_GROUPS:
            total += AccountGroup.objects.get_or_create(
                id_account_group=pk, defaults={'name': name, 'code_prefix': prefix, 'description': description}
            )[1]

        active = Status.objects.get(name='Active')
        for pk, code, name, type_id, group_id, nature_id in ACCOUNTS:
            if AccountAccount.objects.filter(code=code).exists():
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

        total += Role.objects.get_or_create(
            role_name='Administrator',
            defaults={m: 2 for m in ['customers', 'suppliers', 'materials', 'purchases',
                                     'sales', 'inventory', 'accounting', 'reporting']},
        )[1]

        self.stdout.write(self.style.SUCCESS(f'Base data loaded. New records created: {total}.'))
