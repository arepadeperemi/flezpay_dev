/* 
   Login Flow Logic for FlezPay Enterprise
*/

function handleLogin(e) {
    if (e) e.preventDefault();
    
    const btn = document.getElementById('login-btn');
    const btnText = document.getElementById('login-btn-text');
    const btnIcon = document.getElementById('login-btn-icon');
    const spinner = document.getElementById('login-spinner');

    const email_or_phone = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;

    if (!email_or_phone || !password) {
        showToast('Required Fields', 'Please enter your email/phone and password.', 'error');
        return;
    }

    // UI Feedback
    btn.disabled = true;
    if (btnText) btnText.textContent = 'Signing in...';
    if (btnIcon) btnIcon.classList.add('hidden');
    if (spinner) spinner.classList.remove('hidden');

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    fetch(`${window.CONFIG.API_BASE}/api/onboard/login`, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        credentials: 'include',
        body: JSON.stringify({ email_or_phone, password, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status !== false && data.jwt) {
            localStorage.setItem('access_token', data.jwt);
            localStorage.setItem('refresh_token', data.refresh);
            if (data.user) {
                localStorage.setItem('user_data', JSON.stringify(data.user));
                // Set last refresh so dashboard doesn't immediately fetch again
                localStorage.setItem('last_data_refresh', Date.now().toString());
            }
            showToast('Success', 'Welcome back! Initializing your dashboard...', 'success');
            
            setTimeout(() => {
                const urlParams = new URLSearchParams(window.location.search);
                const nextUrl = urlParams.get('next');
                if (nextUrl && nextUrl.startsWith('/')) {
                    window.location.href = nextUrl;
                } else {
                    window.location.href = '/dashboard';
                }
            }, 500);
        } else if (data.requires_2fa) {
            // 2FA required: Store credentials temporarily and redirect
            sessionStorage.setItem('2fa_email', email_or_phone);
            sessionStorage.setItem('2fa_password', password);
            showToast('2FA Required', 'Please enter your authenticator code.', 'info');
            setTimeout(() => { window.location.href = '/2fa'; }, 1000);
        } else {
            resetLoginBtn();
            showToast('Login Failed', data.message || 'Invalid login credentials', 'error');
        }
    })
    .catch(err => {
        resetLoginBtn();
        showToast('Connection Error', 'Please check your internet and try again.', 'error');
    });
}

function resetLoginBtn() {
    const btn = document.getElementById('login-btn');
    const btnText = document.getElementById('login-btn-text');
    const btnIcon = document.getElementById('login-btn-icon');
    const spinner = document.getElementById('login-spinner');

    if (btn) btn.disabled = false;
    if (btnText) btnText.textContent = 'Sign In';
    if (btnIcon) btnIcon.classList.remove('hidden');
    if (spinner) spinner.classList.add('hidden');
}

