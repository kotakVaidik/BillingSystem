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


from decimal import Decimal
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from .gst_utils import (
    TAX_CATEGORY_CHOICES,
    TAX_CATEGORY_TAXABLE,
    TAX_CATEGORY_NIL_RATED,
    TAX_CATEGORY_EXEMPT,
    TAX_CATEGORY_NON_GST,
    ZERO_TAX_CATEGORIES,
    VALID_GST_RATES,
    validate_hsn_code,
    calculate_gst_breakdown,
    round_currency,
)


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


class Product(models.Model):
    """
    Product model supporting full Indian GST classification (HSN, GST rate slabs,
    tax categories, compensation cess, and stock/inventory tracking).
    """

    distributor        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    name               = models.CharField(max_length=200)
    category           = models.CharField(max_length=100)
    hsn_code           = models.CharField(max_length=10, help_text="Harmonized System of Nomenclature code (2-8 digits)")
    price              = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Product unit price (greater than 0)"
    )
    stock              = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Stock quantity on hand (non-negative integer)"
    )
    gst_rate           = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Applicable GST rate percentage (0, 0.25, 3, 5, 12, 18, 28)"
    )
    tax_category       = models.CharField(
        max_length=20,
        choices=TAX_CATEGORY_CHOICES,
        default=TAX_CATEGORY_TAXABLE,
        help_text="Tax classification under Indian GST"
    )
    cess_rate          = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Compensation cess percentage if applicable (e.g. aerated beverages)"
    )
    price_includes_gst = models.BooleanField(
        default=False,
        help_text="Whether the entered price is inclusive of GST"
    )
    description        = models.TextField(blank=True, null=True)
    is_active          = models.BooleanField(default=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Product'
        verbose_name_plural = 'Products'

    def __str__(self):
        return f"{self.name} ({self.category}) — ₹{self.price} [GST {self.gst_rate}%]"

    def clean(self):
        super().clean()
        if self.price is not None and self.price <= Decimal('0.00'):
            raise ValidationError({'price': 'Price must be greater than zero.'})
        if self.stock is not None and self.stock < 0:
            raise ValidationError({'stock': 'Stock quantity cannot be negative.'})
        if self.hsn_code:
            clean_hsn = self.hsn_code.strip()
            if not validate_hsn_code(clean_hsn):
                raise ValidationError({'hsn_code': 'HSN code must consist of 2 to 8 numeric digits.'})
        if self.tax_category in ZERO_TAX_CATEGORIES:
            if self.gst_rate and self.gst_rate > Decimal('0.00'):
                raise ValidationError({'gst_rate': f'{self.get_tax_category_display()} items must have 0% GST.'})
        elif self.tax_category == TAX_CATEGORY_TAXABLE:
            if self.gst_rate is None or self.gst_rate < Decimal('0.00'):
                raise ValidationError({'gst_rate': 'GST rate cannot be negative.'})
            if self.gst_rate not in VALID_GST_RATES:
                raise ValidationError({'gst_rate': f'{self.gst_rate}% is not a standard Indian GST slab (0%, 0.25%, 3%, 5%, 12%, 18%, 28%).'})
        if self.cess_rate is not None and self.cess_rate < Decimal('0.00'):
            raise ValidationError({'cess_rate': 'Compensation cess rate cannot be negative.'})

    @property
    def is_exempt(self):
        return self.tax_category == TAX_CATEGORY_EXEMPT

    @property
    def is_nil_rated(self):
        return self.tax_category == TAX_CATEGORY_NIL_RATED

    @property
    def is_taxable(self):
        return self.tax_category == TAX_CATEGORY_TAXABLE

    @property
    def is_non_gst(self):
        return self.tax_category == TAX_CATEGORY_NON_GST

    def calculate_tax(self, quantity=1, is_interstate=False, discount=Decimal('0.00')):
        return calculate_gst_breakdown(
            price=self.price,
            quantity=Decimal(str(quantity)),
            gst_rate=self.gst_rate,
            cess_rate=self.cess_rate,
            tax_category=self.tax_category,
            price_includes_gst=self.price_includes_gst,
            is_interstate=is_interstate,
            discount=Decimal(str(discount)),
        )


class Invoice(models.Model):
    """
    Stores generated invoices with GST tax totals, distributor, and customer details.
    """

    distributor     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
    customer        = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    customer_name   = models.CharField(max_length=150, blank=True)
    invoice_number  = models.CharField(max_length=50, unique=True)
    invoice_date    = models.DateField(default=timezone.now)
    due_date        = models.DateField(null=True, blank=True)
    place_of_supply = models.CharField(max_length=100, default='Intra-State')
    is_interstate   = models.BooleanField(default=False)
    taxable_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    cgst_amount     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    sgst_amount     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    igst_amount     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    cess_amount     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_tax       = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    round_off       = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    grand_total     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status          = models.CharField(max_length=20, default='pending')  # paid, pending, overdue
    notes           = models.TextField(blank=True, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-invoice_date', '-id']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'

    def __str__(self):
        return f"{self.invoice_number} — {self.customer_name or (self.customer.name if self.customer else 'Cash')} — ₹{self.grand_total}"

    @property
    def subtotal(self):
        return self.taxable_amount

    @property
    def final_total(self):
        return self.grand_total


class InvoiceItem(models.Model):
    """
    Line items for an Invoice. Preserves snapshot of price, HSN, tax rate, and tax breakdown
    so historical invoices are NEVER modified when product rates change.
    """

    invoice            = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product            = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice_items')
    product_name       = models.CharField(max_length=200)
    hsn_code           = models.CharField(max_length=10, blank=True)
    quantity           = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price         = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    tax_category       = models.CharField(max_length=20, default=TAX_CATEGORY_TAXABLE)
    gst_rate           = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    cess_rate          = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    price_includes_gst = models.BooleanField(default=False)
    taxable_value      = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    cgst_amount        = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    sgst_amount        = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    igst_amount        = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    cess_amount        = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    total_amount       = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    class Meta:
        verbose_name = 'Invoice Item'
        verbose_name_plural = 'Invoice Items'

    def __str__(self):
        return f"{self.product_name} x {self.quantity} [₹{self.total_amount}]"

    @property
    def line_total(self):
        return self.total_amount

