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
