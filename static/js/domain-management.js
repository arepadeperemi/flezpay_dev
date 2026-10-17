function formatCurrency(price, currencyCode) {
    const symbols = {
        'USD': '$',
        'NGN': '₦',
        'GBP': '£',
        'EUR': '€',
        'KES': 'KSh ',
        'GHS': 'GH₵ ',
        'ZAR': 'R '
    };
    const symbol = symbols[currencyCode?.toUpperCase()] || currencyCode + ' ';
    return symbol + Number(price).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fetchDomainData() {
    try {
        const userDataStr = localStorage.getItem('user_data');
        if (userDataStr) {
            const userData = JSON.parse(userDataStr);
            const business = userData.business_details?.[0] || {};
            updateDomainStatusUI(business);
        }
        
        if (typeof window.apiFetch === 'function') {
            window.apiFetch('/api/user/data', { method: 'POST' })
                .then(res => res.json())
                .then(res => {
                    if (res.status && res.data) {
                        localStorage.setItem('user_data', JSON.stringify(res.data));
                        const business = res.data.business_details?.[0] || {};
                        updateDomainStatusUI(business);
                    }
                })
                .catch(e => console.error("Error refreshing domain data:", e));
        }
    } catch (e) {
        console.error("Error fetching domain data:", e);
    }
}

function updateDomainStatusUI(business) {
    const domainStatusEl = document.getElementById('currentDomainStatus');
    const domainIconBg = document.getElementById('domainIconBg');
    if (!domainStatusEl || !domainIconBg) return;
    
    if (business.store_custom_domain) {
        domainStatusEl.innerHTML = `<span class="text-green-400">${business.store_custom_domain}</span>`;
        domainIconBg.className = 'w-12 h-12 rounded-full bg-green-500/10 flex items-center justify-center border border-green-500/20';
        domainIconBg.innerHTML = '<i data-lucide="globe" class="w-6 h-6 text-green-500"></i>';
    } else {
        domainStatusEl.innerHTML = `<span class="text-amber-400">Not Connected</span>`;
        domainIconBg.className = 'w-12 h-12 rounded-full bg-amber-500/10 flex items-center justify-center border border-amber-500/20';
        domainIconBg.innerHTML = '<i data-lucide="globe" class="w-6 h-6 text-amber-500"></i>';
    }
    if (window.lucide) lucide.createIcons();
}

function initDomainManagement() {
    const statusEl = document.getElementById('currentDomainStatus');
    const searchBtn = document.getElementById('searchDomainBtn');
    if (!statusEl && !searchBtn) return; // Exit if not on the domain management page
    
    fetchDomainData();
    
    if (!searchBtn || searchBtn.dataset.bound) return;
    searchBtn.dataset.bound = "true";
    
    const searchInput = document.getElementById('domainSearchInput');
    const searchExtension = document.getElementById('domainSearchExtension');
    const searchLoader = document.getElementById('searchLoader');
    const searchResultArea = document.getElementById('searchResultArea');
    
    // Prevent invalid characters on input & allow enter to search
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            this.value = this.value.replace(/[^a-zA-Z0-9-]/g, '').toLowerCase();
        });
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                if (searchBtn && !searchBtn.disabled) searchBtn.click();
            }
        });
    }
    
    searchBtn.addEventListener('click', async () => {
        const domainQuery = searchInput.value.trim().toLowerCase();
        if (!domainQuery) {
            searchInput.focus();
            return;
        }
        
        let name = domainQuery;
        let extension = searchExtension ? searchExtension.value : 'com';
        
        // Ensure no dots remain if somehow bypassed
        name = name.replace(/\./g, '');
        
        // Disable search button and show animated spinner inside button
        const originalBtnHtml = searchBtn.innerHTML;
        searchBtn.disabled = true;
        searchBtn.classList.add('opacity-60', 'cursor-not-allowed', 'pointer-events-none');
        searchBtn.innerHTML = `
            <div class="w-4 h-4 rounded-full animate-spin shrink-0" style="border: 2px solid rgba(0, 0, 0, 0.25); border-top-color: #000;"></div>
            <span>Searching...</span>
        `;
        
        searchResultArea.classList.add('hidden');
        searchLoader.classList.remove('hidden');
        searchLoader.classList.add('flex');
        
        try {
            const res = await window.apiFetch('/api/domain/check', {
                method: 'POST',
                body: JSON.stringify({
                    domain_name: name,
                    extension: extension
                })
            });
            
            const data = await res.json();
            searchLoader.classList.add('hidden');
            searchLoader.classList.remove('flex');
            searchResultArea.classList.remove('hidden');
            
            if (data.status && data.data) {
                const domainData = data.data;
                const isAvailable = domainData.availability === 'free';
                let html = `
                    <div class="p-4 sm:p-6 bg-white/[0.02] border border-white/10 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        <div>
                            <h3 class="text-xl sm:text-2xl font-bold text-white mb-2">${domainData.domain}</h3>
                            <div class="flex flex-wrap items-center gap-3">
                                ${isAvailable 
                                    ? '<span class="flex items-center gap-1 text-green-400"><i data-lucide="check-circle" class="w-4 h-4"></i> Available</span>' 
                                    : '<span class="flex items-center gap-1 text-red-400"><i data-lucide="x-circle" class="w-4 h-4"></i> Taken</span>'}
                                ${domainData.premium ? '<span class="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs font-medium border border-purple-500/20">Premium</span>' : ''}
                            </div>
                        </div>
                `;
                
                if (isAvailable) {
                    html += `
                        <div class="flex flex-row items-center gap-4 sm:gap-6 w-full sm:w-auto justify-between sm:justify-end border-t border-white/10 sm:border-0 pt-4 sm:pt-0 mt-2 sm:mt-0">
                            <div class="text-left sm:text-right">
                                <p class="text-slate-400 text-sm">Price</p>
                                <p class="text-xl font-bold text-white">${formatCurrency(domainData.price, domainData.currency)}</p>
                            </div>
                            <button onclick="buyDomain(this, '${name}', '${extension}', ${domainData.price}, '${domainData.currency}')" class="px-6 py-2.5 bg-primary hover:bg-primary-dark text-bg-dark font-medium rounded-xl transition-colors shadow-[0_0_15px_rgba(34,197,94,0.3)] shrink-0">
                                Buy Domain
                            </button>
                        </div>
                    `;
                }
                
                html += `</div>`;
                
                if (domainData.suggestions && domainData.suggestions.length > 0) {
                    html += `<div class="mt-6">
                        <h4 class="text-sm font-medium text-slate-400 uppercase tracking-wider mb-3">Suggested Alternatives</h4>
                        <div class="space-y-3">`;
                    
                    domainData.suggestions.forEach(sug => {
                        html += `
                            <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between p-3 sm:p-4 bg-white/[0.02] hover:bg-white/5 border border-white/5 hover:border-white/10 rounded-lg transition-colors gap-3 sm:gap-0">
                                <div>
                                    <h4 class="font-bold text-white mb-0.5">${sug.domain}</h4>
                                    <div class="flex items-center gap-2 text-xs">
                                        <span class="text-green-400">Available</span>
                                        ${sug.premium ? '<span class="px-1.5 py-0.5 bg-purple-500/20 text-purple-400 rounded border border-purple-500/20">Premium</span>' : ''}
                                    </div>
                                </div>
                                <div class="flex items-center justify-between sm:justify-end gap-4 w-full sm:w-auto border-t border-white/5 sm:border-0 pt-3 sm:pt-0">
                                    <p class="font-bold text-white">${formatCurrency(sug.price, sug.currency)}</p>
                                    <button onclick="buyDomain(this, '${name}', '${sug.extension}', ${sug.price}, '${sug.currency}')" class="px-4 py-1.5 bg-white/10 hover:bg-white/20 text-white text-sm font-medium rounded-lg transition-colors">
                                        Buy
                                    </button>
                                </div>
                            </div>
                        `;
                    });
                    
                    html += `</div></div>`;
                }

                searchResultArea.innerHTML = html;
                if (window.lucide) lucide.createIcons();
            } else {
                searchResultArea.innerHTML = `
                    <div class="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-center">
                        ${data.message || 'Error checking domain availability.'}
                    </div>
                `;
            }
        } catch (e) {
            console.error("Search error:", e);
            searchLoader.classList.add('hidden');
            searchLoader.classList.remove('flex');
            searchResultArea.classList.remove('hidden');
            searchResultArea.innerHTML = `
                <div class="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-center">
                    A network error occurred. Please try again.
                </div>
            `;
        } finally {
            searchLoader.classList.add('hidden');
            searchLoader.classList.remove('flex');
            searchBtn.disabled = false;
            searchBtn.classList.remove('opacity-60', 'cursor-not-allowed', 'pointer-events-none');
            searchBtn.innerHTML = originalBtnHtml;
            if (window.lucide) lucide.createIcons();
        }
    });

    // Tab Logic
    const tabReg = document.getElementById('tabRegister');
    const tabTrans = document.getElementById('tabTransfer');
    const flowReg = document.getElementById('flowRegister');
    const flowTrans = document.getElementById('flowTransfer');
    
    if (tabReg && tabTrans && flowReg && flowTrans) {
        tabReg.addEventListener('click', () => {
            tabReg.className = "pb-3 text-white font-semibold border-b-2 border-primary transition-colors";
            tabTrans.className = "pb-3 text-slate-400 font-semibold border-b-2 border-transparent hover:text-white transition-colors";
            flowReg.classList.remove('hidden');
            flowTrans.classList.add('hidden');
        });
        tabTrans.addEventListener('click', () => {
            tabTrans.className = "pb-3 text-white font-semibold border-b-2 border-primary transition-colors";
            tabReg.className = "pb-3 text-slate-400 font-semibold border-b-2 border-transparent hover:text-white transition-colors";
            flowTrans.classList.remove('hidden');
            flowReg.classList.add('hidden');
        });
    }

    // Transfer Logic
    const transferInput = document.getElementById('transferDomainInput');
    const transferExtension = document.getElementById('transferDomainExtension');
    const transferAuthCodeInput = document.getElementById('transferAuthCodeInput');
    const checkTransferBtn = document.getElementById('checkTransferBtn');
    const transferLoader = document.getElementById('transferLoader');
    const transferResultArea = document.getElementById('transferResultArea');

    if (transferInput) {
        transferInput.addEventListener('input', function() {
            this.value = this.value.replace(/[^a-zA-Z0-9-]/g, '').toLowerCase();
        });
    }

    if (checkTransferBtn) {
        checkTransferBtn.addEventListener('click', async (e) => {
            const domainQuery = transferInput.value.trim().toLowerCase();
            const authCode = transferAuthCodeInput.value.trim();
            const extension = transferExtension ? transferExtension.value : 'com';
            
            if (!domainQuery || !authCode) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Missing Information',
                    text: 'Please enter both the domain name and the authorization code.',
                    background: '#1e293b',
                    color: '#fff',
                    confirmButtonColor: '#22c55e'
                });
                return;
            }
            
            // Remove dot just in case
            let name = domainQuery.replace(/\./g, '');
            
            // Disable transfer button and show animated spinner inside button
            const originalTransferBtnHtml = checkTransferBtn.innerHTML;
            checkTransferBtn.disabled = true;
            checkTransferBtn.classList.add('opacity-60', 'cursor-not-allowed', 'pointer-events-none');
            checkTransferBtn.innerHTML = `
                <div class="w-4 h-4 rounded-full animate-spin shrink-0" style="border: 2px solid rgba(0, 0, 0, 0.25); border-top-color: #000;"></div>
                <span>Verifying...</span>
            `;
            
            transferResultArea.classList.add('hidden');
            transferLoader.classList.remove('hidden');
            transferLoader.classList.add('flex');
            
            try {
                const response = await window.apiFetch('/api/domain/check', {
                    method: 'POST',
                    body: JSON.stringify({
                        domain_name: name,
                        extension: extension
                    })
                });
                
                const data = await response.json();
                transferLoader.classList.add('hidden');
                transferLoader.classList.remove('flex');
                transferResultArea.classList.remove('hidden');
                
                if (data.status) {
                    const domainData = data.data;
                    if (domainData.availability === 'free') {
                        transferResultArea.innerHTML = `
                            <div class="p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-400 text-center">
                                This domain is not registered anywhere yet. Please use the Register tab instead.
                            </div>
                        `;
                    } else if (domainData.availability === 'active') {
                        transferResultArea.innerHTML = `
                            <div class="p-6 bg-white/5 border border-white/10 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-6">
                                <div>
                                    <div class="flex items-center gap-3 mb-2">
                                        <h3 class="text-xl text-white font-bold">${name}.${extension}</h3>
                                        <span class="px-2 py-1 bg-primary/20 text-primary text-xs font-semibold rounded-md">Ready for Transfer</span>
                                    </div>
                                    <p class="text-slate-400">Transfer cost: <span class="text-white font-medium">${domainData.currency} ${domainData.price.toFixed(2)}</span></p>
                                </div>
                                <button onclick="confirmTransfer(this, '${name}', '${extension}', '${authCode}', ${domainData.price}, '${domainData.currency}')" class="w-full md:w-auto px-6 py-3 bg-primary hover:bg-primary-dark text-bg-dark font-medium rounded-xl transition-colors shadow-[0_0_20px_rgba(34,197,94,0.3)]">
                                    Confirm & Pay Transfer
                                </button>
                            </div>
                        `;
                    } else {
                        transferResultArea.innerHTML = `
                            <div class="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-center">
                                Cannot transfer this domain right now.
                            </div>
                        `;
                    }
                } else {
                    transferResultArea.innerHTML = `
                        <div class="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-center">
                            ${data.message || 'Error verifying domain transfer.'}
                        </div>
                    `;
                }
            } catch (e) {
                console.error("Transfer Check Error:", e);
                transferLoader.classList.add('hidden');
                transferLoader.classList.remove('flex');
                transferResultArea.classList.remove('hidden');
                transferResultArea.innerHTML = `
                    <div class="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-center">
                        A network error occurred. Please try again.
                    </div>
                `;
            } finally {
                transferLoader.classList.add('hidden');
                transferLoader.classList.remove('flex');
                checkTransferBtn.disabled = false;
                checkTransferBtn.classList.remove('opacity-60', 'cursor-not-allowed', 'pointer-events-none');
                checkTransferBtn.innerHTML = originalTransferBtnHtml;
                if (window.lucide) lucide.createIcons();
            }
        });
    }
}

