/**
 * System Settings Management
 */

// Expose globally for dashboard.js
window.initSettingsPage = initSettingsPage;

var currentActiveTab = "branding";
var userData = null;
var privacySettings = null;
var allSubscriptions = [];
window.allSubscriptions = [];

async function initSettingsPage() {
  if (!document.getElementById("save-settings") && !document.getElementById("settings-content-container")) return;

  setupTabs();
  await loadSettingsData();

  // If user navigated away from settings while loadSettingsData was fetching
  if (!document.getElementById("save-settings") && !document.getElementById("settings-content-container")) return;

  setupEventListeners();

  // Initialize Lucide icons
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

const tabMeta = {
  branding: {
    title: "Business Branding",
    subtitle: "Customize your business details, logo, colors, and receipt info."
  },
  withdrawals: {
    title: "Withdrawal Accounts",
    subtitle: "Manage bank accounts for settlement withdrawals."
  },
  security: {
    title: "Security & Password",
    subtitle: "Update your password, two-factor authentication, and account access."
  },
  subscription: {
    title: "Subscription & Plans",
    subtitle: "View your current subscription tier, usage limits, and renewal details."
  },
  general: {
    title: "General System Settings",
    subtitle: "Configure notification preferences, tax settings, and store parameters."
  }
};

function activateTab(tabId) {
  const tabs = document.querySelectorAll(".tab-link");
  const contents = document.querySelectorAll(".tab-content");

  // Validate tabId — fall back to default if unknown
  if (!tabMeta[tabId]) tabId = "branding";
  currentActiveTab = tabId;

  // Update tab link active states
  tabs.forEach((t) => {
    t.classList.remove(
      "active",
      "text-white",
      "font-semibold",
      "text-primary",
      "bg-primary/10",
      "border-l-2",
      "border-l-4",
      "border-primary",
      "font-bold",
      "border-b-2"
    );
    t.classList.add("text-slate-400");
    if (t.getAttribute("data-tab") === tabId) {
      t.classList.remove("text-slate-400", "text-slate-500");
      t.classList.add("active", "text-white", "font-semibold");
    }
  });

  // Update header title & subtitle
  const headTitle = document.getElementById("tab-head-title");
  const headSubtitle = document.getElementById("tab-head-subtitle");
  if (tabMeta[tabId]) {
    if (headTitle) headTitle.innerText = tabMeta[tabId].title;
    if (headSubtitle) headSubtitle.innerText = tabMeta[tabId].subtitle;
  }

  // Show target content, hide others
  contents.forEach((c) => {
    if (c.id === `tab-${tabId}`) {
      c.classList.remove("hidden");
    } else {
      c.classList.add("hidden");
    }
  });

  if (window.lucide) window.lucide.createIcons();
}

function setupTabs() {
  const tabs = document.querySelectorAll(".tab-link");

  // Read hash from URL on load (e.g. /settings#subscription)
  const hashTab = window.location.hash.replace("#", "").trim();
  activateTab(hashTab || currentActiveTab);

  tabs.forEach((tab) => {
    tab.onclick = (e) => {
      e.preventDefault();
      const tabId = tab.getAttribute("data-tab");
      if (!tabId) return;

      // Persist the active tab in the URL hash without adding a history entry
      history.replaceState(null, "", `#${tabId}`);
      activateTab(tabId);
    };
  });

  // Support browser back/forward navigating between hashes
  window.addEventListener("hashchange", () => {
    const tabId = window.location.hash.replace("#", "").trim();
    if (tabId) activateTab(tabId);
  });
}

async function loadSettingsData() {
  const saveBtn = document.getElementById("save-settings");
  const skeleton = document.getElementById("settings-skeleton");
  const contentContainer = document.getElementById("settings-content-container");

  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerText = "Loading...";
  }

  // Pre-fill immediately from local cache if present to avoid blank/pulsing delay
  try {
    const cachedUserData = JSON.parse(localStorage.getItem("user_data") || "null");
    if (cachedUserData) {
      userData = cachedUserData;
      populateBrandingTab(userData.business_details ? userData.business_details[0] : null);
      populateWithdrawalsTab(userData.withdrawal_accounts);
      populateSubscriptionTab(userData);
      updateVerificationBanner(userData);
      if (skeleton) skeleton.classList.add("hidden");
      if (contentContainer) contentContainer.classList.remove("hidden");
    }
  } catch (e) {
    console.warn("Cached user data parse failed in settings:", e);
  }

  try {
    const [userRes, privacyRes] = await Promise.all([
      apiFetch(
        `${window.FLEZ_API_BASE || ""}/api/user/data`,
        { method: "POST" },
      ),
      apiFetch(
        `${window.FLEZ_API_BASE || ""}/api/user/privacy/settings`,
      ),
    ]);

    if (userRes.status === 401 || userRes.status === 403) {
      window.location.href = "/login";
      return;
    }

    const userResponse = await userRes.json();
    const privacyResponse = await privacyRes.json();

    if (userResponse.status && userResponse.data) {
      userData = userResponse.data;
      localStorage.setItem("user_data", JSON.stringify(userData));

      populateBrandingTab(
        userData.business_details ? userData.business_details[0] : null,
      );
      populateWithdrawalsTab(userData.withdrawal_accounts);
      populateSubscriptionTab(userData);
      updateVerificationBanner(userData);

      // Load Store Regions if admin
      if (userData.user_type === "admin" || userData.is_staff) {
        await loadStoreRegions();
      }
    }

    if (privacyResponse.status) {
      privacySettings = privacyResponse.settings;
      populateGeneralTab(privacyResponse.settings);
      populateSecurityTab(privacyResponse.settings);
    }
  } catch (err) {
    console.error("Failed to load settings:", err);
    Swal.fire(
      "Error",
      "Failed to load system settings. Please try again.",
      "error",
    );
  } finally {
    if (skeleton) skeleton.classList.add("hidden");
    if (contentContainer) contentContainer.classList.remove("hidden");
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerText = "Save Changes";
    }
    if (window.lucide) window.lucide.createIcons();
  }
}


function populateBrandingTab(business) {
  if (!business) return;

  const bName = business.business_name || business.store_name || "";
  setInputValue("branding-store-name", bName);
  setInputValue(
    "primary-color-input",
    business.primary_color || "#cfff45",
  );

  // Update color indicator
  const indicator = document.getElementById("primary-color-indicator");
  if (indicator) {
    indicator.style.backgroundColor =
      business.primary_color || "#cfff45";
  }

  // Update logo preview
  if (business.business_image) {
    const preview = document.getElementById("logo-preview-img");
    const container = document.getElementById("logo-preview-container");
    const placeholder = document.getElementById("logo-upload-placeholder");

    if (preview && container && placeholder) {
      preview.src = business.business_image;
      container.classList.remove("hidden");
      placeholder.classList.add("hidden");
    }
  }
}

function toggleWithdrawalDropdown(btnElement, event, accId) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }

  const dropdownId = `withdrawal-dropdown-${accId}`;
  const dropdown = document.getElementById(dropdownId);
  if (!dropdown) return;

  const isCurrentlyVisible = dropdown.style.display === "block";

  // Close all open dropdowns first
  document.querySelectorAll('[id^="withdrawal-dropdown-"]').forEach((el) => {
    el.style.display = "none";
  });

  if (!isCurrentlyVisible && btnElement) {
    // Move dropdown to body so it escapes overflow-x-auto clipping
    document.body.appendChild(dropdown);

    const rect = btnElement.getBoundingClientRect();
    dropdown.style.position = "fixed";
    dropdown.style.top = `${rect.bottom + 4}px`;
    dropdown.style.left = `${Math.max(10, rect.right - 144)}px`;
    dropdown.style.zIndex = "99999";
    dropdown.style.display = "block";
    dropdown.classList.remove("hidden");
  }
}

// Global click & scroll handlers to dismiss dropdowns
document.addEventListener("click", (e) => {
  if (!e.target || !e.target.closest) return;
  if (e.target.closest('[id^="withdrawal-dropdown-"]')) return;
  if (e.target.closest('[onclick*="toggleWithdrawalDropdown"]')) return;
  document.querySelectorAll('[id^="withdrawal-dropdown-"]').forEach((el) => {
    el.style.display = "none";
  });
});

