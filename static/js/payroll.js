/**
 * Payroll Management Logic - FlezPay Enterprise
 */

const payrollState = {
    search: '',
    page: 1,
    perPage: 10,
    banks: [],
    localStaff: [], // Combined list of managers and payroll for search
    isValidated: false,
    validatedName: '',
    autoPayrollEnabled: false
};

function checkTier2Verification(userData) {
    const data = userData || window.userData || JSON.parse(localStorage.getItem('user_data') || '{}');
    const isTier2 = Boolean(data?.kyb_verified);
    const verifications = data?.verification || [];
    const kybRec = verifications.find(v => (v.verification_type || '').toUpperCase() === 'KYB');
    const isKybApproved = kybRec ? String(kybRec.verification_status) === '1' : false;
    return isTier2 || isKybApproved;
}

function updatePayrollActionButtons(userData) {
    const isVerified = checkTier2Verification(userData);
    const addBtn = document.getElementById('add-payroll-btn');
    if (addBtn) {
        if (!isVerified) {
            addBtn.classList.add('opacity-50', 'cursor-not-allowed');
            addBtn.setAttribute('title', 'Tier 2 account verification required');
        } else {
            addBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            addBtn.removeAttribute('title');
        }
    }

    const runBtn = document.getElementById('run-payroll-btn');
    if (runBtn) {
        if (!isVerified) {
            runBtn.classList.add('opacity-60');
            runBtn.setAttribute('title', 'Tier 2 account verification required');
        } else if (window.userData && window.userData.withdrawals_disabled) {
            runBtn.classList.add('opacity-60');
            runBtn.setAttribute('title', 'Withdrawals are temporarily disabled for your account');
        } else {
            runBtn.classList.remove('opacity-60');
            runBtn.removeAttribute('title');
        }
    }
}

function updateVerificationNotice(userData) {
    const noticeEl = document.getElementById('payroll-verification-notice');
    if (noticeEl) {
        if (checkTier2Verification(userData)) {
            noticeEl.classList.add('hidden');
        } else {
            noticeEl.classList.remove('hidden');
            if (window.lucide) lucide.createIcons();
        }
    }
    updatePayrollActionButtons(userData);
}

window.initPayroll = () => {
    payrollState.autoPayrollEnabled = false; // Reset/Default
    const tableBody = document.getElementById('payroll-tbody');
    const runBtn = document.getElementById('run-payroll-btn');
    const addBtn = document.getElementById('add-payroll-btn');
    
    // Check if on the List page or Add page
    const listPage = !!tableBody;
    const addPage = !!document.getElementById('payroll-form');

    updateVerificationNotice();

    if (listPage) {
        loadPayrollData();
        setupSearch();
        
        if (addBtn) {
            addBtn.onclick = (e) => {
                if (!checkTier2Verification()) {
                    e.preventDefault();
                    Swal.fire({
                        icon: 'warning',
                        title: 'Verification Required',
                        text: 'Tier 2 account verification is required to add or manage employee payroll.',
                        confirmButtonText: 'Verify Account',
                        showCancelButton: true,
                        cancelButtonText: 'Cancel',
                        customClass: { popup: 'swal2-cuperino', confirmButton: 'bg-primary', cancelButton: 'bg-slate-700' }
                    }).then((result) => {
                        if (result.isConfirmed) {
                            if (window.flezSwup) window.flezSwup.navigate('/verification');
                            else window.location.href = '/verification';
                        }
                    });
                }
            };
        }

        if (runBtn) {
            runBtn.onclick = (e) => runPayrollFlow(e.currentTarget);
        }
    }
    
    if (addPage) {
        setupAddPayrollForm();
    }
}

