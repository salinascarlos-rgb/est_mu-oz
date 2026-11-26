import json
from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.models import Currency, ExchangeRate
from customers.models import Customer
from inventory.models import InventoryMovements, LocationInventory, MovementType
from inventory import services as inventory_services
from materials.models import Material, Unit
from users.models import User, Role, UserRole
from .models import SalesOrder, LinesSalesOrder
from . import services


class SalesTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command('seed_data', verbosity=0)
        cls.user = User.objects.create_user(username='admin', password='pass12345')
        UserRole.objects.create(user_id=cls.user, role=Role.objects.get(role_name='Administrador'))
        cls.viewer = User.objects.create_user(username='viewer', password='pass12345')
        UserRole.objects.create(user_id=cls.viewer, role=Role.objects.create(role_name='SalesViewer', sales=1))

        cls.customer = Customer.objects.create(
            id_customer='C001', name='Ferretería Yumbo', tax_id='900', country='Colombia', state_province='Valle',
            city='Yumbo', address='Calle 5', zip_code=760001, phone=3000000, email='c@x.com', contact_name='Luis',
            contact_role='Compras', category='Ferretería', payment_terms='30', currency='COP',
            payment_method='Transfer', bank_account='1', status='Active',
        )
        cls.material = Material.objects.create(id_material='M001', name='Estuco', unit=Unit.objects.get(symbol='UN'))
        cls.bodega = LocationInventory.objects.create(id_location='L1', name='Bodega', code='B1')
        # 10 unidades compradas a 12.000 COP
        InventoryMovements.objects.create(
            id_inventory_movement='GR1-1', id_location=cls.bodega, id_material=cls.material, quantity=10,
            unit_type=cls.material.unit, price=12000, currency=Currency.objects.get(symbol='COP'),
            movement_type=MovementType.objects.get(symbol='PUR'), created_by=cls.user,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def post_order(self, lines, delivery=None):
        payload = {
            'id_customer': 'C001',
            'estimated_delivery_date': (delivery or date.today() + timedelta(days=3)).isoformat(),
            'lines': lines,
        }
        return self.client.post(reverse('sales:sales_order_form'), json.dumps(payload), content_type='application/json')

    def line(self, qty, price=15000):
        return {'material_id': self.material.pk, 'location_id': self.bodega.pk, 'quantity': qty, 'price': price}

    def test_create_order_reserves_stock(self):
        r = self.post_order([self.line(4)])
        self.assertEqual(r.status_code, 201, r.content)
        order = SalesOrder.objects.get()
        self.assertEqual(order.id_sales_order, 'SO-00001')
        self.assertEqual(order.status.symbol, 'CONFIRMED')
        line = order.lines.get()
        self.assertEqual(line.wac, 12000)
        self.assertEqual(line.margin, 20.0)                     # (15000-12000)/15000
        self.assertEqual(line.currency.symbol, 'COP')
        # Reserva: físico no cambia, disponible sí
        self.assertEqual(inventory_services.get_stock(self.material, self.bodega), 10)
        self.assertEqual(services.reserved_quantity(self.material, self.bodega), 4)
        self.assertEqual(services.available_quantity(self.material, self.bodega), 6)

    def test_cannot_sell_more_than_available(self):
        self.assertEqual(self.post_order([self.line(7)]).status_code, 201)
        r = self.post_order([self.line(4)])                     # solo quedan 3 disponibles
        self.assertEqual(r.status_code, 400)
        self.assertIn('Disponible: 3', r.json()['error'])

    def test_repeated_lines_are_added_up(self):
        # Dos líneas de 6 suman 12 > 10: el curso las validaba por separado
        r = self.post_order([self.line(6), self.line(6)])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(SalesOrder.objects.count(), 0)

    def test_cancelled_order_releases_reservation(self):
        self.post_order([self.line(5)])
        from .models import SalesOrderStatus
        SalesOrder.objects.update(status=SalesOrderStatus.objects.get(symbol='CANCELLED'))
        self.assertEqual(services.available_quantity(self.material, self.bodega), 10)

    def test_past_delivery_date_rejected(self):
        r = self.post_order([self.line(1)], delivery=date.today() - timedelta(days=1))
        self.assertEqual(r.status_code, 400)

    def test_wac_converted_to_order_currency(self):
        usd = Currency.objects.get(symbol='USD')
        ExchangeRate.objects.create(currency=Currency.objects.get(symbol='COP'), date=date.today(), rate=Decimal('4000'))
        self.assertAlmostEqual(services.cost_in_currency(self.material, usd), 3.0)   # 12.000 / 4.000

    def test_stock_api_and_pages(self):
        self.post_order([self.line(2)])
        data = self.client.get(reverse('sales:api_stock_data'),
                               {'material_id': self.material.pk, 'location_id': self.bodega.pk}).json()
        self.assertEqual((data['physical'], data['reserved'], data['available']), (10, 2, 8))
        self.assertEqual(self.client.get(reverse('sales:api_customer_details', args=['C001'])).json()['name'], 'Ferretería Yumbo')
        order = SalesOrder.objects.get()
        for url in [reverse('sales:sales_order_list'), reverse('sales:sales_order_form'),
                    reverse('sales:sales_order_detail', args=[order.pk])]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        csv_text = self.client.get(reverse('sales:sales_order_list'), {'export': 'csv'}).content.decode('utf-8-sig')
        self.assertIn('SO-00001', csv_text)
        stock_csv = self.client.get(reverse('inventory:stock'), {'export': 'csv'}).content.decode('utf-8-sig')
        self.assertIn(',10,2,8,', stock_csv)                   # físico, reservado, disponible

    def test_snapshot_keeps_reserved_for_today(self):
        self.post_order([self.line(3)])
        inventory_services.sync_daily_stock()
        from inventory.models import Stock
        self.assertEqual(Stock.objects.get(date=date.today()).reserved_quantity, 3)

    def test_view_only_user_cannot_create(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.post_order([self.line(1)]).status_code, 403)
        self.assertEqual(self.client.get(reverse('sales:sales_order_list')).status_code, 200)