window.addEventListener("scroll", () => {
  document.querySelectorAll('[id^="withdrawal-dropdown-"]').forEach((el) => {
    el.style.display = "none";
  });
}, true);

function populateWithdrawalsTab(instruments) {
  const list = document.getElementById("withdrawal-accounts-list");
  if (!list) return;

  if (!instruments || instruments.length === 0) {
    list.innerHTML = `
      <div class="py-8 text-center text-slate-500">
        No withdrawal accounts added yet.
      </div>
    `;
    return;
  }

  list.innerHTML = instruments
    .map(
      (acc) => `
        <div class="py-4 flex flex-col gap-3 md:grid md:grid-cols-[1fr_1fr_1fr_auto] md:gap-4 md:items-center">
          <!-- Bank Name -->
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-500 flex items-center justify-center shrink-0">
              <i data-lucide="landmark" class="w-4 h-4"></i>
            </div>
            <div>
              <span class="md:hidden text-[10px] font-bold text-slate-500 uppercase tracking-widest block">Bank / Method</span>
              <span class="text-sm font-semibold text-slate-900 dark:text-white">${acc.bank_name || 'Bank Account'}</span>
            </div>
          </div>
          <!-- Account Number -->
          <div>
            <span class="md:hidden text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-0.5">Account Number</span>
            <span class="text-sm text-slate-600 dark:text-slate-300 font-mono">${acc.account_number}</span>
          </div>
          <!-- Account Name -->
          <div>
            <span class="md:hidden text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-0.5">Account Name</span>
            <span class="text-sm text-slate-600 dark:text-slate-300">${acc.account_name}</span>
          </div>
          <!-- Action -->
          <div class="flex justify-end md:justify-end">
            <button
              type="button"
              onclick="toggleWithdrawalDropdown(this, event, ${acc.uniq_id})"
              class="p-2 text-slate-400 hover:text-slate-900 dark:hover:text-white rounded-lg transition-all"
              title="Options"
            >
              <i data-lucide="more-vertical" class="w-4 h-4"></i>
            </button>
            <div
              id="withdrawal-dropdown-${acc.uniq_id}"
              class="hidden w-36 bg-white dark:bg-slate-900 border border-slate-200 dark:border-white/10 rounded-xl shadow-xl z-20 py-1"
            >
              <button
                type="button"
                onclick="deleteWithdrawalAccount(${acc.uniq_id})"
                class="w-full px-4 py-2 text-left text-xs font-semibold text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 flex items-center gap-2 transition-all"
              >
                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i> Delete
              </button>
            </div>
          </div>
        </div>
      `,
    )
    .join("");

  if (window.lucide) window.lucide.createIcons();
}

async function populateSubscriptionTab(data) {
  const business =
    data.business_details && data.business_details.length > 0
      ? data.business_details[0]
      : {};
  const invoices = data.invoice || [];

  let exchangeRate = 1.0;
  try {
      const userCurrency = window.STORE_CURRENCY_CODE || "NGN";
      if (userCurrency !== "NGN") {
          const res = await fetch("https://open.er-api.com/v6/latest/NGN");
          if (res.ok) {
              const rateData = await res.json();
              exchangeRate = rateData.rates[userCurrency] || 1.0;
          }
      }
  } catch (e) {
      console.error("Exchange rate fetch failed:", e);
  }

  const rawSubscriptions = data.subscriptions || [];
  const subscriptions = rawSubscriptions.map(s => {
      const p = { ...s };
      p.one_amount = parseFloat(p.one_amount || 0) * exchangeRate;
      p.three_months = parseFloat(p.three_months || 0) * exchangeRate;
      p.six_months = parseFloat(p.six_months || 0) * exchangeRate;
      p.twelve_months = parseFloat(p.twelve_months || 0) * exchangeRate;
      return p;
  });
  
  allSubscriptions = subscriptions;
  window.allSubscriptions = subscriptions; // expose for overlay

  const activePlan = subscriptions.find(
    (s) => String(s.uniq_id) === String(business.plan_code),
  );
  const currentPlanNameEl = document.getElementById("current-plan-name");
  if (currentPlanNameEl) {
    currentPlanNameEl.innerText = activePlan
      ? activePlan.plan_name
      : business.plan_code > 0
        ? "Enterprise"
        : "Starter";
  }

  const planExpiryEl = document.getElementById("plan-expiry-text");
  if (planExpiryEl) {
    if (activePlan && (parseFloat(activePlan.one_amount) === 0 || activePlan.plan_name.toLowerCase().includes('free'))) {
      planExpiryEl.innerText = "Free";
    } else if (business.subscription_expiry) {
      planExpiryEl.innerText =
        `Renews on ${formatDate(business.subscription_expiry)}`;
    }
  }

  // Populate Current Plan Features
  const featureContainer = document.getElementById("current-plan-features");
  if (featureContainer) {
    let featuresHtml = "";
    const renderFeature = (text) => `
            <div class="flex items-center gap-3 text-sm text-slate-300">
                <i data-lucide="check-circle-2" class="w-4 h-4 text-primary"></i>
                ${text}
            </div>
        `;

    if (activePlan) {
      const managersText =
        activePlan.cashiers >= 99
          ? "Unlimited Managers & Staff"
          : `${activePlan.cashiers} Managers & Staff`;
      featuresHtml += renderFeature(managersText);

      if (activePlan.inventory) {
        featuresHtml += renderFeature("Multi-branch Inventory Support");
      } else {
        featuresHtml += renderFeature("Basic Inventory Support");
      }

      if (activePlan.ai_manager || activePlan.ai_calls) {
        featuresHtml += renderFeature("AI-Powered Analytics & Predications");
      } else {
        featuresHtml += renderFeature("Standard Analytics");
      }
    } else {
      // Fallback for when no plan is active
      featuresHtml += renderFeature("Limited Managers & Staff");
      featuresHtml += renderFeature("Basic Inventory Support");
      featuresHtml += renderFeature("Standard Analytics");
    }

    featureContainer.innerHTML = featuresHtml;
    if (window.lucide) {
      lucide.createIcons();
    }
  }

  // Configure Renew Button
  const renewBtn = document.getElementById("renew-plan-btn");
  if (renewBtn) {
    if (!activePlan || parseFloat(activePlan.one_amount || 0) === 0) {
      renewBtn.disabled = true;
      renewBtn.classList.add("opacity-50", "cursor-not-allowed");
      renewBtn.removeAttribute("onclick");
    } else {
      renewBtn.disabled = false;
      renewBtn.classList.remove("opacity-50", "cursor-not-allowed");
      renewBtn.setAttribute(
        "onclick",
        `openSubscriptionOverlay('${activePlan.uniq_id}')`,
      );
    }
  }

  // Populate Other Plans List
  const plansList = document.getElementById("other-plans-list");
  if (plansList) {
    const activeAmount = activePlan
      ? parseFloat(activePlan.one_amount || 0)
      : 0;
    const hasActivePaidSub = activeAmount > 0;

    plansList.innerHTML = subscriptions
      .map((plan) => {
        const isActive = String(plan.uniq_id) === String(business.plan_code);
        const planAmount = parseFloat(plan.one_amount || 0);

        let isDisabled = false;
        let statusText = isActive
          ? "Current active subscription"
          : plan.description;

        if (!isActive && hasActivePaidSub) {
          if (planAmount === 0 || planAmount < activeAmount) {
            isDisabled = true;
            statusText = "Unavailable for downgrade";
          }
        }

        return `
                <div
                    class="p-4 rounded-2xl bg-white/5 border ${isActive ? "border-primary/50 bg-primary/5" : "border-white/10 hover:border-primary/50 cursor-pointer"} transition-all ${isDisabled ? "opacity-50 pointer-events-none grayscale" : ""}"
                    ${!isActive && !isDisabled ? `onclick="openSubscriptionOverlay('${plan.uniq_id}')"` : ""}
                >
                    <div class="flex justify-between items-center mb-1">
                        <span class="text-sm font-bold text-white">${plan.plan_name}</span>
                        <span class="text-xs font-bold ${isActive ? "text-primary" : "text-slate-500"}">
                            ${planAmount === 0 ? "FREE" : (window.STORE_CURRENCY_SYMBOL || "\u20a6") + planAmount.toLocaleString() + "/mo"}
                        </span>
                    </div>
                    <p class="text-[10px] text-slate-500">
                        ${statusText}
                    </p>
                    ${!isActive && !isDisabled ? '<p class="text-[10px] text-primary mt-2 font-semibold">Tap to switch plan →</p>' : ""}
                </div>
            `;
      })
      .join("");
  }

  fetchSubscriptionInvoices(1);
}