async function loadPayrollData(page = 1, search = '') {
    payrollState.page = page;
    payrollState.search = search;

    try {
        // 1. Load Summary Data - Use cached data if fresh (< 30s) to avoid 429
        const cachedData = localStorage.getItem('user_data');
        const lastRefresh = parseInt(localStorage.getItem('last_data_refresh') || '0');
        const isFresh = (Date.now() - lastRefresh) < 30000;

        if (cachedData && isFresh) {
            const data = JSON.parse(cachedData);
            const summary = data.payroll_details || {};
            const totalCount = (data.payroll || []).length;
            const businessDetails = (data.business_details || [])[0] || {};
            updatePayrollSummary(summary, totalCount, businessDetails, data.payroll || []);
            updateVerificationNotice(data);
        } else {
            const summaryResponse = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/data`, {
                method: 'POST'
            });
            const summaryResult = await summaryResponse.json();
            if (summaryResult.status && summaryResult.data) {
                const summary = summaryResult.data.payroll_details || {};
                const totalCount = (summaryResult.data.payroll || []).length;
                const businessDetails = (summaryResult.data.business_details || [])[0] || {};
                updatePayrollSummary(summary, totalCount, businessDetails, summaryResult.data.payroll || []);
                updateVerificationNotice(summaryResult.data);
            }
        }

        // 2. Load Paginated List
        const listUrl = `${window.FLEZ_API_BASE || ''}/api/user/payroll/list?page=${page}&search=${encodeURIComponent(search)}`;
        const listResponse = await apiFetch(listUrl, {
            method: 'GET'
        });
        const listResult = await listResponse.json();

        if (listResult.status) {
            renderPayrollTable(listResult.data);
            renderPaginationControls(listResult.pagination);
        }
    } catch (err) {
        console.error('Failed to load payroll data:', err);
    }
}

function renderPaginationControls(pagination) {
    const container = document.getElementById('pagination-controls');
    if (!container) return;
    
    if (!pagination || pagination.total_pages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    container.innerHTML = `
        <p class="text-[10px] text-slate-500 font-bold uppercase">
            Showing ${(pagination.current_page - 1) * pagination.per_page + 1} to ${Math.min(pagination.current_page * pagination.per_page, pagination.total_items)} of ${pagination.total_items} entries
        </p>
        <div class="flex gap-2">
            <button 
                ${!pagination.has_previous ? 'disabled' : ''} 
                onclick="loadPayrollData(${pagination.current_page - 1}, payrollState.search)"
                class="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-[10px] font-bold text-slate-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
                Previous
            </button>
            <button 
                ${!pagination.has_next ? 'disabled' : ''} 
                onclick="loadPayrollData(${pagination.current_page + 1}, payrollState.search)"
                class="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-[10px] font-bold text-slate-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
                Next
            </button>
        </div>
    `;
}

function setupSearch() {
    const searchInput = document.getElementById('payroll-search');
    if (!searchInput) return;
    
    let debounceTimer;
    searchInput.oninput = (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            loadPayrollData(1, e.target.value);
        }, 500);
    };
}

function updatePayrollSummary(summary, activeCount, businessDetails = {}, payrollList = []) {
    const payoutEl = document.querySelector('h3.text-3xl.font-bold');
    const countEl = document.querySelector('p.text-xs.text-slate-500.mt-2');
    const readyCountEl = document.getElementById('ready-count');
    const blockedCountEl = document.getElementById('blocked-count');
    
    // Auto Payroll Toggle Init
    const autoPayrollToggle = document.getElementById('auto-payroll-toggle');
    if (autoPayrollToggle && businessDetails.hasOwnProperty('enable_auto_payroll')) {
        const isEnabled = businessDetails.enable_auto_payroll === true || businessDetails.enable_auto_payroll === 'true' || businessDetails.enable_auto_payroll == 1;
        payrollState.autoPayrollEnabled = isEnabled;
        autoPayrollToggle.setAttribute('data-enabled', isEnabled.toString());
        const knob = autoPayrollToggle.querySelector('#toggle-knob');
        if (isEnabled) {
            autoPayrollToggle.classList.replace('bg-slate-800', 'bg-primary');
            autoPayrollToggle.classList.add('border-primary/20');
            if (knob) {
                knob.style.transform = 'translateX(1.25rem)';
                knob.classList.replace('bg-slate-400', 'bg-white');
            }
        } else {
            autoPayrollToggle.classList.replace('bg-primary', 'bg-slate-800');
            autoPayrollToggle.classList.remove('border-primary/20');
            if (knob) {
                knob.style.transform = 'translateX(0)';
                knob.classList.replace('bg-white', 'bg-slate-400');
            }
        }
    }
    
    if (payoutEl) payoutEl.textContent = `${window.STORE_CURRENCY_SYMBOL}${(summary.total_monthly_disbursement || 0).toLocaleString()}`;
    if (countEl) countEl.textContent = `For ${activeCount} active employees`;
    
    const overdraftEl = document.getElementById('overdraft-amount');
    if (overdraftEl) overdraftEl.textContent = `${window.STORE_CURRENCY_SYMBOL}${(summary.overdraft || 0).toLocaleString()}`;
    
    if (readyCountEl) readyCountEl.textContent = `${summary.active_count || 0} Ready`;
    if (blockedCountEl) blockedCountEl.textContent = `${summary.blocked_count || 0} Blocked`;

    // Dynamic Next Run Date - Closest payout date from any user
    const nextRunBtn = document.getElementById('next-run-badge');
    const processingDateEl = document.querySelector('.underline.decoration-primary.decoration-2.underline-offset-4');
    
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    let closestDate = null;
    let minDiff = Infinity;

    if (payrollList && payrollList.length > 0) {
        payrollList.forEach(p => {
            if (!p.pay_date) return;
            const originalD = new Date(p.pay_date);
            if (!isNaN(originalD.getTime())) {
                // Normalize to current month
                const d = new Date(now.getFullYear(), now.getMonth(), originalD.getDate());
                
                const diff = Math.abs(d.getTime() - now.getTime());
                if (diff < minDiff) {
                    minDiff = diff;
                    closestDate = d;
                }
            }
        });
    }

    let dateStr;
    if (closestDate) {
        dateStr = closestDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } else {
        // Fallback to end of month if no dates found
        const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
        dateStr = lastDay.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    if (nextRunBtn) {
        nextRunBtn.innerHTML = `<i data-lucide="check-circle" class="w-4 h-4"></i> Next Run: ${dateStr}`;
        if (window.lucide) lucide.createIcons();
    }
    
    if (processingDateEl) {
        processingDateEl.textContent = dateStr;
    }

    // Spinner Animation Control
    const spinner = document.getElementById('payroll-spinner');
    if (spinner) {
        // Robust check for truthiness (handles boolean true, string 'true', or number 1)
        const isAutoEnabled = businessDetails.enable_auto_payroll === true || 
                             businessDetails.enable_auto_payroll === 'true' || 
                             businessDetails.enable_auto_payroll == 1;
                             
        const hasUnpaid = (summary.active_count || 0) > 0;
        
        if (isAutoEnabled && hasUnpaid) {
            spinner.classList.add('animate-spin-slow');
        } else {
            spinner.classList.remove('animate-spin-slow');
        }
    }
}

function renderPayrollTable(payrolls) {
    const tbody = document.getElementById('payroll-tbody');
    if (!tbody) return;

    if (!payrolls || payrolls.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-10 text-center text-slate-500">No payroll records found.</td></tr>`;
        return;
    }

    const isAuto = payrollState.autoPayrollEnabled;
    const isVerified = checkTier2Verification();
    const isLocked = isAuto || !isVerified;
    const lockTitle = !isVerified ? 'Disabled: Tier 2 verification required' : (isAuto ? 'Editing is locked while Auto Payroll is active' : '');

    tbody.innerHTML = payrolls.map(p => {
        const totalPayout = (parseFloat(p.pay_amount) || 0) + (parseFloat(p.allowances) || 0) - (parseFloat(p.deductions) || 0);
        return `
            <tr class="group hover:bg-white/5 transition-all">
                <td class="px-6 py-4">
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-xl bg-primary/10 flex items-center justify-center text-[10px] font-bold text-primary">
                            ${(p.account_name || '??').split(' ').map(n => n[0]).join('')}
                        </div>
                        <div>
                            <p class="text-sm font-bold text-white">${p.account_name}</p>
                            <p class="text-[10px] text-slate-500 font-medium">${p.description || 'Employee'}</p>
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4 text-sm text-slate-400 font-medium">${p.department || 'General'}</td>
                <td class="px-6 py-4">
                    <p class="text-sm font-bold text-white">${window.STORE_CURRENCY_SYMBOL}${totalPayout.toLocaleString()}</p>
                    <p class="text-[10px] text-slate-500 mt-0.5">Last Paid: ${p.last_payment_date || 'Never'}</p>
                </td>
                <td class="px-6 py-4">
                    <span class="status-badge px-3 py-1 ${p.pay_status === 'active' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 'bg-rose-500/10 text-rose-500 border-rose-500/20'} text-[10px] font-black rounded-full uppercase border">
                        ${p.pay_status === 'active' ? 'Ready' : 'Blocked'}
                    </span>
                </td>
                <td class="px-6 py-4 text-right">
                    <div class="flex items-center justify-end gap-1">
                        <a href="/edit-payroll/${p.id}" class="p-2 hover:bg-white/10 rounded-lg text-slate-400 hover:text-white transition-all ${isLocked ? 'opacity-30 pointer-events-none' : ''}" title="${lockTitle || 'Edit Profile'}">
                            <i data-lucide="settings" class="w-4 h-4"></i>
                        </a>
                        <button onclick="togglePayrollStatus(this, ${p.id}, '${p.pay_status}')" class="p-2 hover:bg-white/10 rounded-lg text-slate-400 hover:text-white transition-all ${isLocked ? 'opacity-30 pointer-events-none' : ''}" title="${lockTitle || (p.pay_status === 'active' ? 'Block Disbursement' : 'Ready Disbursement')}">
                            <i data-lucide="${p.pay_status === 'active' ? 'lock' : 'unlock'}" class="w-4 h-4"></i>
                        </button>
                        <button onclick="deletePayroll(${p.id})" class="p-2 hover:bg-rose-500/10 rounded-lg text-slate-400 hover:text-rose-500 transition-all ${isLocked ? 'opacity-30 pointer-events-none' : ''}" title="${lockTitle || 'Delete Record'}">
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

/**
 * Add/Edit Payroll Form Logic
 */
async function checkAutoPayrollEnabled(forceFresh = false) {
    let raw = window.userData;
    if (!raw && !forceFresh) {
        try {
            raw = JSON.parse(localStorage.getItem('user_data') || 'null');
        } catch (e) {}
    }
    if (!raw || !raw.business_details || forceFresh) {
        try {
            const resp = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/data`, {
                method: 'POST'
            });
            if (resp.ok) {
                const resJson = await resp.json();
                if (resJson.status && resJson.data) {
                    raw = resJson.data;
                    window.userData = raw;
                    localStorage.setItem('user_data', JSON.stringify(raw));
                }
            }
        } catch (e) {
            console.error('Error checking auto payroll status', e);
        }
    }
    const business = (raw?.business_details || [])[0] || {};
    const isAuto = business.enable_auto_payroll === true || 
                   business.enable_auto_payroll === 'true' || 
                   business.enable_auto_payroll == 1;
    payrollState.autoPayrollEnabled = isAuto;
    return isAuto;
}

