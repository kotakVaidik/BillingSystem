import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from billing_app.models import Customer, DistributorProfile



class CustomerManagementTests(TestCase):
    def setUp(self):
        self.distributor_group, _ = Group.objects.get_or_create(name='Distributor')

        self.user1 = User.objects.create_user(
            username='dist1',
            email='dist1@gmail.com',
            password='Password@123'
        )
        self.user1.groups.add(self.distributor_group)
        DistributorProfile.objects.create(user=self.user1, phone='+919876543210')

        self.user2 = User.objects.create_user(
            username='dist2',
            email='dist2@gmail.com',
            password='Password@123'
        )
        self.user2.groups.add(self.distributor_group)
        DistributorProfile.objects.create(user=self.user2, phone='+919876543211')

        # Customers for user1
        self.c1 = Customer.objects.create(
            distributor=self.user1,
            name='Alice Wonderland',
            email='alice@gmail.com',
            phone='+919111111111',
            address='123 Fantasy Lane'
        )
        self.c2 = Customer.objects.create(
            distributor=self.user1,
            name='Bob Builder',
            email='bob@outlook.com',
            phone='+919222222222',
            address='456 Construction Rd'
        )

        # Customer for user2
        self.c3 = Customer.objects.create(
            distributor=self.user2,
            name='Charlie Chaplin',
            email='charlie@gmail.com',
            phone='+919333333333',
            address='789 Cinema Blvd'
        )

        self.client = Client()

    def test_customer_list_unauthenticated(self):
        response = self.client.get(reverse('customer_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/distributor/', response.url)

    def test_customer_list_display_own_customers(self):
        self.client.login(username='dist1', password='Password@123')
        response = self.client.get(reverse('customer_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice Wonderland')
        self.assertContains(response, 'Bob Builder')
        self.assertNotContains(response, 'Charlie Chaplin')

    def test_customer_search_by_name_phone_email(self):
        self.client.login(username='dist1', password='Password@123')

        # Search by name
        response = self.client.get(reverse('customer_list') + '?q=Alice')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice Wonderland')
        self.assertNotContains(response, 'Bob Builder')

        # Search by phone
        response = self.client.get(reverse('customer_list') + '?q=9222222222')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bob Builder')
        self.assertNotContains(response, 'Alice Wonderland')

        # Search with no match
        response = self.client.get(reverse('customer_list') + '?q=NonExistent')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No customers found')

    def test_edit_customer_get_form(self):
        self.client.login(username='dist1', password='Password@123')
        response = self.client.get(reverse('edit_customer', kwargs={'customer_id': self.c1.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice Wonderland')
        self.assertContains(response, '+919111111111')
        self.assertContains(response, 'alice@gmail.com')

    def test_edit_customer_post_valid(self):
        self.client.login(username='dist1', password='Password@123')
        response = self.client.post(reverse('edit_customer', kwargs={'customer_id': self.c1.id}), {
            'name': 'Alice Updated',
            'phone': '+919999999999',
            'email': 'alice.new@gmail.com',
            'address': 'New Address'
        })
        self.assertRedirects(response, reverse('customer_list'))

        self.c1.refresh_from_db()
        self.assertEqual(self.c1.name, 'Alice Updated')
        self.assertEqual(self.c1.phone, '+919999999999')
        self.assertEqual(self.c1.email, 'alice.new@gmail.com')
        self.assertEqual(self.c1.address, 'New Address')

    def test_edit_customer_validation(self):
        self.client.login(username='dist1', password='Password@123')

        # Empty name
        response = self.client.post(reverse('edit_customer', kwargs={'customer_id': self.c1.id}), {
            'name': '',
            'phone': '+919111111111',
            'email': 'alice@gmail.com',
            'address': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Customer name is required.')

        # Invalid phone
        response = self.client.post(reverse('edit_customer', kwargs={'customer_id': self.c1.id}), {
            'name': 'Alice',
            'phone': '123',
            'email': 'alice@gmail.com',
            'address': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a valid phone number')

    def test_edit_other_distributor_customer_forbidden(self):
        # User 1 attempts to edit User 2's customer
        self.client.login(username='dist1', password='Password@123')
        response = self.client.get(reverse('edit_customer', kwargs={'customer_id': self.c3.id}))
        self.assertEqual(response.status_code, 404)

    def test_delete_customer(self):
        self.client.login(username='dist1', password='Password@123')
        target_id = self.c2.id
        response = self.client.post(reverse('delete_customer', kwargs={'customer_id': target_id}))
        self.assertRedirects(response, reverse('customer_list'))
        self.assertFalse(Customer.objects.filter(id=target_id).exists())

    def test_delete_other_distributor_customer_forbidden(self):
        # User 1 attempts to delete User 2's customer
        self.client.login(username='dist1', password='Password@123')
        response = self.client.post(reverse('delete_customer', kwargs={'customer_id': self.c3.id}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Customer.objects.filter(id=self.c3.id).exists())


from decimal import Decimal
from django.core.exceptions import ValidationError
from billing_app.models import Product, Invoice, InvoiceItem
from billing_app.gst_utils import (
    calculate_gst_breakdown,
    lookup_hsn,
    validate_hsn_code,
    round_to_rupee,
    round_currency,
    TAX_CATEGORY_TAXABLE,
    TAX_CATEGORY_NIL_RATED,
    TAX_CATEGORY_EXEMPT,
    TAX_CATEGORY_NON_GST,
)


class ProductModelAndGstTests(TestCase):
    def setUp(self):
        self.distributor_group, _ = Group.objects.get_or_create(name='Distributor')
        self.user = User.objects.create_user(username='dist_gst', email='dist_gst@gmail.com', password='Password@123')
        self.user.groups.add(self.distributor_group)

    def test_valid_product_creation(self):
        product = Product.objects.create(
            distributor=self.user,
            name='Basmati Rice 25kg',
            category='Grains & Pulses',
            hsn_code='1006',
            price=Decimal('1450.00'),
            stock=100,
            gst_rate=Decimal('5.00'),
            tax_category=TAX_CATEGORY_TAXABLE,
            cess_rate=Decimal('0.00'),
            price_includes_gst=False,
        )
        product.full_clean()
        self.assertEqual(product.name, 'Basmati Rice 25kg')
        self.assertEqual(product.gst_rate, Decimal('5.00'))
        self.assertTrue(product.is_taxable)

    def test_price_must_be_greater_than_zero(self):
        product = Product(
            distributor=self.user,
            name='Free Sample Item',
            category='Samples',
            hsn_code='1006',
            price=Decimal('0.00'),
            stock=10,
            gst_rate=Decimal('5.00'),
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_stock_cannot_be_negative(self):
        product = Product(
            distributor=self.user,
            name='Test Product',
            category='Test',
            hsn_code='1006',
            price=Decimal('100.00'),
            stock=-5,
            gst_rate=Decimal('5.00'),
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_invalid_hsn_format(self):
        product = Product(
            distributor=self.user,
            name='Test HSN',
            category='Test',
            hsn_code='INVALID',
            price=Decimal('100.00'),
            stock=10,
            gst_rate=Decimal('5.00'),
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_invalid_gst_rate_for_taxable_product(self):
        # 17% is not an official Indian GST slab
        product = Product(
            distributor=self.user,
            name='Arbitrary Rate Product',
            category='Test',
            hsn_code='8471',
            price=Decimal('1000.00'),
            stock=10,
            gst_rate=Decimal('17.00'),
            tax_category=TAX_CATEGORY_TAXABLE,
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_exempt_and_nil_rated_require_zero_gst(self):
        # Exempt items must have 0% GST
        product = Product(
            distributor=self.user,
            name='Fresh Milk',
            category='Dairy',
            hsn_code='0401',
            price=Decimal('50.00'),
            stock=20,
            gst_rate=Decimal('5.00'),
            tax_category=TAX_CATEGORY_EXEMPT,
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_official_hsn_catalogue_lookup(self):
        rice_info = lookup_hsn('1006')
        self.assertIsNotNone(rice_info)
        self.assertTrue(rice_info['is_verified'])
        self.assertEqual(rice_info['gst_rate'], Decimal('5.00'))

        milk_info = lookup_hsn('0401')
        self.assertIsNotNone(milk_info)
        self.assertEqual(milk_info['tax_category'], TAX_CATEGORY_EXEMPT)

        aerated_info = lookup_hsn('2202')
        self.assertIsNotNone(aerated_info)
        self.assertEqual(aerated_info['gst_rate'], Decimal('28.00'))
        self.assertEqual(aerated_info['cess_rate'], Decimal('12.00'))

    def test_intra_state_gst_calculation(self):
        # 18% GST on ₹1000.00 intra-state -> 9% CGST (₹90.00), 9% SGST (₹90.00), IGST 0
        calc = calculate_gst_breakdown(
            price=Decimal('1000.00'),
            quantity=Decimal('1'),
            gst_rate=Decimal('18.00'),
            is_interstate=False
        )
        self.assertEqual(calc['taxable_value'], Decimal('1000.00'))
        self.assertEqual(calc['cgst_rate'], Decimal('9.00'))
        self.assertEqual(calc['cgst_amount'], Decimal('90.00'))
        self.assertEqual(calc['sgst_rate'], Decimal('9.00'))
        self.assertEqual(calc['sgst_amount'], Decimal('90.00'))
        self.assertEqual(calc['igst_amount'], Decimal('0.00'))
        self.assertEqual(calc['total_tax'], Decimal('180.00'))
        self.assertEqual(calc['total_amount'], Decimal('1180.00'))

    def test_inter_state_gst_calculation(self):
        # 18% GST on ₹1000.00 inter-state -> 18% IGST (₹180.00), CGST 0, SGST 0
        calc = calculate_gst_breakdown(
            price=Decimal('1000.00'),
            quantity=Decimal('1'),
            gst_rate=Decimal('18.00'),
            is_interstate=True
        )
        self.assertEqual(calc['taxable_value'], Decimal('1000.00'))
        self.assertEqual(calc['igst_rate'], Decimal('18.00'))
        self.assertEqual(calc['igst_amount'], Decimal('180.00'))
        self.assertEqual(calc['cgst_amount'], Decimal('0.00'))
        self.assertEqual(calc['sgst_amount'], Decimal('0.00'))
        self.assertEqual(calc['total_amount'], Decimal('1180.00'))

    def test_gst_inclusive_price_extraction(self):
        # Inclusive price ₹118.00 with 18% GST -> Taxable = 118 / 1.18 = ₹100.00, Tax = ₹18.00
        calc = calculate_gst_breakdown(
            price=Decimal('118.00'),
            quantity=Decimal('1'),
            gst_rate=Decimal('18.00'),
            price_includes_gst=True,
            is_interstate=False
        )
        self.assertEqual(calc['taxable_value'], Decimal('100.00'))
        self.assertEqual(calc['cgst_amount'], Decimal('9.00'))
        self.assertEqual(calc['sgst_amount'], Decimal('9.00'))
        self.assertEqual(calc['total_amount'], Decimal('118.00'))

    def test_compensation_cess_calculation(self):
        # Aerated drink 28% GST + 12% Cess on ₹100.00
        calc = calculate_gst_breakdown(
            price=Decimal('100.00'),
            quantity=Decimal('1'),
            gst_rate=Decimal('28.00'),
            cess_rate=Decimal('12.00'),
            is_interstate=False
        )
        self.assertEqual(calc['taxable_value'], Decimal('100.00'))
        self.assertEqual(calc['cgst_amount'], Decimal('14.00'))
        self.assertEqual(calc['sgst_amount'], Decimal('14.00'))
        self.assertEqual(calc['cess_amount'], Decimal('12.00'))
        self.assertEqual(calc['total_tax'], Decimal('40.00'))
        self.assertEqual(calc['total_amount'], Decimal('140.00'))

    def test_historical_invoice_rate_stability(self):
        # Invoice created with product at 18%
        prod = Product.objects.create(
            distributor=self.user,
            name='Historical Widget',
            category='Hardware',
            hsn_code='8471',
            price=Decimal('500.00'),
            stock=50,
            gst_rate=Decimal('18.00'),
        )
        inv = Invoice.objects.create(
            distributor=self.user,
            invoice_number='INV-TEST-001',
            taxable_amount=Decimal('500.00'),
            cgst_amount=Decimal('45.00'),
            sgst_amount=Decimal('45.00'),
            total_tax=Decimal('90.00'),
            grand_total=Decimal('590.00'),
        )
        item = InvoiceItem.objects.create(
            invoice=inv,
            product=prod,
            product_name=prod.name,
            hsn_code=prod.hsn_code,
            quantity=1,
            unit_price=prod.price,
            gst_rate=prod.gst_rate,
            taxable_value=Decimal('500.00'),
            cgst_amount=Decimal('45.00'),
            sgst_amount=Decimal('45.00'),
            total_amount=Decimal('590.00'),
        )

        # Later, product price and GST rate are changed in catalog
        prod.price = Decimal('800.00')
        prod.gst_rate = Decimal('12.00')
        prod.save()

        # Historical invoice and items MUST remain unchanged
        item.refresh_from_db()
        inv.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal('500.00'))
        self.assertEqual(item.gst_rate, Decimal('18.00'))
        self.assertEqual(inv.grand_total, Decimal('590.00'))


class ProductViewAndValidationTests(TestCase):
    def setUp(self):
        self.distributor_group, _ = Group.objects.get_or_create(name='Distributor')

        self.user1 = User.objects.create_user(
            username='dist_v1',
            email='dist_v1@gmail.com',
            password='Password@123'
        )
        self.user1.groups.add(self.distributor_group)

        self.user2 = User.objects.create_user(
            username='dist_v2',
            email='dist_v2@gmail.com',
            password='Password@123'
        )
        self.user2.groups.add(self.distributor_group)

        # Products for user1
        self.p1 = Product.objects.create(
            distributor=self.user1,
            name='Alpha Rice 25kg',
            category='Grocery',
            hsn_code='1006',
            price=Decimal('1500.00'),
            stock=40,
            gst_rate=Decimal('5.00'),
        )
        self.p2 = Product.objects.create(
            distributor=self.user1,
            name='Beta Sunflower Oil 15L',
            category='Edible Oils',
            hsn_code='1512',
            price=Decimal('2400.00'),
            stock=25,
            gst_rate=Decimal('5.00'),
        )

        self.client = Client()

    def test_product_list_unauthenticated(self):
        response = self.client.get(reverse('product_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/distributor/', response.url)

    def test_product_list_displays_own_products(self):
        self.client.login(username='dist_v1', password='Password@123')
        response = self.client.get(reverse('product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha Rice 25kg')
        self.assertContains(response, 'Beta Sunflower Oil 15L')

    def test_product_search_by_name_category_hsn(self):
        self.client.login(username='dist_v1', password='Password@123')

        # Search by name
        res = self.client.get(reverse('product_list') + '?q=Alpha')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Alpha Rice 25kg')
        self.assertNotContains(res, 'Beta Sunflower Oil 15L')

        # Search by category
        res = self.client.get(reverse('product_list') + '?q=Edible')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Beta Sunflower Oil 15L')
        self.assertNotContains(res, 'Alpha Rice 25kg')

        # Search by HSN
        res = self.client.get(reverse('product_list') + '?q=1512')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Beta Sunflower Oil 15L')

        # Non-matching search shows clear message
        res = self.client.get(reverse('product_list') + '?q=NonExistent999')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'No products found')

    def test_product_pagination_and_invalid_page(self):
        self.client.login(username='dist_v1', password='Password@123')
        # Create 12 more products (total 14 products, 8 per page = 2 pages)
        for i in range(12):
            Product.objects.create(
                distributor=self.user1,
                name=f'Bulk Product {i:02d}',
                category='Bulk',
                hsn_code='1006',
                price=Decimal('100.00'),
                stock=10,
                gst_rate=Decimal('5.00'),
            )

        # Page 1
        res = self.client.get(reverse('product_list') + '?page=1')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context['products']), 8)
        self.assertTrue(res.context['page_obj'].has_next())

        # Page 2
        res = self.client.get(reverse('product_list') + '?page=2')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context['products']), 6)

        # Invalid page number (string) handles gracefully without error
        res = self.client.get(reverse('product_list') + '?page=abc')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['page_obj'].number, 1)

        # Out-of-range page number handles gracefully
        res = self.client.get(reverse('product_list') + '?page=9999')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['page_obj'].number, 2)

    def test_add_product_get_form(self):
        self.client.login(username='dist_v1', password='Password@123')
        response = self.client.get(reverse('add_product'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Product Name')
        self.assertContains(response, 'HSN Code')
        self.assertContains(response, 'Applicable GST Rate')

    def test_add_product_post_valid(self):
        self.client.login(username='dist_v1', password='Password@123')
        response = self.client.post(reverse('add_product'), {
            'name': 'Organic Green Tea 100g',
            'category': 'Beverages',
            'hsn_code': '0902',
            'price': '250.00',
            'stock': '50',
            'tax_category': 'TAXABLE',
            'gst_rate': '5.00',
            'cess_rate': '0.00',
            'price_includes_gst': False,
            'description': 'High altitude whole leaf tea',
        })
        self.assertRedirects(response, reverse('product_list'))
        created = Product.objects.get(name='Organic Green Tea 100g')
        self.assertEqual(created.price, Decimal('250.00'))
        self.assertEqual(created.stock, 50)
        self.assertEqual(created.hsn_code, '0902')

    def test_add_product_validation_errors(self):
        self.client.login(username='dist_v1', password='Password@123')

        # 1. Empty name
        res = self.client.post(reverse('add_product'), {
            'name': '',
            'category': 'Beverages',
            'hsn_code': '0902',
            'price': '100.00',
            'stock': '10',
            'gst_rate': '5.00',
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Product name is required.')

        # 2. Zero price
        res = self.client.post(reverse('add_product'), {
            'name': 'Zero Price Product',
            'category': 'Beverages',
            'hsn_code': '0902',
            'price': '0.00',
            'stock': '10',
            'gst_rate': '5.00',
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Price must be a valid number greater than zero.')

        # 3. Negative stock
        res = self.client.post(reverse('add_product'), {
            'name': 'Negative Stock Product',
            'category': 'Beverages',
            'hsn_code': '0902',
            'price': '100.00',
            'stock': '-5',
            'gst_rate': '5.00',
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Stock quantity must be a non-negative whole number')

        # 4. Invalid GST slab
        res = self.client.post(reverse('add_product'), {
            'name': 'Illegal GST Rate Item',
            'category': 'Beverages',
            'hsn_code': '0902',
            'price': '100.00',
            'stock': '10',
            'tax_category': 'TAXABLE',
            'gst_rate': '13.50',
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'not a valid Indian GST slab')

        # 5. Duplicate product name
        res = self.client.post(reverse('add_product'), {
            'name': 'Alpha Rice 25kg',  # already exists for user1
            'category': 'Grocery',
            'hsn_code': '1006',
            'price': '1500.00',
            'stock': '20',
            'gst_rate': '5.00',
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'already exists in your inventory')

    def test_edit_product_post(self):
        self.client.login(username='dist_v1', password='Password@123')
        res = self.client.post(reverse('edit_product', kwargs={'product_id': self.p1.id}), {
            'name': 'Alpha Rice 25kg Premium',
            'category': 'Grocery',
            'hsn_code': '1006',
            'price': '1650.00',
            'stock': '35',
            'tax_category': 'TAXABLE',
            'gst_rate': '5.00',
            'cess_rate': '0.00',
            'price_includes_gst': False,
        })
        self.assertRedirects(res, reverse('product_list'))
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.name, 'Alpha Rice 25kg Premium')
        self.assertEqual(self.p1.price, Decimal('1650.00'))

    def test_delete_product_post(self):
        self.client.login(username='dist_v1', password='Password@123')
        target_id = self.p2.id
        res = self.client.post(reverse('delete_product', kwargs={'product_id': target_id}))
        self.assertRedirects(res, reverse('product_list'))
        self.assertFalse(Product.objects.filter(id=target_id).exists())

    def test_api_hsn_lookup(self):
        res = self.client.get(reverse('api_hsn_lookup') + '?hsn=1006')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['found'])
        self.assertEqual(data['gst_rate'], '5.00')

    def test_api_save_invoice_creates_record_and_decrements_stock(self):
        self.client.login(username='dist_v1', password='Password@123')
        initial_stock = self.p1.stock
        payload = {
            'customer_name': 'Test Store',
            'place_of_supply': 'Intra-State',
            'is_interstate': False,
            'items': [
                {
                    'product_id': self.p1.id,
                    'name': self.p1.name,
                    'hsn_code': self.p1.hsn_code,
                    'qty': 5,
                    'rate': float(self.p1.price),
                    'gst_rate': float(self.p1.gst_rate),
                    'cess_rate': 0,
                    'price_includes_gst': False,
                }
            ]
        }
        res = self.client.post(
            reverse('api_save_invoice'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])

        inv = Invoice.objects.get(invoice_number=data['invoice_number'])
        self.assertEqual(inv.items.count(), 1)
        self.p1.refresh_from_db()
        # Stock should be decremented by 5
        self.assertEqual(self.p1.stock, initial_stock - 5)

