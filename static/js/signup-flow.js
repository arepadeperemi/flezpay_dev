/* 
   Signup Flow Logic for FlezPay Enterprise
   4-Step multi-step registration flow
*/

let currentStep = 1;

// Converts raw server/Python errors into user-friendly messages
function friendlyError(msg) {
    if (!msg || typeof msg !== 'string') return 'Something went wrong. Please try again.';
    const technical = [
        'argument must be', 'NoneType', 'object has no attribute',
        'unsupported operand', 'int()', '__', 'Traceback', 'Exception',
        'KeyError', 'TypeError', 'ValueError', 'AttributeError'
    ];
    if (technical.some(t => msg.includes(t))) {
        return 'Something went wrong on our end. Please try again or contact support.';
    }
    return msg;
}
const totalSteps = 3;
let validatedPin = '';

const stepContextData = {
    1: [
        { icon: 'user', text: 'Personal information' },
        { icon: 'lock', text: 'Secure password creation' },
    ],
    2: [
        { icon: 'mail', text: 'Email verification' },
        { icon: 'shield-check', text: 'Secure account validation' },
    ],
    3: [
        { icon: 'globe',        text: 'Regional settings' },
        { icon: 'hash',         text: 'Transaction PIN setup' },
    ]
};

function renderStepContext(step) {
    const container = document.getElementById('step-context');
    if (!container) return;
    const items = stepContextData[step] || [];
    container.innerHTML = items.map(item => `
        <div class="flex items-center gap-3 text-slate-300 text-sm">
            <div class="w-7 h-7 bg-primary/15 border border-primary/25 rounded-full flex items-center justify-center shrink-0">
                <i data-lucide="${item.icon}" class="w-3.5 h-3.5 text-primary"></i>
            </div>
            ${item.text}
        </div>
    `).join('');
    if (window.lucide) lucide.createIcons();
}

function goToStep(next) {
    if (next > currentStep && !validateStep(currentStep)) return;

    const panels = {
        1: 'step-1',
        2: 'step-verify',
        3: 'step-2',
        4: 'step-success'
    };

    const fromPanel = document.getElementById(panels[currentStep]);
    const toPanel   = document.getElementById(panels[next]);

    if (!fromPanel || !toPanel) return;

    const exitClass = next > currentStep ? 'exiting-left' : 'exiting-right';
    const entryClass = next > currentStep ? 'hidden-right' : 'hidden-left';

    // Start exit animation on outgoing panel
    fromPanel.classList.remove('active');
    fromPanel.classList.add(exitClass);

    // Show incoming panel in off-screen position, then animate in
    toPanel.classList.remove('hidden-left', 'hidden-right');
    toPanel.classList.add(entryClass);
    toPanel.offsetHeight; // force reflow
    toPanel.classList.remove(entryClass);
    toPanel.classList.add('active');

    // Hide outgoing panel after transition completes
    setTimeout(() => {
        fromPanel.classList.remove(exitClass);
        fromPanel.classList.add(next > currentStep ? 'hidden-left' : 'hidden-right');
    }, 450);

    updateProgress(currentStep, next);
    currentStep = next;
    if (next <= 3) renderStepContext(next);
}

function updateProgress(from, to) {
    // Step index → fill percentage targets
    const stepPercents = { 1: 0, 2: 50, 3: 100, 4: 100 };
    const stepNames    = { 1: 'Step 1 of 3', 2: 'Step 2 of 3', 3: 'Step 3 of 3', 4: 'Complete!' };

    const fill    = document.getElementById('linear-progress-fill');
    const pctEl   = document.getElementById('progress-pct');
    const labelEl = document.getElementById('progress-step-label');

    const startPct  = stepPercents[from] ?? 0;
    const targetPct = stepPercents[to]   ?? 0;

    if (fill)    fill.style.width = targetPct + '%';
    if (labelEl) labelEl.textContent = stepNames[to] ?? '';

    // Animated numeric counter (ease-out cubic, 700 ms)
    if (pctEl) {
        let animFrame = null;
        let startTs   = null;
        const duration = 700;
        const diff     = targetPct - startPct;

        function tick(ts) {
            if (!startTs) startTs = ts;
            const elapsed  = ts - startTs;
            const t        = Math.min(elapsed / duration, 1);
            const eased    = 1 - Math.pow(1 - t, 3); // ease-out cubic
            pctEl.textContent = Math.round(startPct + diff * eased) + '%';
            if (t < 1) animFrame = requestAnimationFrame(tick);
        }
        if (animFrame) cancelAnimationFrame(animFrame);
        animFrame = requestAnimationFrame(tick);
    }
}

// ── Validation ─────────────────────────────────────────────────
function showError(id, show) {
    const el = document.getElementById('err-' + id);
    const input = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('hidden', !show);
    if (input) input.classList.toggle('error', show);
    if (window.lucide) lucide.createIcons();
}

