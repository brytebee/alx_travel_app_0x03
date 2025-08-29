# tests/test_payment_integration.py

import json
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from listings.models import Listing, Booking, Payment
from unittest.mock import patch, Mock

class PaymentIntegrationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.listing = Listing.objects.create(
            title='Test Hotel',
            description='A nice hotel',
            price_per_night=100.00,
            location='Addis Ababa'
        )
        self.booking = Booking.objects.create(
            listing=self.listing,
            user=self.user,
            check_in_date='2024-12-01',
            check_out_date='2024-12-03',
            total_price=200.00
        )
        self.client.force_authenticate(user=self.user)

    @patch('listings.services.payment_service.requests.post')
    def test_initiate_payment_success(self, mock_post):
        # Mock successful Chapa response
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'success',
            'data': {
                'checkout_url': 'https://checkout.chapa.co/test',
                'reference': 'chapa_ref_123'
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        response = self.client.post('/api/payments/initiate/', {
            'booking_id': self.booking.id,
            'phone_number': '+251911123456'
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('checkout_url', data)
        self.assertIn('transaction_id', data)

    @patch('listings.services.payment_service.requests.get')
    def test_verify_payment_success(self, mock_get):
        # Create payment record
        payment = Payment.objects.create(
            booking=self.booking,
            transaction_id='test_tx_123',
            amount=200.00,
            status='pending'
        )

        # Mock successful verification response
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'success',
            'data': {
                'status': 'success',
                'method': 'card'
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        response = self.client.get(f'/api/payments/verify/{payment.transaction_id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'completed')

        # Check payment status updated
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'completed')