let currentSubscriptionInvoicesPage = 1;

async function fetchSubscriptionInvoices(page = 1) {
  currentSubscriptionInvoicesPage = page;
  const invoiceList = document.getElementById("subscription-invoices-list");
  if (!invoiceList) return;

  invoiceList.innerHTML =
    '<tr><td colspan="5" class="py-8 text-center text-slate-500"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto"></i></td></tr>';
  if (window.lucide) window.lucide.createIcons();

  try {
    const response = await apiFetch(
      `${window.FLEZ_API_BASE || ""}/api/user/subscription_invoices`,
      {
        method: "POST",
        body: JSON.stringify({ page: page, per_page: 10 }),
      },
    );
    const result = await response.json();

    if (result.status && result.data.length > 0) {
      invoiceList.innerHTML = result.data
        .map(
          (inv) => `
                <tr class="group hover:bg-white/5 transition-all">
                    <td class="py-4 text-sm font-medium text-white">${formatDate(inv.timestamp)}</td>
                    <td class="py-4 text-sm text-slate-300">${inv.invoice_note || "Subscription Payment"}</td>
                    <td class="py-4 text-sm font-bold text-white">${window.STORE_CURRENCY_SYMBOL}${parseFloat(inv.amount || 0).toLocaleString()}</td>
                    <td class="py-4">
                        <span class="px-2 py-1 rounded-md text-[10px] font-bold ${inv.invoice_status === "completed" ? "bg-primary/20 text-primary" : "bg-amber-500/20 text-amber-500"} uppercase">
                            ${inv.invoice_status}
                        </span>
                    </td>
                    <td class="py-4 text-right">
                        <button onclick="downloadSubscriptionInvoice('${inv.invoice_id}')" class="p-2 text-primary hover:bg-primary/10 rounded-lg transition-all" title="Download Invoice">
                            <i data-lucide="download" class="w-4 h-4"></i>
                        </button>
                    </td>
                </tr>
            `,
        )
        .join("");
      renderSubscriptionInvoicesPagination(result.pagination);
    } else {
      invoiceList.innerHTML =
        '<tr><td colspan="5" class="py-8 text-center text-slate-500">No invoices yet.</td></tr>';
      renderSubscriptionInvoicesPagination(null);
    }
    if (window.lucide) window.lucide.createIcons();
  } catch (err) {
    console.error("Error fetching subscription invoices:", err);
    invoiceList.innerHTML =
      '<tr><td colspan="5" class="py-8 text-center text-red-500">Failed to load invoices.</td></tr>';
  }
}

function renderSubscriptionInvoicesPagination(pagination) {
  let paginationContainer = document.getElementById(
    "subscription-invoices-pagination",
  );

  if (!paginationContainer) {
    const listEl = document.getElementById("subscription-invoices-list");
    if (!listEl) return;
    const tableContainer = listEl.closest("div");
    paginationContainer = document.createElement("div");
    paginationContainer.id = "subscription-invoices-pagination";
    paginationContainer.className =
      "mt-6 pt-4 border-t border-white/5 flex flex-col sm:flex-row items-center justify-between gap-4";
    tableContainer.parentNode.insertBefore(
      paginationContainer,
      tableContainer.nextSibling,
    );
  }

  if (!pagination || pagination.total_pages <= 1) {
    paginationContainer.innerHTML = "";
    return;
  }

  const { current_page, total_pages, total_items, per_page, has_next, has_previous } = pagination;
  const startItem = (current_page - 1) * (per_page || 10) + 1;
  const endItem = Math.min(current_page * (per_page || 10), total_items || 0);

  let pageButtons = "";
  for (let i = 1; i <= total_pages; i++) {
    if (i === 1 || i === total_pages || (i >= current_page - 1 && i <= current_page + 1)) {
      pageButtons += `
        <button 
          onclick="fetchSubscriptionInvoices(${i})" 
          class="w-8 h-8 rounded-lg text-xs font-bold transition-all ${
            i === current_page
              ? "bg-primary text-white"
              : "bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white"
          }">
          ${i}
        </button>
      `;
    } else if (i === current_page - 2 || i === current_page + 2) {
      pageButtons += `<span class="px-1 text-slate-500 text-xs">...</span>`;
    }
  }

  paginationContainer.innerHTML = `
    <div class="text-xs font-medium text-slate-400">
      Showing <span class="text-white font-bold">${startItem}-${endItem}</span> of <span class="text-white font-bold">${total_items || 0}</span> invoices
    </div>
    <div class="flex items-center gap-2">
      <button 
        onclick="fetchSubscriptionInvoices(${current_page - 1})"
        class="px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-xs font-bold text-slate-300 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-all flex items-center gap-1"
        ${!has_previous ? "disabled" : ""}>
        <i data-lucide="chevron-left" class="w-3.5 h-3.5"></i> Previous
      </button>
      <div class="flex items-center gap-1 mx-1">
        ${pageButtons}
      </div>
      <button 
        onclick="fetchSubscriptionInvoices(${current_page + 1})"
        class="px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-xs font-bold text-slate-300 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-all flex items-center gap-1"
        ${!has_next ? "disabled" : ""}>
        Next <i data-lucide="chevron-right" class="w-3.5 h-3.5"></i>
      </button>
    </div>
  `;
  if (window.lucide) window.lucide.createIcons();
}

function downloadSubscriptionInvoice(invoiceId) {
  const token = localStorage.getItem("auth_token") || "";
  const url = `${window.FLEZ_API_BASE || ""}/api/user/subscription_invoices/${invoiceId}/download?token=${token}`;
  window.open(url, "_blank");
}

function populateGeneralTab(settings) {
  if (!settings) return;

  updateToggleUI("noti-sales", settings.notifications_sales);
  
  // Business Reporting Toggle Validation
  const businessDetails = userData?.business_details?.[0] || {};
  const activePlan = (window.allSubscriptions || []).find(
    (s) => String(s.uniq_id) === String(businessDetails.plan_code),
  );
  
  const emailToggle = document.getElementById("noti-email");
  if (activePlan && !activePlan.business_reporting) {
    // If not supported by plan, force off and visually disable
    updateToggleUI("noti-email", false);
    if (emailToggle) {
        emailToggle.classList.add("opacity-50", "cursor-not-allowed");
        // Disable clicking logic for this button
        emailToggle.style.pointerEvents = "none";
        
        // Add a small tooltip or text hint (optional)
        const parentDiv = emailToggle.closest('div.flex');
        if (parentDiv && !parentDiv.querySelector('.plan-upgrade-hint')) {
            const hint = document.createElement('span');
            hint.className = 'plan-upgrade-hint text-[10px] text-primary ml-2';
            hint.innerText = 'Requires Upgrade';
            parentDiv.querySelector('span').appendChild(hint);
        }
    }
  } else {
    updateToggleUI("noti-email", settings.notifications_email);
    if (emailToggle) {
        emailToggle.classList.remove("opacity-50", "cursor-not-allowed");
        emailToggle.style.pointerEvents = "auto";
        const hint = emailToggle.closest('div.flex').querySelector('.plan-upgrade-hint');
        if (hint) hint.remove();
    }
  }

  updateToggleUI("noti-stock", settings.notifications_stock);

  // Business Configuration
  const business = userData?.business_details?.[0] || {};
  
  updateToggleUI("toggle-loyalty", business.enable_loyalty);
  
  const lpEl = document.getElementById("loyalty-point-equivalent");
  if (lpEl) {
    lpEl.value = business.loyalty_point_equivalent || 0;
    lpEl.disabled = !business.enable_loyalty;
    if (!business.enable_loyalty) {
      lpEl.classList.add("opacity-50", "cursor-not-allowed");
    } else {
      lpEl.classList.remove("opacity-50", "cursor-not-allowed");
    }
  }
  
  const vatEl = document.getElementById("vat-percentage");
  if (vatEl) vatEl.value = business.vat_percentage || 0;
}

