(function () {
  'use strict';

  var form    = document.getElementById('verifyOtpForm');
  var otpInput = document.getElementById('id_otp');
  var otpError = document.getElementById('error_otp');
  var resendBtn = document.getElementById('btn-resend-otp');
  var countdown = document.getElementById('resendCountdown');

  var OTP_REGEX = /^\d{6}$/;
  var COOLDOWN_SECONDS = 60;
  var cooldownTimer = null;

  function showError(input, errorEl, message) {
    input.classList.add('is-error');
    errorEl.querySelector('span').textContent = message;
    errorEl.classList.add('is-visible');
  }

  function clearError(input, errorEl) {
    input.classList.remove('is-error');
    errorEl.classList.remove('is-visible');
  }

  if (otpInput) {
    otpInput.addEventListener('input', function () {
      this.value = this.value.replace(/[^0-9]/g, '').slice(0, 6);
      clearError(otpInput, otpError);
    });

    otpInput.addEventListener('keydown', function (e) {
      var allowed = ['Backspace', 'Delete', 'Tab', 'ArrowLeft', 'ArrowRight', 'Home', 'End'];
      if (allowed.indexOf(e.key) !== -1) return;
      if (e.ctrlKey || e.metaKey) return;
      if (!/^\d$/.test(e.key)) {
        e.preventDefault();
      }
    });
  }

  if (form) {
    form.addEventListener('submit', function (e) {
      var val = otpInput.value.trim();

      if (!val) {
        showError(otpInput, otpError, 'OTP is required.');
        e.preventDefault();
        return;
      }

      if (!OTP_REGEX.test(val)) {
        showError(otpInput, otpError, 'OTP must be exactly 6 digits.');
        e.preventDefault();
        return;
      }

      clearError(otpInput, otpError);
    });
  }

  function startCooldown() {
    var remaining = COOLDOWN_SECONDS;
    resendBtn.disabled = true;
    resendBtn.classList.add('resend-btn--disabled');
    countdown.hidden = false;
    countdown.textContent = 'Resend available in ' + remaining + 's';

    cooldownTimer = setInterval(function () {
      remaining -= 1;
      countdown.textContent = 'Resend available in ' + remaining + 's';
      if (remaining <= 0) {
        clearInterval(cooldownTimer);
        resendBtn.disabled = false;
        resendBtn.classList.remove('resend-btn--disabled');
        countdown.hidden = true;
      }
    }, 1000);
  }

  if (resendBtn) {
    var resendForm = document.getElementById('resendOtpForm');
    resendBtn.addEventListener('click', function (e) {
      if (resendBtn.disabled) {
        e.preventDefault();
        return;
      }
      startCooldown();
    });
  }

})();