function validateStep(step) {
    let valid = true;

    if (step === 1) {
        const fn = document.getElementById('first-name').value.trim();
        const ln = document.getElementById('last-name').value.trim();
        const ph = document.getElementById('phone').value.trim();

        showError('first-name', !fn);
        showError('last-name',  !ln);
        showError('phone',      !ph);

        if (!fn || !ln || !ph) valid = false;

        // Google Auth users skip email/password validation
        if (!isGoogleAuth) {
            const em = document.getElementById('email').value.trim();
            const pw = document.getElementById('password').value;
            const cpw = document.getElementById('confirm-password').value;

            showError('email',      !em || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(em));
            showError('password', pw.length < 8);
            showError('confirm', pw !== cpw);

            if (!em || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(em) || pw.length < 8 || pw !== cpw) valid = false;

            let score = 0;
            if (pw.length >= 8) score++;
            if (/[A-Z]/.test(pw)) score++;
            if (/[0-9]/.test(pw)) score++;
            if (/[^A-Za-z0-9]/.test(pw)) score++;

            if (score < 4 && pw.length > 0) {
                showToast('Security', 'Your password must meet all 4 requirements (Length, Uppercase, Number, Special Char)', 'error');
                valid = false;
            }
        }
    }

    if (step === 2) {
        // Verification step - checked by handleVerifyPin
        if (!validatedPin) return false;
    }

    if (step === 3) {
        const terms = document.getElementById('terms').checked;
        const country = document.getElementById('country').value;

        showError('terms',    !terms);
        showError('country',  !country || country === 'other');

        if (!terms || !country || country === 'other') valid = false;
    }
    return valid;
}

// ── OTP & PIN ──────────────────────────────────────────────────
async function sendValidationPin() {
    if (!validateStep(1)) return;

    // Google Auth: skip email verification entirely, go straight to step 3
    if (isGoogleAuth) {
        validatedPin = 'google_auth_bypass';
        goToStep(3);
        return;
    }

    const btn = document.getElementById('step1-btn');
    const text = document.getElementById('step1-btn-text');
    const icon = document.getElementById('step1-btn-icon');
    const spin = document.getElementById('step1-btn-spinner');
    const em = document.getElementById('email').value.trim();
    const ph = document.getElementById('phone').value.trim();

    btn.disabled = true;
    if (text) text.textContent = 'Sending code...';
    if (icon) icon.classList.add('hidden');
    if (spin) spin.classList.remove('hidden');

    try {
        const res = await fetch(`${window.CONFIG.API_BASE}/api/onboard/validate/number`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_email: em, user_phone: ph })
        });
        const data = await res.json();
        if (data.status) {
            document.getElementById('verify-email-display').textContent = em;
            goToStep(2);
        } else {
            showToast('Oops!', friendlyError(data.message) || 'Unable to send code. Please try again.', 'error');
        }
    } catch (e) {
        showToast('Connection Error', 'Please check your internet and try again.', 'error');
    } finally {
        btn.disabled = false;
        if (text) text.textContent = 'Continue';
        if (icon) icon.classList.remove('hidden');
        if (spin) spin.classList.add('hidden');
        if (window.lucide) lucide.createIcons();
    }
}

async function handleVerifyPin() {
    const boxes = document.querySelectorAll('.pinput-box');
    let pin = '';
    boxes.forEach(box => pin += box.value);
    pin = pin.trim();
    const em  = document.getElementById('email').value.trim();
    const errorBox = document.getElementById('login-error-verify');
    const errorText = document.getElementById('verify-error-text');

    if (pin.length < 6) {
        if (errorBox) errorBox.classList.remove('hidden');
        if (errorText) errorText.textContent = 'Enter the 6-digit code';
        return;
    }

    const btn = document.getElementById('verify-btn');
    const text = document.getElementById('verify-btn-text');
    const spin = document.getElementById('verify-btn-spinner');

    btn.disabled = true;
    if (text) text.textContent = 'Verifying...';
    if (spin) spin.classList.remove('hidden');
    if (errorBox) errorBox.classList.add('hidden');

    try {
        const res = await fetch(`${window.CONFIG.API_BASE}/api/onboard/validate/pin`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_email: em, user_pin: pin })
        });
        const data = await res.json();
        if (data.status) {
            validatedPin = pin;
            goToStep(3);
        } else {
            if (errorBox) errorBox.classList.remove('hidden');
            if (errorText) errorText.textContent = data.message || 'Invalid PIN';
        }
    } catch (e) {
        if (errorBox) errorBox.classList.remove('hidden');
        if (errorText) errorText.textContent = 'Connection error. Try again.';
    } finally {
        btn.disabled = false;
        if (text) text.textContent = 'Verify & Continue';
        if (spin) spin.classList.add('hidden');
        if (window.lucide) lucide.createIcons();
    }
}

