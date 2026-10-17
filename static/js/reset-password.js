/**
 * reset-password.js
 * Logic for updating the password using a verification PIN.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Extract email and pin from URL
    const params = new URLSearchParams(window.location.search);
    const email = params.get('email');
    const pin = params.get('pin');

    if (email) {
        document.getElementById('reset-email-hidden').value = email;
    } else {
        showToast('Error', 'Missing reset context. Please try requesting a new link.', 'error');
        setTimeout(() => { window.location.href = 'forgot-password'; }, 3000);
    }

    initPinput();

    // Auto-fill PIN if provided in URL
    if (pin && pin.length === 6) {
        const boxes = document.querySelectorAll('.pinput-box');
        pin.split('').forEach((d, i) => {
            if (boxes[i]) {
                boxes[i].value = d;
                boxes[i].classList.add('filled');
            }
        });
        const pwField = document.getElementById('new-password');
        if (pwField) pwField.focus();
    }
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
                // Move to next
                if (index < boxes.length - 1) {
                    boxes[index + 1].focus();
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

function handleReset(e) {
    if (e) e.preventDefault();

    const email = document.getElementById('reset-email-hidden').value;
    
    // Aggregate PIN from boxes
    const boxes = document.querySelectorAll('.pinput-box');
    let pin = '';
    boxes.forEach(box => pin += box.value);

    const pw = document.getElementById('new-password').value;
    const cpw = document.getElementById('confirm-new-password').value;
    
    const errBox = document.getElementById('reset-error');
    const errText = document.getElementById('reset-error-text');

    // Validation
    if (!pin || pin.length < 6) {
        showToast('Required', 'Please enter the 6-digit PIN sent to your email.', 'error');
        return;
    }
    if (pw !== cpw) {
        showToast('Error', 'Passwords do not match.', 'error');
        return;
    }
    
    if (getStrengthScore(pw) < 4) {
        showToast('Security', 'Please meet all password security requirements.', 'error');
        return;
    }

    setLoading(true);

    fetch(`${window.CONFIG.API_BASE}/api/onboard/password/reset-confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            email: email,
            pin: pin,
            password: pw
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status) {
            // Success: Switch to success state
            document.getElementById('form-state').classList.add('hidden');
            document.getElementById('success-state').classList.remove('hidden');
            showToast('Success', data.message, 'success');
        } else {
            setLoading(false);
            showToast('Error', data.message || 'Unable to update password.', 'error');
        }
    })
    .catch(err => {
        setLoading(false);
        showToast('Connection Error', 'Please check your internet and try again.', 'error');
    });
}


function setLoading(isLoading) {
    const btn = document.getElementById('reset-btn');
    const btnText = document.getElementById('reset-btn-text');
    const btnIcon = document.getElementById('reset-icon');
    const spinner = document.getElementById('reset-spinner');

    btn.disabled = isLoading;
    if (isLoading) {
        btnText.textContent = 'Updating...';
        btnIcon.classList.add('hidden');
        spinner.classList.remove('hidden');
    } else {
        btnText.textContent = 'Update Password';
        btnIcon.classList.remove('hidden');
        spinner.classList.add('hidden');
    }
}

function checkStrength(pw) {
    const score = getStrengthScore(pw);
    const colors = ['#ef4444', '#f97316', '#eab308', '#cfff45'];
    const lbls = ['Weak', 'Fair', 'Good', 'Strong'];

    // Update bars
    ['bar1', 'bar2', 'bar3', 'bar4'].forEach((id, i) => {
        const bar = document.getElementById(id);
        if (!bar) return;
        bar.style.width = i < score ? '100%' : '0%';
        if (i < score) bar.style.backgroundColor = colors[score - 1];
    });

    // Update label
    const lbl = document.getElementById('strength-label');
    if (lbl) {
        lbl.textContent = pw.length > 0 ? lbls[score - 1] || 'Weak' : '';
        lbl.style.color = pw.length > 0 ? colors[score - 1] || colors[0] : '';
    }

    // Update checklist icons
    updateReqIcon('req-length', pw.length >= 8);
    updateReqIcon('req-upper', /[A-Z]/.test(pw));
    updateReqIcon('req-number', /[0-9]/.test(pw));
    updateReqIcon('req-special', /[^A-Za-z0-9]/.test(pw));
}

function updateReqIcon(id, isValid) {
    const el = document.getElementById(id);
    if (!el) return;
    const icon = el.querySelector('i, svg');
    if (!icon) return;
    
    if (isValid) {
        el.classList.remove('text-slate-500');
        el.classList.add('text-primary');
        icon.setAttribute('data-lucide', 'check-circle-2');
    } else {
        el.classList.remove('text-primary');
        el.classList.add('text-slate-500');
        icon.setAttribute('data-lucide', 'circle');
    }
    if (window.lucide) lucide.createIcons();
}

function getStrengthScore(pw) {
    let s = 0;
    if (pw.length >= 8) s++;
    if (/[A-Z]/.test(pw)) s++;
    if (/[0-9]/.test(pw)) s++;
    if (/[^A-Za-z0-9]/.test(pw)) s++;
    return s;
}

// Global exposure
window.handleReset = handleReset;
window.checkStrength = checkStrength;