function lockPayrollFormForAutoPayroll() {
    const form = document.getElementById('payroll-form');
    if (!form) return;

    // 1. Alert Banner
    if (!document.getElementById('auto-payroll-lock-banner')) {
        const banner = document.createElement('div');
        banner.id = 'auto-payroll-lock-banner';
        banner.className = 'p-5 rounded-2xl bg-amber-50 dark:bg-amber-500/10 border border-amber-300/80 dark:border-amber-500/30 flex items-start gap-3.5 text-amber-950 dark:text-amber-200 mb-6 shadow-sm dark:shadow-amber-500/5 animate-in fade-in slide-in-from-top-2 duration-300';
        banner.innerHTML = `
            <div class="w-9 h-9 rounded-xl bg-amber-100 dark:bg-amber-500/20 flex items-center justify-center shrink-0 text-amber-600 dark:text-amber-400 mt-0.5">
                <i data-lucide="lock" class="w-5 h-5"></i>
            </div>
            <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                    <h4 class="text-sm font-bold text-amber-950 dark:text-amber-300">Auto Payroll is Currently Active</h4>
                    <span class="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200 dark:bg-amber-500/20 dark:text-amber-300 dark:border-amber-500/30 text-[10px] font-bold uppercase tracking-wider">Locked</span>
                </div>
                <p class="text-xs text-amber-800 dark:text-amber-200/90 mt-1 leading-relaxed font-normal">
                    Employee payroll details cannot be modified while automated disbursements are scheduled. To change compensation, direct deposit, or disbursement details, please disable Auto Payroll from the dashboard first.
                </p>
                <div class="mt-2.5">
                    <a href="/payroll" class="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-700 hover:text-amber-950 dark:text-amber-400 dark:hover:text-amber-300 hover:underline transition-colors">
                        <i data-lucide="arrow-left" class="w-3.5 h-3.5"></i>
                        <span>Return to Payroll Dashboard</span>
                    </a>
                </div>
            </div>
        `;
        form.insertBefore(banner, form.firstChild);
    }

    // 2. Disable all interactive inputs and selects
    const inputs = form.querySelectorAll('input, select, textarea');
    inputs.forEach(el => {
        el.disabled = true;
        el.classList.add('opacity-60', 'cursor-not-allowed', 'bg-white/5');
        el.setAttribute('title', 'Editing is locked while Auto Payroll is active');
    });

    // 3. Disable toggle switches
    const switches = form.querySelectorAll('button.switch, #toggle-staff-search, #recurring-toggle, .hours-switch');
    switches.forEach(sw => {
        sw.classList.add('opacity-40', 'pointer-events-none', 'cursor-not-allowed');
        sw.setAttribute('title', 'Editing is locked while Auto Payroll is active');
    });

    // 4. Lock Save Button
    const saveBtn = document.getElementById('save-payroll-btn');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.classList.remove('bg-primary', 'hover:bg-primary/90', 'shadow-primary/20', 'text-white');
        saveBtn.classList.add('opacity-50', 'pointer-events-none', 'cursor-not-allowed', 'bg-slate-200', 'dark:bg-slate-700/60', 'text-slate-500', 'dark:text-slate-400', 'border', 'border-slate-300', 'dark:border-white/10', 'shadow-none');
        saveBtn.innerHTML = `<span>Editing Locked (Auto Payroll Active)</span> <i data-lucide="lock" class="w-5 h-5"></i>`;
    }

    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function lockPayrollFormForUnverified(isEdit = false) {
    const form = document.getElementById('payroll-form');
    if (!form) return;

    // 1. Disable all interactive inputs and selects
    const inputs = form.querySelectorAll('input, select, textarea');
    inputs.forEach(el => {
        el.disabled = true;
        el.classList.add('opacity-60', 'cursor-not-allowed', 'bg-white/5');
        el.setAttribute('title', 'Disabled: Tier 2 account verification required');
    });

    // 2. Disable toggle switches
    const switches = form.querySelectorAll('button.switch, #toggle-staff-search, #recurring-toggle, .hours-switch');
    switches.forEach(sw => {
        sw.classList.add('opacity-40', 'pointer-events-none', 'cursor-not-allowed');
        sw.setAttribute('title', 'Disabled: Tier 2 account verification required');
    });

    // 3. Lock Save Button
    const saveBtn = document.getElementById('save-payroll-btn');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.classList.remove('bg-primary', 'hover:bg-primary/90', 'shadow-primary/20', 'text-white');
        saveBtn.classList.add('opacity-50', 'pointer-events-none', 'cursor-not-allowed', 'bg-slate-200', 'dark:bg-slate-700/60', 'text-slate-500', 'dark:text-slate-400', 'border', 'border-slate-300', 'dark:border-white/10', 'shadow-none');
        saveBtn.innerHTML = `<span>${isEdit ? 'Editing Locked' : 'Adding Locked'} (Tier 2 Required)</span> <i data-lucide="shield-alert" class="w-5 h-5"></i>`;
    }

    if (typeof lucide !== 'undefined') lucide.createIcons();
}

