import random
import string
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

OTP_EXPIRY_MINUTES = 10


class OTPToken(models.Model):
    """
    Stores a one-time password tied to a user for password-reset flows.

    Lifecycle:
      1. Created when user requests a password reset.
      2. Validated when user submits the OTP form.
      3. Marked used (is_used=True) on successful verification.
      4. Invalidated (is_used=True) when a resend occurs, so only the
         latest OTP for a user is ever active.
    """

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_tokens')
    otp        = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used    = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'OTP Token'
        verbose_name_plural = 'OTP Tokens'

    def __str__(self):
        return f"OTP for {self.user.email} — {'used' if self.is_used else 'active'}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_expired(self):
        """Return True if this OTP is older than OTP_EXPIRY_MINUTES."""
        expiry_time = self.created_at + timedelta(minutes=OTP_EXPIRY_MINUTES)
        return timezone.now() > expiry_time

    def is_valid(self, code):
        """Return True if the supplied code matches, is not used, and not expired."""
        return (
            not self.is_used
            and not self.is_expired()
            and self.otp == str(code).strip()
        )

    # ------------------------------------------------------------------
    # Class-level helpers
    # ------------------------------------------------------------------

    @classmethod
    def generate_otp(cls):
        """Return a cryptographically safe 6-digit numeric OTP string."""
        return ''.join(random.choices(string.digits, k=6))

    @classmethod
    def invalidate_all_for_user(cls, user):
        """Mark all existing active OTPs for this user as used (before resend)."""
        cls.objects.filter(user=user, is_used=False).update(is_used=True)

    @classmethod
    def create_for_user(cls, user):
        """
        Invalidate any existing OTPs, generate a new one, persist and return it.
        """
        cls.invalidate_all_for_user(user)
        otp_code = cls.generate_otp()
        return cls.objects.create(user=user, otp=otp_code)


class DistributorProfile(models.Model):
    """
    Extended profile for distributors, storing phone number.
    Linked 1-to-1 with the built-in User model.
    """

    user  = models.OneToOneField(User, on_delete=models.CASCADE, related_name='distributor_profile')
    phone = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = 'Distributor Profile'
        verbose_name_plural = 'Distributor Profiles'

    def __str__(self):
        return f"Distributor: {self.user.get_full_name() or self.user.username}"


class Customer(models.Model):
    """
    Stores customer records associated with a specific distributor (User).
    """

    distributor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customers')
    name        = models.CharField(max_length=150)
    email       = models.EmailField(blank=True, null=True)
    phone       = models.CharField(max_length=20)
    address     = models.TextField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    def __str__(self):
        return f"{self.name} ({self.phone})"

