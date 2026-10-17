/**
 * Store Settings JS
 * Handles loading and saving of store configuration
 */

var settingsLogoClearPending = false;
var settingsLogoObjectUrl = null;
var settingsBannerClearPending = false;
var settingsBannerObjectUrl = null;
var settingsCurrentBusiness = {};

// Expose globally for dashboard.js and SPA navigation
window.initStoreSettings = initStoreSettings;

function renderStoreLogoPreview(logoUrl, filenameLabel) {
  const removeBtn = document.getElementById("settings-remove-logo-btn");
  const headerLogo = document.getElementById("store-logo-header");

  if (removeBtn) {
    removeBtn.classList.toggle("hidden", !logoUrl);
  }

  if (headerLogo) {
    if (logoUrl) {
      headerLogo.innerHTML = `<img src="${logoUrl}" alt="Store logo" class="w-full h-full object-cover">`;
    } else {
      headerLogo.innerHTML =
        '<i data-lucide="store" class="w-10 h-10 sm:w-11 sm:h-11"></i>';
    }
  }

  if (typeof lucide !== "undefined") lucide.createIcons();
}

function renderStoreBannerPreview(bannerUrl) {
  const headerBanner = document.getElementById("store-banner-header");
  const removeBtn = document.getElementById("settings-remove-banner-btn");

  if (removeBtn) {
    removeBtn.classList.toggle("hidden", !bannerUrl);
  }

  if (headerBanner) {
    if (bannerUrl) {
      headerBanner.innerHTML = `<img src="${bannerUrl}" alt="Store banner" class="w-full h-full object-cover">`;
    } else {
      headerBanner.innerHTML = `<div class="absolute right-0 top-0 w-1/2 h-full opacity-20" style="background-image: linear-gradient(#cfff45 1px, transparent 1px), linear-gradient(90deg, #cfff45 1px, transparent 1px); background-size: 50px 50px;"></div>`;
    }
  }
}

function initStoreSettings() {
  console.log("Initializing Store Settings...");

  // Failsafe: Remove Swup animation class if stuck
  document.documentElement.classList.remove("is-animating");

  loadStoreSettings();
  bindStoreSettingsEvents();
}

async function loadStoreSettings(showSkeleton = true) {
  console.log("Fetching fresh store settings...");
  const skeleton = document.getElementById("store-settings-skeleton");
  const mainWrapper = document.getElementById("store-settings-main-wrapper");

  if (showSkeleton && skeleton && mainWrapper) {
    skeleton.classList.remove("hidden");
    mainWrapper.classList.add("hidden");
  }

  try {
    const response = await apiFetch(`${window.CONFIG.API_BASE}/api/user/data`, {
      method: "POST",
    });
    const result = await response.json();
    if (result.status) {
      localStorage.setItem("user_data", JSON.stringify(result.data));
      await renderStoreSettings(result.data);
      if (typeof renderUserData === "function") renderUserData();
    }
  } catch (error) {
    console.error("Error fetching fresh user data:", error);
    const userData = JSON.parse(localStorage.getItem("user_data"));
    if (userData) await renderStoreSettings(userData);
  } finally {
    if (showSkeleton && skeleton && mainWrapper) {
      skeleton.classList.add("hidden");
      mainWrapper.classList.remove("hidden");
    }
  }
}

