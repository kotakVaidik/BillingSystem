/**
 * Billing System — Shared Login Page JavaScript
 * Handles: password visibility toggle, client-side validation
 */

(function () {
  'use strict';

  /* ----------------------------------------------------------------
     Password Visibility Toggle
  ---------------------------------------------------------------- */
  const EYE_OPEN_SVG = `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>`;

  const EYE_CLOSED_SVG = `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
      <line x1="1" y1="1" x2="23" y2="23"/>
    </svg>`;

  document.querySelectorAll('.password-toggle').forEach(function (btn) {
    var inputId = btn.getAttribute('data-target');
    var input = document.getElementById(inputId);
    if (!input) return;

    btn.innerHTML = EYE_OPEN_SVG;
    btn.setAttribute('aria-label', 'Show password');
    btn.setAttribute('type', 'button');

    btn.addEventListener('click', function () {
      var isPassword = input.type === 'password';
      input.type = isPassword ? 'text' : 'password';
      btn.innerHTML = isPassword ? EYE_CLOSED_SVG : EYE_OPEN_SVG;
      btn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
    });
  });

  /* ----------------------------------------------------------------
     Client-side Validation
  ---------------------------------------------------------------- */
  var form = document.getElementById('loginForm');
  if (!form) return;

  /**
   * Show a field-level error message.
   * @param {HTMLElement} input
   * @param {HTMLElement} errorEl
   * @param {string} message
   */
  function showError(input, errorEl, message) {
    input.classList.add('is-error');
    errorEl.querySelector('span') && (errorEl.querySelector('span').textContent = message);
    errorEl.classList.add('is-visible');
  }

  /**
   * Clear a field-level error message.
   * @param {HTMLElement} input
   * @param {HTMLElement} errorEl
   */
  function clearError(input, errorEl) {
    input.classList.remove('is-error');
    errorEl.classList.remove('is-visible');
  }

  var emailInput    = document.getElementById('id_email');
  var passwordInput = document.getElementById('id_password');
  var emailError    = document.getElementById('error_email');
  var passwordError = document.getElementById('error_password');

  /* Clear errors on input */
  if (emailInput && emailError) {
    emailInput.addEventListener('input', function () {
      clearError(emailInput, emailError);
    });
  }

  if (passwordInput && passwordError) {
    passwordInput.addEventListener('input', function () {
      clearError(passwordInput, passwordError);
    });
  }

  /* Validate on submit */
  form.addEventListener('submit', function (e) {
    var valid = true;
    var EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (emailInput && emailError) {
      var emailVal = emailInput.value.trim();
      if (!emailVal) {
        showError(emailInput, emailError, 'Email address is required.');
        valid = false;
      } else if (!EMAIL_REGEX.test(emailVal)) {
        showError(emailInput, emailError, 'Please enter a valid email address.');
        valid = false;
      } else {
        clearError(emailInput, emailError);
      }
    }

    if (passwordInput && passwordError) {
      var pwVal = passwordInput.value;
      if (!pwVal) {
        showError(passwordInput, passwordError, 'Password is required.');
        valid = false;
      } else {
        clearError(passwordInput, passwordError);
      }
    }

    if (!valid) {
      e.preventDefault();
    }
  });

})();
