/**
 * forgot-password.js
 * Logic for requesting a password reset PIN.
 */

function handleForgot(e) {
    if (e) e.preventDefault();

    const emailInput = document.getElementById('reset-email');
    const email = emailInput.value.trim();
    const btn = document.getElementById('forgot-btn');
    const btnText = document.getElementById('forgot-btn-text');
    const btnIcon = document.getElementById('forgot-icon');
    const spinner = document.getElementById('forgot-spinner');

    if (!email) {
        showToast('Error', 'Please enter your email address.', 'error');
        return;
    }

    // UI Feedback
    btn.disabled = true;
    if (btnText) btnText.textContent = 'Sending...';
    if (btnIcon) btnIcon.classList.add('hidden');
    if (spinner) spinner.classList.remove('hidden');

    fetch(`${window.CONFIG.API_BASE}/api/onboard/password/reset-request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status) {
            window.location.href = `reset-password?email=${encodeURIComponent(email)}`;
        } else {
            resetForgotBtn();
            showToast('Reset Failed', data.message || 'Unable to process request.', 'error');
        }
    })
    .catch(err => {
        resetForgotBtn();
        showToast('Connection Error', 'Please check your internet and try again.', 'error');
    });
}

function resetForgotBtn() {
    const btn = document.getElementById('forgot-btn');
    const btnText = document.getElementById('forgot-btn-text');
    const btnIcon = document.getElementById('forgot-icon');
    const spinner = document.getElementById('forgot-spinner');

    if (btn) btn.disabled = false;
    if (btnText) btnText.textContent = 'Send Reset Link';
    if (btnIcon) btnIcon.classList.remove('hidden');
    if (spinner) spinner.classList.add('hidden');
}

// Ensure handleForgot is globally available
window.handleForgot = handleForgot;
