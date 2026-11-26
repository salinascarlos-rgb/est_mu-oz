from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.models import Currency
from materials.models import Material, Unit
from users.models import User, Role, UserRole
from .models import InventoryMovements, LocationInventory, MovementType
from . import services


class InventoryTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command('seed_data', verbosity=0)

        cls.user = User.objects.create_user(username='admin', password='pass12345')
        UserRole.objects.create(user_id=cls.user, role=Role.objects.get(role_name='Administrator'))

        cls.viewer = User.objects.create_user(username='viewer', password='pass12345')
        UserRole.objects.create(user_id=cls.viewer, role=Role.objects.create(role_name='Viewer', inventory=1))

        cls.nobody = User.objects.create_user(username='nobody', password='pass12345')

        cls.material = Material.objects.create(id_material='M001', name='Estuco', unit=Unit.objects.get(symbol='UND'))
        cls.bodega = LocationInventory.objects.create(id_location='L1', name='Bodega', code='B1')
        cls.local = LocationInventory.objects.create(id_location='L2', name='Local', code='B2')

        # Compra previa: 10 unidades a 2.000 en la bodega
        InventoryMovements.objects.create(
            id_inventory_movement='GR1-1', id_location=cls.bodega, id_material=cls.material,
            quantity=10, unit_type=cls.material.unit, price=2000,
            currency=Currency.objects.get(symbol='COP'),
            movement_type=MovementType.objects.get(symbol='PUR'), created_by=cls.user,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_stock_from_purchase(self):
        self.assertEqual(services.get_stock(self.material, self.bodega), 10)
        self.assertEqual(services.average_costs()[self.material.pk], 2000)

    def test_adjustment_out_reduces_stock(self):
        r = self.client.post(reverse('inventory:adjustment_create'), {
            'material': self.material.pk, 'location': self.bodega.pk,
            'direction': MovementType.DIRECTION_OUT, 'quantity': 3, 'reason': 'Bultos dañados',
        })
        self.assertRedirects(r, reverse('inventory:movements_list'))
        self.assertEqual(services.get_stock(self.material, self.bodega), 7)
        movement = InventoryMovements.objects.get(movement_type__symbol='ADJ_OUT')
        self.assertEqual(movement.id_inventory_movement, 'MV00000001')
        self.assertEqual(movement.reference, 'Bultos dañados')

    def test_cannot_remove_more_than_available(self):
        r = self.client.post(reverse('inventory:adjustment_create'), {
            'material': self.material.pk, 'location': self.bodega.pk,
            'direction': MovementType.DIRECTION_OUT, 'quantity': 50, 'reason': 'Error',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Not enough stock')
        self.assertEqual(services.get_stock(self.material, self.bodega), 10)

    def test_transfer_moves_stock_between_locations(self):
        r = self.client.post(reverse('inventory:transfer_create'), {
            'material': self.material.pk, 'origin': self.bodega.pk,
            'destination': self.local.pk, 'quantity': 4, 'notes': 'Para vitrina',
        })
        self.assertRedirects(r, reverse('inventory:movements_list'))
        self.assertEqual(services.get_stock(self.material, self.bodega), 6)
        self.assertEqual(services.get_stock(self.material, self.local), 4)
        ids = sorted(InventoryMovements.objects.filter(movement_type__symbol__startswith='TRF')
                     .values_list('id_inventory_movement', flat=True))
        self.assertEqual(ids, ['MV00000001', 'MV00000002'])

    def test_transfer_to_same_location_fails(self):
        r = self.client.post(reverse('inventory:transfer_create'), {
            'material': self.material.pk, 'origin': self.bodega.pk,
            'destination': self.bodega.pk, 'quantity': 1,
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(InventoryMovements.objects.count(), 1)

    def test_pages_and_csv(self):
        for name in ['inventory:stock_list', 'inventory:movements_list',
                     'inventory:adjustment_create', 'inventory:transfer_create']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        r = self.client.get(reverse('inventory:stock_list'), {'export': 'csv'})
        lines = r.content.decode('utf-8-sig').splitlines()
        self.assertTrue(lines[0].startswith('Location Code'))
        self.assertIn('M001', lines[1])
        self.assertIn('20000', lines[1])   # 10 x 2.000

    def test_view_only_user(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse('inventory:stock_list')).status_code, 200)
        self.assertRedirects(self.client.get(reverse('inventory:adjustment_create')), reverse('inventory:stock_list'))

    def test_user_without_permission(self):
        self.client.force_login(self.nobody)
        self.assertRedirects(self.client.get(reverse('inventory:stock_list')), reverse('dashboard'))


from datetime import date, datetime, timedelta
from decimal import Decimal
from django.test import override_settings
from django.utils import timezone
from core.models import ExchangeRate
from .models import Stock


@override_settings(BASE_CURRENCY='USD')
class StockSnapshotTests(TestCase):
    """Foto diaria de stock valorizada en USD (video 16), restando salidas."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_data', verbosity=0)
        cls.user = User.objects.create_user(username='admin', password='pass12345')
        cls.cop = Currency.objects.get(symbol='COP')
        cls.material = Material.objects.create(id_material='M001', name='Estuco', unit=Unit.objects.get(symbol='UND'))
        cls.bodega = LocationInventory.objects.create(id_location='L1', name='Bodega', code='B1')
        cls.local = LocationInventory.objects.create(id_location='L2', name='Local', code='B2')

    def movement(self, mid, symbol, qty, days_ago, price=0, rate=Decimal('4000'), location=None):
        mv = InventoryMovements.objects.create(
            id_inventory_movement=mid, id_location=location or self.bodega, id_material=self.material,
            quantity=qty, unit_type=self.material.unit, price=price, currency=self.cop, exchange_rate=rate,
            movement_type=MovementType.objects.get(symbol=symbol), created_by=self.user,
        )
        # created_at es auto_now_add: se ajusta a mano para simular días anteriores
        moment = timezone.now() - timedelta(days=days_ago)
        InventoryMovements.objects.filter(pk=mv.pk).update(created_at=moment)
        return mv

    def test_purchase_then_sale_is_subtracted(self):
        today = timezone.localdate()
        self.movement('A1', 'PUR', 10, days_ago=2, price=40000)     # 10 a 10 USD
        self.movement('A2', 'PUR', 10, days_ago=1, price=80000)     # 10 a 20 USD -> promedio 15
        self.movement('A3', 'ADJ_OUT', 5, days_ago=0)               # salida: 15 quedan

        services.sync_daily_stock(today=today)

        d2 = Stock.objects.get(date=today - timedelta(days=2))
        self.assertEqual((d2.quantity, d2.avg_price_usd), (10, Decimal('10.000000')))
        d1 = Stock.objects.get(date=today - timedelta(days=1))
        self.assertEqual((d1.quantity, d1.avg_price_usd), (20, Decimal('15.000000')))
        d0 = Stock.objects.get(date=today)
        self.assertEqual(d0.quantity, 15)                 # el curso dejaría 20
        self.assertEqual(d0.avg_price_usd, Decimal('15.000000'))
        self.assertEqual(d0.total_value_usd, Decimal('225.0000'))

    def test_incremental_sync_does_not_duplicate(self):
        today = timezone.localdate()
        self.movement('B1', 'PUR', 4, days_ago=3, price=40000)
        services.sync_daily_stock(today=today)
        self.movement('B2', 'PUR', 6, days_ago=0, price=40000)
        services.sync_daily_stock(today=today)
        self.assertEqual(Stock.objects.filter(date=today).count(), 1)
        self.assertEqual(Stock.objects.get(date=today).quantity, 10)
        self.assertEqual(Stock.objects.count(), 4)        # un registro por día

    def test_transfer_moves_value_between_locations(self):
        today = timezone.localdate()
        self.movement('C1', 'PUR', 10, days_ago=1, price=40000)
        services.register_transfer(material=self.material, origin=self.bodega, destination=self.local,
                                   quantity=4, notes='', user=self.user)
        services.sync_daily_stock(today=today)
        self.assertEqual(Stock.objects.get(date=today, id_location=self.bodega).quantity, 6)
        self.assertEqual(Stock.objects.get(date=today, id_location=self.local).quantity, 4)

    def test_fill_missing_exchange_rates(self):
        mv = self.movement('D1', 'PUR', 1, days_ago=0, price=4000, rate=Decimal('1'))
        ExchangeRate.objects.create(currency=self.cop, date=timezone.localdate(), rate=Decimal('4000'))
        self.assertEqual(services.fill_missing_exchange_rates(), 1)
        mv.refresh_from_db()
        self.assertEqual(mv.exchange_rate, Decimal('4000'))

    def test_stock_screen_shows_base_currency_value(self):
        UserRole.objects.create(user_id=self.user, role=Role.objects.get(role_name='Administrator'))
        self.client.force_login(self.user)
        self.movement('E1', 'PUR', 10, days_ago=0, price=40000)
        services.sync_daily_stock()
        r = self.client.get(reverse('inventory:stock_list'))
        self.assertContains(r, 'Value in USD')
        self.assertContains(r, '100.00')                 # 10 x 10 USD


class BackgroundTaskTests(TestCase):

    def test_only_one_thread_at_a_time(self):
        from unittest import mock
        from core import background
        with override_settings(BACKGROUND_TASKS_ENABLED=True), \
             mock.patch.object(background, '_last_run', None), \
             mock.patch('core.background.threading.Thread') as thread:
            self.assertTrue(background.trigger_background_tasks())
            self.assertFalse(background.trigger_background_tasks())   # el candado sigue tomado
            background._lock.release()
        self.assertEqual(thread.call_count, 1)
