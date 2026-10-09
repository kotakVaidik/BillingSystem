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