async function setupAddPayrollForm() {
    const saveBtn = document.getElementById('save-payroll-btn');
    if (!saveBtn) return;

    updateVerificationNotice();

    // Load initial data and auto payroll status in parallel
    await Promise.all([
        loadBanks(),
        loadLocalStaffData(),
        loadDepartments(),
        checkAutoPayrollEnabled()
    ]);

    // Load existing data if editing (support both clean URL and query param)
    const path = window.location.pathname;
    const match = path.match(/\/edit-payroll\/(\d+)/);
    const payrollId = match ? match[1] : new URLSearchParams(window.location.search).get('id');
    
    const titleEl = document.getElementById('payroll-header-title');
    const mobileTitleEl = document.getElementById('payroll-mobile-title');

    if (payrollId) {
        if (titleEl) titleEl.textContent = 'Edit Employee Payroll';
        if (mobileTitleEl) mobileTitleEl.textContent = 'Edit Employee Payroll';
        await loadExistingPayroll(payrollId);
        if (!checkTier2Verification()) {
            lockPayrollFormForUnverified(true);
        } else if (payrollState.autoPayrollEnabled) {
            lockPayrollFormForAutoPayroll();
        }
    } else {
        if (titleEl) titleEl.textContent = 'Add New Payroll';
        if (mobileTitleEl) mobileTitleEl.textContent = 'Add New Payroll';
        if (!checkTier2Verification()) {
            lockPayrollFormForUnverified(false);
        }
    }

    saveBtn.onclick = (e) => {
        if (!checkTier2Verification()) {
            Swal.fire({
                title: 'Verification Required',
                text: `Tier 2 account verification is required to ${payrollId ? 'edit' : 'add'} employee payroll.`,
                icon: 'warning',
                confirmButtonText: 'Verify Account',
                showCancelButton: true,
                cancelButtonText: 'Cancel',
                customClass: { popup: 'swal2-cuperino', confirmButton: 'bg-primary', cancelButton: 'bg-slate-700' }
            }).then((result) => {
                if (result.isConfirmed) {
                    if (window.flezSwup) window.flezSwup.navigate('/verification');
                    else window.location.href = '/verification';
                }
            });
            return;
        }
        if (payrollId && payrollState.autoPayrollEnabled) {
            Swal.fire({
                title: 'Editing Locked',
                text: 'Cannot edit employee payroll while Auto Payroll is enabled. Please disable Auto Payroll from the main payroll dashboard first.',
                icon: 'warning',
                confirmButtonText: 'Go to Payroll',
                showCancelButton: true,
                cancelButtonText: 'Stay Here',
                customClass: { popup: 'swal2-cuperino', confirmButton: 'bg-primary', cancelButton: 'bg-slate-700' }
            }).then((result) => {
                if (result.isConfirmed) {
                    if (window.flezSwup) window.flezSwup.navigate('/payroll');
                    else window.location.href = '/payroll';
                }
            });
            return;
        }
        handleSavePayroll(e.currentTarget);
    };

    const cancelBtn = saveBtn.parentElement?.querySelector('a[href="/payroll"]');
    if (cancelBtn) {
        cancelBtn.onclick = (e) => {
            e.preventDefault();
            if (window.flezSwup) window.flezSwup.navigate('/payroll');
            else window.location.href = '/payroll';
        };
    }

    ['account-number', 'bank-select'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.onchange = resetValidation;
            el.oninput = resetValidation;
        }
    });

    ['base-salary', 'allowances', 'deductions', 'disbursement-date', 'payment-frequency'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.oninput = window.updateSummary;
    });

    // Search listeners
    const searchInput = document.getElementById('staff-search-input');
    const searchToggle = document.getElementById('search-staff-toggle');

    if (searchInput) {
        searchInput.oninput = (e) => filterStaffSearch(e.target.value);
        searchInput.onfocus = () => {
            if (searchInput.value) {
                 document.getElementById('staff-search-results')?.classList.remove('hidden');
            }
        };
    }

    // Toggle listener
    if (searchToggle) {
        searchToggle.onclick = () => {
            const enabled = searchToggle.getAttribute('aria-checked') === 'true';
            document.getElementById('staff-search-container').classList.toggle('hidden', enabled);
        };
    }

    window.updateSummary();
}

async function loadDepartments() {
    const select = document.getElementById('department');
    if (!select) return;

    try {
        const response = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/departments/filter`, {
            method: 'POST'
        });
        const result = await response.json();
        if (result.status) {
            const depts = result.data || [];
            if (depts.length > 0) {
                select.innerHTML = depts.map(d => `<option value="${d.department_name}">${d.department_name}</option>`).join('');
            } else {
                select.innerHTML = '<option value="General">General Operations</option>';
            }
        }
    } catch (err) {
        console.error('Failed to load departments:', err);
    }
}

async function loadBanks() {
    const select = document.getElementById('bank-select');
    if (!select) return;

    try {
        const response = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/data/banks`);
        const result = await response.json();
        if (result.status) {
            payrollState.banks = result.data || [];
            select.innerHTML = '<option value="" disabled selected>Select Bank</option>' + 
                payrollState.banks.map(b => `<option value="${b.code}">${b.name}</option>`).join('');
        }
    } catch (err) {
        console.error('Failed to load banks:', err);
        select.innerHTML = '<option value="" disabled selected>Error loading banks</option>';
    }
}

