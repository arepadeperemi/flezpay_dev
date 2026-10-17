// Initialize Swup
if (!window.flezSwup) {
  window.flezSwup = new Swup({
    animationSelector: '[class*="swup-transition-"]',
  });

  // Swup 4 Event: Re-initialize App on Content Replace
  // Single authoritative hook — handles all per-page init
  window.flezSwup.hooks.on("page:view", () => {
    initApp();
    initTtsModal();
    if (typeof lucide !== "undefined") lucide.createIcons();
    if (window.SidebarComponent) window.SidebarComponent.initActiveLink();
    if (window.NotificationComponent) window.NotificationComponent.render();
  });

  // Manually execute scripts found in the new content
  window.flezSwup.hooks.on("content:replace", () => {
    const swupContainer = document.querySelector("#swup");
    if (!swupContainer) return;

    // Signal Tailwind to re-process new content
    if (window.tailwind && typeof window.tailwind.reprocess === "function") {
      console.log("SPA: Re-processing Tailwind styles...");
      tailwind.reprocess();
    }

    const scripts = swupContainer.querySelectorAll("script");
    scripts.forEach((oldScript) => {
      try {
        const newScript = document.createElement("script");
        // Copy attributes
        Array.from(oldScript.attributes).forEach((attr) => {
          newScript.setAttribute(attr.name, attr.value);
        });
        // Copy content
        newScript.appendChild(document.createTextNode(oldScript.innerHTML));
        // Replace old with new to trigger execution
        oldScript.parentNode.replaceChild(newScript, oldScript);
      } catch (err) {
        console.error("SPA script replacement warning:", err);
      }
    });
  });
}

// Global chart instances to prevent "Canvas is already in use" errors
window.flezCharts = window.flezCharts || {};

// Centralized User Currency Resolution
const CURRENCY_SYMBOLS_MAP = {
  USD: "$",
  EUR: "€",
  GBP: "£",
  NGN: "₦",
  KES: "KSh",
  GHS: "GH₵",
  ZAR: "R",
  CAD: "C$",
  AUD: "A$",
  INR: "₹",
};

function getUserCurrencySymbol(user) {
  if (typeof window !== "undefined" && window.STORE_CURRENCY_SYMBOL) {
    return window.STORE_CURRENCY_SYMBOL;
  }
  let code = user?.details?.[0]?.currency;
  if (!code && typeof window !== "undefined") {
    try {
      const stored = JSON.parse(localStorage.getItem("user_data") || "{}");
      code = stored?.details?.[0]?.currency;
    } catch (e) {}
  }
  if (!code && typeof window !== "undefined") {
    code = window.STORE_CURRENCY_CODE;
  }
  code = (code || "NGN").toUpperCase();
  return CURRENCY_SYMBOLS_MAP[code] || code;
}
window.getUserCurrencySymbol = getUserCurrencySymbol;

/** Django API origin. Set before this script: window.FLEZ_API_BASE = 'https://api.example.com' */
window.FLEZ_API_BASE = String(window.FLEZ_API_BASE || "").replace(/\/$/, "");
const FLEZ_API_BASE = window.FLEZ_API_BASE;

window.editProduct =
  window.editProduct ||
  ((id) => {
    const url = `/edit-product?id=${id}`;
    if (window.flezSwup) window.flezSwup.navigate(url);
    else window.location.href = url;
  });

window.copyToClipboard = (text, message = "Copied to clipboard!") => {
  if (!text) return;
  navigator.clipboard
    .writeText(text)
    .then(() => {
      if (window.showToast) window.showToast("Success", message, "success");
      else alert(message);
    })
    .catch((err) => {
      console.error("Could not copy text: ", err);
      if (window.showToast)
        window.showToast("Error", "Failed to copy", "error");
    });
};

/**
 * refreshUserData: Fetches fresh data from backend
 */
async function refreshUserData() {
  // Update last refresh timestamp to prevent redundant calls in initApp
  localStorage.setItem("last_data_refresh", Date.now().toString());
  try {
    const res = await apiFetch(`${FLEZ_API_BASE}/api/user/data`, {
      method: "POST",
    });
    const data = await res.json();
    if (data.status) {
      // apiFetch already saves to localStorage and calls renderUserData
      console.log("User data refreshed from backend");

      // Re-init current view stats if visible
      if (document.getElementById("dashboard-date-filter")) {
        initDashboardStats();
        initDashboardCharts();
      }
      if (document.getElementById("analyticsRevenueChart")) {
        initAnalyticsStats();
        initAnalyticsCharts();
      }
      if (document.getElementById("invoices-tbody")) initInvoices();
      if (document.getElementById("transactions-tbody")) initTransactions();
      if (document.getElementById("wallet-transactions-tbody")) initWallet();
    }
  } catch (err) {
    console.error("Failed to refresh user data:", err);
  }
}
window.refreshUserData = refreshUserData;

/**
 * SliverBar Logic (Shrinking Header)
 */
function initSliverBar() {
  const header = document.getElementById("sliver-header");
  const title = document.getElementById("sliver-title");
  const version = document.getElementById("sliver-version");
  const scrollable =
    document.querySelector("main .overflow-y-auto") ||
    document.querySelector("main");

  if (!header || !title || !scrollable) return;

  const handleScroll = () => {
    const scrollTop = scrollable.scrollTop;
    const isMobile = window.innerWidth < 1024;
    const maxScroll = isMobile ? 100 : 200;
    const progress = Math.min(scrollTop / maxScroll, 1);

    const baseHeight = isMobile ? 180 : 300;
    const targetHeight = 80;
    const currentHeight = baseHeight - (baseHeight - targetHeight) * progress;
    header.style.height = `${currentHeight}px`;

    const baseFontSize = isMobile ? 3 : 5;
    const targetFontSize = isMobile ? 1.2 : 1.5;
    const currentFontSize =
      baseFontSize - (baseFontSize - targetFontSize) * progress;
    title.style.fontSize = `${currentFontSize}rem`;

    if (version) {
      version.style.opacity = 1 - progress;
      version.style.transform = `translateY(${progress * 20}px)`;
      if (progress > 0.5) {
        version.style.display = "none";
      } else {
        version.style.display = "block";
      }
    }

    if (progress > 0.9) {
      header.classList.add(
        "bg-bg-sidebar/90",
        "backdrop-blur-xl",
        "shadow-2xl",
      );
      header.classList.remove("bg-transparent");
    } else {
      header.classList.remove(
        "bg-bg-sidebar/90",
        "backdrop-blur-xl",
        "shadow-2xl",
      );
      header.classList.add("bg-transparent");
    }
  };

  scrollable.addEventListener("scroll", handleScroll);
  window.addEventListener("resize", handleScroll);
  handleScroll();
}

window.switchRevenueChart = (type, btn, forceFilterVal) => {
  console.log(
    "[switchRevenueChart] Called with type:",
    type,
    "forceFilterVal:",
    forceFilterVal,
  );
  const rawData = localStorage.getItem("user_data");
  if (!rawData) {
    console.log("[switchRevenueChart] No user_data, returning");
    return;
  }
  const user = JSON.parse(rawData);
  const summary = user.sales_summary || {};

  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];

  let labels = [];
  let data = [];
  let label = "";
  let color = "#cfff45";
  let bg = "rgba(207, 255, 69, 0.12)";
  let chartType = "line"; // default

  // Dynamic Date Filtering Calculation
  let filterVal = forceFilterVal;
  if (!filterVal) {
    // Find visible select element in case of Swup cached elements
    const selects = document.querySelectorAll(
      'select[onchange*="handleDateFilterChange"]',
    );
    for (let s of selects) {
      if (s.offsetParent !== null) {
        filterVal = s.value;
        break;
      }
    }
  }
  if (!filterVal) filterVal = "year";

  const now = new Date();
  let startDate = new Date(0);
  let endDate = new Date();

  if (filterVal === "today") {
    startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  } else if (filterVal === "this_week") {
    startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  } else if (filterVal === "last_week") {
    startDate = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);
    endDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  } else if (filterVal === "this_month") {
    startDate = new Date(now.getFullYear(), now.getMonth(), 1);
  } else if (filterVal === "year") {
    startDate = new Date(now.getFullYear(), 0, 1);
  } else if (filterVal === "custom" && window.customDateRange) {
    startDate = new Date(window.customDateRange.start);
    endDate = new Date(window.customDateRange.end);
    endDate.setHours(23, 59, 59, 999);
  }

  const deptSales = {};
  const catSales = {};
  const itemSales = {};

  const itemMap = {};
  (user.items || []).forEach((item) => {
    itemMap[item.item_id] = {
      dept: item.item_department || "General",
      cat: item.item_category || "General",
    };
  });

  (user.invoice || []).forEach((inv) => {
    if (
      inv.invoice_status === "completed" ||
      inv.invoice_status === "success"
    ) {
      const invDate = new Date(inv.timestamp);
      if (invDate >= startDate && invDate <= endDate) {
        (inv.invoice_items || []).forEach((item) => {
          const amount =
            parseFloat(item.item_quantity) * parseFloat(item.item_amount);
          const mapped = itemMap[item.item_id] || {
            dept: "General",
            cat: "General",
          };
          deptSales[mapped.dept] = (deptSales[mapped.dept] || 0) + amount;
          catSales[mapped.cat] = (catSales[mapped.cat] || 0) + amount;
          itemSales[item.item_name] = (itemSales[item.item_name] || 0) + amount;
        });
      }
    }
  });

  if (type === "revenue") {
    if (filterVal === "today") {
      labels = ["12 AM", "4 AM", "8 AM", "12 PM", "4 PM", "8 PM", "11 PM"];
      data = [0, 0, 0, 0, 0, 0, 0];
      const todayStr = now.toISOString().split("T")[0];
      (user.invoice || []).forEach((inv) => {
        if (
          inv.invoice_status === "completed" ||
          inv.invoice_status === "success"
        ) {
          const invDate = new Date(inv.timestamp);
          if (invDate.toISOString().split("T")[0] === todayStr) {
            const hour = invDate.getHours();
            let bucket = 0;
            if (hour < 4) bucket = 0;
            else if (hour < 8) bucket = 1;
            else if (hour < 12) bucket = 2;
            else if (hour < 16) bucket = 3;
            else if (hour < 20) bucket = 4;
            else if (hour < 23) bucket = 5;
            else bucket = 6;
            const amt = (inv.invoice_items || []).reduce(
              (s, i) =>
                s + parseFloat(i.item_quantity) * parseFloat(i.item_amount),
              0,
            );
            for (let i = bucket; i < 7; i++) data[i] += amt;
          }
        }
      });
    } else if (filterVal === "this_week" || filterVal === "last_week") {
      const endD =
        filterVal === "this_week"
          ? now
          : new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      for (let i = 6; i >= 0; i--) {
        const d = new Date(endD);
        d.setDate(endD.getDate() - i);
        labels.push(d.toLocaleDateString(undefined, { weekday: "short" }));
        data.push(summary.daily_sales?.[d.toISOString().split("T")[0]] || 0);
      }
    } else if (filterVal === "this_month") {
      const daysInMonth = new Date(
        now.getFullYear(),
        now.getMonth() + 1,
        0,
      ).getDate();
      for (let i = 1; i <= daysInMonth; i++) {
        const d = new Date(now.getFullYear(), now.getMonth(), i);
        labels.push(i % 5 === 0 || i === 1 || i === daysInMonth ? i : "");
        data.push(summary.daily_sales?.[d.toISOString().split("T")[0]] || 0);
      }
    } else if (filterVal === "custom" && window.customDateRange) {
      // Build daily buckets between start and end date
      const customStart = new Date(window.customDateRange.start);
      const customEnd = new Date(window.customDateRange.end);
      customEnd.setHours(23, 59, 59, 999);
      const diffDays = Math.ceil(
        (customEnd - customStart) / (1000 * 60 * 60 * 24),
      );
      if (diffDays <= 31) {
        // Day-by-day
        for (let i = 0; i <= diffDays; i++) {
          const d = new Date(customStart);
          d.setDate(customStart.getDate() + i);
          const key = d.toISOString().split("T")[0];
          labels.push(
            d.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
          );
          data.push(summary.daily_sales?.[key] || 0);
        }
      } else {
        // Week-by-week buckets
        let cursor = new Date(customStart);
        while (cursor <= customEnd) {
          const weekEnd = new Date(cursor);
          weekEnd.setDate(cursor.getDate() + 6);
          let weekTotal = 0;
          for (
            let d = new Date(cursor);
            d <= weekEnd && d <= customEnd;
            d.setDate(d.getDate() + 1)
          ) {
            const key = d.toISOString().split("T")[0];
            weekTotal += summary.daily_sales?.[key] || 0;
          }
          labels.push(
            cursor.toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
            }),
          );
          data.push(weekTotal);
          cursor.setDate(cursor.getDate() + 7);
        }
      }
    } else {
      const months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
      ];
      labels = months;
      data = months.map((m) => (summary.monthly_sales || {})[m] || 0);
    }
    label = "Revenue";
    chartType = "line";
  } else if (type === "stocks") {
    const sortedItems = Object.entries(itemSales)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);
    labels = sortedItems.map((i) => i[0]);
    data = sortedItems.map((i) => i[1]);
    const curSym = getUserCurrencySymbol();
    label = `Sales (${curSym})`;
    color = "#3b82f6";
    bg = "rgba(59, 130, 246, 0.6)";
    chartType = "bar";
  } else if (type === "categories") {
    labels = Object.keys(catSales);
    data = Object.values(catSales);
    const curSym = getUserCurrencySymbol();
    label = `Category Sales (${curSym})`;
    color = "#a855f7";
    bg = "rgba(168, 85, 247, 0.6)";
    chartType = "bar";
  } else if (type === "departments") {
    labels = Object.keys(deptSales);
    data = Object.values(deptSales);
    const curSym = getUserCurrencySymbol();
    label = `Department Sales (${curSym})`;
    color = "#f97316";
    bg = "rgba(249, 115, 22, 0.6)";
    chartType = "bar";
  }

  // Fallback: if no data, show empty state instead of reverting to revenue
  if (!labels.length) {
    labels = ["No Data for Period"];
    data = [0];
  }

  console.log(
    "[switchRevenueChart] labels:",
    labels.length,
    "data:",
    data.length,
    "chartType:",
    chartType,
  );

  // Identify the active chart key and its canvas based on which canvas exists and is visible
  const analyticsCanvas = document.getElementById("analyticsRevenueChart");
  const dashboardCanvas = document.getElementById("revenueChart");

  let canvas = null;
  let chartKey = "revenue";

  if (analyticsCanvas && analyticsCanvas.offsetParent !== null) {
    canvas = analyticsCanvas;
    chartKey = "analyticsRev";
  } else if (dashboardCanvas && dashboardCanvas.offsetParent !== null) {
    canvas = dashboardCanvas;
    chartKey = "revenue";
  } else {
    canvas = analyticsCanvas || dashboardCanvas;
    chartKey = analyticsCanvas ? "analyticsRev" : "revenue";
  }

  console.log(
    "[switchRevenueChart] chartKey:",
    chartKey,
    "canvas found:",
    !!canvas,
  );
  if (!canvas) return;

  // Destroy and recreate — Chart.js cannot change type in-place
  if (window.flezCharts[chartKey]) {
    window.flezCharts[chartKey].destroy();
    window.flezCharts[chartKey] = null;
  }

  const isDark = document.documentElement.classList.contains("dark");
  const textColor = isDark ? "rgba(255,255,255,0.3)" : "rgba(15, 23, 42, 0.5)";
  const gridColor = isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)";

  const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: textColor, font: { size: 10 } },
      },
      y: {
        grid: { color: gridColor },
        ticks: { color: textColor, font: { size: 10 } },
      },
    },
  };

  const datasetBase = {
    label,
    data,
    borderColor: color,
    backgroundColor: bg,
    borderWidth: chartType === "line" ? 3 : 0,
  };
  if (chartType === "line") {
    Object.assign(datasetBase, { fill: true, tension: 0.4, pointRadius: 0 });
  } else {
    Object.assign(datasetBase, { borderRadius: 6, borderSkipped: false });
  }

  window.flezCharts[chartKey] = new Chart(canvas.getContext("2d"), {
    type: chartType,
    data: { labels, datasets: [datasetBase] },
    options: commonOptions,
  });
  console.log("[switchRevenueChart] Chart created successfully");

  // Update active tab styling — use data-type attribute for reliable matching
  document.querySelectorAll(".chart-tab").forEach((tab) => {
    const tabType =
      tab.dataset.type ||
      tab.getAttribute("onclick")?.match(/'([^']+)'/)?.[1] ||
      "";
    const isActive = tabType === type;
    if (isActive) {
      tab.classList.add(
        "active-tab",
        "bg-primary",
        "text-white",
        "shadow-lg",
        "shadow-primary/20",
      );
      tab.classList.remove("text-slate-500", "hover:text-white");
    } else {
      tab.classList.remove(
        "active-tab",
        "bg-primary",
        "text-white",
        "shadow-lg",
        "shadow-primary/20",
      );
      tab.classList.add("text-slate-500");
    }
  });

  if (typeof lucide !== "undefined") lucide.createIcons();
};
window.handleDateFilterChange = (select) => {
  console.log("[handleDateFilterChange] Called with value:", select.value);
  const activeTab = document.querySelector(".chart-tab.active-tab");
  let currentType = "revenue";
  if (activeTab) {
    currentType =
      activeTab.dataset.type ||
      activeTab.getAttribute("onclick")?.match(/'([^']+)'/)?.[1] ||
      "revenue";
  }

  if (select.value === "custom") {
    const modal = document.getElementById("dateModal");
    if (modal) modal.classList.remove("hidden");
    // Don't re-render yet — wait for applyCustomRange
    return;
  }

  // Clear any stale custom range when switching away from custom
  if (select.value !== "custom") {
    window.customDateRange = null;
  }

  // Re-render revenue/analytics chart
  if (typeof window.switchRevenueChart === "function") {
    window.switchRevenueChart(currentType, activeTab, select.value);
  }

  // Re-render category pie chart if on analytics page
  if (
    typeof window.initAnalyticsCategoryChart === "function" &&
    document.getElementById("analyticsCategoryChart")
  ) {
    window.initAnalyticsCategoryChart();
  }

  if (typeof window.updateAnalyticsStats === "function") {
    window.updateAnalyticsStats();
  }
};

window.closeDateModal = () => {
  const modal = document.getElementById("dateModal");
  if (modal) {
    modal.classList.add("hidden");
  }
};

window.applyCustomRange = () => {
  const start = document.getElementById("startDate").value;
  const end = document.getElementById("endDate").value;
  if (start && end) {
    window.customDateRange = { start, end };

    const activeTab = document.querySelector(".chart-tab.active-tab");
    let currentType = "revenue";
    if (activeTab) {
      currentType =
        activeTab.dataset.type ||
        activeTab.getAttribute("onclick")?.match(/'([^']+)'/)?.[1] ||
        "revenue";
    }
    if (typeof window.switchRevenueChart === "function") {
      window.switchRevenueChart(currentType, activeTab, "custom");
    }
    if (
      typeof window.initAnalyticsCategoryChart === "function" &&
      document.getElementById("analyticsCategoryChart")
    ) {
      window.initAnalyticsCategoryChart();
    }
    if (typeof window.updateAnalyticsStats === "function") {
      window.updateAnalyticsStats();
    }
    closeDateModal();
  } else {
    alert("Please select both start and end dates");
  }
};

// Global initialization function
function initApp() {
  console.log("Initializing Dashboard App...");

  if (typeof lucide !== "undefined") {
    lucide.createIcons();
  }

  // Refresh data if last refresh was > 1 min ago or not exists
  const now = Date.now();
  const lastRefresh = parseInt(
    localStorage.getItem("last_data_refresh") || "0",
  );
  if (now - lastRefresh > 60000) {
    localStorage.setItem("last_data_refresh", now.toString());
    refreshUserData();
  }

  if (document.getElementById("fund-modal")) initWallet();
  if (document.getElementById("staff-tbody")) initStaff();
  if (document.getElementById("managers-tbody")) initManagers();
  if (document.getElementById("departments-tbody")) initDepartments();
  if (document.getElementById("infinite-grid")) initProducts();
  if (document.getElementById("categories-grid")) initCategories();
  if (document.getElementById("sd-tabs")) initStaffDetails();
  if (
    document.getElementById("chat-messages") &&
    typeof initAiChat === "function"
  )
    initAiChat();
  if (document.getElementById("upload-step")) initImport();
  if (document.getElementById("items-container")) initInvoiceBuilder();
  if (document.querySelector(".tab-link")) initSettings();
  if (document.getElementById("dashboard-date-filter")) {
    initDashboardStats();
    initDashboardCharts();
  }
  if (document.getElementById("analyticsRevenueChart")) {
    initAnalyticsStats();
    initAnalyticsCharts();
  }
  if (document.getElementById("invoices-tbody")) initInvoices();
  if (document.getElementById("transactions-tbody")) initTransactions();
  if (document.getElementById("wallet-transactions-tbody")) initWallet();
  if (document.getElementById("store-grid")) initStore();
  if (
    document.getElementById("edit-product-page") &&
    typeof initEditPage === "function"
  )
    initEditPage();
  if (
    document.getElementById("edit-employee-page") &&
    typeof window.initEditEmployee === "function"
  )
    window.initEditEmployee();

  if (document.getElementById("templates-grid")) initStoreLayouts();
  if (document.getElementById("download-dropdown-menu")) initPosDownload();
  if (document.getElementById("buyKitDrawer") && typeof window.initPOS === "function") {
    window.initPOS();
  }
  if (
    document.getElementById("m-department") &&
    typeof window.populateDepartments === "function"
  ) {
    window.populateDepartments("m-department");
  }
  if (document.getElementById("p-category")) {
    // Only auto-populate if NOT the edit/add product pages (which have their own init)
    if (
      !document.getElementById("edit-product-page") &&
      !document.getElementById("items-count") &&
      typeof window.populateCategories === "function"
    ) {
      window.populateCategories("p-category");
    }
    if (typeof window.initPage === "function") window.initPage();
  }
  if (document.getElementById("edit-product-page")) {
    if (typeof window.initEditPage === "function") window.initEditPage();
  }
  if (document.getElementById("store-setup-form")) {
    if (typeof initStoreWizard === "function") initStoreWizard();
  }
  if (document.getElementById("create-employee-page")) {
    if (typeof window.initCreateEmployee === "function")
      window.initCreateEmployee();
  }
  if (document.getElementById("tax-credit-page")) {
    if (typeof window.initTaxCreditPage === "function")
      window.initTaxCreditPage();
  }
  if (
    document.getElementById("verification-container") ||
    document.getElementById("verification-status-banner") ||
    document.getElementById("verification-form")
  ) {
    if (typeof window.initVerificationPage === "function")
      window.initVerificationPage();
  }
  if (
    document.getElementById("reportsChart") &&
    typeof window.initGrowthReports === "function"
  ) {
    window.initGrowthReports();
  }
  if (
    document.getElementById("articles-table-body") &&
    typeof window.initBlogPage === "function"
  ) {
    window.initBlogPage();
  }
  if (
    (document.getElementById("currentDomainStatus") ||
      document.getElementById("searchDomainBtn")) &&
    typeof window.initDomainManagement === "function"
  ) {
    window.initDomainManagement();
  }

  // Attach hours toggle logic universally
  document.querySelectorAll(".hours-switch").forEach((sw) => {
    if (sw.dataset.initHours) return;
    sw.dataset.initHours = "1";
    sw.addEventListener("click", function (e) {
      e.preventDefault();
      const isChecked = this.getAttribute("aria-checked") === "true";
      this.setAttribute("aria-checked", !isChecked);
      const row = this.closest(".group");
      if (row) {
        const inputs = row.querySelector(".hours-inputs");
        if (!isChecked) {
          row.classList.remove("opacity-70");
          if (inputs)
            inputs.classList.remove("pointer-events-none", "opacity-50");
        } else {
          row.classList.add("opacity-70");
          if (inputs) inputs.classList.add("pointer-events-none", "opacity-50");
        }
      }
    });
  });

  // Attach publish logic universally
  const pubBtn = document.getElementById("settings-store-publish-btn");
  if (pubBtn && !pubBtn.dataset.initPub) {
    pubBtn.dataset.initPub = "1";
    pubBtn.addEventListener("click", function (e) {
      e.preventDefault();
      const isPub = this.textContent.includes("Unpublish");
      if (!isPub) {
        this.textContent = "Unpublish Store";
        this.classList.remove(
          "bg-primary",
          "text-bg-dark",
          "hover:bg-primary/90",
          "shadow-primary/20",
        );
        this.classList.add(
          "bg-rose-500/10",
          "text-rose-500",
          "border",
          "border-rose-500/20",
          "hover:bg-rose-500/20",
        );
      } else {
        this.textContent = "Publish Store";
        this.classList.add(
          "bg-primary",
          "text-bg-dark",
          "hover:bg-primary/90",
          "shadow-primary/20",
        );
        this.classList.remove(
          "bg-rose-500/10",
          "text-rose-500",
          "border",
          "border-rose-500/20",
          "hover:bg-rose-500/20",
        );
      }
    });
  }

  window.switchStoreView = (view) => {
    const grid = document.getElementById("store-grid");
    const list = document.getElementById("store-list-view");
    const gridBtn = document.getElementById("view-grid");
    const listBtn = document.getElementById("view-list");

    if (!grid || !list) return;

    if (view === "grid") {
      grid.classList.remove("hidden");
      list.classList.add("hidden");
      gridBtn.classList.add("text-primary", "bg-primary/10");
      gridBtn.classList.remove("text-slate-400");
      listBtn.classList.remove("text-primary", "bg-primary/10");
      listBtn.classList.add("text-slate-400");
    } else {
      grid.classList.add("hidden");
      list.classList.remove("hidden");
      gridBtn.classList.remove("text-primary", "bg-primary/10");
      gridBtn.classList.add("text-slate-400");
      listBtn.classList.add("text-primary", "bg-primary/10");
      listBtn.classList.remove("text-slate-400");
      renderStoreList();
    }
  };

  // Page-specific initializations
  if (
    document.getElementById("payroll-tbody") ||
    document.getElementById("payroll-form")
  ) {
    if (typeof initPayroll === "function") initPayroll();
  }
  if (
    document.getElementById("settings-content-container") ||
    document.getElementById("save-settings")
  ) {
    if (typeof window.initSettingsPage === "function")
      window.initSettingsPage();
  }
  if (
    document.getElementById("profile-content-container") ||
    document.getElementById("save-profile")
  ) {
    if (typeof window.initProfilePage === "function") window.initProfilePage();
  }
  if (document.getElementById("store-settings-container")) {
    if (typeof initStoreSettings === "function") initStoreSettings();
  }
  if (document.getElementById("chats-list")) {
    if (typeof window.initLivechat === "function") window.initLivechat();
    if (typeof window.checkLivechatStatus === "function")
      window.checkLivechatStatus();
  }

  // Re-bind theme toggle (the button is inside #swup, so it's replaced on navigation)
  initTheme();

  // Re-bind sidebar mobile toggle (the #sidebar-toggle button is inside #swup header)
  if (window.SidebarComponent) {
    window.SidebarComponent.initMobileToggle();
  }

  renderUserData();
}

/**
 * switchOrgTab — toggles between the Categories / Staff / Managers / Departments
 * tabs on the Organization page. Called by onclick attributes in organization.html.
 */
window.switchOrgTab = function (tabName) {
  // Hide all panes
  document.querySelectorAll(".org-tab-pane").forEach((pane) => {
    pane.style.display = "none";
  });

  // Show the target pane
  const target = document.getElementById(`tab-${tabName}`);
  if (target) {
    target.style.display = "block";
    target.style.animation = "none";
    // Force reflow so the animation restarts cleanly
    void target.offsetWidth;
    target.style.animation = "modalPop 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)";
  }

  // Update button active states
  document.querySelectorAll(".org-tab-btn").forEach((btn) => {
    btn.classList.remove("active");
  });
  const activeBtn = document.getElementById(`btn-tab-${tabName}`);
  if (activeBtn) activeBtn.classList.add("active");
};

/**
 * renderUserData: Populates the UI with details of the logged-in user.
 */
