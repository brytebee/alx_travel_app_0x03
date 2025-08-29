# listings/tasks.py

from alx_travel_app.listings.celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_payment_confirmation_email(user_email, booking_id, amount):
    """
    Send payment confirmation email to user
    """
    try:
        subject = 'Payment Confirmation - Booking Confirmed'
        
        # Create HTML content
        html_message = render_to_string('emails/payment_confirmation.html', {
            'booking_id': booking_id,
            'amount': amount
        })
        
        # Create plain text content
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject,
            plain_message,
            settings.EMAIL_HOST_USER,
            [user_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Payment confirmation email sent to {user_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send payment confirmation email: {str(e)}")
        return False

@shared_task
def send_booking_confirmation_email(to_email, booking_id):
    subject = "Booking Confirmation"
    message = f"Your booking with ID {booking_id} has been confirmed!"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [to_email])
    return f"Confirmation email sent to {to_email} for booking {booking_id}"
