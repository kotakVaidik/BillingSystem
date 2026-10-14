import json
import re
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .gst_utils import (
    TAX_CATEGORY_CHOICES,
    TAX_CATEGORY_TAXABLE,
    ZERO_TAX_CATEGORIES,
    VALID_GST_RATES,
    lookup_hsn,
    validate_hsn_code,
    calculate_gst_breakdown,
    round_currency,
    round_to_rupee,
)
from .models import Customer, DistributorProfile, OTPToken, Product, Invoice, InvoiceItem


ALLOWED_EMAIL_DOMAINS = {'gmail.com', 'outlook.com'}

SESSION_RESET_EMAIL    = 'pwd_reset_email'
SESSION_OTP_VERIFIED   = 'otp_verified'

def _validate_identifier(identifier):
    """
    If the identifier looks like an email, validate its domain.
    Returns an error string or None.
    """
    if '@' in identifier:
        parts = identifier.rsplit('@', 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return 'Enter a valid email address.'
        domain = parts[1].lower()
        if domain not in ALLOWED_EMAIL_DOMAINS:
            return 'Only @gmail.com and @outlook.com email addresses are accepted.'
    return None


def _validate_password(password):
    """
    Password rules:
      - Minimum 8 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one digit
      - At least one special character
    Returns an error string or None.
    """
    if len(password) < 8:
        return 'Password must be at least 8 characters long.'
    if not re.search(r'[A-Z]', password):
        return 'Password must contain at least one uppercase letter.'
    if not re.search(r'[a-z]', password):
        return 'Password must contain at least one lowercase letter.'
    if not re.search(r'\d', password):
        return 'Password must contain at least one number.'
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', password):
        return 'Password must contain at least one special character.'
    return None


def _get_user_by_identifier(identifier):
    if '@' in identifier:
        try:
            return User.objects.get(email=identifier)
        except User.DoesNotExist:
            return None
    try:
        return User.objects.get(username=identifier)
    except User.DoesNotExist:
        return None


def _redirect_if_authenticated(request, role):
    if request.user.is_authenticated:
        if role == 'admin' and request.user.is_staff:
            return redirect('admin_dashboard')
        if role == 'distributor' and request.user.groups.filter(name='Distributor').exists():
            return redirect('distributor_dashboard')
    return None


def _send_otp_email(email, otp_code):
    """Send the OTP to the user's email address."""
    subject = 'Your Password Reset OTP — Billing System'
    body = (
        f'Hello,\n\n'
        f'You requested a password reset for your Billing System distributor account.\n\n'
        f'Your One-Time Password (OTP) is:\n\n'
        f'    {otp_code}\n\n'
        f'This OTP is valid for {settings.OTP_EXPIRY_MINUTES} minutes.\n'
        f'Do not share this code with anyone.\n\n'
        f'If you did not request this, please ignore this email.\n\n'
        f'— Billing System'
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@billingsystem.local', [email])




def portal_home(request):

    return render(request, 'portal_home.html')




def admin_login(request):
    early = _redirect_if_authenticated(request, 'admin')
    if early:
        return early

    if request.method == 'POST':
        identifier = request.POST.get('email', '').strip()
        password   = request.POST.get('password', '')
        remember   = request.POST.get('remember_me')

        if not identifier or not password:
            messages.error(request, 'Email / username and password are required.')
            return render(request, 'admin/login.html', {'email_value': identifier})

        hardcoded_admin_login = (
            identifier.casefold() == settings.ADMIN_LOGIN_EMAIL.casefold()
            and password == settings.ADMIN_LOGIN_PASSWORD
        )

        email_error = None if hardcoded_admin_login else _validate_identifier(identifier)
        if email_error:
            messages.error(request, email_error)
            return render(request, 'admin/login.html', {'email_value': identifier})

        password_error = _validate_password(password)
        if password_error:
            messages.error(request, password_error)
            return render(request, 'admin/login.html', {'email_value': identifier})

        matched = _get_user_by_identifier(
            settings.ADMIN_LOGIN_EMAIL if hardcoded_admin_login else identifier
        )
        if hardcoded_admin_login and matched:
            user = matched
        else:
            username = matched.username if matched else identifier
            user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, 'Invalid credentials. Please try again.')
        elif not user.is_active:
            messages.error(request, 'Your account is inactive. Contact the administrator.')
        elif not user.is_staff:
            messages.error(request, 'Access denied. This portal is for administrators only.')
        else:
            login(request, user)
            if not remember:
                request.session.set_expiry(0)
            return redirect('admin_dashboard')

        return render(request, 'admin/login.html', {'email_value': identifier})

    return render(request, 'admin/login.html')


def admin_password_reset(request):
    return render(request, 'admin/login.html')




def distributor_login(request):
    early = _redirect_if_authenticated(request, 'distributor')
    if early:
        return early

    if request.method == 'POST':
        identifier = request.POST.get('email', '').strip()
        password   = request.POST.get('password', '')
        remember   = request.POST.get('remember_me')

        if not identifier or not password:
            messages.error(request, 'Email / username and password are required.')
            return render(request, 'distributor/login.html', {'email_value': identifier})

        email_error = _validate_identifier(identifier)
        if email_error:
            messages.error(request, email_error)
            return render(request, 'distributor/login.html', {'email_value': identifier})

        password_error = _validate_password(password)
        if password_error:
            messages.error(request, password_error)
            return render(request, 'distributor/login.html', {'email_value': identifier})

        matched  = _get_user_by_identifier(identifier)
        username = matched.username if matched else identifier
        user     = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, 'Invalid credentials. Please try again.')
        elif not user.is_active:
            messages.error(request, 'Your account is inactive. Contact the administrator.')
        elif not user.groups.filter(name='Distributor').exists():
            messages.error(request, 'Access denied. This portal is for distributors only.')
        else:
            login(request, user)
            if not remember:
                request.session.set_expiry(0)
            return redirect('distributor_dashboard')

        return render(request, 'distributor/login.html', {'email_value': identifier})

    return render(request, 'distributor/login.html')