async function renderStoreSettings(data) {
  const business = data.business_details?.[0];
  if (!business) {
    console.error("CRITICAL: No business details found in user data object");
    return;
  }
  
  settingsCurrentBusiness = business;

  if (
    typeof business.store_pickup_locations === "string" &&
    business.store_pickup_locations.trim()
  ) {
    try {
      business.store_pickup_locations = JSON.parse(
        business.store_pickup_locations,
      );
    } catch (e) {
      console.error("Pickup Locations Parse Error:", e);
      business.store_pickup_locations = {};
    }
  }

  const allowedCountries = data.allowed_countries || [];
  const withdrawalAccounts = data.withdrawal_accounts || [];

  // 1. Store Status & Publication
  const publishToggle = document.getElementById(
    "settings-store-publish-toggle",
  );
  const statusText = document.getElementById("settings-store-status-text");
  if (publishToggle) {
    const isPublished = !!business.is_published;
    publishToggle.setAttribute("aria-checked", isPublished ? "true" : "false");
    if (statusText) {
      statusText.innerText = isPublished ? "Online" : "Offline";
      statusText.className = isPublished
        ? "text-xs font-bold text-emerald-500 uppercase tracking-widest transition-colors"
        : "text-xs font-bold text-slate-500 uppercase tracking-widest transition-colors";
    }
  }
  const hideStoreNameToggleInit = document.getElementById(
    "settings-hide-store-name",
  );
  if (hideStoreNameToggleInit) {
    hideStoreNameToggleInit.setAttribute(
      "aria-checked",
      business.hide_store_name ? "true" : "false",
    );
  }

  const hideHotProductsToggleInit = document.getElementById(
    "settings-hide-hot-products",
  );
  if (hideHotProductsToggleInit) {
    hideHotProductsToggleInit.setAttribute(
      "aria-checked",
      business.hide_hot_products ? "true" : "false",
    );
  }

  // Update Store Display Name in Header
  const storeDisplayName = document.getElementById("store-display-name");
  if (storeDisplayName) {
    storeDisplayName.innerText =
      business.store_name || business.business_name || "My Store";
  }

  // Update Store Settings Page Title
  const storeSettingsTitle = document.getElementById("store-settings-title");
  if (storeSettingsTitle) {
    storeSettingsTitle.innerText =
      business.store_name || business.business_name || "Store Settings";
  }

  // 2. Allowed Countries
  const searchInput = document.getElementById("settings-region-search-input");
  const dropdown = document.getElementById("settings-region-dropdown");
  const container = document.getElementById(
    "settings-region-dropdown-container",
  );
  const pillsContainer = document.getElementById(
    "settings-selected-regions-container",
  );
  const hiddenInputsContainer = document.getElementById(
    "settings-hidden-region-inputs",
  );

  if (dropdown && allowedCountries) {
    dropdown.innerHTML = "";
    if (allowedCountries.length === 0) {
      dropdown.innerHTML =
        '<div class="p-4 text-center text-gray-500 text-sm font-bold">No regions available</div>';
    } else {
      allowedCountries.forEach((country) => {
        const opt = document.createElement("div");
        opt.className =
          "settings-region-option p-3 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer flex items-center justify-between transition-colors";
        opt.dataset.code = country.code;
        opt.dataset.name = country.name;
        opt.innerHTML = `
                    <div class="flex items-center gap-3 pointer-events-none">
                        <div class="w-6 h-6 rounded bg-gray-100 dark:bg-gray-700 flex items-center justify-center text-gray-500">
                            <i data-lucide="map-pin" class="w-3 h-3"></i>
                        </div>
                        <div>
                            <span class="text-sm font-bold text-gray-900 dark:text-white block">${country.name}</span>
                        </div>
                    </div>
                    <i data-lucide="check" class="w-4 h-4 text-primary opacity-0 selected-check transition-opacity pointer-events-none"></i>
                `;
        dropdown.appendChild(opt);
      });
    }
    if (window.lucide) lucide.createIcons({ root: dropdown });
  }

  const options = document.querySelectorAll(".settings-region-option");
  const selectedRegions = new Set();

  window.settingsClearRegionPills = () => {
    selectedRegions.clear();
    if (pillsContainer) pillsContainer.innerHTML = "";
    if (hiddenInputsContainer) hiddenInputsContainer.innerHTML = "";
    options.forEach((opt) =>
      opt.querySelector(".selected-check")?.classList.remove("opacity-100"),
    );
  };

  window.settingsAddRegionPill = (code, name) => {
    if (selectedRegions.has(code)) return;
    selectedRegions.add(code);

    const opt = document.querySelector(
      `.settings-region-option[data-code="${code}"]`,
    );
    if (opt) opt.querySelector(".selected-check")?.classList.add("opacity-100");

    if (pillsContainer) {
      const pill = document.createElement("div");
      pill.className =
        "flex items-center gap-2 bg-primary/10 border border-primary/20 text-primary px-3 py-1.5 rounded-xl text-sm font-bold";
      pill.innerHTML = `
                ${name}
                <button type="button" class="hover:text-primary-dark remove-region-btn transition-colors" data-code="${code}">
                    <i data-lucide="x" class="w-3.5 h-3.5"></i>
                </button>
            `;
      pillsContainer.appendChild(pill);
      if (window.lucide) lucide.createIcons({ root: pill });
    }

    if (hiddenInputsContainer) {
      const hiddenInput = document.createElement("input");
      hiddenInput.type = "hidden";
      hiddenInput.name = "countries";
      hiddenInput.value = code;
      hiddenInput.dataset.code = code;
      hiddenInputsContainer.appendChild(hiddenInput);
    }
  };

  window.settingsRemoveRegionPill = (code) => {
    selectedRegions.delete(code);
    const opt = document.querySelector(
      `.settings-region-option[data-code="${code}"]`,
    );
    if (opt)
      opt.querySelector(".selected-check")?.classList.remove("opacity-100");

    if (pillsContainer) {
      const btn = pillsContainer.querySelector(`button[data-code="${code}"]`);
      if (btn) btn.closest("div").remove();
    }

    if (hiddenInputsContainer) {
      const hidden = hiddenInputsContainer.querySelector(
        `input[data-code="${code}"]`,
      );
      if (hidden) hidden.remove();
    }
  };

  if (pillsContainer) {
    pillsContainer.addEventListener("click", (e) => {
      const btn = e.target.closest("button.remove-region-btn");
      if (btn) {
        const code = btn.dataset.code;
        window.settingsRemoveRegionPill(code);
      }
    });
  }

  if (searchInput && dropdown) {
    searchInput.addEventListener("focus", () => {
      dropdown.classList.remove("hidden");
    });

    document.addEventListener("click", (e) => {
      if (container && !container.contains(e.target)) {
        dropdown.classList.add("hidden");
      }
    });

    searchInput.addEventListener("input", (e) => {
      const val = e.target.value.toLowerCase();
      options.forEach((opt) => {
        const name = opt.dataset.name.toLowerCase();
        const code = opt.dataset.code.toLowerCase();
        if (name.includes(val) || code.includes(val)) {
          opt.style.display = "flex";
        } else {
          opt.style.display = "none";
        }
      });
    });

    options.forEach((opt) => {
      opt.addEventListener("click", () => {
        const code = opt.dataset.code;
        const name = opt.dataset.name;
        if (selectedRegions.has(code)) {
          window.settingsRemoveRegionPill(code);
        } else {
          window.settingsAddRegionPill(code, name);
        }
        searchInput.value = "";
        options.forEach((o) => (o.style.display = "flex"));
      });
    });
  }

  window.settingsClearRegionPills();
  let initialCountries = business.store_countries || [];
  if (typeof initialCountries === "string") {
    try {
      initialCountries = JSON.parse(initialCountries);
    } catch (e) {
      initialCountries = [];
    }
  }

  // Fallback: If no countries, check 'countries' or 'settings_countries' fields
  // depending on API variations. Assuming `business.store_countries` is correct.
  initialCountries.forEach((code) => {
    const opt = document.querySelector(
      `.settings-region-option[data-code="${code}"]`,
    );
    const name = opt ? opt.dataset.name : code;
    window.settingsAddRegionPill(code, name);
  });

  // 3. Domains & Info
  const defaultLink = document.getElementById("settings-default-link");
  if (defaultLink) {
    defaultLink.innerText = business.store_slug || "mystore";
    defaultLink.dataset.slug = business.store_slug;
  }

  const storeNameInput = document.getElementById("settings-store-name");
  if (storeNameInput)
    storeNameInput.value = business.store_name || business.business_name || "";

  const storeDescInput = document.getElementById("settings-store-description");
  if (storeDescInput)
    storeDescInput.value =
      business.store_description || business.business_description || "";

  const slugInput = document.getElementById("settings-store-slug");
  const slugStatus = document.getElementById("settings-slug-status");
  const slugCheck = document.getElementById("settings-slug-check");
  const slugCross = document.getElementById("settings-slug-cross");
  const slugSpinner = document.getElementById("settings-slug-spinner");
  const slugContainer = document.getElementById("settings-slug-container");

  if (slugInput && defaultLink) {
    slugInput.value = business.store_slug || "";
    if (business.store_slug && slugStatus) {
      slugStatus.classList.remove("opacity-0");
      if (slugCheck) slugCheck.classList.remove("hidden");
      if (slugCross) slugCross.classList.add("hidden");
      if (slugContainer) {
        slugContainer.classList.remove(
          "border-gray-200",
          "dark:border-gray-700",
          "border-red-500/50",
        );
        slugContainer.classList.add("border-primary/50");
      }
    }

    let slugDebounceTimer;
    slugInput.addEventListener("input", (e) => {
      const val = e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "");
      e.target.value = val;
      defaultLink.innerText = val || "mystore";

      if (slugStatus && slugContainer) {
        if (val.length < 3) {
          slugStatus.classList.add("opacity-0");
          slugContainer.classList.remove(
            "border-primary/50",
            "border-red-500/50",
          );
          slugContainer.classList.add(
            "border-gray-200",
            "dark:border-gray-700",
          );
          return;
        }

        slugStatus.classList.remove("opacity-0");
        const reservedZones = [
          "www",
          "api",
          "admin",
          "mail",
          "smtp",
          "ftp",
          "static",
          "media",
          "dashboard",
        ];
        const isReserved = reservedZones.includes(val);
        const isValidFormat = val.length >= 3 && /^[a-z0-9-]+$/.test(val);
        const isValid = isValidFormat && !isReserved;

        if (isValid) {
          // Show spinner, hide others
          if (slugCheck) slugCheck.classList.add("hidden");
          if (slugCross) slugCross.classList.add("hidden");
          if (slugSpinner) slugSpinner.classList.remove("hidden");

          slugContainer.classList.remove(
            "border-red-500/50",
            "border-gray-200",
            "dark:border-gray-700",
          );
          slugContainer.classList.add("border-primary/50");

          clearTimeout(slugDebounceTimer);
          slugDebounceTimer = setTimeout(async () => {
            try {
              const response = await apiFetch("/api/user/store/check-slug", {
                method: "POST",
                body: JSON.stringify({ slug: val }),
              });
              const result = await response.json();

              if (slugSpinner) slugSpinner.classList.add("hidden");
              if (result.available) {
                if (slugCheck) slugCheck.classList.remove("hidden");
                if (slugCross) slugCross.classList.add("hidden");
                slugContainer.classList.remove("border-red-500/50");
                slugContainer.classList.add("border-primary/50");
              } else {
                if (slugCheck) slugCheck.classList.add("hidden");
                if (slugCross) slugCross.classList.remove("hidden");
                slugContainer.classList.remove("border-primary/50");
                slugContainer.classList.add("border-red-500/50");
              }
            } catch (error) {
              console.error("Error checking slug:", error);
              if (slugSpinner) slugSpinner.classList.add("hidden");
            }
          }, 500);
        } else {
          clearTimeout(slugDebounceTimer);
          if (slugCheck) slugCheck.classList.add("hidden");
          if (slugCross) slugCross.classList.remove("hidden");
          if (slugSpinner) slugSpinner.classList.add("hidden");

          slugContainer.classList.remove("border-primary/50");
          slugContainer.classList.add("border-red-500/50");
        }
      }
    });
  }

  const customDomainDisplay = document.getElementById(
    "settings-custom-domain-display",
  );
  const customDomainBtn = document.getElementById("settings-custom-domain-btn");
  if (customDomainDisplay && customDomainBtn) {
    if (business.store_custom_domain) {
      customDomainDisplay.innerText = business.store_custom_domain;
      customDomainDisplay.classList.remove("hidden");
      customDomainBtn.innerHTML = '<i data-lucide="link" class="w-3.5 h-3.5"></i> Manage Domain';
    } else {
      customDomainDisplay.classList.add("hidden");
      customDomainBtn.innerHTML = '<i data-lucide="link" class="w-3.5 h-3.5"></i> Connect Custom Domain';
    }
    if (window.lucide) {
      window.lucide.createIcons({ root: customDomainBtn });
    }
  }

  // 4. Delivery Mode
  const deliveryRadios = document.querySelectorAll(
    'input[name="deliveryMode"]',
  );
  const selfDeliverySettings = document.getElementById(
    "self-delivery-settings",
  );
  const baseFeeInput = document.getElementById("store-delivery-base-fee");
  const weightFeeInput = document.getElementById("store-delivery-fee-weight");
  const payInstantlyCheckbox = document.getElementById(
    "store-delivery-pay-instantly",
  );
  const payOnDeliveryCheckbox = document.getElementById(
    "store-delivery-pay-on-delivery",
  );

  if (baseFeeInput)
    baseFeeInput.value = business.store_delivery_base_fee || "0.00";
  if (weightFeeInput)
    weightFeeInput.value = business.store_delivery_fee_per_weight || "0.00";
  if (payInstantlyCheckbox)
    payInstantlyCheckbox.checked =
      business.store_delivery_pay_instantly !== false;
  if (payOnDeliveryCheckbox)
    payOnDeliveryCheckbox.checked =
      business.store_delivery_pay_on_delivery === true;

  const systemDeliverySettings = document.getElementById(
    "system-delivery-settings",
  );

  window.toggleStoreDeliverySettings = async (mode) => {
    if (selfDeliverySettings && systemDeliverySettings) {
      if (mode === "self") {
        selfDeliverySettings.classList.remove("hidden");
        systemDeliverySettings.classList.add("hidden");
      } else if (mode === "system") {
        selfDeliverySettings.classList.add("hidden");
        systemDeliverySettings.classList.remove("hidden");
        // Always generate accordions when system delivery is selected
        if (window.generateSettingsPickupAccordions) {
          await window.generateSettingsPickupAccordions();
        }
      } else {
        selfDeliverySettings.classList.add("hidden");
        systemDeliverySettings.classList.add("hidden");
      }
    }
  };

  // --- Delivery Location Logic ---
  const COUNTRY_NAMES = {
    NG: "Nigeria",
    KE: "Kenya",
    GH: "Ghana",
    ZA: "South Africa",
  };

  let settingsCurrentCountriesStr = "";

  window.removeSettingsRegion = (e, countryCode) => {
    e.stopPropagation();

    // Remove from the hidden inputs block
    const existingInput = document.querySelector(
      `input[name="countries"][value="${countryCode}"]`,
    );
    if (existingInput) existingInput.remove();

    // Also remove the visual pill in the General tab if it exists
    const pill = document.querySelector(
      `.settings-region-pill[data-code="${countryCode}"]`,
    );
    if (pill) pill.remove();

    // Remove from the business object so it doesn't get restored
    if (business && business.store_countries) {
        business.store_countries = business.store_countries.filter(c => c !== countryCode);
    }

    // Re-generate accordions
    window.generateSettingsPickupAccordions();
  };

  window.settingsDeliveryIsLoading = false;

  window.generateSettingsPickupAccordions = async (force = false) => {
    const accordionContainer = document.getElementById(
      "settings-pickup-locations-accordion",
    );
    if (!accordionContainer) return;

    // Collect countries from the current form hidden inputs (added dynamically in Settings)
    const countryInputs = document.querySelectorAll('input[name="countries"]');
    let countries = Array.from(countryInputs).map((i) => i.value);
    if (countries.length === 0 && business.store_countries) {
      countries = business.store_countries; // initial fallback if inputs aren't in DOM yet
    }

    // Deduplicate countries to prevent duplicate API requests
    countries = [...new Set(countries)];

    const newCountriesStr = [...countries].sort().join(",");
    if (!force && newCountriesStr === settingsCurrentCountriesStr) return;
    settingsCurrentCountriesStr = newCountriesStr;

    accordionContainer.innerHTML = `
            <div id="settings-pickup-skeleton" class="space-y-4 animate-pulse">
                <div class="h-16 bg-gray-200 dark:bg-gray-700 rounded-2xl w-full"></div>
                <div class="h-16 bg-gray-200 dark:bg-gray-700 rounded-2xl w-full"></div>
            </div>
            <div id="settings-pickup-content" class="hidden space-y-4"></div>
        `;

    window.settingsDeliveryIsLoading = true;
    const contentDiv = document.getElementById("settings-pickup-content");
    const skeletonDiv = document.getElementById("settings-pickup-skeleton");

    if (countries.length === 0) {
      accordionContainer.innerHTML = `<div class="p-4 text-center text-gray-500 text-sm">No regions selected. Add allowed regions in the General tab.</div>`;
      window.settingsDeliveryIsLoading = false;
      return;
    }

    let finalHtml = "";

    countries.forEach((countryCode, idx) => {
      const countryName = COUNTRY_NAMES[countryCode] || countryCode;
      const savedLoc =
        (business.store_pickup_locations &&
          business.store_pickup_locations[countryCode]) ||
        {};
      const isFirst = idx === 0;

      const accHtml = `
              <div class="border border-gray-200 dark:border-gray-700 rounded-2xl overflow-hidden bg-white dark:bg-gray-800 settings-pickup-accordion-item" data-country="${countryCode}">
                <button type="button" class="w-full px-5 py-4 flex items-center justify-between bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" onclick="this.nextElementSibling.classList.toggle('hidden')">
                  <span class="font-bold text-gray-900 dark:text-white text-sm">${countryName} Pickup Location</span>
                  <div class="flex items-center gap-3">
                    <div class="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors text-red-500 z-10" onclick="window.removeSettingsRegion(event, '${countryCode}')" title="Remove Region">
                      <i data-lucide="trash-2" class="w-4 h-4"></i>
                    </div>
                    <i data-lucide="chevron-down" class="w-5 h-5 text-gray-500 pointer-events-none"></i>
                  </div>
                </button>
                <div class="p-5 border-t border-gray-200 dark:border-gray-700 ${isFirst ? "" : "hidden"}">
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div>
                      <label class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">State</label>
                      <select class="settings-pickup-state block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/50 py-2.5 px-3 text-sm text-gray-900 dark:text-white focus:border-primary focus:ring-primary">
                        <option value="">Select State</option>
                      </select>
                    </div>
                    <div>
                      <label class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">LGA / Province</label>
                      <select class="settings-pickup-lga block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/50 py-2.5 px-3 text-sm text-gray-900 dark:text-white focus:border-primary focus:ring-primary" disabled>
                        <option value="">Select LGA / Province</option>
                      </select>
                    </div>
                  </div>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Street Address</label>
                      <input type="text" class="settings-pickup-address block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/50 py-2.5 px-3 text-sm text-gray-900 dark:text-white focus:border-primary focus:ring-primary" placeholder="E.g., 123 Main Street" value="${savedLoc.address || ""}">
                    </div>
                    <div>
                      <label class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Pickup Contact Phone</label>
                      <input type="text" class="settings-pickup-phone block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/50 py-2.5 px-3 text-sm text-gray-900 dark:text-white focus:border-primary focus:ring-primary" placeholder="E.g., 09011111111" value="${savedLoc.phone || business.store_pickup_phone || window.userData?.user_phone || ""}">
                    </div>
                    <div>
                      <label class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Pickup Contact Email</label>
                      <input type="email" class="settings-pickup-email block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/50 py-2.5 px-3 text-sm text-gray-900 dark:text-white focus:border-primary focus:ring-primary" placeholder="E.g., teststore@gmail.com" value="${savedLoc.email || business.store_pickup_email || window.userData?.user_email || ""}">
                    </div>
                    <div>
                      <label class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Pickup Shop Name</label>
                      <input type="text" class="settings-pickup-name block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/50 py-2.5 px-3 text-sm text-gray-900 dark:text-white focus:border-primary focus:ring-primary" placeholder="E.g., Test Shop" value="${savedLoc.name || business.store_pickup_name || business.store_name || ""}">
                    </div>
                  </div>
                </div>
                </div>
              </div>
            `;
      finalHtml += accHtml;
    });

    contentDiv.innerHTML = finalHtml;
    const loadPromises = [];

    countries.forEach((countryCode) => {
      const acc = contentDiv.querySelector(`[data-country="${countryCode}"]`);
      if (!acc) return;
      const stateSelect = acc.querySelector(".settings-pickup-state");
      const lgaSelect = acc.querySelector(".settings-pickup-lga");
      const savedLoc =
        (business.store_pickup_locations &&
          business.store_pickup_locations[countryCode]) ||
        {};

      loadPromises.push(
        loadSettingsDeliveryStates(
          countryCode,
          stateSelect,
          savedLoc.state,
          lgaSelect,
          savedLoc.lga,
        ),
      );

      stateSelect.addEventListener("change", (e) => {
        loadSettingsDeliveryLgas(countryCode, e.target.value, lgaSelect);
      });
    });

    if (window.lucide) window.lucide.createIcons({ root: contentDiv });

    await Promise.all(loadPromises);

    if (skeletonDiv && contentDiv) {
      skeletonDiv.remove();
      contentDiv.classList.remove("hidden");
    }
    window.settingsDeliveryIsLoading = false;
  };

  async function loadSettingsDeliveryStates(
    countryCode,
    stateSelect,
    selectedState,
    lgaSelect,
    selectedLga,
  ) {
    try {
      const res = await fetch(`/api/delivery/states?country=${countryCode}`);
      const data = await res.json();
      if (data && data.status && data.data) {
        data.data.forEach((st) => {
          const opt = document.createElement("option");
          opt.value = st.id;
          opt.textContent = st.name;
          if (selectedState && selectedState == st.id) {
            opt.selected = true;
          }
          stateSelect.appendChild(opt);
          if (selectedState && selectedState == st.id) {
            stateSelect.value = st.id;
          }
        });
        if (selectedState) {
          await loadSettingsDeliveryLgas(
            countryCode,
            selectedState,
            lgaSelect,
            selectedLga,
          );
        }
      }
    } catch (e) {
      console.error("Error loading states:", e);
    }
  }

  async function loadSettingsDeliveryLgas(
    countryCode,
    stateId,
    lgaSelect,
    selectedLga = null,
  ) {
    if (!lgaSelect) return;
    lgaSelect.innerHTML = '<option value="">Select LGA / Province</option>';
    lgaSelect.disabled = true;
    if (!stateId) return;

    try {
      const res = await fetch(
        `/api/delivery/lgas?country=${countryCode}&state_id=${stateId}`,
      );
      const data = await res.json();
      if (data && data.status && data.data) {
        data.data.forEach((lga) => {
          const opt = document.createElement("option");
          opt.value = lga.id;
          opt.textContent = lga.name;
          if (selectedLga && selectedLga == lga.id) {
            opt.selected = true;
          }
          lgaSelect.appendChild(opt);
          if (selectedLga && selectedLga == lga.id) {
            lgaSelect.value = lga.id;
          }
        });
        lgaSelect.disabled = false;
      }
    } catch (e) {
      console.error("Error loading lgas:", e);
    }
  }
  // --- End Delivery Location Logic ---

  for (const radio of deliveryRadios) {
    if (radio.value === (business.store_delivery_type || "self")) {
      radio.checked = true;
      await window.toggleStoreDeliverySettings(radio.value);
    }
  }

  // States and LGAs are now lazy-loaded when navigating to the delivery tab

  // 5. Payout Account
  const payoutSelect = document.getElementById("settings-payout-account");
  if (payoutSelect) {
    payoutSelect.innerHTML = '<option value="">Select Account</option>';
    const currentPayoutId = business.store_payment_collection;

    console.table(
      withdrawalAccounts.map((a) => ({
        bank: a.bank_name,
        id: a.id,
        uniq_id: a.uniq_id,
        withdrawal_unique: a.withdrawal_unique,
      })),
    );

    withdrawalAccounts.forEach((acc) => {
      const option = document.createElement("option");
      // Prefer uniq_id or withdrawal_unique as they are more likely to be used in the API
      const accId = acc.uniq_id || acc.withdrawal_unique || acc.id;

      option.value = accId;
      option.innerText = `${acc.bank_name} (**** ${String(acc.account_number).slice(-4)})`;

      if (
        currentPayoutId &&
        (String(currentPayoutId) === String(acc.id) ||
          String(currentPayoutId) === String(acc.uniq_id) ||
          String(currentPayoutId) === String(acc.withdrawal_unique))
      ) {
        option.selected = true;
      }
      payoutSelect.appendChild(option);
    });
  }

  // 6. Instant Settlement & Chats
  const instantToggle = document.getElementById("settings-instant-settlement");
  if (instantToggle) {
    const isInstant =
      business.store_instant_settlement === true ||
      business.store_instant_settlement === "true";
    instantToggle.setAttribute("aria-checked", isInstant ? "true" : "false");
  }

  const livechatToggle = document.getElementById("settings-enable-livechat");
  if (livechatToggle) {
    const isLivechat =
      business.enable_livechat === true ||
      business.enable_livechat === "true" ||
      business.enable_livechat === 1 ||
      business.enable_livechat === "1";
    livechatToggle.setAttribute("aria-checked", isLivechat ? "true" : "false");
  }

  const whatsappToggle = document.getElementById("settings-enable-whatsapp");
  if (whatsappToggle) {
    const isWhatsapp = !!business.enable_whatsapp;
    whatsappToggle.setAttribute("aria-checked", isWhatsapp ? "true" : "false");
  }

  const whatsappInput = document.getElementById("settings-whatsapp-number");
  if (whatsappInput) {
    whatsappInput.value = business.store_whatsapp_number || "";
  }

  // Social Links
  const igInput = document.getElementById("settings-social-instagram");
  const twInput = document.getElementById("settings-social-twitter");
  const fbInput = document.getElementById("settings-social-facebook");
  if (igInput) igInput.value = business.store_social_instagram || "";
  if (twInput) twInput.value = business.store_social_twitter || "";
  if (fbInput) fbInput.value = business.store_social_facebook || "";

  // Shipping Policy
  const shippingQuillContainer = document.getElementById(
    "quill-editor-shipping",
  );
  if (
    shippingQuillContainer &&
    !shippingQuillContainer.classList.contains("ql-container") &&
    typeof Quill !== "undefined"
  ) {
    window.settingsShippingQuill = new Quill("#quill-editor-shipping", {
      theme: "snow",
      modules: {
        toolbar: [
          [{ header: [1, 2, 3, false] }],
          ["bold", "italic", "underline"],
          [{ list: "ordered" }, { list: "bullet" }],
          ["link", "clean"],
        ],
      },
    });
  }

  const policyType = business.store_shipping_policy_type || "default";
  const policyRadios = document.querySelectorAll(
    'input[name="shippingPolicyType"]',
  );
  const customPolicyContainer = document.getElementById(
    "custom-shipping-policy-container",
  );

  policyRadios.forEach((radio) => {
    radio.checked = radio.value === policyType;

    radio.addEventListener("change", (e) => {
      if (e.target.value === "custom") {
        customPolicyContainer?.classList.remove("hidden");
      } else {
        customPolicyContainer?.classList.add("hidden");
      }
    });
  });

  if (policyType === "custom" && customPolicyContainer) {
    customPolicyContainer.classList.remove("hidden");
  } else if (customPolicyContainer) {
    customPolicyContainer.classList.add("hidden");
  }

  if (window.settingsShippingQuill && business.store_custom_shipping_policy) {
    // Reset contents first
    window.settingsShippingQuill.setContents([]);
    window.settingsShippingQuill.clipboard.dangerouslyPasteHTML(
      0,
      business.store_custom_shipping_policy,
    );
  }

  // Promotions
  const promoToggle = document.getElementById("settings-promo-toggle");
  const promoContainer = document.getElementById("promo-settings-container");
  const promoPercentage = document.getElementById("settings-promo-percentage");
  const promoEndDate = document.getElementById("settings-promo-end-date");

  window.handlePromoToggle = (e) => {
    const btn = e.currentTarget;
    const isChecked = btn.getAttribute("aria-checked") === "true";
    btn.setAttribute("aria-checked", !isChecked);

    if (promoContainer) {
      if (!isChecked) {
        promoContainer.classList.remove("opacity-50", "pointer-events-none");
      } else {
        promoContainer.classList.add("opacity-50", "pointer-events-none");
      }
    }
  };

  if (promoToggle) {
    const isPromoEnabled = !!business.store_promo_enabled;
    promoToggle.setAttribute("aria-checked", isPromoEnabled ? "true" : "false");
    if (promoContainer) {
      if (isPromoEnabled) {
        promoContainer.classList.remove("opacity-50", "pointer-events-none");
      } else {
        promoContainer.classList.add("opacity-50", "pointer-events-none");
      }
    }
  }
  if (promoPercentage) {
    promoPercentage.value = business.store_promo_percentage || "";
  }
  if (promoEndDate && business.store_promo_end_date) {
    // format datetime to YYYY-MM-DDThh:mm
    try {
      const dateObj = new Date(business.store_promo_end_date);
      const isoString = dateObj.toISOString().slice(0, 16);
      promoEndDate.value = isoString;
    } catch (e) {
      console.error("Invalid promo end date:", e);
    }
  }

  // Developer Settings
  const devModeToggle = document.getElementById("developer_mode_enabled");
  if (devModeToggle) {
    const isDevModeEnabled = !!business.developer_mode_enabled;
    devModeToggle.checked = isDevModeEnabled;
    const devScriptsSection = document.getElementById("developer-scripts-section");
    if (devScriptsSection) {
      if (isDevModeEnabled) {
        devScriptsSection.classList.remove("opacity-50", "pointer-events-none");
      } else {
        devScriptsSection.classList.add("opacity-50", "pointer-events-none");
      }
    }
  }
  const devScriptsInput = document.getElementById("store_head_scripts");
  if (devScriptsInput) {
    devScriptsInput.value = business.store_head_scripts || "";
  }

  // Authors & Digital Goods Settings
  const featAuthorInput = document.getElementById("settings-featured-author-name");
  if (featAuthorInput) {
    featAuthorInput.value = business.store_featured_author || "";
  }
  const featAuthorImgInput = document.getElementById("settings-featured-author-image");
  if (featAuthorImgInput) {
    featAuthorImgInput.value = business.store_featured_author_image || "";
  }
  let authorsData = business.store_authors || [];
  if (typeof authorsData === "string" && authorsData.trim()) {
    try {
      authorsData = JSON.parse(authorsData);
    } catch (e) {
      authorsData = [];
    }
  }
  renderStoreAuthorsList(authorsData);

  // 7. Store Layout
  const layoutRadios = document.querySelectorAll('input[name="store_layout"]');
  layoutRadios.forEach((radio) => {
    if (radio.value === (business.store_layout_template || "grid")) {
      radio.checked = true;
    }
  });

  const catLayoutRadios = document.querySelectorAll(
    'input[name="storeCategoryLayout"]',
  );
  catLayoutRadios.forEach((radio) => {
    if (radio.value === (business.store_category_layout || "standard")) {
      radio.checked = true;
    }
  });

  // 8. Accent Color & Theme
  const accentColorInput = document.getElementById(
    "settings-accent-color-input",
  );
  if (accentColorInput) {
    const color = business.store_accent_color || "#cfff45";
    accentColorInput.value = color;

    const colorOpts = document.querySelectorAll(".color-opt");
    const customColorInput = document.getElementById("settings-custom-color");
    const customColorWrapper = document.getElementById("custom-color-wrapper");

    let foundPreset = false;
    colorOpts.forEach((opt) => {
      if (opt.dataset.color === color) {
        opt.classList.add(
          "ring-2",
          "ring-white",
          "ring-offset-2",
          "ring-offset-bg-dark",
        );
        foundPreset = true;
      } else {
        opt.classList.remove(
          "ring-2",
          "ring-white",
          "ring-offset-2",
          "ring-offset-bg-dark",
        );
      }
    });

    if (customColorInput && customColorWrapper) {
      if (!foundPreset) {
        customColorInput.value = color;
        customColorWrapper.classList.add(
          "ring-2",
          "ring-white",
          "ring-offset-2",
          "ring-offset-bg-dark",
        );
      } else {
        customColorWrapper.classList.remove(
          "ring-2",
          "ring-white",
          "ring-offset-2",
          "ring-offset-bg-dark",
        );
      }
    }
  }

  const themeRadios = document.querySelectorAll('input[name="storeTheme"]');
  themeRadios.forEach((radio) => {
    if (radio.value === (business.store_theme || "light")) {
      radio.checked = true;
    }
  });

  // Store logo
  settingsLogoClearPending = false;
  const logoInput = document.getElementById("settings-store-logo-upload");
  if (logoInput) logoInput.value = "";
  if (settingsLogoObjectUrl) {
    URL.revokeObjectURL(settingsLogoObjectUrl);
    settingsLogoObjectUrl = null;
  }
  renderStoreLogoPreview(
    business.business_image || null,
    business.business_image ? "Current store logo" : "No logo uploaded",
  );

  // Store banner
  settingsBannerClearPending = false;
  const bannerInput = document.getElementById("settings-store-banner-upload");
  if (bannerInput) bannerInput.value = "";
  if (settingsBannerObjectUrl) {
    URL.revokeObjectURL(settingsBannerObjectUrl);
    settingsBannerObjectUrl = null;
  }
  renderStoreBannerPreview(business.store_banner || null);

  // 9. Operating Hours
  let hoursData = business?.store_operating_hours;
  if (typeof hoursData === "string" && hoursData.trim()) {
    try {
      hoursData = JSON.parse(hoursData);
    } catch (e) {
      console.error("Hours Parse Error:", e);
      hoursData = {};
    }
  }

  const modeSelect = document.getElementById("settings-operating-mode");
  const hoursContainer = document.getElementById("settings-hours-container");

  if (modeSelect) {
    modeSelect.value =
      hoursData && hoursData.always_open ? "always_open" : "custom";
    modeSelect.onchange = (e) => {
      if (hoursContainer) {
        hoursContainer.style.display =
          e.target.value === "always_open" ? "none" : "block";
      }
    };
    // Initial state
    if (hoursContainer) {
      hoursContainer.style.display =
        modeSelect.value === "always_open" ? "none" : "block";
    }
  }

  if (hoursContainer) {
    const days = [
      "monday",
      "tuesday",
      "wednesday",
      "thursday",
      "friday",
      "saturday",
      "sunday",
    ];
    hoursContainer.innerHTML = "";

    days.forEach((day) => {
      const dayData =
        hoursData && typeof hoursData === "object" ? hoursData[day] : null;
      // A day is enabled if its data exists and it's not explicitly disabled
      const isEnabled = !dayData || dayData.enabled !== false;
      const is24Hours =
        !!dayData &&
        (dayData.is_24_hours === true ||
          dayData.is_24_hours === "true" ||
          (dayData.open === "00:00" &&
            (dayData.close === "23:59" || dayData.close === "00:00")));
      const openTime = dayData?.open || "09:00";
      const closeTime = dayData?.close || "18:00";
      const displayDay = day.charAt(0).toUpperCase() + day.slice(1);

      const row = document.createElement("div");
      row.className = `flex flex-col sm:flex-row sm:items-center justify-between gap-3 py-3.5 border-b border-gray-100 dark:border-gray-700 last:border-b-0 group ${!isEnabled ? "opacity-70" : ""}`;
      row.dataset.day = day;
      row.innerHTML = `
                <div class="flex items-center gap-3 w-36">
                  <button class="switch hours-toggle" role="switch" aria-checked="${isEnabled}">
                    <span class="switch-thumb"></span>
                  </button>
                  <span class="text-sm font-semibold text-gray-900 dark:text-white">${displayDay}</span>
                </div>
                <div class="flex flex-wrap items-center gap-2.5 flex-1 sm:justify-end hours-inputs ${!isEnabled ? "pointer-events-none opacity-50" : ""}">
                  <label class="inline-flex items-center gap-1.5 cursor-pointer text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 transition-colors select-none">
                    <input type="checkbox" name="is_24_hours" class="hours-24-checkbox rounded text-emerald-600 focus:ring-emerald-500 h-3.5 w-3.5 cursor-pointer" ${is24Hours ? "checked" : ""} />
                    <span>24 Hours</span>
                  </label>
                  <div class="flex items-center gap-2 hours-time-inputs ${is24Hours ? "hidden" : ""}">
                    <input type="time" name="open" value="${openTime}" class="flat-input w-auto py-1.5 px-3" />
                    <span class="text-gray-400 text-xs">to</span>
                    <input type="time" name="close" value="${closeTime}" class="flat-input w-auto py-1.5 px-3" />
                  </div>
                  <span class="hours-24-badge text-xs font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/60 px-3 py-1.5 rounded-lg border border-emerald-200 dark:border-emerald-800 ${is24Hours ? "" : "hidden"}">
                    Open 24 Hours
                  </span>
                </div>
            `;
      hoursContainer.appendChild(row);

      // Add toggle event directly to the new button
      const toggle = row.querySelector(".hours-toggle");
      toggle.addEventListener("click", function (e) {
        e.preventDefault();
        const currentlyEnabled = this.getAttribute("aria-checked") === "true";
        const newState = !currentlyEnabled;
        this.setAttribute("aria-checked", newState);

        const inputs = row.querySelector(".hours-inputs");
        if (newState) {
          row.classList.remove("opacity-70");
          if (inputs)
            inputs.classList.remove("pointer-events-none", "opacity-50");
        } else {
          row.classList.add("opacity-70");
          if (inputs) inputs.classList.add("pointer-events-none", "opacity-50");
        }
      });

      // Add 24-hours checkbox toggle event
      const checkbox24 = row.querySelector(".hours-24-checkbox");
      if (checkbox24) {
        checkbox24.addEventListener("change", function () {
          const is24 = this.checked;
          const timeInputs = row.querySelector(".hours-time-inputs");
          const badge24 = row.querySelector(".hours-24-badge");
          if (is24) {
            if (timeInputs) timeInputs.classList.add("hidden");
            if (badge24) badge24.classList.remove("hidden");
          } else {
            if (timeInputs) timeInputs.classList.remove("hidden");
            if (badge24) badge24.classList.add("hidden");
          }
        });
      }
    });
    if (typeof lucide !== "undefined") lucide.createIcons();
  }

  if (typeof lucide !== "undefined") lucide.createIcons();
}

