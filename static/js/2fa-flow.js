/**
 * 2fa-flow.js
 * Handles the Two-Factor Authentication verification process.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Check if we have the temporary credentials
    const tempEmail = sessionStorage.getItem('2fa_email');
    const tempPassword = sessionStorage.getItem('2fa_password');

    if (!tempEmail || !tempPassword) {
        showToast('Error', 'Session expired. Please log in again.', 'error');
        setTimeout(() => { window.location.href = 'login'; }, 2000);
        return;
    }

    initPinput();
});

/**
 * initPinput: Handles the behavior of the split PIN boxes
 */
function initPinput() {
    const boxes = document.querySelectorAll('.pinput-box');
    
    boxes.forEach((box, index) => {
        // Handle typing
        box.addEventListener('input', (e) => {
            const val = e.target.value.replace(/\D/g, ''); // Numeric only
            box.value = val;

            if (val) {
                box.classList.add('filled');
                if (index < boxes.length - 1) {
                    boxes[index + 1].focus();
                } else {
                    // Auto-submit if all filled? (Optional, let's just blur or let user click button)
                }
            } else {
                box.classList.remove('filled');
            }
        });

        // Handle backspace
        box.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && !box.value && index > 0) {
                boxes[index - 1].focus();
            }
        });

        // Handle paste
        box.addEventListener('paste', (e) => {
            e.preventDefault();
            const data = (e.clipboardData || window.clipboardData).getData('text');
            const digits = data.replace(/\D/g, '').split('');
            
            digits.forEach((digit, i) => {
                if (i < boxes.length) {
                    boxes[i].value = digit;
                    boxes[i].classList.add('filled');
                    if (i < boxes.length - 1) boxes[i+1].focus();
                    else boxes[i].blur();
                }
            });
        });
    });
}

function handle2FA(e) {
    if (e) e.preventDefault();

    const email = sessionStorage.getItem('2fa_email');
    const password = sessionStorage.getItem('2fa_password');
    
    const boxes = document.querySelectorAll('.pinput-box');
    let code = '';
    boxes.forEach(box => code += box.value);

    if (code.length < 6) {
        showToast('Required', 'Please enter your 6-digit code.', 'error');
        return;
    }

    setLoading(true);

    fetch(`${window.CONFIG.API_BASE}/api/onboard/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            email_or_phone: email,
            password: password,
            two_factor_code: code
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status !== false && data.jwt) {
            // Success! Save tokens and redirect
            localStorage.setItem('access_token', data.jwt);
            localStorage.setItem('refresh_token', data.refresh);
            if (data.user) {
                localStorage.setItem('user_data', JSON.stringify(data.user));
            }
            
            // Clear temporary credentials
            sessionStorage.removeItem('2fa_email');
            sessionStorage.removeItem('2fa_password');
            
            showToast('Success', 'Verified successfully. Entering dashboard...', 'success');
            setTimeout(() => { window.location.href = 'dashboard'; }, 1500);
        } else {
            setLoading(false);
            showToast('Verification Failed', data.message || 'Invalid 2FA code.', 'error');
            // Clear inputs for retry
            document.querySelectorAll('.pinput-box').forEach(b => { b.value = ''; b.classList.remove('filled'); });
            document.querySelectorAll('.pinput-box')[0].focus();
        }
    })
    .catch(err => {
        setLoading(false);
        showToast('Connection Error', 'Please check your internet and try again.', 'error');
    });
}

function setLoading(isLoading) {
    const btn = document.getElementById('verify-btn');
    const btnText = document.getElementById('verify-btn-text');
    const icon = document.getElementById('verify-icon');
    const spinner = document.getElementById('verify-spinner');

    if (btn) btn.disabled = isLoading;
    if (isLoading) {
        if (btnText) btnText.textContent = 'Verifying...';
        if (icon) icon.classList.add('hidden');
        if (spinner) spinner.classList.remove('hidden');
    } else {
        if (btnText) btnText.textContent = 'Verify Account';
        if (icon) icon.classList.remove('hidden');
        if (spinner) spinner.classList.add('hidden');
    }
}

// Global exposure
window.handle2FA = handle2FA;
