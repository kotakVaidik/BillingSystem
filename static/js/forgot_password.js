(function () {
  'use strict';

  var form = document.getElementById('forgotPasswordForm');
  if (!form) return;

  var emailInput = document.getElementById('id_email');
  var emailError = document.getElementById('error_email');
  var EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function showError(input, errorEl, message) {
    input.classList.add('is-error');
    errorEl.querySelector('span').textContent = message;
    errorEl.classList.add('is-visible');
  }

  function clearError(input, errorEl) {
    input.classList.remove('is-error');
    errorEl.classList.remove('is-visible');
  }

  emailInput.addEventListener('input', function () {
    clearError(emailInput, emailError);
  });

  form.addEventListener('submit', function (e) {
    var val = emailInput.value.trim();
    emailInput.value = val;

    if (!val) {
      showError(emailInput, emailError, 'Email address is required.');
      e.preventDefault();
      return;
    }

    if (!EMAIL_REGEX.test(val)) {
      showError(emailInput, emailError, 'Please enter a valid email address.');
      e.preventDefault();
      return;
    }

    clearError(emailInput, emailError);
  });

})();