function bindStoreSettingsEvents() {
  // Tab Switching
  const tabs = document.querySelectorAll(".tab-link");
  const contents = document.querySelectorAll(".tab-content");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;

      // Update URL hash without scrolling
      history.replaceState(null, '', `#${target}`);

      tabs.forEach((t) => {
        t.classList.remove("active", "text-primary");
        t.classList.add("text-gray-500");
        const indicator = t.querySelector(".tab-indicator");
        if (indicator) indicator.classList.add("scale-x-0");
      });
      tab.classList.add("active", "text-primary");
      tab.classList.remove("text-gray-500");
      const indicator = tab.querySelector(".tab-indicator");
      if (indicator) indicator.classList.remove("scale-x-0");

      contents.forEach((c) => {
        if (c.id === `tab-${target}`) {
          c.classList.remove("hidden");
        } else {
          c.classList.add("hidden");
        }
      });

      // Generate accordions if clicking delivery tab and system delivery is active
      if (target === "delivery" && window.generateSettingsPickupAccordions) {
        const deliveryType = document.querySelector('input[name="deliveryMode"]:checked')?.value;
        if (deliveryType === "system") {
          window.generateSettingsPickupAccordions();
        }
      }

      // Initialize Store Blog tab when clicked
      if (target === "blog" && window.initStoreBlogTab) {
        window.initStoreBlogTab();
      }

      // Initialize Authors tab when clicked
      if (target === "authors" && window.initStoreAuthorsTab) {
        window.initStoreAuthorsTab();
      }
    });
  });

  // Activate tab from URL hash on load
  const activateTabFromHash = () => {
    const hash = window.location.hash.replace('#', '');
    if (hash) {
      const targetTab = document.querySelector(`.tab-link[data-tab="${hash}"]`);
      if (targetTab) {
        targetTab.click();
        // Scroll the tab into view smoothly
        targetTab.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        return;
      }
    }
  };
  // Run after a short delay to allow renderStoreSettings to complete
  setTimeout(activateTabFromHash, 300);

  // Accent Color Selection
  const colorOpts = document.querySelectorAll(".color-opt");
  const accentInput = document.getElementById("settings-accent-color-input");

  colorOpts.forEach((opt) => {
    opt.addEventListener("click", () => {
      const color = opt.dataset.color;
      accentInput.value = color;

      colorOpts.forEach((o) =>
        o.classList.remove(
          "ring-2",
          "ring-white",
          "ring-offset-2",
          "ring-offset-bg-dark",
        ),
      );
      opt.classList.add(
        "ring-2",
        "ring-white",
        "ring-offset-2",
        "ring-offset-bg-dark",
      );

      const customColorWrapper = document.getElementById(
        "custom-color-wrapper",
      );
      if (customColorWrapper) {
        customColorWrapper.classList.remove(
          "ring-2",
          "ring-white",
          "ring-offset-2",
          "ring-offset-bg-dark",
        );
      }
    });
  });

  const customColorInput = document.getElementById("settings-custom-color");
  const customColorWrapper = document.getElementById("custom-color-wrapper");
  if (customColorInput && customColorWrapper) {
    const handleCustomColor = (e) => {
      const color = e.target.value;
      accentInput.value = color;

      colorOpts.forEach((o) =>
        o.classList.remove(
          "ring-2",
          "ring-white",
          "ring-offset-2",
          "ring-offset-bg-dark",
        ),
      );
      customColorWrapper.classList.add(
        "ring-2",
        "ring-white",
        "ring-offset-2",
        "ring-offset-bg-dark",
      );
    };
    customColorInput.addEventListener("input", handleCustomColor);
    customColorInput.addEventListener("change", handleCustomColor);
    customColorInput.addEventListener("click", handleCustomColor);
  }

  // Instant Settlement Toggle
  const instantSettlementBtn = document.getElementById(
    "settings-instant-settlement",
  );
  if (instantSettlementBtn) {
    instantSettlementBtn.onclick = () => {
      const isChecked =
        instantSettlementBtn.getAttribute("aria-checked") === "true";
      instantSettlementBtn.setAttribute("aria-checked", !isChecked);
    };
  }

  // Chat Toggles
  const livechatBtn = document.getElementById("settings-enable-livechat");
  if (livechatBtn) {
    livechatBtn.onclick = () => {
      const isChecked = livechatBtn.getAttribute("aria-checked") === "true";
      livechatBtn.setAttribute("aria-checked", !isChecked);
    };
  }

  const hideStoreNameToggle = document.getElementById(
    "settings-hide-store-name",
  );
  if (hideStoreNameToggle) {
    hideStoreNameToggle.onclick = () => {
      const isChecked =
        hideStoreNameToggle.getAttribute("aria-checked") === "true";
      hideStoreNameToggle.setAttribute("aria-checked", !isChecked);
    };
  }

  const hideHotProductsToggle = document.getElementById(
    "settings-hide-hot-products",
  );
  if (hideHotProductsToggle) {
    hideHotProductsToggle.onclick = () => {
      const isChecked =
        hideHotProductsToggle.getAttribute("aria-checked") === "true";
      hideHotProductsToggle.setAttribute("aria-checked", !isChecked);
    };
  }

  const whatsappBtn = document.getElementById("settings-enable-whatsapp");
  const waInput = document.getElementById("settings-whatsapp-number");
  if (whatsappBtn) {
    whatsappBtn.onclick = () => {
      const isChecked = whatsappBtn.getAttribute("aria-checked") === "true";

      // Validate number before enabling
      if (!isChecked && waInput) {
        if (!waInput.value.trim()) {
          Swal.fire({
            icon: "error",
            title: "Number Required",
            text: "Please enter a WhatsApp number before enabling.",
            background: "#0f0f0f",
            color: "#ffffff",
            customClass: { popup: "border border-white/10 rounded-2xl" },
          });
          waInput.focus();
          return;
        }
      }

      whatsappBtn.setAttribute("aria-checked", !isChecked);
    };
  }

  // Save Button
  const saveBtn = document.getElementById("save-store-settings-btn");
  if (saveBtn) {
    saveBtn.addEventListener("click", saveStoreSettings);
  }

  // Publish/Unpublish Toggle
  const publishToggle = document.getElementById(
    "settings-store-publish-toggle",
  );
  if (publishToggle) {
    publishToggle.addEventListener("click", toggleStorePublication);
  }

  const logoInput = document.getElementById("settings-store-logo-upload");
  if (logoInput) {
    logoInput.addEventListener("change", (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      if (file.size > 2 * 1024 * 1024) {
        showToast("File too large", "Logo must be 2MB or less", "error");
        logoInput.value = "";
        return;
      }
      settingsLogoClearPending = false;
      if (settingsLogoObjectUrl) URL.revokeObjectURL(settingsLogoObjectUrl);
      settingsLogoObjectUrl = URL.createObjectURL(file);
      renderStoreLogoPreview(settingsLogoObjectUrl, file.name);
    });
  }

  const removeLogoBtn = document.getElementById("settings-remove-logo-btn");
  if (removeLogoBtn) {
    removeLogoBtn.addEventListener("click", () => {
      settingsLogoClearPending = true;
      if (logoInput) logoInput.value = "";
      if (settingsLogoObjectUrl) {
        URL.revokeObjectURL(settingsLogoObjectUrl);
        settingsLogoObjectUrl = null;
      }
      renderStoreLogoPreview(null, "Logo will be removed on save");
    });
  }

  const bannerInput = document.getElementById("settings-store-banner-upload");
  if (bannerInput) {
    bannerInput.addEventListener("change", (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      if (file.size > 2 * 1024 * 1024) {
        showToast("File too large", "Banner must be 2MB or less", "error");
        bannerInput.value = "";
        return;
      }
      settingsBannerClearPending = false;
      if (settingsBannerObjectUrl) URL.revokeObjectURL(settingsBannerObjectUrl);
      settingsBannerObjectUrl = URL.createObjectURL(file);
      renderStoreBannerPreview(settingsBannerObjectUrl);
    });
  }

  const removeBannerBtn = document.getElementById("settings-remove-banner-btn");
  if (removeBannerBtn) {
    removeBannerBtn.addEventListener("click", () => {
      settingsBannerClearPending = true;
      if (bannerInput) bannerInput.value = "";
      if (settingsBannerObjectUrl) {
        URL.revokeObjectURL(settingsBannerObjectUrl);
        settingsBannerObjectUrl = null;
      }
      renderStoreBannerPreview(null);
    });
  }
}