function populateSecurityTab(settings) {
  if (!settings) return;

  updateToggleUI("toggle-2fa-btn", settings.two_factor_enabled);
  updateToggleUI("toggle-biometric-btn", settings.biometric_login);

  // Also load payroll otp which is in business_details
  const business =
    userData.business_details && userData.business_details.length > 0
      ? userData.business_details[0]
      : {};
  const payrollOtpEnabled =
    business.enable_payroll_otp !== false &&
    business.enable_payroll_otp !== "false" &&
    business.enable_payroll_otp !== 0; // Default true
  updateToggleUI("toggle-payroll-otp-btn", payrollOtpEnabled);
}

function setupEventListeners() {
  // Global Save
  const saveBtn = document.getElementById("save-settings");
  if (saveBtn) {
    if (saveBtn.dataset.listenerAttached !== "true") {
      saveBtn.dataset.listenerAttached = "true";
      saveBtn.addEventListener("click", handleSave);
    }
  }

  // Color selector
  const colorInput = document.getElementById("primary-color-input");
  if (colorInput) {
    colorInput.addEventListener("input", (e) => {
      const indicator = document.getElementById("primary-color-indicator");
      if (indicator) indicator.style.backgroundColor = e.target.value;
    });
  }


  // Logo Upload
  const logoTrigger = document.getElementById("logo-upload-trigger");
  const logoInput = document.getElementById("logo-upload-input");
  if (logoTrigger && logoInput) {
    logoTrigger.addEventListener("click", () => logoInput.click());
    logoInput.addEventListener("change", (e) => handleLogoPreview(e));
  }

  // Notification & Business Toggles
  const toggles = ["noti-sales", "noti-email", "noti-stock", "toggle-loyalty"];
  toggles.forEach((id) => {
    const btn = document.getElementById(id);
    if (btn) {
      if (btn.dataset.listenerAttached === "true") return;
      btn.dataset.listenerAttached = "true";

      btn.addEventListener("click", () => {
        const enabled = btn.getAttribute("data-enabled") === "true";
        const newState = !enabled;
        updateToggleUI(id, newState);
        
        if (id === "toggle-loyalty") {
          const lpEl = document.getElementById("loyalty-point-equivalent");
          if (lpEl) {
            lpEl.disabled = !newState;
            if (!newState) {
              lpEl.classList.add("opacity-50", "cursor-not-allowed");
            } else {
              lpEl.classList.remove("opacity-50", "cursor-not-allowed");
            }
          }
        }
      });
    }
  });

  // Security Toggles
  const secToggles = [
    "toggle-2fa-btn",
    "toggle-biometric-btn",
    "toggle-payroll-otp-btn",
  ];
  secToggles.forEach((id) => {
    const btn = document.getElementById(id);
    if (btn) {
      if (btn.dataset.listenerAttached === "true") return;
      btn.dataset.listenerAttached = "true";

      btn.addEventListener("click", () => {
        if (id === "toggle-2fa-btn") {
          handle2FAToggle();
        } else if (id === "toggle-payroll-otp-btn") {
          handlePayrollOtpToggle();
        } else {
          const enabled = btn.getAttribute("data-enabled") === "true";
          updateToggleUI(id, !enabled);
        }
      });
    }
  });

  // 2FA Logic (already handled by secToggles click listener above)

  // Add Withdrawal Account
  const addAccountBtn = document.getElementById("add-account-btn");
  if (addAccountBtn) {
    addAccountBtn.addEventListener("click", handleAddAccount);
  }

  // Change Email Flow
  const changeEmailBtn = document.getElementById("change-email-btn");
  if (changeEmailBtn) {
    changeEmailBtn.addEventListener("click", handleChangeEmail);
  }

  // Delete / Soft Deactivate Account
  const deleteAccountBtn = document.getElementById("delete-account-btn");
  if (deleteAccountBtn) {
    if (deleteAccountBtn.dataset.listenerAttached !== "true") {
      deleteAccountBtn.dataset.listenerAttached = "true";
      deleteAccountBtn.addEventListener("click", handleAccountDeletion);
    }
  }
}

async function handleAccountDeletion() {
  if (typeof Swal === "undefined") {
    if (!confirm("Are you sure you want to delete your account? This will log you out.")) return;
  }

  const result = await Swal.fire({
    title: "Delete Account",
    html: `
      <div class="text-left space-y-4">
        <p class="text-sm text-slate-300">
          Are you sure you want to delete your account? This action will terminate all active login sessions and revoke your account access.
        </p>
        <p class="text-xs font-semibold text-slate-400">
          Please enter your <strong>Account Password</strong> to confirm deletion:
        </p>
        <input id="swal-input-password" type="password" class="swal2-input !m-0 !w-full bg-slate-800 border-white/10 text-white" placeholder="Enter your password">
      </div>
    `,
    icon: "warning",
    showCancelButton: true,
    confirmButtonColor: "#ef4444",
    cancelButtonColor: "#334155",
    confirmButtonText: "Yes, Delete Account",
    cancelButtonText: "Cancel",
    focusConfirm: false,
    preConfirm: () => {
      const password = document.getElementById("swal-input-password").value;
      if (!password) {
        Swal.showValidationMessage("Account password is required to confirm deletion");
        return false;
      }
      return { password };
    }
  });

  if (!result.isConfirmed || !result.value) return;

  const { password } = result.value;

  Swal.fire({
    title: "Deleting Account...",
    text: "Please wait while we process your request.",
    allowOutsideClick: false,
    didOpen: () => {
      Swal.showLoading();
    }
  });

  try {
    const res = await apiFetch(`${window.FLEZ_API_BASE || ""}/api/user/delete/account`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ password })
    });

    const data = await res.json();

    if (data.status) {
      await Swal.fire({
        icon: "success",
        title: "Account Deleted",
        text: data.message || "Your account has been deleted. Logging out...",
        timer: 2500,
        showConfirmButton: false
      });
      if (typeof window.logout === "function") {
        window.logout();
      } else {
        localStorage.clear();
        window.location.href = "/login";
      }
    } else {
      Swal.fire({
        icon: "error",
        title: "Deletion Failed",
        text: data.message || "Failed to delete account. Please check your password and try again."
      });
    }
  } catch (err) {
    Swal.fire({
      icon: "error",
      title: "Error",
      text: err.message || "An unexpected error occurred. Please try again."
    });
  }
}