async function loadLocalStaffData() {
    try {
        const response = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/data`, { method: 'POST' });
        const result = await response.json();
        if (result.status && result.data) {
            const managers = (result.data.managers || []).map(m => ({
                name: `${m.manager_name}`,
                email: m.manager_email,
                role: 'Manager',
                dept: 'Management',
                id: m.uniq_id
            }));
            const employees = (result.data.payroll || []).map(p => ({
                name: p.account_name,
                email: '', // Payroll might not have emails in this schema
                role: p.description || 'Staff',
                dept: p.department || 'Retail Ops',
                id: p.id
            }));
            payrollState.localStaff = [...managers, ...employees];
        }
    } catch (err) {
        console.error('Failed to load staff data:', err);
    }
}

function filterStaffSearch(query) {
    const resultsContainer = document.getElementById('staff-search-results');
    if (!query) {
        resultsContainer.classList.add('hidden');
        return;
    }

    const filtered = payrollState.localStaff.filter(s => 
        s.name.toLowerCase().includes(query.toLowerCase()) || 
        s.email.toLowerCase().includes(query.toLowerCase())
    );

    if (filtered.length === 0) {
        resultsContainer.innerHTML = '<div class="p-4 text-center text-xs text-slate-500">No results found</div>';
    } else {
        resultsContainer.innerHTML = filtered.map(s => `
            <div class="p-3 border-b border-white/5 hover:bg-white/5 cursor-pointer transition-all" onclick="selectStaff('${s.name}', '${s.role}', '${s.dept}')">
                <p class="text-sm font-bold text-white">${s.name}</p>
                <p class="text-[10px] text-slate-500">${s.email ? s.email + ' • ' : ''}${s.role}</p>
            </div>
        `).join('');
    }
    resultsContainer.classList.remove('hidden');
}

function resetValidation() {
    if (!payrollState.isValidated) return;
    payrollState.isValidated = false;
    payrollState.validatedName = '';
    
    const saveBtn = document.getElementById('save-payroll-btn');
    if (saveBtn) {
        saveBtn.innerHTML = 'Validate Account <i data-lucide="shield-check" class="w-5 h-5"></i>';
        if (window.lucide) lucide.createIcons();
    }
    
    const summaryRow = document.getElementById('summary-beneficiary-row');
    if (summaryRow) summaryRow.classList.add('hidden');
}

async function handleSavePayroll(btn) {
    const path = window.location.pathname;
    const match = path.match(/\/edit-payroll\/(\d+)/);
    const payrollId = match ? match[1] : new URLSearchParams(window.location.search).get('id');

    if (!checkTier2Verification()) {
        Swal.fire({
            icon: 'warning',
            title: 'Verification Required',
            text: `Tier 2 account verification is required to ${payrollId ? 'edit' : 'add'} employee payroll.`,
            confirmButtonText: 'Verify Account',
            showCancelButton: true,
            cancelButtonText: 'Cancel',
            customClass: { popup: 'swal2-cuperino', confirmButton: 'bg-primary', cancelButton: 'bg-slate-700' }
        }).then((result) => {
            if (result.isConfirmed) {
                if (window.flezSwup) window.flezSwup.navigate('/verification');
                else window.location.href = '/verification';
            }
        });
        return;
    }

    if (payrollId) {
        const isAuto = await checkAutoPayrollEnabled();
        if (isAuto) {
            Swal.fire({
                title: 'Editing Locked',
                text: 'Cannot edit employee payroll while Auto Payroll is active. Please disable Auto Payroll from the main payroll dashboard first.',
                icon: 'warning',
                confirmButtonText: 'Go to Payroll',
                showCancelButton: true,
                cancelButtonText: 'Stay Here',
                customClass: { popup: 'swal2-cuperino', confirmButton: 'bg-primary', cancelButton: 'bg-slate-700' }
            }).then((result) => {
                if (result.isConfirmed) {
                    if (window.flezSwup) window.flezSwup.navigate('/payroll');
                    else window.location.href = '/payroll';
                }
            });
            return;
        }
    }

    const fields = {
        name: document.getElementById('beneficiary-name'),
        dept: document.getElementById('department'),
        job: document.getElementById('job-title'),
        salary: document.getElementById('base-salary'),
        date: document.getElementById('disbursement-date'),
        bank: document.getElementById('bank-select'),
        account: document.getElementById('account-number')
    };

    // Helper to highlight missing fields
    const missing = [];
    Object.entries(fields).forEach(([key, el]) => {
        if (!el || !el.value || el.value.trim() === '') {
            missing.push(key.charAt(0).toUpperCase() + key.slice(1));
            el?.classList.add('border-rose-500', 'ring-1', 'ring-rose-500/20');
        } else {
            el?.classList.remove('border-rose-500', 'ring-1', 'ring-rose-500/20');
        }
    });

    if (missing.length > 0) {
        Swal.fire({
            title: 'Required Fields',
            text: `Please fill in the following: ${missing.join(', ')}`,
            icon: 'warning',
            customClass: { popup: 'swal2-cuperino' }
        });
        return;
    }

    // Additional numeric validation
    const salary = parseFloat(fields.salary.value);
    if (isNaN(salary) || salary <= 0) {
        Swal.fire('Invalid Salary', 'Base salary must be a positive number.', 'warning');
        fields.salary.classList.add('border-rose-500');
        return;
    }

    const { value: bankCode } = fields.bank;
    const { value: accountNumber } = fields.account;

    // Phase 1: Validation
    if (!payrollState.isValidated) {
        const originalContent = setBtnLoading(btn, 'Validating...');
        try {
            const response = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/data/account/validate`, {
                method: 'POST',
                body: JSON.stringify({ account_number: accountNumber, bank_code: bankCode })
            });
            const result = await response.json();
            
            if (result.status && result.data && result.data.length > 0) {
                payrollState.isValidated = true;
                payrollState.validatedName = result.data[0].account_name;
                
                // Update UI Summary
                document.getElementById('summary-beneficiary-name').textContent = payrollState.validatedName;
                document.getElementById('summary-beneficiary-row').classList.remove('hidden');
                
                // Update Button
                restoreBtn(btn, 'Save Payroll <i data-lucide="check-circle" class="w-5 h-5"></i>');
                
                // Success Toast
                showToast('Validated', 'Account Validated', 'success');
            } else {
                restoreBtn(btn, originalContent);
                Swal.fire('Validation Failed', result.message || 'Could not verify account.', 'error');
            }
        } catch (err) {
            restoreBtn(btn, originalContent);
            Swal.fire('Error', 'Validation service unavailable.', 'error');
        }
        return;
    }

    // Phase 2: Save
    const otpEnabled = isPayrollOtpEnabled();
    let pin = '';
    const originalContent2 = btn.innerHTML; // get current content

    if (otpEnabled) {
        // Request PIN
        setBtnLoading(btn, 'Sending PIN...');
        try {
            await requestPayrollPin();
        } catch (err) {
            restoreBtn(btn, originalContent2);
            Swal.fire('Error', 'Failed to send authorization PIN.', 'error');
            return;
        }
    
        restoreBtn(btn, originalContent2);
    
        pin = await getPinWithCupertinoInput(
            payrollId ? 'Update Record' : 'Save New Record',
            'Enter the 6-digit PIN sent to your email to authorize this change.'
        );
    
        if (!pin) return;
    }

    setBtnLoading(btn, 'Saving...');

    const data = {
        id: payrollId,
        pin: pin,
        account_name: document.getElementById('beneficiary-name').value || payrollState.validatedName,
        pay_amount: document.getElementById('base-salary').value,
        account_number: accountNumber,
        account_id: bankCode,
        description: document.getElementById('job-title').value,
        department: document.getElementById('department').value,
        allowances: document.getElementById('allowances').value,
        deductions: document.getElementById('deductions').value,
        pay_date: document.getElementById('disbursement-date').value,
        pay_status: document.querySelector('.hours-switch')?.getAttribute('aria-checked') === 'true' ? 'active' : 'disabled',
        pay_frequency: document.getElementById('payment-frequency')?.value || 'monthly'
    };

    try {
        const response = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/add/payroll`, {
            method: payrollId ? 'PATCH' : 'POST',
            body: JSON.stringify(data)
        });
        const result = await response.json();
        
        if (result.status) {
            Swal.fire({
                title: 'Success!', text: result.message, icon: 'success', timer: 2000, showConfirmButton: false
            });
            setTimeout(() => { 
                if (window.flezSwup) window.flezSwup.navigate('/payroll');
                else window.location.href = '/payroll';
            }, 2000);
        } else {
            restoreBtn(btn, 'Save Payroll <i data-lucide="check-circle" class="w-5 h-5"></i>');
            Swal.fire('Failed', result.message, 'error');
        }
    } catch (err) {
        restoreBtn(btn, 'Save Payroll <i data-lucide="check-circle" class="w-5 h-5"></i>');
        Swal.fire('Error', 'Communication with server failed.', 'error');
    }
}

async function togglePayrollStatus(btn, id, currentStatus) {
    if (!checkTier2Verification()) {
        Swal.fire({
            icon: 'warning',
            title: 'Verification Required',
            text: 'Tier 2 account verification is required to manage payroll disbursements.',
            confirmButtonText: 'Verify Account',
            showCancelButton: true,
            cancelButtonText: 'Cancel',
            customClass: { popup: 'swal2-cuperino', confirmButton: 'bg-primary', cancelButton: 'bg-slate-700' }
        }).then((result) => {
            if (result.isConfirmed) {
                if (window.flezSwup) window.flezSwup.navigate('/verification');
                else window.location.href = '/verification';
            }
        });
        return;
    }

    if (payrollState.autoPayrollEnabled) {
        Swal.fire({
            title: 'Action Locked',
            text: 'Cannot modify employee disbursement status while Auto Payroll is enabled. Please disable Auto Payroll first.',
            icon: 'warning',
            customClass: { popup: 'swal2-cuperino' }
        });
        return;
    }

    const newStatus = currentStatus === 'active' ? 'disabled' : 'active';
    const actionText = newStatus === 'active' ? 'Enable' : 'Disable';

    const otpEnabled = isPayrollOtpEnabled();
    let pin = '';
    const originalContent = btn.innerHTML;

    if (otpEnabled) {
        setBtnLoading(btn, 'Wait...');
        try {
            await requestPayrollPin();
            restoreBtn(btn, originalContent);
            
            pin = await getPinWithCupertinoInput(
                `${actionText} Employee?`,
                `Enter PIN to ${actionText.toLowerCase()} this employee record.`
            );
    
            if (!pin) return;
        } catch (err) {
            restoreBtn(btn, originalContent);
            Swal.fire('Error', 'Processing failed.', 'error');
            return;
        }
    }
    try {
        setBtnLoading(btn, 'Updating...');
        const response = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/add/payroll`, {
            method: 'PATCH',
            body: JSON.stringify({ id: id, pin: pin, pay_status: newStatus })
        });
        const result = await response.json();
        
        if (result.status) {
            showToast('Updated!', `Status set to ${newStatus}.`, 'success');
            localStorage.removeItem('user_data');
            localStorage.removeItem('last_data_refresh');
            loadPayrollData();
        } else {
            Swal.fire('Failed', result.message, 'error');
            restoreBtn(btn, originalContent);
        }
    } catch (err) {
        restoreBtn(btn, originalContent);
        Swal.fire('Error', 'Network request failed.', 'error');
    }
}