function renderUserData() {
  const rawData = localStorage.getItem("user_data");
  if (!rawData) return;

  try {
    const user = JSON.parse(rawData);
    const details = user.details?.[0] || {};
    const fullName =
      `${details.first_name || ""} ${details.last_name || ""}`.trim() || "User";
    const firstName = details.first_name || "User";
    const initials =
      (
        (details.first_name?.[0] || "") + (details.last_name?.[0] || "")
      ).toUpperCase() || "U";

    // Update all instances of the full name
    document.querySelectorAll("p, span, h4").forEach((el) => {
      if (el.textContent.trim() === "James Flez") {
        el.textContent = fullName;
      }
    });

    // Update greeting
    document.querySelectorAll("h1").forEach((el) => {
      if (el.textContent.includes("Welcome back, James!")) {
        el.textContent = `Welcome back, ${firstName}!`;
      }
      if (
        el.textContent.includes("Hello, James!") ||
        el.id === "dashboard-user-greeting"
      ) {
        el.textContent = `Hello, ${firstName}!`;
      }
    });

    // Check manager permissions for finances & payroll
    const isFinancesMasked = !!(
      user.finances_masked ||
      (user.manager_account && user.manager_account.manage_finances === false)
    );
    const isPayrollMasked = !!(
      user.payroll_masked ||
      (user.manager_account && user.manager_account.manage_payroll === false)
    );

    // Update Balance & Stats (Global)
    const balEls = document.querySelectorAll(
      "#stat-wallet-balance, #header-wallet-balance, #wallet-balance-main",
    );
    if (isFinancesMasked) {
      balEls.forEach((el) => {
        if (el.id === "header-wallet-balance")
          el.textContent = "Balance: ••••••";
        else el.textContent = "••••••";
      });
      const walletActionDiv = document
        .querySelector("#stat-wallet-balance")
        ?.closest(".p-4, .p-5")
        ?.querySelector(".flex.gap-2, .flex.items-center.gap-1");
      if (walletActionDiv) {
        walletActionDiv.className =
          "flex items-center gap-1 text-[11px] text-slate-500 font-semibold";
        walletActionDiv.innerHTML = `<i data-lucide="lock" class="w-3 h-3"></i> Restricted`;
        if (typeof lucide !== "undefined") lucide.createIcons();
      }
    } else {
      const balance = user.balance || 0;
      const curSym = getUserCurrencySymbol(user);
      const formattedBalance = `${curSym}${balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

      balEls.forEach((el) => {
        if (el.id === "header-wallet-balance")
          el.textContent = `Balance: ${formattedBalance}`;
        else if (el.id === "wallet-balance-main")
          el.innerHTML = `${curSym}${Math.floor(balance).toLocaleString()}<span class="text-2xl text-slate-500">.${(balance % 1).toFixed(2).split(".")[1]}</span>`;
        else el.textContent = formattedBalance;
      });
    }

    if (isPayrollMasked) {
      const activeStaffEl = document.getElementById("stat-active-staff");
      if (activeStaffEl) activeStaffEl.textContent = "••••••";
    }

    // Store Name & Status Update
    const business = user.business_details?.[0];
    if (business) {
      const bName = business.business_name || business.store_name || "My Store";

      // 1. Update by ID
      const storeTitle = document.getElementById("store-display-name");
      if (storeTitle) storeTitle.textContent = bName;

      const storeViews = document.getElementById("store-views-count");
      if (storeViews)
        storeViews.textContent = (business.store_views || 0).toLocaleString();

      // 2. Update by text matching (catch-all for other instances)
      document.querySelectorAll("h1, h2, h3, h4, p, span").forEach((el) => {
        if (el.textContent.trim() === "My Store") {
          el.textContent = bName;
        }
      });

      // 3. Custom domain banner on store page
      const customDomainBanner = document.getElementById("customDomainBanner");
      if (customDomainBanner) {
        if (business.store_custom_domain) {
          customDomainBanner.classList.add("hidden");
        } else {
          customDomainBanner.classList.remove("hidden");
        }
      }

      // 4. Custom domain status on domain management page
      if (typeof window.updateDomainStatusUI === "function") {
        window.updateDomainStatusUI(business);
      }
    }

    // Update initials and other common placeholders
    document.querySelectorAll("div, span, p, h1, h4").forEach((el) => {
      const text = el.textContent.trim();
      if (text === "JF" && el.children.length === 0) {
        const userAvatar = details.user_avatar;
        if (userAvatar) {
          el.innerHTML = `<img src="${userAvatar}" class="w-full h-full object-cover">`;
          el.classList.add("overflow-hidden");
        } else if (business && business.business_image) {
          el.innerHTML = `<img src="${business.business_image}" class="w-full h-full object-cover">`;
          el.classList.add("overflow-hidden");
        } else {
          el.textContent = initials;
        }
      }
      if (text === "James Flez" && el.children.length === 0)
        el.textContent = fullName;
      if (text.includes("Welcome back, James!") && el.children.length === 0)
        el.textContent = `Welcome back, ${firstName}!`;
      if (text.includes("Hello, James!") && el.children.length === 0)
        el.textContent = `Hello, ${firstName}!`;
    });
  } catch (e) {
    console.error("Failed to render user data:", e);
  }
}

/**
 * Theme Management
 */
function initTheme() {
  const themeToggle = document.getElementById("theme-toggle");
  const html = document.documentElement;

  const savedTheme = localStorage.getItem("theme") || "dark";
  html.classList.remove("light", "dark");
  html.classList.add(savedTheme);
  updateThemeIcon(savedTheme);
  injectGlobalThemeStyles();

  if (themeToggle) {
    themeToggle.onclick = (e) => {
      if (e) e.preventDefault();
      const currentTheme = html.classList.contains("dark") ? "light" : "dark";
      html.classList.remove("light", "dark");
      html.classList.add(currentTheme);
      localStorage.setItem("theme", currentTheme);
      updateThemeIcon(currentTheme);
      injectGlobalThemeStyles();

      // Re-render charts for theme responsiveness
      if (
        window.location.pathname === "/dashboard" ||
        window.location.pathname === "/"
      ) {
        if (typeof initDashboardCharts === "function") initDashboardCharts();
      } else if (window.location.pathname.startsWith("/analytics")) {
        if (typeof initAnalyticsCharts === "function") initAnalyticsCharts();
      }
    };
  }
}

function injectGlobalThemeStyles() {
  let style = document.getElementById("theme-overrides");
  if (!style) {
    style = document.createElement("style");
    style.id = "theme-overrides";
    document.head.appendChild(style);
  }
  style.innerHTML = `
        html.light body { background-color: #f8fafc !important; color: #1e293b !important; }
        html.light {
            --swal-bg: #ffffff;
            --swal-text: #0f172a;
        }
        html.dark {
            --swal-bg: #13151a;
            --swal-text: #ffffff;
        }
        html.light .bg-bg-dark { background-color: #f8fafc !important; }

        html.light .bg-bg-sidebar { background-color: #ffffff !important; border-right-color: rgba(0,0,0,0.1) !important; }
        html.light .bg-bg-card { background-color: #ffffff !important; border-color: rgba(0,0,0,0.05) !important; }
        html.light .glass-card { background: rgba(255, 255, 255, 0.7) !important; border-color: rgba(0, 0, 0, 0.05) !important; backdrop-filter: blur(10px); }
        html.light .text-white { color: #0f172a !important; }
        html.light .text-slate-200 { color: #1e293b !important; }
        html.light .text-slate-400 { color: #475569 !important; }
        html.light .text-slate-500 { color: #64748b !important; }
        html.light .border-white\\/5, html.light .border-white\\/10 { border-color: rgba(0, 0, 0, 0.08) !important; }
        html.light header { background-color: rgba(255, 255, 255, 0.8) !important; border-bottom-color: rgba(0, 0, 0, 0.08) !important; }
        html.light .sidebar-link:not(.active) { color: #64748b !important; }
        html.light .sidebar-link:not(.active):hover { background-color: rgba(0, 0, 0, 0.03) !important; color: #0f172a !important; }
        
        /* Unified Input Styling for Theme Consistency */
        html.light input, html.light select, html.light textarea { 
            background-color: #ffffff !important; 
            color: #0f172a !important; 
            border: 1px solid rgba(0, 0, 0, 0.1) !important; 
        }
        html.dark input, html.dark select, html.dark textarea { 
            background-color: rgba(255, 255, 255, 0.05) !important; 
            color: #ffffff !important; 
            border: 1px solid rgba(255, 255, 255, 0.1) !important; 
        }
        html.light input:focus, html.light select:focus, html.light textarea:focus {
            border-color: #29594b !important;
            outline: none !important;
            box-shadow: 0 0 0 4px rgba(41, 89, 75, 0.15) !important;
        }
        html.dark input:focus, html.dark select:focus, html.dark textarea:focus {
            border-color: #cfff45 !important;
            outline: none !important;
            box-shadow: 0 0 0 4px rgba(207, 255, 69, 0.25) !important;
        }

        html.light .bg-white\\/5 { background-color: rgba(0, 0, 0, 0.03) !important; }
        html.light .text-slate-300 { color: #334155 !important; }
        html.light .bg-white\\/10 { background-color: rgba(0, 0, 0, 0.06) !important; }
        html.light .bg-bg-card\\/95 { background-color: rgba(255, 255, 255, 0.95) !important; }
        html.light .bg-bg-sidebar\\/90 { background-color: rgba(255, 255, 255, 0.9) !important; }
        html.light .bg-primary\\/20 { background-color: rgba(207, 255, 69, 0.12) !important; }
        
        /* Light Theme & White Parent Contrast Protection for Primary Text, Icons, and Borders */
        html.light .text-primary,
        html.light [class*="text-[#cfff45]"] {
            color: #29594b !important;
        }
        html.light svg.text-primary,
        html.light i.text-primary,
        html.light [data-lucide].text-primary,
        html.light .text-primary svg,
        html.light .text-primary i,
        html.light .text-primary [data-lucide],
        html.light svg[stroke="#cfff45"],
        html.light [stroke="#cfff45"] {
            color: #29594b !important;
            stroke: #29594b !important;
        }
        html.light .hover\:text-primary:hover,
        html.light a.text-primary:hover,
        html.light button.text-primary:hover,
        html.light .group:hover .group-hover\:text-primary {
            color: #19352d !important;
        }
        html.light .border-primary,
        html.light .border-t-primary,
        html.light .border-b-primary,
        html.light .border-r-primary,
        html.light .border-l-primary {
            border-color: #29594b !important;
        }
        html.light .focus\:border-primary:focus {
            border-color: #29594b !important;
        }
        html.light .shadow-primary\/20,
        html.light .shadow-primary\/10 {
            box-shadow: 0 4px 14px 0 rgba(41, 89, 75, 0.15) !important;
        }

        /* Context-Aware White & Light Surface Parent Element Contrast */
        .bg-white .text-primary,
        .bg-white [class*="text-[#cfff45]"],
        [class*="bg-white"] .text-primary,
        [class*="bg-white"] [class*="text-[#cfff45]"],
        .bg-slate-50 .text-primary,
        .bg-gray-50 .text-primary {
            color: #29594b !important;
        }
        .bg-white svg.text-primary,
        .bg-white i.text-primary,
        .bg-white [data-lucide].text-primary,
        .bg-white .text-primary svg,
        .bg-white .text-primary i,
        .bg-white .text-primary [data-lucide],
        [class*="bg-white"] svg.text-primary,
        [class*="bg-white"] i.text-primary,
        [class*="bg-white"] [data-lucide].text-primary,
        [class*="bg-white"] .text-primary svg,
        [class*="bg-white"] .text-primary i,
        .bg-white svg[stroke="#cfff45"],
        .bg-white [stroke="#cfff45"],
        [class*="bg-white"] svg[stroke="#cfff45"],
        [class*="bg-white"] [stroke="#cfff45"] {
            color: #29594b !important;
            stroke: #29594b !important;
        }
        .bg-white .border-primary,
        [class*="bg-white"] .border-primary {
            border-color: #29594b !important;
        }
        .bg-white .hover\:text-primary:hover,
        [class*="bg-white"] .hover\:text-primary:hover {
            color: #19352d !important;
        }

        /* Active Tabs & Component Indicators in Light Mode */
        html.light .tab-link.active,
        html.light .tab-link.active .tab-active-icon,
        html.light .tab-link.active .tab-lead-icon,
        html.light .sd-tab.active,
        html.light .org-tab-btn.active,
        html.light .img-tab-btn.active {
            color: #29594b !important;
            border-color: #29594b !important;
        }
        html.light .settings-tab.active {
            border-left-color: #29594b !important;
            border-bottom-color: #29594b !important;
            background-color: rgba(41, 89, 75, 0.08) !important;
        }
        html.light .ai-typing-cursor::after {
            color: #29594b !important;
        }
        html.light #select-all-products:checked,
        html.light .product-select:checked {
            border-color: #29594b !important;
            background-color: #29594b !important;
        }
        html.light #gauge-progress-circle,
        html.light #tc-credit-gauge-arc {
            stroke: #29594b !important;
        }
        
        /* Switch Toggle Component - Unified High-Definition Thick Border */
        .switch { 
            position: relative; 
            display: inline-flex; 
            height: 1.25rem; 
            width: 2.25rem; 
            flex-shrink: 0; 
            cursor: pointer; 
            align-items: center; 
            border-radius: 9999px; 
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); 
            background-color: rgba(255, 255, 255, 0.08); 
            border: 2px solid rgba(255, 255, 255, 0.35) !important;
            box-sizing: border-box;
            outline: none;
        }
        html.light .switch {
            border-color: #94a3b8 !important;
            background-color: #cbd5e1 !important;
        }
        html.dark .switch[aria-checked="true"],
        .switch[aria-checked="true"] { 
            background-color: #cfff45 !important; 
            border-color: #a3e635 !important;
        }
        html.light .switch[aria-checked="true"] { 
            background-color: #29594b !important; 
            border-color: #1e3f35 !important;
        }
        .switch-thumb,
        .switch span:not(.sr-only) { 
            pointer-events: none; 
            display: block; 
            height: 0.875rem !important; 
            width: 0.875rem !important; 
            border-radius: 9999px; 
            background-color: #ffffff !important; 
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.25); 
            transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            transform: translateX(0.0625rem);
        }
        .switch[aria-checked="true"] .switch-thumb,
        .switch[aria-checked="true"] span:not(.sr-only) { 
            transform: translateX(1.0625rem) !important; 
        }
        
        /* Sidebar Active Link Styles - Signature brand lime background */
        .sidebar-link.active,
        html.light .sidebar-link.active,
        html.dark .sidebar-link.active,
        #sidebar .sidebar-link.active {
            background-color: #cfff45 !important;
            color: #000000 !important;
            font-weight: 700 !important;
            border: none !important;
            box-shadow: 0 4px 14px 0 rgba(0, 0, 0, 0.2) !important;
        }
        .sidebar-link.active i,
        .sidebar-link.active svg,
        .sidebar-link.active span,
        html.light .sidebar-link.active i,
        html.light .sidebar-link.active svg,
        html.light .sidebar-link.active span,
        html.dark .sidebar-link.active i,
        html.dark .sidebar-link.active svg,
        html.dark .sidebar-link.active span,
        #sidebar .sidebar-link.active i,
        #sidebar .sidebar-link.active svg,
        #sidebar .sidebar-link.active span {
            color: #000000 !important;
            stroke: #000000 !important;
        }

        /* SweetAlert Theme Overrides */
        .swal2-popup {
            background: #ffffff !important;
            color: #0f172a !important;
            border-radius: 24px !important;
        }
        .swal2-title, .swal2-html-container {
            color: #0f172a !important;
        }
        html.dark .swal2-popup {
            background: #13151a !important;
            color: #ffffff !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
        }
        html.dark .swal2-title, html.dark .swal2-html-container {
            color: #ffffff !important;
        }
        .swal2-confirm {
            border-radius: 12px !important;
        }
        .swal2-cancel {
            border-radius: 12px !important;
        }
        
        /* Toast Specific Overrides */
        .swal2-popup.swal2-toast {
            background-color: #ffffff !important;
            color: #0f172a !important;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1) !important;
        }
        html.dark .swal2-popup.swal2-toast {
            background-color: #1e293b !important;
            color: #ffffff !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            box-shadow: 0 10px 40px rgba(0,0,0,0.4) !important;
        }
        .swal2-popup.swal2-toast .swal2-title, 
        .swal2-popup.swal2-toast .swal2-html-container {
            color: inherit !important;
        }

    `;
}

function updateThemeIcon(theme) {
  const iconContainer = document.getElementById("theme-toggle");
  if (!iconContainer) return;

  if (theme === "light") {
    iconContainer.innerHTML = '<i data-lucide="moon" class="w-5 h-5"></i>';
  } else {
    iconContainer.innerHTML = '<i data-lucide="sun" class="w-5 h-5"></i>';
  }
  if (typeof lucide !== "undefined") lucide.createIcons();
}

/**
 * Products Micro Badges Helper
 * Formats high-contrast, compact, modern pill badges with micro-icons
 */
function formatProductMicroBadges(isDigital, isPromo, promoVal) {
  let promoText = "Promo";
  if (promoVal) {
    const num = parseFloat(promoVal);
    promoText = !isNaN(num) ? `${num}% OFF` : String(promoVal);
  }

  const digitalBadge = isDigital
    ? `<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[9.5px] font-bold leading-none bg-sky-50 dark:bg-sky-500/15 text-sky-700 dark:text-sky-300 border border-sky-300/80 dark:border-sky-500/30 shadow-xs shrink-0" title="Digital Download - Instant Delivery"><i data-lucide="download" class="w-2.5 h-2.5 stroke-[2.5] shrink-0"></i><span>Digital</span></span>`
    : "";
  const promoBadge = isPromo
    ? `<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[9.5px] font-bold leading-none bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-300/80 dark:border-amber-500/30 shadow-xs shrink-0" title="Promotional Item"><i data-lucide="percent" class="w-2.5 h-2.5 stroke-[2.5] shrink-0"></i><span>${promoText}</span></span>`
    : "";

  return { digitalBadge, promoBadge };
}

/**
 * Products Page Logic
 */
function initProducts() {
  const grid = document.getElementById("infinite-grid");
  const listBody = document.getElementById("product-list-body");
  const scrollContainer =
    document.querySelector("#swup .overflow-y-auto") ||
    document.querySelector("main .overflow-y-auto");
  const loader = document.getElementById("grid-loader");
  const scrollSentinel = document.getElementById("grid-scroll-sentinel");

  if (!grid) return;

  // State
  let currentPage = 1;
  let totalPages = 1;
  let isLoading = false;
  let hasMore = true;
  let activeView = "grid";
  let searchQuery = "";
  const gridPerPage = 20;
  const listPerPage = 15;
  let lastPagination = {};
  let productCurrencySymbol = window.getUserCurrencySymbol
    ? window.getUserCurrencySymbol()
    : window.STORE_CURRENCY_SYMBOL || "₦";

  if (window._productsGridObserver) {
    window._productsGridObserver.disconnect();
    window._productsGridObserver = null;
  }

  window.switchProductView = (view) => {
    activeView = view;
    currentPage = 1;
    hasMore = true;
    if (view === "grid") {
      document.getElementById("product-grid-view")?.classList.remove("hidden");
      document.getElementById("product-list-view")?.classList.add("hidden");
      document
        .getElementById("view-grid")
        ?.classList.add("text-primary", "bg-primary/10");
      document.getElementById("view-grid")?.classList.remove("text-slate-400");
      document
        .getElementById("view-list")
        ?.classList.remove("text-primary", "bg-primary/10");
      document.getElementById("view-list")?.classList.add("text-slate-400");
      grid.innerHTML = "";
      fetchProducts(false, 1);
    } else {
      document.getElementById("product-grid-view")?.classList.add("hidden");
      document.getElementById("product-list-view")?.classList.remove("hidden");
      document
        .getElementById("view-grid")
        ?.classList.remove("text-primary", "bg-primary/10");
      document.getElementById("view-grid")?.classList.add("text-slate-400");
      document
        .getElementById("view-list")
        ?.classList.add("text-primary", "bg-primary/10");
      document.getElementById("view-list")?.classList.remove("text-slate-400");
      fetchProducts(false, 1);
    }
  };

  async function fetchProducts(append = false, pageNum = null) {
    const pageToFetch = pageNum ?? currentPage;
    if (isLoading) return;
    if (append && !hasMore) return;

    isLoading = true;
    if (activeView === "grid") loader?.classList.remove("hidden");

    try {
      const res = await apiFetch(
        `${window.FLEZ_API_BASE}/api/products/filter`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            page: pageToFetch,
            per_page: activeView === "list" ? listPerPage : gridPerPage,
            search: searchQuery,
          }),
        },
      );
      const result = await res.json();

      if (result.status) {
        const items = result.data || [];
        const pagination = result.pagination || {};
        currentPage = pagination.current_page || pageToFetch;
        totalPages = pagination.total_pages || 1;
        hasMore = !!pagination.has_next;
        lastPagination = pagination;

        if (result.metrics) {
          if (result.metrics.currency)
            productCurrencySymbol = result.metrics.currency;
          renderProductMetrics(result.metrics);
        }
        if (result.low_stock_items !== undefined) {
          renderLowStockAlerts(result.low_stock_items);
        }
        renderProducts(items, append);
        updatePaginationUI(pagination);
      }
    } catch (err) {
      console.error("fetchProducts:", err);
    } finally {
      isLoading = false;
      loader?.classList.add("hidden");
    }
  }

  function loadMoreGrid() {
    if (activeView !== "grid" || isLoading || !hasMore) return;
    fetchProducts(true, currentPage + 1);
  }

  function renderProducts(items, append = false) {
    if (!grid) return;

    if (!append) {
      if (activeView === "grid") grid.innerHTML = "";
      if (listBody && activeView === "list") listBody.innerHTML = "";
    }

    if (!Array.isArray(items) || items.length === 0) {
      if (!append) {
        if (activeView === "grid") {
          grid.innerHTML =
            '<div class="col-span-full py-20 text-center text-slate-500">No products found.</div>';
        } else if (listBody) {
          listBody.innerHTML =
            '<tr><td colspan="6" class="py-20 text-center text-slate-500">No products found.</td></tr>';
        }
      }
      return;
    }

    const html = items.map((p) => {
      const price = Number(p.item_amount).toLocaleString();
      const stock = Number(p.item_quantity);
      const isDigital = !!(
        p.is_digital ||
        p.digital_file ||
        p.digital_file_url
      );
      const isPromo = !!(p.is_promo || p.promo_amount || p.promo_percentage);
      const promoVal = p.promo_amount || p.promo_percentage;

      const stockBadge = !isDigital
        ? `<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[8px] font-bold ${stock <= 5 ? "bg-rose-500/90 border-rose-400/40" : "bg-emerald-500/90 border-emerald-400/40"} text-white shadow-sm backdrop-blur-xs border"><i data-lucide="${stock <= 5 ? "alert-circle" : "check"}" class="w-2.5 h-2.5 stroke-[2.5]"></i>${stock <= 5 ? "Low Stock" : "In Stock"}</span>`
        : "";

      const { digitalBadge: digitalMicroBadge, promoBadge: promoMicroBadge } =
        formatProductMicroBadges(isDigital, isPromo, promoVal);

      // Grid Item
      const gridItem = `
                <div class="glass-card p-4 rounded-3xl group transition-all hover:border-primary/30 animate-fade-in relative flex flex-col justify-between">
                    <div>
                        <div class="relative aspect-square bg-white/5 rounded-2xl mb-4 overflow-hidden flex items-center justify-center">
                            <div class="absolute top-2 left-2 z-10">
                                <input type="checkbox" data-id="${p.item_id}" class="product-select w-5 h-5 rounded-lg border-2 border-slate-400 dark:border-white/20 bg-white/90 dark:bg-black/40 text-primary focus:ring-offset-0 focus:ring-primary checked:bg-primary checked:border-primary transition-all cursor-pointer appearance-none checked:after:content-['✓'] checked:after:flex checked:after:items-center checked:after:justify-center checked:after:text-slate-900 dark:checked:after:text-white checked:after:text-[10px] checked:after:font-bold">
                            </div>
                            ${
                              p.images && p.images.length > 0
                                ? `<img src="${p.images[0].image}" class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500">`
                                : `<i data-lucide="box" class="w-12 h-12 text-slate-700 group-hover:scale-110 transition-transform"></i>`
                            }
                            ${
                              stockBadge
                                ? `
                            <div class="absolute top-2 right-2 z-10 pointer-events-none">
                                ${stockBadge}
                            </div>`
                                : ""
                            }
                        </div>
                        <h4 class="text-sm font-bold text-white mb-1 truncate">${p.item_name}</h4>
                        ${
                          isDigital || isPromo
                            ? `
                        <div class="flex items-center flex-wrap gap-1.5 mb-1.5">
                            ${digitalMicroBadge}
                            ${promoMicroBadge}
                        </div>`
                            : ""
                        }
                        <p class="text-[10px] text-slate-500 mb-3">${p.item_department || "General"} • ${isDigital ? "Instant Delivery" : stock + " units"}</p>
                    </div>
                    <div class="flex items-center justify-between pt-3 border-t border-white/5 mt-auto">
                        <p class="text-sm font-bold text-primary">${productCurrencySymbol}${price}</p>
                        <div class="relative dropdown-container">
                            <button type="button" class="p-1.5 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-all dropdown-toggle" title="Options">
                                <i data-lucide="more-vertical" class="w-4 h-4 pointer-events-none"></i>
                            </button>
                            <div class="dropdown-menu absolute right-0 bottom-full mb-2 w-32 bg-white dark:bg-[#151922] border border-slate-200 dark:border-white/10 rounded-xl shadow-xl py-1.5 z-50 text-left">
                                <button type="button" class="w-full text-left px-3.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2 transition-colors" onclick="editProduct('${p.item_id}')">
                                    <i data-lucide="edit-3" class="w-3.5 h-3.5"></i> Edit
                                </button>
                                <button type="button" class="w-full text-left px-3.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2 transition-colors" onclick="printProductQR('${p.item_id}')">
                                    <i data-lucide="qr-code" class="w-3.5 h-3.5"></i> QR Code
                                </button>
                                <button type="button" class="w-full text-left px-3.5 py-2 text-xs font-semibold text-rose-500 hover:bg-rose-500/10 flex items-center gap-2 transition-colors" onclick="deleteProduct('${p.item_id}')">
                                    <i data-lucide="trash-2" class="w-3.5 h-3.5"></i> Delete
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

      // List Item
      const listItem = `
                <tr class="group hover:bg-white/5 transition-all text-sm">
                    <td class="px-6 py-4">
                        <div class="p-1">
                            <input type="checkbox" data-id="${p.item_id}" class="product-select w-5 h-5 rounded-lg border-2 border-slate-400 dark:border-white/20 bg-white/90 dark:bg-black/40 text-primary focus:ring-offset-0 focus:ring-primary checked:bg-primary checked:border-primary transition-all cursor-pointer appearance-none checked:after:content-['✓'] checked:after:flex checked:after:items-center checked:after:justify-center checked:after:text-slate-900 dark:checked:after:text-white checked:after:text-[10px] checked:after:font-bold">
                        </div>
                    </td>
                    <td class="px-6 py-4">
                        <div class="flex items-center gap-3 min-w-0">
                            <div class="w-10 h-10 shrink-0 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-slate-500 overflow-hidden">
                                ${
                                  p.images && p.images.length > 0
                                    ? `<img src="${p.images[0].image}" alt="" class="w-full h-full object-cover">`
                                    : `<i data-lucide="box" class="w-4 h-4"></i>`
                                }
                            </div>
                            <div class="min-w-0">
                                <div class="flex items-center gap-1.5 flex-wrap">
                                    <p class="font-bold text-white truncate">${p.item_name}</p>
                                    ${digitalMicroBadge}
                                    ${promoMicroBadge}
                                </div>
                                <p class="text-[10px] text-slate-500 truncate">${p.item_id}</p>
                            </div>
                        </div>
                    </td>
                    <td class="px-6 py-4 text-slate-400">${p.item_department || "General"}</td>
                    <td class="px-6 py-4">
                        <span class="${isDigital ? "text-blue-400" : stock <= 5 ? "text-rose-500" : "text-emerald-500"} font-bold text-xs">
                            ${isDigital ? "Digital" : stock}
                        </span>
                    </td>
                    <td class="px-6 py-4 font-bold text-primary">${productCurrencySymbol}${price}</td>
                    <td class="px-6 py-4 text-right">
                        <div class="relative dropdown-container inline-block text-right">
                            <button type="button" class="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-all dropdown-toggle" title="Options">
                                <i data-lucide="more-vertical" class="w-4 h-4 pointer-events-none"></i>
                            </button>
                            <div class="dropdown-menu absolute right-0 top-full mt-1.5 w-32 bg-white dark:bg-[#151922] border border-slate-200 dark:border-white/10 rounded-xl shadow-xl py-1.5 z-50 text-left">
                                <button type="button" class="w-full text-left px-3.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2 transition-colors" onclick="editProduct('${p.item_id}')">
                                    <i data-lucide="edit-3" class="w-3.5 h-3.5"></i> Edit
                                </button>
                                <button type="button" class="w-full text-left px-3.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2 transition-colors" onclick="printProductQR('${p.item_id}')">
                                    <i data-lucide="qr-code" class="w-3.5 h-3.5"></i> QR Code
                                </button>
                                <button type="button" class="w-full text-left px-3.5 py-2 text-xs font-semibold text-rose-500 hover:bg-rose-500/10 flex items-center gap-2 transition-colors" onclick="deleteProduct('${p.item_id}')">
                                    <i data-lucide="trash-2" class="w-3.5 h-3.5"></i> Delete
                                </button>
                            </div>
                        </div>
                    </td>
                </tr>
            `;

      return { grid: gridItem, list: listItem };
    });

    if (activeView === "grid") {
      grid.insertAdjacentHTML("beforeend", html.map((h) => h.grid).join(""));
    } else if (listBody) {
      listBody.innerHTML = html.map((h) => h.list).join("");
    }

    // Add selection listeners
    document.querySelectorAll(".product-select").forEach((cb) => {
      cb.onchange = updateBatchButton;
    });

    if (typeof lucide !== "undefined") lucide.createIcons();
    if (window.initDropdownListeners) window.initDropdownListeners();
  }

  function updatePaginationUI(pagination) {
    const info = document.getElementById("product-pagination-info");
    const prevBtn = document.getElementById("product-prev-btn");
    const nextBtn = document.getElementById("product-next-btn");

    if (info) {
      const start = (pagination.current_page - 1) * pagination.per_page + 1;
      const end = Math.min(
        pagination.current_page * pagination.per_page,
        pagination.total_items,
      );
      info.textContent = `Showing ${pagination.total_items > 0 ? start : 0}-${end} of ${pagination.total_items} products`;
    }

    if (prevBtn) prevBtn.disabled = !pagination.has_previous;
    if (nextBtn) nextBtn.disabled = !pagination.has_next;
  }

  function renderProductMetrics(m) {
    if (!m) return;
    const totalProductsEl = document.getElementById("metric-total-products");
    const totalAmountEl = document.getElementById("metric-total-amount");
    const changePctEl = document.getElementById("metric-change-pct");
    const changeBadgeEl = document.getElementById("metric-change-badge");
    const changeSubEl = document.getElementById("metric-change-sub");

    if (totalProductsEl) {
      totalProductsEl.textContent = (m.total_products ?? 0).toLocaleString();
    }

    if (totalAmountEl) {
      const curr =
        (m.currency ? CURRENCY_SYMBOLS_MAP[m.currency] || m.currency : null) ||
        productCurrencySymbol ||
        (window.getUserCurrencySymbol
          ? window.getUserCurrencySymbol()
          : window.STORE_CURRENCY_SYMBOL || "₦");
      const amt = m.total_amount || 0;
      totalAmountEl.textContent = `${curr}${amt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      totalAmountEl.setAttribute(
        "title",
        `${curr}${amt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      );
    }

    if (changePctEl && changeBadgeEl) {
      const pct = typeof m.change_pct === "number" ? m.change_pct : 0;
      const dir =
        m.change_direction || (pct > 0 ? "up" : pct < 0 ? "down" : "neutral");
      const sign = pct > 0 ? "+" : "";

      changePctEl.textContent = `${sign}${pct}%`;

      if (dir === "up") {
        changePctEl.className =
          "text-2xl sm:text-3xl font-extrabold font-display text-emerald-500 dark:text-emerald-400 tracking-tight";
        changeBadgeEl.className =
          "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-500 dark:text-emerald-400 border border-emerald-500/20";
        changeBadgeEl.innerHTML =
          '<i data-lucide="trending-up" class="w-3.5 h-3.5"></i><span>Growing</span>';
      } else if (dir === "down") {
        changePctEl.className =
          "text-2xl sm:text-3xl font-extrabold font-display text-rose-500 dark:text-rose-400 tracking-tight";
        changeBadgeEl.className =
          "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-500 dark:text-rose-400 border border-rose-500/20";
        changeBadgeEl.innerHTML =
          '<i data-lucide="trending-down" class="w-3.5 h-3.5"></i><span>Down</span>';
      } else {
        changePctEl.className =
          "text-2xl sm:text-3xl font-extrabold font-display text-slate-700 dark:text-slate-300 tracking-tight";
        changeBadgeEl.className =
          "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-white/10";
        changeBadgeEl.innerHTML =
          '<i data-lucide="minus" class="w-3.5 h-3.5"></i><span>Steady</span>';
      }
    }

    if (changeSubEl && m.change_description) {
      changeSubEl.textContent = m.change_description;
    }

    if (typeof lucide !== "undefined") lucide.createIcons();
  }

  function renderLowStockAlerts(lowStockItems) {
    const indicator = document.getElementById("low-stock-indicator");
    const countBadge = document.getElementById("tooltip-low-stock-count");
    const listContainer = document.getElementById("tooltip-low-stock-list");

    if (!indicator || !countBadge || !listContainer) return;

    if (!lowStockItems || lowStockItems.length === 0) {
      indicator.classList.add("hidden");
      indicator.classList.remove("flex");
      return;
    }

    indicator.classList.remove("hidden");
    indicator.classList.add("flex");
    countBadge.textContent = lowStockItems.length;
    listContainer.innerHTML = "";

    lowStockItems.forEach((item) => {
      const qty = Number(item.item_quantity) || 0;
      const colorClass = qty === 0 ? "bg-red-500" : "bg-yellow-500";
      const progressWidth = qty === 0 ? "5%" : qty === 1 ? "15%" : "30%";

      const itemDiv = document.createElement("div");
      itemDiv.className =
        "px-2 py-1.5 hover:bg-slate-50 dark:hover:bg-white/5 rounded-lg cursor-pointer flex flex-col gap-1 transition-colors";
      itemDiv.onclick = (e) => {
        e.stopPropagation();
        if (typeof window.editProduct === "function") {
          window.editProduct(item.item_id);
        } else {
          console.warn("editProduct not found");
        }
      };

      itemDiv.innerHTML = `
                <div class="flex justify-between items-center w-full">
                    <span class="text-xs text-slate-700 dark:text-slate-300 truncate pr-2 font-medium">${item.item_name}</span>
                    <span class="text-[10px] font-semibold text-slate-500 dark:text-slate-400 shrink-0">${qty} left</span>
                </div>
                <div class="w-full bg-slate-100 dark:bg-white/10 rounded-full h-1 mt-0.5 overflow-hidden">
                    <div class="h-full ${colorClass}" style="width: ${progressWidth}"></div>
                </div>
            `;
      listContainer.appendChild(itemDiv);
    });

    if (typeof lucide !== "undefined") lucide.createIcons();
  }

  // Close tooltip on click outside
  document.addEventListener("click", (e) => {
    const tooltip = document.getElementById("low-stock-tooltip");
    if (tooltip && !tooltip.classList.contains("invisible")) {
      tooltip.classList.add("invisible", "opacity-0", "translate-y-2");
    }
  });

  // Infinite scroll for grid (IntersectionObserver + scroll fallback)
  if (scrollContainer && scrollSentinel && "IntersectionObserver" in window) {
    window._productsGridObserver = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) loadMoreGrid();
      },
      { root: scrollContainer, rootMargin: "240px", threshold: 0 },
    );
    window._productsGridObserver.observe(scrollSentinel);
  } else if (scrollContainer) {
    scrollContainer.onscroll = () => {
      if (activeView !== "grid" || isLoading || !hasMore) return;
      if (
        scrollContainer.scrollTop + scrollContainer.clientHeight >=
        scrollContainer.scrollHeight - 240
      ) {
        loadMoreGrid();
      }
    };
  }

  const prevBtn = document.getElementById("product-prev-btn");
  if (prevBtn) {
    prevBtn.onclick = () => {
      if (lastPagination.has_previous) fetchProducts(false, currentPage - 1);
    };
  }

  const nextBtn = document.getElementById("product-next-btn");
  if (nextBtn) {
    nextBtn.onclick = () => {
      if (lastPagination.has_next) fetchProducts(false, currentPage + 1);
    };
  }

  // Search Filter
  const productSearch = document.getElementById("product-filter-search");
  if (productSearch) {
    let searchTimeout;
    productSearch.oninput = (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        searchQuery = e.target.value;
        currentPage = 1;
        hasMore = true;
        if (activeView === "grid") grid.innerHTML = "";
        else if (listBody) listBody.innerHTML = "";
        fetchProducts(false, 1);
      }, 500);
    };
  }

  function updateBatchButton() {
    const selected = document.querySelectorAll(".product-select:checked");
    const batchBtn = document.getElementById("batch-delete-btn");
    if (batchBtn) {
      if (selected.length > 0) batchBtn.classList.remove("hidden");
      else batchBtn.classList.add("hidden");
    }
  }

  const selectAll = document.getElementById("select-all-products");
  if (selectAll) {
    selectAll.onchange = (e) => {
      document.querySelectorAll(".product-select").forEach((cb) => {
        cb.checked = e.target.checked;
      });
      updateBatchButton();
    };
  }

  window.editProduct = (id) => {
    const url = `/edit-product?id=${id}`;
    if (window.flezSwup) window.flezSwup.navigate(url);
    else window.location.href = url;
  };

  window.deleteProduct = (id) => {
    Swal.fire({
      title: "Delete Product?",
      text: "This action cannot be undone.",
      icon: "warning",
      showCancelButton: true,
      confirmButtonColor: "#ef4444",
      confirmButtonText: "Yes, delete it!",
    }).then(async (result) => {
      if (result.isConfirmed) {
        try {
          const res = await apiFetch(
            `${window.FLEZ_API_BASE}/api/user/products/delete`,
            {
              method: "POST",
              body: JSON.stringify({ product_ids: [id] }),
            },
          );
          const data = await res.json();
          if (data.status) {
            Swal.fire("Deleted!", "Product has been removed.", "success");
            currentPage = 1;
            if (activeView === "grid") grid.innerHTML = "";
            else if (listBody) listBody.innerHTML = "";
            fetchProducts(false, 1);
          } else {
            throw new Error(data.message);
          }
        } catch (err) {
          Swal.fire("Error", err.message, "error");
        }
      }
    });
  };

  window.batchDeleteProducts = () => {
    const selected = Array.from(
      document.querySelectorAll(".product-select:checked"),
    ).map((cb) => cb.dataset.id);
    if (selected.length === 0) return;

    Swal.fire({
      title: `Delete ${selected.length} Products?`,
      icon: "warning",
      showCancelButton: true,
      confirmButtonColor: "#ef4444",
      confirmButtonText: "Yes, delete all!",
    }).then(async (result) => {
      if (result.isConfirmed) {
        try {
          const res = await apiFetch(
            `${window.FLEZ_API_BASE}/api/user/products/delete`,
            {
              method: "POST",
              body: JSON.stringify({ product_ids: selected }),
            },
          );
          const data = await res.json();
          if (data.status) {
            Swal.fire(
              "Deleted!",
              "Selected products have been removed.",
              "success",
            );
            currentPage = 1;
            if (activeView === "grid") grid.innerHTML = "";
            else if (listBody) listBody.innerHTML = "";
            fetchProducts(false, 1);
          } else {
            throw new Error(data.message);
          }
        } catch (err) {
          Swal.fire("Error", err.message, "error");
        }
      }
    });
  };

  fetchProducts(false, 1);
}

/**
 * Import Products Logic
 */
