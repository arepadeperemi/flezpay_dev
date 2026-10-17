/* 
   Shared Utilities for FlezPay Auth
   Toast system, Theme management, and UI helpers
*/

(function () {
// Guard against double-loading (file is included both globally and per-page on many dashboards)
if (window.__authUtilsLoaded) {
    return;
}
window.__authUtilsLoaded = true;

// Suppress known harmless Chromium DevTools / Web-Vitals soft-navigation internal bug
window.addEventListener('error', function (event) {
    if (event && event.message && event.message.includes("Cannot read properties of undefined (reading 'startTime')")) {
        event.stopImmediatePropagation();
        event.preventDefault();
        return true;
    }
});

// Global Configuration
// Determine base domain based on current host
var defaultStoreDomain = window.location.host;

// Globally fix FLEZ_API_BASE so it doesn't fall back to localhost:8000 in production
window.FLEZ_API_BASE = window.FLEZ_API_BASE || window.location.origin;

window.CONFIG = {
    API_BASE: window.FLEZ_API_BASE,
    STORE_BASE_DOMAIN: defaultStoreDomain
};

window.buildStoreUrl = function(slug, customDomain) {
    if (!slug && !customDomain) return "#";
    const protocol = window.location.protocol;
    if (customDomain) {
        const cleanDomain = customDomain.trim().replace(/^https?:\/\//, '').replace(/\/+$/, '');
        if (cleanDomain) return `${protocol}//${cleanDomain}/`;
    }
    const hostname = window.location.hostname;
    const port = window.location.port ? `:${window.location.port}` : '';

    // Localhost or loopback
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return `${protocol}//${slug}.localhost${port}/`;
    }

    // If currently on a store subdomain
    if (hostname.startsWith(`${slug}.`)) {
        return `${protocol}//${window.location.host}/`;
    }

    // Configured base domain
    const configBaseDomain = window.CONFIG?.STORE_BASE_DOMAIN ? window.CONFIG.STORE_BASE_DOMAIN.split(':')[0] : null;
    if (configBaseDomain && configBaseDomain !== 'localhost' && configBaseDomain !== '127.0.0.1' && hostname.endsWith(configBaseDomain)) {
        return `${protocol}//${slug}.${configBaseDomain}${port}/`;
    }

    // Multi-part domain (e.g. app.flezpay.com -> flezpay.com)
    const parts = hostname.split('.');
    const isIp = parts.every(p => !isNaN(p));
    if (!isIp && parts.length > 2) {
        const rootDomain = parts.slice(-2).join('.');
        return `${protocol}//${slug}.${rootDomain}${port}/`;
    }

    return `${protocol}//${slug}.${hostname}${port}/`;
};

window.getCookie = function (name) {
    let v = null;
    if (document.cookie) {
        document.cookie.split(';').forEach((c) => {
            c = c.trim();
            if (c.startsWith(name + '=')) {
                v = decodeURIComponent(c.substring(name.length + 1));
            }
        });
    }
    return v;
};

// Initialize Icons
document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) {
        lucide.createIcons();
    }
    initTheme();

    // Dynamically update UI elements that display the base domain
    document.querySelectorAll('.base-domain-display').forEach(el => {
        el.textContent = '.' + defaultStoreDomain;
    });

    try {
        const stored = localStorage.getItem('user_data');
        if (stored) {
            enforcePlanSelection(JSON.parse(stored));
        }
    } catch (e) {}
});