async function loadExistingPayroll(id) {
    try {
        const resp = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/payroll/list?per_page=1000`);
        const data = await resp.json();
        if (data.status) {
            const p = data.data.find(item => String(item.id) === String(id));
            if (p) {
                document.getElementById('beneficiary-name').value = p.account_name || '';
                document.getElementById('base-salary').value = p.pay_amount || 0;
                document.getElementById('account-number').value = p.account_number || '';
                document.getElementById('bank-select').value = p.account_id || '';
                document.getElementById('job-title').value = p.job_title || p.description || '';
                document.getElementById('department').value = p.department || 'Retail Ops';
                document.getElementById('allowances').value = p.allowances || 0;
                document.getElementById('deductions').value = p.deductions || 0;
                document.getElementById('disbursement-date').value = p.pay_date || '';
                
                if (p.pay_frequency && p.pay_frequency !== 'once') {
                    const recurringToggle = document.getElementById('recurring-toggle');
                    if (recurringToggle && recurringToggle.getAttribute('aria-checked') === 'false') {
                        recurringToggle.click();
                    }
                    document.getElementById('payment-frequency').value = p.pay_frequency;
                }
                
                // If editing, we can consider it "validated" if details are same
                payrollState.isValidated = true; 
                if (!checkTier2Verification()) {
                    lockPayrollFormForUnverified(true);
                } else if (payrollState.autoPayrollEnabled) {
                    lockPayrollFormForAutoPayroll();
                } else {
                    restoreBtn(document.getElementById('save-payroll-btn'), 'Save Payroll <i data-lucide="check-circle" class="w-5 h-5"></i>');
                }
                
                window.updateSummary();
            }
        }
    } catch (e) {
        console.error('Failed to load payroll for edit', e);
    }
}

async function deletePayroll(id) {
    if (!checkTier2Verification()) {
        Swal.fire({
            icon: 'warning',
            title: 'Verification Required',
            text: 'Tier 2 account verification is required to manage employee payroll.',
            confirmButtonText: 'Verify Account',
            showCancelButton: true,
            cancelButtonText: 'Cancel',
            customClass: { popup: 'swal2-cuperino', confirmButton: 'bg-primary', cancelButton: 'bg-slate-700' }
        }).then((result) => {
            if (result.isConfirmed) {
                if (window.flezSwup) window.flezSwup.navigate('/verification');
                else window.location.href = '/verification';
            }
        });
        return;
    }

    if (payrollState.autoPayrollEnabled) {
        Swal.fire({
            title: 'Action Locked',
            text: 'Cannot delete employee payroll records while Auto Payroll is enabled. Please disable Auto Payroll first.',
            icon: 'warning',
            customClass: { popup: 'swal2-cuperino' }
        });
        return;
    }

    const confirmation = await Swal.fire({
        title: 'Delete Payroll?', text: 'This action cannot be undone.', icon: 'warning',
        showCancelButton: true, confirmButtonText: 'Delete', cancelButtonText: 'Cancel',
        customClass: { popup: 'swal2-cuperino', confirmButton: 'bg-rose-500', cancelButton: 'bg-slate-700' }
    });

    if (confirmation.isConfirmed) {
        try {
            const resp = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/delete/payroll`, {
                method: 'POST',
                body: JSON.stringify({ id })
            });
            const res = await resp.json();
            if (res.status) {
                Swal.fire('Deleted', 'Record removed.', 'success');
                localStorage.removeItem('user_data');
                localStorage.removeItem('last_data_refresh');
                loadPayrollData();
            } else {
                Swal.fire('Error', res.message || 'Failed to delete payroll', 'error');
            }
        } catch (err) { 
            console.error(err); 
            Swal.fire('Error', 'A network error occurred.', 'error');
        }
    }
}