async function handleChangeEmail() {
  const { value: newEmail } = await Swal.fire({
    title: "Change Email Address",
    input: "email",
    inputLabel: "Enter your new email address",
    inputPlaceholder: "e.g., james@example.com",
    showCancelButton: true,
    confirmButtonText: "Send OTP",
    confirmButtonColor: "#cfff45",
    showLoaderOnConfirm: true,
    preConfirm: async (email) => {
      try {
        const token = localStorage.getItem("auth_token") || "";
        const res = await apiFetch(`${window.FLEZ_API_BASE || ""}/api/user/validateEmail`, {
          method: "POST",
          body: JSON.stringify({ user_email: email }),
        });
        const data = await res.json();
        if (!data.status) {
          throw new Error(data.message || "Failed to send OTP");
        }
        return email;
      } catch (error) {
        Swal.showValidationMessage(`Request failed: ${error}`);
      }
    },
    allowOutsideClick: () => !Swal.isLoading()
  });

  if (newEmail) {
    const { value: otp } = await Swal.fire({
      title: "Verify New Email",
      text: `Enter the OTP sent to ${newEmail}`,
      input: "text",
      inputPlaceholder: "Enter 4-digit PIN",
      showCancelButton: true,
      confirmButtonText: "Verify & Update",
      confirmButtonColor: "#cfff45",
      showLoaderOnConfirm: true,
      preConfirm: async (pin) => {
        try {
          const res = await apiFetch(`${window.FLEZ_API_BASE || ""}/api/user/validateEmail/update`, {
            method: "PATCH",
            body: JSON.stringify({ user_email: newEmail, user_pin: pin }),
          });
          const data = await res.json();
          if (!data.status) {
            throw new Error(data.message || "Invalid OTP");
          }
          return data;
        } catch (error) {
          Swal.showValidationMessage(`Verification failed: ${error}`);
        }
      },
      allowOutsideClick: () => !Swal.isLoading()
    });

    if (otp) {
      document.getElementById("profile-email").value = newEmail;
      Swal.fire({
        title: "Success",
        text: "Your email has been updated successfully.",
        icon: "success",
        confirmButtonColor: "#cfff45"
      });
    }
  }

  // Add Country (Admin)
  const addCountryBtn = document.getElementById("add-country-btn");
  if (addCountryBtn) {
    addCountryBtn.addEventListener("click", handleAddCountry);
  }

  // Renew Subscription handled by inline onclick in renderActivePlan

  // Password Visibility Toggles
  const passToggles = document.querySelectorAll('.toggle-password');
  passToggles.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-target');
      const input = document.getElementById(targetId);
      if (input) {
        if (input.type === 'password') {
          input.type = 'text';
          btn.innerHTML = '<i data-lucide="eye-off" class="w-4 h-4"></i>';
        } else {
          input.type = 'password';
          btn.innerHTML = '<i data-lucide="eye" class="w-4 h-4"></i>';
        }
        if (window.lucide) window.lucide.createIcons();
      }
    });
  });
}

async function handleSave() {
  const saveBtn = document.getElementById("save-settings");
  saveBtn.disabled = true;
  saveBtn.innerText = "Saving...";

  try {
    let success = false;
    switch (currentActiveTab) {
      case "branding":
        success = await saveBranding();
        break;
      case "security":
        success = await saveSecurity();
        break;
      case "general":
        success = await saveGeneralSettings();
        break;
      case "withdrawals":
        // Handled individually by "Add Account" or "Delete"
        success = true;
        break;
      default:
        success = true;
    }

    if (success) {
      Swal.fire({
        title: "Success",
        text: "Settings updated successfully.",
        icon: "success",
        timer: 2000,
        showConfirmButton: false,
        background: "var(--swal-bg)",
        color: "var(--swal-text)",
      });
      await loadSettingsData(); // Refresh UI
    }
  } catch (err) {
    console.error("Save failed:", err);
    Swal.fire({
      title: "Error",
      text: err.message || "Failed to save settings.",
      icon: "error",
      background: "var(--swal-bg)",
      color: "var(--swal-text)",
    });
  } finally {
    saveBtn.disabled = false;
    saveBtn.innerText = "Save Changes";
  }
}

async function handleAddAccount() {
  // 1. Fetch Banks
  let banks = [];
  try {
    const response = await apiFetch(
      `${window.FLEZ_API_BASE || ""}/api/data/banks`,
    );
    const data = await response.json();
    banks = data.data || [];
  } catch (err) {
    console.error("Failed to load banks:", err);
  }

  const { value: formValues } = await Swal.fire({
    title: "Add Withdrawal Account",
    html: `
            <div class="space-y-4 text-left p-2">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-2">Select Bank</label>
                    <select id="swal-bank" class="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white outline-none focus:border-primary">
                        ${banks.map((b) => `<option value="${b.code}">${b.name}</option>`).join("")}
                    </select>
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-2">Account Number</label>
                    <input id="swal-account-number" type="text" maxlength="10" placeholder="1234567890" class="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white outline-none focus:border-primary">
                </div>
                <div id="swal-account-name-container" class="hidden">
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-2">Account Name</label>
                    <input id="swal-account-name" type="text" readonly class="w-full bg-slate-700/50 border border-white/10 rounded-xl px-4 py-3 text-sm text-slate-400 outline-none">
                </div>
            </div>
        `,
    focusConfirm: false,
    showCancelButton: true,
    confirmButtonText: "Validate & Save",
    background: "var(--swal-bg)",
    color: "var(--swal-text)",
    didOpen: () => {
      const accInput = document.getElementById("swal-account-number");
      const bankSelect = document.getElementById("swal-bank");
      const nameContainer = document.getElementById(
        "swal-account-name-container",
      );
      const nameInput = document.getElementById("swal-account-name");

      accInput.addEventListener("input", async (e) => {
        if (e.target.value.length === 10) {
          nameContainer.classList.remove("hidden");
          nameInput.value = "Validating...";
          try {
            const response = await apiFetch(
              `${window.FLEZ_API_BASE || ""}/api/data/account/validate`,
              {
                method: "POST",
                body: JSON.stringify({
                  account_number: e.target.value,
                  bank_code: bankSelect.value,
                }),
              },
            );
            const data = await response.json();
            if (data.status && data.data && data.data.length > 0) {
              nameInput.value = data.data[0].account_name;
            } else {
              nameInput.value = "Invalid account details";
            }
          } catch (err) {
            nameInput.value = "Validation failed";
          }
        } else {
          nameContainer.classList.add("hidden");
        }
      });
    },
    preConfirm: () => {
      const bank = document.getElementById("swal-bank").value;
      const bankName =
        document.getElementById("swal-bank").options[
          document.getElementById("swal-bank").selectedIndex
        ].text;
      const number = document.getElementById("swal-account-number").value;
      const name = document.getElementById("swal-account-name").value;

      if (
        !bank ||
        number.length !== 10 ||
        name.includes("Validating") ||
        name.includes("Invalid")
      ) {
        Swal.showValidationMessage("Please provide valid account details");
        return false;
      }
      return { bank, bankName, number, name };
    },
  });

  if (formValues) {
    try {
      const response = await apiFetch(
        `${window.FLEZ_API_BASE || ""}/api/user/data/add/withdrawalAccount`,
        {
          method: "POST",
          body: JSON.stringify({
            account_number: formValues.number,
            account_name: formValues.name,
            bank_code: formValues.bank,
            bank_name: formValues.bankName,
          }),
        },
      );
      const data = await response.json();
      if (data.status) {
        Swal.fire("Added", "Withdrawal account saved.", "success");
        await loadSettingsData();
      } else {
        Swal.fire("Error", data.message || "Failed to add account.", "error");
      }
    } catch (err) {
      Swal.fire("Error", "An unexpected error occurred.", "error");
    }
  }
}



async function saveBranding() {
  const storeName = document.getElementById("branding-store-name").value;
  const primaryColor = document.getElementById("primary-color-input").value;
  const logoInput = document.getElementById("logo-upload-input");

  const formData = new FormData();
  formData.append("business_name", storeName);
  formData.append("store_name", storeName);
  formData.append("primary_color", primaryColor);

  if (logoInput.files[0]) {
    formData.append("business_image", logoInput.files[0]);
  }

  const response = await apiFetch(
    `${window.FLEZ_API_BASE || ""}/api/user/data/update/settings`,
    {
      method: "POST",
      body: formData,
    },
  );

  return response.status;
}

async function saveSecurity() {
  const currentPass = document.getElementById("current-password").value;
  const newPass = document.getElementById("new-password").value;
  const confirmPass = document.getElementById("confirm-password").value;

  if (!currentPass) return true; // Nothing to change

  if (newPass !== confirmPass) {
    throw new Error("New passwords do not match");
  }

  const response = await apiFetch(
    `${window.FLEZ_API_BASE || ""}/api/user/update/secure`,
    {
      method: "PATCH",
      body: JSON.stringify({
        user_pass: currentPass,
        new_pass: newPass,
      }),
    },
  );

  const data = await response.json();
  if (!data.status) throw new Error(data.message || "Failed to update password");

  // Clear fields
  document.getElementById("current-password").value = "";
  document.getElementById("new-password").value = "";
  document.getElementById("confirm-password").value = "";

  return true;
}