def user_logout(request):
    logout(request)
    return redirect('admin_login')




from .models import Customer, DistributorProfile, OTPToken


@login_required(login_url='admin_login')
def admin_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('admin_login')
    return render(request, 'admin/dashboard.html')


@login_required(login_url='distributor_login')
def distributor_dashboard(request):
    if not request.user.groups.filter(name='Distributor').exists():
        messages.error(request, 'Access denied.')
        return redirect('distributor_login')

    customers = Customer.objects.filter(distributor=request.user).order_by('name')
    customer_count = customers.count()

    products = Product.objects.filter(
        Q(distributor=request.user) | Q(distributor__isnull=True),
        is_active=True
    ).order_by('name')
    product_count = products.count()

    products_data = [
        {
            'id': p.id,
            'name': p.name,
            'category': p.category,
            'hsn_code': p.hsn_code,
            'price': float(p.price),
            'stock': p.stock,
            'gst_rate': float(p.gst_rate),
            'tax_category': p.tax_category,
            'cess_rate': float(p.cess_rate),
            'price_includes_gst': p.price_includes_gst,
        }
        for p in products
    ]

    invoices = Invoice.objects.filter(distributor=request.user).order_by('-invoice_date', '-id')
    invoice_count = invoices.count()

    context = {
        'customers': customers,
        'customer_count': customer_count,
        'products': products,
        'product_count': product_count,
        'products_json': json.dumps(products_data),
        'invoices': invoices,
        'invoice_count': invoice_count,
    }
    return render(request, 'distributor/dashboard.html', context)





def distributor_forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()


        if not email or '@' not in email:
            messages.error(request, 'Please enter a valid email address.')
            return render(request, 'distributor/forgot_password.html', {'email_value': email})

        # Show the same message regardless of whether the user exists to prevent user enumeration.
        try:
            user = User.objects.get(email__iexact=email)
            is_distributor = user.groups.filter(name='Distributor').exists()
        except User.DoesNotExist:
            user = None
            is_distributor = False

        if user and is_distributor and user.is_active:
            token = OTPToken.create_for_user(user)
            try:
                _send_otp_email(user.email, token.otp)
            except Exception:

                pass


        request.session[SESSION_RESET_EMAIL]  = email
        request.session[SESSION_OTP_VERIFIED] = False

        messages.success(
            request,
            'If this email is registered, an OTP has been sent. Check your inbox.'
        )
        return redirect('distributor_verify_otp')

    return render(request, 'distributor/forgot_password.html')


def distributor_verify_otp(request):
   
    email = request.session.get(SESSION_RESET_EMAIL)

    if not email:
       
        messages.error(request, 'Your session has expired. Please start again.')
        return redirect('distributor_password_reset')

    if request.method == 'POST':
        otp_input = request.POST.get('otp', '').strip()

        if not otp_input or not re.match(r'^\d{6}$', otp_input):
            messages.error(request, 'Please enter a valid 6-digit OTP.')
            return render(request, 'distributor/verify_otp.html', {'masked_email': _mask_email(email)})

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            messages.error(request, 'Invalid request. Please start again.')
            return redirect('distributor_password_reset')

        token = (
            OTPToken.objects
            .filter(user=user, is_used=False)
            .order_by('-created_at')
            .first()
        )

        if token is None:
            messages.error(request, 'No active OTP found. Please request a new one.')
            return render(request, 'distributor/verify_otp.html', {'masked_email': _mask_email(email)})

        if token.is_expired():
            token.is_used = True
            token.save(update_fields=['is_used'])
            messages.error(request, 'Your OTP has expired. Please request a new one.')
            return render(request, 'distributor/verify_otp.html', {'masked_email': _mask_email(email)})

        if not token.is_valid(otp_input):
            messages.error(request, 'Incorrect OTP. Please try again.')
            return render(request, 'distributor/verify_otp.html', {'masked_email': _mask_email(email)})

      
        token.is_used = True
        token.save(update_fields=['is_used'])
        request.session[SESSION_OTP_VERIFIED] = True

        messages.success(request, 'OTP verified successfully. Please set your new password.')
        return redirect('distributor_reset_password')

    return render(request, 'distributor/verify_otp.html', {'masked_email': _mask_email(email)})


