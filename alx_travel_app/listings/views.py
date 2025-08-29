# alx_travel_app/listings/views.py

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site
from .models import Booking, Payment
from .services.payment_service import ChapaPaymentService
from .tasks import send_payment_confirmation_email
import logging
import uuid

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    """
    Initiate payment for a booking
    """
    try:
        booking_id = request.data.get('booking_id')
        
        if not booking_id:
            return Response(
                {'error': 'Booking ID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the booking
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
        
        # Check if payment already exists
        if hasattr(booking, 'payment') and booking.payment.status != 'failed':
            return Response(
                {'error': 'Payment already exists for this booking'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or get payment record
        payment, created = Payment.objects.get_or_create(
            booking=booking,
            defaults={
                'amount': booking.total_price,
                'currency': 'ETB',
                'status': 'pending'
            }
        )
        
        if not created and payment.status == 'completed':
            return Response(
                {'error': 'Payment already completed for this booking'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate unique transaction reference
        tx_ref = f"booking_{booking.id}_{uuid.uuid4().hex[:8]}"
        
        # Get current site domain
        current_site = get_current_site(request)
        domain = f"http://{current_site.domain}" if request.is_secure() else f"http://{current_site.domain}"
        
        # Prepare payment data
        payment_data = {
            'amount': float(booking.total_price),
            'currency': 'ETB',
            'email': request.user.email,
            'first_name': request.user.first_name or request.user.username,
            'last_name': request.user.last_name or '',
            'phone_number': request.data.get('phone_number', ''),
            'tx_ref': tx_ref,
            'callback_url': f"{domain}/api/payments/callback/",
            'return_url': f"{domain}/booking/success/",
            'description': f"Booking payment for {booking.listing.title}",
            'meta': {
                'booking_id': str(booking.id),
                'payment_id': str(payment.id),
                'user_id': str(request.user.id)
            }
        }
        
        # Initialize payment with Chapa
        chapa_service = ChapaPaymentService()
        result = chapa_service.initiate_payment(payment_data)
        
        if result['success']:
            # Update payment record
            payment.transaction_id = tx_ref
            payment.chapa_reference = result['data'].get('reference')
            payment.save()
            
            logger.info(f"Payment initiated successfully for booking {booking.id}")
            
            return Response({
                'success': True,
                'payment_id': str(payment.id),
                'checkout_url': result['checkout_url'],
                'transaction_id': tx_ref
            }, status=status.HTTP_200_OK)
        else:
            logger.error(f"Payment initiation failed for booking {booking.id}: {result['error']}")
            return Response(
                {'error': result['error']}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
    except Exception as e:
        logger.error(f"Error initiating payment: {str(e)}")
        return Response(
            {'error': 'An unexpected error occurred'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_payment(request, transaction_id):
    """
    Verify payment status
    """
    try:
        # Get payment record
        payment = get_object_or_404(Payment, transaction_id=transaction_id)
        
        # Check if user owns this payment
        if payment.booking.user != request.user:
            return Response(
                {'error': 'Unauthorized'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Skip verification if already completed
        if payment.status == 'completed':
            return Response({
                'success': True,
                'status': 'completed',
                'message': 'Payment already verified and completed'
            })
        
        # Verify with Chapa
        chapa_service = ChapaPaymentService()
        result = chapa_service.verify_payment(transaction_id)
        
        if result['success']:
            payment_data = result['data']
            
            # Update payment status based on Chapa response
            if payment_data['status'] == 'success':
                payment.status = 'completed'
                payment.payment_method = payment_data.get('method')
                payment.save()
                
                # Send confirmation email asynchronously
                send_payment_confirmation_email.delay(
                    payment.booking.user.email,
                    payment.booking.id,
                    str(payment.amount)
                )
                
                logger.info(f"Payment {payment.id} verified and completed")
                
                return Response({
                    'success': True,
                    'status': 'completed',
                    'message': 'Payment verified successfully',
                    'payment_details': {
                        'amount': str(payment.amount),
                        'currency': payment.currency,
                        'method': payment.payment_method,
                        'transaction_id': payment.transaction_id
                    }
                })
            else:
                payment.status = 'failed'
                payment.save()
                
                return Response({
                    'success': False,
                    'status': 'failed',
                    'message': 'Payment verification failed'
                })
        else:
            logger.error(f"Payment verification failed for {transaction_id}: {result['error']}")
            return Response(
                {'error': result['error']}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}")
        return Response(
            {'error': 'An unexpected error occurred'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def payment_callback(request):
    """
    Handle Chapa payment callback (webhook)
    """
    try:
        # Extract callback data
        status_data = request.data.get('status')
        tx_ref = request.data.get('tx_ref')
        
        if not tx_ref:
            logger.warning("Callback received without tx_ref")
            return Response({'message': 'Invalid callback'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get payment record
        try:
            payment = Payment.objects.get(transaction_id=tx_ref)
        except Payment.DoesNotExist:
            logger.warning(f"Payment not found for tx_ref: {tx_ref}")
            return Response({'message': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Update payment status based on callback
        if status_data == 'success':
            payment.status = 'completed'
            payment.save()
            
            # Send confirmation email
            send_payment_confirmation_email.delay(
                payment.booking.user.email,
                payment.booking.id,
                str(payment.amount)
            )
            
            logger.info(f"Payment {payment.id} completed via callback")
        else:
            payment.status = 'failed'
            payment.save()
            logger.info(f"Payment {payment.id} failed via callback")
        
        return Response({'message': 'Callback processed'}, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error processing callback: {str(e)}")
        return Response(
            {'error': 'Callback processing failed'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_status(request, payment_id):
    """
    Get payment status
    """
    try:
        payment = get_object_or_404(Payment, id=payment_id)
        
        # Check if user owns this payment
        if payment.booking.user != request.user:
            return Response(
                {'error': 'Unauthorized'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        return Response({
            'payment_id': str(payment.id),
            'status': payment.status,
            'amount': str(payment.amount),
            'currency': payment.currency,
            'transaction_id': payment.transaction_id,
            'created_at': payment.created_at,
            'updated_at': payment.updated_at
        })
        
    except Exception as e:
        logger.error(f"Error getting payment status: {str(e)}")
        return Response(
            {'error': 'An unexpected error occurred'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