async function saveGeneralSettings() {
  const settings = {
    ...privacySettings,
    notifications_sales:
      document.getElementById("noti-sales").getAttribute("data-enabled") ===
      "true",
    notifications_email:
      document.getElementById("noti-email").getAttribute("data-enabled") ===
      "true",
    notifications_stock:
      document.getElementById("noti-stock").getAttribute("data-enabled") ===
      "true",
    biometric_login:
      document
        .getElementById("toggle-biometric-btn")
        .getAttribute("data-enabled") === "true",
    two_factor_enabled:
      document.getElementById("toggle-2fa-btn").getAttribute("data-enabled") ===
      "true",
  };

  const response = await apiFetch(
    `${window.FLEZ_API_BASE || ""}/api/user/privacy/settings`,
    {
      method: "PATCH",
      body: JSON.stringify({ settings }),
    },
  );

  const enableLoyalty = document.getElementById("toggle-loyalty").getAttribute("data-enabled") === "true";
  const loyaltyPointEq = document.getElementById("loyalty-point-equivalent").value || 0;
  const vatPerc = document.getElementById("vat-percentage").value || 0;

  await apiFetch(
    `${window.FLEZ_API_BASE || ""}/api/user/data/update/settings`,
    {
      method: "PATCH",
      body: JSON.stringify({
        enable_loyalty: enableLoyalty,
        loyalty_point_equivalent: parseInt(loyaltyPointEq, 10),
        vat_percentage: parseFloat(vatPerc)
      }),
    }
  );

  return response.status;
}

async function handle2FAToggle() {
  const btn = document.getElementById("toggle-2fa-btn");
  const dot = document.getElementById("toggle-2fa-dot");
  const currentlyEnabled = btn.classList.contains("bg-primary");

  if (!currentlyEnabled) {
    // Navigate to dedicated 2FA setup page
    window.location.href = "/2fa-setup";
  } else {
    // Disable 2FA
    const { value: confirmed } = await Swal.fire({
      title: "Disable 2FA?",
      text: "This will reduce your account security.",
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Yes, disable",
    });

    if (confirmed) {
      const response = await apiFetch(
        `${window.FLEZ_API_BASE || ""}/api/user/2fa/disable`,
        {
          method: "POST",
        },
      );
      if (response.status) {
        btn.classList.remove("bg-primary");
        btn.classList.add("bg-slate-700");
        dot.style.left = "4px";
        dot.style.right = "auto";
        Swal.fire(
          "Disabled",
);
      }
    }
  }
}

let isTogglingPayrollOtp = false;

async function handlePayrollOtpToggle() {
  if (isTogglingPayrollOtp) return;
  isTogglingPayrollOtp = true;

  const btn = document.getElementById("toggle-payroll-otp-btn");
  const currentlyEnabled = btn ? btn.getAttribute("data-enabled") === "true" : true;
  const newState = !currentlyEnabled;

  try {
    if (btn) btn.classList.add("opacity-50", "pointer-events-none");

    // 1. Request PIN
    await apiFetch("/api/auth/payroll/pin", { method: "POST" });

    // 2. Prompt for PIN
    const { value: pin } = await Swal.fire({
      title: "Security Verification",
      text: "Enter the 6-digit OTP sent to your email to authorize this change.",
      input: "password",
      inputAttributes: {
        maxlength: 6,
        autocapitalize: "off",
        autocorrect: "off",
      },
      showCancelButton: true,
      confirmButtonText: "Verify",
      confirmButtonColor: "#cfff45",
      background: "var(--swal-bg)",
      color: "var(--swal-text)",
      inputValidator: (value) => {
        if (!value || value.length !== 6) {
          return "Please enter a valid 6-digit PIN";
        }
      },
    });

    if (!pin) {
      if (btn) btn.classList.remove("opacity-50", "pointer-events-none");
      return; // User cancelled
    }

    // 3. Send update with PIN
    const response = await apiFetch(
      `${window.FLEZ_API_BASE || ""}/api/user/data/update/settings`,
      {
        method: "PATCH",
        body: JSON.stringify({
          enable_payroll_otp: newState,
          auth_pin: pin,
        }),
      },
    );

    const result = await response.json();
    if (result.status) {
      // Update UI
      updateToggleUI("toggle-payroll-otp-btn", newState);

      // Update Local Storage for persistence
      const userData = JSON.parse(localStorage.getItem("user_data") || "{}");
      if (userData.business_details && userData.business_details[0]) {
        userData.business_details[0].enable_payroll_otp = newState;
        localStorage.setItem("user_data", JSON.stringify(userData));
      }

      showToast(
        "Payroll OTP",
        newState ? "Payroll OTP Enabled" : "Payroll OTP Disabled",
        "success"
      );
    } else {
      throw new Error(result.message);
    }
  } catch (err) {
    if (btn) btn.classList.remove("opacity-50", "pointer-events-none");
    Swal.fire({
      icon: "error",
      title: "Error",
      text: err.message || "Failed to update setting",
      background: "var(--swal-bg)",
      color: "var(--swal-text)",
    });
  } finally {
    isTogglingPayrollOtp = false;
  }
}

async function deleteWithdrawalAccount(id) {
  const { value: confirmed } = await Swal.fire({
    title: "Delete Account?",
    text: "Remove this withdrawal method?",
    icon: "warning",
    showCancelButton: true,
    confirmButtonText: "Delete",
  });

  if (confirmed) {
    const response = await apiFetch(
      `${window.FLEZ_API_BASE || ""}/api/user/data/delete/withdrawal`,
      {
        method: "POST",
        body: JSON.stringify({ id }),
      },
    );
    if (response.status) {
      await loadSettingsData(); // Refresh list
      Swal.fire("Deleted", "Withdrawal account removed.", "success");
    }
  }
}