function initImport() {
  window.handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const data = new Uint8Array(e.target.result);
      const workbook = XLSX.read(data, { type: "array" });
      const firstSheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[firstSheetName];
      const jsonData = XLSX.utils.sheet_to_json(worksheet);

      if (jsonData.length === 0) {
        Swal.fire("Error", "The file is empty or invalid.", "error");
        return;
      }

      // Show review step
      $("#upload-step").addClass("hidden");
      $("#review-step").removeClass("hidden").addClass("animate-fade-in");

      // Populate review table
      renderImportedItems(jsonData);
    };
    reader.readAsArrayBuffer(file);
  };

  window.renderImportedItems = async (items) => {
    const tbody = $("#import-tbody");
    tbody.empty();

    // Pre-fetch categories and departments if not already cached for this session
    if (!window.cachedCategories || !window.cachedDepartments) {
      try {
        const [catRes, deptRes] = await Promise.all([
          apiFetch(`${window.FLEZ_API_BASE}/api/categories/filter`, {
            method: "POST",
          }),
          apiFetch(`${window.FLEZ_API_BASE}/api/departments/filter`, {
            method: "POST",
          }),
        ]);
        const catData = await catRes.json();
        const deptData = await deptRes.json();
        window.cachedCategories = catData.status ? catData.data : [];
        window.cachedDepartments = deptData.status ? deptData.data : [];
      } catch (err) {
        console.error("Failed to fetch categories/departments for import", err);
      }
    }

    const catOptions = (window.cachedCategories || [])
      .map(
        (c) => `<option value="${c.category_name}">${c.category_name}</option>`,
      )
      .join("");
    const deptOptions = (window.cachedDepartments || [])
      .map(
        (d) =>
          `<option value="${d.department_name}">${d.department_name}</option>`,
      )
      .join("");

    items.forEach((item, index) => {
      const name =
        item["Product Name"] || item["item_name"] || item["Name"] || "";
      const sku =
        item["SKU"] ||
        item["item_serial_number"] ||
        item["Serial Number"] ||
        "";
      const cat = item["Category"] || item["item_category"] || "";
      const dept = item["Department"] || item["item_department"] || "";
      const stock =
        item["Initial Stock"] || item["item_quantity"] || item["Stock"] || 0;
      const buy =
        item["Buy Price"] || item["item_buy_amount"] || item["Buy Amount"] || 0;
      const sell =
        item["Sell Price"] || item["item_amount"] || item["Price"] || 0;

      const row = $(`
                <tr class="group table-row-hover transition-all" data-index="${index}">
                    <td class="px-6 py-4"><input type="text" name="item_name" class="input-elegant" value="${name}"></td>
                    <td class="px-6 py-4"><input type="text" name="item_serial_number" class="input-elegant" value="${sku}"></td>
                    <td class="px-6 py-4">
                        <select name="item_category" class="select-elegant">
                            <option value="">Select Category</option>
                            ${catOptions}
                        </select>
                    </td>
                    <td class="px-6 py-4">
                        <select name="item_department" class="select-elegant">
                            <option value="">Select Department</option>
                            ${deptOptions}
                        </select>
                    </td>
                    <td class="px-6 py-4"><input type="number" name="item_quantity" class="input-elegant" value="${stock}"></td>
                    <td class="px-6 py-4"><input type="number" name="item_buy_amount" class="input-elegant" value="${buy}"></td>
                    <td class="px-6 py-4"><input type="number" name="item_amount" class="input-elegant" value="${sell}"></td>
                    <td class="px-6 py-4 text-right">
                        <button class="p-2 text-rose-500 hover:bg-rose-500/10 rounded-lg transition-all" onclick="$(this).closest('tr').fadeOut(300, function(){ $(this).remove(); updateItemCount(); })">
                            <i data-lucide="trash-2" class="w-5 h-5"></i>
                        </button>
                    </td>
                </tr>
            `);

      // Set selected values
      if (cat) row.find('select[name="item_category"]').val(cat);
      if (dept) row.find('select[name="item_department"]').val(dept);

      tbody.append(row);
    });

    window.updateItemCount();
    if (window.lucide) lucide.createIcons();
  };

  window.updateItemCount = () => {
    const count = $("#import-tbody tr").length;
    $("#review-step p.text-slate-400").text(
      `Review ${count} items. Edit details before saving.`,
    );
    $("#review-step p.text-[10px]").text(`Items 1 - ${count} of ${count}`);
  };

  window.saveImportedItems = async () => {
    const rows = $("#import-tbody tr");
    const items = [];

    rows.each(function () {
      const row = $(this);
      const item = {
        item_name: row.find('input[name="item_name"]').val(),
        item_serial_number: row.find('input[name="item_serial_number"]').val(),
        item_category:
          row.find('select[name="item_category"]').val() || "General",
        item_department:
          row.find('select[name="item_department"]').val() || "Retail Ops",
        item_quantity:
          parseInt(row.find('input[name="item_quantity"]').val()) || 0,
        item_buy_amount:
          parseFloat(row.find('input[name="item_buy_amount"]').val()) || 0,
        item_amount:
          parseFloat(row.find('input[name="item_amount"]').val()) || 0,
        item_id: "PRD-" + Math.random().toString(36).substr(2, 9).toUpperCase(),
        item_description: "Imported product",
      };
      items.push(item);
    });

    if (items.length === 0) {
      Swal.fire("Error", "No items to save.", "error");
      return;
    }

    Swal.fire({
      title: "Saving Items",
      text: `Uploading ${items.length} products...`,
      allowOutsideClick: false,
      didOpen: () => {
        Swal.showLoading();
      },
    });

    try {
      const response = await apiFetch(
        `${window.FLEZ_API_BASE}/api/user/data/add/items`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(items),
        },
      );

      const result = await response.json();

      if (result.status) {
        await Swal.fire({
          icon: "success",
          title: "Import Successful",
          text: result.message,
          timer: 2000,
          showConfirmButton: false,
        });
        // Clear cache and redirect
        localStorage.removeItem("user_data");
        if (window.flezSwup) window.flezSwup.navigate("/products");
        else window.location.href = "/products";
      } else {
        Swal.fire(
          "Import Failed",
          result.message || "Something went wrong.",
          "error",
        );
      }
    } catch (err) {
      console.error("Import error:", err);
      Swal.fire("Error", "Failed to communicate with server.", "error");
    }
  };
}

/**
 * Invoice Builder Logic
 */
