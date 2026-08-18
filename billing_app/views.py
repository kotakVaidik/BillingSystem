import re

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required

ALLOWED_EMAIL_DOMAINS = {'gmail.com', 'outlook.com'}


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

        matched = _get_user_by_identifier(identifier)
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

        matched = _get_user_by_identifier(identifier)
        username = matched.username if matched else identifier
        user = authenticate(request, username=username, password=password)

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
    return render(request, 'distributor/dashboard.html')


def admin_password_reset(request):
    return render(request, 'admin/login.html')


def distributor_password_reset(request):
    return render(request, 'distributor/login.html')