async function saveStoreSettings() {
  const saveBtn = document.getElementById("save-store-settings-btn");
  const originalHTML = saveBtn.innerHTML;
  saveBtn.disabled = true;
  saveBtn.innerText = "Saving...";

  try {
    const formData = new FormData();

    // General Settings
    // For new pill UI, countries are just hidden inputs
    const countryInputs = document.querySelectorAll('input[name="countries"]');
    const selectedCountries = Array.from(countryInputs).map((i) => i.value);
    formData.append("store_countries", JSON.stringify(selectedCountries));

    const storeSlug =
      document.getElementById("settings-store-slug")?.value || "";
    formData.append("store_slug", storeSlug);

    const storeName =
      document.getElementById("settings-store-name")?.value || "";
    formData.append("store_name", storeName);

    const storeDesc =
      document.getElementById("settings-store-description")?.value || "";
    formData.append("store_description", storeDesc);

    const deliveryModeEl = document.querySelector(
      'input[name="deliveryMode"]:checked',
    );
    if (deliveryModeEl) {
      formData.append("store_delivery_type", deliveryModeEl.value);
      if (deliveryModeEl.value === "self") {
        const baseFeeInput = document.getElementById("store-delivery-base-fee");
        const weightFeeInput = document.getElementById(
          "store-delivery-fee-weight",
        );

        if (baseFeeInput)
          formData.append("store_delivery_base_fee", baseFeeInput.value);
        if (weightFeeInput)
          formData.append(
            "store_delivery_fee_per_weight",
            weightFeeInput.value,
          );
      } else if (deliveryModeEl.value === "system") {
        const activeTab = document.querySelector(".tab-link.active")?.dataset.tab;
        
        if (activeTab === "delivery") {
          if (!document.getElementById("settings-pickup-content") && window.generateSettingsPickupAccordions) {
              await window.generateSettingsPickupAccordions();
          }

          const locations = {};
          let missingFields = [];

          if (window.settingsDeliveryIsLoading) {
            throw new Error(
              "Validation Error: Please wait for delivery locations to load before saving.",
            );
          }

          document
            .querySelectorAll(".settings-pickup-accordion-item")
            .forEach((acc) => {
              const countryCode = acc.dataset.country;
              const state = acc.querySelector(".settings-pickup-state").value;
              const lga = acc.querySelector(".settings-pickup-lga").value;
              const address = acc
                .querySelector(".settings-pickup-address")
                .value.trim();
              const phone = acc
                .querySelector(".settings-pickup-phone")
                .value.trim();
              const email = acc
                .querySelector(".settings-pickup-email")
                .value.trim();
              const name = acc
                .querySelector(".settings-pickup-name")
                .value.trim();

              if (!state) missingFields.push(`${countryCode} State`);
              if (!lga) missingFields.push(`${countryCode} LGA`);
              if (!address) missingFields.push(`${countryCode} Address`);
              if (!phone) missingFields.push(`${countryCode} Phone`);
              if (!email) missingFields.push(`${countryCode} Email`);
              if (!name) missingFields.push(`${countryCode} Name`);

              if (state && lga && address && phone && email && name) {
                locations[countryCode] = {
                  state,
                  lga,
                  address,
                  phone,
                  email,
                  name,
                };
              }
            });

          if (Object.keys(locations).length === 0 && missingFields.length === 0) {
              missingFields.push("At least one pickup location is required for system delivery");
          }

          if (missingFields.length > 0) {
            if (window.showToast) {
              window.showToast(
                "Pickup Information Required",
                "Missing fields: " + missingFields.join(", "),
                "error",
              );
            }
            console.error(
              "Validation Error: Missing Pickup Information",
              missingFields,
            );
            saveBtn.disabled = false;
            saveBtn.innerHTML = originalHTML;
            // Automatically switch to Delivery tab if there's an error
            const deliveryTabBtn = document.querySelector(
              '.tab-link[data-tab="delivery"]',
            );
            if (deliveryTabBtn) deliveryTabBtn.click();

            return; // Stop form submission cleanly
          }

          formData.append("store_pickup_locations", JSON.stringify(locations));
        } else {
          // If not on the delivery tab, just pass the existing data to prevent it from being wiped
          formData.append("store_pickup_locations", JSON.stringify(settingsCurrentBusiness.store_pickup_locations || {}));
        }
      }
    }

    // Payment methods should always be saved regardless of delivery mode
    const payInstantlyCheckbox = document.getElementById(
      "store-delivery-pay-instantly",
    );
    const payOnDeliveryCheckbox = document.getElementById(
      "store-delivery-pay-on-delivery",
    );
    if (payInstantlyCheckbox)
      formData.append(
        "store_delivery_pay_instantly",
        payInstantlyCheckbox.checked ? "true" : "false",
      );
    if (payOnDeliveryCheckbox)
      formData.append(
        "store_delivery_pay_on_delivery",
        payOnDeliveryCheckbox.checked ? "true" : "false",
      );

    // Shipping Policy
    const shippingPolicyEl = document.querySelector(
      'input[name="shippingPolicyType"]:checked',
    );
    if (shippingPolicyEl) {
      formData.append("store_shipping_policy_type", shippingPolicyEl.value);
      if (shippingPolicyEl.value === "custom" && window.settingsShippingQuill) {
        const htmlContent = window.settingsShippingQuill.root.innerHTML;
        formData.append("store_custom_shipping_policy", htmlContent);
      }
    }

    // Payment
    const payoutAccountEl = document.getElementById("settings-payout-account");
    if (payoutAccountEl)
      formData.append("store_payment_collection", payoutAccountEl.value);

    const instantSettlementEl = document.getElementById(
      "settings-instant-settlement",
    );
    if (instantSettlementEl)
      formData.append(
        "store_instant_settlement",
        instantSettlementEl.getAttribute("aria-checked") === "true"
          ? "true"
          : "false",
      );

    // Customer Support & Chat
    const enableLivechatEl = document.getElementById(
      "settings-enable-livechat",
    );
    if (enableLivechatEl)
      formData.append(
        "enable_livechat",
        enableLivechatEl.getAttribute("aria-checked") === "true"
          ? "true"
          : "false",
      );

    const enableWhatsappEl = document.getElementById(
      "settings-enable-whatsapp",
    );
    if (enableWhatsappEl)
      formData.append(
        "enable_whatsapp",
        enableWhatsappEl.getAttribute("aria-checked") === "true"
          ? "true"
          : "false",
      );

    const hideStoreNameEl = document.getElementById("settings-hide-store-name");
    if (hideStoreNameEl)
      formData.append(
        "hide_store_name",
        hideStoreNameEl.getAttribute("aria-checked") === "true"
          ? "true"
          : "false",
      );

    const hideHotProductsEl = document.getElementById(
      "settings-hide-hot-products",
    );
    if (hideHotProductsEl)
      formData.append(
        "hide_hot_products",
        hideHotProductsEl.getAttribute("aria-checked") === "true"
          ? "true"
          : "false",
      );

    const whatsappNumberEl = document.getElementById(
      "settings-whatsapp-number",
    );
    if (whatsappNumberEl)
      formData.append("store_whatsapp_number", whatsappNumberEl.value);

    // Social Links
    const igUrl =
      document.getElementById("settings-social-instagram")?.value || "";
    const twUrl =
      document.getElementById("settings-social-twitter")?.value || "";
    const fbUrl =
      document.getElementById("settings-social-facebook")?.value || "";
    formData.append("store_social_instagram", igUrl);
    formData.append("store_social_twitter", twUrl);
    formData.append("store_social_facebook", fbUrl);

    const logoInput = document.getElementById("settings-store-logo-upload");
    if (logoInput?.files?.[0]) {
      formData.append("business_image", logoInput.files[0]);
    }
    if (settingsLogoClearPending) {
      formData.append("clear_business_image", "true");
    }

    const bannerInput = document.getElementById("settings-store-banner-upload");
    if (bannerInput?.files?.[0]) {
      formData.append("store_banner", bannerInput.files[0]);
    }
    if (settingsBannerClearPending) {
      formData.append("clear_store_banner", "true");
    }

    // Developer Settings
    const devModeToggle = document.getElementById("developer_mode_enabled");
    if (devModeToggle) {
      formData.append("developer_mode_enabled", devModeToggle.checked ? "true" : "false");
    }
    const devScriptsInput = document.getElementById("store_head_scripts");
    if (devScriptsInput) {
      formData.append("store_head_scripts", devScriptsInput.value);
    }

    // Promotions
    const promoToggle = document.getElementById("settings-promo-toggle");
    if (promoToggle) {
      formData.append(
        "store_promo_enabled",
        promoToggle.getAttribute("aria-checked") === "true" ? "true" : "false",
      );
    }
    const promoPercentage = document.getElementById(
      "settings-promo-percentage",
    );
    if (promoPercentage) {
      formData.append("store_promo_percentage", promoPercentage.value || "0");
    }
    const promoEndDate = document.getElementById("settings-promo-end-date");
    if (promoEndDate && promoEndDate.value) {
      try {
        // Convert to UTC ISO string before saving if possible, or just send the local datetime string
        const d = new Date(promoEndDate.value);
        formData.append("store_promo_end_date", d.toISOString());
      } catch (e) {
        formData.append("store_promo_end_date", promoEndDate.value);
      }
    }

    // Theme
    const layoutEl = document.querySelector(
      'input[name="store_layout"]:checked',
    );
    if (layoutEl) formData.append("store_layout_template", layoutEl.value);

    const catLayoutEl = document.querySelector(
      'input[name="storeCategoryLayout"]:checked',
    );
    if (catLayoutEl)
      formData.append("store_category_layout", catLayoutEl.value);

    const accentColorEl = document.getElementById(
      "settings-accent-color-input",
    );
    if (accentColorEl)
      formData.append("store_accent_color", accentColorEl.value);

    const themeEl = document.querySelector('input[name="storeTheme"]:checked');
    if (themeEl) formData.append("store_theme", themeEl.value);

    // Featured Author (Best Seller Books Spotlight)
    const featuredAuthorSelect = document.getElementById("settings-featured-author-select");
    if (featuredAuthorSelect) {
      const selectedAuthorName = featuredAuthorSelect.value.trim();
      formData.append("store_featured_author", selectedAuthorName);
      const matchingAuthor = (storeAuthorsCache || []).find((a) => {
        const aName = typeof a === "string" ? a : (a.name || "");
        return aName.toLowerCase() === selectedAuthorName.toLowerCase();
      });
      formData.append("store_featured_author_image", (matchingAuthor && matchingAuthor.image) ? matchingAuthor.image : "");
    }

    // Operating Hours
    const hours = {};
    const modeSelect = document.getElementById("settings-operating-mode");
    if (modeSelect && modeSelect.value === "always_open") {
      hours.always_open = true;
    } else {
      hours.always_open = false;
    }

    document
      .querySelectorAll("#settings-hours-container > div")
      .forEach((row) => {
        const day = row.dataset.day;
        const enabled =
          row.querySelector(".hours-toggle")?.getAttribute("aria-checked") ===
          "true";
        const is24Checkbox = row.querySelector(".hours-24-checkbox");
        const is24Hours = is24Checkbox ? is24Checkbox.checked : false;
        let open = row.querySelector('input[name="open"]')?.value || "09:00";
        let close = row.querySelector('input[name="close"]')?.value || "18:00";
        if (is24Hours) {
          open = "00:00";
          close = "23:59";
        }
        hours[day] = {
          enabled: enabled,
          is_24_hours: is24Hours,
          open: open,
          close: close,
        };
      });
    formData.append("store_operating_hours", JSON.stringify(hours));

    const response = await apiFetch(
      `${window.CONFIG.API_BASE}/api/user/store/setup`,
      {
        method: "POST",
        body: formData,
      },
    );

    const result = await response.json();
    if (result.status) {
      showToast("Store settings updated successfully!", "success");
      // Refresh local data without showing skeleton
      await loadStoreSettings(false);
    } else {
      let errorMsg = "Failed to update settings";
      if (typeof result.message === 'string') {
        errorMsg = result.message;
      } else if (typeof result.message === 'object' && result.message !== null) {
        const firstKey = Object.keys(result.message)[0];
        if (firstKey && Array.isArray(result.message[firstKey])) {
            errorMsg = result.message[firstKey][0];
        } else if (firstKey) {
            errorMsg = result.message[firstKey];
        }
      }
      showToast(errorMsg, "error");
    }
  } catch (error) {
    // console.error("Error saving settings:", error);
    if (error.message && error.message.includes("Validation Error:")) {
      // The validation block already shows a detailed toast, but to satisfy the user request:
      showToast(error.message, "error");
    } else {
      showToast(error.message || "An error occurred while saving", "error");
    }
  } finally {
    saveBtn.disabled = false;
    saveBtn.innerHTML = originalHTML;
    if (window.lucide) window.lucide.createIcons({ root: saveBtn });
  }
}