async function getPinWithCupertinoInput(title, description) {
    const { value: pin } = await Swal.fire({
        title: title,
        html: `
            <div class="text-sm text-slate-400 mb-4">${description}</div>
            <div class="pinput-container" id="pinput-wrapper">
                ${Array(6).fill('<input type="text" maxlength="1" class="pinput-digit" pattern="\\d*">').join('')}
            </div>
        `,
        showCancelButton: true, confirmButtonText: 'Authorize',
        customClass: { popup: 'swal2-cuperino' },
        didOpen: () => {
            const inputs = document.querySelectorAll('#pinput-wrapper input');
            inputs[0].focus();
            inputs.forEach((input, idx) => {
                input.addEventListener('input', (e) => {
                    if (e.target.value && idx < inputs.length - 1) inputs[idx + 1].focus();
                });
                input.addEventListener('keydown', (e) => {
                    if (e.key === 'Backspace' && !e.target.value && idx > 0) inputs[idx - 1].focus();
                });
            });
        },
        preConfirm: () => {
            const pin = Array.from(document.querySelectorAll('#pinput-wrapper input')).map(i => i.value).join('');
            if (pin.length < 6) { Swal.showValidationMessage('Enter 6-digit PIN'); return false; }
            return pin;
        }
    });
    return pin;
}

async function runPayrollFlow(btn) {
    if (!checkTier2Verification()) {
        Swal.fire({
            icon: 'warning',
            title: 'Verification Required',
            text: 'Tier 2 account verification is required to start using payroll and running disbursements.',
            confirmButtonText: 'Verify Account',
            showCancelButton: true,
            cancelButtonText: 'Cancel',
            customClass: { popup: 'swal2-cuperino', confirmButton: 'bg-primary', cancelButton: 'bg-slate-700' }
        }).then((result) => {
            if (result.isConfirmed) {
                if (window.flezSwup) window.flezSwup.navigate('/verification');
                else window.location.href = '/verification';
            }
        });
        return;
    }

    if (window.userData && window.userData.withdrawals_disabled) {
        Swal.fire({
            icon: 'warning',
            title: 'Withdrawals Disabled',
            text: 'Withdrawals have been temporarily disabled for your account. Please contact support for assistance.',
            background: 'var(--swal-bg, #111827)',
            color: 'var(--swal-text, #fff)',
            confirmButtonColor: '#cfff45'
        });
        return;
    }

    const originalContent = btn.innerHTML;
    try {
        const otpEnabled = isPayrollOtpEnabled();
        let pin = '';
        
        if (otpEnabled) {
            // 1. Show immediate loading state while waiting for PIN modal
            setBtnLoading(btn, 'Wait...');
    
            await requestPayrollPin();
            restoreBtn(btn, originalContent); // Wait, restoring here so the modal isn't over a loading button
            pin = await getPinWithCupertinoInput('Run Payroll', 'Enter PIN to authorize total disbursements.');
            
            if (!pin) {
                // User cancelled - Restore original label and exit
                restoreBtn(btn, originalContent);
                return;
            }
        }

        // 2. Full processing state for the network request
        setBtnLoading(btn, 'Processing...');
        const resp = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/payroll/run`, {
            method: 'POST', body: JSON.stringify({ pin })
        });
        const res = await resp.json();
        if (res.status) {
            Swal.fire({ title: 'Success', text: res.message, icon: 'success' });
            localStorage.removeItem('user_data');
            localStorage.removeItem('last_data_refresh');
            loadPayrollData();
        } else {
            Swal.fire({
                icon: resp.status === 403 ? 'warning' : 'error',
                title: resp.status === 403 ? 'Action Restricted' : 'Denied',
                text: res.message,
                background: 'var(--swal-bg, #111827)',
                color: 'var(--swal-text, #fff)',
                confirmButtonColor: '#cfff45'
            });
        }
    } catch (err) { 
        console.error(err); 
        Swal.fire('Error', 'An unexpected error occurred.', 'error');
    } finally {
        btn.disabled = false;
        btn.classList.remove('opacity-70', 'cursor-not-allowed');
        restoreBtn(btn, '<i data-lucide="play" class="w-5 h-5"></i> Run Payroll');
    }
}

async function toggleAutoPayroll(btn) {
    const isEnabled = btn.getAttribute('data-enabled') === 'true';
    const newState = !isEnabled;

    if (newState && !checkTier2Verification()) {
        Swal.fire({
            icon: 'warning',
            title: 'Verification Required',
            text: 'Tier 2 account verification is required to activate automated payroll disbursements.',
            confirmButtonText: 'Verify Account',
            showCancelButton: true,
            cancelButtonText: 'Cancel',
            customClass: { popup: 'swal2-cuperino', confirmButton: 'bg-primary', cancelButton: 'bg-slate-700' }
        }).then((result) => {
            if (result.isConfirmed) {
                if (window.flezSwup) window.flezSwup.navigate('/verification');
                else window.location.href = '/verification';
            }
        });
        return;
    }

    if (newState && window.userData && window.userData.withdrawals_disabled) {
        Swal.fire({
            icon: 'warning',
            title: 'Withdrawals Disabled',
            text: 'Withdrawals have been temporarily disabled for your account. Please contact support for assistance.',
            background: 'var(--swal-bg, #111827)',
            color: 'var(--swal-text, #fff)',
            confirmButtonColor: '#cfff45'
        });
        return;
    }

    const knob = btn.querySelector('#toggle-knob');

    // 1. Immediate Disable & Opacity to prevent multiple clicks
    btn.disabled = true;
    btn.classList.add('opacity-70', 'cursor-not-allowed');

    try {
        const otpEnabled = isPayrollOtpEnabled();
        let pin = '';
        
        if (otpEnabled) {
            // 2. Request PIN for global setting change
            await requestPayrollPin();
            pin = await getPinWithCupertinoInput(
                newState ? 'Enable Auto Payroll?' : 'Disable Auto Payroll?',
                `Enter your 6-digit PIN to authorize this change to your company disbursement settings.`
            );
    
            if (!pin) {
                // User cancelled - Re-enable and exit
                btn.disabled = false;
                btn.classList.remove('opacity-70', 'cursor-not-allowed');
                return;
            }
        }

        // 3. Visual processing state in the knob
        if (knob) {
            // Explicitly set dimensions and background to prevent disappearance
            const bgColor = isEnabled ? 'bg-white' : 'bg-slate-400';
            knob.className = `absolute ${isEnabled ? 'translate-x-5' : 'left-0.5'} top-0.5 w-4 h-4 ${bgColor} rounded-full transition-all duration-300 flex items-center justify-center shadow-sm`;
            // Use a faster, more visible spinner
            knob.innerHTML = '<div style="width: 10px; height: 10px; border: 2px solid rgba(16, 185, 129, 0.2); border-top: 2px solid #10b981; border-radius: 50%; animation: spin-slow 0.6s linear infinite;"></div>';
        }

        const response = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/data/update/settings`, {
            method: 'PATCH',
            body: JSON.stringify({ enable_auto_payroll: newState, pin: pin })
        });
        const result = await response.json();
        
        if (result.status) {
            // Update Local Storage for persistence
            const userData = JSON.parse(localStorage.getItem('user_data') || '{}');
            if (userData.business_details && userData.business_details[0]) {
                userData.business_details[0].enable_auto_payroll = newState;
                localStorage.setItem('user_data', JSON.stringify(userData));
            }
            if (window.userData && window.userData.business_details && window.userData.business_details[0]) {
                window.userData.business_details[0].enable_auto_payroll = newState;
            }
            payrollState.autoPayrollEnabled = newState;

            btn.setAttribute('data-enabled', newState.toString());
            
            // Re-render table and update summary instantly
            loadPayrollData(payrollState.page, payrollState.search); 
            
            showToast('Auto Payroll', newState ? 'Auto Payroll Enabled' : 'Auto Payroll Disabled', 'success');
        } else {
            throw new Error(result.message);
        }
    } catch (err) {
        console.error('Failed to toggle auto payroll:', err);
        Swal.fire('Error', err.message || 'Failed to update auto payroll setting.', 'error');
    } finally {
        btn.disabled = false;
        btn.classList.remove('opacity-70', 'cursor-not-allowed');
        if (knob) {
            knob.innerHTML = '';
            // Restore proper classes based on current (potentially updated) state
            const finalEnabled = btn.getAttribute('data-enabled') === 'true';
            knob.className = `absolute ${finalEnabled ? 'translate-x-5' : 'left-0.5'} top-0.5 w-4 h-4 ${finalEnabled ? 'bg-white' : 'bg-slate-400'} rounded-full transition-all duration-300 shadow-sm`;
        }
    }
}