def distributor_resend_otp(request):
    if request.method != 'POST':
        return redirect('distributor_verify_otp')

    email = request.session.get(SESSION_RESET_EMAIL)
    if not email:
        messages.error(request, 'Session expired. Please start the password reset again.')
        return redirect('distributor_password_reset')

    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        messages.error(request, 'No account found for this email.')
        return redirect('distributor_password_reset')

    if not user.groups.filter(name='Distributor').exists() or not user.is_active:
        messages.error(request, 'Account is not eligible for password reset.')
        return redirect('distributor_password_reset')

    token = OTPToken.create_for_user(user)
    try:
        _send_otp_email(user.email, token.otp)
    except Exception:
        pass

    messages.success(request, 'A new OTP has been sent to your email.')
    return redirect('distributor_verify_otp')


def distributor_reset_password(request):

    email    = request.session.get(SESSION_RESET_EMAIL)
    verified = request.session.get(SESSION_OTP_VERIFIED, False)

    if not email or not verified:
        messages.error(request, 'Unauthorized access. Please complete OTP verification first.')
        return redirect('distributor_password_reset')

    if request.method == 'POST':
        new_password     = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        pw_error = _validate_password(new_password)
        if pw_error:
            messages.error(request, pw_error)
            return render(request, 'distributor/reset_password.html')

        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'distributor/reset_password.html')

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            messages.error(request, 'User not found. Please start again.')
            return redirect('distributor_password_reset')

        user.set_password(new_password)
        user.save()


        request.session.pop(SESSION_RESET_EMAIL, None)
        request.session.pop(SESSION_OTP_VERIFIED, None)

        messages.success(request, 'Your password has been reset successfully. Please sign in.')
        return redirect('distributor_login')

    return render(request, 'distributor/reset_password.html')




def distributor_register(request):
  
    if request.user.is_authenticated and request.user.groups.filter(name='Distributor').exists():
        return redirect('distributor_dashboard')

    if request.method == 'POST':
        full_name        = request.POST.get('full_name', '').strip()
        email            = request.POST.get('email', '').strip().lower()
        phone            = request.POST.get('phone', '').strip()
        password         = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        context = {
            'full_name_value': full_name,
            'email_value':     email,
            'phone_value':     phone,
        }


        if not full_name or not email or not phone or not password or not confirm_password:
            messages.error(request, 'All fields are required.')
            return render(request, 'distributor/register.html', context)


        email_error = _validate_identifier(email)
        if email_error:
            messages.error(request, email_error)
            return render(request, 'distributor/register.html', context)


        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'An account with this email address already exists.')
            return render(request, 'distributor/register.html', context)

      
        if not re.match(r'^\+?\d{7,15}$', phone):
            messages.error(request, 'Enter a valid phone number (digits only, 7–15 characters).')
            return render(request, 'distributor/register.html', context)


        pw_error = _validate_password(password)
        if pw_error:
            messages.error(request, pw_error)
            return render(request, 'distributor/register.html', context)

       
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'distributor/register.html', context)

     
        base_username = email.split('@')[0]
        username      = base_username
        counter       = 1
        while User.objects.filter(username=username).exists():
            username = f'{base_username}{counter}'
            counter += 1

      
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0]
        last_name  = name_parts[1] if len(name_parts) > 1 else ''

        user = User.objects.create_user(
            username   = username,
            email      = email,
            password   = password,
            first_name = first_name,
            last_name  = last_name,
        )

       
        distributor_group, _ = Group.objects.get_or_create(name='Distributor')
        user.groups.add(distributor_group)

      
        DistributorProfile.objects.create(user=user, phone=phone)

        messages.success(
            request,
            'Your distributor account has been created successfully. Please sign in.'
        )
        return redirect('distributor_login')

    return render(request, 'distributor/register.html')




def _mask_email(email):
    """Return a partially masked email for display, e.g. jo**@gmail.com."""
    if not email or '@' not in email:
        return email
    local, domain = email.rsplit('@', 1)
    if len(local) <= 2:
        masked_local = local[0] + '*'
    else:
        masked_local = local[:2] + '*' * (len(local) - 2)
    return f'{masked_local}@{domain}'


def _validate_phone(phone):
    """
    Phone number format validation: 7 to 15 digits, optional leading +.
    Returns error string or None.
    """
    if not phone or not re.match(r'^\+?\d{7,15}$', phone):
        return 'Enter a valid phone number (digits only, 7–15 characters).'
    return None



