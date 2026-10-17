/**
 * verification.js - Minimalist Tier-Based Verification System
 * 
 * Rules:
 * - Tier 1 (Personal Identity): Unlocks up to ₦50,000 daily limit (in user currency).
 * - When Tier 1 is verified: Tier 1 is hidden, and Tier 2 (Corporate KYB) shows.
 * - When both are verified: Shows verification complete celebration screen.
 * - 100% powered by embedded Myaza Trust SDK. Zero manual inputs or redundant badges.
 */

(function () {
  "use strict";

  // Expose global methods
  window.initVerificationPage = initVerificationPage;
  window.loadVerificationData = loadVerificationData;
  window.initTier1Widget = initTier1Widget;
  window.initTier2Widget = initTier2Widget;

  // Backwards compatibility stubs for legacy references
  window.goToVerificationStep = function () {};
  window.proceedToKyb = function () {};
  window.proceedToSummary = function () {};
  window.handleVerificationFileChange = function () {};
  window.triggerFileInput = function () {};
  window.submitFinalVerification = function () {};
  window.fillTestId = function () {};
  window.openHeadshotChoiceModal = function () {};
  window.closeHeadshotChoiceModal = function () {};
  window.selectHeadshotMethod = function () {};
  window.openCameraModal = function () {};
  window.captureCameraSnapshot = function () {};
  window.retakeCameraSnapshot = function () {};
  window.acceptCameraSnapshot = function () {};
  window.closeCameraModal = function () {};
  window.toggleManualKyc = function () {};
  window.toggleManualKyb = function () {};
  window.initMyazaWidget = function (step) {
    if (step === "kyb") {
      initTier2Widget();
    } else {
      initTier1Widget();
    }
  };

  // State
  let _verificationInitializing = false;
  let _kycRecord = null;
  let _kybRecord = null;
  let _kycStatus = null; // '0' = Under Review, '1' = Verified, '2' = Declined, null = Unverified
  let _kybStatus = null;
  let _kycSessionUrl = null;
  let _kybSessionUrl = null;

  /**
   * Formats Tier 1 daily withdrawal limit in the user's active country currency.
   * Dynamically reads tier1_daily_limit and tier1_currency from user data or country configuration.
   */
  function getTier1LimitDisplay(currencyCode, data) {
    const activeData = data || window.userData || JSON.parse(localStorage.getItem("user_data") || "null");
    const limitAmount = (activeData && activeData.tier1_daily_limit !== undefined && activeData.tier1_daily_limit !== null)
      ? Number(activeData.tier1_daily_limit)
      : (window.USER_TIER1_DAILY_LIMIT !== undefined ? window.USER_TIER1_DAILY_LIMIT : 50000);

    const code = (
      (activeData && activeData.tier1_currency) ||
      currencyCode ||
      window.STORE_CURRENCY_CODE ||
      "NGN"
    ).toUpperCase().trim();

    const symbols = {
      USD: "$",
      EUR: "€",
      GBP: "£",
      NGN: "₦",
      KES: "KSh ",
      GHS: "GH₵ ",
      ZAR: "R ",
      CAD: "C$",
      AUD: "A$",
      INR: "₹"
    };
    const symbol = symbols[code] || (window.STORE_CURRENCY_SYMBOL || code + " ");

    const formattedNumber = Number(limitAmount).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });

    return {
      symbol: symbol,
      amount: limitAmount,
      currency: code,
      formatted: `${symbol}${formattedNumber}`,
      short: `${symbol}${formattedNumber} / day`
    };
  }

  /**
   * Initializes the verification page.
   */
  async function initVerificationPage() {
    const container = document.getElementById("verification-container");
    if (!container) return;

    // Instantly render daily limit and tier status from local cache (0ms delay)
    try {
      const cached = JSON.parse(localStorage.getItem("user_data") || "null");
      if (cached) {
        applyComplianceStatus(cached);
      } else {
        const currencyCode = window.STORE_CURRENCY_CODE || "NGN";
        const limitInfo = getTier1LimitDisplay(currencyCode);
        const limitEl = document.getElementById("verif-withdrawal-limit");
        if (limitEl && (!limitEl.textContent || limitEl.textContent.trim() === "₦0.00")) {
          limitEl.textContent = `${limitInfo.symbol}0.00`;
        }
      }
    } catch (e) {
      console.warn("[Verification] Cache read failed:", e);
    }

    try {
      await loadVerificationData();
    } catch (err) {
      console.error("[Verification] Init error:", err);
    } finally {
      if (window.lucide) window.lucide.createIcons();
    }
  }

  /**
   * Fetches latest user data and verification records from backend.
   */
  async function loadVerificationData() {
    // Check cached data first for instant UI response
    try {
      const cached = JSON.parse(localStorage.getItem("user_data") || "null");
      if (cached) {
        applyComplianceStatus(cached);
      }
    } catch (e) {
      console.warn("Cached user data parse failed:", e);
    }

    try {
      const res = await apiFetch(`${window.FLEZ_API_BASE || ""}/api/user/data`, {
        method: "POST"
      });
      if (res.status === 401 || res.status === 403) {
        window.location.href = "/login";
        return;
      }
      const json = await res.json();
      if (json.status && json.data) {
        window.userData = json.data;
        localStorage.setItem("user_data", JSON.stringify(json.data));
        applyComplianceStatus(json.data);
      }
    } catch (err) {
      console.error("[Verification] Failed to fetch compliance status:", err);
    }
  }

  /**
   * Applies the compliance state:
   * - Tier 1: Shows only Tier 1 widget or Under Review.
   * - Tier 2: Shows ONLY when Tier 1 is verified (Tier 1 is completely hidden).
   * - All Verified: Shows clean completion screen when both are verified.
   */
  function applyComplianceStatus(data) {
    if (!data) return;

    const verifications = data.verification || [];
    _kycRecord = verifications.find(
      (v) => (v.verification_type || "").toUpperCase() === "KYC"
    ) || null;
    _kybRecord = verifications.find(
      (v) => (v.verification_type || "").toUpperCase() === "KYB"
    ) || null;

    _kycStatus = _kycRecord ? String(_kycRecord.verification_status) : null;
    _kybStatus = _kybRecord ? String(_kybRecord.verification_status) : null;

    // Ground truth: If kyc_verified or kyb_verified is false on user, verification is NOT approved
    const isKycApproved = Boolean(data.kyc_verified);
    const isKybApproved = Boolean(data.kyb_verified);

    if (!isKycApproved) {
      if (_kycStatus === "1") {
        _kycStatus = null; // Reset to unverified so Tier 1 widget displays
      }
    } else {
      _kycStatus = "1";
    }

    if (!isKybApproved) {
      if (_kybStatus === "1") {
        _kybStatus = null;
      }
    } else {
      _kybStatus = "1";
    }

    const userCurrency =
      data.tier1_currency ||
      window.STORE_CURRENCY_CODE ||
      data.details?.[0]?.currency ||
      data.details?.currency ||
      "NGN";
    const limitInfo = getTier1LimitDisplay(userCurrency, data);

    // Update dynamic currency limit labels
    const widgetLimitEl = document.getElementById("tier1-widget-limit-text");
    const reviewLimitEl = document.getElementById("tier1-review-limit-text");
    if (widgetLimitEl) widgetLimitEl.textContent = limitInfo.formatted;
    if (reviewLimitEl) reviewLimitEl.textContent = limitInfo.formatted;

    // Update Top Banner indicating Current Tier & Withdrawal Limit
    updateTopBanner(_kycStatus, _kybStatus, limitInfo);

    // Apply clean progressive visibility
    applyTierVisibility(_kycStatus, _kybStatus);

    if (window.lucide) window.lucide.createIcons();
  }

  /**
   * Updates Top Compliance Banner with active Tier and Current Daily Withdrawal Limit.
   */
  function updateTopBanner(kycStatus, kybStatus, limitInfo) {
    const tierBadgeEl = document.getElementById("verif-current-tier-badge");
    const descEl = document.getElementById("verif-status-desc");
    const limitEl = document.getElementById("verif-withdrawal-limit");

    if (!limitEl) return;

    if (kycStatus === "1" && kybStatus === "1") {
      // Both Verified: Tier 2 Active, Unlimited
      if (tierBadgeEl) {
        tierBadgeEl.textContent = "Verified";
        tierBadgeEl.className = "text-xs font-semibold px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400";
      }
      if (descEl) {
        descEl.textContent = "Your identity and business are verified. Unlimited platform withdrawals active.";
      }
      limitEl.textContent = "Unlimited";
    } else if (kycStatus === "1") {
      // Tier 1 Verified
      const isKybInReview = kybStatus === "0";
      if (tierBadgeEl) {
        tierBadgeEl.textContent = isKybInReview ? "Tier 2 In Review" : "Tier 2";
        tierBadgeEl.className = isKybInReview
          ? "text-xs font-semibold px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-400"
          : "text-xs font-semibold px-2 py-0.5 rounded-md bg-primary/10 text-primary";
      }
      if (descEl) {
        descEl.textContent = isKybInReview
          ? "Tier 1 verified. Tier 2 corporate verification is currently under review."
          : "Tier 1 verified. Complete Tier 2 verification below to unlock unlimited withdrawals.";
      }
      limitEl.textContent = limitInfo.formatted;
    } else {
      // Tier 1 Not Verified
      const isUnderReview = kycStatus === "0";
      if (tierBadgeEl) {
        tierBadgeEl.textContent = isUnderReview ? "Tier 1 In Review" : "Tier 1";
        tierBadgeEl.className = isUnderReview
          ? "text-xs font-semibold px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-400"
          : "text-xs font-semibold px-2 py-0.5 rounded-md bg-primary/10 text-primary";
      }
      if (descEl) {
        descEl.textContent = isUnderReview
          ? "Personal identity details submitted and under review."
          : "Complete personal verification below to activate daily withdrawals.";
      }
      const symbol = limitInfo.symbol || (window.STORE_CURRENCY_SYMBOL || "₦");
      limitEl.textContent = `${symbol}0.00`;
    }
  }

  /**
   * Progressive Tier Visibility State Machine:
   * 1. If both are verified ('1'): Show all-verified celebration card, hide everything else.
   * 2. If Tier 1 is verified ('1'): HIDE Tier 1 completely! Show Tier 2 widget or under-review card.
   * 3. If Tier 1 is NOT verified: HIDE Tier 2 completely! Show Tier 1 widget or under-review card.
   */
  function applyTierVisibility(kycStatus, kybStatus) {
    const tier1Container = document.getElementById("tier1-container");
    const tier1ReviewCard = document.getElementById("tier1-under-review-card");
    const tier1WidgetCard = document.getElementById("tier1-widget-card");

    const tier2Container = document.getElementById("tier2-container");
    const tier2ReviewCard = document.getElementById("tier2-under-review-card");
    const tier2WidgetCard = document.getElementById("tier2-widget-card");

    const allVerifiedContainer = document.getElementById("all-verified-container");

    if (!tier1Container || !tier2Container) return;

    if (kycStatus === "1" && kybStatus === "1") {
      // Both Fully Verified!
      tier1Container.classList.add("hidden");
      tier2Container.classList.add("hidden");
      if (allVerifiedContainer) allVerifiedContainer.classList.remove("hidden");
      return;
    }

    if (allVerifiedContainer) allVerifiedContainer.classList.add("hidden");

    if (kycStatus === "1") {
      // Tier 1 is verified -> HIDE Tier 1 completely! SHOW Tier 2!
      tier1Container.classList.add("hidden");
      tier2Container.classList.remove("hidden");

      if (kybStatus === "0") {
        // Corporate KYB is Under Review
        if (tier2ReviewCard) tier2ReviewCard.classList.remove("hidden");
        if (tier2WidgetCard) tier2WidgetCard.classList.add("hidden");
      } else {
        // Corporate KYB is unverified or declined -> Show interactive KYB widget
        if (tier2ReviewCard) tier2ReviewCard.classList.add("hidden");
        if (tier2WidgetCard) tier2WidgetCard.classList.remove("hidden");
        initTier2Widget();
      }
    } else {
      // Tier 1 is NOT verified -> HIDE Tier 2 completely! SHOW Tier 1!
      tier2Container.classList.add("hidden");
      tier1Container.classList.remove("hidden");

      if (kycStatus === "0") {
        // Individual KYC is Under Review
        if (tier1ReviewCard) tier1ReviewCard.classList.remove("hidden");
        if (tier1WidgetCard) tier1WidgetCard.classList.add("hidden");
      } else {
        // Individual KYC is unverified or declined -> Show interactive KYC widget
        if (tier1ReviewCard) tier1ReviewCard.classList.add("hidden");
        if (tier1WidgetCard) tier1WidgetCard.classList.remove("hidden");
        initTier1Widget();
      }
    }
  }

  /**
   * Initializes or refreshes the embedded Myaza Trust KYC widget for Tier 1.
   */
  async function initTier1Widget(forceRefresh = false) {
    const iframe = document.getElementById("kyc-myaza-iframe");
    const loading = document.getElementById("kyc-widget-loading");
    if (!iframe) return;

    if (!forceRefresh && _kycSessionUrl) {
      if (iframe.src !== _kycSessionUrl) iframe.src = _kycSessionUrl;
      if (loading) loading.classList.add("hidden");
      return;
    }

    if (loading) {
      loading.classList.remove("hidden");
      loading.innerHTML = `
        <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
        <p class="text-xs text-slate-400 font-medium">Initializing verification session...</p>
      `;
    }

    try {
      const res = await apiFetch(`${window.FLEZ_API_BASE || ""}/api/user/verification/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ step: "kyc" })
      });
      const data = await res.json();

      if (data.status && data.url) {
        let finalUrl = data.url;
        try {
          const u = new URL(data.url);
          u.searchParams.set("origin", window.location.origin);
          finalUrl = u.toString();
        } catch (e) {
          finalUrl = data.url;
        }

        _kycSessionUrl = finalUrl;
        iframe.src = finalUrl;

        iframe.onload = () => {
          setTimeout(() => {
            if (loading) loading.classList.add("hidden");
          }, 600);
        };
      } else if (data.locked) {
        if (loading) loading.classList.add("hidden");
        await loadVerificationData();
      } else {
        if (loading) {
          loading.innerHTML = `
            <div class="text-center p-6 space-y-3">
              <p class="text-xs text-rose-400 font-medium">${data.message || "Failed to initialize verification session"}</p>
              <button type="button" onclick="initTier1Widget(true)" class="px-3.5 py-1.5 bg-white/10 hover:bg-white/20 text-white rounded-lg text-xs font-semibold transition-all">
                Try Again
              </button>
            </div>
          `;
        }
      }
    } catch (err) {
      console.error("[Myaza] Error requesting Tier 1 session:", err);
      if (loading) {
        loading.innerHTML = `
          <div class="text-center p-6 space-y-3">
            <p class="text-xs text-rose-400 font-medium">Unable to connect to verification provider.</p>
            <button type="button" onclick="initTier1Widget(true)" class="px-3.5 py-1.5 bg-white/10 hover:bg-white/20 text-white rounded-lg text-xs font-semibold transition-all">
              Retry Connection
            </button>
          </div>
        `;
      }
    }
  }

  /**
   * Initializes or refreshes the embedded Myaza Trust KYB widget for Tier 2.
   */
  async function initTier2Widget(forceRefresh = false) {
    const iframe = document.getElementById("kyb-myaza-iframe");
    const loading = document.getElementById("kyb-widget-loading");
    if (!iframe) return;

    if (!forceRefresh && _kybSessionUrl) {
      if (iframe.src !== _kybSessionUrl) iframe.src = _kybSessionUrl;
      if (loading) loading.classList.add("hidden");
      return;
    }

    if (loading) {
      loading.classList.remove("hidden");
      loading.innerHTML = `
        <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
        <p class="text-xs text-slate-400 font-medium">Initializing business verification session...</p>
      `;
    }

    try {
      const res = await apiFetch(`${window.FLEZ_API_BASE || ""}/api/user/verification/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ step: "kyb" })
      });
      const data = await res.json();

      if (data.status && data.url) {
        let finalUrl = data.url;
        try {
          const u = new URL(data.url);
          u.searchParams.set("origin", window.location.origin);
          finalUrl = u.toString();
        } catch (e) {
          finalUrl = data.url;
        }

        _kybSessionUrl = finalUrl;
        iframe.src = finalUrl;

        iframe.onload = () => {
          setTimeout(() => {
            if (loading) loading.classList.add("hidden");
          }, 600);
        };
      } else if (data.locked) {
        if (loading) loading.classList.add("hidden");
        await loadVerificationData();
      } else {
        if (loading) {
          loading.innerHTML = `
            <div class="text-center p-6 space-y-3">
              <p class="text-xs text-rose-400 font-medium">${data.message || "Failed to initialize business verification session"}</p>
              <button type="button" onclick="initTier2Widget(true)" class="px-3.5 py-1.5 bg-white/10 hover:bg-white/20 text-white rounded-lg text-xs font-semibold transition-all">
                Try Again
              </button>
            </div>
          `;
        }
      }
    } catch (err) {
      console.error("[Myaza] Error requesting Tier 2 session:", err);
      if (loading) {
        loading.innerHTML = `
          <div class="text-center p-6 space-y-3">
            <p class="text-xs text-rose-400 font-medium">Unable to connect to verification provider.</p>
            <button type="button" onclick="initTier2Widget(true)" class="px-3.5 py-1.5 bg-white/10 hover:bg-white/20 text-white rounded-lg text-xs font-semibold transition-all">
              Retry Connection
            </button>
          </div>
        `;
      }
    }
  }

  /**
   * Listen to Myaza Trust Hosted Link events via postMessage.
   */
  window.addEventListener("message", async (event) => {
    if (event.origin !== "https://trust.myaza.co") return;
    if (!event.data || event.data.source !== "myaza-kyc") return;

    console.log("[Myaza Trust Event]", event.data);
    const { type, sessionId, verificationId, step } = event.data;

    if (type === "ready" || type === "started") {
      const kycLoading = document.getElementById("kyc-widget-loading");
      const kybLoading = document.getElementById("kyb-widget-loading");
      if (kycLoading) kycLoading.classList.add("hidden");
      if (kybLoading) kybLoading.classList.add("hidden");
    }

    if (type === "submitted" || type === "completed") {
      const isTier2Active =
        step === "kyb" ||
        (_kycStatus === "1" && !document.getElementById("tier2-container")?.classList.contains("hidden"));
      const currentStep = isTier2Active ? "kyb" : "kyc";
      const verifId = verificationId || sessionId;

      try {
        await apiFetch(`${window.FLEZ_API_BASE || ""}/api/user/verification/complete-session`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            step: currentStep,
            verification_id: verifId
          })
        });

        const currencyCode = window.STORE_CURRENCY_CODE || "NGN";
        const limitInfo = getTier1LimitDisplay(currencyCode, window.userData);

        Swal.fire({
          icon: "success",
          title: currentStep === "kyc" ? "Identity Submitted" : "Business Submitted",
          text: currentStep === "kyc"
            ? `Your identity verification was submitted. Once approved, withdrawals up to ${limitInfo.formatted} daily will be unlocked.`
            : "Your business details were submitted and are undergoing official review.",
          background: "#111827",
          color: "#fff",
          confirmButtonColor: "#cfff45",
          timer: 3500,
          timerProgressBar: true
        });

        await loadVerificationData();
      } catch (err) {
        console.error("[Verification] Error updating session completion:", err);
      }
    }

    if (type === "error") {
      console.warn("[Myaza] Verification Error event:", event.data);
    }
  });

  // Self-initialize on DOM ready and Swup SPA navigation
  function triggerInitIfPresent() {
    if (document.getElementById("verification-container") || document.getElementById("verification-status-banner")) {
      initVerificationPage();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", triggerInitIfPresent);
  } else {
    triggerInitIfPresent();
  }

  // Handle Swup SPA content replacements
  document.addEventListener("swup:contentReplaced", triggerInitIfPresent);
  document.addEventListener("swup:pageView", triggerInitIfPresent);
  if (window.swup && window.swup.hooks) {
    try {
      window.swup.hooks.on("page:view", triggerInitIfPresent);
    } catch (e) {}
  }
})();
