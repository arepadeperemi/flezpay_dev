// Immediate stub definitions to prevent ReferenceError before init
window.openBuyKitDrawer = window.openBuyKitDrawer || function() {
    if (typeof window.initPOS === 'function') {
        window.initPOS();
        if (typeof window.openBuyKitDrawer === 'function') {
            return window.openBuyKitDrawer();
        }
    }
};
window.closeBuyKitDrawer = window.closeBuyKitDrawer || function() {
    const drawer = document.getElementById('buyKitDrawer');
    if (drawer) drawer.classList.add('invisible', 'opacity-0');
};
window.updateUnits = window.updateUnits || function() {};
window.nextStep = window.nextStep || function() {};
window.prevStep = window.prevStep || function() {};
window.submitBuyKit = window.submitBuyKit || function() {};

window.initPOS = function() {
    // Initialize lucide icons if available
    if (typeof lucide !== 'undefined') lucide.createIcons();

    // Drawer State
    let currentStep = 1;
    const totalSteps = 3;
    const basePrice = 100;
    
    // Auto-open drawer if requested via URL
    const urlParams = new URLSearchParams(window.location.search);
    const shouldAutoOpen = urlParams.get('buy') === 'true';

    let exchangeRate = 1.0;

    window.openBuyKitDrawer = async function() {
        const drawer = document.getElementById('buyKitDrawer');
        if (!drawer) return;
        
        // Reset state on open
        currentStep = 1;
        document.getElementById('kit-units').value = 1;
        updateDrawerUI();
        
        drawer.classList.remove('invisible', 'opacity-0');
        setTimeout(() => {
            const content = drawer.querySelector('.drawer-content');
            if (content) content.classList.remove('translate-x-full');
        }, 10);
        
        // Fetch exchange rate in background for accurate summary
        try {
            const targetCurrency = window.STORE_CURRENCY_CODE || 'USD';
            if (targetCurrency !== 'USD') {
                const res = await fetch('https://open.er-api.com/v6/latest/USD');
                if (res.ok) {
                    const data = await res.json();
                    if (data.rates && data.rates[targetCurrency]) {
                        exchangeRate = data.rates[targetCurrency];
                    }
                }
            }
        } catch (e) {
            console.error('Error fetching exchange rate:', e);
            exchangeRate = 1.0; // fallback
        }
    };

    window.closeBuyKitDrawer = function() {
        const drawer = document.getElementById('buyKitDrawer');
        if (!drawer) return;
        
        const content = drawer.querySelector('.drawer-content');
        if (content) content.classList.add('translate-x-full');
        
        setTimeout(() => {
            drawer.classList.add('invisible', 'opacity-0');
        }, 300);
    };

    window.updateUnits = function(change) {
        const input = document.getElementById('kit-units');
        let val = parseInt(input.value) || 1;
        val += change;
        if (val < 1) val = 1;
        if (val > 50) val = 50; // Max 50 kits
        input.value = val;
    };

    window.nextStep = function() {
        // Validation before moving to next step
        if (currentStep === 2) {
            const form = document.getElementById('buyKitForm');
            if (!form.checkValidity()) {
                form.reportValidity();
                return;
            }
        }

        if (currentStep < totalSteps) {
            currentStep++;
            updateDrawerUI();
        }
    };

    window.prevStep = function() {
        if (currentStep > 1) {
            currentStep--;
            updateDrawerUI();
        }
    };

    function updateDrawerUI() {
        // Update Step text
        document.getElementById('current-step-display').innerText = currentStep;

        // Show/Hide steps
        for (let i = 1; i <= totalSteps; i++) {
            const stepEl = document.getElementById(`drawer-step-${i}`);
            if (stepEl) {
                if (i === currentStep) {
                    stepEl.classList.remove('hidden');
                } else {
                    stepEl.classList.add('hidden');
                }
            }
        }

        // Button logic
        const btnPrev = document.getElementById('btn-prev-step');
        const btnNext = document.getElementById('btn-next-step');
        const btnSubmit = document.getElementById('btn-submit-step');

        if (currentStep === 1) {
            btnPrev.classList.add('hidden');
            btnNext.classList.remove('hidden');
            btnSubmit.classList.add('hidden');
        } else if (currentStep === totalSteps) {
            btnPrev.classList.remove('hidden');
            btnNext.classList.add('hidden');
            btnSubmit.classList.remove('hidden');
            
            // Populate Summary
            updateSummary();
        } else {
            btnPrev.classList.remove('hidden');
            btnNext.classList.remove('hidden');
            btnSubmit.classList.add('hidden');
        }
    }

    function updateSummary() {
        const units = parseInt(document.getElementById('kit-units').value) || 1;
        document.getElementById('summary-units').innerText = units;
        
        // Format to local string for better readability, applying exchange rate
        const localBasePrice = (basePrice * exchangeRate).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        document.getElementById('summary-base-price').innerText = localBasePrice;

        const total = (basePrice * units * exchangeRate).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        document.getElementById('summary-total').innerText = total;
    }

    window.submitBuyKit = async function() {
        const btn = document.getElementById('btn-submit-step');
        const originalContent = btn.innerHTML;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> <span>Processing...</span>`;
        btn.disabled = true;

        try {
            const data = {
                units: parseInt(document.getElementById('kit-units').value) || 1,
                email: document.getElementById('kit-email').value,
                phone: document.getElementById('kit-phone').value,
                country: document.getElementById('kit-country').value,
                state: document.getElementById('kit-state').value,
                address: document.getElementById('kit-address').value
            };

            const response = await apiFetch('/api/pos/buy-kit/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (response.ok && result.status) {
                closeBuyKitDrawer();
                Swal.fire({
                    icon: 'success',
                    title: 'Purchase Successful!',
                    text: 'Your FlezPay POS Kit order has been placed. The amount has been deducted from your wallet.',
                    confirmButtonColor: '#cfff45'
                });
                document.getElementById('buyKitForm').reset();
            } else {
                throw new Error(result.message || 'An error occurred during purchase');
            }
        } catch (error) {
            Swal.fire({
                icon: 'error',
                title: 'Purchase Failed',
                text: error.message,
                confirmButtonColor: '#ef4444'
            });
        } finally {
            btn.innerHTML = originalContent;
            btn.disabled = false;
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    };
    
    // Helper to get CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    // Execute auto-open if flagged
    if (shouldAutoOpen && typeof window.openBuyKitDrawer === 'function') {
        setTimeout(() => {
            window.openBuyKitDrawer();
        }, 500);
    }
};

// Auto-initialize if DOM is ready or when loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('buyKitDrawer') && typeof window.initPOS === 'function') {
            window.initPOS();
        }
    });
} else {
    if (document.getElementById('buyKitDrawer') && typeof window.initPOS === 'function') {
        window.initPOS();
    }
}