@login_required(login_url='distributor_login')
def distributor_profile(request):
    if not request.user.groups.filter(name='Distributor').exists():
        messages.error(request, 'Access denied. This page is for distributors only.')
        return redirect('distributor_login')

    profile, _ = DistributorProfile.objects.get_or_create(user=request.user)
    context = {
        'profile': profile,
    }
    return render(request, 'distributor/profile.html', context)


@login_required(login_url='distributor_login')
def edit_profile(request):
    if not request.user.groups.filter(name='Distributor').exists():
        messages.error(request, 'Access denied.')
        return redirect('distributor_login')

    profile, _ = DistributorProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email     = request.POST.get('email', '').strip().lower()
        phone     = request.POST.get('phone', '').strip()

        context = {
            'full_name_value': full_name,
            'email_value': email,
            'phone_value': phone,
        }

        if not full_name:
            messages.error(request, 'Full name is required.')
            return render(request, 'distributor/edit_profile.html', context)

        email_err = _validate_identifier(email)
        if email_err:
            messages.error(request, email_err)
            return render(request, 'distributor/edit_profile.html', context)


        if User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
            messages.error(request, 'This email address is already in use by another account.')
            return render(request, 'distributor/edit_profile.html', context)

        phone_err = _validate_phone(phone)
        if phone_err:
            messages.error(request, phone_err)
            return render(request, 'distributor/edit_profile.html', context)

        name_parts = full_name.split(' ', 1)
        request.user.first_name = name_parts[0]
        request.user.last_name  = name_parts[1] if len(name_parts) > 1 else ''
        request.user.email      = email
        request.user.save()

        profile.phone = phone
        profile.save()

        messages.success(request, 'Your profile details have been updated successfully.')
        return redirect('distributor_profile')

    full_name_initial = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
    context = {
        'full_name_value': full_name_initial,
        'email_value': request.user.email,
        'phone_value': profile.phone,
    }
    return render(request, 'distributor/edit_profile.html', context)


@login_required(login_url='distributor_login')
def customer_list(request):
    if not request.user.groups.filter(name='Distributor').exists():
        messages.error(request, 'Access denied.')
        return redirect('distributor_login')

    query = request.GET.get('q', '').strip()
    customers = Customer.objects.filter(distributor=request.user)
    if query:
        customers = customers.filter(
            Q(name__icontains=query) |
            Q(phone__icontains=query) |
            Q(email__icontains=query) |
            Q(address__icontains=query)
        )
    return render(request, 'distributor/customer_list.html', {
        'customers': customers,
        'search': query,
    })


@login_required(login_url='distributor_login')
def add_customer(request):
    if not request.user.groups.filter(name='Distributor').exists():
        messages.error(request, 'Access denied.')
        return redirect('distributor_login')

    if request.method == 'POST':
        name    = request.POST.get('name', '').strip()
        email   = request.POST.get('email', '').strip().lower()
        phone   = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()

        context = {
            'name_value': name,
            'email_value': email,
            'phone_value': phone,
            'address_value': address,
        }

        if not name:
            messages.error(request, 'Customer name is required.')
            return render(request, 'distributor/add_customer.html', context)

        if email:
            email_err = _validate_identifier(email)
            if email_err:
                messages.error(request, email_err)
                return render(request, 'distributor/add_customer.html', context)

        phone_err = _validate_phone(phone)
        if phone_err:
            messages.error(request, phone_err)
            return render(request, 'distributor/add_customer.html', context)

        Customer.objects.create(
            distributor=request.user,
            name=name,
            email=email if email else None,
            phone=phone,
            address=address if address else None
        )

        messages.success(request, f'Customer "{name}" added successfully.')
        return redirect('customer_list')

    return render(request, 'distributor/add_customer.html')


@login_required(login_url='distributor_login')
def edit_customer(request, customer_id):
    if not request.user.groups.filter(name='Distributor').exists():
        messages.error(request, 'Access denied.')
        return redirect('distributor_login')

    customer = get_object_or_404(Customer, id=customer_id, distributor=request.user)

    if request.method == 'POST':
        name    = request.POST.get('name', '').strip()
        email   = request.POST.get('email', '').strip().lower()
        phone   = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()

        context = {
            'customer': customer,
            'name_value': name,
            'email_value': email,
            'phone_value': phone,
            'address_value': address,
        }

        if not name:
            messages.error(request, 'Customer name is required.')
            return render(request, 'distributor/edit_customer.html', context)

        if email:
            email_err = _validate_identifier(email)
            if email_err:
                messages.error(request, email_err)
                return render(request, 'distributor/edit_customer.html', context)

        phone_err = _validate_phone(phone)
        if phone_err:
            messages.error(request, phone_err)
            return render(request, 'distributor/edit_customer.html', context)

        customer.name = name
        customer.email = email if email else None
        customer.phone = phone
        customer.address = address if address else None
        customer.save()

        messages.success(request, f'Customer "{name}" updated successfully.')
        return redirect('customer_list')

    context = {
        'customer': customer,
        'name_value': customer.name,
        'email_value': customer.email or '',
        'phone_value': customer.phone,
        'address_value': customer.address or '',
    }
    return render(request, 'distributor/edit_customer.html', context)


