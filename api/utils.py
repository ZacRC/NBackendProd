from django.core.mail import send_mail
from django.conf import settings
import random
import string

def generate_reset_token():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=20))

def send_reset_email(email, reset_token):
    reset_url = f"https://testprod142.netlify.app/reset-password?token={reset_token}"
    subject = "Password Reset Request"
    message = f"Click the following link to reset your password: {reset_url}"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])