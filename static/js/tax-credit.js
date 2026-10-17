/**
 * tax-credit.js
 * Controller for FlezPay Tax & Credit Dashboard View
 */

(function(window) {
  'use strict';

  let currentTab = 'tax';
  let currentTaxSubTab = 'overview';
  let currentCreditSubTab = 'overview';
  let isTInMasked = true;
  let currentCountryConfig = null;
  let currentTaxProfile = null;
  let currentTaxSettings = null;

  // Helper to obtain logged-in user currency symbol
  function getUserCurrency() {
    if (typeof window !== 'undefined') {
      if (typeof window.getUserCurrencySymbol === 'function') return window.getUserCurrencySymbol();
      if (window.STORE_CURRENCY_SYMBOL) return window.STORE_CURRENCY_SYMBOL;
    }
    return '₦';
  }

  // Global entry point
  window.initTaxCreditPage = async function() {
    const root = document.getElementById('tax-credit-page');
    if (!root) return;

    // Clean up legacy v1 mock cache to guarantee 0 values & active user currency
    ['flezpay_tax_insights_v1', 'flezpay_credit_plan_v1', 'flezpay_credit_issues_v1', 'flezpay_tax_profile_v1', 'flezpay_tax_docs_v1'].forEach(k => {
      try { localStorage.removeItem(k); } catch (e) {}
    });

    // Detect initial tab from URL query (?tab=credit or ?tab=tax)
    const urlParams = new URLSearchParams(window.location.search);
    const requestedTab = urlParams.get('tab');
    if (requestedTab === 'credit' || requestedTab === 'tax') {
      currentTab = requestedTab;
    } else {
      currentTab = 'tax';
    }

    // Detect initial sub-tabs (?sub=...)
    const requestedSub = urlParams.get('sub');
    if (currentTab === 'tax') {
      if (['overview', 'profile', 'documents', 'settings'].includes(requestedSub)) {
        currentTaxSubTab = requestedSub;
      } else {
        currentTaxSubTab = 'overview';
      }
    } else if (currentTab === 'credit') {
      if (['overview', 'accounts', 'plan', 'disputes', 'agent'].includes(requestedSub)) {
        currentCreditSubTab = requestedSub;
      } else {
        currentCreditSubTab = 'overview';
      }
    }

    setupTabs();
    setupTaxSubTabs();
    setupCreditSubTabs();
    setupMaskToggle();
    setupCountrySelector();
    setupModals();
    setupAIAssistant();
    setupRegionOverlay();

    // Load initial data
    await loadTaxCreditData();

    if (window.lucide) {
      window.lucide.createIcons();
    }
  };

  /**
   * Region Unsupported Notice Interaction Setup
   */
  function setupRegionOverlay() {
    const notifyBtn = document.getElementById('tc-notify-region-btn');
    if (notifyBtn) {
      notifyBtn.onclick = function(e) {
        e.preventDefault();
        if (typeof window.showToast === 'function') {
          window.showToast(
            'Request Registered',
            'We will notify you via email as soon as Tax & Credit becomes active in your region.',
            'success'
          );
        }
        notifyBtn.disabled = true;
        notifyBtn.classList.add('opacity-80', 'cursor-not-allowed');
        notifyBtn.innerHTML = '<i data-lucide="check" class="w-4 h-4 text-emerald-500"></i><span>Request Registered</span>';
        if (window.lucide) {
          window.lucide.createIcons();
        }
      };
    }
  }

  /**
   * Primary Tab Navigation Setup (Tax vs Credit)
   */
  function setupTabs() {
    const tabButtons = document.querySelectorAll('.tax-credit-tab-btn');
    tabButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const tab = btn.getAttribute('data-tab');
        switchTab(tab);
      });
    });

    // Apply active state
    applyTabState(currentTab);
  }

  function switchTab(tab) {
    currentTab = tab;
    applyTabState(tab);

    // Update URL query string without reloading page
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tab);
    const sub = tab === 'tax' ? currentTaxSubTab : currentCreditSubTab;
    url.searchParams.set('sub', sub);
    window.history.replaceState({}, '', url.toString());

    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  function applyTabState(tab) {
    const taxContent = document.getElementById('tax-tab-content');
    const creditContent = document.getElementById('credit-tab-content');
    const tabBtns = document.querySelectorAll('.tax-credit-tab-btn');

    tabBtns.forEach(btn => {
      const btnTab = btn.getAttribute('data-tab');
      if (btnTab === tab) {
        btn.classList.add('bg-primary', 'text-black', 'font-bold', 'shadow-lg', 'shadow-primary/20');
        btn.classList.remove('text-slate-400', 'hover:text-white', 'hover:bg-white/5');
      } else {
        btn.classList.remove('bg-primary', 'text-black', 'font-bold', 'shadow-lg', 'shadow-primary/20');
        btn.classList.add('text-slate-400', 'hover:text-white', 'hover:bg-white/5');
      }
    });

    if (tab === 'tax') {
      if (taxContent) taxContent.classList.remove('hidden');
      if (creditContent) creditContent.classList.add('hidden');
      applyTaxSubTabState(currentTaxSubTab);
    } else {
      if (taxContent) taxContent.classList.add('hidden');
      if (creditContent) creditContent.classList.remove('hidden');
      applyCreditSubTabState(currentCreditSubTab);
    }
  }

  /**
   * Tax Sub-Tabs Setup (Overview, Profile, Documents, Settings)
   */
  function setupTaxSubTabs() {
    const subBtns = document.querySelectorAll('.tax-sub-tab-btn');
    subBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const sub = btn.getAttribute('data-tax-sub');
        switchTaxSubTab(sub);
      });
    });

    applyTaxSubTabState(currentTaxSubTab);
  }

  function switchTaxSubTab(sub) {
    currentTaxSubTab = sub;
    applyTaxSubTabState(sub);

    // Update URL query string
    const url = new URL(window.location.href);
    url.searchParams.set('tab', 'tax');
    url.searchParams.set('sub', sub);
    window.history.replaceState({}, '', url.toString());

    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  function applyTaxSubTabState(sub) {
    const subBtns = document.querySelectorAll('.tax-sub-tab-btn');
    subBtns.forEach(btn => {
      const btnSub = btn.getAttribute('data-tax-sub');
      if (btnSub === sub) {
        btn.classList.add('sub-tab-active', 'bg-orange-500', 'text-white', 'font-bold', 'shadow-md', 'shadow-orange-500/25');
        btn.classList.remove('text-slate-400', 'hover:text-white', 'hover:bg-white/5', 'bg-primary', 'text-black', 'shadow-primary/20');

        // Mobile smooth scroll active button into view within its scroll container
        const scrollParent = btn.closest('.overflow-x-auto');
        if (scrollParent) {
          const parentRect = scrollParent.getBoundingClientRect();
          const btnRect = btn.getBoundingClientRect();
          if (btnRect.left < parentRect.left + 10 || btnRect.right > parentRect.right - 10) {
            scrollParent.scrollTo({
              left: btn.offsetLeft - 12,
              behavior: 'smooth'
            });
          }
        }
      } else {
        btn.classList.remove('sub-tab-active', 'bg-orange-500', 'text-white', 'font-bold', 'shadow-md', 'shadow-orange-500/25', 'bg-primary', 'text-black', 'shadow-primary/20');
        btn.classList.add('text-slate-400', 'hover:text-white', 'hover:bg-white/5');
      }
    });

    const subContents = {
      overview: document.getElementById('tax-sub-overview'),
      profile: document.getElementById('tax-sub-profile'),
      documents: document.getElementById('tax-sub-documents'),
      settings: document.getElementById('tax-sub-settings'),
    };

    Object.keys(subContents).forEach(key => {
      const el = subContents[key];
      if (el) {
        if (key === sub) el.classList.remove('hidden');
        else el.classList.add('hidden');
      }
    });
  }

  /**
   * Credit Sub-Tabs Setup (Overview, Accounts, Plan, Disputes, Agent)
   */
  function setupCreditSubTabs() {
    const subBtns = document.querySelectorAll('.credit-sub-tab-btn');
    subBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const sub = btn.getAttribute('data-credit-sub');
        switchCreditSubTab(sub);
      });
    });

    applyCreditSubTabState(currentCreditSubTab);
  }

  function switchCreditSubTab(sub) {
    currentCreditSubTab = sub;
    applyCreditSubTabState(sub);

    // Update URL query string
    const url = new URL(window.location.href);
    url.searchParams.set('tab', 'credit');
    url.searchParams.set('sub', sub);
    window.history.replaceState({}, '', url.toString());

    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  function applyCreditSubTabState(sub) {
    const subBtns = document.querySelectorAll('.credit-sub-tab-btn');
    subBtns.forEach(btn => {
      const btnSub = btn.getAttribute('data-credit-sub');
      if (btnSub === sub) {
        btn.classList.add('sub-tab-active', 'bg-orange-500', 'text-white', 'font-bold', 'shadow-md', 'shadow-orange-500/25');
        btn.classList.remove('text-slate-400', 'hover:text-white', 'hover:bg-white/5', 'bg-primary', 'text-black', 'shadow-primary/20');

        // Mobile smooth scroll active button into view within its scroll container
        const scrollParent = btn.closest('.overflow-x-auto');
        if (scrollParent) {
          const parentRect = scrollParent.getBoundingClientRect();
          const btnRect = btn.getBoundingClientRect();
          if (btnRect.left < parentRect.left + 10 || btnRect.right > parentRect.right - 10) {
            scrollParent.scrollTo({
              left: btn.offsetLeft - 12,
              behavior: 'smooth'
            });
          }
        }
      } else {
        btn.classList.remove('sub-tab-active', 'bg-orange-500', 'text-white', 'font-bold', 'shadow-md', 'shadow-orange-500/25', 'bg-primary', 'text-black', 'shadow-primary/20');
        btn.classList.add('text-slate-400', 'hover:text-white', 'hover:bg-white/5');
      }
    });

    const subContents = {
      overview: document.getElementById('credit-sub-overview'),
      accounts: document.getElementById('credit-sub-accounts'),
      plan: document.getElementById('credit-sub-plan'),
      disputes: document.getElementById('credit-sub-disputes'),
      agent: document.getElementById('credit-sub-agent'),
    };

    Object.keys(subContents).forEach(key => {
      const el = subContents[key];
      if (el) {
        if (key === sub) el.classList.remove('hidden');
        else el.classList.add('hidden');
      }
    });
  }

  /**
   * Load Data for Both Sections
   */
  async function loadTaxCreditData() {
    showSkeletons(true);
    hideError();

    try {
      // Parallel load of core mock services
      const [
        profile,
        overview,
        filingStatus,
        documents,
        taxInsights,
        taxSettings,
        creditOverview,
        creditFactors,
        creditInsights,
        creditPlan,
        creditAccounts,
        creditIssues,
        agentSettings
      ] = await Promise.all([
        window.TaxCreditService.TaxService.getTaxProfile(),
        window.TaxCreditService.TaxService.getTaxOverview(),
        window.TaxCreditService.TaxService.getFilingStatus(),
        window.TaxCreditService.TaxService.getTaxDocuments(),
        window.TaxCreditService.TaxService.getTaxInsights(),
        window.TaxCreditService.TaxService.getTaxSettings(),
        window.TaxCreditService.CreditService.getCreditOverview(),
        window.TaxCreditService.CreditService.getCreditFactors(),
        window.TaxCreditService.CreditService.getCreditInsights(),
        window.TaxCreditService.CreditService.getCreditActionPlan(),
        window.TaxCreditService.CreditService.getCreditAccounts(),
        window.TaxCreditService.CreditService.getCreditIssues(),
        window.TaxCreditService.FinancialAgentService.getSettings()
      ]);

      currentTaxProfile = profile;
      currentTaxSettings = taxSettings;

      // Render Tax Tab
      renderTaxOverview(overview);
      renderFilingStatus(filingStatus);
      renderTaxInsights(taxInsights);
      await populateCountryForm(profile.country || 'US', profile);
      renderTaxSettings(taxSettings);
      renderTaxDocuments(documents);

      // Render Credit Tab
      renderCreditOverview(creditOverview);
      renderCreditFactors(creditFactors);
      renderCreditInsights(creditInsights);
      renderCreditActionPlan(creditPlan);
      renderCreditAccounts(creditAccounts);
      renderCreditIssues(creditIssues);
      renderAgentSettings(agentSettings);

      showSkeletons(false);

      if (window.lucide) {
        window.lucide.createIcons();
      }
    } catch (err) {
      console.error('Error loading tax/credit data:', err);
      showSkeletons(false);
      showError('Unable to load tax and credit information. Please check your connection and try again.');
    }
  }

  /**
   * Skeleton Loaders & Error States
   * Fixed: Cleanly manages skeleton vs main container, enforcing active tab states on hide.
   */
  function showSkeletons(show) {
    const skeletons = document.getElementById('tc-skeletons');
    const mainContainer = document.getElementById('tc-main-container');

    if (skeletons) {
      if (show) skeletons.classList.remove('hidden');
      else skeletons.classList.add('hidden');
    }

    if (mainContainer) {
      if (show) {
        mainContainer.classList.add('hidden');
      } else {
        mainContainer.classList.remove('hidden');
        // Authoritatively enforce active tab and sub-tab states so reload never shows both
        applyTabState(currentTab);
        if (currentTab === 'tax') {
          applyTaxSubTabState(currentTaxSubTab);
        } else if (currentTab === 'credit') {
          applyCreditSubTabState(currentCreditSubTab);
        }
      }
    }
  }

  function showError(msg) {
    const errContainer = document.getElementById('tc-error-state');
    const errMsg = document.getElementById('tc-error-message');
    if (errContainer) {
      if (errMsg) errMsg.textContent = msg;
      errContainer.classList.remove('hidden');
    }
  }

  function hideError() {
    const errContainer = document.getElementById('tc-error-state');
    if (errContainer) errContainer.classList.add('hidden');
  }

  // Hook retry button
  document.addEventListener('click', (e) => {
    if (e.target && e.target.closest('#tc-retry-btn')) {
      loadTaxCreditData();
    }
  });

  // -------------------------------------------------------------------------
  // RENDER: TAX TAB
  // -------------------------------------------------------------------------

  function renderTaxOverview(overview) {
    const cur = getUserCurrency() || overview.currencySymbol || '₦';
    const incomeEl = document.getElementById('tc-est-income');
    const liabilityEl = document.getElementById('tc-est-liability');
    const deductionsEl = document.getElementById('tc-est-deductions');
    const docsCountEl = document.getElementById('tc-docs-count');

    if (incomeEl) incomeEl.textContent = cur + Number(overview.estimatedTaxableIncome || 0).toLocaleString('en-US', { minimumFractionDigits: 0 });
    if (liabilityEl) liabilityEl.textContent = cur + Number(overview.estimatedTaxLiability || 0).toLocaleString('en-US', { minimumFractionDigits: 0 });
    if (deductionsEl) deductionsEl.textContent = cur + Number(overview.deductibleExpenses || 0).toLocaleString('en-US', { minimumFractionDigits: 0 });
    if (docsCountEl) docsCountEl.textContent = `${overview.taxDocumentsCollected} / ${overview.taxDocumentsRequired}`;
  }

  function renderFilingStatus(status) {
    const yearEl = document.getElementById('tc-filing-year');
    const statusTextEl = document.getElementById('tc-filing-status-text');
    const syncTimeEl = document.getElementById('tc-filing-sync-time');
    const txCountEl = document.getElementById('tc-filing-tx-count');
    const docsCountEl = document.getElementById('tc-filing-docs-count');
    const timelineEl = document.getElementById('tc-filing-timeline');

    if (yearEl) yearEl.textContent = `${status.taxYear} Tax Year`;
    if (statusTextEl) statusTextEl.textContent = status.statusText;
    if (syncTimeEl) syncTimeEl.textContent = status.lastSynchronized;
    if (txCountEl) txCountEl.textContent = Number(status.transactionsAnalyzed).toLocaleString();
    if (docsCountEl) docsCountEl.textContent = `${status.documentsCollected} / ${status.documentsTotal}`;

    if (timelineEl && status.timeline) {
      timelineEl.innerHTML = status.timeline.map((step, idx) => {
        let dotClass = 'bg-slate-700 text-slate-500 border-slate-600';
        let textClass = 'text-slate-400';
        let checkIcon = '<i data-lucide="circle" class="w-3.5 h-3.5"></i>';

        if (step.status === 'completed') {
          dotClass = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
          textClass = 'text-slate-200 font-medium';
          checkIcon = '<i data-lucide="check" class="w-3.5 h-3.5"></i>';
        } else if (step.status === 'active') {
          dotClass = 'bg-primary text-black border-primary shadow-lg shadow-primary/30';
          textClass = 'text-white font-semibold';
          checkIcon = '<i data-lucide="clock" class="w-3.5 h-3.5"></i>';
        }

        const isLast = idx === status.timeline.length - 1;
        const line = !isLast ? `<div class="w-0.5 flex-1 bg-white/10 my-1"></div>` : '';

        return `
          <div class="flex items-start gap-3 relative pb-4 last:pb-0">
            <div class="flex flex-col items-center">
              <div class="w-6 h-6 rounded-full flex items-center justify-center border ${dotClass} shrink-0">
                ${checkIcon}
              </div>
              ${line}
            </div>
            <div class="pt-0.5">
              <p class="text-xs ${textClass}">${step.stage}</p>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  function renderTaxInsights(insights) {
    const listEl = document.getElementById('tc-insights-list');
    const badgeEl = document.getElementById('tc-insights-badge');

    const activeInsights = insights.filter(i => i.status !== 'resolved');
    if (badgeEl) {
      badgeEl.textContent = `${activeInsights.length} detected`;
    }

    if (listEl) {
      if (activeInsights.length === 0) {
        listEl.innerHTML = `
          <div class="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
            <i data-lucide="check-circle" class="w-4 h-4"></i>
            <span>All compliance insights and deductions reviewed!</span>
          </div>
        `;
        return;
      }

      listEl.innerHTML = activeInsights.map(item => {
        let valBadge = '';
        const cur = getUserCurrency();
        if (item.amount !== null && item.amount !== undefined) {
          valBadge = `<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">+${cur}${Number(item.amount || 0).toLocaleString()}</span>`;
        } else if (item.transactionsCount) {
          valBadge = `<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">${item.transactionsCount} txns</span>`;
        }

        return `
          <div class="p-3.5 rounded-xl bg-white/5 border border-white/10 hover:border-white/20 transition-all flex flex-col gap-2">
            <div class="flex items-center justify-between gap-2">
              <span class="text-xs font-semibold text-white truncate">${item.title}</span>
              ${valBadge}
            </div>
            <p class="text-[11px] text-slate-400 leading-relaxed">${item.description}</p>
          </div>
        `;
      }).join('');
    }
  }

  /**
   * Country Configuration & Multi-Section Tax Profile
   */
  async function populateCountryForm(countryCode, existingProfile) {
    currentCountryConfig = await window.TaxCreditService.TaxService.getCountryConfig(countryCode);
    const cfg = currentCountryConfig;

    // Update labels and placeholders dynamically based on country config
    const taxIdLabel = document.getElementById('tc-label-tax-id');
    const taxIdInput = document.getElementById('tc-input-tin');
    const vatLabel = document.getElementById('tc-label-vat');
    const vatInput = document.getElementById('tc-input-vat');
    const regLabel = document.getElementById('tc-label-reg-num');
    const regInput = document.getElementById('tc-input-reg-num');
    const countrySelect = document.getElementById('tc-select-country');
    const taxTypeSelect = document.getElementById('tc-select-tax-type');
    const jurisdictionSelect = document.getElementById('tc-select-jurisdiction');
    const filingPeriodSelect = document.getElementById('tc-select-filing-period');
    const taxRegimeSelect = document.getElementById('tc-select-tax-regime');

    if (taxIdLabel) taxIdLabel.textContent = cfg.taxIdLabel;
    if (taxIdInput) taxIdInput.placeholder = cfg.taxIdPlaceholder;
    if (vatLabel) vatLabel.textContent = cfg.vatLabel;
    if (vatInput) vatInput.placeholder = cfg.vatPlaceholder;
    if (regLabel) regLabel.textContent = cfg.businessRegistrationLabel;
    if (regInput) regInput.placeholder = cfg.businessRegistrationPlaceholder;

    // Country Select
    if (countrySelect) {
      countrySelect.value = cfg.code;
    }

    // Populate Dropdown: Tax Types
    if (taxTypeSelect) {
      taxTypeSelect.innerHTML = cfg.supportedTaxTypes.map(t => `<option value="${t}">${t}</option>`).join('');
    }

    // Populate Dropdown: Jurisdictions
    if (jurisdictionSelect) {
      jurisdictionSelect.innerHTML = cfg.jurisdictions.map(j => `<option value="${j}">${j}</option>`).join('');
    }

    // Populate Dropdown: Filing Periods
    if (filingPeriodSelect) {
      filingPeriodSelect.innerHTML = cfg.filingPeriods.map(f => `<option value="${f}">${f}</option>`).join('');
    }

    // Populate Dropdown: Tax Regimes
    if (taxRegimeSelect) {
      taxRegimeSelect.innerHTML = cfg.taxRegimes.map(r => `<option value="${r}">${r}</option>`).join('');
    }

    // Fill form values from profile (or defaults for that country)
    const profile = existingProfile || cfg.defaultProfile;
    setFormValues(profile, cfg);
  }

  function setFormValues(p, cfg) {
    const setValue = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val || '';
    };

    setValue('tc-input-legal-name', p.legalName || cfg.defaultProfile.legalName);
    setValue('tc-input-trading-name', p.tradingName || cfg.defaultProfile.tradingName);
    setValue('tc-input-reg-num', p.regNumber || cfg.defaultProfile.regNumber);
    setValue('tc-input-industry', p.industry || cfg.defaultProfile.industry);
    setValue('tc-input-state', p.state || cfg.defaultProfile.state);
    setValue('tc-input-city', p.city || cfg.defaultProfile.city);
    setValue('tc-input-address', p.address || cfg.defaultProfile.address);
    setValue('tc-input-postal', p.postalCode || cfg.defaultProfile.postalCode);
    setValue('tc-input-email', p.email || cfg.defaultProfile.email);
    setValue('tc-input-phone', p.phone || cfg.defaultProfile.phone);

    setValue('tc-input-vat', p.vatNumber || cfg.defaultProfile.vatNumber);
    setValue('tc-input-fiscal-start', p.fiscalYearStart || cfg.defaultProfile.fiscalYearStart);
    setValue('tc-input-fiscal-end', p.fiscalYearEnd || cfg.defaultProfile.fiscalYearEnd);
    setValue('tc-input-residency', p.taxResidency || cfg.defaultProfile.taxResidency);

    // Dropdowns
    const selectTaxType = document.getElementById('tc-select-tax-type');
    if (selectTaxType) selectTaxType.value = p.taxEntityType || p.businessType || cfg.supportedTaxTypes[0];

    const selectJurisdiction = document.getElementById('tc-select-jurisdiction');
    if (selectJurisdiction) selectJurisdiction.value = p.jurisdiction || cfg.jurisdictions[0];

    const selectPeriod = document.getElementById('tc-select-filing-period');
    if (selectPeriod) selectPeriod.value = p.filingFrequency || cfg.filingPeriods[0];

    const selectRegime = document.getElementById('tc-select-tax-regime');
    if (selectRegime) selectRegime.value = p.taxRegime || cfg.taxRegimes[0];

    // TIN & Masking
    const rawTin = p.tin || cfg.defaultProfile.tin;
    const tinInput = document.getElementById('tc-input-tin');
    if (tinInput) {
      tinInput.dataset.rawTin = rawTin;
      tinInput.value = isTInMasked ? maskTin(rawTin, cfg) : rawTin;
    }
  }

  function maskTin(rawTin, cfg) {
    if (!rawTin) return '';
    if (rawTin.length <= 4) return '••••';
    const last4 = rawTin.slice(-4);
    return '••••••••' + last4;
  }

  function setupMaskToggle() {
    const toggleBtn = document.getElementById('tc-toggle-tin-mask');
    const tinInput = document.getElementById('tc-input-tin');

    if (toggleBtn && tinInput) {
      toggleBtn.addEventListener('click', (e) => {
        e.preventDefault();
        isTInMasked = !isTInMasked;
        const raw = tinInput.dataset.rawTin || tinInput.value;

        if (isTInMasked) {
          tinInput.value = maskTin(raw, currentCountryConfig);
          toggleBtn.innerHTML = '<i data-lucide="eye" class="w-4 h-4"></i>';
        } else {
          tinInput.value = raw;
          toggleBtn.innerHTML = '<i data-lucide="eye-off" class="w-4 h-4"></i>';
        }
        if (window.lucide) window.lucide.createIcons();
      });

      // Keep rawTin updated if user types while unmasked
      tinInput.addEventListener('input', () => {
        if (!isTInMasked) {
          tinInput.dataset.rawTin = tinInput.value;
        }
      });
    }
  }

  function setupCountrySelector() {
    const countrySelect = document.getElementById('tc-select-country');
    if (countrySelect) {
      countrySelect.onchange = async (e) => {
        const newCode = e.target.value;
        const configs = window.TaxCreditService.COUNTRY_CONFIGS;
        const targetCfg = configs[newCode];
        if (targetCfg) {
          await populateCountryForm(newCode, targetCfg.defaultProfile);
          if (window.showToast) {
            window.showToast('Country Configured', `Tax configuration loaded for ${targetCfg.name}`, 'info');
          }
          if (window.lucide) window.lucide.createIcons();
        }
      };
    }

    // Save Profile Form Submission
    const saveProfileBtn = document.getElementById('tc-save-profile-btn');
    if (saveProfileBtn) {
      saveProfileBtn.onclick = async (e) => {
        e.preventDefault();
        await saveTaxProfile();
      };
    }
  }

  async function saveTaxProfile() {
    const saveBtn = document.getElementById('tc-save-profile-btn');
    const originalText = saveBtn ? saveBtn.innerHTML : '';

    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerHTML = `
        <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-black inline" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
        Saving Profile...
      `;
    }

    try {
      const getValue = (id) => {
        const el = document.getElementById(id);
        return el ? el.value.trim() : '';
      };

      const tinInput = document.getElementById('tc-input-tin');
      const rawTin = tinInput ? (tinInput.dataset.rawTin || tinInput.value) : '';

      const updated = {
        legalName: getValue('tc-input-legal-name'),
        tradingName: getValue('tc-input-trading-name'),
        regNumber: getValue('tc-input-reg-num'),
        tin: rawTin,
        businessType: getValue('tc-select-tax-type'),
        industry: getValue('tc-input-industry'),
        country: getValue('tc-select-country'),
        state: getValue('tc-input-state'),
        city: getValue('tc-input-city'),
        address: getValue('tc-input-address'),
        postalCode: getValue('tc-input-postal'),
        email: getValue('tc-input-email'),
        phone: getValue('tc-input-phone'),
        jurisdiction: getValue('tc-select-jurisdiction'),
        vatNumber: getValue('tc-input-vat'),
        filingFrequency: getValue('tc-select-filing-period'),
        fiscalYearStart: getValue('tc-input-fiscal-start'),
        fiscalYearEnd: getValue('tc-input-fiscal-end'),
        taxEntityType: getValue('tc-select-tax-type'),
        taxResidency: getValue('tc-input-residency'),
        taxRegime: getValue('tc-select-tax-regime')
      };

      await window.TaxCreditService.TaxService.updateTaxProfile(updated);
      currentTaxProfile = updated;

      if (window.showToast) {
        window.showToast('Tax Profile Updated', 'Business and tax compliance information saved.', 'success');
      }
    } catch (err) {
      console.error('Error saving tax profile:', err);
      if (window.showToast) {
        window.showToast('Save Failed', 'Unable to save profile changes.', 'error');
      }
    } finally {
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i data-lucide="save" class="w-4 h-4"></i><span>Save Tax Profile</span>';
        if (window.lucide) window.lucide.createIcons();
      }
    }
  }

  function renderTaxSettings(settings) {
    const realtimeToggle = document.getElementById('tc-toggle-realtime-invoicing');
    const realtimeStatus = document.getElementById('tc-realtime-status-pill');
    const autoTaxToggle = document.getElementById('tc-toggle-auto-filing');
    const authLevelsContainer = document.getElementById('tc-auth-level-container');

    if (realtimeToggle) {
      realtimeToggle.checked = !!settings.realtimeInvoicing;
      updateRealtimeStatus(settings.realtimeInvoicing);

      realtimeToggle.onchange = async () => {
        const isEnabled = realtimeToggle.checked;
        updateRealtimeStatus(isEnabled);
        await window.TaxCreditService.TaxService.updateTaxSettings({ realtimeInvoicing: isEnabled });
        if (window.showToast) {
          window.showToast('Real-time Invoicing', isEnabled ? 'Automated invoice compliance sync activated.' : 'Real-time synchronization paused.', isEnabled ? 'success' : 'info');
        }
      };
    }

    if (autoTaxToggle) {
      autoTaxToggle.checked = !!settings.autonomousTaxFiling;
      if (authLevelsContainer) {
        if (settings.autonomousTaxFiling) authLevelsContainer.classList.remove('opacity-50', 'pointer-events-none');
        else authLevelsContainer.classList.add('opacity-50', 'pointer-events-none');
      }

      autoTaxToggle.onchange = async () => {
        const isEnabled = autoTaxToggle.checked;
        if (authLevelsContainer) {
          if (isEnabled) authLevelsContainer.classList.remove('opacity-50', 'pointer-events-none');
          else authLevelsContainer.classList.add('opacity-50', 'pointer-events-none');
        }
        await window.TaxCreditService.TaxService.updateTaxSettings({ autonomousTaxFiling: isEnabled });
        if (window.showToast) {
          window.showToast('Autonomous Tax Intelligence', isEnabled ? 'Continuous tax filing preparation enabled.' : 'Autonomous preparation turned off.', isEnabled ? 'success' : 'info');
        }
      };
    }

    // Authorization level radio inputs
    const authRadios = document.querySelectorAll('input[name="tc_auth_level"]');
    authRadios.forEach(radio => {
      if (radio.value === settings.authorizationLevel) {
        radio.checked = true;
      }
      radio.onchange = async () => {
        if (radio.checked) {
          await window.TaxCreditService.TaxService.updateTaxSettings({ authorizationLevel: radio.value });
          if (window.showToast) {
            window.showToast('Authorization Updated', `Filing permission set to ${radio.value.replace('_', ' ')}`, 'info');
          }
        }
      };
    });
  }

  function updateRealtimeStatus(active) {
    const pill = document.getElementById('tc-realtime-status-pill');
    if (!pill) return;
    if (active) {
      pill.innerHTML = `
        <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
        <span class="text-xs font-semibold text-emerald-400">Active</span>
      `;
      pill.className = 'flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20';
    } else {
      pill.innerHTML = `
        <span class="w-2 h-2 rounded-full bg-slate-500"></span>
        <span class="text-xs font-semibold text-slate-400">Inactive</span>
      `;
      pill.className = 'flex items-center gap-2 px-2.5 py-1 rounded-full bg-white/5 border border-white/10';
    }
  }

  function renderTaxDocuments(docs) {
    const tbody = document.getElementById('tc-docs-tbody');
    if (!tbody) return;

    tbody.innerHTML = docs.map(doc => {
      const isVerified = doc.verified;
      const statusBadge = isVerified
        ? `<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
             <i data-lucide="check" class="w-3 h-3"></i> Verified
           </span>`
        : `<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
             <i data-lucide="clock" class="w-3 h-3"></i> Pending
           </span>`;

      return `
        <tr class="hover:bg-white/[0.02] transition-colors border-b border-white/5 last:border-0">
          <td class="px-6 py-4">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-slate-400">
                <i data-lucide="file-text" class="w-4 h-4"></i>
              </div>
              <div>
                <p class="text-sm font-semibold text-white">${doc.name}</p>
                <p class="text-xs text-slate-500">${doc.type}</p>
              </div>
            </div>
          </td>
          <td class="px-6 py-4 text-xs text-slate-400">${doc.date}</td>
          <td class="px-6 py-4 text-xs text-slate-400">${doc.count}</td>
          <td class="px-6 py-4">${statusBadge}</td>
        </tr>
      `;
    }).join('');
  }

  // -------------------------------------------------------------------------
  // RENDER: CREDIT TAB
  // -------------------------------------------------------------------------

  function renderCreditOverview(credit) {
    const scoreValEl = document.getElementById('tc-credit-score-val');
    const scoreRatingEl = document.getElementById('tc-credit-score-rating');
    const scoreDeltaEl = document.getElementById('tc-credit-score-delta');
    const scoreArcEl = document.getElementById('tc-credit-gauge-arc');

    if (scoreValEl) scoreValEl.textContent = credit.score;
    if (scoreRatingEl) scoreRatingEl.textContent = credit.rating;
    if (scoreDeltaEl) scoreDeltaEl.innerHTML = `↑ ${credit.changePoints} ${credit.changePeriod}`;

    // SVG Gauge calculation: 300 to 850 scale mapped to 0% to 100% of arc
    if (scoreArcEl) {
      const percentage = Math.min(Math.max((credit.score - 300) / (850 - 300), 0), 1);
      const dashOffset = 440 - (percentage * 220);
      scoreArcEl.style.strokeDashoffset = dashOffset;
    }

    // Quick Factor Matrix
    const f = credit.summaryFactors;
    if (f) {
      const setQuickFactor = (id, text, ratingClass) => {
        const el = document.getElementById(id);
        if (el) {
          el.textContent = text;
          if (ratingClass) el.className = `text-xs font-bold ${ratingClass}`;
        }
      };

      setQuickFactor('tc-qf-payment', `${f.paymentHistory.rating} (${f.paymentHistory.score})`, 'text-emerald-400');
      setQuickFactor('tc-qf-utilization', `${f.creditUtilization.rating} (${f.creditUtilization.score})`, 'text-amber-400');
      setQuickFactor('tc-qf-age', `${f.creditAge.rating} (${f.creditAge.score})`, 'text-emerald-400');
      setQuickFactor('tc-qf-mix', `${f.creditMix.rating} (${f.creditMix.score})`, 'text-indigo-400');
      setQuickFactor('tc-qf-inquiries', `${f.newApplications.rating} (${f.newApplications.score})`, 'text-emerald-400');
    }
  }

  function renderCreditFactors(factors) {
    const grid = document.getElementById('tc-factors-grid');
    if (!grid) return;

    grid.innerHTML = factors.map(f => {
      let badgeColor = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      let barColor = 'bg-emerald-500';

      if (f.statusClass === 'amber') {
        badgeColor = 'bg-amber-500/10 text-amber-400 border-amber-500/20';
        barColor = 'bg-amber-500';
      } else if (f.statusClass === 'indigo') {
        badgeColor = 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
        barColor = 'bg-indigo-500';
      }

      return `
        <div class="glass-card rounded-2xl p-5 border border-white/5 flex flex-col justify-between space-y-4 hover:border-white/15 transition-all">
          <div class="space-y-2">
            <div class="flex items-center justify-between gap-2">
              <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">${f.name}</span>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-bold border ${badgeColor}">${f.rating}</span>
            </div>
            <div class="flex items-baseline gap-2">
              <span class="text-2xl font-display font-bold text-white">${f.value}</span>
              <span class="text-[11px] text-slate-500 font-medium">${f.impact}</span>
            </div>
          </div>

          <div class="space-y-2">
            <div class="w-full bg-white/5 rounded-full h-1.5 overflow-hidden">
              <div class="${barColor} h-1.5 rounded-full transition-all duration-700" style="width: ${f.progressBar}%"></div>
            </div>
            <p class="text-[11px] text-slate-400 leading-relaxed">${f.description}</p>
          </div>
        </div>
      `;
    }).join('');
  }

  function renderCreditInsights(insights) {
    const list = document.getElementById('tc-credit-insights-list');
    if (!list) return;

    list.innerHTML = insights.map(item => {
      return `
        <div class="p-5 rounded-2xl bg-white/[0.03] border border-white/10 hover:border-white/20 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div class="flex items-start gap-4">
            <span class="font-display font-bold text-xl text-primary shrink-0">${item.number}</span>
            <div class="space-y-1">
              <div class="flex items-center gap-2">
                <h4 class="text-sm font-bold text-white">${item.title}</h4>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-white/10 text-slate-300">${item.badge}</span>
              </div>
              <p class="text-xs text-slate-300 font-medium">${item.currentMetric}</p>
              <p class="text-xs text-slate-400 leading-relaxed">${item.recommendedAction}</p>
              <p class="text-[11px] text-emerald-400/90 pt-1 flex items-center gap-1">
                <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
                <span>Potential benefit: ${item.potentialBenefit}</span>
              </p>
            </div>
          </div>
          <button data-action-target="${item.targetView}" class="tc-insight-action-btn shrink-0 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 text-white rounded-xl text-xs font-semibold transition-all">
            ${item.buttonText}
          </button>
        </div>
      `;
    }).join('');
  }

  function renderCreditActionPlan(plan) {
    const progressEl = document.getElementById('tc-plan-progress-percent');
    const progressBarEl = document.getElementById('tc-plan-progress-bar');
    const listEl = document.getElementById('tc-plan-items-list');

    if (progressEl) progressEl.textContent = `${plan.completionPercentage}% complete`;
    if (progressBarEl) progressBarEl.style.width = `${plan.completionPercentage}%`;

    if (listEl) {
      listEl.innerHTML = plan.items.map(item => {
        const isChecked = item.completed;
        const icon = isChecked ? '<i data-lucide="check" class="w-3.5 h-3.5 text-black"></i>' : '';
        const boxClass = isChecked ? 'bg-primary border-primary' : 'bg-transparent border-slate-600 hover:border-white';
        const titleClass = isChecked ? 'line-through text-slate-500' : 'text-slate-200 font-medium';

        return `
          <div class="p-3.5 rounded-xl bg-white/[0.02] border border-white/5 hover:border-white/10 flex items-start gap-3.5 cursor-pointer transition-all tc-plan-toggle" data-plan-id="${item.id}">
            <div class="w-5 h-5 rounded-md border flex items-center justify-center shrink-0 mt-0.5 transition-colors ${boxClass}">
              ${icon}
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="text-[10px] uppercase font-bold text-slate-500 tracking-wider">${item.week}</span>
                <span class="text-xs ${titleClass}">${item.title}</span>
              </div>
              <p class="text-[11px] text-slate-500 mt-0.5 leading-relaxed">${item.desc}</p>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  function renderCreditAccounts(data) {
    const tbody = document.getElementById('tc-accounts-tbody');
    const updatedEl = document.getElementById('tc-accounts-updated');

    if (updatedEl) updatedEl.textContent = `Last updated: ${data.lastUpdated}`;
    if (!tbody) return;

    const cur = getUserCurrency();

    tbody.innerHTML = data.accounts.map(acc => {
      const limitText = (acc.limit !== null && acc.limit !== undefined) ? `${cur}${Number(acc.limit).toLocaleString()}` : '—';
      const utilText = acc.utilization;
      const statusBadge = acc.statusClass === 'amber'
        ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">${acc.status}</span>`
        : `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">${acc.status}</span>`;

      return `
        <tr class="hover:bg-white/[0.02] transition-colors border-b border-white/5 last:border-0">
          <td class="px-6 py-4">
            <div>
              <p class="text-sm font-semibold text-white">${acc.name}</p>
              <p class="text-xs text-slate-500">${acc.type} • Last paid ${acc.lastPayment}</p>
            </div>
          </td>
          <td class="px-6 py-4 text-xs font-semibold text-slate-200">${cur}${Number(acc.balance || 0).toLocaleString()}</td>
          <td class="px-6 py-4 text-xs text-slate-400">${limitText}</td>
          <td class="px-6 py-4 text-xs font-semibold text-slate-200">${utilText}</td>
          <td class="px-6 py-4">${statusBadge}</td>
        </tr>
      `;
    }).join('');
  }

  function renderCreditIssues(issue) {
    const card = document.getElementById('tc-issue-card');
    if (!card) return;

    const isDisputed = issue.status === 'disputed';
    const statusPill = isDisputed
      ? `<span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">Dispute In Review (${issue.disputeReference || 'REF-82194'})</span>`
      : `<span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">Action Required</span>`;

    const actionBtn = isDisputed
      ? `<button class="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-xs font-bold text-slate-400 cursor-default">Dispute Submitted</button>`
      : `<button id="tc-review-discrepancy-btn" class="px-4 py-2 bg-rose-500 hover:bg-rose-600 text-white rounded-xl text-xs font-bold shadow-lg shadow-rose-500/20 transition-all">Review & Prepare Dispute</button>`;

    const cur = getUserCurrency();

    card.innerHTML = `
      <div class="space-y-4">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
              <i data-lucide="alert-triangle" class="w-4 h-4"></i>
            </div>
            <div>
              <h4 class="text-sm font-bold text-white">${issue.title}</h4>
              <p class="text-xs text-slate-400">${issue.accountName}</p>
            </div>
          </div>
          ${statusPill}
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4 rounded-xl bg-white/[0.02] border border-white/5">
          <div>
            <span class="text-[11px] text-slate-500 uppercase tracking-wider block">Bureau Reported</span>
            <span class="text-base font-display font-bold text-white">${cur}${Number(issue.reportedAmount || 0).toLocaleString()}</span>
          </div>
          <div>
            <span class="text-[11px] text-slate-500 uppercase tracking-wider block">Connected FlezPay Ledger</span>
            <span class="text-base font-display font-bold text-emerald-400">${cur}${Number(issue.connectedLedgerAmount || 0).toLocaleString()}</span>
          </div>
          <div>
            <span class="text-[11px] text-slate-500 uppercase tracking-wider block">Variance</span>
            <span class="text-base font-display font-bold text-rose-400">+${cur}${Number(issue.difference || 0).toLocaleString()}</span>
          </div>
        </div>

        <p class="text-xs text-slate-400 leading-relaxed">${issue.explanation}</p>

        <div class="flex justify-end pt-1">
          ${actionBtn}
        </div>
      </div>
    `;
  }

  function renderAgentSettings(settings) {
    const bindToggle = (id, key) => {
      const el = document.getElementById(id);
      if (el) {
        el.checked = !!settings[key];
        el.onchange = async () => {
          // Special confirmation for automatic payments
          if (key === 'automaticPayments' && el.checked) {
            el.checked = false; // revert until confirmed
            openAutoPaymentsWarningModal();
            return;
          }

          await window.TaxCreditService.FinancialAgentService.updateSettings({ [key]: el.checked });
          if (window.showToast) {
            window.showToast('Financial Agent', 'Automation setting updated.', 'info');
          }
        };
      }
    };

    bindToggle('tc-agent-reminders', 'paymentReminders');
    bindToggle('tc-agent-bill-opt', 'billOptimization');
    bindToggle('tc-agent-utilization', 'utilizationMonitoring');
    bindToggle('tc-agent-tax-deadlines', 'taxDeadlineMonitoring');
    bindToggle('tc-agent-tax-prep', 'taxPreparation');
    bindToggle('tc-agent-autopay', 'automaticPayments');
  }

  // -------------------------------------------------------------------------
  // MODALS & EVENT DELEGATION
  // -------------------------------------------------------------------------

  function setupModals() {
    // 1. Review Filing Modal Trigger
    document.addEventListener('click', async (e) => {
      if (e.target && e.target.closest('#tc-review-filing-btn')) {
        openReviewFilingModal();
      }
    });

    // 2. AI Tax Insights Modal Trigger
    document.addEventListener('click', async (e) => {
      if (e.target && e.target.closest('#tc-review-insights-btn')) {
        openTaxInsightsModal();
      }
    });

    // 3. Document Upload Modal Trigger
    document.addEventListener('click', (e) => {
      if (e.target && e.target.closest('#tc-upload-doc-btn')) {
        openUploadDocModal();
      }
    });

    // 4. Action plan item toggle
    document.addEventListener('click', async (e) => {
      const toggle = e.target.closest('.tc-plan-toggle');
      if (toggle) {
        const id = toggle.getAttribute('data-plan-id');
        if (id) {
          const updatedPlan = await window.TaxCreditService.CreditService.toggleActionPlanItem(id);
          renderCreditActionPlan(updatedPlan);
          if (window.lucide) window.lucide.createIcons();
        }
      }
    });

    // 5. Credit Insight Action Buttons
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.tc-insight-action-btn');
      if (btn) {
        const target = btn.getAttribute('data-action-target');
        if (target === 'action_plan') {
          const planSection = document.getElementById('tc-action-plan-container');
          if (planSection) planSection.scrollIntoView({ behavior: 'smooth' });
        } else if (target === 'payment_review') {
          openPaymentReviewModal();
        } else if (target === 'dispute_review') {
          openDisputeModal();
        }
      }
    });

    // 6. Review Discrepancy Button
    document.addEventListener('click', (e) => {
      if (e.target && e.target.closest('#tc-review-discrepancy-btn')) {
        openDisputeModal();
      }
    });

    // Universal Modal Closer
    document.addEventListener('click', (e) => {
      if (e.target.matches('.tc-modal-backdrop') || e.target.closest('.tc-modal-close-btn')) {
        closeAllModals();
      }
    });
  }

  function closeAllModals() {
    document.querySelectorAll('.tc-modal').forEach(m => m.classList.add('hidden'));
  }

  // MODAL 1: Filing Review
  async function openReviewFilingModal() {
    const modal = document.getElementById('tc-modal-filing-review');
    if (!modal) return;

    const summary = await window.TaxCreditService.TaxService.getFilingSummary();
    const cur = getUserCurrency() || summary.currencySymbol || '₦';
    const content = document.getElementById('tc-filing-modal-content');
    if (content) {
      content.innerHTML = `
        <div class="space-y-6">
          <div class="p-4 rounded-2xl bg-slate-50 dark:bg-white/[0.02] border border-slate-200 dark:border-white/5 space-y-3">
            <div class="flex justify-between text-xs pb-2 border-b border-slate-200 dark:border-white/5">
              <span class="text-slate-500 dark:text-slate-400">Entity Prepared</span>
              <span class="font-semibold text-slate-900 dark:text-white">${summary.preparedFor} (${summary.entityType})</span>
            </div>
            <div class="flex justify-between text-xs pb-2 border-b border-slate-200 dark:border-white/5">
              <span class="text-slate-500 dark:text-slate-400">Gross Revenue (Form 1120 L1a)</span>
              <span class="font-semibold text-slate-900 dark:text-white">${cur}${Number(summary.grossRevenue || 0).toLocaleString()}</span>
            </div>
            <div class="flex justify-between text-xs pb-2 border-b border-slate-200 dark:border-white/5">
              <span class="text-slate-500 dark:text-slate-400">Cost of Goods Sold (L2)</span>
              <span class="font-semibold text-slate-700 dark:text-slate-300">-${cur}${Number(summary.costOfGoods || 0).toLocaleString()}</span>
            </div>
            <div class="flex justify-between text-xs pb-2 border-b border-slate-200 dark:border-white/5">
              <span class="text-slate-500 dark:text-slate-400">Allowed Operating Deductions</span>
              <span class="font-semibold text-slate-700 dark:text-slate-300">-${cur}${Number(summary.operatingExpenses || 0).toLocaleString()}</span>
            </div>
            <div class="flex justify-between text-xs pt-1 pb-2 border-b border-slate-200 dark:border-white/10 font-bold">
              <span class="text-slate-900 dark:text-white">Estimated Net Taxable Base</span>
              <span class="text-primary font-display text-base">${cur}${Number(summary.netTaxableIncome || 0).toLocaleString()}</span>
            </div>
            <div class="flex justify-between text-xs pb-2 border-b border-slate-200 dark:border-white/5">
              <span class="text-slate-500 dark:text-slate-400">Federal Rate (0%) + State (${summary.stateEstimatedRate}%)</span>
              <span class="text-slate-700 dark:text-slate-300">${cur}${Number(summary.totalEstimatedTaxDue || 0).toLocaleString()}</span>
            </div>
            <div class="flex justify-between text-xs pb-2 border-b border-slate-200 dark:border-white/5">
              <span class="text-slate-500 dark:text-slate-400">Prepaid Quarterly Credits / Withholding</span>
              <span class="text-emerald-600 dark:text-emerald-400 font-semibold">-${cur}${Number(summary.prepaidCredits || 0).toLocaleString()}</span>
            </div>
            <div class="flex justify-between text-sm font-bold pt-1">
              <span class="text-slate-900 dark:text-white">Net Estimated Balance Remaining</span>
              <span class="text-slate-900 dark:text-white font-display text-lg">${cur}${Number(summary.balanceRemaining || 0).toLocaleString()}</span>
            </div>
          </div>

          <div class="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 text-amber-800 dark:text-amber-300 text-[11px] leading-relaxed">
            <p class="font-semibold mb-1">Simulated Filing Preview</p>
            ${summary.disclaimer}
          </div>

          <div class="flex items-center justify-end gap-3 pt-2">
            <button class="tc-modal-close-btn px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 text-slate-700 dark:text-white border border-slate-200 dark:border-white/10 rounded-xl text-xs font-semibold transition-colors">
              Close
            </button>
            <button id="tc-mock-export-filing" class="px-4 py-2 bg-primary text-black hover:bg-primary/90 rounded-xl text-xs font-bold shadow-lg shadow-primary/20 flex items-center gap-2">
              <i data-lucide="printer" class="w-3.5 h-3.5"></i>
              <span>Export Mock Filing Summary</span>
            </button>
          </div>
        </div>
      `;

      const exportBtn = content.querySelector('#tc-mock-export-filing');
      if (exportBtn) {
        exportBtn.addEventListener('click', () => {
          if (window.showToast) {
            window.showToast('Export Generated', 'Filing worksheet ready for review.', 'success');
          }
          closeAllModals();
        });
      }
    }

    modal.classList.remove('hidden');
    if (window.lucide) window.lucide.createIcons();
  }

  // MODAL 2: Tax Insights Review
  async function openTaxInsightsModal() {
    const modal = document.getElementById('tc-modal-insights-review');
    if (!modal) return;

    const insights = await window.TaxCreditService.TaxService.getTaxInsights();
    const cur = getUserCurrency();
    const content = document.getElementById('tc-insights-modal-content');

    if (content) {
      content.innerHTML = `
        <div class="space-y-4">
          <p class="text-xs text-slate-600 dark:text-slate-400">
            FlezPay Intelligence scanned 1,248 transactions and highlighted the following compliance adjustments:
          </p>

          <div class="space-y-3 max-h-96 overflow-y-auto pr-1">
            ${insights.map(item => {
              const isResolved = item.status === 'resolved';
              const btnHtml = isResolved
                ? `<span class="text-xs text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1"><i data-lucide="check" class="w-3.5 h-3.5"></i> Resolved</span>`
                : `<button class="tc-resolve-insight-btn px-3 py-1.5 bg-primary text-black rounded-lg text-xs font-bold hover:bg-primary/90 cursor-pointer" data-insight-id="${item.id}">
                     ${item.actionLabel}
                   </button>`;

              return `
                <div class="p-4 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-200 dark:border-white/5 flex flex-col gap-3">
                  <div class="flex items-center justify-between gap-2">
                    <span class="text-sm font-bold text-slate-900 dark:text-white">${item.title}</span>
                    ${(item.amount !== null && item.amount !== undefined) ? `<span class="text-xs font-bold text-emerald-600 dark:text-emerald-400">+${cur}${Number(item.amount).toLocaleString()}</span>` : ''}
                  </div>
                  <p class="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">${item.description}</p>
                  <div class="flex justify-end pt-1">
                    ${btnHtml}
                  </div>
                </div>
              `;
            }).join('')}
          </div>

          <div class="flex justify-end pt-2 border-t border-slate-200 dark:border-white/5">
            <button class="tc-modal-close-btn px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 text-slate-700 dark:text-white border border-slate-200 dark:border-white/10 rounded-xl text-xs font-semibold transition-colors">
              Done
            </button>
          </div>
        </div>
      `;

      content.querySelectorAll('.tc-resolve-insight-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          const id = btn.getAttribute('data-insight-id');
          await window.TaxCreditService.TaxService.resolveTaxInsight(id);
          const updated = await window.TaxCreditService.TaxService.getTaxInsights();
          renderTaxInsights(updated);
          openTaxInsightsModal(); // Refresh modal
          if (window.showToast) {
            window.showToast('Insight Resolved', 'Adjustment applied to mock tax ledger.', 'success');
          }
        });
      });
    }

    modal.classList.remove('hidden');
    if (window.lucide) window.lucide.createIcons();
  }

  // MODAL 3: Document Upload
  function openUploadDocModal() {
    const modal = document.getElementById('tc-modal-doc-upload');
    if (!modal) return;

    modal.classList.remove('hidden');
    const form = document.getElementById('tc-doc-upload-form');
    if (form) {
      form.onsubmit = async (e) => {
        e.preventDefault();
        const nameInput = document.getElementById('tc-upload-doc-name');
        const typeSelect = document.getElementById('tc-upload-doc-type');

        const name = nameInput ? nameInput.value.trim() : 'Financial Statement.pdf';
        const type = typeSelect ? typeSelect.value : 'Supplementary Evidence';

        await window.TaxCreditService.TaxService.uploadTaxDocument({
          name: name || 'Financial Document.pdf',
          type: type,
          size: '2.4 MB'
        });

        const updatedDocs = await window.TaxCreditService.TaxService.getTaxDocuments();
        renderTaxDocuments(updatedDocs);
        closeAllModals();

        if (window.showToast) {
          window.showToast('Document Uploaded', `${name} uploaded and added to filing records.`, 'success');
        }
        if (window.lucide) window.lucide.createIcons();
      };
    }
    if (window.lucide) window.lucide.createIcons();
  }

  // MODAL 4: Dispute Preparation
  async function openDisputeModal() {
    const modal = document.getElementById('tc-modal-dispute');
    if (!modal) return;

    const issue = await window.TaxCreditService.CreditService.getCreditIssues();
    const cur = getUserCurrency();
    const content = document.getElementById('tc-dispute-modal-content');

    if (content) {
      content.innerHTML = `
        <div class="space-y-4">
          <p class="text-xs text-slate-600 dark:text-slate-400">
            FlezPay has assembled transaction records demonstrating an apparent discrepancy in reported revolving credit balances.
          </p>

          <div class="p-4 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-200 dark:border-white/5 space-y-2 text-xs">
            <div class="flex justify-between">
              <span class="text-slate-500 dark:text-slate-400">Account</span>
              <span class="text-slate-900 dark:text-white font-semibold">${issue.accountName}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500 dark:text-slate-400">Bureau Reported Balance</span>
              <span class="text-slate-900 dark:text-white font-semibold">${cur}${Number(issue.reportedAmount || 0).toLocaleString()}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500 dark:text-slate-400">Ledger Verified Balance</span>
              <span class="text-emerald-600 dark:text-emerald-400 font-semibold">${cur}${Number(issue.connectedLedgerAmount || 0).toLocaleString()}</span>
            </div>
            <div class="flex justify-between font-bold border-t border-slate-200 dark:border-white/5 pt-2">
              <span class="text-slate-700 dark:text-slate-300">Discrepancy</span>
              <span class="text-rose-600 dark:text-rose-400">+${cur}${Number(issue.difference || 0).toLocaleString()}</span>
            </div>
          </div>

          <div class="space-y-2">
            <label class="block text-xs font-semibold text-slate-700 dark:text-slate-300">Dispute Reason</label>
            <select id="tc-dispute-reason" class="w-full bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-primary">
              <option value="payment_cleared_before_closing" class="bg-white dark:bg-[#1f2638] text-slate-900 dark:text-white">Payment cleared prior to statement cutoff date</option>
              <option value="duplicate_transaction" class="bg-white dark:bg-[#1f2638] text-slate-900 dark:text-white">Duplicate posting of merchant fee</option>
              <option value="incorrect_balance" class="bg-white dark:bg-[#1f2638] text-slate-900 dark:text-white">Inaccurate balance reported by bureau furnisher</option>
            </select>
          </div>

          <div class="space-y-2">
            <label class="block text-xs font-semibold text-slate-700 dark:text-slate-300">Attached Evidence</label>
            <div class="p-3 rounded-lg bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 flex items-center justify-between text-xs">
              <span class="text-slate-700 dark:text-slate-300 truncate">Aug 28, 2026 - ${cur}0.00 Cleared Payment Record Txn #891</span>
              <span class="text-emerald-600 dark:text-emerald-400 font-bold">Attached</span>
            </div>
          </div>

          <div class="flex items-center justify-end gap-3 pt-2">
            <button class="tc-modal-close-btn px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 text-slate-700 dark:text-white border border-slate-200 dark:border-white/10 rounded-xl text-xs font-semibold transition-colors">
              Cancel
            </button>
            <button id="tc-submit-dispute-btn" class="px-4 py-2 bg-rose-500 hover:bg-rose-600 text-white rounded-xl text-xs font-bold shadow-lg shadow-rose-500/20">
              Submit Mock Dispute
            </button>
          </div>
        </div>
      `;

      const submitBtn = content.querySelector('#tc-submit-dispute-btn');
      if (submitBtn) {
        submitBtn.addEventListener('click', async () => {
          const reason = document.getElementById('tc-dispute-reason')?.value;
          submitBtn.disabled = true;
          submitBtn.textContent = 'Submitting...';

          const updatedIssue = await window.TaxCreditService.CreditService.submitCreditDispute(issue.id, { reason });
          renderCreditIssues(updatedIssue);
          closeAllModals();

          if (window.showToast) {
            window.showToast('Dispute Submitted', 'Mock dispute packet generated and transmitted for review.', 'success');
          }
          if (window.lucide) window.lucide.createIcons();
        });
      }
    }

    modal.classList.remove('hidden');
    if (window.lucide) window.lucide.createIcons();
  }

  // MODAL 5: Payment Review Modal
  function openPaymentReviewModal() {
    const modal = document.getElementById('tc-modal-payment-review');
    if (!modal) return;
    modal.classList.remove('hidden');
    if (window.lucide) window.lucide.createIcons();
  }

  // MODAL 6: High Risk Auto-Payments Warning Modal
  function openAutoPaymentsWarningModal() {
    const modal = document.getElementById('tc-modal-autopay-warning');
    if (!modal) return;

    modal.classList.remove('hidden');
    const confirmBtn = document.getElementById('tc-confirm-autopay-btn');
    if (confirmBtn) {
      confirmBtn.onclick = async () => {
        await window.TaxCreditService.FinancialAgentService.updateSettings({ automaticPayments: true });
        const toggle = document.getElementById('tc-agent-autopay');
        if (toggle) toggle.checked = true;
        closeAllModals();
        if (window.showToast) {
          window.showToast('Automatic Payments Enabled', 'Autonomous payments authorized in simulated mode.', 'warning');
        }
      };
    }
    if (window.lucide) window.lucide.createIcons();
  }

  /**
   * Floating AI Advisor Setup
   */
  function setupAIAssistant() {
    const triggerBtn = document.getElementById('tc-floating-ai-btn');
    const windowEl = document.getElementById('tc-ai-window');
    const closeBtn = document.getElementById('tc-ai-close-btn');
    const clearBtn = document.getElementById('tc-ai-clear-btn');
    const form = document.getElementById('tc-ai-chat-form');
    const input = document.getElementById('tc-ai-chat-input');
    const messagesContainer = document.getElementById('tc-ai-chat-messages');
    const chipsContainer = document.getElementById('tc-ai-chips-container');
    const contextBtns = document.querySelectorAll('.tc-ai-context-btn');

    if (!triggerBtn || !windowEl) return;

    let aiContext = 'all';
    let isWindowOpen = false;

    function openAIWindow() {
      isWindowOpen = true;
      windowEl.classList.remove('scale-95', 'opacity-0', 'pointer-events-none');
      windowEl.classList.add('scale-100', 'opacity-100', 'pointer-events-auto');
      if (input) input.focus();
    }

    function closeAIWindow() {
      isWindowOpen = false;
      windowEl.classList.remove('scale-100', 'opacity-100', 'pointer-events-auto');
      windowEl.classList.add('scale-95', 'opacity-0', 'pointer-events-none');
    }

    triggerBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (isWindowOpen) closeAIWindow();
      else openAIWindow();
    });

    if (closeBtn) {
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        closeAIWindow();
      });
    }

    // Close on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && isWindowOpen) {
        closeAIWindow();
      }
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (isWindowOpen && !windowEl.contains(e.target) && !triggerBtn.contains(e.target)) {
        closeAIWindow();
      }
    });

    const promptSuggestions = {
      all: [
        'How do I optimize Section 179?',
        'How does credit utilization affect score?',
        'When is my next tax filing deadline?',
        'What is the bureau reporting discrepancy?',
        'How is my credit score calculated?'
      ],
      tax: [
        'How do I optimize Section 179?',
        'When is my next tax filing deadline?',
        'How much estimated tax do I owe?',
        'What tax documents are missing?'
      ],
      credit: [
        'How does credit utilization affect score?',
        'How is my credit score calculated?',
        'What is the bureau reporting discrepancy?',
        'How does the 90-Day Credit Plan work?'
      ]
    };

    function renderChips() {
      if (!chipsContainer) return;
      const prompts = promptSuggestions[aiContext] || promptSuggestions.all;
      chipsContainer.innerHTML = prompts.map(prompt => `
        <button
          type="button"
          class="tc-ai-prompt-chip px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 border border-slate-200 dark:border-white/10 hover:border-primary/40 text-[11px] text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-all whitespace-nowrap shrink-0 flex items-center gap-1.5 cursor-pointer"
          data-prompt="${prompt}"
        >
          <i data-lucide="sparkle" class="w-3 h-3 text-primary"></i>
          <span>${prompt}</span>
        </button>
      `).join('');
      if (window.lucide) window.lucide.createIcons();
    }

    // Context filter buttons
    contextBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const ctx = btn.getAttribute('data-ai-context');
        aiContext = ctx;
        contextBtns.forEach(b => {
          if (b.getAttribute('data-ai-context') === ctx) {
            b.className = 'tc-ai-context-btn px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-primary text-black transition-all';
          } else {
            b.className = 'tc-ai-context-btn px-2.5 py-1 rounded-lg text-[11px] font-semibold text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition-all';
          }
        });
        renderChips();
      });
    });

    // Chip click delegation
    if (chipsContainer) {
      chipsContainer.addEventListener('click', (e) => {
        const chip = e.target.closest('.tc-ai-prompt-chip');
        if (chip) {
          const prompt = chip.getAttribute('data-prompt');
          if (prompt) {
            sendUserMessage(prompt);
          }
        }
      });
    }

    // Initial greeting
    function renderInitialGreeting() {
      if (!messagesContainer) return;
      messagesContainer.innerHTML = `
        <div class="flex items-start gap-2.5">
          <div class="w-7 h-7 rounded-lg bg-primary/20 border border-primary/30 text-primary flex items-center justify-center shrink-0 mt-0.5">
            <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
          </div>
          <div class="flex-1 bg-slate-100/80 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 rounded-2xl rounded-tl-sm p-3.5 space-y-2 text-slate-700 dark:text-slate-200">
            <p class="font-medium text-slate-900 dark:text-white">
              Hello! I am your <span class="text-primary font-bold">FlezPay AI Advisor</span>.
            </p>
            <p class="text-slate-600 dark:text-slate-400 leading-relaxed">
              I have real-time visibility into your ledger, tax liabilities, deductions, and credit health factors. Ask me anything about tax compliance or improving your 682 credit score!
            </p>
          </div>
        </div>
      `;
      if (window.lucide) window.lucide.createIcons();
    }

    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        renderInitialGreeting();
      });
    }

    // Send question handler
    async function sendUserMessage(text) {
      const question = text || (input ? input.value.trim() : '');
      if (!question || !messagesContainer) return;

      if (input) input.value = '';

      // Append user bubble
      const userBubble = document.createElement('div');
      userBubble.className = 'flex items-start justify-end gap-2.5';
      userBubble.innerHTML = `
        <div class="max-w-[85%] bg-primary text-black font-medium rounded-2xl rounded-tr-sm px-3.5 py-2.5 shadow-sm text-xs leading-relaxed">
          ${escapeHtml(question)}
        </div>
      `;
      messagesContainer.appendChild(userBubble);
      messagesContainer.scrollTop = messagesContainer.scrollHeight;

      // Append typing indicator
      const typingId = 'tc-ai-typing-' + Date.now();
      const typingBubble = document.createElement('div');
      typingBubble.id = typingId;
      typingBubble.className = 'flex items-start gap-2.5';
      typingBubble.innerHTML = `
        <div class="w-7 h-7 rounded-lg bg-primary/20 border border-primary/30 text-primary flex items-center justify-center shrink-0 mt-0.5">
          <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
        </div>
        <div class="bg-slate-100/80 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 rounded-2xl rounded-tl-sm px-3.5 py-2.5 flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
          <span class="w-1.5 h-1.5 rounded-full bg-primary animate-bounce"></span>
          <span class="w-1.5 h-1.5 rounded-full bg-primary animate-bounce [animation-delay:0.2s]"></span>
          <span class="w-1.5 h-1.5 rounded-full bg-primary animate-bounce [animation-delay:0.4s]"></span>
        </div>
      `;
      messagesContainer.appendChild(typingBubble);
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
      if (window.lucide) window.lucide.createIcons();

      try {
        const response = await window.TaxCreditService.AIService.askAI({
          question,
          context: aiContext
        });

        // Remove typing indicator
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();

        // Format Markdown bolding
        const formattedAnswer = (response.answer || '')
          .replace(/\*\*(.*?)\*\*/g, '<strong class="text-slate-900 dark:text-white font-bold">$1</strong>')
          .replace(/\n/g, '<br>');

        const aiBubble = document.createElement('div');
        aiBubble.className = 'flex items-start gap-2.5';
        aiBubble.innerHTML = `
          <div class="w-7 h-7 rounded-lg bg-primary/20 border border-primary/30 text-primary flex items-center justify-center shrink-0 mt-0.5">
            <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
          </div>
          <div class="flex-1 bg-slate-100/80 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 rounded-2xl rounded-tl-sm p-3.5 space-y-1.5 text-slate-700 dark:text-slate-300 leading-relaxed">
            <p>${formattedAnswer}</p>
          </div>
        `;
        messagesContainer.appendChild(aiBubble);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        if (window.lucide) window.lucide.createIcons();
      } catch (err) {
        console.error('Error fetching AI response:', err);
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();

        const errBubble = document.createElement('div');
        errBubble.className = 'flex items-start gap-2.5';
        errBubble.innerHTML = `
          <div class="w-7 h-7 rounded-lg bg-rose-500/20 border border-rose-500/30 text-rose-500 dark:text-rose-400 flex items-center justify-center shrink-0 mt-0.5">
            <i data-lucide="alert-circle" class="w-3.5 h-3.5"></i>
          </div>
          <div class="flex-1 bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 rounded-2xl rounded-tl-sm p-3 text-rose-800 dark:text-rose-300 text-xs">
            Unable to reach FlezPay AI Advisor. Please try again in a moment.
          </div>
        `;
        messagesContainer.appendChild(errBubble);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        if (window.lucide) window.lucide.createIcons();
      }
    }

    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        sendUserMessage();
      });
    }

    renderChips();
    renderInitialGreeting();
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // Auto-init on DOMContentLoaded if tax-credit-page exists
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      if (document.getElementById('tax-credit-page')) {
        window.initTaxCreditPage();
      }
    });
  } else {
    if (document.getElementById('tax-credit-page')) {
      window.initTaxCreditPage();
    }
  }

})(window);