@login_required(login_url='distributor_login')
def delete_customer(request, customer_id):
    if not request.user.groups.filter(name='Distributor').exists():
        messages.error(request, 'Access denied.')
        return redirect('distributor_login')

    customer = get_object_or_404(Customer, id=customer_id, distributor=request.user)

    if request.method == 'POST':
        try:
            customer_name = customer.name
            customer.delete()
            messages.success(request, f'Customer "{customer_name}" deleted successfully.')
        except Exception:
            messages.error(request, 'An error occurred while deleting the customer.')
        return redirect('customer_list')

    return redirect('customer_list')




@login_required(login_url='distributor_login')
def product_list(request):
   
    is_distributor = request.user.groups.filter(name='Distributor').exists()
    if not (is_distributor or request.user.is_staff):
        messages.error(request, 'Access denied. You do not have permission to view products.')
        return redirect('distributor_login')

    query = request.GET.get('q', '').strip()
    if request.user.is_staff:
        products_qs = Product.objects.all()
    else:
        products_qs = Product.objects.filter(Q(distributor=request.user) | Q(distributor__isnull=True))

    if query:
        products_qs = products_qs.filter(
            Q(name__icontains=query) |
            Q(category__icontains=query) |
            Q(hsn_code__icontains=query)
        )

    products_qs = products_qs.order_by('name')

   
    paginator = Paginator(products_qs, 8)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    return render(request, 'distributor/product_list.html', {
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'search': query,
        'total_count': paginator.count,
    })


@login_required(login_url='distributor_login')
def add_product(request):
    
    is_distributor = request.user.groups.filter(name='Distributor').exists()
    if not (is_distributor or request.user.is_staff):
        messages.error(request, 'Access denied.')
        return redirect('distributor_login')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category = request.POST.get('category', '').strip()
        hsn_code = request.POST.get('hsn_code', '').strip()
        price_raw = request.POST.get('price', '').strip()
        stock_raw = request.POST.get('stock', '').strip()
        gst_rate_raw = request.POST.get('gst_rate', '').strip()
        tax_category = request.POST.get('tax_category', TAX_CATEGORY_TAXABLE).strip()
        cess_rate_raw = request.POST.get('cess_rate', '0').strip()
        price_includes_gst = request.POST.get('price_includes_gst') in ['true', 'on', '1', 'True']
        description = request.POST.get('description', '').strip()

        context = {
            'name_value': name,
            'category_value': category,
            'hsn_code_value': hsn_code,
            'price_value': price_raw,
            'stock_value': stock_raw,
            'gst_rate_value': gst_rate_raw,
            'tax_category_value': tax_category,
            'cess_rate_value': cess_rate_raw,
            'price_includes_gst_value': price_includes_gst,
            'description_value': description,
            'tax_categories': TAX_CATEGORY_CHOICES,
            'valid_gst_rates': [str(r) for r in VALID_GST_RATES],
        }


        if not name:
            messages.error(request, 'Product name is required.')
            return render(request, 'distributor/add_product.html', context)


        dup_query = Product.objects.filter(name__iexact=name)
        if not request.user.is_staff:
            dup_query = dup_query.filter(distributor=request.user)
        if dup_query.exists():
            messages.error(request, f'A product named "{name}" already exists in your inventory.')
            return render(request, 'distributor/add_product.html', context)


        if not category:
            messages.error(request, 'Product category is required.')
            return render(request, 'distributor/add_product.html', context)


        if not hsn_code:
            messages.error(request, 'HSN code is required.')
            return render(request, 'distributor/add_product.html', context)

        clean_hsn = re.sub(r'\s+', '', hsn_code)
        if not validate_hsn_code(clean_hsn):
            messages.error(request, 'Enter a valid HSN code (2 to 8 numeric digits).')
            return render(request, 'distributor/add_product.html', context)


        try:
            price = Decimal(price_raw)
            if price <= Decimal('0.00'):
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            messages.error(request, 'Price must be a valid number greater than zero.')
            return render(request, 'distributor/add_product.html', context)


        try:
            stock = int(stock_raw)
            if stock < 0:
                raise ValueError()
        except (ValueError, TypeError):
            messages.error(request, 'Stock quantity must be a non-negative whole number (0 or greater).')
            return render(request, 'distributor/add_product.html', context)


        valid_cat_keys = [c[0] for c in TAX_CATEGORY_CHOICES]
        if tax_category not in valid_cat_keys:
            messages.error(request, 'Invalid tax category selected.')
            return render(request, 'distributor/add_product.html', context)


        try:
            cess_rate = Decimal(cess_rate_raw or '0')
            if cess_rate < Decimal('0.00'):
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            messages.error(request, 'Compensation cess rate must be 0 or a positive percentage.')
            return render(request, 'distributor/add_product.html', context)

        if tax_category in ZERO_TAX_CATEGORIES:
            gst_rate = Decimal('0.00')
            cess_rate = Decimal('0.00')
        else:
            try:
                gst_rate = Decimal(gst_rate_raw or '0')
                if gst_rate not in VALID_GST_RATES:
                    messages.error(request, f'GST rate {gst_rate}% is not a valid Indian GST slab (0%, 0.25%, 3%, 5%, 12%, 18%, 28%).')
                    return render(request, 'distributor/add_product.html', context)
            except (InvalidOperation, ValueError, TypeError):
                messages.error(request, 'Enter a valid GST rate percentage.')
                return render(request, 'distributor/add_product.html', context)


        try:
            product = Product.objects.create(
                distributor=request.user,
                name=name,
                category=category,
                hsn_code=clean_hsn,
                price=price,
                stock=stock,
                gst_rate=gst_rate,
                tax_category=tax_category,
                cess_rate=cess_rate,
                price_includes_gst=price_includes_gst,
                description=description,
            )
        except Exception as e:
            messages.error(request, f'Error saving product: {e}')
            return render(request, 'distributor/add_product.html', context)

        messages.success(request, f'Product "{name}" added successfully [HSN: {clean_hsn}, GST: {gst_rate}%].')
        return redirect('product_list')

    context = {
        'tax_categories': TAX_CATEGORY_CHOICES,
        'valid_gst_rates': [str(r) for r in VALID_GST_RATES],
        'gst_rate_value': '18.00',
        'stock_value': '0',
    }
    return render(request, 'distributor/add_product.html', context)


