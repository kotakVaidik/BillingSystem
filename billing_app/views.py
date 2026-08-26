"""
billing_app/views.py

Authentication views for:
  - Admin login / logout
  - Distributor login
  - Distributor forgot-password → OTP → reset-password flow
  - Distributor registration
"""

import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import DistributorProfile, OTPToken

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EMAIL_DOMAINS = {'gmail.com', 'outlook.com'}

# Session keys
SESSION_RESET_EMAIL    = 'pwd_reset_email'       # email under reset
SESSION_OTP_VERIFIED   = 'otp_verified'          # True once OTP passes


# ---------------------------------------------------------------------------
# Shared validators
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Portal Landing View
# ---------------------------------------------------------------------------

def portal_home(request):
    """Portal landing page for choosing between Admin and Distributor workspaces."""
    return render(request, 'portal_home.html')


# ---------------------------------------------------------------------------
# Admin views
# ---------------------------------------------------------------------------

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

        email_error = _validate_identifier(identifier)
        if email_error:
            messages.error(request, email_error)
            return render(request, 'admin/login.html', {'email_value': identifier})

        password_error = _validate_password(password)
        if password_error:
            messages.error(request, password_error)
            return render(request, 'admin/login.html', {'email_value': identifier})

        matched  = _get_user_by_identifier(identifier)
        username = matched.username if matched else identifier
        user     = authenticate(request, username=username, password=password)

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


# ---------------------------------------------------------------------------
# Distributor login / logout
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Distributor dashboards
# ---------------------------------------------------------------------------

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
    customer_count = Customer.objects.filter(distributor=request.user).count()
    return render(request, 'distributor/dashboard.html', {'customer_count': customer_count})


# ---------------------------------------------------------------------------
# Distributor forgot-password → OTP → reset flow
# ---------------------------------------------------------------------------

def distributor_forgot_password(request):
    """
    Step 1: User enters their registered email.
    Generates an OTP, stores it in DB, sends it by email,
    and stores the email in the session before redirecting to verify_otp.
    """
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()

        # Basic email format check
        if not email or '@' not in email:
            messages.error(request, 'Please enter a valid email address.')
            return render(request, 'distributor/forgot_password.html', {'email_value': email})

        # Always show the same "success" message to prevent user enumeration.
        # Only actually send if the user exists in the Distributor group.
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
                # Even if email fails in dev (console backend may raise), continue.
                pass

        # Store email in session (used in subsequent steps)
        request.session[SESSION_RESET_EMAIL]  = email
        request.session[SESSION_OTP_VERIFIED] = False

        messages.success(
            request,
            'If this email is registered, an OTP has been sent. Check your inbox.'
        )
        return redirect('distributor_verify_otp')

    return render(request, 'distributor/forgot_password.html')


def distributor_verify_otp(request):
    """
    Step 2: User enters the 6-digit OTP received by email.
    On success, sets the session verified flag and redirects to reset_password.
    """
    email = request.session.get(SESSION_RESET_EMAIL)

    if not email:
        # Session lost — send user back to start
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

        # Get the most recent unused OTP for this user
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

        # Mark OTP as used and set session flag
        token.is_used = True
        token.save(update_fields=['is_used'])
        request.session[SESSION_OTP_VERIFIED] = True

        messages.success(request, 'OTP verified successfully. Please set your new password.')
        return redirect('distributor_reset_password')

    return render(request, 'distributor/verify_otp.html', {'masked_email': _mask_email(email)})


def distributor_resend_otp(request):
    """
    Resend: Invalidates all existing OTPs for the user and sends a fresh one.
    Only responds to POST to prevent CSRF/GET resend abuse.
    """
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
    """
    Step 3: User sets a new password.
    Requires the session OTP verified flag to be True.
    """
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

        # Clean up session keys
        request.session.pop(SESSION_RESET_EMAIL, None)
        request.session.pop(SESSION_OTP_VERIFIED, None)

        messages.success(request, 'Your password has been reset successfully. Please sign in.')
        return redirect('distributor_login')

    return render(request, 'distributor/reset_password.html')


# ---------------------------------------------------------------------------
# Distributor Registration
# ---------------------------------------------------------------------------

def distributor_register(request):
    """
    Distributor self-registration.
    Creates a new User, adds them to the 'Distributor' group, and saves the phone number
    in DistributorProfile.
    """
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

        # --- Required field checks ---
        if not full_name or not email or not phone or not password or not confirm_password:
            messages.error(request, 'All fields are required.')
            return render(request, 'distributor/register.html', context)

        # --- Email domain validation ---
        email_error = _validate_identifier(email)
        if email_error:
            messages.error(request, email_error)
            return render(request, 'distributor/register.html', context)

        # --- Duplicate email check ---
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'An account with this email address already exists.')
            return render(request, 'distributor/register.html', context)

        # --- Phone format check (7–15 digits, optional leading +) ---
        if not re.match(r'^\+?\d{7,15}$', phone):
            messages.error(request, 'Enter a valid phone number (digits only, 7–15 characters).')
            return render(request, 'distributor/register.html', context)

        # --- Password strength ---
        pw_error = _validate_password(password)
        if pw_error:
            messages.error(request, pw_error)
            return render(request, 'distributor/register.html', context)

        # --- Password match ---
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'distributor/register.html', context)

        # --- Create user ---
        # Use email local-part as username; make unique if needed
        base_username = email.split('@')[0]
        username      = base_username
        counter       = 1
        while User.objects.filter(username=username).exists():
            username = f'{base_username}{counter}'
            counter += 1

        # Split full name into first / last
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

        # Add to Distributor group (create group if it doesn't exist yet)
        distributor_group, _ = Group.objects.get_or_create(name='Distributor')
        user.groups.add(distributor_group)

        # Save phone in profile
        DistributorProfile.objects.create(user=user, phone=phone)

        messages.success(
            request,
            'Your distributor account has been created successfully. Please sign in.'
        )
        return redirect('distributor_login')

    return render(request, 'distributor/register.html')


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Distributor Profile & Customer Management
# ---------------------------------------------------------------------------

@login_required(login_url='distributor_login')
def distributor_profile(request):
    """
    Task 6: Display current distributor's profile.
    """
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
    """
    Task 1: Update profile information for the logged-in distributor.
    """
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

        # Check duplicate email excluding current user
        if User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
            messages.error(request, 'This email address is already in use by another account.')
            return render(request, 'distributor/edit_profile.html', context)

        phone_err = _validate_phone(phone)
        if phone_err:
            messages.error(request, phone_err)
            return render(request, 'distributor/edit_profile.html', context)

        # Update User
        name_parts = full_name.split(' ', 1)
        request.user.first_name = name_parts[0]
        request.user.last_name  = name_parts[1] if len(name_parts) > 1 else ''
        request.user.email      = email
        request.user.save()

        # Update Profile
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
    """
    Task 3: List customers created by the logged-in distributor.
    """
    if not request.user.groups.filter(name='Distributor').exists():
        messages.error(request, 'Access denied.')
        return redirect('distributor_login')

    customers = Customer.objects.filter(distributor=request.user)
    return render(request, 'distributor/customer_list.html', {'customers': customers})


@login_required(login_url='distributor_login')
def add_customer(request):
    """
    Task 3: Add new customer associated with the logged-in distributor.
    """
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