function initInvoiceBuilder() {
  const dueDateInput = document.getElementById("due-date");
  if (dueDateInput) {
    dueDateInput.value = new Date().toISOString().split("T")[0];
  }
  const itemContainer = document.getElementById("items-container");
  const typeBtns = document.querySelectorAll(".payment-type-btn");
  const installmentNotice = document.getElementById("installment-notice");

  const manualAddBtn = document.getElementById("add-item");
  if (manualAddBtn) {
    manualAddBtn.onclick = () => {
      console.log("Manual add disabled per requirements.");
    };
  }

  typeBtns.forEach((btn) => {
    btn.onclick = function () {
      typeBtns.forEach((b) => {
        b.classList.remove(
          "active",
          "bg-primary",
          "text-white",
          "shadow-lg",
          "shadow-primary/20",
        );
        b.classList.add(
          "bg-white/5",
          "border",
          "border-white/10",
          "text-slate-400",
          "hover:bg-white/10",
        );
      });
      this.classList.add(
        "active",
        "bg-primary",
        "text-white",
        "shadow-lg",
        "shadow-primary/20",
      );
      this.classList.remove(
        "bg-white/5",
        "border",
        "border-white/10",
        "text-slate-400",
        "hover:bg-white/10",
      );

      if (this.dataset.type === "installment") {
        if (installmentNotice) installmentNotice.classList.remove("hidden");
      } else {
        if (installmentNotice) installmentNotice.classList.add("hidden");
      }
    };
  });

  const createBtn = document.getElementById("create-btn");
  if (createBtn) {
    createBtn.onclick = async () => {
      const rows = document.querySelectorAll(".invoice-item-row");
      if (rows.length === 0) {
        showToast("Empty Invoice", "Please add at least one item.", "error");
        return;
      }

      const activeTypeBtn = document.querySelector(".payment-type-btn.active");
      const invoiceType = activeTypeBtn
        ? activeTypeBtn.dataset.type
        : "instant";

      const items = Array.from(rows).map((row) => {
        const name = row.querySelector("input[readonly]").value;
        const qty = parseInt(row.querySelector(".item-qty").value) || 1;
        const price =
          parseFloat(row.querySelector(".item-price").dataset.price) || 0;
        const itemId =
          row.querySelector(".item-id")?.value ||
          "PRD-" + Math.random().toString(36).substr(2, 9).toUpperCase();

        return {
          item_name: name,
          item_quantity: qty,
          item_amount: price,
          item_id: itemId,
          item_buy_amount: price * 0.7, // Mock buy amount if unknown
        };
      });

      // UI Feedback
      const originalHTML = createBtn.innerHTML;
      createBtn.disabled = true;
      createBtn.innerHTML = `Creating... <svg class="animate-spin ml-2 w-5 h-5 inline" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>`;

      try {
        const dueDate = document.getElementById("due-date")?.value || "";
        const res = await apiFetch(
          `${window.CONFIG.API_BASE}/api/invoice/create`,
          {
            method: "POST",
            body: JSON.stringify({
              invoice_type: invoiceType,
              invoice_payment_type: invoiceType,
              invoice_status:
                invoiceType === "instant" ? "completed" : "pending",
              invoice_note:
                document.getElementById("invoice-note")?.value || "",
              customer_name:
                document.getElementById("customer-name")?.value || "",
              customer_email:
                document.getElementById("customer-email")?.value || "",
              customer_phone:
                document.getElementById("customer-phone")?.value || "",
              due_date: dueDate,
              items: items,
            }),
          },
        );
        const data = await res.json();
        if (data.status) {
          const details = data.details || {};
          if (details.account_number) {
            Swal.fire({
              title: "Installment Invoice Created!",
              html: `
                                <div class="text-left space-y-4 pt-4">
                                    <p class="text-xs text-slate-500 leading-relaxed">Please provide the customer with these unique account details for their installment payments. All credits to this account will automatically update the invoice balance.</p>
                                    <div class="bg-slate-50 dark:bg-white/5 p-5 rounded-2xl border border-slate-200 dark:border-white/10">
                                        <div class="mb-4">
                                            <p class="text-[10px] text-slate-400 font-bold uppercase mb-1">Bank Name</p>
                                            <p class="text-sm font-bold text-slate-800 dark:text-white uppercase">${details.bank_name}</p>
                                        </div>
                                        
                                        <div class="mb-4">
                                            <p class="text-[10px] text-slate-400 font-bold uppercase mb-1">Account Number</p>
                                            <div class="flex items-center gap-2">
                                                <p class="text-2xl font-mono font-black text-primary tracking-tighter">${details.account_number}</p>
                                                <button onclick="copyToClipboard('${details.account_number}')" class="p-2 hover:bg-primary/10 rounded-lg text-primary transition-all" title="Copy">
                                                    <i data-lucide="copy" class="w-4 h-4"></i>
                                                </button>
                                            </div>
                                        </div>
                                        
                                        <div>
                                            <p class="text-[10px] text-slate-400 font-bold uppercase mb-1">Account Name</p>
                                            <p class="text-xs font-bold text-slate-800 dark:text-white uppercase">${details.account_name}</p>
                                        </div>
                                    </div>
                                    <div class="flex items-center gap-2 text-[10px] font-bold text-rose-500 uppercase">
                                        <i data-lucide="info" class="w-3 h-3"></i>
                                        <span>These details are exclusive to Invoice #${details.item_invoice_id}</span>
                                    </div>
                                </div>
                            `,
              icon: "success",
              confirmButtonText: "Go to Invoices",
              confirmButtonColor: "#cfff45",
              background: document.documentElement.classList.contains("dark")
                ? "#1e293b"
                : "#ffffff",
              color: document.documentElement.classList.contains("dark")
                ? "#ffffff"
                : "#1e293b",
              didOpen: () => {
                if (window.lucide) lucide.createIcons();
              },
            }).then(async () => {
              await refreshUserData();
              if (window.flezSwup) window.flezSwup.navigate("/invoices");
              else window.location.href = "/invoices";
            });
          } else {
            showToast("Success", "Invoice created successfully!", "success");
            setTimeout(async () => {
              await refreshUserData();
              if (window.flezSwup) window.flezSwup.navigate("/invoices");
              else window.location.href = "/invoices";
            }, 1500);
          }
        } else {
          throw new Error(data.message || "Failed to create invoice");
        }
      } catch (err) {
        showToast("Error", err.message, "error");
        createBtn.disabled = false;
        createBtn.innerHTML = originalHTML;
        if (typeof lucide !== "undefined") lucide.createIcons();
      }
    };
  }

  const inventorySearch = document.getElementById("inventory-search");
  const searchDropdown = document.getElementById("search-results-dropdown");
  const barcodeBtn = document.getElementById("barcode-scan-btn");

  let inventoryItems = [];
  if (inventorySearch && searchDropdown) {
    apiFetch(`${window.CONFIG.API_BASE}/api/user/data`, { method: "POST" })
      .then((res) => res.json())
      .then((data) => {
        if (data.status && data.data && data.data.items) {
          inventoryItems = data.data.items;
        }
      })
      .catch((err) => console.error("Failed to fetch inventory:", err));

    inventorySearch.oninput = (e) => {
      const query = e.target.value.toLowerCase();
      if (query.length < 1) {
        searchDropdown.classList.add("hidden");
        return;
      }

      const results = inventoryItems.filter(
        (p) =>
          p.item_name.toLowerCase().includes(query) ||
          (p.item_id && p.item_id.toLowerCase().includes(query)),
      );

      if (results.length > 0) {
        const curSym = getUserCurrencySymbol();
        searchDropdown.innerHTML = results
          .map(
            (p) => `
                    <div class="p-4 hover:bg-white/5 cursor-pointer border-b border-white/5 flex items-center justify-between" onclick="addInvoiceItem('${p.item_name.replace(/'/g, "\\'")}', ${p.item_amount}, '${p.item_id}', '${p.item_id}')">
                        <div>
                            <p class="text-sm font-bold text-white">${p.item_name}</p>
                            <p class="text-xs text-slate-500">${curSym}${Number(p.item_amount).toLocaleString()}</p>
                        </div>
                        <div class="text-right">
                            <p class="text-[10px] font-bold text-primary uppercase">${p.item_quantity} In Stock</p>
                        </div>
                    </div>
                `,
          )
          .join("");
        searchDropdown.classList.remove("hidden");
      } else {
        searchDropdown.innerHTML =
          '<div class="p-6 text-center text-slate-500 text-sm">No items found</div>';
        searchDropdown.classList.remove("hidden");
      }
    };

    document.addEventListener("click", (e) => {
      if (
        !inventorySearch.contains(e.target) &&
        !searchDropdown.contains(e.target)
      ) {
        searchDropdown.classList.add("hidden");
      }
    });
  }

  if (barcodeBtn) {
    barcodeBtn.remove();
  }

  window.addInvoiceItem = (name, price, sku = "", id = "") => {
    const itemContainer = document.getElementById("items-container");
    const emptyState = document.getElementById("items-empty-state");
    if (emptyState) emptyState.classList.add("hidden");

    if (!itemContainer) return;

    const curSym = getUserCurrencySymbol();
    const row = document.createElement("div");
    row.className =
      "invoice-item-row grid grid-cols-12 gap-4 items-end fade-in";
    row.innerHTML = `
            <div class="col-span-6">
                <input type="text" value="${name}" readonly class="w-full bg-white/5 border border-white/5 rounded-xl px-4 py-3 text-sm text-slate-300 cursor-not-allowed">
                <input type="hidden" class="item-sku" value="${sku}">
                <input type="hidden" class="item-id" value="${id}">
            </div>
            <div class="col-span-2"><input type="number" value="1" min="1" oninput="if(this.value < 1) this.value = 1; calculateInvoiceTotals()" class="item-qty w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-primary/50"></div>
            <div class="col-span-3"><input type="text" value="${curSym}${price.toLocaleString()}" data-price="${price}" readonly class="item-price w-full bg-white/5 border border-white/5 rounded-xl px-4 py-3 text-sm text-primary font-bold cursor-not-allowed"></div>
            <div class="col-span-1 border-none"><button class="p-3 text-slate-600 hover:text-rose-500 remove-item"><i data-lucide="trash-2" class="w-5 h-5"></i></button></div>
        `;
    itemContainer.appendChild(row);
    lucide.createIcons();

    row.querySelector(".remove-item").onclick = () => {
      row.remove();
      if (itemContainer.querySelectorAll(".invoice-item-row").length === 0) {
        if (emptyState) emptyState.classList.remove("hidden");
      }
      calculateInvoiceTotals();
    };

    if (searchDropdown) searchDropdown.classList.add("hidden");
    if (inventorySearch) inventorySearch.value = "";
    calculateInvoiceTotals();
  };

  window.calculateInvoiceTotals = () => {
    let subtotal = 0;
    document.querySelectorAll(".invoice-item-row").forEach((row) => {
      const qty = parseInt(row.querySelector(".item-qty").value) || 0;
      const price =
        parseFloat(row.querySelector(".item-price").dataset.price) || 0;
      subtotal += qty * price;
    });

    const vat = subtotal * 0.075;
    const total = subtotal + vat;

    const subtotalEl = document.getElementById("subtotal-display");
    const vatEl = document.getElementById("vat-display");
    const totalEl = document.getElementById("total-display");

    const curSym = getUserCurrencySymbol();
    if (subtotalEl)
      subtotalEl.innerText = `${curSym}${subtotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (vatEl)
      vatEl.innerText = `${curSym}${vat.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (totalEl)
      totalEl.innerText = `${curSym}${total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };
}

/**
 * Settings Page Logic
 */
function initSettings() {
  if (
    document.getElementById("settings-content-container") ||
    document.getElementById("save-settings")
  ) {
    // Handled by settings.js initSettingsPage()
    return;
  }
  const tabs = document.querySelectorAll(".tab-link");
  const contents = document.querySelectorAll(".tab-content");

  tabs.forEach((tab) => {
    tab.onclick = function (e) {
      const target = this.getAttribute("data-tab");
      if (!target) return;

      tabs.forEach((t) => {
        t.classList.remove("active", "text-primary", "border-primary");
        t.classList.add("text-slate-500");
      });

      this.classList.add("active", "text-primary", "border-primary");
      this.classList.remove("text-slate-500");

      contents.forEach((content) => {
        if (content.id === `tab-${target}`) {
          content.classList.remove("hidden");
          content.classList.add(
            "animate-in",
            "fade-in",
            "slide-in-from-bottom-4",
            "duration-500",
          );
        } else {
          content.classList.add("hidden");
          content.classList.remove(
            "animate-in",
            "fade-in",
            "slide-in-from-bottom-4",
          );
        }
      });

      if (typeof lucide !== "undefined") lucide.createIcons();
    };
  });
}

/**
 * Dashboard Overview Charts
 */
/**
 * Dashboard Stats
 */
function initDashboardStats() {
  const rawData = localStorage.getItem("user_data");
  if (!rawData) return;
  const user = JSON.parse(rawData);

  // Update Greeting with actual first name if available
  const greetingEl = document.getElementById("dashboard-user-greeting");
  if (greetingEl) {
    const details = user.details?.[0] || {};
    const firstName = details.first_name || user.first_name;
    if (firstName) {
      greetingEl.textContent = `Hello, ${firstName}!`;
    }
  }

  const summary = user.sales_summary || {};
  const transactions = user.transactions || [];

  const dateFilter = document.getElementById("dashboard-date-filter");
  const filterValue = dateFilter ? dateFilter.value : "30";

  let startDate = new Date(0);
  const now = new Date();
  if (filterValue === "today") {
    startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  } else if (filterValue === "7") {
    startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  } else if (filterValue === "30") {
    startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  }

  let totalCredits = 0;
  let totalDebits = 0;

  transactions.forEach((trx) => {
    if (trx.trx_status === "completed" || trx.trx_status === "success") {
      const trxDate = new Date(trx.timestamp);
      if (trxDate >= startDate && trxDate <= now) {
        const amount = parseFloat(trx.trx_amount) || 0;
        if (trx.trx_type === "credit") {
          totalCredits += amount;
        } else {
          totalDebits += amount;
        }
      }
    }
  });

  const netTransactions = totalCredits - totalDebits;

  let revenue = 0;
  if (filterValue === "today") {
    revenue = summary.sales_today || 0;
  } else if (filterValue === "7") {
    revenue = summary.sales_last_7_days || 0;
  } else if (filterValue === "30") {
    revenue = summary.sales_this_month || 0;
  } else {
    revenue = summary.total_paid || 0;
  }

  const userCurSym = getUserCurrencySymbol(user);
  const totalRev = document.getElementById("stat-total-revenue");
  if (totalRev)
    totalRev.textContent = `${userCurSym}${revenue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  // Revenue change % vs previous period
  const revChangeEl = document.getElementById("stat-revenue-change");
  if (revChangeEl) {
    let prevRevenue = 0;
    if (filterValue === "today")
      prevRevenue = summary.sales_last_7_days / 7 || 0; // avg daily
    else if (filterValue === "7")
      prevRevenue = summary.sales_last_month_to_date / 4 || 0; // weekly estimate from month
    else if (filterValue === "30")
      prevRevenue = summary.sales_last_month_to_date || 0;
    else prevRevenue = summary.total_paid > 0 ? summary.total_paid * 0.9 : 0; // fallback for all-time
    const revChg =
      prevRevenue > 0
        ? ((revenue - prevRevenue) / prevRevenue) * 100
        : revenue > 0
          ? 100
          : 0;
    const revUp = revChg >= 0;
    revChangeEl.className = `text-xs font-bold flex items-center gap-1 ${revUp ? "text-emerald-400" : "text-rose-400"}`;
    revChangeEl.innerHTML = `<i data-lucide="${revUp ? "trending-up" : "trending-down"}" class="w-3 h-3"></i> ${revUp ? "+" : ""}${revChg.toFixed(1)}%`;
    if (typeof lucide !== "undefined") lucide.createIcons();
  }

  // Inventory Value
  let inventoryValue = 0;
  const items = user.items || [];
  if (typeof user.inventory_value === "number") {
    inventoryValue = user.inventory_value;
  } else {
    inventoryValue = items.reduce((acc, item) => {
      const amt = parseFloat(item.item_amount) || 0;
      const qty = item.total_stock ?? item.item_quantity ?? 1;
      return acc + amt * (parseInt(qty, 10) || 1);
    }, 0);
  }
  const totalInv =
    document.getElementById("stat-inventory") ||
    document.getElementById("stat-transactions");
  if (totalInv)
    totalInv.textContent = `${userCurSym}${inventoryValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const invCountEl = document.getElementById("stat-inventory-count");
  if (invCountEl) {
    invCountEl.textContent = `${items.length} ${items.length === 1 ? "item" : "items"} in stock`;
  }
  const invChangeEl =
    document.getElementById("stat-inventory-change") ||
    document.getElementById("stat-transactions-change");
  if (invChangeEl && !invCountEl) {
    invChangeEl.className =
      "text-[11px] font-bold text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full flex items-center gap-1 shrink-0";
    invChangeEl.innerHTML = `<i data-lucide="boxes" class="w-3 h-3"></i> ${items.length} ${items.length === 1 ? "item" : "items"} in stock`;
    if (typeof lucide !== "undefined") lucide.createIcons();
  }

  const isFinancesMasked = !!(
    user.finances_masked ||
    (user.manager_account && user.manager_account.manage_finances === false)
  );
  const isPayrollMasked = !!(
    user.payroll_masked ||
    (user.manager_account && user.manager_account.manage_payroll === false)
  );

  if (isFinancesMasked) {
    const walletBal = document.getElementById("stat-wallet-balance");
    if (walletBal) walletBal.textContent = "••••••";
    const walletActionDiv = document
      .querySelector("#stat-wallet-balance")
      ?.closest(".p-4, .p-5")
      ?.querySelector(".flex.gap-2, .flex.items-center.gap-1");
    if (walletActionDiv) {
      walletActionDiv.className =
        "flex items-center gap-1 text-[11px] text-slate-500 font-semibold";
      walletActionDiv.innerHTML = `<i data-lucide="lock" class="w-3 h-3"></i> Restricted`;
      if (typeof lucide !== "undefined") lucide.createIcons();
    }
  }

  const activeStaff = document.getElementById("stat-active-staff");
  if (activeStaff) {
    if (isPayrollMasked) {
      activeStaff.textContent = "••••••";
    } else {
      const staffCount = user.payroll?.length || 0;
      activeStaff.textContent = `${staffCount} / ${staffCount}`; // Mocking limit for now
    }
  }

  // Recent Transactions on Dashboard
  const recentBody = document.getElementById("recent-transactions-body");
  if (recentBody) {
    const transactions = user.transactions || [];
    recentBody.innerHTML = transactions
      .slice(0, 5)
      .map((trx) => {
        const desc = trx.description || "Transaction";
        const safeDesc = desc
          .replace(/"/g, "&quot;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;");
        return `
            <tr class="group hover:bg-white/5 transition-all">
                <td class="px-6 py-4 max-w-xs sm:max-w-sm">
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-lg ${trx.trx_type === "credit" ? "bg-emerald-500/10 text-emerald-500" : "bg-rose-500/10 text-rose-500"} flex items-center justify-center shrink-0">
                            <i data-lucide="${trx.trx_type === "credit" ? "arrow-down-left" : "arrow-up-right"}" class="w-4 h-4"></i>
                        </div>
                        <div class="min-w-0">
                            <p class="text-sm font-bold text-white truncate" title="${safeDesc}">${desc}</p>
                            <p class="text-[10px] text-slate-500 truncate">${trx.trx_id ? trx.trx_id.toString().split("-")[0] : "N/A"} • ${new Date(trx.timestamp).toLocaleDateString()}</p>
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-3 py-1 ${trx.trx_status === "completed" || trx.trx_status === "success" ? "bg-emerald-500/10 text-emerald-500" : "bg-rose-500/10 text-rose-500"} text-[10px] font-bold rounded-full uppercase">${trx.trx_status || "Completed"}</span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="text-xs ${trx.trx_type === "credit" ? "text-emerald-500" : "text-rose-500"} font-bold uppercase">${trx.trx_type || "Debit"}</span>
                </td>
                <td class="px-6 py-4 text-right whitespace-nowrap">
                    <p class="text-sm font-bold text-white">${userCurSym}${parseFloat(trx.trx_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                </td>
            </tr>
        `;
      })
      .join("");
    if (transactions.length === 0) {
      recentBody.innerHTML = `<tr><td colspan="4" class="px-6 py-10 text-center text-slate-500 text-sm">No transactions yet</td></tr>`;
    }
    if (typeof lucide !== "undefined") lucide.createIcons();
  }

  // Top 5 Performing Items on Dashboard
  const topItemsBody = document.getElementById("top-performing-items-body");
  if (topItemsBody) {
    const summary = user.sales_summary || {};
    const topItems = (summary.best_performing_items_month || []).slice(0, 5);
    const currencySymbol = userCurSym;

    if (topItems.length === 0) {
      topItemsBody.innerHTML = `
                <div class="flex flex-col items-center justify-center h-full py-10 text-center gap-3">
                    <div class="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center text-slate-500">
                        <i data-lucide="package" class="w-5 h-5"></i>
                    </div>
                    <div>
                        <p class="text-sm font-semibold text-slate-400">No sales data yet</p>
                        <p class="text-xs text-slate-600 mt-1">Top items will appear once you have completed sales this month.</p>
                    </div>
                </div>
            `;
    } else {
      const maxSales = Math.max(
        ...topItems.map((item) => item.total_sales || 0),
        1,
      );
      topItemsBody.innerHTML = topItems
        .map((item, index) => {
          const pct = Math.round(((item.total_sales || 0) / maxSales) * 100);
          const rankColors = [
            "text-yellow-400",
            "text-slate-300",
            "text-orange-400",
            "text-slate-500",
            "text-slate-500",
          ];
          const barColors = [
            "bg-primary",
            "bg-blue-500",
            "bg-purple-500",
            "bg-orange-500",
            "bg-pink-500",
          ];
          const imgSrc = item.image_url;
          return `
                <div class="flex items-center gap-3 p-2.5 rounded-xl hover:bg-white/5 transition-all group cursor-pointer" onclick="if(window.flezSwup) window.flezSwup.navigate('/edit-product?id=${item.item_id}'); else window.location.href='/edit-product?id=${item.item_id}';">
                    <span class="text-xs font-bold ${rankColors[index] || rankColors[4]} w-4 shrink-0 text-center">#${index + 1}</span>
                    <div class="w-9 h-9 rounded-xl bg-white/5 border border-white/10 overflow-hidden shrink-0 flex items-center justify-center">
                        ${imgSrc ? `<img src="${imgSrc}" alt="${item.item}" class="w-full h-full object-cover">` : `<i data-lucide="box" class="w-4 h-4 text-slate-500"></i>`}
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-xs font-bold text-white truncate">${item.item}</p>
                        <div class="flex items-center gap-2 mt-1">
                            <div class="flex-1 h-1 bg-white/5 rounded-full overflow-hidden">
                                <div class="h-full ${barColors[index % barColors.length]} rounded-full transition-all duration-700" style="width: ${pct}%"></div>
                            </div>
                        </div>
                    </div>
                    <span class="text-xs font-bold text-white shrink-0">${currencySymbol}${(item.total_sales || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                </div>
            `;
        })
        .join("");
    }
    if (typeof lucide !== "undefined") lucide.createIcons();
  }
}

/**
 * initPaginatedTable: Generic handler for tables with backend pagination/filtering
 */
async function initPaginatedTable(config) {
  const {
    endpoint,
    containerId,
    prevBtnId,
    nextBtnId,
    infoId,
    renderRow,
    filters = {},
    perPage = 10,
  } = config;

  let currentPage = 1;
  let totalPages = 1;

  async function loadPage(page = 1) {
    const body = {
      page,
      per_page: perPage,
      ...Object.fromEntries(
        Object.entries(filters).map(([k, v]) => [
          k,
          document.getElementById(v)?.value,
        ]),
      ),
    };

    // Add search if available
    if (config.searchId) {
      body.search = document.getElementById(config.searchId)?.value || "";
    }

    try {
      const res = await apiFetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const result = await res.json();

      if (result.status) {
        const container = document.getElementById(containerId);
        if (container) {
          if (result.data && result.data.length > 0) {
            container.innerHTML = result.data.map(renderRow).join("");
          } else {
            container.innerHTML = `<tr><td colspan="10" class="px-6 py-10 text-center text-slate-500">No data found matching your filters</td></tr>`;
          }
          if (typeof lucide !== "undefined") lucide.createIcons();
        }

        // Update pagination
        currentPage = result.pagination.current_page;
        totalPages = result.pagination.total_pages;

        const info = document.getElementById(infoId);
        if (info) {
          const start = (currentPage - 1) * perPage + 1;
          const end = Math.min(
            currentPage * perPage,
            result.pagination.total_items,
          );
          info.textContent = `Showing ${result.pagination.total_items > 0 ? start : 0}-${end} of ${result.pagination.total_items} items`;
        }

        const prevBtn = document.getElementById(prevBtnId);
        const nextBtn = document.getElementById(nextBtnId);
        if (prevBtn) prevBtn.disabled = !result.pagination.has_previous;
        if (nextBtn) nextBtn.disabled = !result.pagination.has_next;
      }
    } catch (err) {
      console.error(`Failed to load ${containerId}:`, err);
    }
  }

  // Bind Pagination
  document.getElementById(prevBtnId)?.addEventListener("click", () => {
    if (currentPage > 1) loadPage(currentPage - 1);
  });
  document.getElementById(nextBtnId)?.addEventListener("click", () => {
    if (currentPage < totalPages) loadPage(currentPage + 1);
  });

  // Bind Filters
  Object.values(filters).forEach((id) => {
    document.getElementById(id)?.addEventListener("change", () => loadPage(1));
  });
  if (config.searchId) {
    let timeout;
    document.getElementById(config.searchId)?.addEventListener("input", () => {
      clearTimeout(timeout);
      timeout = setTimeout(() => loadPage(1), 500);
    });
  }

  // Initial Load
  loadPage(1);
}

/**
 * Invoices Page Logic
 */
window.initInvoices = () => {
  const tbody = document.getElementById("invoices-tbody");
  if (!tbody) return;

  initPaginatedTable({
    endpoint: `${FLEZ_API_BASE}/api/invoices/filter`,
    containerId: "invoices-tbody",
    prevBtnId: "invoice-prev-btn",
    nextBtnId: "invoice-next-btn",
    infoId: "invoices-pagination-info",
    searchId: "invoice-filter-search",
    filters: {
      status: "invoice-filter-status",
      type: "invoice-filter-type",
    },
    renderRow: (inv) => {
      const dateObj = new Date(inv.timestamp);
      const formattedDate = isNaN(dateObj)
        ? "N/A"
        : dateObj.toLocaleDateString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
          });

      return `
            <tr class="group hover:bg-white/5 transition-all cursor-pointer" onclick="viewInvoice('${inv.invoice_id}')">
                <td class="px-6 py-4">
                    <p class="text-sm font-bold text-white uppercase tracking-wider">${inv.invoice_id}</p>
                    <p class="text-[10px] text-primary font-bold uppercase tracking-tighter">${inv.invoice_type || "Instant"}</p>
                </td>
                <td class="px-6 py-4">
                    <p class="text-sm font-bold text-white">${inv.customer_name || "Walk-in Customer"}</p>
                    <p class="text-[10px] text-slate-500">${inv.customer_email || "No email provided"}</p>
                </td>
                <td class="px-6 py-4 text-sm text-slate-400 font-medium">
                    ${formattedDate}
                </td>
                <td class="px-6 py-4">
                    <span class="px-3 py-1 ${inv.invoice_status === "completed" ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" : "bg-amber-500/10 text-amber-500 border-amber-500/20"} text-[10px] font-bold rounded-full uppercase border">
                        ${inv.invoice_status}
                    </span>
                </td>
                <td class="px-6 py-4 text-right">
                    <p class="text-sm font-bold text-white">${getUserCurrencySymbol()}${parseFloat(inv.total_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                </td>
                <td class="px-6 py-4 text-right">
                    <div class="flex items-center justify-end gap-1">
                        <button onclick="event.stopPropagation(); deleteInvoice('${inv.invoice_id}')" class="p-2 hover:bg-rose-500/10 rounded-lg text-slate-400 hover:text-rose-500 transition-all" title="Delete">
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    },
  });

  // Handle stats summary from user_data
  const user = JSON.parse(localStorage.getItem("user_data") || "{}");
  const summary = user.sales_summary || {};
  const curSym = getUserCurrencySymbol(user);

  const elTotalPaid = document.getElementById("stat-total-paid");
  const elPaidPercent = document.getElementById("stat-paid-percentage");
  const elOutstanding = document.getElementById("stat-outstanding");
  const elPendingCount = document.getElementById("stat-pending-count");
  const elOverdue = document.getElementById("stat-overdue");
  const elOverdueCount = document.getElementById("stat-overdue-count");

  if (elTotalPaid)
    elTotalPaid.textContent = `${curSym}${(summary.total_paid || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (elPaidPercent) {
    const total = (summary.total_paid || 0) + (summary.total_outstanding || 0);
    const percent =
      total > 0 ? Math.round((summary.total_paid / total) * 100) : 0;
    elPaidPercent.textContent = `${percent}% of total issued`;
  }
  if (elOutstanding)
    elOutstanding.textContent = `${curSym}${(summary.total_outstanding || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (elPendingCount)
    elPendingCount.textContent = `${summary.pending_count || 0} invoices pending`;
  if (elOverdue)
    elOverdue.textContent = `${curSym}${(summary.overdue_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (elOverdueCount)
    elOverdueCount.textContent = `${summary.overdue_count || 0} invoices past due`;

  if (typeof lucide !== "undefined") lucide.createIcons();
};

/**
 * Transactions Page Logic
 */
window.initTransactions = () => {
  if (!document.getElementById("transactions-tbody")) return;

  initPaginatedTable({
    endpoint: `${FLEZ_API_BASE}/api/transactions/filter`,
    containerId: "transactions-tbody",
    prevBtnId: "trx-prev-btn",
    nextBtnId: "trx-next-btn",
    infoId: "trx-pagination-info",
    searchId: "trx-filter-search",
    filters: {
      status: "trx-filter-status",
      type: "trx-filter-type",
    },
    renderRow: (trx) => {
      const encodedTrx = encodeURIComponent(JSON.stringify(trx));
      const desc = trx.description || "Transaction";
      const safeDesc = desc
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
      return `
            <tr class="group hover:bg-white/5 transition-all cursor-pointer" onclick="viewTransaction('${encodedTrx}')">
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-lg ${trx.trx_type === "credit" ? "bg-emerald-500/10 text-emerald-500" : "bg-rose-500/10 text-rose-500"} flex items-center justify-center shrink-0">
                            <i data-lucide="${trx.trx_type === "credit" ? "arrow-down-left" : "arrow-up-right"}" class="w-4 h-4"></i>
                        </div>
                        <span class="text-xs font-mono text-slate-400 uppercase">${trx.trx_id ? trx.trx_id.toString().split("-")[0] : "N/A"}</span>
                    </div>
                </td>
                <td class="px-6 py-4 max-w-xs sm:max-w-sm md:max-w-md">
                    <p class="text-sm font-bold text-white truncate" title="${safeDesc}">${desc}</p>
                    <p class="text-[10px] text-slate-500 whitespace-nowrap">${new Date(trx.timestamp).toLocaleString()}</p>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-3 py-1 ${trx.trx_status === "completed" || trx.trx_status === "success" ? "bg-emerald-500/10 text-emerald-500" : "bg-rose-500/10 text-rose-500"} text-[10px] font-bold rounded-full uppercase">${trx.trx_status || "Completed"}</span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="text-xs ${trx.trx_type === "credit" ? "text-emerald-500" : "text-rose-500"} font-bold uppercase">${trx.trx_type || "Debit"}</span>
                </td>
                <td class="px-6 py-4 text-right whitespace-nowrap">
                    <p class="text-sm font-bold text-white">${getUserCurrencySymbol()}${parseFloat(trx.trx_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                </td>
            </tr>
        `;
    },
  });
};

/**
 * Wallet Page Logic
 */
window.initWallet = () => {
  if (!document.getElementById("wallet-transactions-tbody")) return;

  initPaginatedTable({
    endpoint: `${FLEZ_API_BASE}/api/transactions/filter`,
    containerId: "wallet-transactions-tbody",
    prevBtnId: "wallet-trx-prev-btn",
    nextBtnId: "wallet-trx-next-btn",
    infoId: "wallet-trx-pagination-info",
    filters: {
      type: "wallet-trx-filter-type",
      status: "wallet-trx-filter-status",
    },
    renderRow: (trx) => `
            <tr class="group hover:bg-white/5 transition-all">
                <td class="px-6 py-4">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center">
                            <i data-lucide="${trx.trx_type === "credit" ? "arrow-down-left" : "arrow-up-right"}" class="w-5 h-5"></i>
                        </div>
                        <div>
                            <p class="text-sm font-bold text-white capitalize">${trx.trx_type}</p>
                            <p class="text-xs text-slate-500">${new Date(trx.timestamp).toLocaleString()}</p>
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4">
                    <span class="px-3 py-1 bg-emerald-500/10 text-emerald-500 text-[10px] font-bold rounded-full uppercase">${trx.trx_status || "Settled"}</span>
                </td>
                <td class="px-6 py-4 text-right">
                    <p class="text-sm font-bold ${trx.trx_type === "credit" ? "text-emerald-500" : "text-rose-500"}">
                        ${trx.trx_type === "credit" ? "+" : "-"} ${getUserCurrencySymbol()}${parseFloat(trx.trx_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </p>
                </td>
            </tr>
        `,
  });

  // Wallet Stats from LocalData
  const user = JSON.parse(localStorage.getItem("user_data") || "{}");
  const summary = user.sales_summary || {};
  const curSym = getUserCurrencySymbol(user);
  const walletBalance = document.getElementById("stat-wallet-balance");
  if (walletBalance)
    walletBalance.textContent = `${curSym}${(user.balance || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const statNetIncome = document.getElementById("stat-net-income");
  if (statNetIncome)
    statNetIncome.textContent = `${curSym}${(summary.total_sales || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const statPending = document.getElementById("stat-pending-settlements");
  if (statPending)
    statPending.textContent = `${curSym}${(summary.pending_sales || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const statPayouts = document.getElementById("stat-total-payouts");
  if (statPayouts)
    statPayouts.textContent = `${curSym}${(summary.total_payouts || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  // Funding Modal Logic
  // Funding Modal Logic
  const modal = document.getElementById("fund-modal");
  const fundBtn = document.getElementById("fund-btn");
  const closeModal = document.querySelectorAll(".closeModal");
  const methods = document.querySelectorAll("[data-method]");
  const details = document.getElementById("funding-details");

  function getStoredDepositAccount() {
    try {
      const u = JSON.parse(localStorage.getItem("user_data") || "{}");
      if (
        u.deposit_account &&
        u.deposit_account.account_number &&
        u.deposit_account.account_number !== "N/A"
      ) {
        return u.deposit_account;
      }
      if (Array.isArray(u.deposit_details) && u.deposit_details.length > 0) {
        const ownerAcc = u.deposit_details.find(
          (d) => d.account_owner === "owner" && d.account_number,
        );
        if (ownerAcc) return ownerAcc;
        if (u.deposit_details[0].account_number) return u.deposit_details[0];
      }
    } catch (e) {
      console.error("Error parsing user_data for deposit account:", e);
    }
    return null;
  }

  function renderBankAccount(bankDetails) {
    if (!details) return;
    details.innerHTML = `
            <div class="w-full animate-in fade-in zoom-in duration-200">
                <div class="w-full bg-slate-100 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 rounded-2xl p-6 sm:p-7 space-y-5 shadow-sm text-left">
                    <div>
                        <p class="text-[10px] sm:text-xs text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider">Bank Name</p>
                        <p class="text-base sm:text-lg font-bold text-slate-900 dark:text-white mt-1">${bankDetails.bank_name || "Wema Bank (FlezPay)"}</p>
                    </div>
                    <div>
                        <p class="text-[10px] sm:text-xs text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider">Account Name</p>
                        <p class="text-sm sm:text-base font-semibold text-slate-800 dark:text-slate-200 mt-1">${bankDetails.account_name || "FlezPay Merchant"}</p>
                    </div>
                    <div>
                        <p class="text-[10px] sm:text-xs text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider">Account Number</p>
                        <div class="flex items-center justify-between mt-1.5 bg-white dark:bg-black/30 border border-slate-200 dark:border-white/10 px-4 py-3 rounded-xl">
                            <span class="text-xl sm:text-2xl font-display font-bold text-primary tracking-widest">${bankDetails.account_number}</span>
                            <button type="button" id="copy-fund-acc-btn" class="px-3 py-1.5 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary transition-all flex items-center justify-center gap-2 text-xs font-semibold" title="Copy Account Number">
                                <i data-lucide="copy" class="w-4 h-4"></i>
                                <span>Copy</span>
                            </button>
                        </div>
                        <p id="copy-fund-feedback" class="text-xs text-emerald-500 font-medium h-4 mt-1.5 opacity-0 transition-opacity text-right">Copied to clipboard!</p>
                    </div>
                </div>
            </div>
        `;
    if (typeof lucide !== "undefined") lucide.createIcons();

    const copyBtn = details.querySelector("#copy-fund-acc-btn");
    if (copyBtn) {
      copyBtn.onclick = () => {
        const accNo = String(bankDetails.account_number);
        if (navigator.clipboard && window.isSecureContext) {
          navigator.clipboard
            .writeText(accNo)
            .then(showCopied)
            .catch(fallbackCopy);
        } else {
          fallbackCopy();
        }
        function showCopied() {
          const fb = details.querySelector("#copy-fund-feedback");
          if (fb) {
            fb.classList.remove("opacity-0");
            setTimeout(() => fb.classList.add("opacity-0"), 2000);
          }
        }
        function fallbackCopy() {
          const temp = document.createElement("textarea");
          temp.value = accNo;
          document.body.appendChild(temp);
          temp.select();
          document.execCommand("copy");
          document.body.removeChild(temp);
          showCopied();
        }
      };
    }
  }

  async function loadOrGenerateBankDetails() {
    if (!details) return;
    details.classList.remove("hidden");

    // Check if existing deposit account exists
    const existing = getStoredDepositAccount();
    if (existing) {
      renderBankAccount(existing);
      return;
    }

    // Show generating state with animated spinner
    details.innerHTML = `
            <div class="text-center py-10 w-full max-w-sm mx-auto animate-in fade-in duration-200">
                <div class="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin mx-auto mb-4"></div>
                <h4 class="text-base font-bold text-slate-900 dark:text-white">Generating Dedicated Virtual Account...</h4>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs mx-auto">Connecting to our banking infrastructure to issue your permanent deposit details.</p>
            </div>
        `;

    try {
      const token = localStorage.getItem("access_token");
      const res = window.apiFetch
        ? await window.apiFetch("/api/user/add/depositBank", {
            method: "POST",
            body: JSON.stringify({}),
          })
        : await fetch("/api/user/add/depositBank", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({}),
          });

      const resData = await res.json();
      if (resData && (resData.status || resData.data)) {
        const acc = resData.data;
        if (acc && acc.account_number) {
          try {
            const u = JSON.parse(localStorage.getItem("user_data") || "{}");
            u.deposit_account = acc;
            if (!Array.isArray(u.deposit_details)) u.deposit_details = [];
            u.deposit_details = [
              acc,
              ...u.deposit_details.filter(
                (d) => d.account_number !== acc.account_number,
              ),
            ];
            localStorage.setItem("user_data", JSON.stringify(u));
          } catch (e) {
            console.error(
              "Error saving updated deposit account to localStorage:",
              e,
            );
          }
          renderBankAccount(acc);
          return;
        }
      }
      throw new Error(resData?.message || "Unable to generate bank details");
    } catch (err) {
      console.error("Error in loadOrGenerateBankDetails:", err);
      details.innerHTML = `
                <div class="text-center py-8 w-full max-w-sm mx-auto">
                    <div class="w-12 h-12 bg-rose-500/10 text-rose-500 rounded-full flex items-center justify-center mx-auto mb-3">
                        <i data-lucide="alert-circle" class="w-6 h-6"></i>
                    </div>
                    <h4 class="text-sm font-bold text-slate-900 dark:text-white">Failed to Generate Account</h4>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs mx-auto">${err.message || "Please check your connection and try again."}</p>
                    <button id="retry-fund-gen-btn" class="mt-4 px-4 py-2 bg-primary text-black font-bold text-xs rounded-xl hover:bg-primary/90 transition-all shadow-md">
                        Retry Generation
                    </button>
                </div>
            `;
      if (typeof lucide !== "undefined") lucide.createIcons();
      const retryBtn = details.querySelector("#retry-fund-gen-btn");
      if (retryBtn) retryBtn.onclick = () => loadOrGenerateBankDetails();
    }
  }

  let selectedCryptoAssetIndex = 0;
  let selectedCryptoChainIndex = 0;
  window._cryptoWalletsCache = window._cryptoWalletsCache || {};

  const CRYPTO_ICONS_FALLBACK = {
    BTC: "https://assets.coingecko.com/coins/images/1/small/bitcoin.png",
    BITCOIN: "https://assets.coingecko.com/coins/images/1/small/bitcoin.png",
    USDC: "https://assets.coingecko.com/coins/images/6319/small/USD_Coin_favicon.ico",
    "CIRCLE USDC":
      "https://assets.coingecko.com/coins/images/6319/small/USD_Coin_favicon.ico",
    XLM: "https://assets.coingecko.com/coins/images/100/small/Stellar_symbol_black_RGB.png",
    STELLAR:
      "https://assets.coingecko.com/coins/images/100/small/Stellar_symbol_black_RGB.png",
    "STELLAR XLM":
      "https://assets.coingecko.com/coins/images/100/small/Stellar_symbol_black_RGB.png",
    SOL: "https://assets.coingecko.com/coins/images/4128/small/solana.png",
    SOLANA: "https://assets.coingecko.com/coins/images/4128/small/solana.png",
    "SOL-DEVNET":
      "https://assets.coingecko.com/coins/images/4128/small/solana.png",
    MATIC: "https://assets.coingecko.com/coins/images/4713/small/polygon.png",
    POLYGON: "https://assets.coingecko.com/coins/images/4713/small/polygon.png",
    "POLYGON ":
      "https://assets.coingecko.com/coins/images/4713/small/polygon.png",
    "MATIC-AMOY":
      "https://assets.coingecko.com/coins/images/4713/small/polygon.png",
  };

  function getCryptoIcon(key, defaultUrl) {
    const k = String(key || "")
      .trim()
      .toUpperCase();
    if (CRYPTO_ICONS_FALLBACK[k]) return CRYPTO_ICONS_FALLBACK[k];
    return (
      defaultUrl ||
      "https://assets.coingecko.com/coins/images/1/small/bitcoin.png"
    );
  }

  async function fetchCryptoAssets() {
    if (window._cryptoAssetsCache && window._cryptoAssetsCache.length > 0) {
      return window._cryptoAssetsCache;
    }
    try {
      const u = JSON.parse(localStorage.getItem("user_data") || "{}");
      if (Array.isArray(u.crypto_assets) && u.crypto_assets.length > 0) {
        window._cryptoAssetsCache = u.crypto_assets;
        return window._cryptoAssetsCache;
      }
    } catch (e) {}

    try {
      const token = localStorage.getItem("access_token");
      const res = window.apiFetch
        ? await window.apiFetch("/api/crypto/wallet", { method: "GET" })
        : await fetch("/api/crypto/wallet", {
            method: "GET",
            headers: {
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
          });
      const resData = await res.json();
      if (
        resData.status &&
        Array.isArray(resData.data) &&
        resData.data.length > 0
      ) {
        window._cryptoAssetsCache = resData.data;
        return window._cryptoAssetsCache;
      }
    } catch (e) {
      console.error("Error fetching crypto assets:", e);
    }
    return [];
  }

  async function renderCryptoDetails() {
    if (!details) return;
    details.classList.remove("hidden");

    // Loading state while fetching backend assets
    details.innerHTML = `
            <div class="text-center py-12 w-full animate-in fade-in duration-200">
                <div class="w-10 h-10 border-4 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin mx-auto mb-3"></div>
                <p class="text-sm font-semibold text-slate-800 dark:text-slate-200">Loading Supported Crypto Assets...</p>
            </div>
        `;

    const assets = await fetchCryptoAssets();
    if (!assets || assets.length === 0) {
      details.innerHTML = `
                <div class="text-center py-10 w-full animate-in fade-in duration-200">
                    <div class="w-12 h-12 bg-amber-500/10 text-amber-500 rounded-full flex items-center justify-center mx-auto mb-3">
                        <i data-lucide="alert-triangle" class="w-6 h-6"></i>
                    </div>
                    <h4 class="text-sm font-bold text-slate-900 dark:text-white">No Crypto Assets Available</h4>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">Please try again later or use Bank Transfer.</p>
                </div>
            `;
      if (typeof lucide !== "undefined") lucide.createIcons();
      return;
    }

    if (selectedCryptoAssetIndex >= assets.length) selectedCryptoAssetIndex = 0;
    const currentAsset = assets[selectedCryptoAssetIndex];
    const chains = Array.isArray(currentAsset.chains)
      ? currentAsset.chains
      : [];
    if (selectedCryptoChainIndex >= chains.length) selectedCryptoChainIndex = 0;
    const currentChain = chains[selectedCryptoChainIndex] || {
      id: currentAsset.asset_id,
      name: currentAsset.name,
    };

    // Render Asset & Chain Selector Header (Smaller, mobile responsive with genuine images)
    details.innerHTML = `
            <div class="w-full animate-in fade-in zoom-in duration-200 space-y-4">
                <!-- Asset Selector -->
                <div>
                    <label class="block text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">Select Asset</label>
                    <div class="flex flex-wrap items-center gap-1.5 sm:gap-2" id="crypto-assets-selector">
                        ${assets
                          .map((ast, idx) => {
                            const iconUrl = getCryptoIcon(
                              ast.asset_id,
                              ast.icon,
                            );
                            const isSelected = idx === selectedCryptoAssetIndex;
                            return `
                                <button type="button" data-asset-idx="${idx}" class="crypto-asset-pill px-2.5 py-1.5 rounded-xl border text-xs flex items-center gap-2 transition-all shrink-0 ${isSelected ? "border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shadow-sm font-bold ring-1 ring-emerald-500/30" : "border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/[0.02] text-slate-700 dark:text-slate-300 hover:border-emerald-500/40"}">
                                    <img src="${iconUrl}" class="w-4 h-4 rounded-full object-contain shrink-0" alt="${ast.name}" onerror="this.onerror=null; this.src='https://assets.coingecko.com/coins/images/1/small/bitcoin.png'">
                                    <span class="truncate">${ast.name}</span>
                                    <span class="text-[10px] font-mono opacity-60">(${ast.asset_id})</span>
                                </button>
                            `;
                          })
                          .join("")}
                    </div>
                </div>

                <!-- Network / Chain Selector -->
                ${
                  chains.length > 1
                    ? `
                    <div>
                        <label class="block text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">Select Network</label>
                        <div class="flex flex-wrap items-center gap-1.5 sm:gap-2" id="crypto-chains-selector">
                            ${chains
                              .map((chn, cIdx) => {
                                const chainIconUrl = getCryptoIcon(
                                  chn.id || chn.name,
                                  chn.icon,
                                );
                                const isSelected =
                                  cIdx === selectedCryptoChainIndex;
                                return `
                                    <button type="button" data-chain-idx="${cIdx}" class="crypto-chain-pill px-2.5 py-1 rounded-lg border text-xs flex items-center gap-1.5 transition-all font-semibold shrink-0 ${isSelected ? "border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shadow-sm font-bold ring-1 ring-emerald-500/30" : "border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/[0.02] text-slate-600 dark:text-slate-400 hover:border-emerald-500/40"}">
                                        <img src="${chainIconUrl}" class="w-3.5 h-3.5 rounded-full object-contain shrink-0" alt="${chn.name}" onerror="this.onerror=null; this.src='https://assets.coingecko.com/coins/images/1/small/bitcoin.png'">
                                        <span class="truncate">${chn.name.trim()}</span>
                                    </button>
                                `;
                              })
                              .join("")}
                        </div>
                    </div>
                `
                    : `
                    <div class="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                        <span class="text-[10px] font-bold uppercase tracking-wider">Network:</span>
                        <div class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 text-xs font-semibold text-slate-800 dark:text-slate-200">
                            <img src="${getCryptoIcon(currentChain.id || currentChain.name, currentChain.icon)}" class="w-3.5 h-3.5 rounded-full object-contain shrink-0" alt="${currentChain.name}">
                            <span>${(currentChain.name || currentAsset.name).trim()}</span>
                        </div>
                    </div>
                `
                }

                <!-- Wallet Address & QR Area -->
                <div id="crypto-wallet-display" class="w-full bg-slate-100 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 rounded-2xl p-4 sm:p-5 shadow-sm">
                    <div class="text-center py-6">
                        <div class="w-8 h-8 border-3 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin mx-auto mb-2"></div>
                        <p class="text-xs text-slate-500 dark:text-slate-400">Generating deposit address...</p>
                    </div>
                </div>
            </div>
        `;
    if (typeof lucide !== "undefined") lucide.createIcons();

    // Wire asset selector buttons
    details.querySelectorAll(".crypto-asset-pill").forEach((btn) => {
      btn.onclick = () => {
        const idx = parseInt(btn.getAttribute("data-asset-idx"), 10);
        if (idx !== selectedCryptoAssetIndex) {
          selectedCryptoAssetIndex = idx;
          selectedCryptoChainIndex = 0;
          renderCryptoDetails();
        }
      };
    });

    // Wire chain selector buttons
    details.querySelectorAll(".crypto-chain-pill").forEach((btn) => {
      btn.onclick = () => {
        const cIdx = parseInt(btn.getAttribute("data-chain-idx"), 10);
        if (cIdx !== selectedCryptoChainIndex) {
          selectedCryptoChainIndex = cIdx;
          renderCryptoDetails();
        }
      };
    });

    // Fetch / display wallet address for current asset & chain
    loadCryptoAddress(currentAsset, currentChain);
  }

  async function loadCryptoAddress(asset, chain) {
    const displayEl = document.getElementById("crypto-wallet-display");
    if (!displayEl) return;

    const chainParam = chain.id || chain.chain_id || asset.asset_id;
    const cacheKey = `${asset.asset_id}_${chainParam}`;
    let walletData = window._cryptoWalletsCache[cacheKey];

    if (!walletData) {
      displayEl.innerHTML = `
                <div class="text-center py-8">
                    <div class="w-8 h-8 border-3 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin mx-auto mb-3"></div>
                    <p class="text-xs font-semibold text-slate-700 dark:text-slate-300">Retrieving dedicated deposit address...</p>
                    <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">Connecting to ${chain.name || asset.name} node</p>
                </div>
            `;
      try {
        const token = localStorage.getItem("access_token");
        const res = window.apiFetch
          ? await window.apiFetch("/api/crypto/wallet", {
              method: "POST",
              body: JSON.stringify({
                asset: asset.asset_id,
                chain: chainParam,
              }),
            })
          : await fetch("/api/crypto/wallet", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
              },
              body: JSON.stringify({
                asset: asset.asset_id,
                chain: chainParam,
              }),
            });
        const resData = await res.json();
        if (resData.status && resData.data && resData.data.wallet) {
          walletData = resData.data;
          window._cryptoWalletsCache[cacheKey] = walletData;
        } else {
          throw new Error(resData.message || "Could not retrieve address");
        }
      } catch (err) {
        console.error("Error fetching crypto address:", err);
        displayEl.innerHTML = `
                    <div class="text-center py-6">
                        <div class="w-10 h-10 bg-rose-500/10 text-rose-500 rounded-full flex items-center justify-center mx-auto mb-2">
                            <i data-lucide="alert-circle" class="w-5 h-5"></i>
                        </div>
                        <p class="text-xs font-bold text-slate-800 dark:text-slate-200">Unable to generate ${asset.name} address</p>
                        <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-1 max-w-xs mx-auto">${err.message || "Network error"}</p>
                        <button id="retry-crypto-btn" class="mt-3 px-3 py-1.5 bg-emerald-500 text-white text-xs font-semibold rounded-lg hover:bg-emerald-600 transition-all">
                            Retry
                        </button>
                    </div>
                `;
        if (typeof lucide !== "undefined") lucide.createIcons();
        const retryBtn = displayEl.querySelector("#retry-crypto-btn");
        if (retryBtn) retryBtn.onclick = () => loadCryptoAddress(asset, chain);
        return;
      }
    }

    const address = walletData.wallet;
    const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(address)}`;

    displayEl.innerHTML = `
            <div class="space-y-4">
                <div class="flex flex-col sm:flex-row items-center sm:items-start gap-4 sm:gap-5">
                    <div class="w-28 h-28 sm:w-32 sm:h-32 bg-white rounded-xl p-2 shrink-0 flex items-center justify-center overflow-hidden shadow-md border border-slate-200 dark:border-white/10">
                        <img src="${qrUrl}" class="w-full h-full object-contain" alt="${asset.name} Deposit QR">
                    </div>
                    <div class="flex-1 min-w-0 w-full text-center sm:text-left space-y-2.5">
                        <div>
                            <div class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[10px] font-bold uppercase tracking-wider">
                                <img src="${getCryptoIcon(asset.asset_id, asset.icon)}" class="w-3.5 h-3.5 rounded-full object-contain">
                                <span>${asset.name} • ${(chain.name || asset.name).trim()}</span>
                            </div>
                            <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">Scan the QR code or copy the address below to deposit.</p>
                        </div>

                        <div>
                            <p class="text-[10px] sm:text-xs text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider mb-1.5">Deposit Wallet Address</p>
                            <div class="flex items-stretch rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-black/30 overflow-hidden shadow-sm focus-within:border-emerald-500 transition-colors">
                                <input type="text" id="crypto-addr-input" readonly value="${address}" class="w-full min-w-0 bg-transparent px-3 py-2 text-xs font-mono text-slate-800 dark:text-slate-200 focus:outline-none select-all font-semibold" title="Click to copy full address">
                                <button type="button" id="copy-crypto-addr-btn" class="px-3.5 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 transition-colors flex items-center justify-center gap-1.5 text-xs font-semibold shrink-0 border-l border-slate-200 dark:border-white/10" title="Copy Address">
                                    <i data-lucide="copy" class="w-3.5 h-3.5"></i>
                                    <span>Copy</span>
                                </button>
                            </div>
                            <div class="flex items-center justify-between mt-1 px-0.5">
                                <span class="text-[10px] text-slate-400 dark:text-slate-500">Click address or button to copy</span>
                                <p id="copy-crypto-feedback" class="text-[11px] text-emerald-500 font-semibold opacity-0 transition-opacity">Copied to clipboard!</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl flex items-start gap-2.5">
                    <i data-lucide="alert-triangle" class="w-4 h-4 text-amber-500 shrink-0 mt-0.5"></i>
                    <p class="text-[11px] text-amber-700 dark:text-amber-300 leading-snug">
                        Send only <strong>${asset.name}</strong> via the <strong>${(chain.name || asset.name).trim()}</strong> network to this address. Sending any other asset or via an unsupported network may result in permanent loss.
                    </p>
                </div>
            </div>
        `;
    if (typeof lucide !== "undefined") lucide.createIcons();

    const copyBtn = displayEl.querySelector("#copy-crypto-addr-btn");
    const addrInput = displayEl.querySelector("#crypto-addr-input");

    const doCopy = () => {
      if (addrInput) addrInput.select();
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard
          .writeText(address)
          .then(showCopied)
          .catch(fallbackCopy);
      } else {
        fallbackCopy();
      }
      function showCopied() {
        const fb = displayEl.querySelector("#copy-crypto-feedback");
        if (fb) {
          fb.classList.remove("opacity-0");
          setTimeout(() => fb.classList.add("opacity-0"), 2000);
        }
      }
      function fallbackCopy() {
        if (addrInput) {
          addrInput.select();
          document.execCommand("copy");
        } else {
          const temp = document.createElement("textarea");
          temp.value = address;
          document.body.appendChild(temp);
          temp.select();
          document.execCommand("copy");
          document.body.removeChild(temp);
        }
        showCopied();
      }
    };

    if (copyBtn) copyBtn.onclick = doCopy;
    if (addrInput) addrInput.onclick = doCopy;
  }

  function selectFundingMethod(methodType) {
    methods.forEach((m) => {
      if (m.getAttribute("data-method") === methodType) {
        m.classList.add("active-method", "border-primary/50", "bg-primary/5");
      } else {
        m.classList.remove(
          "active-method",
          "border-primary/50",
          "bg-primary/5",
        );
      }
    });
    if (methodType === "bank") {
      loadOrGenerateBankDetails();
    } else {
      renderCryptoDetails();
    }
  }

  function openFundModal() {
    if (modal) {
      modal.classList.remove("hidden");
      selectFundingMethod("bank");
    }
  }

  if (fundBtn && modal) {
    fundBtn.onclick = () => openFundModal();
  }

  if (closeModal.length > 0) {
    closeModal.forEach((btn) => {
      btn.onclick = () => {
        if (modal) modal.classList.add("hidden");
        if (details) details.classList.add("hidden");
      };
    });
  }

  if (methods.length > 0) {
    methods.forEach((method) => {
      method.onclick = function () {
        const type = this.getAttribute("data-method");
        selectFundingMethod(type);
      };
    });
  }

  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("action") === "fund" && modal) {
    setTimeout(() => openFundModal(), 300);
  }

  // Withdraw Modal Logic
  const withdrawModal = document.getElementById("withdraw-modal");
  const withdrawBtn = document.getElementById("withdraw-btn");
  const closeWithdrawModal = document.querySelectorAll(".closeWithdrawModal");

  if (urlParams.get("action") === "withdraw" && withdrawBtn) {
    // Use timeout to ensure all stats/users are loaded before clicking
    setTimeout(() => withdrawBtn.click(), 500);
  }

  if (withdrawBtn && withdrawModal) {
    if (user && user.withdrawals_disabled) {
      withdrawBtn.classList.add("opacity-60");
      withdrawBtn.setAttribute(
        "title",
        "Withdrawals are temporarily disabled for your account",
      );
    }

    withdrawBtn.onclick = () => {
      if (user && user.withdrawals_disabled) {
        Swal.fire({
          icon: "warning",
          title: "Withdrawals Disabled",
          text: "Withdrawals have been temporarily disabled for your account. Please contact support for assistance.",
          background: "var(--swal-bg)",
          color: "var(--swal-text)",
          confirmButtonColor: "#cfff45",
        });
        return;
      }

      const availBal = document.getElementById("withdraw-available-balance");
      const maxText = document.getElementById("withdraw-max-text");
      const minText = document.getElementById("withdraw-min-text");
      const curSym = getUserCurrencySymbol(user);
      const minWithdrawal =
        user && user.min_withdrawal_amount !== undefined
          ? user.min_withdrawal_amount
          : 100;
      if (availBal)
        availBal.textContent = `${curSym}${(user.balance || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      if (maxText)
        maxText.textContent = `Max: ${curSym}${(user.balance || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      if (minText)
        minText.textContent = `Min: ${curSym}${minWithdrawal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

      const accList = document.getElementById("withdraw-accounts-list");
      if (accList) {
        window.selectedWithdrawAccount = null;
        window.selectWithdrawAccount = (idx) => {
          window.selectedWithdrawAccount = user.withdrawal_accounts[idx];
          document
            .querySelectorAll(".withdraw-account-card")
            .forEach((el, i) => {
              const checkIcon = el.querySelector(".check-circle-icon");
              if (i === idx) {
                el.classList.add("border-primary", "bg-primary/5");
                el.classList.remove(
                  "border-slate-200",
                  "dark:border-white/10",
                  "bg-slate-100",
                  "dark:bg-white/5",
                );
                if (checkIcon) checkIcon.classList.remove("opacity-0");
              } else {
                el.classList.remove("border-primary", "bg-primary/5");
                el.classList.add(
                  "border-slate-200",
                  "dark:border-white/10",
                  "bg-slate-100",
                  "dark:bg-white/5",
                );
                if (checkIcon) checkIcon.classList.add("opacity-0");
              }
            });
        };

        let html = "";
        if (user.withdrawal_accounts && user.withdrawal_accounts.length > 0) {
          user.withdrawal_accounts.forEach((acc, idx) => {
            html += `
                            <div class="withdraw-account-card p-4 rounded-2xl bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 hover:border-primary/50 flex items-center gap-4 cursor-pointer transition-all" onclick="selectWithdrawAccount(${idx})">
                                <div class="w-10 h-10 bg-primary/20 rounded-full flex items-center justify-center text-primary shrink-0">
                                    <i data-lucide="building"></i>
                                </div>
                                <div class="flex-1">
                                    <p class="text-sm font-bold text-slate-900 dark:text-white">${acc.bank_name}</p>
                                    <p class="text-xs text-slate-500 dark:text-slate-400">${acc.account_number} • ${acc.account_name || "FlezPay"}</p>
                                </div>
                                <div class="check-circle-icon w-6 h-6 rounded-full bg-primary text-black flex items-center justify-center opacity-0 transition-opacity">
                                    <i data-lucide="check" class="w-4 h-4"></i>
                                </div>
                            </div>
                        `;
          });
        }
        html += `
                    <div class="p-4 rounded-2xl bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 hover:bg-slate-200 dark:hover:bg-white/10 flex items-center gap-4 cursor-pointer transition-all" onclick="window.location.href='/settings#withdrawals'">
                        <div class="w-10 h-10 bg-slate-200 dark:bg-white/10 rounded-full flex items-center justify-center text-slate-500 dark:text-slate-400">
                            <i data-lucide="plus"></i>
                        </div>
                        <p class="text-sm font-bold text-slate-600 dark:text-slate-400">Manage Bank Accounts</p>
                    </div>
                `;
        accList.innerHTML = html;
      }

      const processBtn = document.getElementById("process-withdraw-btn");
      if (processBtn) {
        if (user && user.withdrawals_disabled) {
          processBtn.disabled = true;
          processBtn.classList.add("opacity-50", "cursor-not-allowed");
          processBtn.innerHTML =
            '<i class="lucide-lock w-5 h-5"></i> Withdrawals Disabled';
          const noticeEl = document.getElementById("withdraw-disabled-notice");
          if (!noticeEl) {
            const alertDiv = document.createElement("div");
            alertDiv.id = "withdraw-disabled-notice";
            alertDiv.className =
              "p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm font-medium flex items-center gap-3 mb-6";
            alertDiv.innerHTML =
              '<i class="lucide-alert-triangle w-5 h-5 shrink-0 text-rose-400"></i> Withdrawals have been temporarily disabled for your account. Please contact support for assistance.';
            processBtn.parentNode.insertBefore(alertDiv, processBtn);
          }
          if (typeof lucide !== "undefined") lucide.createIcons();
          return;
        }

        const amountInput = document.getElementById("withdraw-amount-input");
        if (amountInput && !amountInput.hasAttribute("data-formatted")) {
          amountInput.setAttribute("data-formatted", "true");
          amountInput.addEventListener("input", function () {
            let val = this.value.replace(/[^\d.]/g, "");
            let parts = val.split(".");
            if (parts.length > 2) {
              parts = [parts[0], parts.slice(1).join("")];
            }
            if (parts[0]) {
              parts[0] = parseInt(parts[0], 10).toLocaleString("en-US");
            }
            this.value = parts.join(".");
          });
        }

        processBtn.onclick = async () => {
          const rawAmount = amountInput.value.replace(/,/g, "");
          const amount = parseFloat(rawAmount);

          if (!amount || amount <= 0) {
            Swal.fire({
              toast: true,
              position: "top-end",
              icon: "error",
              title: "Please enter a valid amount to withdraw.",
              showConfirmButton: false,
              timer: 3000,
              background: "var(--swal-bg)",
              color: "var(--swal-text)",
            });
            return;
          }

          const minWithdrawal =
            user && user.min_withdrawal_amount !== undefined
              ? user.min_withdrawal_amount
              : 100;
          if (amount < minWithdrawal) {
            Swal.fire({
              toast: true,
              position: "top-end",
              icon: "error",
              title: `Minimum withdrawal amount is ${curSym}${minWithdrawal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}.`,
              showConfirmButton: false,
              timer: 3500,
              background: "var(--swal-bg)",
              color: "var(--swal-text)",
            });
            return;
          }

          if (!window.selectedWithdrawAccount) {
            Swal.fire({
              toast: true,
              position: "top-end",
              icon: "error",
              title: "Please select a destination account.",
              showConfirmButton: false,
              timer: 3000,
              background: "var(--swal-bg)",
              color: "var(--swal-text)",
            });
            return;
          }

          const originalBtnHtml = processBtn.innerHTML;
          processBtn.disabled = true;
          processBtn.innerHTML =
            '<i class="lucide-loader w-5 h-5 animate-spin"></i> Processing...';

          try {
            const pinReq = await apiFetch(
              `${window.FLEZ_API_BASE || ""}/api/auth/trx/pin`,
              { method: "POST" },
            );
            const pinRes = await pinReq.json();
            if (!pinRes.status)
              throw new Error(pinRes.message || "Failed to request PIN");

            const { value: pin } = await Swal.fire({
              title: "Enter Verification PIN",
              text: "A 6-digit PIN has been sent to your email.",
              html: `
                                <div class="flex justify-center gap-2 my-4" id="pinput-container">
                                    <input type="text" inputmode="numeric" maxlength="1" class="w-12 h-14 text-center text-xl font-bold bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-xl focus:border-primary focus:outline-none dark:text-white transition-all" />
                                    <input type="text" inputmode="numeric" maxlength="1" class="w-12 h-14 text-center text-xl font-bold bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-xl focus:border-primary focus:outline-none dark:text-white transition-all" />
                                    <input type="text" inputmode="numeric" maxlength="1" class="w-12 h-14 text-center text-xl font-bold bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-xl focus:border-primary focus:outline-none dark:text-white transition-all" />
                                    <input type="text" inputmode="numeric" maxlength="1" class="w-12 h-14 text-center text-xl font-bold bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-xl focus:border-primary focus:outline-none dark:text-white transition-all" />
                                    <input type="text" inputmode="numeric" maxlength="1" class="w-12 h-14 text-center text-xl font-bold bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-xl focus:border-primary focus:outline-none dark:text-white transition-all" />
                                    <input type="text" inputmode="numeric" maxlength="1" class="w-12 h-14 text-center text-xl font-bold bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-xl focus:border-primary focus:outline-none dark:text-white transition-all" />
                                </div>
                            `,
              showCancelButton: true,
              confirmButtonColor: "#cfff45",
              background: "var(--swal-bg)",
              color: "var(--swal-text)",
              didOpen: () => {
                const inputs = document.querySelectorAll(
                  "#pinput-container input",
                );
                if (inputs.length) inputs[0].focus();
                inputs.forEach((input, index) => {
                  input.addEventListener("input", (e) => {
                    e.target.value = e.target.value.replace(/[^0-9]/g, "");
                    if (e.target.value && index < inputs.length - 1) {
                      inputs[index + 1].focus();
                    }
                  });
                  input.addEventListener("keydown", (e) => {
                    if (e.key === "Backspace" && !e.target.value && index > 0) {
                      inputs[index - 1].focus();
                    }
                  });
                  input.addEventListener("paste", (e) => {
                    e.preventDefault();
                    const pastedData = e.clipboardData
                      .getData("text")
                      .replace(/[^0-9]/g, "")
                      .slice(0, 6);
                    pastedData.split("").forEach((char, i) => {
                      if (inputs[i]) inputs[i].value = char;
                    });
                    if (pastedData.length > 0) {
                      inputs[Math.min(pastedData.length, 5)].focus();
                    }
                  });
                });
              },
              preConfirm: () => {
                const inputs = document.querySelectorAll(
                  "#pinput-container input",
                );
                const pin = Array.from(inputs)
                  .map((i) => i.value)
                  .join("");
                if (pin.length !== 6) {
                  Swal.showValidationMessage(
                    "Please enter a valid 6-digit PIN",
                  );
                  return false;
                }
                return pin;
              },
            });

            if (pin) {
              processBtn.innerHTML =
                '<i class="lucide-loader w-5 h-5 animate-spin"></i> Finalizing...';
              const withdrawReq = await apiFetch(
                `${window.FLEZ_API_BASE || ""}/api/user/transactions/withdraw`,
                {
                  method: "POST",
                  body: JSON.stringify({
                    amount: amount,
                    id: window.selectedWithdrawAccount.uniq_id,
                    pin: pin,
                  }),
                },
              );
              const withdrawRes = await withdrawReq.json();

              if (withdrawRes.status) {
                Swal.fire({
                  icon: "success",
                  title: "Withdrawal Successful!",
                  text: withdrawRes.message || "Your funds are on the way.",
                  background: "var(--swal-bg)",
                  color: "var(--swal-text)",
                }).then(() => {
                  window.location.reload();
                });
              } else {
                throw new Error(withdrawRes.message || "Withdrawal failed");
              }
            }
          } catch (err) {
            console.error("Withdrawal error:", err);
            Swal.fire({
              icon: "error",
              title: "Withdrawal Failed",
              text: err.message || "Something went wrong",
              background: "var(--swal-bg)",
              color: "var(--swal-text)",
            });
          } finally {
            processBtn.disabled = false;
            processBtn.innerHTML = originalBtnHtml;
            if (typeof lucide !== "undefined") lucide.createIcons();
          }
        };
      }
      if (typeof lucide !== "undefined") lucide.createIcons();
      withdrawModal.classList.remove("hidden");
    };
  }

  if (closeWithdrawModal.length > 0) {
    closeWithdrawModal.forEach((btn) => {
      btn.onclick = () => {
        if (withdrawModal) withdrawModal.classList.add("hidden");
      };
    });
  }
};

/**
 * Dashboard Overview Charts
 */
function initDashboardCharts() {
  if (typeof Chart === "undefined") return;
  const rawData = localStorage.getItem("user_data");
  if (!rawData) return;
  const user = JSON.parse(rawData);
  const summary = user.sales_summary || {};

  const isDark = document.documentElement.classList.contains("dark");
  const textColor = isDark ? "rgba(255,255,255,0.3)" : "rgba(15, 23, 42, 0.5)";
  const gridColor = isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)";

  // 1. Revenue Chart
  const monthlySales = summary.monthly_sales || {};
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  const chartData = months.map((m) => monthlySales[m] || 0);

  const revenueCanvas = document.getElementById("revenueChart");
  if (revenueCanvas && typeof Chart !== "undefined") {
    if (window.flezCharts.revenue) window.flezCharts.revenue.destroy();

    const ctxRevenue = revenueCanvas.getContext("2d");
    window.flezCharts.revenue = new Chart(ctxRevenue, {
      type: "line",
      data: {
        labels: months,
        datasets: [
          {
            label: "Revenue",
            data: chartData,
            borderColor: isDark ? "#cfff45" : "#29594b",
            backgroundColor: isDark ? "rgba(207, 255, 69, 0.12)" : "rgba(41, 89, 75, 0.12)",
            borderWidth: 3,
            fill: true,
            tension: 0.4,
            pointRadius: 2,
            pointHoverRadius: 5,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) =>
                `${getUserCurrencySymbol()}${context.parsed.y.toLocaleString()}`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: textColor, font: { size: 10 } },
          },
          y: {
            grid: { color: gridColor },
            ticks: {
              color: textColor,
              font: { size: 10 },
              callback: (v) => getUserCurrencySymbol() + v.toLocaleString(),
            },
          },
        },
      },
    });
  }

  // 2. Inventory Health Chart
  const inventoryCanvas = document.getElementById("inventoryChart");
  if (inventoryCanvas && typeof Chart !== "undefined") {
    if (window.flezCharts.inventory) window.flezCharts.inventory.destroy();

    const invData = summary.inventory_by_category || {};
    const labels = Object.keys(invData);
    const data = Object.values(invData);

    const ctxInventory = inventoryCanvas.getContext("2d");
    window.flezCharts.inventory = new Chart(ctxInventory, {
      type: "doughnut",
      data: {
        labels: labels.length ? labels : ["No Stock"],
        datasets: [
          {
            data: data.length ? data : [1],
            backgroundColor: [
              isDark ? "#cfff45" : "#29594b",
              "#3b82f6",
              "#a855f7",
              "#f97316",
              "#ec4899",
              "#06b6d4",
            ],
            borderWidth: 0,
            hoverOffset: 10,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "75%",
        plugins: { legend: { display: false } },
      },
    });

    // Update Dynamic Legend
    const legendContainer = document.querySelector(".mt-8.space-y-4");
    if (legendContainer && labels.length) {
      const colors = [
        "bg-primary",
        "bg-blue-500",
        "bg-purple-500",
        "bg-orange-500",
        "bg-pink-500",
        "bg-cyan-500",
      ];
      legendContainer.innerHTML = labels
        .map(
          (label, i) => `
                <div class="flex items-center justify-between text-xs">
                  <div class="flex items-center gap-2">
                    <div class="w-3 h-3 ${colors[i % colors.length]} rounded-sm"></div>
                    <span class="text-slate-400">${label}</span>
                  </div>
                  <span class="font-bold text-white">${invData[label].toLocaleString()} units</span>
                </div>
            `,
        )
        .join("");
    }
  }
}

/**
 * Analytics Stats
 */
function initAnalyticsStats() {
  const rawData = localStorage.getItem("user_data");
  if (!rawData) return;
  const user = JSON.parse(rawData);
  const summary = user.sales_summary || {};

  const curSym = getUserCurrencySymbol(user);
  const avgOrder = document.getElementById("stat-avg-order-value");
  if (avgOrder)
    avgOrder.textContent = `${curSym}${(summary.average_order_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const profitMargin = document.getElementById("stat-profit-margin");
  if (profitMargin)
    profitMargin.textContent = `${(summary.profit_margin || 0).toFixed(1)}%`;

  const turnover = document.getElementById("stat-inventory-turnover");
  if (turnover)
    turnover.textContent = `${(summary.inventory_turnover || 0).toFixed(1)}x`;

  const retention = document.getElementById("stat-retention-rate");
  if (retention)
    retention.textContent = `${(summary.customer_retention || 0).toFixed(1)}%`;

  // Now populate change indicators
  updateAnalyticsStats();
}

/**
 * Updates analytics stat change indicators. Called on init and on every date filter change.
 * Derives period-scoped metrics from invoice data in localStorage and updates all 4 analytics stat cards.
 */
window.updateAnalyticsStats = function () {
  const rawData = localStorage.getItem("user_data");
  if (!rawData) return;
  const user = JSON.parse(rawData);
  const summary = user.sales_summary || {};

  // --- Helper to render a change indicator element ---
  function renderChange(el, change, suffix = "%", isAbsolute = false) {
    if (!el) return;
    const up = change >= 0;
    const sign = up ? "+" : "";
    const displayVal = isAbsolute
      ? `${sign}${Math.abs(change).toFixed(1)}${suffix}`
      : `${sign}${change.toFixed(1)}${suffix}`;
    el.className = `text-xs mt-1 flex items-center gap-1 ${up ? "text-emerald-400" : "text-rose-400"}`;
    el.innerHTML = `<i data-lucide="${up ? "trending-up" : "trending-down"}" class="w-3 h-3"></i> ${displayVal} vs last month`;
    if (typeof lucide !== "undefined") lucide.createIcons();
  }

  // --- Compute period-scoped metrics from invoice data ---
  const dateFilter = document.querySelector(
    'select[onchange*="handleDateFilterChange"]',
  );
  const filterVal = dateFilter ? dateFilter.value : "year";

  const now = new Date();
  let startDate = new Date(0);
  let endDate = new Date();
  if (filterVal === "today") {
    startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  } else if (filterVal === "this_week") {
    startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  } else if (filterVal === "last_week") {
    startDate = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);
    endDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  } else if (filterVal === "this_month") {
    startDate = new Date(now.getFullYear(), now.getMonth(), 1);
  } else if (filterVal === "year") {
    startDate = new Date(now.getFullYear(), 0, 1);
  } else if (filterVal === "custom" && window.customDateRange) {
    startDate = new Date(window.customDateRange.start);
    endDate = new Date(window.customDateRange.end);
    endDate.setHours(23, 59, 59, 999);
  }

  let periodRevenue = 0,
    periodCOGS = 0,
    periodCount = 0;
  const periodCustomers = new Set();

  const itemMap = {};
  (user.items || []).forEach((item) => {
    itemMap[String(item.item_id)] = item;
    if (item.id) itemMap[String(item.id)] = item;
  });

  (user.invoice || []).forEach((inv) => {
    if (
      inv.invoice_status === "completed" ||
      inv.invoice_status === "success"
    ) {
      const invDate = new Date(inv.timestamp);
      if (invDate >= startDate && invDate <= endDate) {
        periodCount++;
        if (inv.customer_email) periodCustomers.add(inv.customer_email);
        (inv.invoice_items || []).forEach((item) => {
          const qty = parseFloat(item.item_quantity) || 0;
          const amt = parseFloat(item.item_amount) || 0;
          const buyAmt = parseFloat(item.item_buy_amount) || 0;
          periodRevenue += qty * amt;
          periodCOGS += qty * buyAmt;
        });
      }
    }
  });

  // Period AOV
  const periodAOV = periodCount > 0 ? periodRevenue / periodCount : 0;
  const curSym = getUserCurrencySymbol();
  const avgOrderEl = document.getElementById("stat-avg-order-value");
  if (avgOrderEl && (filterVal !== "year" || filterVal === "custom")) {
    avgOrderEl.textContent = `${curSym}${periodAOV.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  } else if (avgOrderEl) {
    avgOrderEl.textContent = `${curSym}${(summary.average_order_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  // Period Profit Margin
  const periodProfit = periodRevenue - periodCOGS;
  const periodMargin =
    periodRevenue > 0 ? (periodProfit / periodRevenue) * 100 : 0;
  const profitMarginEl = document.getElementById("stat-profit-margin");
  if (profitMarginEl && (filterVal !== "year" || filterVal === "custom")) {
    profitMarginEl.textContent = `${periodMargin.toFixed(1)}%`;
  } else if (profitMarginEl) {
    profitMarginEl.textContent = `${(summary.profit_margin || 0).toFixed(1)}%`;
  }

  // Render change indicators using overall backend-computed values
  const aovChange = summary.aov_change_percentage ?? 0;
  renderChange(document.getElementById("stat-avg-order-change"), aovChange);

  const marginChange = summary.margin_change_percentage ?? 0;
  renderChange(
    document.getElementById("stat-margin-change"),
    marginChange,
    "pp",
    true,
  );

  const turnoverChange = summary.turnover_change ?? 0;
  renderChange(
    document.getElementById("stat-turnover-change"),
    turnoverChange,
    "x",
    true,
  );

  // Retention — show all-time metric (not period-scoped)
  const retentionEl = document.getElementById("stat-retention-rate");
  if (retentionEl)
    retentionEl.textContent = `${(summary.customer_retention || 0).toFixed(1)}%`;

  const retentionChange = summary.retention_change ?? 0;
  const retChangeEl = document.getElementById("stat-retention-change");
  if (retChangeEl) {
    if ((summary.customer_retention || 0) === 0 && !summary.completed_count) {
      retChangeEl.textContent = "No data available";
      retChangeEl.className = "text-xs text-slate-500 mt-1 leading-tight";
    } else {
      renderChange(retChangeEl, retentionChange, "pp", true);
    }
  }

  // Inventory Turnover — backend computed
  const turnoverEl = document.getElementById("stat-inventory-turnover");
  if (turnoverEl)
    turnoverEl.textContent = `${(summary.inventory_turnover || 0).toFixed(1)}x`;
};

/**
 * Analytics Page Charts — initial load only.
 * Revenue chart is owned by switchRevenueChart; this sets up the initial state.
 */
function initAnalyticsCharts() {
  if (typeof Chart === "undefined") return;
  // Kick off the revenue chart via switchRevenueChart so filter logic is shared
  if (typeof window.switchRevenueChart === "function") {
    window.switchRevenueChart("revenue", null);
  }
  // Build the category pie chart
  if (typeof window.initAnalyticsCategoryChart === "function") {
    window.initAnalyticsCategoryChart();
  }
  if (typeof window.updateAnalyticsStats === "function") {
    window.updateAnalyticsStats();
  }
  // Build the visitor location chart
  if (
    typeof window.switchVisitorChart === "function" &&
    document.getElementById("analyticsVisitorChart")
  ) {
    window.switchVisitorChart("countries", null);
  }
}

/**
 * Rebuild only the category distribution doughnut chart.
 * Safe to call on every filter change without touching the revenue chart.
 */
window.initAnalyticsCategoryChart = function () {
  const rawData = localStorage.getItem("user_data");
  if (!rawData) return;
  const user = JSON.parse(rawData);

  const isDark = document.documentElement.classList.contains("dark");
  const legendColor = isDark
    ? "rgba(255,255,255,0.5)"
    : "rgba(15, 23, 42, 0.7)";

  const catCanvas = document.getElementById("analyticsCategoryChart");
  if (!catCanvas || typeof Chart === "undefined") return;

  if (window.flezCharts.analyticsCat) window.flezCharts.analyticsCat.destroy();

  const dateFilter = document.querySelector(
    'select[onchange*="handleDateFilterChange"]',
  );
  const filterVal = dateFilter ? dateFilter.value : "year";

  const now = new Date();
  let startDate = new Date(0);
  let endDate = new Date();

  if (filterVal === "today") {
    startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  } else if (filterVal === "this_week") {
    startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  } else if (filterVal === "last_week") {
    startDate = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);
    endDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  } else if (filterVal === "this_month") {
    startDate = new Date(now.getFullYear(), now.getMonth(), 1);
  } else if (filterVal === "year") {
    startDate = new Date(now.getFullYear(), 0, 1);
  } else if (filterVal === "custom" && window.customDateRange) {
    startDate = new Date(window.customDateRange.start);
    endDate = new Date(window.customDateRange.end);
    endDate.setHours(23, 59, 59, 999);
  }

  const deptSales = {};
  const itemMap = {};
  (user.items || []).forEach((item) => {
    itemMap[item.item_id] = item.item_department || "General";
  });

  (user.invoice || []).forEach((inv) => {
    if (
      inv.invoice_status === "completed" ||
      inv.invoice_status === "success"
    ) {
      const invDate = new Date(inv.timestamp);
      if (invDate >= startDate && invDate <= endDate) {
        (inv.invoice_items || []).forEach((item) => {
          const amount =
            parseFloat(item.item_quantity) * parseFloat(item.item_amount);
          const dept = itemMap[item.item_id] || "General";
          deptSales[dept] = (deptSales[dept] || 0) + amount;
        });
      }
    }
  });

  const labels = Object.keys(deptSales);
  const data = Object.values(deptSales);

  const ctx = catCanvas.getContext("2d");
  window.flezCharts.analyticsCat = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: labels.length ? labels : ["No Sales"],
      datasets: [
        {
          data: data.length ? data : [1],
          backgroundColor: [
            isDark ? "#cfff45" : "#29594b",
            "#3b82f6",
            "#a855f7",
            "#f97316",
            "#ec4899",
          ],
          borderWidth: 0,
          hoverOffset: 15,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "75%",
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: legendColor,
            font: { size: 10 },
            usePointStyle: true,
            padding: 20,
          },
        },
      },
    },
  });
};

/**
 * Convert an ISO 3166-1 alpha-2 code to a flag emoji.
 * Works in all modern browsers — no API needed.
 */
function _countryCodeToFlag(code) {
  if (!code || code.length !== 2) return "";
  const upper = code.toUpperCase();
  return String.fromCodePoint(
    upper.charCodeAt(0) - 65 + 0x1f1e6,
    upper.charCodeAt(1) - 65 + 0x1f1e6,
  );
}

/**
 * Fetch full country names via our backend proxy (avoids CORS restriction).
 * Results are cached in window.flezCountryCache to avoid repeated network calls.
 * Returns a Map: code.toUpperCase() → full common name.
 */
async function _resolveCountryNames(codes) {
  window.flezCountryCache = window.flezCountryCache || {};
  const cache = window.flezCountryCache;

  // Split into uncached codes only
  const missing = codes.filter((c) => !cache[c.toUpperCase()]);

  if (missing.length > 0) {
    try {
      const joined = missing.map((c) => c.toLowerCase()).join(",");
      const res = await fetch(`/api/proxy/country-names?codes=${joined}`, {
        cache: "force-cache",
      });
      if (res.ok) {
        const data = await res.json();
        data.forEach((c) => {
          if (c.cca2 && c.name?.common) {
            cache[c.cca2.toUpperCase()] = c.name.common;
          }
        });
      }
    } catch (_) {
      // Silently fall back to codes if the network request fails
    }
  }

  return cache;
}

/**
 * Render the visitor chart with the given items and (optionally) a name cache.
 */
function _renderVisitorChart(items, type, nameCache) {
  const canvas = document.getElementById("analyticsVisitorChart");
  if (!canvas || typeof Chart === "undefined") return;

  const isDark = document.documentElement.classList.contains("dark");
  const textColor = isDark ? "rgba(255,255,255,0.5)" : "rgba(15, 23, 42, 0.6)";
  const gridColor = isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)";

  if (window.flezCharts.analyticsVisitor) {
    window.flezCharts.analyticsVisitor.destroy();
    window.flezCharts.analyticsVisitor = null;
  }

  if (items.length === 0) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = textColor;
    ctx.font = "13px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("No visitor data yet", canvas.width / 2, canvas.height / 2);
    return;
  }

  const labels = items.map((d) => {
    if (type === "countries") {
      const code = (d.country_code || "").toUpperCase();
      const flag = _countryCodeToFlag(code);
      const fullName = nameCache && nameCache[code] ? nameCache[code] : code;
      return `${flag} ${fullName}`.trim();
    }
    return d.state || "Unknown";
  });

  const data = items.map((d) => d.count || 0);

  // Per-bar heat colors: interpolate red → amber → emerald based on relative value
  const maxVal = Math.max(...data, 1);
  const minVal = Math.min(...data, 0);
  const range = maxVal - minVal || 1;

  // Color stops: 0 = red, 0.5 = amber/yellow, 1 = emerald green
  const stops = [
    { t: 0, h: 0, s: 72, l: 52 }, // red
    { t: 0.5, h: 38, s: 92, l: 50 }, // amber
    { t: 1, h: 142, s: 70, l: 50 }, // emerald
  ];

  function interpolateColor(t) {
    // Clamp t
    t = Math.max(0, Math.min(1, t));
    // Find surrounding stops
    let lo = stops[0],
      hi = stops[stops.length - 1];
    for (let i = 0; i < stops.length - 1; i++) {
      if (t >= stops[i].t && t <= stops[i + 1].t) {
        lo = stops[i];
        hi = stops[i + 1];
        break;
      }
    }
    const seg = hi.t - lo.t || 1;
    const f = (t - lo.t) / seg;
    const h = lo.h + (hi.h - lo.h) * f;
    const s = lo.s + (hi.s - lo.s) * f;
    const l = lo.l + (hi.l - lo.l) * f;
    return {
      fill: `hsl(${h.toFixed(1)}, ${s.toFixed(1)}%, ${l.toFixed(1)}%)`,
      hover: `hsl(${h.toFixed(1)}, ${s.toFixed(1)}%, ${(l + 8).toFixed(1)}%)`,
    };
  }

  const colors = data.map((v) => interpolateColor((v - minVal) / range));
  const bgColors = colors.map((c) => c.fill);
  const hoverColors = colors.map((c) => c.hover);

  const ctx = canvas.getContext("2d");
  window.flezCharts.analyticsVisitor = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label:
            type === "countries" ? "Visitors by Country" : "Visitors by State",
          data,
          backgroundColor: bgColors,
          hoverBackgroundColor: hoverColors,
          borderRadius: 6,
          borderSkipped: false,
          barThickness: 18,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (c) =>
              ` ${c.parsed.x.toLocaleString()} visitor${c.parsed.x !== 1 ? "s" : ""}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: { color: textColor, font: { size: 10 }, precision: 0 },
        },
        y: {
          grid: { display: false },
          ticks: { color: textColor, font: { size: 12, weight: "600" } },
        },
      },
    },
  });
}

/**
 * Store Visitors by Location chart — renders country or state breakdown.
 * Called by the tab buttons in analytics.html: switchVisitorChart('countries'|'states', btnEl)
 */
window.switchVisitorChart = function (type, btn) {
  const rawData = localStorage.getItem("user_data");
  if (!rawData) return;
  const user = JSON.parse(rawData);
  const visitorData = user.visitor_analytics || { countries: [], states: [] };

  // --- Tab active state ---
  const inactiveClasses = [
    "text-slate-500",
    "hover:text-slate-900",
    "dark:hover:text-white",
  ];
  const activeClasses = [
    "bg-primary",
    "text-black",
    "dark:text-white",
    "shadow-lg",
    "shadow-primary/20",
  ];

  document.querySelectorAll(".visitor-tab").forEach((tab) => {
    tab.classList.remove("active-tab", ...activeClasses);
    tab.classList.add(...inactiveClasses);
  });

  const activeBtn =
    btn || document.querySelector(`.visitor-tab[onclick*="'${type}'"]`);
  if (activeBtn) {
    activeBtn.classList.remove(...inactiveClasses);
    activeBtn.classList.add("active-tab", ...activeClasses);
  }

  // --- Build sorted items list ---
  const rawItems =
    type === "countries"
      ? visitorData.countries || []
      : visitorData.states || [];
  const items = rawItems
    .filter((d) => d.country_code || d.state)
    .sort((a, b) => (b.count || 0) - (a.count || 0))
    .slice(0, 10);

  if (type !== "countries") {
    // States need no API — render immediately
    _renderVisitorChart(items, type, null);
    return;
  }

  // --- Countries: render immediately with flag+code, then re-render with full names ---
  _renderVisitorChart(items, type, window.flezCountryCache || {});

  const codes = items.map((d) => d.country_code).filter(Boolean);
  if (codes.length === 0) return;

  _resolveCountryNames(codes).then((nameCache) => {
    // Only re-render if this chart tab is still active
    const stillActive = document.querySelector(".visitor-tab.active-tab");
    if (
      stillActive &&
      stillActive.getAttribute("onclick")?.includes(`'${type}'`)
    ) {
      _renderVisitorChart(items, type, nameCache);
    }
  });
};

/**
 * Invoices Page
 */
function initInvoices() {
  const rawData = localStorage.getItem("user_data");
  if (!rawData) return;
  const user = JSON.parse(rawData);
  const invoices = user.invoice || [];

  const tbody = document.getElementById("invoices-tbody");
  if (tbody) {
    tbody.innerHTML = invoices
      .map((inv) => {
        const dateObj = new Date(inv.timestamp);
        const formattedDate = isNaN(dateObj)
          ? "N/A"
          : dateObj.toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
            });

        return `
            <tr class="group hover:bg-white/5 transition-all">
                <td class="px-6 py-4 text-sm font-mono text-slate-400 uppercase">${inv.invoice_id}</td>
                <td class="px-6 py-4">
                    <p class="text-sm font-bold text-white">${inv.customer_name || "Walk-in Customer"}</p>
                    <p class="text-[10px] text-slate-500">${inv.customer_email || "No email provided"}</p>
                </td>
                <td class="px-6 py-4 text-sm text-slate-400">${formattedDate}</td>
                <td class="px-6 py-4">
                    <span class="px-3 py-1 ${inv.invoice_status === "completed" ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" : "bg-amber-500/10 text-amber-500 border-amber-500/20"} text-[10px] font-bold rounded-full uppercase border">
                        ${inv.invoice_status || "Pending"}
                    </span>
                </td>
                <td class="px-6 py-4 text-right text-sm font-bold text-white">${getUserCurrencySymbol(user)}${parseFloat(inv.total_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                <td class="px-6 py-4 text-right">
                    <div class="flex items-center justify-end gap-1">
                        <button onclick="viewInvoice('${inv.invoice_id}')" class="p-2 hover:bg-white/5 rounded-lg text-slate-400 hover:text-white transition-all" title="View">
                            <i data-lucide="eye" class="w-4 h-4"></i>
                        </button>
                        <button onclick="deleteInvoice('${inv.invoice_id}')" class="p-2 hover:bg-rose-500/10 rounded-lg text-slate-400 hover:text-rose-500 transition-all" title="Delete">
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
      })
      .join("");

    const info = document.getElementById("invoices-pagination-info");
    if (info)
      info.textContent = `Showing ${invoices.length} of ${invoices.length} invoices`;

    if (typeof lucide !== "undefined") lucide.createIcons();
  }

  // Update Invoices Stats
  const summary = user.sales_summary || {};
  const invCurSym = getUserCurrencySymbol(user);
  const totalPaid = document.getElementById("stat-total-paid");
  if (totalPaid)
    totalPaid.textContent = `${invCurSym}${(summary.total_sales || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const outstanding = document.getElementById("stat-outstanding");
  if (outstanding)
    outstanding.textContent = `${invCurSym}${(summary.total_pending_sales || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

window.viewInvoice = async (id) => {
  let rawData = localStorage.getItem("user_data");
  let user = JSON.parse(rawData || "{}");
  let invoice = (user.invoice || []).find((inv) => inv.invoice_id === id);

  if (!invoice) {
    console.warn(`Invoice ${id} not found in local storage, refreshing...`);
    await refreshUserData();
    rawData = localStorage.getItem("user_data");
    user = JSON.parse(rawData || "{}");
    invoice = (user.invoice || []).find((inv) => inv.invoice_id === id);
  }

  if (invoice) {
    InvoiceDetailComponent.render(invoice, user);
  } else {
    showToast("Error", "Invoice not found. Please refresh the page.", "error");
  }
};

const InvoiceDetailComponent = {
  isOpen: false,

  template: `
        <div id="invoice-detail-overlay" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-[100] transition-opacity duration-300 opacity-0 pointer-events-none" onclick="InvoiceDetailComponent.close()"></div>
        <aside id="invoice-detail-panel" class="fixed inset-y-0 right-0 w-full sm:w-[500px] bg-white dark:bg-bg-dark border-l border-slate-200 dark:border-white/10 z-[110] shadow-2xl transition-transform duration-500 translate-x-full flex flex-col">
            <div id="invoice-detail-header" class="p-6 border-b border-slate-200 dark:border-white/5 flex items-center justify-between bg-slate-50/50 dark:bg-bg-card/50 backdrop-blur-md print:hidden">
                <div class="flex items-center gap-4">
                    <button onclick="InvoiceDetailComponent.close()" class="p-2 hover:bg-slate-200 dark:hover:bg-white/5 rounded-lg text-slate-500 dark:text-slate-400">
                        <i data-lucide="arrow-right" class="w-5 h-5"></i>
                    </button>
                    <h2 class="text-xl font-display font-bold text-slate-900 dark:text-white uppercase tracking-wider">Invoice Details</h2>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="window.print()" class="p-2 hover:bg-slate-200 dark:hover:bg-white/5 rounded-lg text-slate-500 dark:text-slate-400" title="Print">
                        <i data-lucide="printer" class="w-5 h-5"></i>
                    </button>
                    <button onclick="InvoiceDetailComponent.downloadPDF()" class="p-2 hover:bg-primary/10 rounded-lg text-primary" title="Download">
                        <i data-lucide="download" class="w-5 h-5"></i>
                    </button>
                </div>
            </div>

            <div class="flex-1 overflow-y-auto p-6 space-y-8 print:p-0 print:overflow-visible" id="invoice-detail-content">
                <!-- Content will be injected here -->
            </div>
        </aside>
    `,

  render(invoice, userData) {
    let container = document.getElementById("invoice-detail-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "invoice-detail-container";
      document.body.appendChild(container);
      container.innerHTML = this.template;

      if (!document.getElementById("invoice-detail-styles")) {
        const style = document.createElement("style");
        style.id = "invoice-detail-styles";
        style.textContent = `
                    #invoice-detail-panel.open { transform: translateX(0); }
                    #invoice-detail-overlay.active { opacity: 1; pointer-events: auto; }
                    @media print {
                        body > *:not(#invoice-detail-container) { display: none !important; }
                        #invoice-detail-overlay { display: none !important; }
                        #invoice-detail-panel { 
                            position: static !important; 
                            width: 100% !important; 
                            transform: none !important;
                            border: none !important;
                            background: white !important;
                        }
                        #invoice-detail-content { background: white !important; color: black !important; padding: 0 !important; }
                        .text-white, .text-primary { color: black !important; }
                        .text-slate-400, .text-slate-500 { color: #475569 !important; }
                        .bg-bg-dark, .bg-bg-card, .bg-white\\/5 { background: white !important; }
                        .border-white\\/5, .border-white\\/10 { border-color: #e2e8f0 !important; }
                        #invoice-detail-panel span[class*="bg-"] { background: #f1f5f9 !important; border: 1px solid #e2e8f0 !important; color: black !important; }
                    }
                `;
        document.head.appendChild(style);
      }
    }

    const content = document.getElementById("invoice-detail-content");
    const isCompleted = invoice.invoice_status === "completed";
    const business = (userData.business_details || [])[0] || {};
    const isInstallment = invoice.invoice_type === "installment";
    const invSym = getUserCurrencySymbol(userData);

    let subtotal = 0;
    let vat = 0;
    let deliveryFee = 0;

    const rawItems = invoice.invoice_items || [];
    const taxItem = rawItems.find(
      (i) =>
        (i.item_id || "").toUpperCase() === "TAX_001" ||
        (i.item_name || "").toLowerCase().includes("tax") ||
        (i.item_name || "").toLowerCase().includes("vat"),
    );
    const deliveryItem = rawItems.find(
      (i) =>
        (i.item_id || "").toUpperCase() === "DELIVERY_001" ||
        (i.item_name || "").toLowerCase().includes("delivery fee"),
    );

    const productItems = rawItems.filter((i) => {
      const id = (i.item_id || "").toUpperCase();
      const name = (i.item_name || "").toLowerCase();
      return (
        id !== "TAX_001" &&
        id !== "DELIVERY_001" &&
        !name.includes("delivery fee") &&
        !name.includes("estimated tax") &&
        !name.includes("vat")
      );
    });

    const displayItems = productItems.length > 0 ? productItems : rawItems;

    const itemsHtml = displayItems
      .map((item) => {
        const total =
          parseFloat(item.item_amount) * parseInt(item.item_quantity);
        subtotal += total;
        const optBadge =
          item.color_name || item.size
            ? `
                <div class="flex items-center gap-1.5 mt-1">
                    <span class="px-2 py-0.5 rounded-md bg-primary/10 text-primary border border-primary/20 text-[11px] font-bold inline-flex items-center gap-1 shadow-sm">
                        ${item.color_hex ? `<span class="w-2 h-2 rounded-full inline-block" style="background-color: ${item.color_hex}"></span>` : ""}
                        <span>${item.color_name || ""}${item.color_name && item.size ? " - " : ""}${item.size || ""}</span>
                    </span>
                </div>
            `
            : "";
        return `
                <div class="flex justify-between py-3 border-b border-white/5">
                    <div>
                        <p class="text-sm font-bold text-white">${item.item_name}</p>
                        ${optBadge}
                        <p class="text-[10px] text-slate-500 mt-0.5">${item.item_quantity} x ${invSym}${parseFloat(item.item_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                    </div>
                    <p class="text-sm font-bold text-white">${invSym}${total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                </div>
            `;
      })
      .join("");

    if (taxItem) {
      vat =
        parseFloat(taxItem.item_amount) * parseInt(taxItem.item_quantity || 1);
    } else {
      vat = subtotal * 0.075;
    }

    if (deliveryItem) {
      deliveryFee =
        parseFloat(deliveryItem.item_amount) *
        parseInt(deliveryItem.item_quantity || 1);
    }

    const grandTotal = invoice.total_amount
      ? parseFloat(invoice.total_amount)
      : subtotal + vat + deliveryFee;
    const paidSoFar = parseFloat(invoice.total_paid || 0);
    const remaining = grandTotal - paidSoFar;
    const payPercent = Math.min(
      100,
      Math.round((paidSoFar / grandTotal) * 100),
    );

    content.innerHTML = `
            <div class="space-y-6">
                <!-- Status & IDs -->
                <div class="flex justify-between items-start">
                    <div>
                        <p class="text-[10px] text-slate-500 font-bold uppercase mb-1">Invoice ID</p>
                        <h3 class="text-xl font-mono font-black text-white">#${invoice.invoice_id}</h3>
                        <p class="text-[10px] text-primary font-bold uppercase mt-1 tracking-widest">${invoice.invoice_type || "Instant"}</p>
                    </div>
                    <span class="px-4 py-2 ${isCompleted ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" : "bg-amber-500/10 text-amber-500 border-amber-500/20"} text-xs font-black rounded-full uppercase border">
                        ${invoice.invoice_status}
                    </span>
                </div>

                <!-- Installment Tracking -->
                ${
                  isInstallment
                    ? `
                <div class="bg-primary/5 border border-primary/10 rounded-2xl p-5 space-y-4">
                    <div class="flex justify-between items-end">
                        <div>
                            <p class="text-[10px] text-primary font-bold uppercase mb-1">Paid So Far</p>
                            <h4 class="text-2xl font-black text-white">${invSym}${paidSoFar.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</h4>
                        </div>
                        <p class="text-xs font-bold text-slate-400">${payPercent}% of ${invSym}${grandTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                    </div>
                    <div class="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                        <div class="h-full bg-primary transition-all duration-1000" style="width: ${payPercent}%"></div>
                    </div>
                    ${
                      remaining > 0
                        ? `
                    <div class="flex items-center gap-2 text-[10px] font-bold text-rose-500 uppercase">
                        <i data-lucide="info" class="w-3 h-3"></i>
                        <span>Outstanding Balance: ${invSym}${remaining.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    </div>
                    `
                        : ""
                    }
                </div>

                <!-- Account Details -->
                <div class="bg-white/5 rounded-2xl p-5 border border-white/10 space-y-4">
                    <p class="text-[10px] text-slate-500 font-bold uppercase">Designated Payment Account</p>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <p class="text-[10px] text-slate-500 uppercase mb-1">Bank Name</p>
                            <p class="text-xs font-bold text-white">${invoice.designated_bank_name || "N/A"}</p>
                        </div>
                        <div>
                            <p class="text-[10px] text-slate-500 uppercase mb-1">Account Number</p>
                            <div class="flex items-center gap-2">
                                <p class="text-sm font-mono font-black text-primary">${invoice.designated_account_number || "N/A"}</p>
                                <button onclick="copyToClipboard('${invoice.designated_account_number}')" class="p-1 hover:bg-primary/10 rounded text-primary transition-all" title="Copy">
                                    <i data-lucide="copy" class="w-3 h-3"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                    <div>
                        <p class="text-[10px] text-slate-500 uppercase mb-1">Account Name</p>
                        <p class="text-xs font-bold text-white uppercase">${invoice.designated_account_name || "N/A"}</p>
                    </div>
                </div>
                `
                    : ""
                }

                <!-- Info Grid -->
                <div class="grid grid-cols-2 gap-6 py-6 border-y border-white/5">
                    <div>
                        <p class="text-[10px] text-slate-500 font-bold uppercase mb-2">Issued On</p>
                        <p class="text-sm font-bold text-white">${new Date(invoice.timestamp).toLocaleDateString()}</p>
                    </div>
                    <div>
                        <p class="text-[10px] text-slate-500 font-bold uppercase mb-2">Due Date</p>
                        <p class="text-sm font-bold text-rose-500">${invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : "N/A"}</p>
                    </div>
                </div>

                <!-- Parties -->
                <div class="grid grid-cols-2 gap-6">
                    <div>
                        <p class="text-[10px] text-slate-500 font-bold uppercase mb-3">From</p>
                        <h4 class="text-sm font-black text-white uppercase">${business.business_name || "FlezPay Business"}</h4>
                        <p class="text-[10px] text-slate-500 mt-1">${business.support_email || "support@flezpay.com"}</p>
                    </div>
                    <div class="text-right">
                        <p class="text-[10px] text-slate-500 font-bold uppercase mb-3">Billed To</p>
                        <h4 class="text-sm font-black text-white uppercase">${invoice.customer_name || "Walk-in Customer"}</h4>
                        <p class="text-[10px] text-slate-500 mt-1">${invoice.customer_email || "No email provided"}</p>
                        <p class="text-[10px] text-slate-500">${invoice.customer_phone || ""}</p>
                    </div>
                </div>

                <!-- Items -->
                <div class="space-y-2">
                    <p class="text-[10px] text-slate-500 font-bold uppercase mb-4">Itemized Breakdown</p>
                    ${itemsHtml}
                </div>

                <!-- Summary -->
                <div class="bg-white/5 rounded-2xl p-6 space-y-4">
                    <div class="flex justify-between text-sm">
                        <span class="text-slate-500">Subtotal</span>
                        <span class="text-white font-bold">${invSym}${subtotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-slate-500">${taxItem ? taxItem.item_name || "Tax" : "VAT (7.5%)"}</span>
                        <span class="text-white font-bold">${invSym}${vat.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    </div>
                    ${
                      deliveryFee > 0
                        ? `
                    <div class="flex justify-between text-sm">
                        <span class="text-slate-500">Delivery Fee</span>
                        <span class="text-white font-bold">${invSym}${deliveryFee.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    </div>
                    `
                        : ""
                    }
                    <div class="flex justify-between items-center pt-4 border-t border-white/10">
                        <span class="text-base font-bold text-white uppercase">Grand Total</span>
                        <span class="text-2xl font-display font-black text-primary">${invSym}${grandTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    </div>
                </div>

                <!-- Note -->
                <div class="pt-6">
                    <p class="text-[10px] text-slate-500 font-bold uppercase mb-2">Note</p>
                    <p class="text-xs text-slate-400 leading-relaxed italic">${invoice.invoice_note || "No additional notes."}</p>
                </div>
            </div>
        `;

    if (window.lucide) lucide.createIcons();

    // Use double requestAnimationFrame to ensure DOM is ready and initial styles are painted
    // This fixes the animation not playing on the first open after a page reload
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        this.open();
      });
    });
  },

  open() {
    this.isOpen = true;
    document.getElementById("invoice-detail-panel")?.classList.add("open");
    document.getElementById("invoice-detail-overlay")?.classList.add("active");
  },

  close() {
    this.isOpen = false;
    document.getElementById("invoice-detail-panel")?.classList.remove("open");
    document
      .getElementById("invoice-detail-overlay")
      ?.classList.remove("active");
  },

  downloadPDF() {
    const element = document.getElementById("invoice-detail-content");
    if (!element) return;

    const invoiceId =
      element.querySelector("h3")?.textContent.replace("#", "") || "invoice";

    // Prepare for capture (temp styles if needed)
    const opt = {
      margin: 0.5,
      filename: `Invoice_${invoiceId}.pdf`,
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true, backgroundColor: "#ffffff" },
      jsPDF: { unit: "in", format: "letter", orientation: "portrait" },
    };

    // We clone or temporarily style the element for PDF if it's dark mode
    const isDarkMode = document.documentElement.classList.contains("dark");
    if (isDarkMode) {
      element.classList.add("bg-white", "text-black");
      // This is a bit tricky with tailwind classes, html2pdf handles it okay-ish
    }

    html2pdf()
      .set(opt)
      .from(element)
      .save()
      .then(() => {
        if (isDarkMode) {
          element.classList.remove("bg-white", "text-black");
        }
      });
  },
};
window.InvoiceDetailComponent = InvoiceDetailComponent;

window.deleteInvoice = async (id) => {
  const result = await Swal.fire({
    title: "Delete Invoice?",
    text: "This will permanently remove this invoice. Proceed?",
    icon: "warning",
    showCancelButton: true,
    confirmButtonColor: "#f43f5e",
    cancelButtonColor: "#64748b",
    confirmButtonText: "Yes, Delete",
  });

  if (result.isConfirmed) {
    try {
      const res = await apiFetch(`${FLEZ_API_BASE}/api/user/invoice/delete`, {
        method: "POST",
        body: JSON.stringify({ invoice_id: id }),
      });
      const data = await res.json();
      if (data.status) {
        showToast("Deleted", "Invoice removed", "success");
        refreshUserData();
      } else {
        showToast("Error", data.message, "error");
      }
    } catch (err) {
      showToast("Error", "Request failed", "error");
    }
  }
};

/**
 * Transactions Page
 */
function initTransactions() {
  const rawData = localStorage.getItem("user_data");
  if (!rawData) return;
  const user = JSON.parse(rawData);
  const transactions = user.transactions || [];
  const curSym = getUserCurrencySymbol(user);

  const tbody = document.getElementById("transactions-tbody");
  if (tbody) {
    tbody.innerHTML = transactions
      .map((trx) => {
        const desc = trx.description || "Transaction";
        const safeDesc = desc
          .replace(/"/g, "&quot;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;");
        return `
            <tr class="group hover:bg-white/5 transition-all">
                <td class="px-6 py-4 text-sm font-mono text-slate-400 uppercase whitespace-nowrap">${trx.trx_id}</td>
                <td class="px-6 py-4 max-w-xs sm:max-w-sm md:max-w-md">
                    <p class="text-sm font-bold text-white truncate" title="${safeDesc}">${desc}</p>
                    <p class="text-xs text-slate-500 whitespace-nowrap">${new Date(trx.timestamp).toLocaleString()}</p>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-3 py-1 ${trx.trx_status === "success" ? "bg-emerald-500/10 text-emerald-500" : "bg-rose-500/10 text-rose-500"} text-[10px] font-bold rounded-full uppercase">${trx.trx_status || "Success"}</span>
                </td>
                <td class="px-6 py-4 text-sm text-slate-400 whitespace-nowrap">${trx.category || "General"}</td>
                <td class="px-6 py-4 text-right text-sm font-bold text-white whitespace-nowrap">${curSym}${parseFloat(trx.trx_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
            </tr>
        `;
      })
      .join("");
  }
}

/**
 * Wallet Page
 */

/**
 * Staff Page Logic
 */
window.initStaff = () => {
  if (!document.getElementById("staff-tbody")) return;

  initPaginatedTable({
    endpoint: `${FLEZ_API_BASE}/api/staff/filter`,
    containerId: "staff-tbody",
    prevBtnId: "staff-prev-btn",
    nextBtnId: "staff-next-btn",
    infoId: "staff-pagination-info",
    searchId: "staff-filter-search",
    renderRow: (staff) => {
      const initials = staff.account_name
        ? staff.account_name
            .split(" ")
            .map((n) => n[0])
            .join("")
            .toUpperCase()
            .substring(0, 2)
        : "??";
      const hasValidImage =
        staff.image && !staff.image.includes("placeholder_avi");
      return `
            <tr class="group hover:bg-white/5 transition-all cursor-pointer" onclick="if (window.flezSwup) window.flezSwup.navigate('/staff-details/${staff.id}'); else window.location.href = '/staff-details/${staff.id}';">
                <td class="px-6 py-4">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl bg-primary/20 border border-primary/20 flex items-center justify-center text-primary font-bold overflow-hidden shrink-0">
                            ${hasValidImage ? `<img src="${staff.image}" class="w-full h-full object-cover" alt="${staff.account_name || "Staff"}" onerror="this.outerHTML='<span>${initials}</span>';" />` : `<span>${initials}</span>`}
                        </div>
                        <div>
                            <p class="text-sm font-bold text-white group-hover:text-primary transition-colors">${staff.account_name || "Staff Member"}</p>
                            <p class="text-xs text-slate-500">${staff.account_number || "No Account"}</p>
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4 text-sm text-slate-400">${staff.job_title || "N/A"}</td>
                <td class="px-6 py-4 text-sm text-slate-400">${staff.department || "General"}</td>
                <td class="px-6 py-4">
                    <div class="flex items-center gap-2">
                        <div class="w-2 h-2 ${staff.is_active ? "bg-emerald-500" : "bg-rose-500"} rounded-full animate-pulse"></div>
                        <span class="text-xs ${staff.is_active ? "text-emerald-500" : "text-rose-500"} font-medium capitalize">${staff.is_active ? "Active" : "Inactive"}</span>
                    </div>
                </td>
            </tr>
            `;
    },
  });
};

window.initDepartments = () => {
  // Departments Table
  window.allDepartments = [];

  window.renderDepartments = (data) => {
    const tbody = document.getElementById("departments-tbody");
    if (!tbody) return;
    tbody.innerHTML = data
      .map(
        (dept) => `
            <tr class="group hover:bg-white/5 transition-all">
                <td class="px-6 py-4">
                    <p class="text-sm font-bold text-white">${dept.department_name}</p>
                    <span class="text-[10px] bg-primary/20 text-primary px-2 py-0.5 rounded-full font-bold">Active</span>
                </td>
                <td class="px-6 py-4">
                    <p class="text-xs text-slate-400">${dept.description || "Business unit for " + dept.department_name.toLowerCase() + " operations."}</p>
                </td>
                <td class="px-6 py-4">
                    <span class="text-xs font-medium text-white">${dept.staff_count} Staff</span>
                </td>
                <td class="px-6 py-4">
                    <span class="text-xs font-medium text-white">${dept.manager_count} Managers</span>
                </td>
                <td class="px-6 py-4 text-right">
                    <button class="p-2 hover:bg-white/10 rounded-lg text-slate-400 hover:text-white transition-all inline-flex" onclick="editDepartment('${dept.uniq_id}', '${dept.department_name}', '${dept.description || ""}')"><i data-lucide="edit-3" class="w-4 h-4"></i></button>
                    <button class="p-2 hover:bg-rose-500/10 rounded-lg text-rose-500 transition-all inline-flex" onclick="deleteDepartment('${dept.uniq_id}', '${dept.department_name}')"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
                </td>
            </tr>
        `,
      )
      .join("");
    document.getElementById("departments-pagination-info").textContent =
      `Showing ${data.length} departments`;
    if (typeof lucide !== "undefined") lucide.createIcons();
  };

  window.fetchDepartments = () => {
    apiFetch(`${FLEZ_API_BASE}/api/departments/filter`, {
      method: "POST",
    })
      .then((r) => r.json())
      .then((res) => {
        if (res.status) {
          window.allDepartments = res.data || [];
          window.renderDepartments(window.allDepartments);
        }
      });
  };

  // Add search listener
  const searchInput = document.getElementById("departments-filter-search");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const term = e.target.value.toLowerCase();
      const filtered = window.allDepartments.filter(
        (dept) =>
          dept.department_name.toLowerCase().includes(term) ||
          (dept.description && dept.description.toLowerCase().includes(term)),
      );
      window.renderDepartments(filtered);
    });
  }

  window.fetchDepartments();
};

// Department Action Handlers
window.editDepartment = (id, name, desc) => {
  const modal = document.getElementById("edit-dept-modal");
  const inputName = document.getElementById("edit-dept-name");
  const inputDesc = document.getElementById("edit-dept-desc");
  const saveBtn = document.getElementById("save-dept-btn");

  if (!modal || !inputName) return;

  inputName.value = name;
  if (inputDesc) inputDesc.value = desc || "";
  modal.classList.add("show");
  if (window.lucide) window.lucide.createIcons();

  saveBtn.onclick = () => {
    const newName = inputName.value.trim();
    const newDesc = inputDesc ? inputDesc.value.trim() : "";
    if (!newName) return;

    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="animate-spin mr-2">◌</span> Saving...';

    apiFetch(`${FLEZ_API_BASE}/api/user/data/update/department`, {
      method: "POST",
      body: JSON.stringify({
        department_id: id,
        department_name: newName,
        description: newDesc,
      }),
    })
      .then((r) => r.json())
      .then((res) => {
        saveBtn.disabled = false;
        saveBtn.innerHTML = "Save Changes";
        if (res.status) {
          Swal.fire("Updated!", "Department has been updated.", "success");
          closeEditDeptModal();
          if (window.fetchDepartments) window.fetchDepartments();
        } else {
          Swal.fire("Error", res.message, "error");
        }
      });
  };
};

window.closeEditDeptModal = () => {
  const modal = document.getElementById("edit-dept-modal");
  if (modal) modal.classList.remove("show");
};

window.openAddDeptModal = () => {
  const modal = document.getElementById("add-dept-modal");
  const inputName = document.getElementById("add-dept-name");
  const inputDesc = document.getElementById("add-dept-desc");
  const createBtn = document.getElementById("create-dept-btn");

  if (!modal || !inputName) return;

  inputName.value = "";
  if (inputDesc) inputDesc.value = "";
  modal.classList.add("show");
  if (window.lucide) window.lucide.createIcons();

  createBtn.onclick = () => {
    const name = inputName.value.trim();
    const desc = inputDesc ? inputDesc.value.trim() : "";
    if (!name) return;

    createBtn.disabled = true;
    createBtn.innerHTML =
      '<span class="animate-spin mr-2">◌</span> Creating...';

    apiFetch(`${FLEZ_API_BASE}/api/user/data/add/department`, {
      method: "POST",
      body: JSON.stringify({ department_name: name, description: desc }),
    })
      .then((r) => r.json())
      .then((res) => {
        createBtn.disabled = false;
        createBtn.innerHTML = "Create Department";
        if (res.status) {
          Swal.fire("Created!", "New department has been added.", "success");
          closeAddDeptModal();
          if (window.fetchDepartments) window.fetchDepartments();
        } else {
          Swal.fire("Error", res.message, "error");
        }
      });
  };
};

window.closeAddDeptModal = () => {
  const modal = document.getElementById("add-dept-modal");
  if (modal) modal.classList.remove("show");
};

window.deleteDepartment = (id, name) => {
  Swal.fire({
    title: "Are you sure?",
    text: `Confirm you want to remove "${name}"?`,
    icon: "warning",
    showCancelButton: true,
    confirmButtonColor: "#ef4444",
    confirmButtonText: "Yes, delete it!",
  }).then((result) => {
    if (result.isConfirmed) {
      apiFetch(`${FLEZ_API_BASE}/api/user/data/delete/department`, {
        method: "POST",
        body: JSON.stringify({ id: id }),
      })
        .then((r) => r.json())
        .then((res) => {
          if (res.status) {
            Swal.fire("Deleted!", res.message, "success");
            if (window.fetchDepartments) window.fetchDepartments();
          } else {
            Swal.fire("Blocked", res.message, "error");
          }
        });
    }
  });
};
/**
 * Staff Details Page Logic
 */
window.initStaffDetails = () => {
  const tabs = document.querySelectorAll(".sd-tab");
  const panels = document.querySelectorAll(".sd-panel");
  if (!tabs.length) return;

  // Tab switching logic
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("data-tab");
      tabs.forEach((t) => t.classList.remove("active"));
      panels.forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      const panel = document.getElementById("panel-" + target);
      if (panel) panel.classList.add("active");
      if (typeof lucide !== "undefined") lucide.createIcons();
    });
  });

  // Fetch staff data
  const pathParts = window.location.pathname.split("/");
  const staffId = pathParts[pathParts.length - 1];
  if (!staffId) return;

  apiFetch(`${FLEZ_API_BASE}/api/staff/detail/${staffId}`)
    .then((r) => r.json())
    .then((res) => {
      if (res.status) {
        const staff = res.data;
        const fullName =
          (staff.first_name + " " + staff.last_name).trim() || "Unknown Staff";
        const initials = fullName
          .split(" ")
          .map((n) => n[0])
          .join("")
          .toUpperCase()
          .substring(0, 2);

        // Header & Primary Info
        document.getElementById("sd-name").textContent = fullName;
        const initialsEl = document.getElementById("sd-initials");
        if (initialsEl) initialsEl.textContent = initials;

        const avatarImg = document.getElementById("sd-avatar-img");
        const hasValidImage =
          staff.image && !staff.image.includes("placeholder_avi");
        if (avatarImg) {
          if (hasValidImage) {
            avatarImg.src = staff.image;
            avatarImg.classList.remove("hidden");
            if (initialsEl) initialsEl.classList.add("hidden");
            avatarImg.onerror = () => {
              avatarImg.classList.add("hidden");
              if (initialsEl) initialsEl.classList.remove("hidden");
            };
          } else {
            avatarImg.classList.add("hidden");
            if (initialsEl) initialsEl.classList.remove("hidden");
          }
        }

        // Avatar Upload Handler
        const avatarUploadBtn = document.getElementById("sd-avatar-upload-btn");
        const avatarFileInput = document.getElementById("sd-avatar-file-input");
        const avatarContainer = document.getElementById("sd-avatar-container");

        if (avatarFileInput && !avatarFileInput.dataset.bound) {
          avatarFileInput.dataset.bound = "true";
          const triggerUpload = () => avatarFileInput.click();
          if (avatarUploadBtn) avatarUploadBtn.onclick = triggerUpload;
          if (avatarContainer) avatarContainer.onclick = triggerUpload;

          avatarFileInput.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            if (!file.type.startsWith("image/")) {
              Swal.fire(
                "Invalid File",
                "Please select a valid image file (PNG, JPG, WebP).",
                "warning",
              );
              return;
            }

            // Instant preview
            const reader = new FileReader();
            reader.onload = (re) => {
              if (avatarImg) {
                avatarImg.src = re.target.result;
                avatarImg.classList.remove("hidden");
                if (initialsEl) initialsEl.classList.add("hidden");
              }
            };
            reader.readAsDataURL(file);

            const formData = new FormData();
            formData.append("id", staff.id);
            formData.append("user_avatar", file);

            if (avatarUploadBtn) {
              avatarUploadBtn.disabled = true;
              avatarUploadBtn.innerHTML =
                '<span class="animate-spin text-xs">◌</span>';
            }

            try {
              const upRes = await apiFetch(
                `${FLEZ_API_BASE}/api/staff/update-details`,
                {
                  method: "POST",
                  body: formData,
                },
              );
              const upData = await upRes.json();
              if (upData.status) {
                Swal.fire({
                  title: "Updated!",
                  text: "Staff profile photo updated successfully.",
                  icon: "success",
                  timer: 1800,
                  showConfirmButton: false,
                });
                if (upData.image && avatarImg) {
                  avatarImg.src = upData.image;
                }
              } else {
                Swal.fire(
                  "Error",
                  upData.message || "Failed to update photo",
                  "error",
                );
              }
            } catch (err) {
              console.error("Error uploading staff photo:", err);
              Swal.fire(
                "Error",
                "An unexpected error occurred while uploading photo.",
                "error",
              );
            } finally {
              if (avatarUploadBtn) {
                avatarUploadBtn.disabled = false;
                avatarUploadBtn.innerHTML =
                  '<i data-lucide="camera" class="w-3.5 h-3.5"></i>';
                if (window.lucide) lucide.createIcons();
              }
            }
          };
        }

        document.getElementById("sd-contact").textContent =
          `${staff.account_number} • ${staff.bank_name || "Bank"}`;
        document.getElementById("sd-dept-label").textContent =
          staff.department || "Unassigned";
        document.getElementById("sd-role-label").textContent =
          staff.job_title || "Staff";

        // Update Department Tab Info
        const deptDisplay = document.getElementById("sd-current-dept-display");
        if (deptDisplay) {
          deptDisplay.textContent = staff.department || "Unassigned";
        }
        if (typeof window.populateDepartments === "function") {
          window.populateDepartments("sd-new-dept", staff.department);
        }
        const reassignBtn = document.getElementById("reassign-dept-btn");
        if (reassignBtn) {
          reassignBtn.onclick = () => {
            const newDept = document.getElementById("sd-new-dept").value;
            if (!newDept) {
              Swal.fire("Error", "Please select a new department", "error");
              return;
            }
            reassignBtn.disabled = true;
            reassignBtn.innerHTML =
              '<span class="animate-spin mr-2">◌</span> Reassigning...';
            apiFetch(`${FLEZ_API_BASE}/api/staff/update-details`, {
              method: "POST",
              body: JSON.stringify({
                id: staff.id,
                department: newDept,
              }),
            })
              .then((r) => r.json())
              .then((res) => {
                reassignBtn.disabled = false;
                reassignBtn.innerHTML =
                  '<i data-lucide="check" class="w-4 h-4"></i>Confirm Reassignment';
                if (typeof lucide !== "undefined") lucide.createIcons();
                if (res.status) {
                  Swal.fire(
                    "Success",
                    "Department reassigned successfully",
                    "success",
                  ).then(() => {
                    window.location.reload();
                  });
                } else {
                  Swal.fire(
                    "Error",
                    res.message || "Failed to reassign department",
                    "error",
                  );
                }
              })
              .catch((err) => {
                reassignBtn.disabled = false;
                reassignBtn.innerHTML =
                  '<i data-lucide="check" class="w-4 h-4"></i>Confirm Reassignment';
                if (typeof lucide !== "undefined") lucide.createIcons();
                Swal.fire("Error", "An error occurred", "error");
              });
          };
        }
        const joinedLabel = document.getElementById("sd-joined-label");
        if (joinedLabel && staff.timestamp) {
          joinedLabel.textContent = `Joined ${new Date(staff.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`;
        }

        // Status Badge
        const statusBadge = document.getElementById("sd-status-badge");
        if (statusBadge) {
          const isActive = staff.is_active;
          statusBadge.className = `px-2.5 py-0.5 ${isActive ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" : "bg-rose-500/10 text-rose-500 border-rose-500/20"} text-[10px] font-bold rounded-full uppercase border flex items-center gap-1`;
          statusBadge.innerHTML = `<span class="w-1.5 h-1.5 ${isActive ? "bg-emerald-500" : "bg-rose-500"} rounded-full animate-pulse"></span> ${isActive ? "Active" : "Suspended"}`;

          // Update Toggle Button in Danger Zone
          const suspendBtn = document.getElementById("suspend-btn");
          if (suspendBtn) {
            suspendBtn.innerHTML = isActive
              ? '<i data-lucide="pause" class="w-4 h-4"></i>Suspend Account'
              : '<i data-lucide="play" class="w-4 h-4"></i>Activate Account';
            suspendBtn.className = isActive
              ? "shrink-0 px-6 py-3 bg-amber-500/10 text-amber-500 border border-amber-500/20 font-bold rounded-xl hover:bg-amber-500/20 transition-all flex items-center gap-2 text-sm"
              : "shrink-0 px-6 py-3 bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 font-bold rounded-xl hover:bg-emerald-500/20 transition-all flex items-center gap-2 text-sm";
          }
        }

        // Information Tab / Personal Details Card
        const fieldName = document.getElementById("field-name");
        if (fieldName) fieldName.textContent = fullName;
        const fieldEmail = document.getElementById("field-email");
        if (fieldEmail)
          fieldEmail.textContent = staff.email || staff.user_email || "--";
        const fieldAccount = document.getElementById("field-account");
        if (fieldAccount)
          fieldAccount.textContent = staff.has_collection_account
            ? staff.collection_account_number
            : staff.account_number || "Not Assigned";
        const fieldBank = document.getElementById("field-bank");
        if (fieldBank)
          fieldBank.textContent = staff.has_collection_account
            ? staff.collection_bank_name
            : staff.bank_name || "No Collection Account";

        // Also update the header contact
        const headerContact = document.getElementById("sd-contact");
        if (headerContact) {
          if (staff.has_collection_account) {
            headerContact.textContent = `${staff.collection_account_number} • ${staff.collection_bank_name}`;
          } else {
            headerContact.textContent = "No Collection Account Assigned";
          }
        }

        // Setup Message / Collection Button
        const messageBtn = document.getElementById("sd-message-btn");

        // Quill Editor Instantiation
        let quillInstance = null;
        const modal = document.getElementById("email-modal");
        const modalContent = document.getElementById("email-modal-content");

        const openEmailModal = () => {
          if (!modal) return;
          modal.classList.remove("hidden");
          setTimeout(() => {
            modalContent.classList.remove("scale-95", "opacity-0");
            modalContent.classList.add("scale-100", "opacity-100");
          }, 10);

          if (!quillInstance) {
            quillInstance = new Quill("#quill-editor", {
              theme: "snow",
              placeholder: "Write your message...",
              modules: {
                toolbar: [
                  ["bold", "italic", "underline"],
                  [{ list: "ordered" }, { list: "bullet" }],
                  ["clean"],
                ],
              },
            });
            // Fix toolbar styling for dark mode
            document
              .querySelector(".ql-toolbar")
              .classList.add("bg-white/5", "border-white/10", "rounded-t-xl");
          }
        };

        const closeEmailModal = () => {
          if (!modal) return;
          modalContent.classList.remove("scale-100", "opacity-100");
          modalContent.classList.add("scale-95", "opacity-0");
          setTimeout(() => modal.classList.add("hidden"), 300);
        };

        document
          .getElementById("close-email-modal")
          ?.addEventListener("click", closeEmailModal);
        document
          .getElementById("cancel-email-btn")
          ?.addEventListener("click", closeEmailModal);

        const sendEmailBtn = document.getElementById("send-email-btn");
        if (sendEmailBtn) {
          sendEmailBtn.onclick = () => {
            const subject = document
              .getElementById("email-subject")
              .value.trim();
            const message = quillInstance.root.innerHTML;

            if (!subject || quillInstance.getText().trim() === "") {
              Swal.fire(
                "Required",
                "Subject and Message cannot be empty.",
                "warning",
              );
              return;
            }

            sendEmailBtn.disabled = true;
            const originalHtml = sendEmailBtn.innerHTML;
            sendEmailBtn.innerHTML =
              '<span class="animate-spin">◌</span> Sending...';

            apiFetch(`${FLEZ_API_BASE}/api/staff/send-email`, {
              method: "POST",
              body: JSON.stringify({ id: staff.id, subject, message }),
            })
              .then((r) => r.json())
              .then((res) => {
                if (res.status) {
                  Swal.fire(
                    "Sent!",
                    "Message has been sent to staff.",
                    "success",
                  );
                  closeEmailModal();
                  document.getElementById("email-subject").value = "";
                  quillInstance.root.innerHTML = "";
                } else {
                  Swal.fire("Error", res.message, "error");
                }
                sendEmailBtn.disabled = false;
                sendEmailBtn.innerHTML = originalHtml;
              })
              .catch(() => {
                Swal.fire("Error", "Failed to send message", "error");
                sendEmailBtn.disabled = false;
                sendEmailBtn.innerHTML = originalHtml;
              });
          };
        }

        if (messageBtn) {
          messageBtn.onclick = openEmailModal;

          if (!staff.has_collection_account) {
            const assignBtn = document.createElement("button");
            assignBtn.id = "sd-assign-btn";
            assignBtn.innerHTML =
              '<i data-lucide="plus-circle" class="w-4 h-4"></i>Assign Collection Account';
            assignBtn.className =
              "px-4 py-2.5 bg-amber-500/10 border border-amber-500/20 text-amber-500 rounded-xl text-xs font-bold hover:bg-amber-500/20 transition-all flex items-center gap-2";
            assignBtn.onclick = () => {
              assignBtn.disabled = true;
              assignBtn.innerHTML =
                '<span class="animate-spin mr-2">◌</span> Assigning...';
              apiFetch(`${FLEZ_API_BASE}/api/staff/assign-collection`, {
                method: "POST",
                body: JSON.stringify({ id: staff.id }),
              })
                .then((r) => r.json())
                .then((res) => {
                  if (res.status) {
                    Swal.fire(
                      "Success",
                      "Collection Account assigned.",
                      "success",
                    ).then(() => window.location.reload());
                  } else {
                    Swal.fire("Error", res.message, "error");
                    assignBtn.disabled = false;
                    assignBtn.innerHTML =
                      '<i data-lucide="plus-circle" class="w-4 h-4"></i>Assign Collection Account';
                  }
                });
            };
            messageBtn.parentNode.insertBefore(assignBtn, messageBtn);
            if (typeof lucide !== "undefined") lucide.createIcons();
          }
        }

        const fieldRole = document.getElementById("field-role");
        if (fieldRole) fieldRole.textContent = staff.job_title || "N/A";
        const fieldStaffId = document.getElementById("field-staff-id");
        if (fieldStaffId)
          fieldStaffId.textContent = `STF-${staff.id.toString().padStart(4, "0")}`;

        // Performance Snapshot logic is handled by the apiFetch below

        // Setup Edit Button
        const editBtn = document.getElementById("sd-edit-btn");
        if (editBtn) {
          editBtn.onclick = () => {
            window.location.href = "/edit-employee/" + staff.id;
          };
        }
        // Fetch Activity Data
        apiFetch(`${FLEZ_API_BASE}/api/staff/activity/${staff.id}`)
          .then((r) => r.json())
          .then((actRes) => {
            if (actRes.status && actRes.data) {
              const act = actRes.data;

              const staffCurSym = getUserCurrencySymbol();
              // Update Performance Snapshot
              document.getElementById("stat-total-trx").textContent =
                act.performance.total_transactions.toLocaleString();
              document.getElementById("stat-today-revenue").textContent =
                staffCurSym +
                act.performance.total_revenue.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                });

              // Update Transactions Tab Summary
              const salesToday = document.getElementById("sd-stat-sales-today");
              if (salesToday)
                salesToday.textContent =
                  staffCurSym +
                  act.performance.total_revenue.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  });
              const salesWeek = document.getElementById("sd-stat-sales-week");
              if (salesWeek)
                salesWeek.textContent =
                  staffCurSym +
                  act.performance.total_revenue.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  });
              const invMonth = document.getElementById("sd-stat-inv-month");
              if (invMonth)
                invMonth.textContent = act.invoices.length.toLocaleString();

              // Update Logins
              const loginsContainer =
                document.getElementById("logins-container");
              if (loginsContainer) {
                if (act.logins.length === 0) {
                  loginsContainer.innerHTML =
                    '<div class="text-sm text-slate-500 italic p-4">No POS logins recorded yet.</div>';
                } else {
                  loginsContainer.innerHTML =
                    '<div class="timeline-line"></div>' +
                    act.logins
                      .map((lg) => {
                        const isOnline = lg.status === "online";
                        return `
                                        <div class="timeline-item">
                                            <div class="timeline-dot ${isOnline ? "" : "offline"}"></div>
                                            <div class="bg-white/5 rounded-2xl p-4">
                                                <div class="flex items-center justify-between mb-1">
                                                    <span class="text-sm font-bold text-white">${isOnline ? "Logged In" : "Logged Out"} — ${lg.terminal_id}</span>
                                                    <span class="text-[10px] ${isOnline ? "text-primary bg-primary/10" : "text-slate-500 bg-white/5"} font-bold uppercase px-2 py-0.5 rounded-full">${isOnline ? "Online" : "Closed"}</span>
                                                </div>
                                                <p class="text-xs text-slate-500">
                                                    ${isOnline ? new Date(lg.login_time).toLocaleString() : new Date(lg.logout_time).toLocaleString()} 
                                                    • IP: ${lg.ip_address || "Unknown"}
                                                </p>
                                            </div>
                                        </div>`;
                      })
                      .join("");
                }
              }

              // Update Transactions
              const trxTbody = document.getElementById("sd-transactions-tbody");
              if (trxTbody) {
                if (act.transactions.length === 0) {
                  trxTbody.innerHTML =
                    '<tr><td colspan="5" class="py-6 text-center text-sm text-slate-500 italic">No transactions processed yet.</td></tr>';
                } else {
                  trxTbody.innerHTML = act.transactions
                    .map((t) => {
                      const isCredit = t.trx_type === "credit";
                      return `
                                        <tr class="hover:bg-white/[0.02] transition-colors group cursor-pointer">
                                            <td class="py-4 px-4"><div class="flex items-center gap-3"><div class="w-10 h-10 rounded-xl ${isCredit ? "bg-primary/10 text-primary" : "bg-rose-500/10 text-rose-500"} flex items-center justify-center shrink-0"><i data-lucide="${isCredit ? "arrow-down-left" : "arrow-up-right"}" class="w-5 h-5"></i></div><div><p class="text-sm font-bold text-white group-hover:text-primary transition-colors">${t.description || t.trx_type}</p><p class="text-[10px] text-slate-500 font-mono mt-0.5">${t.trx_id.substring(0, 8)}</p></div></div></td>
                                            <td class="py-4 px-4 text-xs text-slate-400 capitalize">${t.trx_type}</td>
                                            <td class="py-4 px-4 text-right"><span class="px-2.5 py-0.5 bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 text-[10px] font-bold rounded-full uppercase">${t.trx_status}</span></td>
                                            <td class="py-4 px-4 text-right"><span class="text-sm font-bold ${isCredit ? "text-primary" : "text-white"}">${isCredit ? "+" : "-"}${staffCurSym}${t.trx_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></td>
                                        </tr>`;
                    })
                    .join("");
                }
              }

              // Update Invoices
              const invList = document.getElementById("sd-invoices-list");
              if (invList) {
                if (act.invoices.length === 0) {
                  invList.innerHTML =
                    '<div class="text-sm text-slate-500 italic p-4 border border-white/5 rounded-2xl">No invoices processed yet.</div>';
                }
              }

              // Update Permissions
              const permList = document.getElementById("sd-permissions-list");
              if (permList) {
                const p = act.permissions;
                permList.innerHTML = `
                                    <div class="flex items-center justify-between p-4 bg-white/5 rounded-2xl border border-white/5">
                                        <div><p class="text-sm font-bold text-white">POS Terminal Access</p><p class="text-xs text-slate-500 mt-0.5">Allow login to physical terminals</p></div>
                                        <button id="toggle-pos-access" class="w-10 h-6 bg-${p.pos_access ? "primary" : "white/10"} rounded-full relative transition-colors cursor-pointer"><div class="absolute w-4 h-4 bg-white rounded-full top-1 ${p.pos_access ? "right-1" : "left-1"} transition-all shadow-sm"></div></button>
                                    </div>
                                    <div class="flex items-center justify-between p-4 bg-white/5 rounded-2xl border border-white/5">
                                        <div><p class="text-sm font-bold text-white">Apply Discounts</p><p class="text-xs text-slate-500 mt-0.5">Can override prices and apply custom discounts</p></div>
                                        <button id="toggle-apply-discounts" class="w-10 h-6 bg-${p.can_apply_discounts ? "primary" : "white/10"} rounded-full relative transition-colors cursor-pointer"><div class="absolute w-4 h-4 bg-white rounded-full top-1 ${p.can_apply_discounts ? "right-1" : "left-1"} transition-all shadow-sm"></div></button>
                                    </div>
                                    <div class="flex items-center justify-between p-4 bg-white/5 rounded-2xl border border-white/5">
                                        <div><p class="text-sm font-bold text-white">Process Refunds</p><p class="text-xs text-slate-500 mt-0.5">Authorized to reverse transactions and issue refunds</p></div>
                                        <button id="toggle-process-refunds" class="w-10 h-6 bg-${p.can_process_refunds ? "primary" : "white/10"} rounded-full relative transition-colors cursor-pointer"><div class="absolute w-4 h-4 bg-white rounded-full top-1 ${p.can_process_refunds ? "right-1" : "left-1"} transition-all shadow-sm"></div></button>
                                    </div>
                                `;

                const togglePerm = (field, currentVal, btnId) => {
                  const btn = document.getElementById(btnId);
                  if (!btn) return;
                  btn.onclick = () => {
                    const newVal = !currentVal;
                    btn.style.opacity = "0.5";
                    btn.disabled = true;
                    apiFetch(`${FLEZ_API_BASE}/api/staff/update-details`, {
                      method: "POST",
                      body: JSON.stringify({
                        id: staff.id,
                        [field]: newVal,
                      }),
                    })
                      .then((r) => r.json())
                      .then((res) => {
                        if (res.status) {
                          Swal.fire({
                            toast: true,
                            position: "top-end",
                            icon: "success",
                            title: "Permission updated",
                            showConfirmButton: false,
                            timer: 1500,
                          });
                          btn.style.opacity = "1";
                          btn.disabled = false;
                          // Toggle visuals natively
                          currentVal = newVal;
                          const bgThumb = btn.querySelector("div");
                          if (newVal) {
                            btn.classList.remove("bg-white/10");
                            btn.classList.add("bg-primary");
                            bgThumb.classList.remove("left-1");
                            bgThumb.classList.add("right-1");
                          } else {
                            btn.classList.remove("bg-primary");
                            btn.classList.add("bg-white/10");
                            bgThumb.classList.remove("right-1");
                            bgThumb.classList.add("left-1");
                          }
                        } else {
                          Swal.fire(
                            "Error",
                            res.message || "Failed to update permission",
                            "error",
                          );
                          btn.style.opacity = "1";
                          btn.disabled = false;
                        }
                      })
                      .catch(() => {
                        Swal.fire("Error", "An error occurred", "error");
                        btn.style.opacity = "1";
                        btn.disabled = false;
                      });
                  };
                };

                togglePerm("pos_access", p.pos_access, "toggle-pos-access");
                togglePerm(
                  "can_apply_discounts",
                  p.can_apply_discounts,
                  "toggle-apply-discounts",
                );
                togglePerm(
                  "can_process_refunds",
                  p.can_process_refunds,
                  "toggle-process-refunds",
                );
              }

              if (window.lucide) window.lucide.createIcons();

              // Reset Password
              const resetPwdBtn = document.getElementById("reset-pwd-btn");
              if (resetPwdBtn) {
                resetPwdBtn.onclick = () => {
                  Swal.fire({
                    title: "Reset Password?",
                    text: "This will invalidate their current password and generate a temporary one.",
                    icon: "warning",
                    showCancelButton: true,
                    confirmButtonText: "Yes, reset it!",
                    confirmButtonColor: "#f59e0b",
                  }).then((result) => {
                    if (result.isConfirmed) {
                      resetPwdBtn.disabled = true;
                      resetPwdBtn.innerHTML =
                        '<span class="animate-spin mr-2">◌</span> Resetting...';
                      apiFetch(`${FLEZ_API_BASE}/api/staff/reset-password`, {
                        method: "POST",
                        body: JSON.stringify({ id: staff.id }),
                      })
                        .then((r) => r.json())
                        .then((res) => {
                          if (res.status) {
                            Swal.fire({
                              title: "Password Reset",
                              html: `The new temporary password is:<br><br><strong class="text-xl text-primary bg-white/5 px-4 py-2 rounded-lg tracking-widest">${res.new_password}</strong><br><br><span class="text-sm text-slate-400">Please communicate this to the staff member.</span>`,
                              icon: "success",
                            });
                          } else {
                            Swal.fire("Error", res.message, "error");
                          }
                          resetPwdBtn.disabled = false;
                          resetPwdBtn.innerHTML =
                            '<i data-lucide="refresh-cw" class="w-4 h-4"></i>Reset Password';
                          if (window.lucide) window.lucide.createIcons();
                        });
                    }
                  });
                };
              }
            }
          });

        // Wire up Actions
        initStaffActions(staff);
      }
    });

  function initStaffActions(staff) {
    // Suspend/Activate
    const suspendBtn = document.getElementById("suspend-btn");
    if (suspendBtn) {
      suspendBtn.onclick = () => {
        const isSuspending = staff.is_active;
        const action = isSuspending ? "suspend" : "activate";
        const newStatus = isSuspending ? "suspended" : "active";

        Swal.fire({
          title: `Are you sure?`,
          text: `This will ${action} the staff member's POS access.`,
          icon: "warning",
          showCancelButton: true,
          confirmButtonColor: "#cfff45",
          cancelButtonColor: "#ef4444",
          confirmButtonText: `Yes, ${action}!`,
        }).then((result) => {
          if (result.isConfirmed) {
            apiFetch(`${FLEZ_API_BASE}/api/staff/update-status`, {
              method: "POST",
              body: JSON.stringify({ id: staff.id, status: newStatus }),
            })
              .then((r) => r.json())
              .then((res) => {
                if (res.status) {
                  Swal.fire("Success!", res.message, "success");
                  initStaffDetails(); // Reload
                } else {
                  Swal.fire("Error", res.message, "error");
                }
              });
          }
        });
      };
    }

    // Delete
    const deleteBtn = document.getElementById("delete-btn");
    if (deleteBtn) {
      deleteBtn.onclick = () => {
        Swal.fire({
          title: "CRITICAL ACTION",
          text: "You are about to PERMANENTLY delete this staff member. This cannot be undone!",
          icon: "error",
          showCancelButton: true,
          confirmButtonColor: "#ef4444",
          cancelButtonColor: "#64748b",
          confirmButtonText: "Delete Permanently",
        }).then((result) => {
          if (result.isConfirmed) {
            apiFetch(`${FLEZ_API_BASE}/api/staff/delete`, {
              method: "POST",
              body: JSON.stringify({ id: staff.id }),
            })
              .then((r) => r.json())
              .then((res) => {
                if (res.status) {
                  Swal.fire(
                    "Deleted!",
                    "Staff account has been removed.",
                    "success",
                  ).then(() => {
                    if (window.flezSwup)
                      window.flezSwup.navigate("/organization");
                    else window.location.href = "/organization";
                  });
                } else {
                  Swal.fire("Error", res.message, "error");
                }
              });
          }
        });
      };
    }
  }
};

