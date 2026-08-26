/**
 * Billing System — Distributor Registration Page JavaScript
 * Handles: password visibility toggle (via login.js), client-side field validation
 */

(function () {
  'use strict';

  var form             = document.getElementById('registerForm');
  if (!form) return;

  /* ----------------------------------------------------------------
     Field references
  ---------------------------------------------------------------- */
  var fullNameInput    = document.getElementById('id_full_name');
  var emailInput       = document.getElementById('id_email');
  var phoneInput       = document.getElementById('id_phone');
  var passwordInput    = document.getElementById('id_password');
  var confirmPwInput   = document.getElementById('id_confirm_password');

  var fullNameError    = document.getElementById('error_full_name');
  var emailError       = document.getElementById('error_email');
  var phoneError       = document.getElementById('error_phone');
  var passwordError    = document.getElementById('error_password');
  var confirmPwError   = document.getElementById('error_confirm_password');

  /* ----------------------------------------------------------------
     Regex patterns
  ---------------------------------------------------------------- */
  var EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  var PHONE_REGEX = /^\+?\d{7,15}$/;
  var PW_REGEX    = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{8,}$/;

  /* ----------------------------------------------------------------
     Helpers: show / clear field-level error
  ---------------------------------------------------------------- */
  function showError(input, errorEl, message) {
    input.classList.add('is-error');
    var span = errorEl.querySelector('span');
    if (span) span.textContent = message;
    errorEl.classList.add('is-visible');
  }

  function clearError(input, errorEl) {
    input.classList.remove('is-error');
    errorEl.classList.remove('is-visible');
  }

  /* ----------------------------------------------------------------
     Clear errors on input (live feedback)
  ---------------------------------------------------------------- */
  var fields = [
    [fullNameInput, fullNameError],
    [emailInput,    emailError],
    [phoneInput,    phoneError],
    [passwordInput, passwordError],
    [confirmPwInput, confirmPwError],
  ];

  fields.forEach(function (pair) {
    var input   = pair[0];
    var errorEl = pair[1];
    if (input && errorEl) {
      input.addEventListener('input', function () {
        clearError(input, errorEl);
      });
    }
  });

  /* ----------------------------------------------------------------
     Phone: strip non-digits except leading +
  ---------------------------------------------------------------- */
  if (phoneInput) {
    phoneInput.addEventListener('input', function () {
      // Allow only digits and a leading +
      var val = this.value;
      if (val.startsWith('+')) {
        this.value = '+' + val.slice(1).replace(/[^0-9]/g, '').slice(0, 14);
      } else {
        this.value = val.replace(/[^0-9]/g, '').slice(0, 15);
      }
    });
  }

  /* ----------------------------------------------------------------
     Form submit validation
  ---------------------------------------------------------------- */
  form.addEventListener('submit', function (e) {
    var valid = true;

    // --- Full Name ---
    var nameVal = fullNameInput ? fullNameInput.value.trim() : '';
    if (!nameVal) {
      showError(fullNameInput, fullNameError, 'Full name is required.');
      valid = false;
    } else if (nameVal.length < 2) {
      showError(fullNameInput, fullNameError, 'Please enter your full name.');
      valid = false;
    } else {
      clearError(fullNameInput, fullNameError);
    }

    // --- Email ---
    var emailVal = emailInput ? emailInput.value.trim() : '';
    if (!emailVal) {
      showError(emailInput, emailError, 'Email address is required.');
      valid = false;
    } else if (!EMAIL_REGEX.test(emailVal)) {
      showError(emailInput, emailError, 'Please enter a valid email address.');
      valid = false;
    } else {
      clearError(emailInput, emailError);
    }

    // --- Phone ---
    var phoneVal = phoneInput ? phoneInput.value.trim() : '';
    if (!phoneVal) {
      showError(phoneInput, phoneError, 'Phone number is required.');
      valid = false;
    } else if (!PHONE_REGEX.test(phoneVal)) {
      showError(phoneInput, phoneError, 'Enter a valid phone number (digits only, 7–15 characters).');
      valid = false;
    } else {
      clearError(phoneInput, phoneError);
    }

    // --- Password ---
    var pwVal = passwordInput ? passwordInput.value : '';
    if (!pwVal) {
      showError(passwordInput, passwordError, 'Password is required.');
      valid = false;
    } else if (pwVal.length < 8) {
      showError(passwordInput, passwordError, 'Password must be at least 8 characters long.');
      valid = false;
    } else if (!PW_REGEX.test(pwVal)) {
      showError(passwordInput, passwordError, 'Password must include uppercase, lowercase, a number, and a special character.');
      valid = false;
    } else {
      clearError(passwordInput, passwordError);
    }

    // --- Confirm Password ---
    var confirmVal = confirmPwInput ? confirmPwInput.value : '';
    if (!confirmVal) {
      showError(confirmPwInput, confirmPwError, 'Please confirm your password.');
      valid = false;
    } else if (pwVal && confirmVal !== pwVal) {
      showError(confirmPwInput, confirmPwError, 'Passwords do not match.');
      valid = false;
    } else {
      clearError(confirmPwInput, confirmPwError);
    }

    if (!valid) {
      e.preventDefault();
      // Scroll to first error
      var firstError = form.querySelector('.field-input.is-error');
      if (firstError) {
        firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
        firstError.focus();
      }
    }
  });

})();