// Global helpers attached to window for HTML onclicks
window.toggleStaffSearch = function(btn) {
    const checked = btn.getAttribute('aria-checked') === 'true';
    const newChecked = !checked;
    btn.setAttribute('aria-checked', newChecked.toString());
    btn.classList.toggle('bg-primary', newChecked);
    btn.classList.toggle('bg-slate-600', !newChecked);
    const span = btn.querySelector('span:not(.sr-only)') || btn.querySelector('span');
    if (span) span.style.transform = newChecked ? 'translateX(1.0625rem)' : 'translateX(0.0625rem)';
    document.getElementById('staff-search-container')?.classList.toggle('hidden', !newChecked);
};

window.toggleRecurring = function(btn) {
    const checked = btn.getAttribute('aria-checked') === 'true';
    const newChecked = !checked;
    btn.setAttribute('aria-checked', newChecked.toString());
    btn.classList.toggle('bg-primary', newChecked);
    btn.classList.toggle('bg-slate-600', !newChecked);
    const span = btn.querySelector('span:not(.sr-only)') || btn.querySelector('span');
    if (span) span.style.transform = newChecked ? 'translateX(1.0625rem)' : 'translateX(0.0625rem)';
    document.getElementById('frequency-container')?.classList.toggle('hidden', !newChecked);
    updateSummary();
};

window.selectStaff = function(name, role, dept) {
    document.getElementById('beneficiary-name').value = name;
    document.getElementById('job-title').value = role;
    document.getElementById('department').value = dept;
    document.getElementById('staff-search-results').classList.add('hidden');
    document.getElementById('staff-search-input').value = name;
    window.updateSummary();
};

window.updateSummary = function() {
    const base = parseFloat(document.getElementById('base-salary')?.value || 0);
    const allow = parseFloat(document.getElementById('allowances')?.value || 0);
    const deduc = parseFloat(document.getElementById('deductions')?.value || 0);
    const total = base + allow - deduc;
    
    if (document.getElementById('summary-base')) document.getElementById('summary-base').textContent = `${window.STORE_CURRENCY_SYMBOL}${base.toLocaleString()}.00`;
    if (document.getElementById('summary-allowances')) document.getElementById('summary-allowances').textContent = `+ ${window.STORE_CURRENCY_SYMBOL}${allow.toLocaleString()}.00`;
    if (document.getElementById('summary-deductions')) document.getElementById('summary-deductions').textContent = `- ${window.STORE_CURRENCY_SYMBOL}${deduc.toLocaleString()}.00`;
    if (document.getElementById('summary-total')) document.getElementById('summary-total').textContent = `${window.STORE_CURRENCY_SYMBOL}${total.toLocaleString()}.00`;
    
    const date = document.getElementById('disbursement-date')?.value;
    const isRecur = document.getElementById('recurring-toggle')?.getAttribute('aria-checked') === 'true';
    const freq = document.getElementById('payment-frequency')?.value;
    
    const dateInfo = document.getElementById('summary-date-info');
    if (dateInfo) {
        let text = date ? `Scheduled for ${new Date(date).toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'})}` : 'Not Scheduled';
        if (isRecur && date) text = `${freq.charAt(0).toUpperCase() + freq.slice(1)} • Starts ${new Date(date).toLocaleDateString('en-US', {month: 'short', day: 'numeric'})}`;
        dateInfo.textContent = text;
    }
};

async function requestPayrollPin() {
    await apiFetch(`${window.FLEZ_API_BASE || ''}/api/auth/payroll/pin`, { method: 'POST' });
}

function setBtnLoading(btn, text) {
    if (!btn) return '';
    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `
        <span class="flex items-center gap-2 justify-center">
            <div style="width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.2); border-top: 2px solid white; border-radius: 50%; animation: spin-slow 0.6s linear infinite;"></div>
            ${text}
        </span>
    `;
    return original;
}

function restoreBtn(btn, content) {
    if (!btn) return;
    btn.disabled = false;
    btn.innerHTML = content;
    if (window.lucide) lucide.createIcons();
}

function isPayrollOtpEnabled() {
    const userData = JSON.parse(localStorage.getItem('user_data') || '{}');
    if (userData.business_details && userData.business_details.length > 0) {
        const bd = userData.business_details[0];
        if (bd.hasOwnProperty('enable_payroll_otp')) {
            return bd.enable_payroll_otp === true || bd.enable_payroll_otp === 'true' || bd.enable_payroll_otp == 1;
        }
    }
    return true; // default true
}

// Expose globally for dashboard.js
window.initPayroll = initPayroll;