async function toggleStorePublication() {
  const publishToggle = document.getElementById(
    "settings-store-publish-toggle",
  );
  const isCurrentlyPublished =
    publishToggle.getAttribute("aria-checked") === "true";
  const newState = !isCurrentlyPublished;

  try {
    const formData = new FormData();
    formData.append("is_published", newState);

    const response = await apiFetch(
      `${window.CONFIG.API_BASE}/api/user/store/setup`,
      {
        method: "POST",
        body: formData,
      },
    );

    const result = await response.json();
    if (result.status) {
      showToast(
        `Store ${newState ? "published" : "unpublished"} successfully!`,
        "success",
      );
      publishToggle.setAttribute("aria-checked", newState);
      const statusText = document.getElementById("settings-store-status-text");
      if (statusText) {
        statusText.innerText = newState ? "Online" : "Offline";
        statusText.className = newState
          ? "text-xs font-bold text-emerald-500 uppercase tracking-widest transition-colors"
          : "text-xs font-bold text-slate-500 uppercase tracking-widest transition-colors";
      }
      // Refresh local data to sync other components without skeleton
      loadStoreSettings(false);
    }
  } catch (error) {
    showToast("Failed to update store status", "error");
  }
}

function copyStoreLink() {
  const slug = document.getElementById("settings-default-link").innerText;
  const baseDomain = window.CONFIG?.STORE_BASE_DOMAIN || window.location.host;
  const protocol = window.location.protocol;
  navigator.clipboard
    .writeText(`${protocol}//${slug}.${baseDomain}/`)
    .then(() => {
      showToast("Store link copied to clipboard!", "success");
    });
}

// ═════════════════════════════════════════════════════════════════
// STORE BLOG MANAGEMENT CONTROLLER
// ═════════════════════════════════════════════════════════════════

var isStoreBlogInitialized = false;
var storeBlogCurrentPage = 1;
var storeBlogTotalPages = 1;
var storeBlogSearchTimeout = null;

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.innerText = text;
  return div.innerHTML;
}

function getStoreBlogBaseUrl(storeSlug) {
  const customDomain = settingsCurrentBusiness?.store_custom_domain || window.currentBusinessData?.store_custom_domain;
  if (customDomain) {
    return `${window.location.protocol}//${customDomain}`;
  }
  const baseDomain = window.CONFIG?.STORE_BASE_DOMAIN || window.location.host;
  const protocol = window.location.protocol;
  return storeSlug ? `${protocol}//${storeSlug}.${baseDomain}` : '';
}

function getStoreBlogHostDisplay(storeSlug) {
  const customDomain = settingsCurrentBusiness?.store_custom_domain || window.currentBusinessData?.store_custom_domain;
  if (customDomain) {
    return customDomain;
  }
  const baseDomain = window.CONFIG?.STORE_BASE_DOMAIN || window.location.host;
  return storeSlug ? `${storeSlug}.${baseDomain}` : '';
}

window.initStoreBlogTab = function() {
  if (document.getElementById('tab-blog-locked')) {
    if (window.lucide) lucide.createIcons();
    return;
  }

  // Update public blog link
  const storeSlug = settingsCurrentBusiness?.store_slug ||
    window.currentBusinessData?.store_slug ||
    document.getElementById('settings-default-link')?.dataset?.slug ||
    document.getElementById('settings-default-link')?.innerText?.trim() || '';
  
  const publicBlogBtn = document.getElementById('btn-view-public-blog');
  if (publicBlogBtn && storeSlug) {
    publicBlogBtn.href = `${getStoreBlogBaseUrl(storeSlug)}/blog`;
  }

  setupStoreBlogCategoryModalListeners();

  if (isStoreBlogInitialized) {
    loadStoreBlogArticles(storeBlogCurrentPage);
    return;
  }
  isStoreBlogInitialized = true;

  // Search input with debounce
  const searchInput = document.getElementById('store-blog-search');
  const searchClear = document.getElementById('store-blog-search-clear');
  searchInput?.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    if (searchClear) searchClear.classList.toggle('hidden', !val);
    clearTimeout(storeBlogSearchTimeout);
    storeBlogSearchTimeout = setTimeout(() => {
      loadStoreBlogArticles(1);
    }, 350);
  });

  searchClear?.addEventListener('click', () => {
    if (searchInput) {
      searchInput.value = '';
      searchClear.classList.add('hidden');
      loadStoreBlogArticles(1);
    }
  });

  // Category & Status filters
  document.getElementById('store-blog-category-filter')?.addEventListener('change', () => {
    loadStoreBlogArticles(1);
  });
  document.getElementById('store-blog-status-filter')?.addEventListener('change', () => {
    loadStoreBlogArticles(1);
  });

  // Refresh button
  document.getElementById('store-blog-refresh-btn')?.addEventListener('click', () => {
    loadStoreBlogCategories();
    loadStoreBlogArticles(storeBlogCurrentPage);
  });

  // Pagination buttons
  document.getElementById('store-blog-prev-btn')?.addEventListener('click', () => {
    if (storeBlogCurrentPage > 1) {
      loadStoreBlogArticles(storeBlogCurrentPage - 1);
    }
  });
  document.getElementById('store-blog-next-btn')?.addEventListener('click', () => {
    if (storeBlogCurrentPage < storeBlogTotalPages) {
      loadStoreBlogArticles(storeBlogCurrentPage + 1);
    }
  });

  // Initial loads
  loadStoreBlogCategories();
  loadStoreBlogArticles(1);
};