@login_required(login_url='distributor_login')
def edit_product(request, product_id):
    is_distributor = request.user.groups.filter(name='Distributor').exists()
    if not (is_distributor or request.user.is_staff):
        messages.error(request, 'Access denied.')
        return redirect('distributor_login')

    if request.user.is_staff:
        product = get_object_or_404(Product, id=product_id)
    else:
        product = get_object_or_404(Product, id=product_id, distributor=request.user)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category = request.POST.get('category', '').strip()
        hsn_code = request.POST.get('hsn_code', '').strip()
        price_raw = request.POST.get('price', '').strip()
        stock_raw = request.POST.get('stock', '').strip()
        gst_rate_raw = request.POST.get('gst_rate', '').strip()
        tax_category = request.POST.get('tax_category', TAX_CATEGORY_TAXABLE).strip()
        cess_rate_raw = request.POST.get('cess_rate', '0').strip()
        price_includes_gst = request.POST.get('price_includes_gst') in ['true', 'on', '1', 'True']
        description = request.POST.get('description', '').strip()

        context = {
            'product': product,
            'name_value': name,
            'category_value': category,
            'hsn_code_value': hsn_code,
            'price_value': price_raw,
            'stock_value': stock_raw,
            'gst_rate_value': gst_rate_raw,
            'tax_category_value': tax_category,
            'cess_rate_value': cess_rate_raw,
            'price_includes_gst_value': price_includes_gst,
            'description_value': description,
            'tax_categories': TAX_CATEGORY_CHOICES,
            'valid_gst_rates': [str(r) for r in VALID_GST_RATES],
        }

        if not name:
            messages.error(request, 'Product name is required.')
            return render(request, 'distributor/edit_product.html', context)

        dup_query = Product.objects.filter(name__iexact=name).exclude(pk=product.pk)
        if not request.user.is_staff:
            dup_query = dup_query.filter(distributor=request.user)
        if dup_query.exists():
            messages.error(request, f'Another product named "{name}" already exists.')
            return render(request, 'distributor/edit_product.html', context)

        if not category:
            messages.error(request, 'Category is required.')
            return render(request, 'distributor/edit_product.html', context)

        clean_hsn = re.sub(r'\s+', '', hsn_code)
        if not validate_hsn_code(clean_hsn):
            messages.error(request, 'Enter a valid HSN code (2 to 8 numeric digits).')
            return render(request, 'distributor/edit_product.html', context)

        try:
            price = Decimal(price_raw)
            if price <= Decimal('0.00'):
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            messages.error(request, 'Price must be greater than zero.')
            return render(request, 'distributor/edit_product.html', context)

        try:
            stock = int(stock_raw)
            if stock < 0:
                raise ValueError()
        except (ValueError, TypeError):
            messages.error(request, 'Stock cannot be negative.')
            return render(request, 'distributor/edit_product.html', context)

        try:
            cess_rate = Decimal(cess_rate_raw or '0')
            if cess_rate < Decimal('0.00'):
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            messages.error(request, 'Cess rate must be 0 or positive.')
            return render(request, 'distributor/edit_product.html', context)

        valid_cat_keys = [c[0] for c in TAX_CATEGORY_CHOICES]
        if tax_category not in valid_cat_keys:
            messages.error(request, 'Invalid tax category selected.')
            return render(request, 'distributor/edit_product.html', context)

        if tax_category in ZERO_TAX_CATEGORIES:
            gst_rate = Decimal('0.00')
            cess_rate = Decimal('0.00')
        else:
            try:
                gst_rate = Decimal(gst_rate_raw or '0')
                if gst_rate not in VALID_GST_RATES:
                    messages.error(request, f'GST rate {gst_rate}% is not a valid slab.')
                    return render(request, 'distributor/edit_product.html', context)
            except (InvalidOperation, ValueError, TypeError):
                messages.error(request, 'Invalid GST rate.')
                return render(request, 'distributor/edit_product.html', context)

        product.name = name
        product.category = category
        product.hsn_code = clean_hsn
        product.price = price
        product.stock = stock
        product.gst_rate = gst_rate
        product.tax_category = tax_category
        product.cess_rate = cess_rate
        product.price_includes_gst = price_includes_gst
        product.description = description
        try:
            product.full_clean()
            product.save()
        except ValidationError as exc:
            for field_errors in exc.message_dict.values():
                for error in field_errors:
                    messages.error(request, error)
            return render(request, 'distributor/edit_product.html', context)

        messages.success(request, f'Product "{name}" updated successfully.')
        return redirect('product_list')

    context = {
        'product': product,
        'name_value': product.name,
        'category_value': product.category,
        'hsn_code_value': product.hsn_code,
        'price_value': str(product.price),
        'stock_value': str(product.stock),
        'gst_rate_value': str(product.gst_rate),
        'tax_category_value': product.tax_category,
        'cess_rate_value': str(product.cess_rate),
        'price_includes_gst_value': product.price_includes_gst,
        'description_value': product.description or '',
        'tax_categories': TAX_CATEGORY_CHOICES,
        'valid_gst_rates': [str(r) for r in VALID_GST_RATES],
    }
    return render(request, 'distributor/edit_product.html', context)


