# listings/services/payment_service.py

import requests
import logging
from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

class ChapaPaymentService:
    def __init__(self):
        self.base_url = settings.CHAPA_BASE_URL
        self.secret_key = settings.CHAPA_SECRET_KEY
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
    
    def initiate_payment(self, payment_data):
        """
        Initiate payment with Chapa API
        """
        url = f"{self.base_url}transaction/initialize"
        
        payload = {
            'amount': str(payment_data['amount']),
            'currency': payment_data.get('currency', 'ETB'),
            'email': payment_data['email'],
            'first_name': payment_data['first_name'],
            'last_name': payment_data['last_name'],
            'phone_number': payment_data.get('phone_number', ''),
            'tx_ref': payment_data['tx_ref'],
            'callback_url': payment_data['callback_url'],
            'return_url': payment_data['return_url'],
            'description': payment_data.get('description', 'Hotel Booking Payment'),
            'meta': payment_data.get('meta', {})
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') == 'success':
                return {
                    'success': True,
                    'data': data['data'],
                    'checkout_url': data['data']['checkout_url']
                }
            else:
                logger.error(f"Chapa API error: {data.get('message', 'Unknown error')}")
                return {
                    'success': False,
                    'error': data.get('message', 'Payment initialization failed')
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during payment initiation: {str(e)}")
            return {
                'success': False,
                'error': 'Network error occurred. Please try again.'
            }
        except Exception as e:
            logger.error(f"Unexpected error during payment initiation: {str(e)}")
            return {
                'success': False,
                'error': 'An unexpected error occurred. Please try again.'
            }
    
    def verify_payment(self, tx_ref):
        """
        Verify payment status with Chapa API
        """
        url = f"{self.base_url}transaction/verify/{tx_ref}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') == 'success':
                return {
                    'success': True,
                    'data': data['data']
                }
            else:
                return {
                    'success': False,
                    'error': data.get('message', 'Payment verification failed')
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during payment verification: {str(e)}")
            return {
                'success': False,
                'error': 'Network error occurred during verification.'
            }
        except Exception as e:
            logger.error(f"Unexpected error during payment verification: {str(e)}")
            return {
                'success': False,
                'error': 'An unexpected error occurred during verification.'
            }