// Load categories list for filter dropdown
async function loadStoreBlogCategories() {
  try {
    const res = await apiFetch('/api/store-blog/categories/');
    const data = await res.json();
    if (data.status && Array.isArray(data.categories)) {
      const filterSelect = document.getElementById('store-blog-category-filter');
      if (filterSelect) {
        const currentVal = filterSelect.value;
        filterSelect.innerHTML = '<option value="all">All Categories</option>';
        data.categories.forEach((cat) => {
          const opt = document.createElement('option');
          opt.value = cat;
          opt.text = cat;
          filterSelect.appendChild(opt);
        });
        filterSelect.value = currentVal || 'all';
      }
    }
  } catch (err) {
    console.error('Error fetching blog categories:', err);
  }
}

// Load preview articles (max 5 articles, minimal columns)
async function loadStoreBlogArticles(page = 1) {
  const tbody = document.getElementById('store-blog-table-body');
  if (!tbody) return;

  tbody.innerHTML = `
    <tr>
      <td colspan="3" class="py-10 text-center text-gray-400">
        <div class="inline-block animate-spin rounded-full h-5 w-5 border-2 border-primary border-t-transparent mb-2"></div>
        <p class="text-xs">Loading latest articles...</p>
      </td>
    </tr>
  `;

  const params = new URLSearchParams({
    page: 1,
    page_size: 5,
  });

  try {
    const res = await apiFetch(`/api/store-blog/articles/?${params.toString()}`);
    const data = await res.json();

    if (!data.status) {
      tbody.innerHTML = `
        <tr>
          <td colspan="3" class="py-8 text-center text-rose-500 text-xs">
            Failed to load articles. Please try again.
          </td>
        </tr>
      `;
      return;
    }

    // Update count info
    const rangeEnd = document.getElementById('store-blog-range-end');
    const totalCount = document.getElementById('store-blog-total-count');
    if (rangeEnd) rangeEnd.innerText = (data.articles || []).length;
    if (totalCount) totalCount.innerText = data.total_count || 0;

    // Render table rows
    if (!data.articles || data.articles.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="3" class="py-12 text-center">
            <div class="max-w-xs mx-auto space-y-2.5">
              <div class="w-10 h-10 mx-auto rounded-full bg-primary/10 text-primary flex items-center justify-center">
                <i data-lucide="book-open" class="w-5 h-5"></i>
              </div>
              <h4 class="text-xs font-bold text-gray-900 dark:text-white">No articles published yet</h4>
              <p class="text-[11px] text-gray-500">
                Start engaging customers with brand stories, origin craft, and announcements.
              </p>
              <a
                href="/store-blog/create"
                class="bg-primary hover:bg-primary-dark text-black font-semibold text-xs py-1.5 px-3.5 inline-flex items-center gap-1.5 rounded-lg mt-1 transition-colors shadow-sm"
              >
                <i data-lucide="plus" class="w-3.5 h-3.5"></i>
                <span>Write First Article</span>
              </a>
            </div>
          </td>
        </tr>
      `;
      if (window.lucide) window.lucide.createIcons({ root: tbody });
      return;
    }

    const storeSlug = settingsCurrentBusiness?.store_slug ||
      window.currentBusinessData?.store_slug ||
      document.getElementById('settings-default-link')?.dataset?.slug ||
      document.getElementById('settings-default-link')?.innerText?.trim() || '';
    const blogBaseUrl = getStoreBlogBaseUrl(storeSlug);

    let html = '';
    data.articles.slice(0, 5).forEach((art) => {
      const publicUrl = blogBaseUrl ? `${blogBaseUrl}/blog/${art.slug}` : `/blog/${art.slug}`;
      const statusBadge = art.is_published
        ? '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200/60 dark:border-emerald-800/40">Published</span>'
        : '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400 border border-amber-200/60 dark:border-amber-800/40">Draft</span>';

      const thumb = art.image_url
        ? `<img src="${escapeHtml(art.image_url)}" alt="${escapeHtml(art.title)}" class="w-10 h-10 rounded-lg object-cover border border-gray-200 dark:border-gray-700 flex-shrink-0 shadow-xs" onerror="this.onerror=null; this.src='/static/assets/image/blog/hero_desert_dunes.jpg';" />`
        : `<div class="w-10 h-10 rounded-lg bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 flex items-center justify-center text-gray-400 flex-shrink-0"><i data-lucide="file-text" class="w-4 h-4"></i></div>`;

      html += `
        <tr class="hover:bg-gray-50/60 dark:hover:bg-gray-800/40 transition-colors">
          <td class="py-3 px-4">
            <div class="flex items-center gap-3 min-w-0">
              ${thumb}
              <div class="min-w-0 flex-1">
                <a href="/store-blog/edit/${art.id}" class="font-bold text-gray-900 dark:text-white hover:text-primary transition-colors truncate block text-xs" title="${escapeHtml(art.title)}">
                  ${escapeHtml(art.title)}
                </a>
                <div class="flex items-center gap-2 mt-0.5 flex-wrap">
                  <span class="inline-block px-1.5 py-0.2 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 text-[10px] font-medium">
                    ${escapeHtml(art.category)}
                  </span>
                  <span class="text-[10px] text-gray-400">${escapeHtml(art.updated_at || art.created_at)}</span>
                </div>
              </div>
            </div>
          </td>
          <td class="py-3 px-4 whitespace-nowrap">
            ${statusBadge}
          </td>
          <td class="py-3 px-4 text-right whitespace-nowrap">
            <div class="relative inline-block text-right dropdown-container">
              <button
                type="button"
                class="p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-all dropdown-toggle cursor-pointer"
                title="Article Options"
              >
                <i data-lucide="more-vertical" class="w-4 h-4 pointer-events-none"></i>
              </button>
              <div
                class="dropdown-menu hidden absolute right-0 top-full mt-1.5 w-40 bg-white dark:bg-[#151922] border border-gray-200 dark:border-gray-700/80 rounded-xl shadow-xl py-1.5 z-50 text-left"
              >
                <a
                  href="/store-blog/edit/${art.id}"
                  class="w-full text-left px-3.5 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-white/5 flex items-center gap-2 transition-colors"
                >
                  <i data-lucide="edit-3" class="w-3.5 h-3.5 text-primary"></i>
                  <span>Edit Article</span>
                </a>
                <a
                  href="${publicUrl}"
                  target="_blank"
                  class="w-full text-left px-3.5 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-white/5 flex items-center gap-2 transition-colors border-t border-gray-100 dark:border-white/5"
                >
                  <i data-lucide="external-link" class="w-3.5 h-3.5 text-sky-500"></i>
                  <span>View on Store</span>
                </a>
                <button
                  type="button"
                  onclick="deleteStoreBlogArticle(${art.id}, '${escapeHtml(art.title).replace(/'/g, "\\'")}')"
                  class="w-full text-left px-3.5 py-2 text-xs font-semibold text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/30 flex items-center gap-2 transition-colors border-t border-gray-100 dark:border-white/5 cursor-pointer"
                >
                  <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                  <span>Delete Article</span>
                </button>
              </div>
            </div>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
    if (window.lucide) window.lucide.createIcons({ root: tbody });
    initStoreBlogDropdowns();
  } catch (err) {
    console.error('Error fetching articles:', err);
    tbody.innerHTML = `
      <tr>
        <td colspan="3" class="py-8 text-center text-rose-500 text-xs">
          An error occurred while loading articles.
        </td>
      </tr>
    `;
  }
}

// Three-dot dropdown listeners for articles table
function initStoreBlogDropdowns() {
  document.querySelectorAll('#store-blog-table-body .dropdown-toggle').forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const menu = btn.nextElementSibling;
      if (!menu) return;
      const isShowing = !menu.classList.contains('hidden') && menu.classList.contains('show');
      
      // Close all other dropdown menus
      document.querySelectorAll('#store-blog-table-body .dropdown-menu').forEach(m => {
        m.classList.remove('show');
        m.classList.add('hidden');
      });
      document.querySelectorAll('#store-blog-table-body tr').forEach(r => r.classList.remove('relative', 'z-40'));

      if (!isShowing) {
        menu.classList.remove('hidden');
        menu.classList.add('show');
        const tr = btn.closest('tr');
        if (tr) tr.classList.add('relative', 'z-40');
      }
    };
  });
}

// Close open dropdowns when clicking outside
document.addEventListener('click', (e) => {
  if (!e.target.closest('.dropdown-container')) {
    document.querySelectorAll('#store-blog-table-body .dropdown-menu').forEach(m => {
      m.classList.remove('show');
      m.classList.add('hidden');
    });
    document.querySelectorAll('#store-blog-table-body tr').forEach(r => r.classList.remove('relative', 'z-40'));
  }
});

// Delete article with SweetAlert confirm
window.deleteStoreBlogArticle = async function(articleId, title) {
  // Close any open dropdowns
  document.querySelectorAll('#store-blog-table-body .dropdown-menu').forEach(m => {
    m.classList.remove('show');
    m.classList.add('hidden');
  });

  const isDark = document.documentElement.classList.contains('dark');
  const result = await Swal.fire({
    title: 'Delete Article?',
    html: `Are you sure you want to permanently delete <strong>"${escapeHtml(title)}"</strong>?<br><span class="text-xs text-gray-400">This action cannot be undone.</span>`,
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: 'Yes, Delete Article',
    cancelButtonText: 'Cancel',
    confirmButtonColor: '#e11d48',
    cancelButtonColor: '#64748b',
    background: isDark ? '#0f172a' : '#ffffff',
    color: isDark ? '#ffffff' : '#0f172a',
    customClass: {
      popup: 'rounded-2xl border border-gray-200 dark:border-white/10 shadow-2xl',
      confirmButton: 'rounded-xl font-bold px-4 py-2.5 cursor-pointer',
      cancelButton: 'rounded-xl font-semibold px-4 py-2.5 cursor-pointer'
    }
  });

  if (!result.isConfirmed) {
    return;
  }

  try {
    const res = await apiFetch(`/api/store-blog/articles/${articleId}/`, {
      method: 'DELETE',
    });
    const data = await res.json();
    if (data.status) {
      Swal.fire({
        toast: true,
        position: 'top-end',
        icon: 'success',
        title: data.message || 'Article deleted successfully.',
        showConfirmButton: false,
        timer: 3000,
        background: isDark ? '#1e293b' : '#ffffff',
        color: isDark ? '#ffffff' : '#0f172a'
      });
      loadStoreBlogCategories();
      loadStoreBlogArticles(storeBlogCurrentPage);
    } else {
      Swal.fire({
        icon: 'error',
        title: 'Delete Failed',
        text: data.message || 'Failed to delete article.',
        background: isDark ? '#0f172a' : '#ffffff',
        color: isDark ? '#ffffff' : '#0f172a'
      });
    }
  } catch (err) {
    console.error('Error deleting article:', err);
    Swal.fire({
      icon: 'error',
      title: 'Error',
      text: 'An error occurred while deleting the article.',
      background: isDark ? '#0f172a' : '#ffffff',
      color: isDark ? '#ffffff' : '#0f172a'
    });
  }
};

// ═════════════════════════════════════════════════════════════════
// Store Blog Categories Management Modal
// ═════════════════════════════════════════════════════════════════
window.renderStoreBlogCategoriesModalList = async function() {
  const modalList = document.getElementById('settings-modal-cat-list');
  const modalCount = document.getElementById('settings-modal-cat-count');
  if (!modalList) return;

  try {
    const res = await apiFetch('/api/store-blog/categories/');
    const data = await res.json();
    if (!data.status) return;

    const catDataList = data.categories_data || [];
    if (modalCount) modalCount.innerText = `${catDataList.length} categories`;

    if (catDataList.length === 0) {
      modalList.innerHTML = '<p class="text-xs text-gray-400 py-3 text-center">No categories yet.</p>';
      return;
    }

    modalList.innerHTML = catDataList.map(cat => {
      const isGeneral = cat.name.toLowerCase() === 'general';
      const deleteBtn = isGeneral
        ? '<span class="text-[10px] text-gray-400 italic px-2">Default</span>'
        : `<button type="button" onclick="deleteCategoryFromSettings(${cat.id}, '${escapeHtml(cat.name).replace(/'/g, "\\'")}')" class="p-1.5 text-gray-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg transition-colors cursor-pointer" title="Delete Category">
            <i data-lucide="trash-2" class="w-3.5 h-3.5 pointer-events-none"></i>
           </button>`;

      return `
        <div class="flex items-center justify-between py-2 px-1">
          <div class="flex items-center gap-2 min-w-0">
            <span class="w-1.5 h-1.5 rounded-full bg-primary shrink-0"></span>
            <span class="text-xs font-semibold text-gray-800 dark:text-slate-200 truncate">${escapeHtml(cat.name)}</span>
            <span class="text-[10px] text-gray-400 font-normal">(${cat.count} ${cat.count === 1 ? 'article' : 'articles'})</span>
          </div>
          <div class="shrink-0 flex items-center">
            ${deleteBtn}
          </div>
        </div>
      `;
    }).join('');

    if (window.lucide) window.lucide.createIcons({ root: modalList });
  } catch (err) {
    console.error('Error rendering category modal list:', err);
  }
};