// ── UI Selection Helpers ──────────────────────────────────────────

function handleCountrySelect(select) {
    if (select.value === 'other') {
        const modal = document.getElementById('waitlist-modal');
        const content = document.getElementById('waitlist-modal-content');
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        
        requestAnimationFrame(() => {
            content.classList.remove('scale-95', 'opacity-0');
            content.classList.add('scale-100', 'opacity-100');
        });
    } else {
        showError('country', false);
    }
}

function closeWaitlistModal() {
    const modal = document.getElementById('waitlist-modal');
    const content = document.getElementById('waitlist-modal-content');
    content.classList.remove('scale-100', 'opacity-100');
    content.classList.add('scale-95', 'opacity-0');
    setTimeout(() => {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }, 300);
    // Reset country selection to empty
    document.getElementById('country').value = "";
}

async function submitWaitlist() {
    const country = document.getElementById('waitlist-country').value;
    const err = document.getElementById('err-waitlist-country');
    if (!country) {
        err.classList.remove('hidden');
        return;
    }
    err.classList.add('hidden');

    const btn = document.getElementById('waitlist-submit-btn');
    const text = document.getElementById('waitlist-btn-text');
    const spin = document.getElementById('waitlist-btn-spinner');

    btn.disabled = true;
    text.textContent = 'Submitting...';
    spin.classList.remove('hidden');

    const payload = {
        first_name: document.getElementById('first-name').value.trim(),
        last_name: document.getElementById('last-name').value.trim(),
        user_email: document.getElementById('email').value.trim(),
        user_phone: document.getElementById('phone').value.trim(),
        biz_name: document.getElementById('first-name').value.trim() + ' Business',
        country: country
    };

    try {
        const res = await fetch(`${window.CONFIG.API_BASE}/api/onboard/waitlist`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if (data.status) {
            document.getElementById('waitlist-form-view').classList.add('hidden');
            document.getElementById('waitlist-success-view').classList.remove('hidden');
        } else {
            showToast('Error', data.message || 'Something went wrong.', 'error');
            btn.disabled = false;
            text.textContent = 'Notify Me';
            spin.classList.add('hidden');
        }
    } catch (e) {
        showToast('Connection Error', 'Please check your internet connection.', 'error');
        btn.disabled = false;
        text.textContent = 'Notify Me';
        spin.classList.add('hidden');
    }
}

function checkStrength(pw) {
    let score = 0;
    if (pw.length >= 8) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;

    const colors = ['#ef4444','#f97316','#eab308','#cfff45'];
    const lbls   = ['Weak','Fair','Good','Strong'];

    ['bar1','bar2','bar3','bar4'].forEach((id, i) => {
        const bar = document.getElementById(id);
        if (!bar) return;
        bar.style.width = i < score ? '100%' : '0%';
        if (i < score) bar.style.backgroundColor = colors[score - 1];
    });

    const lbl = document.getElementById('strength-label');
    if (lbl) {
        lbl.textContent  = pw.length > 0 && score > 0 ? lbls[score - 1] : '';
        lbl.style.color  = pw.length > 0 && score > 0 ? colors[score - 1] : '';
    }
}

// ── Final Submission ─────────────────────────────────────────────
async function handleSubmit() {
    if (!validateStep(3)) { if (window.lucide) lucide.createIcons(); return; }

    const btn  = document.getElementById('submit-btn');
    const text = document.getElementById('submit-text');
    const icon = document.getElementById('submit-icon');
    const spin = document.getElementById('submit-spinner');

    btn.disabled = true;
    if (text) text.textContent = 'Creating account…';
    if (icon) icon.classList.add('hidden');
    if (spin) spin.classList.remove('hidden');

    const firstName = document.getElementById('first-name').value.trim();
    const lastName = document.getElementById('last-name').value.trim();

    const payload = {
        user_email: document.getElementById('email').value.trim(),
        user_phone: document.getElementById('phone').value.trim(),
        first_name: firstName,
        last_name: lastName,
        password:   isGoogleAuth ? '' : document.getElementById('password').value,
        user_pin:   isGoogleAuth ? '' : validatedPin,
        biz_name:   firstName + ' ' + lastName,
        biz_type:   'other',
        team_size:  '1',
        country:    document.getElementById('country').value,
        currency:   document.getElementById('country').value === 'KE' ? 'KES' : 'NGN',
        plan:       'free',
        timezone:   Intl.DateTimeFormat().resolvedOptions().timeZone
    };
    if (isGoogleAuth) {
        payload.google_auth = window.googleAuthToken;
    }

    try {
        const res = await fetch(`${window.CONFIG.API_BASE}/api/onboard/register`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if (data.status !== false && data.jwt) {
            localStorage.setItem('access_token', data.jwt);
            localStorage.setItem('refresh_token', data.refresh);
            
            // Show success
            const fromPanel = document.getElementById('step-2');
            const succPanel = document.getElementById('step-success');
            const firstName = document.getElementById('first-name').value.trim();

            fromPanel.classList.remove('active');
            fromPanel.classList.add('hidden-left');

            document.getElementById('success-name').textContent = firstName;

            succPanel.classList.remove('hidden-left','hidden-right');
            requestAnimationFrame(() => requestAnimationFrame(() => {
                succPanel.classList.add('active');
                if (window.lucide) lucide.createIcons();
            }));

            // Mark all as done
            updateProgress(4, 5); 

            if (data.user) {
                localStorage.setItem('user_data', JSON.stringify(data.user));
                // Set last refresh so dashboard doesn't immediately fetch again
                localStorage.setItem('last_data_refresh', Date.now().toString());
            }

            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1000);
        } else {
            showToast('Registration Failed', friendlyError(data.message) || 'Registration failed. Please try again.', 'error');
        }
    } catch (e) {
        showToast('Connection Issue', 'We could not reach the server. Please try again.', 'error');
    } finally {
        btn.disabled = false;
        if (text) text.textContent = 'Create Account';
        if (icon) icon.classList.remove('hidden');
        if (spin) spin.classList.add('hidden');
        if (window.lucide) lucide.createIcons();
    }
}

// Global flag for Google Auth mode
let isGoogleAuth = false;
window.googleAuthToken = '';

// Initial setup
document.addEventListener('DOMContentLoaded', () => {
    renderStepContext(1);
    updateProgress(0, 1); // initialise progress bar

    // Auto-fill from query params if coming from Google Auth
    const params = new URLSearchParams(window.location.search);
    if (params.has('google_auth')) {
        isGoogleAuth = true;
        window.googleAuthToken = params.get('google_auth');
        const email = params.get('email') || '';
        const firstName = params.get('first_name') || '';
        const lastName = params.get('last_name') || '';

        // Pre-fill name fields
        if (firstName) {
            const fnameInput = document.getElementById('first-name');
            if (fnameInput) fnameInput.value = firstName;
        }
        if (lastName) {
            const lnameInput = document.getElementById('last-name');
            if (lnameInput) lnameInput.value = lastName;
        }
        // Store email in a hidden input so handleSubmit can read it
        if (email) {
            const emailInput = document.getElementById('email');
            if (emailInput) emailInput.value = email;
        }

        // Hide: Google signup button, divider, email field, password fields, confirm-password field
        // We target the parent wrappers (space-y-2 divs) so labels disappear too
        const emailField = document.getElementById('email');
        const pwField = document.getElementById('password');
        const cpwField = document.getElementById('confirm-password');

        // Hide email wrapper (the space-y-2 div containing the email label + input)
        if (emailField) {
            const emailWrapper = emailField.closest('.space-y-2');
            if (emailWrapper) emailWrapper.style.display = 'none';
        }
        // Hide password wrapper
        if (pwField) {
            const pwWrapper = pwField.closest('.space-y-2');
            if (pwWrapper) pwWrapper.style.display = 'none';
        }
        // Hide confirm-password wrapper
        if (cpwField) {
            const cpwWrapper = cpwField.closest('.space-y-2');
            if (cpwWrapper) cpwWrapper.style.display = 'none';
        }
        // Hide strength bars + label (they sit outside the password wrapper)
        const strengthBars = document.querySelector('.flex.gap-1\\.5.py-1');
        if (strengthBars) strengthBars.style.display = 'none';
        const strengthLabel = document.getElementById('strength-label');
        if (strengthLabel) strengthLabel.style.display = 'none';

        // Hide "Sign up with Google" button (first button in step-1)
        const googleBtn = document.querySelector('#step-1 button[onclick="handleGoogleLogin()"]');
        if (googleBtn) googleBtn.style.display = 'none';

        // Hide the "or" divider
        const dividers = document.querySelectorAll('#step-1 .flex.items-center.gap-4.py-1');
        dividers.forEach(d => d.style.display = 'none');

        // Update step 1 heading
        const step1Heading = document.querySelector('#step-1 h2');
        if (step1Heading) step1Heading.textContent = 'Complete your profile';
        const step1Sub = document.querySelector('#step-1 h2 + p');
        if (step1Sub) step1Sub.textContent = 'Just a few more details to get you started';

        setTimeout(() => {
            if (typeof showToast === 'function') {
                showToast('Google Auth', 'Please complete your registration to continue.', 'info');
            }
        }, 500);
    }
});