@login_required(login_url='distributor_login')
@require_POST
def delete_product(request, product_id):
    is_distributor = request.user.groups.filter(name='Distributor').exists()
    if not (is_distributor or request.user.is_staff):
        messages.error(request, 'Access denied.')
        return redirect('distributor_login')

    if request.user.is_staff:
        product = get_object_or_404(Product, id=product_id)
    else:
        product = get_object_or_404(Product, id=product_id, distributor=request.user)

    product_name = product.name
    product.delete()
    messages.success(request, f'Product "{product_name}" removed from inventory.')
    return redirect('product_list')


def api_hsn_lookup(request):
    hsn = request.GET.get('hsn', '').strip()
    data = lookup_hsn(hsn)
    if data:
        return JsonResponse({
            'found': True,
            'is_verified': True,
            'hsn_code': data['hsn_code'],
            'description': data['description'],
            'category': data['category'],
            'gst_rate': str(data['gst_rate']),
            'tax_category': data['tax_category'],
            'cess_rate': str(data['cess_rate']),
            'notification': data['notification'],
        })
    return JsonResponse({
        'found': False,
        'is_verified': False,
        'message': 'HSN code not found in verified official catalogue. Please specify rate manually as per applicable notifications.',
    })


@login_required(login_url='distributor_login')
def api_save_invoice(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required.'}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    customer_id = data.get('customer_id')
    customer_name = data.get('customer_name', '').strip()
    place_of_supply = data.get('place_of_supply', 'Intra-State').strip()
    is_interstate = bool(data.get('is_interstate', False))
    notes = data.get('notes', '').strip()
    due_date = data.get('due_date') or None
    items_data = data.get('items', [])

    if not items_data:
        return JsonResponse({'error': 'Invoice must contain at least one line item.'}, status=400)

    try:
        with transaction.atomic():
            customer = None
            if customer_id:
                customer = Customer.objects.filter(
                    id=customer_id,
                    distributor=request.user,
                ).first()
                if customer is None:
                    return JsonResponse({'error': 'Customer not found.'}, status=400)
                customer_name = customer.name

            customer_name = customer_name or 'Cash Sale'
            total_taxable = Decimal('0.00')
            total_cgst = Decimal('0.00')
            total_sgst = Decimal('0.00')
            total_igst = Decimal('0.00')
            total_cess = Decimal('0.00')
            processed_items = []

            for item in items_data:
                try:
                    prod_id = item.get('product_id')
                    qty = int(item.get('qty', 1))
                    unit_price = Decimal(str(item.get('rate', 0)))
                    gst_rate = Decimal(str(item.get('gst_rate', 0)))
                    cess_rate = Decimal(str(item.get('cess_rate', 0)))
                except (InvalidOperation, TypeError, ValueError):
                    return JsonResponse({'error': 'Each item must have valid quantity and price values.'}, status=400)

                if qty < 1 or unit_price <= 0 or gst_rate < 0 or cess_rate < 0:
                    return JsonResponse({'error': 'Quantity must be positive and prices and tax rates cannot be negative.'}, status=400)

                product_obj = None
                if prod_id:
                    product_obj = Product.objects.select_for_update().filter(
                        Q(id=prod_id) & (Q(distributor=request.user) | Q(distributor__isnull=True))
                    ).first()
                    if product_obj is None:
                        return JsonResponse({'error': 'Product not found or not accessible.'}, status=400)
                    if product_obj.stock < qty:
                        return JsonResponse({'error': f'Insufficient stock for {product_obj.name}.'}, status=400)
                    name = product_obj.name
                    hsn = product_obj.hsn_code
                    unit_price = product_obj.price
                    gst_rate = product_obj.gst_rate
                    cess_rate = product_obj.cess_rate
                    tax_category = product_obj.tax_category
                    price_includes_gst = product_obj.price_includes_gst
                else:
                    name = str(item.get('name', '')).strip()
                    hsn = str(item.get('hsn_code', '')).strip()
                    tax_category = item.get('tax_category', TAX_CATEGORY_TAXABLE)
                    price_includes_gst = bool(item.get('price_includes_gst', False))
                    if not name:
                        return JsonResponse({'error': 'Every invoice item needs a product name.'}, status=400)

                breakdown = calculate_gst_breakdown(
                    price=unit_price,
                    quantity=Decimal(str(qty)),
                    gst_rate=gst_rate,
                    cess_rate=cess_rate,
                    tax_category=tax_category,
                    price_includes_gst=price_includes_gst,
                    is_interstate=is_interstate,
                )
                total_taxable += breakdown['taxable_value']
                total_cgst += breakdown['cgst_amount']
                total_sgst += breakdown['sgst_amount']
                total_igst += breakdown['igst_amount']
                total_cess += breakdown['cess_amount']
                processed_items.append({
                    'product': product_obj,
                    'name': name,
                    'hsn': hsn,
                    'qty': qty,
                    'unit_price': unit_price,
                    'tax_category': tax_category,
                    'gst_rate': gst_rate,
                    'cess_rate': cess_rate,
                    'price_includes_gst': price_includes_gst,
                    'breakdown': breakdown,
                })

            total_tax = total_cgst + total_sgst + total_igst + total_cess
            unrounded_total = total_taxable + total_tax
            rounded_grand_total = round_to_rupee(unrounded_total)
            round_off = rounded_grand_total - unrounded_total
            invoice_number = f"INV-{timezone.now():%Y%m}-{uuid4().hex[:8].upper()}"
            invoice = Invoice.objects.create(
                distributor=request.user,
                customer=customer,
                customer_name=customer_name,
                invoice_number=invoice_number,
                invoice_date=timezone.now().date(),
                due_date=due_date,
                place_of_supply=place_of_supply,
                is_interstate=is_interstate,
                taxable_amount=round_currency(total_taxable),
                cgst_amount=round_currency(total_cgst),
                sgst_amount=round_currency(total_sgst),
                igst_amount=round_currency(total_igst),
                cess_amount=round_currency(total_cess),
                total_tax=round_currency(total_tax),
                round_off=round_currency(round_off),
                grand_total=rounded_grand_total,
                status='pending',
                notes=notes,
            )

            for pi in processed_items:
                b = pi['breakdown']
                if pi['product'] is not None:
                    pi['product'].stock -= pi['qty']
                    pi['product'].save(update_fields=['stock', 'updated_at'])
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=pi['product'],
                    product_name=pi['name'],
                    hsn_code=pi['hsn'],
                    quantity=pi['qty'],
                    unit_price=pi['unit_price'],
                    tax_category=pi['tax_category'],
                    gst_rate=pi['gst_rate'],
                    cess_rate=pi['cess_rate'],
                    price_includes_gst=pi['price_includes_gst'],
                    taxable_value=b['taxable_value'],
                    cgst_amount=b['cgst_amount'],
                    sgst_amount=b['sgst_amount'],
                    igst_amount=b['igst_amount'],
                    cess_amount=b['cess_amount'],
                    total_amount=b['total_amount'],
                )
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({'error': 'Invoice contains invalid numeric or tax values.'}, status=400)

    return JsonResponse({
        'success': True,
        'invoice_number': invoice.invoice_number,
        'grand_total': str(invoice.grand_total),
        'taxable_amount': str(invoice.taxable_amount),
        'total_tax': str(invoice.total_tax),
        'message': f'Invoice {invoice.invoice_number} generated successfully.',
    })