// Helpers
function setInputValue(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

function setSelectValue(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

function updateToggleUI(id, enabled) {
  const btn = document.getElementById(id);
  if (!btn) return;

  btn.setAttribute("data-enabled", enabled ? "true" : "false");
  const dot = btn.querySelector("div");

  if (enabled) {
    btn.classList.remove("bg-slate-700");
    btn.classList.add("bg-primary");
    if (dot) {
      dot.classList.remove("left-1");
      dot.classList.add("right-1");
    }
  } else {
    btn.classList.remove("bg-primary");
    btn.classList.add("bg-slate-700");
    if (dot) {
      dot.classList.remove("right-1");
      dot.classList.add("left-1");
    }
  }
}

function handleImagePreview(event, containerSelector) {
  const file = event.target.files[0];
  if (file) {
    if (!file.type.startsWith("image/")) {
      Swal.fire("Invalid Format", "Please select a valid image file.", "error");
      event.target.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      const container = document.querySelector(containerSelector);
      if (container) {
        container.innerHTML = `<img src="${e.target.result}" class="w-full h-full object-cover" />`;
      }
    };
    reader.readAsDataURL(file);
  }
}

function handleLogoPreview(event) {
  const file = event.target.files[0];
  if (file) {
    if (!file.type.startsWith("image/")) {
      Swal.fire("Invalid Format", "Please select a valid image file.", "error");
      event.target.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      const preview = document.getElementById("logo-preview-img");
      const container = document.getElementById("logo-preview-container");
      const placeholder = document.getElementById("logo-upload-placeholder");

      if (preview && container && placeholder) {
        preview.src = e.target.result;
        container.classList.remove("hidden");
        placeholder.classList.add("hidden");
      }
    };
    reader.readAsDataURL(file);
  }
}

function formatDate(val) {
  if (!val) return "N/A";
  try {
    let date;
    if (!isNaN(val) && String(val).trim() !== "") {
      const num = Number(val);
      // If less than 10 billion, it's likely seconds instead of milliseconds
      if (num < 10000000000) {
        date = new Date(num * 1000);
      } else {
        date = new Date(num);
      }
    } else {
      date = new Date(val);
    }
    
    if (isNaN(date.getTime())) return val;
    
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return val;
  }
}

async function loadStoreRegions() {
  const list = document.getElementById("allowed-countries-list");
  if (!list) return;

  try {
    const res = await apiFetch(
      `${window.FLEZ_API_BASE || ""}/admin/api/countries`,
    );
    const data = await res.json();

    if (data.status && data.countries) {
      if (data.countries.length === 0) {
        list.innerHTML = `
                    <div class="col-span-full py-12 text-center border-2 border-dashed border-white/5 rounded-3xl">
                        <p class="text-xs text-slate-500">No regions added yet.</p>
                    </div>
                `;
        return;
      }

      list.innerHTML = data.countries
        .map(
          (country) => `
                <div class="p-5 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-between group hover:border-primary/30 transition-all">
                    <div class="flex items-center gap-4">
                        <div class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary font-bold text-xs">
                            ${country.code}
                        </div>
                        <div>
                            <p class="text-sm font-bold text-white">${country.name}</p>
                            <p class="text-[10px] text-slate-500">Active Region</p>
                        </div>
                    </div>
                    <button onclick="deleteStoreRegion(${country.id})" class="p-2 text-slate-500 hover:text-rose-500 hover:bg-rose-500/10 rounded-lg transition-all opacity-0 group-hover:opacity-100">
                        <i data-lucide="trash-2" class="w-4 h-4"></i>
                    </button>
                </div>
            `,
        )
        .join("");

      if (window.lucide) window.lucide.createIcons();
    }
  } catch (err) {
    console.error("Failed to load regions:", err);
  }
}

async function handleAddCountry() {
  const { value: formValues } = await Swal.fire({
    title: "Add Store Region",
    html: `
            <div class="space-y-4 text-left p-2">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-2">Country Name</label>
                    <input id="swal-country-name" type="text" placeholder="e.g. Canada" class="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white outline-none focus:border-primary">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-2">Country Code (ISO)</label>
                    <input id="swal-country-code" type="text" maxlength="5" placeholder="e.g. CA" class="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white outline-none focus:border-primary">
                </div>
            </div>
        `,
    showCancelButton: true,
    confirmButtonText: "Add Region",
    background: "var(--swal-bg)",
    color: "var(--swal-text)",
    preConfirm: () => {
      const name = document.getElementById("swal-country-name").value;
      const code = document.getElementById("swal-country-code").value;
      if (!name || !code) {
        Swal.showValidationMessage("Please provide both name and code");
        return false;
      }
      return { name, code };
    },
  });

  if (formValues) {
    try {
      const res = await apiFetch(
        `${window.FLEZ_API_BASE || ""}/admin/api/countries`,
        {
          method: "POST",
          body: JSON.stringify(formValues),
        },
      );
      const data = await res.json();
      if (data.status) {
        Swal.fire("Added", "Store region added successfully.", "success");
        await loadStoreRegions();
      } else {
        Swal.fire("Error", data.message || "Failed to add region.", "error");
      }
    } catch (err) {
      Swal.fire("Error", "An unexpected error occurred.", "error");
    }
  }
}

async function deleteStoreRegion(id) {
  const { value: confirmed } = await Swal.fire({
    title: "Delete Region?",
    text: "Stores in this region may be affected.",
    icon: "warning",
    showCancelButton: true,
    confirmButtonText: "Yes, delete",
    background: "var(--swal-bg)",
    color: "var(--swal-text)",
  });

  if (confirmed) {
    try {
      const res = await apiFetch(
        `${window.FLEZ_API_BASE || ""}/admin/api/countries/${id}`,
        {
          method: "DELETE",
        },
      );
      const data = await res.json();
      if (data.status) {
        await loadStoreRegions();
        Swal.fire("Deleted", "Region removed.", "success");
      }
    } catch (err) {
      Swal.fire("Error", "Failed to delete region.", "error");
    }
  }
}
var _overlayPlan = null;
var _overlayDuration = "one_amount";

function openSubscriptionOverlay(planId) {
  const plan = (window.allSubscriptions || []).find(
    (p) => String(p.uniq_id) === String(planId),
  );
  if (!plan) return;
  _overlayPlan = plan;
  _overlayDuration = "one_amount";

  // Populate left column
  document.getElementById("overlay-plan-badge").textContent =
    plan.one_amount == "0" ? "Free Plan" : "Paid Plan";
  document.getElementById("overlay-plan-name").textContent = plan.plan_name;
  document.getElementById("overlay-plan-description").textContent =
    plan.description || "Unlock powerful features with this plan.";

  // Features (split description by comma or use defaults)
  const features = plan.features
    ? plan.features.split(",").map((f) => f.trim())
    : ["Access all core features", "Priority support", "Analytics dashboard"];
  document.getElementById("overlay-plan-features").innerHTML = features
    .map(
      (f) => `
                <div class="flex items-center gap-3 text-sm text-slate-700 dark:text-slate-300">
                    <div class="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                        <i data-lucide="check" class="w-3 h-3 text-primary"></i>
                    </div>
                    ${f}
                </div>
            `,
    )
    .join("");

  const isFreePlan = parseFloat(plan.one_amount || 0) === 0;

  const userData =
    typeof window.userData !== "undefined"
      ? window.userData
      : JSON.parse(localStorage.getItem("user_data") || "{}");
  const business = userData?.business_details?.[0];
  const currentPlan = business
    ? (window.allSubscriptions || []).find(
        (p) => String(p.uniq_id) === String(business.plan_code),
      )
    : null;

  const isCurrentPlanFree =
    currentPlan && parseFloat(currentPlan.one_amount || 0) === 0;

  const isUpgrade =
    currentPlan &&
    !isCurrentPlanFree &&
    parseFloat(plan.one_amount || 0) >
      parseFloat(currentPlan.one_amount || 0) &&
    business.subscription_expiry &&
    new Date(business.subscription_expiry) > new Date();

  let upgradeAmount = 0;
  let remainingDays = 0;
  if (isUpgrade) {
    remainingDays = Math.max(
      0,
      Math.ceil(
        (new Date(business.subscription_expiry) - new Date()) /
          (1000 * 60 * 60 * 24),
      ),
    );
    const oldDaily = parseFloat(currentPlan.one_amount || 0) / 30;
    const newDaily = parseFloat(plan.one_amount || 0) / 30;
    upgradeAmount = Math.max(0, remainingDays * (newDaily - oldDaily));
    _overlayDuration = "prorated_upgrade";
  }

  if (isFreePlan) {
    document.getElementById("overlay-duration-options").innerHTML = `
                    <div class="p-6 rounded-2xl bg-primary/10 border border-primary/30 text-center animate-in fade-in zoom-in">
                        <div class="w-12 h-12 bg-primary/20 rounded-full flex items-center justify-center mx-auto mb-3">
                            <i data-lucide="gift" class="w-6 h-6 text-primary"></i>
                        </div>
                        <h4 class="text-xl font-bold text-white mb-1">Free Forever</h4>
                        <p class="text-sm text-slate-400">No payment is required for this subscription.</p>
                    </div>
                `;
  } else if (isUpgrade) {
    document.getElementById("overlay-duration-options").innerHTML = `
                    <div class="p-6 rounded-2xl bg-primary/5 border border-primary/50 text-center animate-in fade-in zoom-in shadow-xl shadow-primary/5">
                        <div class="w-12 h-12 bg-primary/20 rounded-full flex items-center justify-center mx-auto mb-3">
                            <i data-lucide="arrow-up-circle" class="w-6 h-6 text-primary"></i>
                        </div>
                        <h4 class="text-xl font-bold text-white mb-1">Prorated Upgrade</h4>
                        <p class="text-sm text-slate-400 mb-3">You will be charged for the remaining <strong class="text-white">${remainingDays} days</strong> of your current billing cycle.</p>
                        <div class="inline-flex items-center gap-2 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-sm">
                            <span class="text-slate-400">Expiry Date:</span>
                            <span class="font-bold text-white">${new Date(business.subscription_expiry).toLocaleDateString()}</span>
                        </div>
                    </div>
                `;
  } else {
    const durations = [
      { key: "one_amount", label: "1 Month", months: 1 },
      { key: "three_months", label: "3 Months", months: 3 },
      { key: "six_months", label: "6 Months", months: 6 },
      { key: "twelve_months", label: "12 Months", months: 12 },
    ];
    document.getElementById("overlay-duration-options").innerHTML = durations
      .map((d) => {
        const price = parseFloat(plan[d.key] || 0);
        const isFreeOpt = price === 0;
        return `
                        <button
                            onclick="selectOverlayDuration('${d.key}', ${price})"
                            data-dur-key="${d.key}"
                            class="duration-opt w-full p-4 rounded-2xl border text-left transition-all
                                   ${d.key === "one_amount" ? "border-primary/50 bg-primary/5" : "border-white/10 bg-white/5 hover:border-primary/30"}"
                        >
                            <div class="flex justify-between items-center">
                                <span class="text-sm font-bold text-slate-900 dark:text-white">${d.label}</span>
                                <span class="text-sm font-bold ${d.key === "one_amount" ? "text-primary" : "text-slate-400"}">
                                    ${isFreeOpt ? "FREE" : window.STORE_CURRENCY_SYMBOL + price.toLocaleString()}
                                </span>
                            </div>
                            ${d.months > 1 && !isFreeOpt ? `<p class="text-[10px] text-slate-500 mt-1">~${window.STORE_CURRENCY_SYMBOL}${(price / d.months).toLocaleString(undefined, { maximumFractionDigits: 0 })}/mo</p>` : ""}
                        </button>
                    `;
      })
      .join("");
  }

  // Set initial price
  const initPrice = isUpgrade
    ? upgradeAmount
    : parseFloat(plan.one_amount || 0);
  document.getElementById("overlay-total-price").textContent =
    initPrice === 0
      ? "FREE"
      : window.STORE_CURRENCY_SYMBOL + initPrice.toLocaleString(undefined, { maximumFractionDigits: 0 });

  // Show overlay
  const overlay = document.getElementById("subscription-plan-overlay");
  overlay.classList.remove("hidden");
  document.body.style.overflow = "hidden";

  if (window.lucide) window.lucide.createIcons();
}

function selectOverlayDuration(key, price) {
  _overlayDuration = key;
  document.querySelectorAll(".duration-opt").forEach((btn) => {
    const isSelected = btn.dataset.durKey === key;
    btn.className = btn.className
      .replace(/border-primary\/50 bg-primary\/5/g, "")
      .replace(/border-white\/10 bg-white\/5 hover:border-primary\/30/g, "")
      .trim();
    btn.classList.add(
      ...(isSelected
        ? ["border-primary/50", "bg-primary/5"]
        : ["border-white/10", "bg-white/5", "hover:border-primary/30"]),
    );
    btn
      .querySelector("span:last-child")
      .classList.toggle("text-primary", isSelected);
    btn
      .querySelector("span:last-child")
      .classList.toggle("text-slate-400", !isSelected);
  });
  document.getElementById("overlay-total-price").textContent =
    price === 0 ? "FREE" : window.STORE_CURRENCY_SYMBOL + price.toLocaleString();
}

function closeSubscriptionOverlay() {
  document.getElementById("subscription-plan-overlay").classList.add("hidden");
  document.body.style.overflow = "";
}

async function confirmSubscriptionPlan() {
  if (!_overlayPlan) return;
  const btn = document.querySelector(
    '#subscription-plan-overlay button[onclick="confirmSubscriptionPlan()"]',
  );
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Processing...";
  }

  try {
    const response = await apiFetch(
      `${window.FLEZ_API_BASE || ""}/api/user/subscription/renew`,
      {
        method: "POST",
        body: JSON.stringify({
          duration: _overlayDuration,
          plan_id: _overlayPlan.uniq_id,
        }),
      },
    );
    const data = await response.json();
    if (data.status) {
      closeSubscriptionOverlay();
      Swal.fire({
        title: "Subscribed!",
        text: data.message || "Plan activated successfully.",
        icon: "success",
        background: "var(--swal-bg)",
        color: "var(--swal-text)",
      });
      if (typeof loadSettingsData === "function") await loadSettingsData();
    } else {
      throw new Error(data.message || "Failed to subscribe.");
    }
  } catch (err) {
    Swal.fire({
      title: "Error",
      text: err.message,
      icon: "error",
      background: "var(--swal-bg)",
      color: "var(--swal-text)",
    });
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML =
        'Confirm Subscription <i data-lucide="arrow-right" class="w-5 h-5 group-hover:translate-x-1 transition-transform"></i>';
    }
    if (window.lucide) window.lucide.createIcons();
  }
}