// ── Toast System ──────────────────────────────────────────────────
function showToast(title, message, type = 'info') {
    // Handle cases where only two arguments are passed (e.g. showToast("Message here", "error"))
    if (
        message === undefined ||
        (type !== "success" &&
            type !== "error" &&
            type !== "info" &&
            type !== "warning")
    ) {
        // If the second argument is a type string instead of a message
        if (
            message === "success" ||
            message === "error" ||
            message === "info" ||
            message === "warning"
        ) {
            type = message;
            message = title;
            title = type.charAt(0).toUpperCase() + type.slice(1);
        } else {
            message = title;
            title = "Notification";
            type = "info";
        }
    }

    // Default to 'error' if type is not recognized
    if (!["success", "error", "info", "warning", "question"].includes(type)) {
        type = "error";
    }

    // Inject Toast CSS globally if missing
    if (!document.getElementById('toast-styles')) {
        const style = document.createElement('style');
        style.id = 'toast-styles';
        style.textContent = `
            #toast-container { position: fixed; top: 0; right: 0; z-index: 9999; padding: 24px; display: flex; flex-direction: column; gap: 6px; pointer-events: none; }
            .toast { pointer-events: auto; min-width: 320px; max-width: 420px; background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(20px); border-right: 4px solid var(--toast-color, #10b981); padding: 18px 24px; box-shadow: -10px 10px 40px rgba(0, 0, 0, 0.4); display: flex; align-items: flex-start; gap: 16px; border: 1px solid rgba(255, 255, 255, 0.05); animation: toastIn 0.4s cubic-bezier(0.22, 1, 0.36, 1) both; transition: all 0.3s ease; color: white; }
            html.light .toast { background: rgba(255, 255, 255, 0.98); color: #0f172a; border: 1px solid rgba(0, 0, 0, 0.1); box-shadow: -10px 10px 40px rgba(0, 0, 0, 0.1); }
            .toast.error { --toast-color: #ef4444; }
            .toast.success { --toast-color: #22c55e; }
            .toast.info { --toast-color: #3b82f6; }
            .toast.warning { --toast-color: #f59e0b; }
            .toast.shake { animation: shake 0.5s cubic-bezier(.36, .07, .19, .97) both; }
            .toast.hiding { animation: toastOut 0.3s ease forwards; }
            @keyframes toastIn { from { opacity: 0; transform: translateX(100%); } to { opacity: 1; transform: translateX(0); } }
            @keyframes toastOut { from { opacity: 1; transform: translateX(0); } to { opacity: 0; transform: translateX(100%); } }
            @keyframes shake { 10%, 90% { transform: translate3d(-1px, 0, 0); } 20%, 80% { transform: translate3d(2px, 0, 0); } 30%, 50%, 70% { transform: translate3d(-4px, 0, 0); } 40%, 60% { transform: translate3d(4px, 0, 0); } }
        `;
        document.head.appendChild(style);
    }

    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type} ${type === 'error' ? 'shake' : ''}`;
    
    const icons = {
        success: 'check-circle',
        error: 'alert-circle',
        info: 'info',
        warning: 'alert-triangle',
        question: 'help-circle'
    };

    toast.innerHTML = `
        <i data-lucide="${icons[type] || 'info'}" class="w-5 h-5 shrink-0 mt-0.5" style="color: var(--toast-color)"></i>
        <div class="flex-1 min-w-0">
            <h4 class="text-sm font-bold text-slate-900 dark:text-white mb-1">${title}</h4>
            <p class="text-xs text-slate-500 dark:text-slate-400 leading-relaxed break-words">${message}</p>
        </div>
        <div class="flex flex-col gap-2">
            <button class="copy-btn text-slate-400 hover:text-slate-900 dark:hover:text-white" title="Copy message">
                <i data-lucide="copy" class="w-3.5 h-3.5"></i>
            </button>
        </div>
    `;

    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();

    // Copy logic
    const copyBtn = toast.querySelector('.copy-btn');
    if (copyBtn) {
        copyBtn.onclick = (e) => {
            e.stopPropagation();
            navigator.clipboard.writeText(message).then(() => {
                showToast('Copied!', 'Message copied to clipboard', 'info');
            });
        };
    }

    // Auto removal
    setTimeout(() => {
        toast.classList.add('hiding');
        setTimeout(() => toast.remove(), 400);
    }, 5000);
}
window.showToast = showToast;

// ── Theme Management ──────────────────────────────────────────────
function initTheme() {
    const html = document.documentElement;
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);

    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.onclick = () => {
            const current = html.classList.contains('dark') ? 'dark' : 'light';
            const next = current === 'dark' ? 'light' : 'dark';
            applyTheme(next);
        };
    }
}

function applyTheme(theme) {
    const html = document.documentElement;
    html.setAttribute('data-theme', theme);
    html.classList.remove('light', 'dark');
    html.classList.add(theme);
    localStorage.setItem('theme', theme);
}

// ── UI Helpers ────────────────────────────────────────────────────
function togglePasswordVisibility(inputId, iconId) {
    const input = document.getElementById(inputId);
    const icon = document.getElementById(iconId);
    if (!input || !icon) return;

    const isPw = input.type === 'password';
    input.type = isPw ? 'text' : 'password';
    
    // Update Lucide icon
    icon.setAttribute('data-lucide', isPw ? 'eye-off' : 'eye');
    if (window.lucide) lucide.createIcons();
}

// Alias for older code compatibility
window.togglePw = togglePasswordVisibility;
window.togglePassword = togglePasswordVisibility;

// ── Session Management ────────────────────────────────────────────

/**
 * checkAuth: Runs at the top of the HEAD to prevent FOUC.
 * Verifies if an access token exists. Redirects if missing.
 */
function checkAuth() {
    const token = localStorage.getItem('access_token');
    const path = window.location.pathname;
    
    // Clean URL checks
    const isLoginPage = path.includes('login');
    const isSignupPage = path.includes('signup');
    const isForgotPassword = path.includes('forgot-password');
    const isResetPassword = path.includes('reset-password');
    const isLandingPage = path === '/' || path.endsWith('index') || path.endsWith('/') || path === '';

    if (!token && !isLoginPage && !isSignupPage && !isLandingPage && !isForgotPassword && !isResetPassword) {
        window.location.replace('/login');
    }
}

/**
 * logout: Clears all authentication-related data and redirects to login.
 */
function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_data');
    window.location.replace('/logout');
}

/**
 * apiFetch: A wrapper for window.fetch that adds JWT headers and handles auto-refresh.
 */
async function apiFetch(url, options = {}) {
    let token = localStorage.getItem('access_token');
    
    // Default headers
    const headers = {
        ...options.headers
    };

    if (token && token !== 'null') {
        headers['Authorization'] = `Bearer ${token}`;
    }

    // Add CSRF token for Django session authentication compatibility
    const csrfToken = document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1];
    if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken;
    }

    // If body is NOT FormData or Blob, serialize plain objects to JSON
    let fetchBody = options.body;
    if (fetchBody && !(fetchBody instanceof FormData) && !(fetchBody instanceof Blob)) {
        headers['Content-Type'] = headers['Content-Type'] || 'application/json';
        if (typeof fetchBody === 'object') {
            fetchBody = JSON.stringify(fetchBody);
        }
    }

    try {
        let response = await fetch(url, { ...options, headers, body: fetchBody });

        // Handle expired token (401 Unauthorized)
        if (response.status === 401) {
            const refreshed = await refreshToken();
            if (refreshed) {
                // Retry request with new token
                token = localStorage.getItem('access_token');
                headers['Authorization'] = `Bearer ${token}`;
                response = await fetch(url, { ...options, headers, body: fetchBody });
            } else {
                // If refresh also fails, force logout
                logout();
            }
        }

        // Automatically sync user_data if this was a request to the user data endpoint
        if (url.includes('/api/user/data') && response.ok) {
            const clone = response.clone();
            clone.json().then(data => {
                if (data.status && data.data) {
                    localStorage.setItem('user_data', JSON.stringify(data.data));
                    enforcePlanSelection(data.data);
                    if (typeof renderUserData === 'function') renderUserData();
                }
            });
        }

        return response;
    } catch (error) {
        console.error('API Fetch Error:', error);
        throw error;
    }
}

/**
 * refreshToken: Attempts to get a new access token using the refresh token.
 */
async function refreshToken() {
    const refresh = localStorage.getItem('refresh_token');
    if (!refresh) return false;

    try {
        const response = await fetch('/api/token/refresh/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh })
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('access_token', data.access);
            return true;
        }
    } catch (err) {
        console.error('Token refresh failed:', err);
    }
    
    return false;
}

window.initTheme = initTheme;
window.applyTheme = applyTheme;
window.checkAuth = checkAuth;
window.logout = logout;
window.apiFetch = apiFetch;
window.refreshToken = refreshToken;

/**
 * enforcePlanSelection: Forces user to select a subscription plan if none is active.
 */
function enforcePlanSelection(userData) {
    // Handled by SubscriptionOverlayMiddleware
    return;
}
window.enforcePlanSelection = enforcePlanSelection;

// ── Google Auth ──────────────────────────────────────────────────
function handleGoogleLogin() {
    const urlParams = new URLSearchParams(window.location.search);
    const nextUrl = urlParams.get('next');
    let url = `${window.CONFIG?.API_BASE || ''}/api/onboard/google/login`;
    if (nextUrl && nextUrl.startsWith('/')) {
        url += `?next=${encodeURIComponent(nextUrl)}`;
    }
    window.location.href = url;
}

// Export Google Auth to window for global access
window.handleGoogleLogin = handleGoogleLogin;

})();
