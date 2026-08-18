# Advance Billing System with QR

An advanced billing system application built with Django for internship project setup.

## Project Structure

```
BillingSystem/
├── BillingSystem/         # Django project configuration
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── billing_app/           # Main Django application
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── tests.py
│   └── views.py
├── templates/             # HTML Templates
│   ├── admin/
│   │   └── login.html
│   └── distributor/
│       └── login.html
├── static/                # Static assets
│   ├── css/
│   ├── js/
│   └── images/
├── media/                 # User-uploaded files
├── venv/                  # Python Virtual Environment
├── manage.py
├── db.sqlite3
├── requirements.txt
└── README.md
```

## Setup & Running

1. Activate virtual environment:
   `venv\Scripts\activate`

2. Run system checks:
   `python manage.py check`

3. Apply database migrations:
   `python manage.py migrate`

4. Start development server:
   `python manage.py runserver`
