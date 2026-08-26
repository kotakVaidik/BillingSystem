(function () {
  'use strict';

  var form            = document.getElementById('resetPasswordForm');
  var newPwInput      = document.getElementById('id_new_password');
  var confirmPwInput  = document.getElementById('id_confirm_password');
  var newPwError      = document.getElementById('error_new_password');
  var confirmPwError  = document.getElementById('error_confirm_password');

  var PW_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{8,}$/;

  function showError(input, errorEl, message) {
    input.classList.add('is-error');
    errorEl.querySelector('span').textContent = message;
    errorEl.classList.add('is-visible');
  }

  function clearError(input, errorEl) {
    input.classList.remove('is-error');
    errorEl.classList.remove('is-visible');
  }

  if (newPwInput) {
    newPwInput.addEventListener('input', function () {
      clearError(newPwInput, newPwError);
      if (confirmPwInput.value) {
        clearError(confirmPwInput, confirmPwError);
      }
    });
  }

  if (confirmPwInput) {
    confirmPwInput.addEventListener('input', function () {
      clearError(confirmPwInput, confirmPwError);
    });
  }

  if (form) {
    form.addEventListener('submit', function (e) {
      var valid = true;
      var newVal     = newPwInput.value;
      var confirmVal = confirmPwInput.value;

      if (!newVal) {
        showError(newPwInput, newPwError, 'New password is required.');
        valid = false;
      } else if (newVal.length < 8) {
        showError(newPwInput, newPwError, 'Password must be at least 8 characters long.');
        valid = false;
      } else if (!PW_REGEX.test(newVal)) {
        showError(newPwInput, newPwError, 'Password must include uppercase, lowercase, a number, and a special character.');
        valid = false;
      } else {
        clearError(newPwInput, newPwError);
      }

      if (!confirmVal) {
        showError(confirmPwInput, confirmPwError, 'Please confirm your new password.');
        valid = false;
      } else if (newVal && confirmVal !== newVal) {
        showError(confirmPwInput, confirmPwError, 'Passwords do not match.');
        valid = false;
      } else if (valid) {
        clearError(confirmPwInput, confirmPwError);
      }

      if (!valid) {
        e.preventDefault();
      }
    });
  }

})();