window.deleteCategoryFromSettings = async function(catId, catName) {
  const isDark = document.documentElement.classList.contains('dark');
  const result = await Swal.fire({
    title: 'Delete Category?',
    html: `Are you sure you want to delete category <strong>"${escapeHtml(catName)}"</strong>?<br><span class="text-xs text-gray-400">Articles in this category will be reassigned to General.</span>`,
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: 'Yes, Delete',
    cancelButtonText: 'Cancel',
    confirmButtonColor: '#e11d48',
    cancelButtonColor: '#64748b',
    background: isDark ? '#0f172a' : '#ffffff',
    color: isDark ? '#ffffff' : '#0f172a',
    customClass: {
      popup: 'rounded-2xl border border-gray-200 dark:border-white/10 shadow-2xl',
      confirmButton: 'rounded-xl font-bold px-4 py-2.5 cursor-pointer',
      cancelButton: 'rounded-xl font-semibold px-4 py-2.5 cursor-pointer'
    }
  });

  if (!result.isConfirmed) return;

  try {
    const res = await apiFetch(`/api/store-blog/categories/${catId}/delete/`, {
      method: 'POST'
    });
    const data = await res.json();
    if (data.status) {
      await renderStoreBlogCategoriesModalList();
      await loadStoreBlogCategories();
      await loadStoreBlogArticles(storeBlogCurrentPage);
      Swal.fire({
        toast: true,
        position: 'top-end',
        icon: 'success',
        title: data.message || `Deleted category "${catName}"`,
        showConfirmButton: false,
        timer: 2500,
        background: isDark ? '#1e293b' : '#ffffff',
        color: isDark ? '#ffffff' : '#0f172a'
      });
    } else {
      Swal.fire({
        icon: 'error',
        title: 'Delete Failed',
        text: data.message || 'Could not delete category.',
        background: isDark ? '#0f172a' : '#ffffff',
        color: isDark ? '#ffffff' : '#0f172a'
      });
    }
  } catch (err) {
    console.error('Error deleting category:', err);
  }
};

window.openStoreBlogCategoryModal = function() {
  const modal = document.getElementById('store-blog-categories-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
  setTimeout(() => modal.classList.remove('opacity-0'), 10);
  renderStoreBlogCategoriesModalList();
  setTimeout(() => {
    document.getElementById('settings-modal-cat-input')?.focus();
  }, 100);
};

window.closeStoreBlogCategoryModal = function() {
  const modal = document.getElementById('store-blog-categories-modal');
  if (!modal) return;
  modal.classList.add('opacity-0');
  setTimeout(() => modal.classList.add('hidden'), 200);
};

window.addStoreBlogCategoryFromModal = async function() {
  const input = document.getElementById('settings-modal-cat-input');
  const val = input?.value?.trim();
  if (!val) return;

  const formData = new FormData();
  formData.append('name', val);

  try {
    const res = await apiFetch('/api/store-blog/categories/', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (data.status) {
      if (input) input.value = '';
      await renderStoreBlogCategoriesModalList();
      await loadStoreBlogCategories();
      const isDark = document.documentElement.classList.contains('dark');
      Swal.fire({
        toast: true,
        position: 'top-end',
        icon: 'success',
        title: data.message || `Added category "${val}"`,
        showConfirmButton: false,
        timer: 2500,
        background: isDark ? '#1e293b' : '#ffffff',
        color: isDark ? '#ffffff' : '#0f172a'
      });
    } else {
      const isDark = document.documentElement.classList.contains('dark');
      Swal.fire({
        icon: 'error',
        title: 'Category Error',
        text: data.message || 'Could not add category.',
        background: isDark ? '#0f172a' : '#ffffff',
        color: isDark ? '#ffffff' : '#0f172a'
      });
    }
  } catch (err) {
    console.error('Error adding category:', err);
  }
};

function setupStoreBlogCategoryModalListeners() {
  const modal = document.getElementById('store-blog-categories-modal');
  const openBtn = document.getElementById('btn-manage-blog-categories');
  const closeBtn = document.getElementById('btn-close-store-blog-categories-modal');
  const doneBtn = document.getElementById('btn-done-store-blog-categories-modal');
  const addBtn = document.getElementById('settings-modal-btn-add-cat');
  const input = document.getElementById('settings-modal-cat-input');

  if (openBtn && !openBtn._categoryListenerBound) {
    openBtn._categoryListenerBound = true;
    openBtn.addEventListener('click', (e) => {
      e.preventDefault();
      window.openStoreBlogCategoryModal();
    });
  }

  if (closeBtn && !closeBtn._categoryListenerBound) {
    closeBtn._categoryListenerBound = true;
    closeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      window.closeStoreBlogCategoryModal();
    });
  }

  if (doneBtn && !doneBtn._categoryListenerBound) {
    doneBtn._categoryListenerBound = true;
    doneBtn.addEventListener('click', (e) => {
      e.preventDefault();
      window.closeStoreBlogCategoryModal();
    });
  }

  if (addBtn && !addBtn._categoryListenerBound) {
    addBtn._categoryListenerBound = true;
    addBtn.addEventListener('click', (e) => {
      e.preventDefault();
      window.addStoreBlogCategoryFromModal();
    });
  }

  if (input && !input._categoryListenerBound) {
    input._categoryListenerBound = true;
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        window.addStoreBlogCategoryFromModal();
      }
    });
  }
}

// Global delegated listeners (works across Swup page transitions and dynamic DOM swaps)
if (!window._storeBlogCategoryDelegationAttached) {
  window._storeBlogCategoryDelegationAttached = true;

  document.addEventListener('click', (e) => {
    const openBtn = e.target.closest('#btn-manage-blog-categories');
    if (openBtn) {
      e.preventDefault();
      window.openStoreBlogCategoryModal();
      return;
    }

    const closeBtn = e.target.closest('#btn-close-store-blog-categories-modal, #btn-done-store-blog-categories-modal');
    if (closeBtn) {
      e.preventDefault();
      window.closeStoreBlogCategoryModal();
      return;
    }

    const modal = document.getElementById('store-blog-categories-modal');
    if (modal && e.target === modal) {
      window.closeStoreBlogCategoryModal();
      return;
    }

    const addBtn = e.target.closest('#settings-modal-btn-add-cat');
    if (addBtn) {
      e.preventDefault();
      window.addStoreBlogCategoryFromModal();
      return;
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target && e.target.id === 'settings-modal-cat-input') {
      e.preventDefault();
      window.addStoreBlogCategoryFromModal();
    } else if (e.key === 'Escape') {
      const modal = document.getElementById('store-blog-categories-modal');
      if (modal && !modal.classList.contains('hidden')) {
        window.closeStoreBlogCategoryModal();
      }
    }
  });
}

// Attach category modal listener when page loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', setupStoreBlogCategoryModalListeners);
} else {
  setupStoreBlogCategoryModalListeners();
}

// ==========================================
// Authors Tab Management (Digital Goods & Featured Author)
// ==========================================

var storeAuthorsCache = window.storeAuthorsCache || [];
var currentFeaturedAuthor = window.currentFeaturedAuthor || "";
var newAuthorSelectedFile = null;

function renderStoreAuthorsList(authors, featuredAuthorName) {
  const container = document.getElementById("settings-authors-list");
  if (!container) return;

  storeAuthorsCache = Array.isArray(authors) ? authors : [];
  const featName = (featuredAuthorName !== undefined ? featuredAuthorName : currentFeaturedAuthor) || "";

  if (storeAuthorsCache.length === 0) {
    container.innerHTML = `
      <div class="py-8 px-4 text-center">
        <div class="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center mx-auto mb-2.5">
          <i data-lucide="user-plus" class="w-5 h-5"></i>
        </div>
        <p class="text-xs font-semibold text-gray-700 dark:text-gray-300">No authors in your directory yet</p>
        <p class="text-[11px] text-gray-500 mt-0.5 mb-3">Add authors for your digital goods, ebooks, and storefront showcases.</p>
        <button type="button" onclick="window.openAddAuthorModal?.()" class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary text-xs font-semibold rounded-lg transition-colors cursor-pointer">
          <i data-lucide="plus" class="w-3.5 h-3.5"></i>
          <span>Add First Author</span>
        </button>
      </div>
    `;
    if (typeof lucide !== "undefined") lucide.createIcons();
    return;
  }

  container.innerHTML = storeAuthorsCache.map((author) => {
    const name = typeof author === "string" ? author : (author.name || "");
    const imgUrl = typeof author === "object" ? (author.image || "") : "";
    const safeName = name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const isSpotlight = featName && name.toLowerCase() === featName.toLowerCase();
    const avatarPlaceholder = `https://ui-avatars.com/api/?name=${encodeURIComponent(name || 'Author')}&background=1e293b&color=fff`;
    const imgSrc = imgUrl || avatarPlaceholder;

    return `
      <div class="grid grid-cols-12 items-center py-3 px-4 hover:bg-gray-50/70 dark:hover:bg-gray-800/40 transition-colors">
        <!-- Author Info -->
        <div class="col-span-6 sm:col-span-5 flex items-center gap-3 min-w-0">
          <div class="w-9 h-10 rounded-lg bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 overflow-hidden shrink-0 flex items-center justify-center shadow-xs">
            <img src="${imgSrc}" onerror="this.onerror=null; this.src='${avatarPlaceholder}';" alt="${safeName}" class="w-full h-full object-cover">
          </div>
          <div class="min-w-0">
            <span class="text-xs font-semibold text-gray-900 dark:text-gray-100 truncate block" title="${safeName}">${name}</span>
          </div>
        </div>

        <!-- Featured Status & Action -->
        <div class="col-span-4 sm:col-span-5 flex items-center">
          ${isSpotlight ? `
            <span class="text-xs font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
              <i data-lucide="check" class="w-3.5 h-3.5"></i>
              <span>Featured</span>
            </span>
          ` : `
            <button
              type="button"
              onclick="window.quickSetSpotlightAuthor?.('${safeName}')"
              class="text-xs text-gray-500 hover:text-primary dark:text-gray-400 dark:hover:text-primary transition-colors cursor-pointer"
            >
              Set as featured
            </button>
          `}
        </div>

        <!-- Actions -->
        <div class="col-span-2 flex items-center justify-end">
          <button
            type="button"
            onclick="window.deleteStoreAuthor('${safeName}')"
            class="text-gray-400 hover:text-red-500 p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors cursor-pointer"
            title="Delete Author"
          >
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      </div>
    `;
  }).join("");

  if (typeof lucide !== "undefined") lucide.createIcons();
}

window.quickSetSpotlightAuthor = async function(authorName) {
  const select = document.getElementById("settings-featured-author-select");
  if (select) select.value = authorName;
  updateSpotlightAuthorPreview(authorName);
  await window.saveFeaturedAuthorSettings();
};

function populateFeaturedAuthorSelect(authors, selectedName) {
  const select = document.getElementById("settings-featured-author-select");
  if (!select) return;

  const currentVal = selectedName !== undefined ? selectedName : currentFeaturedAuthor;
  select.innerHTML = '<option value="">Select from existing authors...</option>';

  (authors || []).forEach((author) => {
    const name = typeof author === "string" ? author : (author.name || "");
    if (!name) return;
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    if (currentVal && name.toLowerCase() === currentVal.toLowerCase()) {
      opt.selected = true;
    }
    select.appendChild(opt);
  });

  updateSpotlightAuthorPreview(select.value);
}

function updateSpotlightAuthorPreview(authorName) {
  const card = document.getElementById("settings-spotlight-author-preview-card");
  const nameEl = document.getElementById("settings-spotlight-author-name");
  const imgEl = document.getElementById("settings-spotlight-author-img");
  const iconEl = document.getElementById("settings-spotlight-author-icon");
  if (!card) return;

  if (!authorName) {
    card.classList.add("hidden");
    return;
  }

  const author = (storeAuthorsCache || []).find((a) => {
    const aName = typeof a === "string" ? a : (a.name || "");
    return aName.toLowerCase() === authorName.toLowerCase();
  });

  card.classList.remove("hidden");
  if (nameEl) nameEl.textContent = authorName;

  const imgUrl = author && typeof author === "object" ? (author.image || "") : "";
  const avatarPlaceholder = `https://ui-avatars.com/api/?name=${encodeURIComponent(authorName || 'Author')}&background=1e293b&color=fff`;

  if (imgEl) {
    imgEl.src = imgUrl || avatarPlaceholder;
    imgEl.onerror = () => { imgEl.src = avatarPlaceholder; };
    imgEl.classList.remove("hidden");
  }
  if (iconEl) iconEl.classList.add("hidden");

  if (typeof lucide !== "undefined") lucide.createIcons();
}

window.renderStoreAuthorsList = renderStoreAuthorsList;
window.populateFeaturedAuthorSelect = populateFeaturedAuthorSelect;
window.updateSpotlightAuthorPreview = updateSpotlightAuthorPreview;

window.onFeaturedAuthorSelectChange = function(authorName) {
  updateSpotlightAuthorPreview(authorName);
};

window.clearSpotlightAuthorSelection = function() {
  const select = document.getElementById("settings-featured-author-select");
  if (select) select.value = "";
  updateSpotlightAuthorPreview("");
};

function validateAuthorImageFile(file) {
  if (!file) return { valid: false, message: 'No file selected.' };
  
  const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/jpg'];
  const allowedExts = ['jpg', 'jpeg', 'png', 'webp', 'gif'];
  const maxSizeBytes = 5 * 1024 * 1024; // 5MB

  const ext = file.name ? file.name.split('.').pop().toLowerCase() : '';
  const isTypeValid = allowedTypes.includes(file.type);
  const isExtValid = allowedExts.includes(ext);

  if (!isTypeValid && !isExtValid) {
    return {
      valid: false,
      message: `Invalid format (${ext ? '.' + ext : 'unknown'}). Supported formats are JPG, PNG, WEBP, and GIF.`
    };
  }

  if (file.size > maxSizeBytes) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    return {
      valid: false,
      message: `File is too large (${sizeMb}MB). Maximum allowed size is 5MB.`
    };
  }

  return { valid: true };
}