function updateVerificationBanner(data) {
  const pill = document.getElementById("verification-status-pill");
  const subtext = document.getElementById("verification-banner-subtext");
  if (!pill || !data) return;

  const verifications = data.verification || [];
  const kyc = verifications.find(v => (v.verification_type || '').toUpperCase() === 'KYC');
  const kyb = verifications.find(v => (v.verification_type || '').toUpperCase() === 'KYB');

  let kycStatus = kyc ? String(kyc.verification_status) : null;
  let kybStatus = kyb ? String(kyb.verification_status) : null;

  // Ground truth: respect boolean flags from UserSecure
  const isKycVerified = Boolean(data.kyc_verified);
  const isKybVerified = Boolean(data.kyb_verified);

  if (!isKycVerified && kycStatus === '1') {
    kycStatus = null;
  }
  if (!isKybVerified && kybStatus === '1') {
    kybStatus = null;
  }

  // 1. Both Tiers Verified
  if (isKycVerified && isKybVerified) {
    pill.textContent = "Verified";
    pill.className = "text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
    if (subtext) subtext.textContent = "Your account is fully verified with unlimited withdrawal limits.";
    if (window.lucide) window.lucide.createIcons();
    return;
  }

  // 2. Tier 1 is Verified, Tier 2 is in progress or pending
  if (isKycVerified) {
    if (kybStatus === '0') {
      pill.textContent = "Tier 2 Pending";
      pill.className = "text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20";
      if (subtext) subtext.textContent = "Tier 1 verified. Your Tier 2 corporate verification is currently under review.";
    } else if (kybStatus === '2') {
      pill.textContent = "Action Required";
      pill.className = "text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20";
      if (subtext) subtext.textContent = "Tier 1 verified. Tier 2 corporate verification was rejected. Click to resubmit.";
    } else {
      pill.textContent = "Tier 1 Verified";
      pill.className = "text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20";
      if (subtext) subtext.textContent = "Tier 1 verified - proceed to Tier 2 to unlock unlimited platform withdrawals.";
    }
    if (window.lucide) window.lucide.createIcons();
    return;
  }

  // 3. Tier 1 is NOT Verified (Tier 2 is completely hidden and irrelevant)
  if (kycStatus === '0') {
    pill.textContent = "Tier 1 Pending";
    pill.className = "text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20";
    if (subtext) subtext.textContent = "Your Tier 1 personal identity verification is currently under review.";
  } else if (kycStatus === '2') {
    pill.textContent = "Action Required";
    pill.className = "text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20";
    if (subtext) subtext.textContent = "Your Tier 1 identity verification was rejected. Click to review and resubmit.";
  } else {
    // Default: No tier is verified
    pill.textContent = "Verify Account";
    pill.className = "text-[11px] font-medium px-2 py-0.5 rounded-full border border-white/10 text-slate-400";
    if (subtext) subtext.textContent = "Complete your identity verification (Tier 1) to unlock daily platform withdrawals.";
  }

  if (window.lucide) window.lucide.createIcons();
}

// Auto-run if settings container is present on direct page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('settings-content-container') || document.getElementById('save-settings')) {
      initSettingsPage();
    }
  });
} else {
  if (document.getElementById('settings-content-container') || document.getElementById('save-settings')) {
    initSettingsPage();
  }
}