async function confirmTransfer(btn, name, extension, authCode, price, currency) {
    const originalText = btn.innerHTML;
    const result = await Swal.fire({
        title: 'Confirm Transfer?',
        text: `You are about to transfer ${name}.${extension}. ${currency} ${price.toFixed(2)} will be deducted from your wallet.`,
        icon: 'question',
        showCancelButton: true,
        background: '#1e293b',
        color: '#fff',
        confirmButtonColor: '#22c55e',
        cancelButtonColor: '#ef4444',
        confirmButtonText: 'Yes, transfer it!'
    });
    
    if (!result.isConfirmed) return;
    
    btn.innerHTML = '<i data-lucide="loader" class="w-5 h-5 animate-spin"></i> Processing...';
    btn.disabled = true;
    lucide.createIcons();
    
    try {
        const response = await window.apiFetch('/api/domain/transfer', {
            method: 'POST',
            body: JSON.stringify({
                domain_name: name,
                extension: extension,
                auth_code: authCode,
                price: price,
                currency: currency
            })
        });
        
        const data = await response.json();
        
        if (data.status) {
            await Swal.fire({
                icon: 'success',
                title: 'Transfer Initiated!',
                text: 'Your domain transfer has been initiated successfully. It may take a few days to complete depending on the current registrar.',
                background: '#1e293b',
                color: '#fff',
                confirmButtonColor: '#22c55e'
            });
            window.location.reload();
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Transfer Failed',
                text: data.message || 'An error occurred during transfer.',
                background: '#1e293b',
                color: '#fff',
                confirmButtonColor: '#22c55e'
            });
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    } catch (e) {
        console.error("Transfer Submit Error:", e);
        Swal.fire({
            icon: 'error',
            title: 'Network Error',
            text: 'Could not connect to the server.',
            background: '#1e293b',
            color: '#fff',
            confirmButtonColor: '#22c55e'
        });
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

window.buyDomain = async function(btn, name, extension, price, currency) {
    const originalText = btn.innerHTML;

    const result = await Swal.fire({
        title: 'Confirm Purchase',
        text: `Are you sure you want to purchase ${name}.${extension} for ${formatCurrency(price, currency)}? This will be deducted from your wallet.`,
        icon: 'question',
        showCancelButton: true,
        background: '#1e293b',
        color: '#fff',
        confirmButtonColor: '#22c55e',
        cancelButtonColor: '#ef4444',
        confirmButtonText: 'Yes, purchase it!'
    });
    
    if (!result.isConfirmed) return;
    
    btn.innerHTML = '<i data-lucide="loader" class="w-5 h-5 animate-spin"></i> Processing...';
    btn.disabled = true;
    lucide.createIcons();
    
    try {
        const res = await window.apiFetch('/api/domain/buy', {
            method: 'POST',
            body: JSON.stringify({
                domain_name: name,
                extension: extension,
                price: price,
                currency: currency
            })
        });
        
        const data = await res.json();
        if (data.status) {
            Swal.fire({
                icon: 'success',
                title: 'Success!',
                text: data.message || 'Domain purchased successfully!',
                background: '#1e293b',
                color: '#fff',
                confirmButtonColor: '#22c55e'
            });
            fetchDomainData();
            document.getElementById('searchResultArea').classList.add('hidden');
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Purchase Failed',
                text: data.message || 'Failed to purchase domain.',
                background: '#1e293b',
                color: '#fff',
                confirmButtonColor: '#22c55e'
            });
        }
    } catch (e) {
        console.error("Buy error:", e);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'A network error occurred. Please try again.',
            background: '#1e293b',
            color: '#fff',
            confirmButtonColor: '#22c55e'
        });
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
        lucide.createIcons();
    }
};

window.initDomainManagement = initDomainManagement;
window.fetchDomainData = fetchDomainData;
window.updateDomainStatusUI = updateDomainStatusUI;

document.addEventListener('DOMContentLoaded', initDomainManagement);
document.addEventListener('swup:contentReplaced', initDomainManagement);

if (window.flezSwup && window.flezSwup.hooks) {
    window.flezSwup.hooks.on('page:view', () => {
        initDomainManagement();
    });
}