window.handleNewAuthorFileChange = function(source) {
  let file = null;
  if (source instanceof File) {
    file = source;
  } else if (source && source.files && source.files[0]) {
    file = source.files[0];
  }

  if (!file) return;

  const validation = validateAuthorImageFile(file);
  if (!validation.valid) {
    const isDark = document.documentElement.classList.contains('dark');
    Swal.fire({
      title: 'Invalid Image Format',
      text: validation.message,
      icon: 'error',
      confirmButtonText: 'OK',
      confirmButtonColor: '#e11d48',
      background: isDark ? '#0f172a' : '#ffffff',
      color: isDark ? '#ffffff' : '#0f172a',
      customClass: { popup: 'rounded-2xl' }
    });
    window.clearNewAuthorPhoto();
    return;
  }

  newAuthorSelectedFile = file;

  const promptEl = document.getElementById("settings-author-upload-prompt");
  const previewContainer = document.getElementById("settings-author-selected-preview");
  const previewImg = document.getElementById("settings-new-author-preview-img");
  const fnEl = document.getElementById("settings-new-author-filename");
  const sizeEl = document.getElementById("settings-new-author-filesize");

  if (fnEl) fnEl.textContent = file.name;
  if (sizeEl) {
    const kb = Math.round(file.size / 1024);
    sizeEl.textContent = kb >= 1024 ? `${(file.size / (1024 * 1024)).toFixed(1)} MB` : `${kb} KB`;
  }
  if (previewImg) {
    previewImg.src = URL.createObjectURL(file);
  }
  if (promptEl) promptEl.classList.add("hidden");
  if (previewContainer) previewContainer.classList.remove("hidden");
  if (typeof lucide !== "undefined") lucide.createIcons();
};

window.clearNewAuthorPhoto = function() {
  newAuthorSelectedFile = null;
  const fileInput = document.getElementById("settings-new-author-file");
  if (fileInput) fileInput.value = "";

  const promptEl = document.getElementById("settings-author-upload-prompt");
  const previewContainer = document.getElementById("settings-author-selected-preview");
  const previewImg = document.getElementById("settings-new-author-preview-img");
  const fnEl = document.getElementById("settings-new-author-filename");
  const sizeEl = document.getElementById("settings-new-author-filesize");

  if (fnEl) fnEl.textContent = "";
  if (sizeEl) sizeEl.textContent = "";
  if (previewImg) previewImg.src = "";
  if (previewContainer) previewContainer.classList.add("hidden");
  if (promptEl) promptEl.classList.remove("hidden");
  if (typeof lucide !== "undefined") lucide.createIcons();
};

function setupAuthorDropzone() {
  const dropzone = document.getElementById("settings-author-dropzone");
  if (!dropzone || dropzone._hasDragListeners) return;
  dropzone._hasDragListeners = true;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('border-primary', 'bg-primary/5', 'dark:bg-primary/10');
      dropzone.classList.remove('border-gray-300', 'dark:border-gray-700');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('border-primary', 'bg-primary/5', 'dark:bg-primary/10');
      dropzone.classList.add('border-gray-300', 'dark:border-gray-700');
    }, false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files[0]) {
      window.handleNewAuthorFileChange(dt.files[0]);
    }
  }, false);
}

window.openAddAuthorModal = function() {
  const modal = document.getElementById("store-add-author-modal");
  if (!modal) return;
  modal.classList.remove("hidden");
  setTimeout(() => modal.classList.remove("opacity-0"), 10);
  const input = document.getElementById("settings-new-author-input");
  if (input) {
    input.value = "";
    setTimeout(() => input.focus(), 100);
  }
  window.clearNewAuthorPhoto();
  setupAuthorDropzone();
  if (typeof lucide !== "undefined") lucide.createIcons();
};

window.closeAddAuthorModal = function() {
  const modal = document.getElementById("store-add-author-modal");
  if (!modal) return;
  modal.classList.add("opacity-0");
  setTimeout(() => modal.classList.add("hidden"), 200);
  window.clearNewAuthorPhoto();
};

window.confirmClearSpotlightAuthor = async function() {
  const isDark = document.documentElement.classList.contains("dark");
  const currentName = currentFeaturedAuthor || (document.getElementById("settings-spotlight-author-name")?.textContent || "").trim();
  const authorDisplay = currentName && currentName !== "None selected" ? `<strong>"${escapeHtml(currentName)}"</strong>` : "the active spotlight author";

  const result = await Swal.fire({
    title: "Clear Spotlight Author?",
    html: `Are you sure you want to remove ${authorDisplay} from the BEST SELLER BOOKS storefront showcase?`,
    icon: "question",
    showCancelButton: true,
    confirmButtonText: "Yes, Clear Spotlight",
    cancelButtonText: "Keep Author",
    confirmButtonColor: "#e11d48",
    cancelButtonColor: "#64748b",
    background: isDark ? "#0f172a" : "#ffffff",
    color: isDark ? "#ffffff" : "#0f172a",
    customClass: {
      popup: "rounded-2xl border border-gray-200 dark:border-white/10 shadow-2xl",
      confirmButton: "rounded-xl font-bold px-4 py-2.5 cursor-pointer",
      cancelButton: "rounded-xl font-semibold px-4 py-2.5 cursor-pointer"
    }
  });

  if (result.isConfirmed) {
    window.clearSpotlightAuthorSelection();
    await window.saveFeaturedAuthorSettings();
  }
};

window.initStoreAuthorsTab = async function() {
  const container = document.getElementById("settings-authors-list");
  if (!container) return;
  const apiBase = (window.CONFIG && window.CONFIG.API_BASE) || '';

  try {
    const res = await apiFetch(`${apiBase}/api/user/store/authors`, { method: "GET" });
    const data = await res.json();
    if (data.status) {
      storeAuthorsCache = data.authors || [];
      currentFeaturedAuthor = data.featured_author || "";
      renderStoreAuthorsList(storeAuthorsCache, currentFeaturedAuthor);
      populateFeaturedAuthorSelect(storeAuthorsCache, currentFeaturedAuthor);
    }
  } catch (err) {
    console.error("Error loading authors:", err);
  }
};

window.addStoreAuthor = async function() {
  const input = document.getElementById("settings-new-author-input");
  if (!input) return;
  const name = input.value.trim();
  const isDark = document.documentElement.classList.contains("dark");

  if (!name) {
    Swal.fire({
      title: "Author Name Required",
      text: "Please enter the author's full name.",
      icon: "warning",
      confirmButtonText: "OK",
      confirmButtonColor: "#2563eb",
      background: isDark ? "#0f172a" : "#ffffff",
      color: isDark ? "#ffffff" : "#0f172a",
      customClass: {
        popup: "rounded-2xl border border-gray-200 dark:border-white/10 shadow-2xl",
        confirmButton: "rounded-xl font-bold px-4 py-2.5 cursor-pointer"
      }
    });
    return;
  }

  // Validate image if selected
  if (newAuthorSelectedFile) {
    const validation = validateAuthorImageFile(newAuthorSelectedFile);
    if (!validation.valid) {
      Swal.fire({
        title: "Invalid Image",
        text: validation.message,
        icon: "error",
        confirmButtonText: "OK",
        confirmButtonColor: "#e11d48",
        background: isDark ? "#0f172a" : "#ffffff",
        color: isDark ? "#ffffff" : "#0f172a",
        customClass: { popup: "rounded-2xl" }
      });
      return;
    }
  }

  const btn = document.getElementById("btn-add-store-author");
  if (btn) {
    btn.disabled = true;
    btn.classList.add("opacity-50");
  }
  const apiBase = (window.CONFIG && window.CONFIG.API_BASE) || '';

  try {
    const fd = new FormData();
    fd.append("action", "add_author");
    fd.append("name", name);

    if (newAuthorSelectedFile) {
      fd.append("image", newAuthorSelectedFile);
    }

    const res = await apiFetch(`${apiBase}/api/user/store/authors`, {
      method: "POST",
      body: fd
    });
    const data = await res.json();
    if (data.status) {
      window.closeAddAuthorModal();
      Swal.fire({
        title: "Author Saved",
        text: data.message || `Author "${name}" saved successfully.`,
        icon: "success",
        timer: 1800,
        showConfirmButton: false,
        background: isDark ? "#0f172a" : "#ffffff",
        color: isDark ? "#ffffff" : "#0f172a",
        customClass: { popup: "rounded-2xl" }
      });
      input.value = "";
      window.clearNewAuthorPhoto();
      storeAuthorsCache = data.authors || [];
      currentFeaturedAuthor = data.featured_author || currentFeaturedAuthor;
      renderStoreAuthorsList(storeAuthorsCache, currentFeaturedAuthor);
      populateFeaturedAuthorSelect(storeAuthorsCache, currentFeaturedAuthor);
    } else {
      Swal.fire({
        title: "Error",
        text: data.message || "Failed to add author",
        icon: "error",
        confirmButtonColor: "#e11d48",
        background: isDark ? "#0f172a" : "#ffffff",
        color: isDark ? "#ffffff" : "#0f172a",
        customClass: { popup: "rounded-2xl" }
      });
    }
  } catch (err) {
    console.error("Error adding author:", err);
    showToast("Error adding author", "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.classList.remove("opacity-50");
    }
  }
};

window.deleteStoreAuthor = async function(name) {
  if (!name) return;
  const isDark = document.documentElement.classList.contains("dark");
  const result = await Swal.fire({
    title: "Delete Author?",
    html: `Are you sure you want to remove <strong>"${escapeHtml(name)}"</strong> from your store authors?<br><span class="text-xs text-gray-400">If this author is currently in the spotlight, they will be removed from the storefront showcase.</span>`,
    icon: "warning",
    showCancelButton: true,
    confirmButtonText: "Yes, Delete Author",
    cancelButtonText: "Cancel",
    confirmButtonColor: "#e11d48",
    cancelButtonColor: "#64748b",
    background: isDark ? "#0f172a" : "#ffffff",
    color: isDark ? "#ffffff" : "#0f172a",
    customClass: {
      popup: "rounded-2xl border border-gray-200 dark:border-white/10 shadow-2xl",
      confirmButton: "rounded-xl font-bold px-4 py-2.5 cursor-pointer",
      cancelButton: "rounded-xl font-semibold px-4 py-2.5 cursor-pointer"
    }
  });

  if (!result.isConfirmed) return;
  const apiBase = (window.CONFIG && window.CONFIG.API_BASE) || '';

  try {
    const res = await apiFetch(`${apiBase}/api/user/store/authors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "delete_author", name: name })
    });
    const data = await res.json();
    if (data.status) {
      Swal.fire({
        title: "Author Deleted",
        text: data.message || `Author "${name}" has been removed.`,
        icon: "success",
        timer: 1800,
        showConfirmButton: false,
        background: isDark ? "#0f172a" : "#ffffff",
        color: isDark ? "#ffffff" : "#0f172a",
        customClass: { popup: "rounded-2xl" }
      });
      storeAuthorsCache = data.authors || [];
      currentFeaturedAuthor = data.featured_author || "";
      renderStoreAuthorsList(storeAuthorsCache, currentFeaturedAuthor);
      populateFeaturedAuthorSelect(storeAuthorsCache, currentFeaturedAuthor);
    } else {
      Swal.fire({
        title: "Error",
        text: data.message || "Failed to delete author",
        icon: "error",
        confirmButtonColor: "#e11d48",
        background: isDark ? "#0f172a" : "#ffffff",
        color: isDark ? "#ffffff" : "#0f172a",
        customClass: { popup: "rounded-2xl" }
      });
    }
  } catch (err) {
    console.error("Error deleting author:", err);
    showToast("Error deleting author", "error");
  }
};

window.saveFeaturedAuthorSettings = async function() {
  const select = document.getElementById("settings-featured-author-select");
  const authorName = select ? select.value.trim() : "";
  const isDark = document.documentElement.classList.contains("dark");

  const btn = document.getElementById("btn-save-featured-author");
  if (btn) {
    btn.disabled = true;
    btn.classList.add("opacity-50");
  }
  const apiBase = (window.CONFIG && window.CONFIG.API_BASE) || '';

  try {
    const res = await apiFetch(`${apiBase}/api/user/store/authors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "set_featured_author",
        author_name: authorName
      })
    });
    const data = await res.json();
    if (data.status) {
      currentFeaturedAuthor = data.featured_author || "";
      Swal.fire({
        title: "Spotlight Author Saved",
        text: authorName
          ? `"${authorName}" is now showcased in BEST SELLER BOOKS on your storefront.`
          : "Featured author spotlight cleared.",
        icon: "success",
        timer: 2000,
        showConfirmButton: false,
        background: isDark ? "#0f172a" : "#ffffff",
        color: isDark ? "#ffffff" : "#0f172a",
        customClass: { popup: "rounded-2xl" }
      });
      renderStoreAuthorsList(storeAuthorsCache, currentFeaturedAuthor);
      updateSpotlightAuthorPreview(currentFeaturedAuthor);
    } else {
      Swal.fire({
        title: "Error",
        text: data.message || "Failed to update spotlight author",
        icon: "error",
        confirmButtonColor: "#e11d48",
        background: isDark ? "#0f172a" : "#ffffff",
        color: isDark ? "#ffffff" : "#0f172a",
        customClass: { popup: "rounded-2xl" }
      });
    }
  } catch (err) {
    console.error("Error saving featured author:", err);
    showToast("Error saving featured author", "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.classList.remove("opacity-50");
    }
  }
};

// Backdrop click and escape key for Add Author modal
document.addEventListener("click", (e) => {
  const modal = document.getElementById("store-add-author-modal");
  if (modal && e.target === modal) {
    window.closeAddAuthorModal();
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const modal = document.getElementById("store-add-author-modal");
    if (modal && !modal.classList.contains("hidden")) {
      window.closeAddAuthorModal();
    }
  }
});