/**
 * TTS Modal — initialized on every page view (Swup or hard load).
 * Because the modal lives inside #swup and gets replaced on navigation,
 * we bind fresh event listeners each time instead of relying on a
 * one-time delegated listener registered by ai_manager.js.
 */
function initTtsModal() {
  const settingsBtn = document.getElementById("tts-settings-btn");
  const modal = document.getElementById("tts-settings-modal");
  if (!settingsBtn || !modal) return; // not on ai-manager page

  const innerPanel = modal.querySelector(".transform");

  function openModal() {
    modal.classList.remove("opacity-0", "pointer-events-none");
    if (innerPanel) innerPanel.classList.remove("scale-95");
  }

  function closeModal() {
    modal.classList.add("opacity-0", "pointer-events-none");
    if (innerPanel) innerPanel.classList.add("scale-95");
  }

  // Open on gear-icon click
  settingsBtn.addEventListener("click", function (e) {
    e.preventDefault();
    e.stopPropagation();
    openModal();
  });

  // Close on backdrop click
  modal.addEventListener("click", function (e) {
    if (e.target === modal) closeModal();
  });

  // Close on any [data-modal-close="tts-settings-modal"] button
  modal
    .querySelectorAll('[data-modal-close="tts-settings-modal"]')
    .forEach((btn) => {
      btn.addEventListener("click", closeModal);
    });

  // Expose globally so legacy onclick="" attributes and ai_manager.js still work
  window.openTtsModal = openModal;
  window.closeTtsModal = closeModal;
}

// Initial Call — runs once on hard load/reload
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    initApp();
    initTtsModal();
  });
} else {
  initApp();
  initTtsModal();
}

/**
 * Store Page Logic
 */
function initStore() {
  const modal = document.getElementById("add-items-modal");
  const openBtn = document.getElementById("open-add-items");
  const closeBtns = document.querySelectorAll(".closeModal");
  const searchInput = document.getElementById("product-search");
  const selectionList = document.getElementById("product-selection-list");
  const addSelectedBtn = document.getElementById("add-selected-items");
  const storeGrid = document.getElementById("store-grid");
  const emptyState = document.getElementById("store-empty-state");
  const statusBadge = document.getElementById("store-status-badge");

  let allProducts = [];
  let selectedItems = new Set();

  // Sync UI with current state
  const userData = JSON.parse(localStorage.getItem("user_data") || "{}");
  if (userData && Array.isArray(userData.items)) {
    allProducts = userData.items;
    window.currentStoreItems = allProducts
      .filter((p) => p.in_store)
      .map((p) => ({
        ...p,
        featured: p.is_featured,
      }));
  } else {
    window.currentStoreItems = [];
  }

  const currSym = getUserCurrencySymbol(userData);
  const toggle = document.getElementById("store-publish-toggle");
  const previewBtn = document.getElementById("preview-store-btn");

  const business = userData.business_details?.[0];
  if (business) {
    if (toggle) {
      toggle.checked = business.is_published;
      updateStoreStatusLabel(business.is_published);
    }
    if (previewBtn) {
      const slug = business.store_slug || "";
      if (slug) {
        const storeUrl = typeof window.buildStoreUrl === "function"
          ? window.buildStoreUrl(slug, business.store_custom_domain)
          : (function() {
              const protocol = window.location.protocol;
              const hostname = window.location.hostname;
              const port = window.location.port ? `:${window.location.port}` : "";
              if (business.store_custom_domain) {
                const cd = business.store_custom_domain.trim().replace(/^https?:\/\//, "").replace(/\/+$/, "");
                return `${protocol}//${cd}/`;
              }
              if (hostname === "localhost" || hostname === "127.0.0.1") {
                return `${protocol}//${slug}.localhost${port}/`;
              }
              const parts = hostname.split(".");
              const isIp = parts.every(p => !isNaN(p));
              const root = (!isIp && parts.length > 2) ? parts.slice(-2).join(".") : hostname;
              return `${protocol}//${slug}.${root}${port}/`;
            })();
        previewBtn.href = storeUrl;
        previewBtn.classList.remove("opacity-50", "pointer-events-none");
        previewBtn.removeAttribute("title");
      } else {
        previewBtn.href = "#";
        previewBtn.classList.add("opacity-50", "pointer-events-none");
        previewBtn.title = "Please set a store slug in settings first";
      }
    }

    const pendingCountEl = document.getElementById("pending-orders-count");
    if (pendingCountEl) {
      pendingCountEl.innerText = business.online_orders_pending_count || 0;
    }
  }

  // Sync custom domain banner visibility
  const domainBanner = document.getElementById("customDomainBanner");
  if (domainBanner) {
    const hasCustomDomain = !!(business && business.store_custom_domain);
    if (hasCustomDomain) {
      domainBanner.classList.add("hidden");
    } else {
      domainBanner.classList.remove("hidden");
    }
  }

  function updateStoreStatusLabel(isPublished) {
    const label = document.getElementById("store-status-text");
    if (label) {
      label.innerText = isPublished ? "Online" : "Offline";
      if (isPublished) {
        label.classList.remove("text-slate-400");
        label.classList.add("text-emerald-500");
      } else {
        label.classList.remove("text-emerald-500");
        label.classList.add("text-slate-400");
      }
    }
  }

  if (toggle) {
    toggle.onchange = async () => {
      const isPublished = toggle.checked;
      updateStoreStatusLabel(isPublished);
      try {
        const res = await apiFetch(
          `${window.CONFIG.API_BASE}/api/user/store/setup`,
          {
            method: "POST",
            body: JSON.stringify({ is_published: isPublished }),
          },
        );
        const result = await res.json();
        if (result.status) {
          showToast(
            "Store Updated",
            `Your store is now ${isPublished ? "Published" : "Unpublished"}`,
            "success",
          );

          // Refresh user data to sync other UI components
          const freshRes = await apiFetch(
            `${window.CONFIG.API_BASE}/api/user/data`,
            { method: "POST" },
          );
          const freshData = await freshRes.json();
          if (freshData.status) {
            localStorage.setItem("user_data", JSON.stringify(freshData.data));
            renderUserData();
          }
        } else {
          throw new Error(result.message || "Update failed");
        }
      } catch (err) {
        showToast("Sync Error", err.message, "error");
        toggle.checked = !isPublished;
      }
    };
  }

  // Fetch actual products from backend
  async function fetchProducts() {
    try {
      const res = await apiFetch(`${window.CONFIG.API_BASE}/api/user/data`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.status && data.data && data.data.items) {
        allProducts = data.data.items;
        // Sync currentStoreItems with actual backend data
        window.currentStoreItems = allProducts
          .filter((p) => p.in_store)
          .map((p) => ({
            ...p,
            featured: p.is_featured,
          }));

        localStorage.setItem("user_data", JSON.stringify(data.data));
        syncStoreViews();
        renderUserData(); // Update views count in header/stats
      }
    } catch (err) {
      console.error("Failed to fetch products for store:", err);
    }
  }

  function openAddModal() {
    const m = modal || document.getElementById("add-items-modal");
    if (!m) return;
    const dropdown = document.getElementById("store-options-dropdown");
    if (dropdown) dropdown.classList.add("hidden");
    m.classList.remove("hidden");
    const sInput = document.getElementById("product-search");
    if (sInput) sInput.value = "";
    if (!allProducts || allProducts.length === 0) {
      fetchProducts().then(() => renderProductSelection(""));
    } else {
      renderProductSelection("");
    }
  }

  window.storeOpenAddModal = openAddModal;
  window.openAddStoreModal = openAddModal;

  // Attach click listener to all Add Product / Add Items buttons on the Store page
  const addTriggers = [
    document.getElementById("open-add-items"),
    document.getElementById("add-first-product-btn"),
    document.getElementById("dropdown-add-items"),
  ].filter(Boolean);

  addTriggers.forEach((btn) => {
    btn.onclick = (e) => {
      e.preventDefault();
      openAddModal();
    };
  });

  document
    .querySelectorAll(".open-add-items-btn, .open-add-items")
    .forEach((btn) => {
      btn.onclick = (e) => {
        e.preventDefault();
        openAddModal();
      };
    });

  // Store options dropdown toggle
  const optionsBtn = document.getElementById("store-options-btn");
  const optionsDropdown = document.getElementById("store-options-dropdown");
  const optionsContainer = document.getElementById("store-options-container");

  if (optionsBtn && optionsDropdown) {
    optionsBtn.onclick = (e) => {
      e.stopPropagation();
      optionsDropdown.classList.toggle("hidden");
    };
    document.addEventListener("click", (e) => {
      if (optionsContainer && !optionsContainer.contains(e.target)) {
        optionsDropdown.classList.add("hidden");
      }
    });
  }

  const allCloseBtns = document.querySelectorAll(
    ".closeModal, #add-items-modal .closeModal",
  );
  allCloseBtns.forEach((btn) => {
    btn.onclick = () => {
      const m = modal || document.getElementById("add-items-modal");
      if (m) m.classList.add("hidden");
    };
  });

  if (modal) {
    modal.onclick = (e) => {
      if (e.target === modal) modal.classList.add("hidden");
    };
  }

  if (searchInput) {
    searchInput.oninput = (e) => {
      renderProductSelection(e.target.value || "");
    };
  }

  function renderProductSelection(query = "") {
    const q = (query || "").toLowerCase();
    const filtered = allProducts.filter(
      (p) =>
        (p.item_name || "").toLowerCase().includes(q) &&
        !window.currentStoreItems.some((si) => si.item_id === p.item_id),
    );

    if (filtered.length === 0 && allProducts.length > 0) {
      selectionList.innerHTML =
        '<div class="text-center py-10 text-slate-500"><p class="text-sm">No new products to add to store.</p></div>';
      return;
    } else if (allProducts.length === 0) {
      selectionList.innerHTML = `
                <div class="text-center py-10 text-slate-500">
                    <p class="text-sm mb-3">No products found in your inventory.</p>
                    <a href="/add-product" class="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-black font-bold text-xs rounded-xl shadow-lg hover:bg-primary/90 transition-all">
                        <i data-lucide="plus" class="w-4 h-4"></i> Add a Product First
                    </a>
                </div>`;
      if (typeof lucide !== "undefined") lucide.createIcons();
      return;
    }

    // Use currSym from store management scope

    selectionList.innerHTML = filtered
      .map((p) => {
        const hasImage = p.images && p.images.length > 0;
        const isSelected = selectedItems.has(p.item_id);

        return `
                <div class="flex items-center justify-between p-4 ${hasImage ? "bg-white/5 border border-white/5" : "bg-rose-500/5 border border-rose-500/10"} rounded-2xl transition-all ${hasImage ? "hover:bg-white/10 cursor-pointer product-select-item" : "opacity-90 cursor-not-allowed"} ${isSelected ? "border-primary bg-primary/5" : ""}" data-id="${p.item_id}">
                    <div class="flex items-center gap-4">
                        <div class="w-12 h-12 rounded-xl ${hasImage ? "bg-white/5" : "bg-rose-500/10"} flex items-center justify-center text-slate-500 overflow-hidden relative border border-white/5">
                            ${
                              hasImage
                                ? `<img src="${p.images[0].image}" class="w-full h-full object-cover">`
                                : `<i data-lucide="image" class="w-6 h-6 text-rose-500/40"></i>`
                            }
                        </div>
                        <div>
                            <p class="text-sm font-bold text-white">${p.item_name}</p>
                            ${
                              hasImage
                                ? `<p class="text-[10px] text-slate-500">${p.item_department || "General"} • ${currSym}${Number(p.item_amount).toLocaleString()}</p>`
                                : `<div class="flex flex-col gap-2 mt-1">
                                     <div class="flex items-center gap-1.5 text-rose-500">
                                         <i data-lucide="alert-triangle" class="w-3 h-3"></i>
                                         <span class="text-[10px] font-bold uppercase tracking-tight">Requires Image</span>
                                     </div>
                                     <a href="/edit-product?id=${p.item_id}" 
                                        class="w-fit text-[10px] bg-primary/10 hover:bg-primary text-primary hover:text-white px-3 py-1 rounded-lg transition-all flex items-center gap-1.5 font-bold border border-primary/20" 
                                        onclick="event.stopPropagation()">
                                       <i data-lucide="image-plus" class="w-3 h-3"></i> Upload Image to List
                                     </a>
                                   </div>`
                            }
                        </div>
                    </div>
                    ${
                      hasImage
                        ? `
                    <div class="w-6 h-6 rounded-full border-2 border-white/10 flex items-center justify-center ${isSelected ? "bg-primary border-primary" : ""}">
                        ${isSelected ? '<i data-lucide="check" class="w-4 h-4 text-white"></i>' : ""}
                    </div>
                    `
                        : `
                    <div class="w-10 h-10 flex items-center justify-center text-rose-500/20">
                        <i data-lucide="lock" class="w-5 h-5"></i>
                    </div>
                    `
                    }
                </div>
            `;
      })
      .join("");

    if (typeof lucide !== "undefined") lucide.createIcons();

    document.querySelectorAll(".product-select-item").forEach((item) => {
      item.onclick = function () {
        const id = this.dataset.id;
        const product = allProducts.find((p) => p.item_id === id);
        if (!product || !product.images || product.images.length === 0) return;

        if (selectedItems.has(id)) selectedItems.delete(id);
        else selectedItems.add(id);
        renderProductSelection(searchInput.value);
      };
    });
  }

  if (addSelectedBtn) {
    addSelectedBtn.onclick = async () => {
      const idsToAdd = Array.from(selectedItems);
      if (idsToAdd.length === 0) return;

      addSelectedBtn.disabled = true;
      addSelectedBtn.innerHTML =
        '<i class="lucide-loader w-4 h-4 animate-spin"></i> Adding...';

      try {
        const res = await apiFetch(
          `${window.CONFIG.API_BASE}/api/user/store/items/sync`,
          {
            method: "POST",
            body: JSON.stringify({ action: "add", item_ids: idsToAdd }),
          },
        );
        const result = await res.json();
        if (result.status) {
          selectedItems.clear();
          modal.classList.add("hidden");
          await fetchProducts(); // Refresh data
          showToast("Success", "Items added to store", "success");
        } else {
          showToast("Error", result.message, "error");
        }
      } catch (err) {
        showToast("Error", err.message, "error");
      } finally {
        addSelectedBtn.disabled = false;
        addSelectedBtn.innerHTML = "Add Selected Items";
      }
    };
  }

  window.syncStoreViews = () => {
    if (!storeGrid) return;
    if (window.currentStoreItems.length === 0) {
      if (emptyState) emptyState.classList.remove("hidden");
      storeGrid.classList.add("hidden");
      document.getElementById("store-list-view")?.classList.add("hidden");
    } else {
      if (emptyState) emptyState.classList.add("hidden");
      if (
        document.getElementById("store-list-view")?.classList.contains("hidden")
      ) {
        storeGrid.classList.remove("hidden");
      }
      renderStoreGrid();
      renderStoreList();
    }
    updateStoreStats();
  };

  function renderStoreGrid() {
    storeGrid.innerHTML = window.currentStoreItems
      .map((p) => {
        const isDigital = !!(
          p.is_digital ||
          p.digital_file ||
          p.digital_file_url
        );
        const isPromo = !!(
          p.is_promo ||
          p.promo_amount ||
          p.promo_percentage ||
          p.discounted_price
        );
        const promoVal = p.promo_amount || p.promo_percentage;

        const { digitalBadge: digitalMicroBadge, promoBadge: promoMicroBadge } =
          formatProductMicroBadges(isDigital, isPromo, promoVal);

        return `
            <div class="glass-card p-3 sm:p-4 rounded-2xl sm:rounded-3xl group transition-all hover:border-primary/30 relative flex flex-col justify-between" data-id="${p.item_id}">
                <div>
                    <div class="relative aspect-square bg-white/5 rounded-2xl mb-3 sm:mb-4 overflow-hidden flex items-center justify-center">
                        ${
                          p.images && p.images.length > 0
                            ? `<img src="${p.images[0].image}" class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500">`
                            : `<i data-lucide="box" class="w-12 h-12 text-slate-700 group-hover:scale-110 transition-transform"></i>`
                        }
                        ${p.featured ? '<div class="absolute top-2 left-2"><span class="bg-primary/20 text-primary text-[8px] font-bold px-2 py-0.5 rounded-full uppercase">Featured</span></div>' : ""}
                    </div>
                    <h4 class="text-sm font-bold text-white mb-1 truncate">${p.item_name}</h4>
                    ${
                      isDigital || isPromo
                        ? `
                    <div class="flex items-center flex-wrap gap-1.5 mb-1.5">
                        ${digitalMicroBadge}
                        ${promoMicroBadge}
                    </div>`
                        : ""
                    }
                    <p class="text-[10px] text-slate-500 mb-2 sm:mb-3 truncate">${p.item_department || "General"} • ${isDigital ? "Instant Delivery" : p.item_quantity + " in stock"}</p>
                </div>
                <div class="pt-2.5 sm:pt-3 border-t border-white/5 mt-auto flex flex-col min-[480px]:flex-row min-[480px]:items-center justify-between gap-2">
                    <div class="min-w-0">
                        <p class="text-[10px] sm:text-xs text-slate-500 uppercase tracking-wider font-semibold">Price</p>
                        <p class="text-xs sm:text-sm font-bold text-primary truncate">${currSym}${Number(p.item_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                    </div>
                    <div class="flex items-center justify-between min-[480px]:justify-end gap-1.5 sm:gap-2 shrink-0 pt-1.5 min-[480px]:pt-0 border-t border-white/5 min-[480px]:border-t-0">
                        <div class="flex items-center gap-1.5 shrink-0">
                            <span class="text-[10px] text-slate-400 font-medium min-[480px]:hidden">Featured</span>
                            <button class="switch shrink-0" role="switch" aria-checked="${p.featured}" onclick="toggleFeatured('${p.item_id}')" title="Featured toggle">
                                <span class="switch-thumb"></span>
                            </button>
                        </div>
                        <div class="relative dropdown-container shrink-0">
                            <button type="button" class="p-1 sm:p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-all dropdown-toggle" title="Options">
                                <i data-lucide="more-vertical" class="w-4 h-4 pointer-events-none"></i>
                            </button>
                            <div class="dropdown-menu absolute right-0 bottom-full mb-2 w-32 bg-white dark:bg-[#151922] border border-slate-200 dark:border-white/10 rounded-xl shadow-xl py-1.5 z-50">
                                <button type="button" class="w-full text-left px-3.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2 transition-colors" onclick="editProduct('${p.item_id}')">
                                    <i data-lucide="edit-3" class="w-3.5 h-3.5"></i> Edit
                                </button>
                                <button type="button" class="w-full text-left px-3.5 py-2 text-xs font-semibold text-rose-500 hover:bg-rose-500/10 flex items-center gap-2 transition-colors" onclick="confirmRemoveStoreItem('${p.item_id}', '${(p.item_name || "this item").replace(/'/g, "\\'")}')">
                                    <i data-lucide="trash-2" class="w-3.5 h-3.5"></i> Delete
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            `;
      })
      .join("");
    if (typeof lucide !== "undefined") lucide.createIcons();
    if (window.initDropdownListeners) window.initDropdownListeners();
  }

  window.renderStoreList = () => {
    const tbody = document.getElementById("store-list-tbody");
    if (!tbody) return;
    tbody.innerHTML = window.currentStoreItems
      .map((p) => {
        const isDigital = !!(
          p.is_digital ||
          p.digital_file ||
          p.digital_file_url
        );
        const isPromo = !!(
          p.is_promo ||
          p.promo_amount ||
          p.promo_percentage ||
          p.discounted_price
        );
        const promoVal = p.promo_amount || p.promo_percentage;

        const { digitalBadge: digitalMicroBadge, promoBadge: promoMicroBadge } =
          formatProductMicroBadges(isDigital, isPromo, promoVal);

        return `
            <tr class="group hover:bg-white/5 transition-all">
                <td class="px-6 py-4">
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-slate-500 overflow-hidden shrink-0">
                            ${
                              p.images && p.images.length > 0
                                ? `<img src="${p.images[0].image}" class="w-full h-full object-cover">`
                                : `<i data-lucide="box" class="w-4 h-4"></i>`
                            }
                        </div>
                        <div class="min-w-0">
                            <div class="flex items-center gap-1.5 flex-wrap">
                                <p class="text-sm font-bold text-white truncate">${p.item_name}</p>
                                ${digitalMicroBadge}
                                ${promoMicroBadge}
                            </div>
                            <p class="text-[10px] text-slate-500">${p.item_department || "General"}</p>
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4 text-center">
                    <button class="switch mx-auto" role="switch" aria-checked="${p.featured}" onclick="toggleFeatured('${p.item_id}')" title="Featured toggle">
                        <span class="switch-thumb"></span>
                    </button>
                </td>
                <td class="px-6 py-4 text-sm font-bold text-primary">${currSym}${Number(p.item_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                <td class="px-6 py-4 text-sm text-slate-400">${isDigital ? '<span class="text-blue-400 font-bold text-xs">Digital</span>' : p.item_quantity + " units"}</td>
                <td class="px-6 py-4 text-right">
                    <div class="relative dropdown-container inline-block text-right">
                        <button type="button" class="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-all dropdown-toggle" title="Options">
                            <i data-lucide="more-vertical" class="w-4 h-4 pointer-events-none"></i>
                        </button>
                        <div class="dropdown-menu absolute right-0 top-full mt-1.5 w-32 bg-white dark:bg-[#151922] border border-slate-200 dark:border-white/10 rounded-xl shadow-2xl py-1.5 z-50 text-left">
                            <button type="button" class="w-full text-left px-3.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2 transition-colors" onclick="editProduct('${p.item_id}')">
                                <i data-lucide="edit-3" class="w-3.5 h-3.5"></i> Edit
                            </button>
                            <button type="button" class="w-full text-left px-3.5 py-2 text-xs font-semibold text-rose-500 hover:bg-rose-500/10 flex items-center gap-2 transition-colors" onclick="confirmRemoveStoreItem('${p.item_id}', '${(p.item_name || "this item").replace(/'/g, "\\'")}')">
                                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i> Delete
                            </button>
                        </div>
                    </div>
                </td>
            </tr>
            `;
      })
      .join("");
    if (typeof lucide !== "undefined") lucide.createIcons();
    if (window.initDropdownListeners) window.initDropdownListeners();
  };

  window.confirmRemoveStoreItem = (id, name = "this item") => {
    if (typeof Swal !== "undefined") {
      Swal.fire({
        title: "Remove from Store?",
        text: `Are you sure you want to remove "${name}" from your store?`,
        icon: "warning",
        showCancelButton: true,
        confirmButtonColor: "#ef4444",
        cancelButtonColor: "#64748b",
        confirmButtonText: "Yes, remove it!",
      }).then(async (result) => {
        if (result.isConfirmed) {
          removeStoreItem(id);
        }
      });
    } else {
      if (
        confirm(`Are you sure you want to remove "${name}" from your store?`)
      ) {
        removeStoreItem(id);
      }
    }
  };

  window.removeStoreItem = async (id) => {
    try {
      const res = await apiFetch(
        `${window.CONFIG.API_BASE}/api/user/store/items/sync`,
        {
          method: "POST",
          body: JSON.stringify({ action: "remove", item_ids: [id] }),
        },
      );
      const result = await res.json();
      if (result.status) {
        await fetchProducts();
      } else {
        showToast("Error", result.message, "error");
      }
    } catch (err) {
      showToast("Error", err.message, "error");
    }
  };

  window.toggleFeatured = async (id) => {
    const item = window.currentStoreItems.find((p) => p.item_id === id);
    if (item) {
      const newStatus = !item.featured;
      try {
        const res = await apiFetch(
          `${window.CONFIG.API_BASE}/api/user/store/items/sync`,
          {
            method: "POST",
            body: JSON.stringify({
              action: "featured",
              item_id: id,
              is_featured: newStatus,
            }),
          },
        );
        const result = await res.json();
        if (result.status) {
          await fetchProducts();
        } else {
          showToast("Error", result.message, "error");
        }
      } catch (err) {
        showToast("Error", err.message, "error");
      }
    }
  };

  window.updateStoreStats = () => {
    const liveEl = document.getElementById("live-items-count");
    const featEl = document.getElementById("featured-items-count");
    const viewsEl = document.getElementById("store-views-count");

    if (liveEl) liveEl.innerText = window.currentStoreItems.length;
    if (featEl)
      featEl.innerText = window.currentStoreItems.filter(
        (p) => p.featured,
      ).length;

    const userData = JSON.parse(localStorage.getItem("user_data") || "{}");
    const business = userData.business_details?.[0];
    if (viewsEl && business)
      viewsEl.innerText = (business.store_views || 0).toLocaleString();
  };

  fetchProducts();
}

/**
 * Store Settings Page Logic
 */
// Actual logic moved to store-settings.js

/**
 * Store Layouts Infinite Scroll
 * NOTE: Does NOT depend on a <template> DOM element — all card HTML is generated
 * inline so it works correctly on Swup navigation (where only #swup is replaced).
 */
function initStoreLayouts() {
  if (typeof window.highlightSelectedLayout === "function") {
    window.highlightSelectedLayout();
  }
  if (typeof lucide !== "undefined") {
    lucide.createIcons();
  }
}

/**
 * POS Download Logic
 */
function initPosDownload() {
  const toggle = document.getElementById("download-dropdown-toggle");
  const menu = document.getElementById("download-dropdown-menu");
  const chevron = document.getElementById("dropdown-chevron");
  const osNameEl = document.getElementById("os-name");
  const osIconEl = document.getElementById("os-icon");

  if (!toggle || !menu || !chevron || !osNameEl || !osIconEl) return;

  // Clear any previous listeners or state
  let isOpen = false;
  menu.classList.add("opacity-0", "translate-y-[-10px]", "pointer-events-none");
  menu.classList.remove("opacity-100", "translate-y-0");
  chevron.classList.remove("rotate-180");

  function detectOS() {
    const userAgent = window.navigator.userAgent;
    if (userAgent.indexOf("Mac") !== -1) return "macOS";
    if (userAgent.indexOf("Win") !== -1) return "Windows";
    if (userAgent.indexOf("Linux") !== -1) return "Linux";
    return "Windows";
  }

  function updateOSUI(os) {
    osNameEl.textContent = os;
    if (os === "macOS") {
      osIconEl.setAttribute("data-lucide", "apple");
    } else if (os === "Linux") {
      osIconEl.setAttribute("data-lucide", "terminal");
    } else {
      osIconEl.setAttribute("data-lucide", "monitor");
    }
    if (typeof lucide !== "undefined") lucide.createIcons();
  }

  if (!osNameEl.dataset.initialized) {
    updateOSUI(detectOS());
    osNameEl.dataset.initialized = "true";
  }

  window.setManualOS = function (os) {
    updateOSUI(os);
    isOpen = false;
    menu.classList.add(
      "opacity-0",
      "translate-y-[-10px]",
      "pointer-events-none",
    );
    menu.classList.remove("opacity-100", "translate-y-0");
    chevron.classList.remove("rotate-180");
  };

  // Make toggle function independent
  const clickHandler = function (e) {
    if (e) e.preventDefault();
    isOpen = !isOpen;
    if (isOpen) {
      menu.classList.remove(
        "opacity-0",
        "translate-y-[-10px]",
        "pointer-events-none",
      );
      menu.classList.add("opacity-100", "translate-y-0");
      chevron.classList.add("rotate-180");
    } else {
      menu.classList.add(
        "opacity-0",
        "translate-y-[-10px]",
        "pointer-events-none",
      );
      menu.classList.remove("opacity-100", "translate-y-0");
      chevron.classList.remove("rotate-180");
    }
  };

  // Remove existing listener if any and add
  const newToggle = toggle.cloneNode(true);
  toggle.parentNode.replaceChild(newToggle, toggle);
  newToggle.addEventListener("click", clickHandler);

  // Outside click
  document.addEventListener("click", (e) => {
    if (!newToggle.contains(e.target) && !menu.contains(e.target) && isOpen) {
      isOpen = false;
      menu.classList.add(
        "opacity-0",
        "translate-y-[-10px]",
        "pointer-events-none",
      );
      menu.classList.remove("opacity-100", "translate-y-0");
      chevron.classList.remove("rotate-180");
    }
  });
}

/**
 * Payroll Page Logic
 */

/**
 * Categories Page Logic
 */
window.initCategories = () => {
  const grid = document.getElementById("categories-grid");
  const searchInput = document.getElementById("category-search");
  if (!grid) return;

  // Fetching extracted to window scope for reuse
  window.fetchCategories = (search = "") => {
    apiFetch(`${FLEZ_API_BASE}/api/categories/filter`, {
      method: "POST",
      body: JSON.stringify({ search }),
    })
      .then((r) => r.json())
      .then((res) => {
        if (res.status) {
          if (res.data.length === 0) {
            grid.innerHTML = `
                        <div class="col-span-full flex flex-col items-center justify-center py-16 text-center">
                            <div class="w-16 h-16 bg-white/5 rounded-2xl flex items-center justify-center mb-4 text-slate-400">
                                <i data-lucide="package-x" class="w-8 h-8"></i>
                            </div>
                            <h3 class="text-xl font-bold text-white mb-2">No categories found</h3>
                            <p class="text-slate-400 max-w-sm mb-6">You haven't created any product categories yet. Create one to organize your inventory.</p>
                            <button onclick="openAddModal()" class="px-6 py-3 bg-primary/20 text-primary hover:bg-primary/30 rounded-xl font-bold transition-all inline-flex items-center gap-2">
                                <i data-lucide="plus" class="w-4 h-4"></i> Add First Category
                            </button>
                        </div>
                    `;
          } else {
            grid.innerHTML = res.data
              .map(
                (cat) => `
                        <div class="glass-card p-6 rounded-3xl hover:bg-white/5 transition-all group relative">
                            <div class="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary mb-4 group-hover:scale-110 transition-transform">
                                <i data-lucide="${cat.icon || "package"}" class="w-6 h-6"></i>
                            </div>
                            <h4 class="text-lg font-bold text-white mb-1">${cat.category_name}</h4>
                            <p class="text-xs text-slate-500 mb-4">${cat.active_products} Active Products</p>
                            <div class="flex justify-between items-center pt-4 border-t border-white/5">
                                <span class="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Inventory</span>
                                <div class="relative dropdown-container">
                                    <button class="text-slate-500 hover:text-white transition-colors dropdown-toggle" data-id="${cat.id}">
                                        <i data-lucide="more-vertical" class="w-4 h-4 pointer-events-none"></i>
                                    </button>
                                    <div class="dropdown-menu absolute right-0 bottom-full mb-2 w-32 bg-white/95 dark:bg-bg-card border border-black/10 dark:border-white/10 rounded-xl shadow-2xl py-2 z-50">
                                        <button class="w-full text-left px-4 py-2 text-xs text-slate-600 dark:text-slate-300 hover:bg-black/5 dark:hover:bg-white/5 flex items-center gap-2" onclick="editCategory('${cat.id}', '${cat.category_name}')">
                                            <i data-lucide="edit-2" class="w-3.5 h-3.5"></i> Edit
                                        </button>
                                        <button class="w-full text-left px-4 py-2 text-xs text-rose-500 hover:bg-rose-500/10 flex items-center gap-2" onclick="deleteCategory('${cat.id}', '${cat.category_name}')">
                                            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i> Delete
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `,
              )
              .join("");
          }
          if (window.lucide) window.lucide.createIcons();
          if (window.initDropdownListeners) window.initDropdownListeners();
        }
      });
  };

  window.fetchCategories();
};

// Global action handlers
window.editCategory = (id, name) => {
  const modal = document.getElementById("edit-category-modal");
  const input = document.getElementById("edit-cat-name");
  const saveBtn = document.getElementById("save-cat-btn");

  if (!modal || !input) return;

  input.value = name;
  modal.classList.add("show");
  if (window.lucide) window.lucide.createIcons();

  saveBtn.onclick = () => {
    const newName = input.value.trim();
    if (!newName) return;

    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="animate-spin mr-2">◌</span> Saving...';

    apiFetch(`${FLEZ_API_BASE}/api/user/data/update/category`, {
      method: "POST",
      body: JSON.stringify({ category_id: id, category_name: newName }),
    })
      .then((r) => r.json())
      .then((res) => {
        saveBtn.disabled = false;
        saveBtn.innerHTML = "Save Changes";
        if (res.status) {
          Swal.fire("Updated!", "Category name has been changed.", "success");
          closeEditModal();
          const searchInput = document.getElementById("category-search");
          if (window.fetchCategories)
            fetchCategories(searchInput ? searchInput.value : "");
        } else {
          Swal.fire("Error", res.message, "error");
        }
      });
  };
};

window.closeEditModal = () => {
  const modal = document.getElementById("edit-category-modal");
  if (modal) modal.classList.remove("show");
};

window.openAddModal = () => {
  const modal = document.getElementById("add-category-modal");
  const input = document.getElementById("add-cat-name");
  const createBtn = document.getElementById("create-cat-btn");

  if (!modal || !input) return;

  input.value = "";
  modal.classList.add("show");
  if (window.lucide) window.lucide.createIcons();

  createBtn.onclick = () => {
    const name = input.value.trim();
    if (!name) return;

    createBtn.disabled = true;
    createBtn.innerHTML =
      '<span class="animate-spin mr-2">◌</span> Creating...';

    apiFetch(`${FLEZ_API_BASE}/api/user/data/add/category`, {
      method: "POST",
      body: JSON.stringify({ category_name: name }),
    })
      .then((r) => r.json())
      .then((res) => {
        createBtn.disabled = false;
        createBtn.innerHTML = "Create Category";
        if (res.status) {
          Swal.fire("Created!", "New category has been added.", "success");
          closeAddModal();
          const searchInput = document.getElementById("category-search");
          if (window.fetchCategories)
            fetchCategories(searchInput ? searchInput.value : "");
        } else {
          Swal.fire("Error", res.message, "error");
        }
      });
  };
};

window.closeAddModal = () => {
  const modal = document.getElementById("add-category-modal");
  if (modal) modal.classList.remove("show");
};

window.deleteCategory = (id, name) => {
  Swal.fire({
    title: "Are you sure?",
    text: `Confirm you want to remove "${name}"? This action cannot be undone if no active records are linked.`,
    icon: "warning",
    showCancelButton: true,
    confirmButtonColor: "#ef4444",
    confirmButtonText: "Yes, delete it!",
  }).then((result) => {
    if (result.isConfirmed) {
      apiFetch(`${FLEZ_API_BASE}/api/user/data/delete/category`, {
        method: "POST",
        body: JSON.stringify({ id: id }),
      })
        .then((r) => r.json())
        .then((res) => {
          if (res.status) {
            Swal.fire("Deleted!", res.message, "success");
            if (window.fetchCategories) window.fetchCategories();
            if (window.fetchDepartments) window.fetchDepartments();
          } else {
            Swal.fire("Blocked", res.message, "error");
          }
        });
    }
  });
};

// Global Dropdown Handlers
window.initDropdownListeners = () => {
  const toggles = document.querySelectorAll(".dropdown-toggle");
  toggles.forEach((toggle) => {
    toggle.onclick = (e) => {
      e.stopPropagation();
      const menu = toggle.nextElementSibling;
      if (!menu) return;
      const isShowing = menu.classList.contains("show");
      const container = toggle.closest(".dropdown-container");
      const tr = toggle.closest("tr");
      const card = toggle.closest(".glass-card");

      // Close all others and reset stacking contexts
      document.querySelectorAll(".dropdown-menu").forEach((m) => {
        if (m !== menu) m.classList.remove("show");
      });
      document.querySelectorAll(".dropdown-container").forEach((c) => {
        c.classList.remove("z-50");
      });
      document.querySelectorAll("tr").forEach((r) => {
        r.classList.remove("relative", "z-40");
      });
      document.querySelectorAll(".glass-card").forEach((gc) => {
        gc.classList.remove("z-40");
      });

      if (!isShowing) {
        if (tr) tr.classList.add("relative", "z-40");
        if (card) card.classList.add("z-40");
        if (container) container.classList.add("z-50");
        menu.classList.add("show");
      } else {
        menu.classList.remove("show");
        if (tr) tr.classList.remove("relative", "z-40");
        if (card) card.classList.remove("z-40");
        if (container) container.classList.remove("z-50");
      }
    };
  });
};

// Global Select Population
window.populateDepartments = async (selectId, selectedValue = "") => {
  const select = document.getElementById(selectId);
  if (!select) return;

  try {
    const res = await apiFetch(`${FLEZ_API_BASE}/api/departments/filter`, {
      method: "POST",
    });
    const data = await res.json();
    if (data.status) {
      let options = '<option value="">Select Department</option>';
      data.data.forEach((dept) => {
        const selected =
          dept.department_name === selectedValue ? "selected" : "";
        options += `<option value="${dept.department_name}" ${selected}>${dept.department_name}</option>`;
      });
      select.innerHTML = options;
    }
  } catch (err) {
    console.error("Failed to populate departments:", err);
  }
};

window.populateCategories = async (selectId, selectedValue = "") => {
  const select = document.getElementById(selectId);
  if (!select) return;

  try {
    const res = await apiFetch(`${FLEZ_API_BASE}/api/categories/filter`, {
      method: "POST",
    });
    const data = await res.json();
    if (data.status) {
      let options = '<option value="">Select Category</option>';
      data.data.forEach((cat) => {
        const selected = cat.category_name === selectedValue ? "selected" : "";
        options += `<option value="${cat.category_name}" ${selected}>${cat.category_name}</option>`;
      });
      select.innerHTML = options;
    }
  } catch (err) {
    console.error("Failed to populate categories:", err);
  }
};

// Global Outside Click
document.addEventListener("click", (e) => {
  if (!e.target.closest(".dropdown-container")) {
    document
      .querySelectorAll(".dropdown-menu")
      .forEach((m) => m.classList.remove("show"));
    document
      .querySelectorAll(".dropdown-container")
      .forEach((c) => c.classList.remove("z-50"));
    document
      .querySelectorAll("tr")
      .forEach((r) => r.classList.remove("relative", "z-40"));
  }
});
// Create Employee Page Logic
window.initCreateEmployee = () => {
  const page = document.getElementById("create-employee-page");
  if (!page) return;

  if (typeof window.populateDepartments === "function") {
    window.populateDepartments("emp-department");
  }

  const createBtn = document.getElementById("create-employee-btn");
  if (createBtn) {
    createBtn.onclick = async () => {
      const firstName = document.getElementById("emp-first-name").value.trim();
      const lastName = document.getElementById("emp-last-name").value.trim();
      const email = document.getElementById("emp-email").value.trim();
      const phone = document.getElementById("emp-phone").value.trim();
      const role = document.getElementById("emp-role").value.trim();
      const department = document.getElementById("emp-department").value;
      const startDate = document.getElementById("emp-start-date").value;

      if (!firstName || !lastName || !email || !role || !department) {
        Swal.fire(
          "Required Fields",
          "Please fill in all necessary information (Names, Email, Role, and Department).",
          "warning",
        );
        return;
      }

      createBtn.disabled = true;
      createBtn.innerHTML =
        '<span class="animate-spin mr-2">◌</span> Creating...';

      try {
        const res = await apiFetch(`${FLEZ_API_BASE}/api/staff/create`, {
          method: "POST",
          body: JSON.stringify({
            first_name: firstName,
            last_name: lastName,
            email: email,
            phone: phone,
            department: department,
            job_title: role,
          }),
        });
        const data = await res.json();
        if (data.status) {
          Swal.fire({
            title: "Success!",
            text: "Employee account created successfully. Login credentials and PIN have been sent to their email.",
            icon: "success",
            confirmButtonColor: "#cfff45",
          }).then(() => {
            if (window.flezSwup) window.flezSwup.navigate("/organization");
            else window.location.href = "/organization";
          });
        } else {
          Swal.fire(
            "Creation Failed",
            data.message || "Could not create employee record.",
            "error",
          );
        }
      } catch (err) {
        console.error("Error creating employee:", err);
        Swal.fire("Error", "An unexpected connection error occurred.", "error");
      } finally {
        createBtn.disabled = false;
        createBtn.innerHTML =
          '<span>Create Employee</span> <i data-lucide="user-plus" class="w-5 h-5"></i>';
        if (window.lucide) lucide.createIcons();
      }
    };
  }
};

// Transaction Detail Component
const TransactionDetailComponent = {
  isOpen: false,

  template: `
        <div id="trx-detail-overlay" class="fixed inset-0 bg-black/40 backdrop-blur-sm z-[100] transition-opacity duration-300 opacity-0 pointer-events-none" onclick="TransactionDetailComponent.close()"></div>
        <aside id="trx-detail-panel" class="fixed inset-y-0 right-0 w-full sm:w-[500px] bg-white dark:bg-bg-dark border-l border-slate-200 dark:border-white/10 z-[110] shadow-2xl transition-transform duration-500 translate-x-full flex flex-col">
            <div id="trx-detail-header" class="p-6 border-b border-slate-200 dark:border-white/5 flex items-center justify-between bg-slate-50/50 dark:bg-bg-card/50 backdrop-blur-md">
                <div class="flex items-center gap-4">
                    <button onclick="TransactionDetailComponent.close()" class="p-2 hover:bg-slate-200 dark:hover:bg-white/5 rounded-lg text-slate-500 dark:text-slate-400">
                        <i data-lucide="arrow-right" class="w-5 h-5"></i>
                    </button>
                    <h2 class="text-xl font-display font-bold text-slate-900 dark:text-white uppercase tracking-wider">Transaction Details</h2>
                </div>
            </div>

            <div class="flex-1 overflow-y-auto p-6 space-y-8" id="trx-detail-content">
                <!-- Content will be injected here -->
            </div>
        </aside>
    `,

  render(trx) {
    let container = document.getElementById("trx-detail-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "trx-detail-container";
      document.body.appendChild(container);
    }

    container.innerHTML = this.template;
    if (window.lucide) lucide.createIcons();

    const content = document.getElementById("trx-detail-content");

    const dateObj = new Date(trx.timestamp);
    const formattedDate = isNaN(dateObj)
      ? "N/A"
      : dateObj.toLocaleString("en-US", {
          year: "numeric",
          month: "long",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        });

    const isCredit = trx.trx_type === "credit";
    const colorClass = isCredit ? "text-emerald-500" : "text-rose-500";
    const bgClass = isCredit ? "bg-emerald-500/10" : "bg-rose-500/10";

    let html = `
            <div class="text-center space-y-4">
                <div class="w-16 h-16 mx-auto rounded-full ${bgClass} ${colorClass} flex items-center justify-center">
                    <i data-lucide="${isCredit ? "arrow-down-left" : "arrow-up-right"}" class="w-8 h-8"></i>
                </div>
                <div>
                    <h3 class="text-3xl font-display font-bold text-slate-900 dark:text-white">${(trx.currency ? CURRENCY_SYMBOLS_MAP[trx.currency] || trx.currency : null) || getUserCurrencySymbol()}${parseFloat(trx.trx_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</h3>
                    <p class="text-sm text-slate-500 uppercase tracking-widest mt-1">${trx.trx_status || "Completed"}</p>
                </div>
            </div>

            <div class="space-y-4">
                <div class="p-5 bg-slate-50 dark:bg-bg-card border border-slate-100 dark:border-white/5 rounded-2xl space-y-4">
                    <div class="flex justify-between items-center">
                        <span class="text-xs text-slate-500 uppercase tracking-wider">Reference</span>
                        <span class="text-sm font-mono font-bold text-slate-900 dark:text-white">${trx.trx_id || "N/A"}</span>
                    </div>
                    <div class="flex justify-between items-center">
                        <span class="text-xs text-slate-500 uppercase tracking-wider">Type</span>
                        <span class="text-sm font-bold ${colorClass} uppercase">${trx.trx_type || "Unknown"}</span>
                    </div>
                    <div class="flex justify-between items-center">
                        <span class="text-xs text-slate-500 uppercase tracking-wider">Category</span>
                        <span class="text-sm font-medium text-slate-900 dark:text-white uppercase">${trx.category || "General"}</span>
                    </div>
                    <div class="flex justify-between items-center">
                        <span class="text-xs text-slate-500 uppercase tracking-wider">Date & Time</span>
                        <span class="text-sm font-medium text-slate-900 dark:text-white">${formattedDate}</span>
                    </div>
                </div>

                <div class="p-5 bg-slate-50 dark:bg-bg-card border border-slate-100 dark:border-white/5 rounded-2xl space-y-4">
                    <div>
                        <span class="text-xs text-slate-500 uppercase tracking-wider block mb-1">Description</span>
                        <p class="text-sm font-medium text-slate-900 dark:text-white">${trx.description || "No description provided"}</p>
                    </div>
                </div>
            </div>
        `;

    content.innerHTML = html;
    if (window.lucide) lucide.createIcons();
    this.open();
  },

  open() {
    this.isOpen = true;
    const overlay = document.getElementById("trx-detail-overlay");
    const panel = document.getElementById("trx-detail-panel");

    requestAnimationFrame(() => {
      overlay.classList.remove("opacity-0", "pointer-events-none");
      panel.classList.remove("translate-x-full");
    });
  },

  close() {
    this.isOpen = false;
    const overlay = document.getElementById("trx-detail-overlay");
    const panel = document.getElementById("trx-detail-panel");

    if (overlay && panel) {
      overlay.classList.add("opacity-0", "pointer-events-none");
      panel.classList.add("translate-x-full");

      setTimeout(() => {
        const container = document.getElementById("trx-detail-container");
        if (container) container.remove();
      }, 300);
    }
  },
};

window.viewTransaction = (encodedTrx) => {
  try {
    const trx = JSON.parse(decodeURIComponent(encodedTrx));
    TransactionDetailComponent.render(trx);
  } catch (err) {
    console.error("Failed to parse transaction data:", err);
    showToast("Error", "Could not open transaction details.", "error");
  }
};

// Export CSV Functions
window.openExportModal = () => {
  const modal = document.getElementById("export-trx-modal");
  const panel = document.getElementById("export-trx-panel");
  if (!modal || !panel) return;

  const today = new Date();
  const lastMonth = new Date();
  lastMonth.setDate(today.getDate() - 30);

  document.getElementById("export-end-date").value = today
    .toISOString()
    .split("T")[0];
  document.getElementById("export-start-date").value = lastMonth
    .toISOString()
    .split("T")[0];

  modal.classList.remove("hidden");
  requestAnimationFrame(() => {
    modal.classList.remove("opacity-0");
    panel.classList.remove("scale-95", "opacity-0");
    panel.classList.add("scale-100", "opacity-100");
  });
};

window.closeExportModal = () => {
  const modal = document.getElementById("export-trx-modal");
  const panel = document.getElementById("export-trx-panel");
  if (!modal || !panel) return;

  modal.classList.add("opacity-0");
  panel.classList.remove("scale-100", "opacity-100");
  panel.classList.add("scale-95", "opacity-0");

  setTimeout(() => {
    modal.classList.add("hidden");
  }, 300);
};

window.exportTransactions = async () => {
  const startDate = document.getElementById("export-start-date").value;
  const endDate = document.getElementById("export-end-date").value;
  const format = document.getElementById("export-format").value;

  const body = {
    page: 1,
    per_page: 10000,
    start_date: startDate ? new Date(startDate).toISOString() : undefined,
    end_date: endDate ? new Date(endDate).toISOString() : undefined,
  };

  try {
    if (typeof Swal !== "undefined") {
      Swal.fire({
        title: "Exporting...",
        text: `Preparing your ${format.toUpperCase()} file`,
        allowOutsideClick: false,
        didOpen: () => {
          Swal.showLoading();
        },
      });
    }

    const res = await apiFetch(`${FLEZ_API_BASE}/api/transactions/filter`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const result = await res.json();

    if (result.status && result.data) {
      if (result.data.length === 0) {
        if (typeof Swal !== "undefined") {
          Swal.fire(
            "No Data",
            "No transactions found for the selected date range.",
            "info",
          );
        }
        return;
      }

      const headers = [
        "Reference",
        "Description",
        "Amount",
        "Type",
        "Status",
        "Date",
      ];
      const rows = result.data.map((trx) => [
        trx.trx_id || "N/A",
        trx.description || "",
        trx.trx_amount || 0,
        trx.trx_type || "N/A",
        trx.trx_status || "N/A",
        new Date(trx.timestamp).toLocaleString(),
      ]);

      const fileName = `transactions_export_${startDate}_to_${endDate}`;

      if (format === "csv") {
        const csvRows = result.data.map((trx) => [
          trx.trx_id || "N/A",
          `"${(trx.description || "").replace(/"/g, '""')}"`,
          trx.trx_amount || 0,
          trx.trx_type || "N/A",
          trx.trx_status || "N/A",
          new Date(trx.timestamp).toLocaleString(),
        ]);
        const csvContent = [
          headers.join(","),
          ...csvRows.map((r) => r.join(",")),
        ].join("\n");
        const blob = new Blob([csvContent], {
          type: "text/csv;charset=utf-8;",
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `${fileName}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else if (format === "excel") {
        if (typeof XLSX === "undefined") {
          throw new Error("Excel export library not loaded.");
        }
        const worksheet = XLSX.utils.aoa_to_sheet([headers, ...rows]);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, "Transactions");
        XLSX.writeFile(workbook, `${fileName}.xlsx`);
      } else if (format === "pdf") {
        if (typeof html2pdf === "undefined") {
          throw new Error("PDF export library not loaded.");
        }

        const container = document.createElement("div");
        container.style.padding = "20px";
        container.style.fontFamily = "sans-serif";

        let tableHtml = `
                    <h2 style="text-align: center; margin-bottom: 20px;">Transactions Export</h2>
                    <p style="text-align: center; margin-bottom: 20px; font-size: 12px; color: #666;">
                        ${startDate} to ${endDate}
                    </p>
                    <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                        <thead>
                            <tr style="background-color: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                                ${headers.map((h) => `<th style="padding: 10px; text-align: left;">${h}</th>`).join("")}
                            </tr>
                        </thead>
                        <tbody>
                            ${rows
                              .map(
                                (row, i) => `
                                <tr style="border-bottom: 1px solid #e2e8f0; ${i % 2 === 0 ? "background-color: #ffffff;" : "background-color: #f8fafc;"}">
                                    ${row.map((cell, j) => `<td style="padding: 10px;">${j === 2 ? getUserCurrencySymbol() + cell : cell}</td>`).join("")}
                                </tr>
                            `,
                              )
                              .join("")}
                        </tbody>
                    </table>
                `;
        container.innerHTML = tableHtml;

        const opt = {
          margin: 10,
          filename: `${fileName}.pdf`,
          image: { type: "jpeg", quality: 0.98 },
          html2canvas: { scale: 2 },
          jsPDF: { unit: "mm", format: "a4", orientation: "landscape" },
        };

        await html2pdf().set(opt).from(container).save();
      }

      if (typeof Swal !== "undefined") Swal.close();
      closeExportModal();
      if (typeof showToast !== "undefined")
        showToast("Success", "Transactions exported successfully", "success");
    } else {
      if (typeof Swal !== "undefined")
        Swal.fire(
          "Error",
          result.message || "Failed to fetch transactions for export.",
          "error",
        );
    }
  } catch (err) {
    console.error("Export error:", err);
    if (typeof Swal !== "undefined")
      Swal.fire(
        "Error",
        err.message || "An unexpected error occurred during export.",
        "error",
      );
  }
};

// Global initialization on first load
document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

window.initEditEmployee = () => {
  const page = document.getElementById("edit-employee-page");
  if (!page) return;

  if (typeof window.populateDepartments === "function") {
    window.populateDepartments("emp-department");
  }

  const pathParts = window.location.pathname.split("/");
  const staffId = pathParts[pathParts.length - 1];
  if (!staffId) return;

  // Fetch existing staff details
  apiFetch(`${FLEZ_API_BASE}/api/staff/detail/${staffId}`)
    .then((r) => r.json())
    .then((res) => {
      if (res.status && res.data) {
        const staff = res.data;
        document.getElementById("emp-first-name").value =
          staff.first_name || "";
        document.getElementById("emp-last-name").value = staff.last_name || "";
        document.getElementById("emp-email").value = staff.user_email || "";
        document.getElementById("emp-phone").value = staff.phone_number || "";
        document.getElementById("emp-role").value = staff.job_title || "";

        if (staff.timestamp) {
          const dateObj = new Date(staff.timestamp);
          const yyyy = dateObj.getFullYear();
          const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
          const dd = String(dateObj.getDate()).padStart(2, "0");
          document.getElementById("emp-start-date").value =
            `${yyyy}-${mm}-${dd}`;
        }

        // Avatar preview
        const empAvatarImg = document.getElementById("emp-avatar-img");
        const empAvatarInitials = document.getElementById(
          "emp-avatar-initials",
        );
        const fullName =
          `${staff.first_name || ""} ${staff.last_name || ""}`.trim() ||
          "Staff";
        const initials = fullName
          .split(" ")
          .map((n) => n[0])
          .join("")
          .toUpperCase()
          .substring(0, 2);
        if (empAvatarInitials) empAvatarInitials.textContent = initials;

        if (empAvatarImg) {
          if (staff.image && !staff.image.includes("placeholder_avi")) {
            empAvatarImg.src = staff.image;
            empAvatarImg.classList.remove("hidden");
            if (empAvatarInitials) empAvatarInitials.classList.add("hidden");
            empAvatarImg.onerror = () => {
              empAvatarImg.classList.add("hidden");
              if (empAvatarInitials)
                empAvatarInitials.classList.remove("hidden");
            };
          } else {
            empAvatarImg.classList.add("hidden");
            if (empAvatarInitials) empAvatarInitials.classList.remove("hidden");
          }
        }

        // wait slightly for departments to populate then set
        setTimeout(() => {
          document.getElementById("emp-department").value =
            staff.department || "";
        }, 500);
      }
    });

  const empAvatarBtn = document.getElementById("emp-avatar-btn");
  const empAvatarInput = document.getElementById("emp-avatar-input");
  let pendingAvatarFile = null;

  if (empAvatarBtn && empAvatarInput) {
    empAvatarBtn.onclick = () => empAvatarInput.click();
    empAvatarInput.onchange = (e) => {
      const file = e.target.files[0];
      if (!file) return;
      if (!file.type.startsWith("image/")) {
        Swal.fire(
          "Invalid File",
          "Please select a valid image file.",
          "warning",
        );
        return;
      }
      pendingAvatarFile = file;
      const reader = new FileReader();
      reader.onload = (re) => {
        const empAvatarImg = document.getElementById("emp-avatar-img");
        const empAvatarInitials = document.getElementById(
          "emp-avatar-initials",
        );
        if (empAvatarImg) {
          empAvatarImg.src = re.target.result;
          empAvatarImg.classList.remove("hidden");
          if (empAvatarInitials) empAvatarInitials.classList.add("hidden");
        }
      };
      reader.readAsDataURL(file);
    };
  }

  const cancelBtn = document.getElementById("cancel-edit-btn");
  if (cancelBtn) {
    cancelBtn.href = `/staff-details/${staffId}`;
  }

  const saveBtn = document.getElementById("edit-employee-btn");
  if (saveBtn) {
    saveBtn.onclick = async () => {
      const firstName = document.getElementById("emp-first-name").value.trim();
      const lastName = document.getElementById("emp-last-name").value.trim();
      const role = document.getElementById("emp-role").value.trim();
      const department = document.getElementById("emp-department").value;

      if (!firstName || !lastName || !role || !department) {
        Swal.fire(
          "Required Fields",
          "Please fill in Name, Role, and Department.",
          "warning",
        );
        return;
      }

      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="animate-spin mr-2">◌</span> Saving...';

      try {
        const formData = new FormData();
        formData.append("id", staffId);
        formData.append("first_name", firstName);
        formData.append("last_name", lastName);
        formData.append(
          "email",
          document.getElementById("emp-email").value.trim(),
        );
        formData.append(
          "phone",
          document.getElementById("emp-phone").value.trim(),
        );
        formData.append("department", department);
        formData.append("job_title", role);
        formData.append("account_name", `${firstName} ${lastName}`);
        if (pendingAvatarFile) {
          formData.append("user_avatar", pendingAvatarFile);
        }

        const res = await apiFetch(
          `${FLEZ_API_BASE}/api/staff/update-details`,
          {
            method: "POST",
            body: formData,
          },
        );
        const data = await res.json();
        if (data.status) {
          Swal.fire({
            title: "Success!",
            text: "Employee account updated successfully.",
            icon: "success",
            confirmButtonColor: "#cfff45",
          }).then(() => {
            if (window.flezSwup)
              window.flezSwup.navigate(`/staff-details/${staffId}`);
            else window.location.href = `/staff-details/${staffId}`;
          });
        } else {
          Swal.fire(
            "Update Failed",
            data.message || "Could not update employee record.",
            "error",
          );
        }
      } catch (err) {
        console.error("Error updating employee:", err);
        Swal.fire("Error", "An unexpected connection error occurred.", "error");
      } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML =
          '<span>Save Changes</span><i data-lucide="save" class="w-5 h-5"></i>';
        if (window.lucide) window.lucide.createIcons();
      }
    };
  }
};

window.printProductQR = function (id) {
  const userData = JSON.parse(localStorage.getItem("user_data") || "{}");
  const items = userData.items || [];
  const product = items.find((p) => p.item_id === id);
  if (!product) return;

  _promptPrintFormat([product]);
};

window.printAllProductQRCodes = function () {
  const userData = JSON.parse(localStorage.getItem("user_data") || "{}");
  const items = userData.items || [];
  if (items.length === 0) {
    if (typeof window.showToast === "function")
      window.showToast("Info", "No products to print", "info");
    return;
  }
  _promptPrintFormat(items);
};

window.batchPrintQRCodes = function () {
  const selectedInputs = document.querySelectorAll(".product-select:checked");
  if (selectedInputs.length === 0) {
    if (typeof window.showToast === "function")
      window.showToast("Info", "Please select at least one product", "info");
    return;
  }

  const userData = JSON.parse(localStorage.getItem("user_data") || "{}");
  const items = userData.items || [];
  const selectedIds = Array.from(selectedInputs).map(
    (input) => input.dataset.id,
  );
  const selectedItems = items.filter((p) => selectedIds.includes(p.item_id));

  _promptPrintFormat(selectedItems);
};

window._promptPrintFormat = function (items) {
  Swal.fire({
    title: "Select Format",
    text: "Would you like to print QR codes or Barcodes?",
    icon: "question",
    showCancelButton: true,
    showDenyButton: true,
    confirmButtonText:
      '<i data-lucide="qr-code" class="w-4 h-4 mr-2 inline-block"></i> QR Code',
    denyButtonText:
      '<i data-lucide="barcode" class="w-4 h-4 mr-2 inline-block"></i> Barcode',
    cancelButtonText: "Cancel",
    confirmButtonColor: "#cfff45",
    denyButtonColor: "#000000",
    didOpen: () => {
      if (typeof lucide !== "undefined") lucide.createIcons();
    },
  }).then((result) => {
    if (result.isConfirmed) {
      _printItems(items, "qr");
    } else if (result.isDenied) {
      _printItems(items, "barcode");
    }
  });
};

window._printItems = function (itemsToPrint, format) {
  const printWindow = window.open("", "_blank");
  if (!printWindow) {
    if (typeof window.showToast === "function")
      window.showToast("Error", "Please allow popups to print codes", "error");
    else alert("Please allow popups to print codes");
    return;
  }

  let gridHtml = itemsToPrint
    .map((product) => {
      const name = product.item_name || product.item_id;

      const codeData = product.sku || product.item_id;

      let imgHtml = "";
      if (format === "qr") {
        const scanUrl = `${window.location.origin}/product/info/${product.item_id}`;
        const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(scanUrl)}`;
        imgHtml = `<div class="qr-wrapper qr"><div class="corners"></div><img src="${qrUrl}" alt="QR Code" /></div>`;
      } else {
        const barcodeUrl = `https://barcode.tec-it.com/barcode.ashx?data=${encodeURIComponent(codeData)}&code=Code128&translate-esc=on`;
        imgHtml = `<div class="barcode-wrapper"><img src="${barcodeUrl}" alt="Barcode" /></div>`;
      }

      return `
            <div class="card ${format === "barcode" ? "is-barcode" : "is-qr"}">
                <h1>${name}</h1>
                ${imgHtml}
                ${format === "qr" ? '<div class="btn">SCAN ME</div>' : ""}
            </div>
        `;
    })
    .join("");

  printWindow.document.write(`
        <html>
            <head>
                <title>Print ${format === "qr" ? "QR Codes" : "Barcodes"}</title>
                <style>
                    body { font-family: 'Inter', system-ui, sans-serif; margin: 0; padding: 40px; text-align: center; background: #fff; }
                    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 40px; justify-content: center; }
                    .card { background-color: #f8f9fa; padding: 30px; border-radius: 24px; display: flex; flex-direction: column; align-items: center; box-sizing: border-box; break-inside: avoid; }
                    h1 { font-size: 18px; font-weight: 800; margin: 0 0 24px 0; color: #000; line-height: 1.3; }
                    .card.is-barcode h1 { margin-bottom: 8px; }
                    
                    .qr-wrapper { position: relative; padding: 16px; margin-bottom: 24px; display: inline-flex; }
                    .qr-wrapper::before, .qr-wrapper::after, .qr-wrapper .corners::before, .qr-wrapper .corners::after { content: ''; position: absolute; border: 6px solid #000; width: 32px; height: 32px; }
                    .qr-wrapper::before { top: 0; left: 0; border-right: none; border-bottom: none; }
                    .qr-wrapper::after { top: 0; right: 0; border-left: none; border-bottom: none; }
                    .qr-wrapper .corners::before { bottom: 0; left: 0; border-right: none; border-top: none; }
                    .qr-wrapper .corners::after { bottom: 0; right: 0; border-left: none; border-top: none; }
                    
                    .qr-wrapper.qr img { width: 220px; height: 220px; margin: 0; display: block; }
                    
                    .barcode-wrapper { padding: 0; margin-bottom: 16px; display: inline-flex; }
                    .barcode-wrapper img { width: 220px; height: 100px; margin: 0; display: block; object-fit: contain; }
                    
                    .btn { border: 4px solid #000; border-radius: 50px; padding: 10px 24px; font-size: 16px; font-weight: 900; color: #000; background: transparent; text-transform: uppercase; letter-spacing: 0.5px; }
                    
                    .single-card-container { display: flex; justify-content: center; align-items: center; min-height: 80vh; }
                    .single-card-container .card { width: 320px; padding: 40px; }
                    .single-card-container h1 { font-size: 20px; }
                    .single-card-container .btn { padding: 12px 30px; font-size: 18px; }

                    @media print { 
                        .card { border: none; } 
                        body { padding: 0; }
                    }
                </style>
            </head>
            <body>
                <div class="${itemsToPrint.length === 1 ? "single-card-container" : "grid"}">
                    ${gridHtml}
                </div>
                <script>
                    window.onload = () => {
                        setTimeout(() => {
                            window.print();
                            window.close();
                        }, 800);
                    };
                </script>
            </body>
        </html>
    `);
  printWindow.document.close();
};
