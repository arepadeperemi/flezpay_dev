/**
 * sidebar.js - Dynamic Sidebar Component for FlezPay Enterprise
 * Centralizes the navigation menu for easy maintenance.
 */

const DASHBOARD_NAV_ITEMS = [
  // Core
  {
    title: "Overview",
    url: "/dashboard",
    icon: "layout-dashboard",
    category: "Core",
    desc: "Main dashboard metrics and business overview",
    keywords: ["home", "main", "metrics", "stats", "kpi", "summary", "revenue"]
  },
  {
    title: "Analytics",
    url: "/analytics",
    icon: "bar-chart-3",
    category: "Core",
    desc: "Sales trends, performance charts & data insights",
    keywords: ["charts", "reports", "graphs", "trends", "insights", "sales data"]
  },

  // Finance & Invoices
  {
    title: "Transactions",
    url: "/transactions",
    icon: "arrow-left-right",
    category: "Finance",
    desc: "Payment history, transfers & transaction logs",
    keywords: ["payments", "history", "transfers", "ledger", "money in", "money out", "deposits"]
  },
  {
    title: "Wallet & Balances",
    url: "/wallet",
    icon: "wallet",
    category: "Finance",
    desc: "Multi-currency balances, virtual cards & payouts",
    keywords: ["funds", "balance", "bank", "deposit", "cards", "currency", "crypto", "usdc"]
  },
  {
    title: "Fund Wallet",
    url: "/wallet?action=fund",
    icon: "plus-circle",
    category: "Finance",
    desc: "Instant funding via dedicated virtual account or crypto",
    keywords: ["fund", "deposit", "top up", "add money", "account details", "virtual account", "bank transfer", "fund wallet"]
  },
  {
    title: "Withdraw Funds",
    url: "/wallet?action=withdraw",
    icon: "arrow-up-right",
    category: "Finance",
    desc: "Transfer balance to your local bank or crypto wallet",
    keywords: ["withdraw", "payout", "transfer", "cash out", "bank transfer", "withdrawal", "send money", "wallet withdraw"]
  },
  {
    title: "Invoices",
    url: "/invoices",
    icon: "file-text",
    category: "Finance",
    desc: "Manage, track and send customer invoices",
    keywords: ["billing", "bills", "receipts", "client invoices", "estimates", "due"]
  },
  {
    title: "Create Invoice",
    url: "/create-invoice",
    icon: "file-plus",
    category: "Finance",
    desc: "Draft and dispatch a new payment invoice",
    keywords: ["new invoice", "send invoice", "bill client", "generate invoice", "create bill"]
  },
  {
    title: "Tax & Credit AI",
    url: "/tax-credit",
    icon: "shield-check",
    category: "Finance",
    desc: "Stay tax compliant, analyze & boost credit score with AI",
    keywords: ["taxes", "vat", "credit score", "compliance", "deductions", "filing", "tin", "credit health"]
  },

  // Store & Inventory
  {
    title: "Products & Inventory",
    url: "/products",
    icon: "shopping-bag",
    category: "Store",
    desc: "Catalog items, variants, stock & pricing",
    keywords: ["items", "inventory", "stock", "catalog", "goods", "pricing", "variants"]
  },
  {
    title: "Add Product",
    url: "/add-product",
    icon: "package-plus",
    category: "Store",
    desc: "Create and publish a new item in your catalog",
    keywords: ["new product", "create item", "upload product", "add item", "new item"]
  },
  {
    title: "Import Products",
    url: "/import-products",
    icon: "file-up",
    category: "Store",
    desc: "Bulk import products via CSV or spreadsheets",
    keywords: ["csv", "bulk upload", "excel", "migrate items", "import data"]
  },
  {
    title: "Online Store",
    url: "/store",
    icon: "store",
    category: "Store",
    desc: "E-commerce storefront management & orders",
    keywords: ["shop", "webshop", "storefront", "ecommerce", "online shop", "store page"]
  },
  {
    title: "Online Orders",
    url: "/online-orders",
    icon: "package",
    category: "Store",
    desc: "Customer store orders, fulfillment & waybills",
    keywords: ["orders", "deliveries", "fulfillment", "shipments", "purchases", "pending orders", "tracking"]
  },
  {
    title: "Store Settings",
    url: "/store-settings",
    icon: "sliders",
    category: "Store",
    desc: "Store currency, delivery zones, fees & branding",
    keywords: ["shipping", "delivery", "store config", "payment options", "cart", "zones"]
  },
  {
    title: "Custom Domains",
    url: "/domain-management",
    icon: "globe",
    category: "Store",
    desc: "Connect and manage custom domains for your store",
    keywords: ["dns", "domain", "url", "subdomain", "cname", "openprovider", "domain name"]
  },
  {
    title: "Store Layouts",
    url: "/store-layouts",
    icon: "layout",
    category: "Store",
    desc: "Visual page builder & storefront theme templates",
    keywords: ["theme", "template", "design", "builder", "homepage", "store appearance"]
  },

  // Sales & POS
  {
    title: "POS Terminal",
    url: "/pos",
    icon: "monitor",
    category: "Sales",
    desc: "In-person checkout, register & receipt printer",
    keywords: ["point of sale", "checkout", "cashier", "terminal", "in-person", "register", "cash register"]
  },

  // Team & HR
  {
    title: "Organization",
    url: "/organization",
    icon: "building-2",
    category: "Team",
    desc: "Staff directory, departments & permissions",
    keywords: ["team", "employees", "staff", "roles", "members", "departments", "organization"]
  },
  {
    title: "Add Employee",
    url: "/create-employee",
    icon: "user-plus",
    category: "Team",
    desc: "Invite team members and assign role privileges",
    keywords: ["new staff", "invite user", "add worker", "hire", "new employee"]
  },
  {
    title: "Payroll",
    url: "/payroll",
    icon: "users",
    category: "Team",
    desc: "Salary disbursements, payslips & employee wages",
    keywords: ["salaries", "compensation", "wages", "payslips", "direct deposit", "pay staff"]
  },
  {
    title: "Run / Add Payroll",
    url: "/add-payroll",
    icon: "calendar-check",
    category: "Team",
    desc: "Schedule and process staff salary payouts",
    keywords: ["disburse", "pay salary", "process payroll", "pay team", "add payroll"]
  },

  // Growth & Marketing
  {
    title: "Growth Overview",
    url: "/growth",
    icon: "trending-up",
    category: "Growth",
    desc: "Marketing hub, campaign performance & ROI",
    keywords: ["marketing", "ads", "advertising", "growth", "facebook ads", "promotions", "campaigns"]
  },
  {
    title: "Promotions & Ads",
    url: "/growth/promotions",
    icon: "megaphone",
    category: "Growth",
    desc: "Manage active ad campaigns and discounts",
    keywords: ["campaigns", "facebook ads", "meta", "coupons", "promo", "advertisements"]
  },
  {
    title: "Create Campaign",
    url: "/growth/promotions/create",
    icon: "sparkles",
    category: "Growth",
    desc: "Launch targeted Facebook & Instagram ads with AI",
    keywords: ["launch ad", "new promotion", "boost sales", "ad setup", "create campaign"]
  },
  {
    title: "Growth Reports",
    url: "/growth/reports",
    icon: "pie-chart",
    category: "Growth",
    desc: "Detailed ad spend, conversion & ROAS reports",
    keywords: ["ad metrics", "roas", "cpc", "conversion", "spend", "marketing analytics", "roi"]
  },
  {
    title: "Audience & Segments",
    url: "/growth/audience",
    icon: "target",
    category: "Growth",
    desc: "Customer segments, targeting & retargeting lists",
    keywords: ["customers", "demographics", "targeting", "leads", "subscribers", "audience"]
  },
  {
    title: "Marketing AI Assistant",
    url: "/growth/ai-assistant",
    icon: "bot",
    category: "Growth",
    desc: "Generate high-converting ad copy and strategies",
    keywords: ["ai copy", "caption generator", "growth strategist", "assistant", "ad copy"]
  },
  {
    title: "Ad Creative Generator",
    url: "/growth/ai-creator",
    icon: "palette",
    category: "Growth",
    desc: "AI-powered product visual and banner generation",
    keywords: ["creative", "banners", "images", "ad visuals", "ai image", "marketing banner"]
  },
  {
    title: "Growth Settings",
    url: "/growth/settings",
    icon: "settings-2",
    category: "Growth",
    desc: "Meta Pixel, ad accounts & credit configuration",
    keywords: ["meta pixel", "facebook page", "ad credit", "growth config", "pixel setup"]
  },

  // AI & Support & Account
  {
    title: "AI Business Manager",
    url: "/ai-manager",
    icon: "sparkles",
    category: "AI",
    desc: "Autonomous AI store manager and operations advisor",
    keywords: ["agent", "automation", "ai bot", "business intelligence", "copilot", "manager"]
  },
  {
    title: "Live Support Chat",
    url: "/livechat",
    icon: "message-square",
    category: "Support",
    desc: "Real-time customer messaging & visitor inbox",
    keywords: ["chat", "customer service", "inbox", "messages", "support", "conversations"]
  },
  {
    title: "Settings",
    url: "/settings",
    icon: "settings",
    category: "Account",
    desc: "Business profile, security, notifications & preferences",
    keywords: ["preferences", "configuration", "dark mode", "password", "security", "tax details"]
  },
  {
    title: "Profile & Security",
    url: "/profile",
    icon: "user",
    category: "Account",
    desc: "User account, personal info & login credentials",
    keywords: ["my account", "avatar", "email", "credentials", "account profile"]
  },
  {
    title: "Help Center",
    url: "/help-center",
    icon: "help-circle",
    category: "Support",
    desc: "Documentation, user guides and knowledge base",
    keywords: ["docs", "tutorials", "guide", "faq", "contact support", "help"]
  },
  {
    title: "Log Out",
    url: "/logout",
    icon: "log-out",
    category: "Account",
    desc: "Sign out of your FlezPay business account",
    keywords: ["logout", "sign out", "exit", "leave", "switch account"]
  }
];

const SidebarComponent = {
    NAV_ITEMS: DASHBOARD_NAV_ITEMS,

    template: `
      <aside
        id="sidebar"
        class="fixed inset-y-0 left-0 z-50 w-64 lg:w-20 bg-white dark:bg-bg-sidebar border-r border-slate-200 dark:border-white/5 flex flex-col items-center transition-all duration-300 -translate-x-full lg:translate-x-0 lg:h-screen lg:sticky lg:top-0 shadow-2xl lg:shadow-none"
      >
        <div id="sidebar-logo-container" class="p-4 w-full flex lg:justify-center items-center mb-1 lg:px-0 px-6">
          <a
            href="/"
            class="flex shrink-0 items-center justify-center transition-opacity hover:opacity-80"
          >
            <img src="/static/assets/image/logo.webp" alt="FlezPay" class="w-10 h-10 object-contain" />
          </a>
          <span class="lg:hidden ml-4 font-display font-bold text-lg text-slate-800 dark:text-white">FlezPay</span>
        </div>

        <div class="w-full flex justify-center mb-4 px-3 lg:px-0">
          <button
            type="button"
            id="sidebar-search-trigger"
            data-tooltip="Search (Ctrl+K)"
            class="sidebar-search-btn shrink-0 flex items-center justify-start lg:justify-center w-full lg:w-11 h-11 px-3 lg:px-0 text-slate-500 dark:text-slate-400 bg-slate-100/80 hover:bg-slate-200/80 dark:bg-white/5 dark:hover:bg-white/10 hover:text-slate-900 dark:hover:text-white rounded-xl transition-all group relative border border-transparent hover:border-slate-200 dark:hover:border-white/10 shadow-sm overflow-hidden"
            aria-label="Open search"
          >
            <i data-lucide="search" class="w-[18px] h-[18px] shrink-0 text-slate-400 dark:text-slate-400 group-hover:text-emerald-500 transition-colors"></i>
            <span class="sidebar-search-text lg:hidden ml-2.5 text-[13px] font-medium text-slate-500 dark:text-slate-400 group-hover:text-slate-800 dark:group-hover:text-white flex-1 text-left whitespace-nowrap truncate overflow-hidden">Search</span>
            <kbd class="sidebar-search-kbd lg:hidden shrink-0 px-1.5 py-0.5 rounded bg-slate-200/80 dark:bg-white/10 font-mono text-[10px] text-slate-400 dark:text-slate-500 tracking-wider ml-auto">⌘K</kbd>
          </button>
        </div>

        <nav class="flex-1 w-full flex flex-col items-center py-2 space-y-2 overflow-y-auto overflow-x-hidden">
          <a href="/dashboard" data-tooltip="Overview" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <i data-lucide="layout-dashboard" class="w-[18px] h-[18px] shrink-0"></i>
            <span class="lg:hidden ml-3 text-[13px] font-normal">Overview</span>
          </a>
          
          <a href="/analytics" data-tooltip="Analytics" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <i data-lucide="bar-chart-3" class="w-[18px] h-[18px] shrink-0"></i>
            <span class="lg:hidden ml-3 text-[13px] font-normal">Analytics</span>
          </a>

          <a href="/transactions" data-tooltip="Transactions" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <i data-lucide="arrow-left-right" class="w-[18px] h-[18px] shrink-0"></i>
            <span class="lg:hidden ml-3 text-[13px] font-normal">Transactions</span>
          </a>

          <a href="/invoices" data-tooltip="Invoices" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <i data-lucide="file-text" class="w-[18px] h-[18px] shrink-0"></i>
            <span class="lg:hidden ml-3 text-[13px] font-normal">Invoices</span>
          </a>

          <a href="/products" data-tooltip="Products" id="sidebar-products-link" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <div class="relative shrink-0 flex items-center justify-center">
              <i data-lucide="shopping-bag" class="w-[18px] h-[18px]"></i>
              <div id="products-low-stock-badge" class="absolute -top-0.5 -right-0.5 w-2 h-2 bg-rose-500 rounded-full animate-pulse hidden"></div>
            </div>
            <span class="lg:hidden ml-3 text-[13px] font-normal flex items-center gap-2">Products<span id="products-low-stock-badge-text" class="hidden bg-rose-500 text-white text-[9px] font-bold leading-none px-1.5 py-0.5 rounded-full min-w-[18px] text-center"></span></span>
          </a>

          <a href="/store" data-tooltip="Online Store" id="sidebar-store-link" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <div class="relative shrink-0 flex items-center justify-center">
              <i data-lucide="store" class="w-[18px] h-[18px]"></i>
              <div id="store-pending-badge" class="absolute -top-0.5 -right-0.5 w-2 h-2 bg-rose-500 rounded-full animate-pulse hidden"></div>
            </div>
            <span class="lg:hidden ml-3 text-[13px] font-normal flex items-center gap-2">Online Store<span id="store-pending-badge-text" class="hidden bg-rose-500 text-white text-[9px] font-bold leading-none px-1.5 py-0.5 rounded-full min-w-[18px] text-center"></span></span>
          </a>

          <a href="/pos" data-tooltip="POS" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <i data-lucide="monitor" class="w-[18px] h-[18px] shrink-0"></i>
            <span class="lg:hidden ml-3 text-[13px] font-normal">POS</span>
          </a>

          <div class="w-[calc(100%-4rem)] lg:w-8 h-[1px] shrink-0 bg-slate-300 dark:bg-white/20 my-3 rounded-full"></div>

          <a href="/organization" data-tooltip="Organization" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <i data-lucide="building-2" class="w-[18px] h-[18px] shrink-0"></i>
            <span class="lg:hidden ml-3 text-[13px] font-normal">Organization</span>
          </a>

          <a href="/wallet" data-tooltip="Wallet" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <i data-lucide="wallet" class="w-[18px] h-[18px] shrink-0"></i>
            <span class="lg:hidden ml-3 text-[13px] font-normal">Wallet</span>
          </a>
          
          <a href="/payroll" data-tooltip="Payroll" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <i data-lucide="users" class="w-[18px] h-[18px] shrink-0"></i>
            <span class="lg:hidden ml-3 text-[13px] font-normal">Payroll</span>
          </a>

          <a href="/tax-credit" data-tooltip="Tax & Credit" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <i data-lucide="shield-check" class="w-[18px] h-[18px] shrink-0"></i>
            <span class="lg:hidden ml-3 text-[13px] font-normal">Tax & Credit</span>
          </a>

          <div class="w-[calc(100%-4rem)] lg:w-8 h-[1px] shrink-0 bg-slate-300 dark:bg-white/20 my-3 rounded-full"></div>

          <a href="/growth" data-tooltip="Growth" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <i data-lucide="trending-up" class="w-[18px] h-[18px] shrink-0"></i>
            <span class="lg:hidden ml-3 text-[13px] font-normal flex items-center gap-2">Growth</span>
          </a>
          
          <a href="/livechat" data-tooltip="Livechat" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <div class="relative shrink-0 flex items-center justify-center">
              <i data-lucide="message-square" class="w-[18px] h-[18px]"></i>
              <div id="livechat-sidebar-badge" class="absolute -top-0.5 -right-0.5 w-2 h-2 bg-rose-500 rounded-full animate-pulse hidden"></div>
            </div>
            <span class="lg:hidden ml-3 text-[13px] font-normal flex items-center gap-2">Livechat<span id="livechat-sidebar-badge-text" class="hidden bg-rose-500 text-white text-[9px] font-bold leading-none px-1.5 py-0.5 rounded-full min-w-[18px] text-center"></span></span>
          </a>

          <a href="/ai-manager" data-tooltip="AI Manager (BETA)" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <i data-lucide="sparkles" class="w-[18px] h-[18px] shrink-0"></i>
            <span class="lg:hidden ml-3 text-[13px] font-normal flex items-center gap-2">AI Manager <span class="bg-red-500 border border-white/50 rounded-sm text-[8px] px-1 py-0.5 font-bold uppercase tracking-wider leading-none" style="color: white !important;">BETA</span></span>
          </a>
        </nav>

        <div class="w-full flex flex-col items-center pb-6 pt-2 space-y-2">
          <a href="/settings" data-tooltip="Settings" class="sidebar-link shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-slate-500 dark:text-slate-400 transition-all hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white rounded-xl relative">
            <i data-lucide="settings" class="w-[18px] h-[18px] shrink-0"></i>
            <span class="lg:hidden ml-3 text-[13px] font-normal">Settings</span>
          </a>
          <button onclick="logout()" data-tooltip="Logout" class="shrink-0 flex items-center justify-start lg:justify-center w-[calc(100%-2rem)] lg:w-11 h-11 px-4 lg:px-0 text-rose-500 transition-all hover:bg-rose-50 dark:hover:bg-rose-500/10 hover:text-rose-600 dark:hover:text-rose-400 rounded-xl relative">
            <i data-lucide="log-out" class="w-[18px] h-[18px] shrink-0"></i>
            <span class="lg:hidden ml-3 text-[13px] font-normal">Logout</span>
          </button>
        </div>
      </aside>
      
      <!-- Centered Command Palette Search Modal Overlay -->
      <dialog
        id="global-search-modal"
        closedby="any"
        aria-label="Global Search"
        class="fixed inset-0 m-0 w-screen h-screen max-w-none max-h-none bg-transparent p-0 z-[99999] border-none outline-none overflow-hidden"
      >
        <div id="global-search-backdrop" class="modal-backdrop fixed inset-0 bg-slate-950/60 backdrop-blur-md"></div>
        
        <div class="relative z-10 w-full h-full flex items-start justify-center p-4 sm:p-6 md:p-8 pt-[8vh] sm:pt-[12vh] overflow-y-auto pointer-events-none">
          <div
            id="global-search-dialog-card"
            class="modal-card pointer-events-auto w-full max-w-2xl bg-white/95 dark:bg-[#0b1324]/95 border border-slate-200/80 dark:border-white/10 rounded-2xl shadow-[0_25px_60px_-15px_rgba(0,0,0,0.5),0_0_40px_0_rgba(16,185,129,0.06)] backdrop-blur-xl flex flex-col overflow-hidden"
          >
            <!-- Unified Spotlight Search Bar Header -->
            <div id="global-search-header" class="relative flex items-center px-4 sm:px-5 border-b border-slate-200/80 dark:border-white/10 bg-transparent gap-3">
              <div class="shrink-0 flex items-center justify-center text-emerald-500">
                <i data-lucide="search" class="w-5 h-5"></i>
              </div>
              <input
                id="global-search-input"
                type="text"
                autocomplete="off"
                spellcheck="false"
                placeholder="Search pages, actions, settings..."
              />
              <div class="shrink-0 flex items-center gap-2 ml-1">
                <button
                  id="sidebar-search-clear"
                  type="button"
                  class="hidden w-7 h-7 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-white/10 transition-colors"
                  aria-label="Clear search input"
                  title="Clear input"
                >
                  <i data-lucide="x" class="w-4 h-4"></i>
                </button>
                <button
                  type="button"
                  id="global-search-close-btn"
                  class="hidden sm:inline-flex items-center px-2 py-0.5 rounded-lg bg-slate-100 hover:bg-slate-200/80 dark:bg-white/10 dark:hover:bg-white/15 text-slate-500 dark:text-slate-400 font-mono text-[10.5px] font-medium border border-slate-200/80 dark:border-white/5 cursor-pointer select-none transition-colors"
                  title="Close (Esc)"
                  aria-label="Close search"
                >
                  esc
                </button>
              </div>
            </div>

            <!-- Category Filter Chips -->
            <div id="global-search-filters" class="px-4 py-2 bg-slate-50/60 dark:bg-white/[0.01] border-b border-slate-100/80 dark:border-white/5 flex items-center gap-1.5 overflow-x-auto no-scrollbar text-[11px]">
              <span class="text-slate-400 dark:text-slate-500 font-medium mr-1 text-[10px] uppercase tracking-wider shrink-0">Filter:</span>
              <button type="button" data-category="all" class="search-filter-chip active px-2.5 py-1 rounded-lg font-medium transition-all">All</button>
              <button type="button" data-category="Core" class="search-filter-chip px-2.5 py-1 rounded-lg font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-white/5 transition-all">Core</button>
              <button type="button" data-category="Finance" class="search-filter-chip px-2.5 py-1 rounded-lg font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-white/5 transition-all">Finance</button>
              <button type="button" data-category="Store" class="search-filter-chip px-2.5 py-1 rounded-lg font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-white/5 transition-all">Store</button>
              <button type="button" data-category="Sales" class="search-filter-chip px-2.5 py-1 rounded-lg font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-white/5 transition-all">Sales</button>
              <button type="button" data-category="Team" class="search-filter-chip px-2.5 py-1 rounded-lg font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-white/5 transition-all">Team</button>
              <button type="button" data-category="Growth" class="search-filter-chip px-2.5 py-1 rounded-lg font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-white/5 transition-all">Growth</button>
              <button type="button" data-category="AI" class="search-filter-chip px-2.5 py-1 rounded-lg font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-white/5 transition-all">AI</button>
              <button type="button" data-category="Account" class="search-filter-chip px-2.5 py-1 rounded-lg font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-white/5 transition-all">Account</button>
            </div>

            <!-- Result Count Header -->
            <div class="px-4 py-2 bg-slate-50/70 dark:bg-white/[0.02] border-b border-slate-100/60 dark:border-white/5 flex items-center justify-between text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
              <span id="global-search-count">Quick Navigation</span>
              <span id="global-search-hint" class="text-[10px] lowercase font-normal opacity-75 hidden sm:inline">Use ↑↓ to navigate, ↵ to open</span>
            </div>

            <!-- Results List Container -->
            <div
              id="global-search-results"
              class="overflow-y-auto divide-y divide-slate-100/60 dark:divide-white/5 max-h-[380px] sm:max-h-[420px] overscroll-contain p-1"
            ></div>

            <!-- Modal Footer -->
            <div class="px-4 py-2.5 bg-slate-50/90 dark:bg-[#070d18]/90 border-t border-slate-100 dark:border-white/5 flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
              <div class="flex items-center gap-3">
                <span class="flex items-center gap-1.5"><kbd class="px-1.5 py-0.5 rounded bg-slate-200/80 dark:bg-white/10 font-mono text-[9px] text-slate-600 dark:text-slate-300">↑↓</kbd> navigate</span>
                <span class="flex items-center gap-1.5"><kbd class="px-1.5 py-0.5 rounded bg-slate-200/80 dark:bg-white/10 font-mono text-[9px] text-slate-600 dark:text-slate-300">↵</kbd> select</span>
                <span class="flex items-center gap-1.5"><kbd class="px-1.5 py-0.5 rounded bg-slate-200/80 dark:bg-white/10 font-mono text-[9px] text-slate-600 dark:text-slate-300">esc</kbd> close</span>
              </div>
              <div class="hidden sm:flex items-center gap-2 text-[10.5px] text-slate-400 dark:text-slate-500">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>FlezPay Command Palette</span>
              </div>
            </div>
          </div>
        </div>
      </dialog>
    `,

  render() {
    const container = document.getElementById("sidebar-container");
    if (!container) return;

    // Inject Styles
    if (!document.getElementById("sidebar-styles")) {
      const style = document.createElement("style");
      style.id = "sidebar-styles";
      style.textContent = `
                .sidebar-link { border-radius: 9999px !important; }
                .sidebar-link.active { 
                    background-color: #cfff45 !important; 
                    color: black !important;
                    font-weight: 700;
                    box-shadow: 0 4px 14px 0 rgba(0,0,0,0.3);
                }
                .sidebar-link.active i, .sidebar-link.active svg, .sidebar-link.active span { color: black !important; stroke: black !important; }
                
                /* Overflow Handling for Sidebar & Search Dropdown */
                #sidebar { overflow: hidden; }
                #sidebar:focus-within, #sidebar.search-open {
                    overflow: visible !important;
                }

                @media (min-width: 1024px) {
                    #sidebar { transition: width 0.3s ease; overflow-x: hidden; }
                    
                    /* Sidebar Expanded State (Hover or Focus-Within) */
                    #sidebar:hover, #sidebar:focus-within { width: 13.5rem !important; }
                    #sidebar:hover .lg\\:hidden, #sidebar:focus-within .lg\\:hidden { display: flex !important; align-items: center; }
                    #sidebar:hover #sidebar-logo-container, #sidebar:focus-within #sidebar-logo-container {
                        justify-content: flex-start !important;
                        padding-left: 1.5rem !important;
                        padding-right: 1.5rem !important;
                    }
                    #sidebar:hover .sidebar-link, #sidebar:focus-within .sidebar-link,
                    #sidebar:hover .sidebar-search-btn, #sidebar:focus-within .sidebar-search-btn,
                    #sidebar:hover button.shrink-0, #sidebar:focus-within button.shrink-0 { 
                        justify-content: flex-start !important;
                        width: calc(100% - 2rem) !important;
                        padding-left: 1rem !important;
                        padding-right: 1rem !important;
                    }
                    #sidebar:hover nav > div.shrink-0, #sidebar:focus-within nav > div.shrink-0 {
                        width: calc(100% - 2rem) !important;
                    }

                    /* Sidebar Search Trigger Collapsed & Expanded States */
                    .sidebar-search-btn {
                        white-space: nowrap !important;
                    }
                    .sidebar-search-btn .sidebar-search-text {
                        white-space: nowrap !important;
                        overflow: hidden !important;
                        text-overflow: ellipsis !important;
                    }
                    #sidebar:not(:hover):not(:focus-within) .sidebar-search-btn {
                        width: 2.75rem !important;
                        padding-left: 0 !important;
                        padding-right: 0 !important;
                        justify-content: center !important;
                    }
                    #sidebar:not(:hover):not(:focus-within) .sidebar-search-btn .sidebar-search-text,
                    #sidebar:not(:hover):not(:focus-within) .sidebar-search-btn .sidebar-search-kbd {
                        display: none !important;
                    }
                    #sidebar:hover .sidebar-search-btn,
                    #sidebar:focus-within .sidebar-search-btn {
                        padding-left: 0.75rem !important;
                        padding-right: 0.75rem !important;
                    }
                    #sidebar:hover .sidebar-search-btn .sidebar-search-text,
                    #sidebar:focus-within .sidebar-search-btn .sidebar-search-text {
                        display: block !important;
                        white-space: nowrap !important;
                        overflow: hidden !important;
                        text-overflow: ellipsis !important;
                    }
                    #sidebar:hover .sidebar-search-btn .sidebar-search-kbd,
                    #sidebar:focus-within .sidebar-search-btn .sidebar-search-kbd {
                        display: inline-flex !important;
                        flex-shrink: 0 !important;
                        margin-left: auto !important;
                    }
                }
                
                /* Layout Fixes */
                #sidebar nav {
                    flex: 1 1 0%;
                    min-height: 0;
                    overflow-y: auto;
                    padding-bottom: 2rem; /* Clearance for footer */
                }

                /* Minimalist Sidebar Scrollbar */
                #sidebar nav::-webkit-scrollbar {
                    width: 0px; /* Hide scrollbar completely for ultra-clean look */
                }
                #sidebar nav {
                    scrollbar-width: none; /* Firefox */
                }

                /* Centered Search Overlay Modal */
                #global-search-modal {
                    border: none;
                    background: transparent;
                    padding: 0;
                    max-width: none;
                    max-height: none;
                    width: 100vw;
                    height: 100vh;
                    margin: 0;
                    display: none;
                }
                #global-search-modal[open] {
                    display: block;
                }
                #global-search-modal::backdrop {
                    background: transparent;
                }
                #global-search-modal .modal-backdrop {
                    transition: opacity 0.2s cubic-bezier(0.16, 1, 0.3, 1);
                    opacity: 0;
                }
                #global-search-modal .modal-card {
                    transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s cubic-bezier(0.16, 1, 0.3, 1);
                    transform: scale(0.96) translateY(-8px);
                    opacity: 0;
                }
                #global-search-modal.is-active .modal-backdrop {
                    opacity: 1;
                }
                #global-search-modal.is-active .modal-card {
                    transform: scale(1) translateY(0);
                    opacity: 1;
                }

                /* Command Palette Header & Search Input Reset & Styling */
                #global-search-header {
                    height: 3.75rem !important; /* 60px */
                    min-height: 3.75rem !important;
                }
                #global-search-input {
                    all: unset !important;
                    box-sizing: border-box !important;
                    width: 100% !important;
                    flex: 1 1 0% !important;
                    min-width: 0 !important;
                    height: 100% !important;
                    background: transparent !important;
                    background-color: transparent !important;
                    border: none !important;
                    border-width: 0 !important;
                    outline: none !important;
                    outline-width: 0 !important;
                    box-shadow: none !important;
                    appearance: none !important;
                    -webkit-appearance: none !important;
                    -moz-appearance: none !important;
                    padding: 0 !important;
                    margin: 0 !important;
                    font-family: inherit !important;
                    font-size: 1.025rem !important;
                    font-weight: 400 !important;
                    line-height: 1.5 !important;
                    color: #0f172a !important;
                    cursor: text !important;
                }
                .dark #global-search-input {
                    color: #f8fafc !important;
                }
                #global-search-input::placeholder {
                    color: #94a3b8 !important;
                    font-size: 0.9375rem !important;
                    font-weight: 400 !important;
                    opacity: 1 !important;
                }
                .dark #global-search-input::placeholder {
                    color: #64748b !important;
                }
                #global-search-input:focus,
                #global-search-input:focus-visible,
                #global-search-input:hover {
                    outline: none !important;
                    border: none !important;
                    box-shadow: none !important;
                }

                /* Search Results Scrollbar */
                #global-search-results {
                    scrollbar-width: thin;
                    scrollbar-color: rgba(156, 163, 175, 0.4) transparent;
                    -webkit-overflow-scrolling: touch;
                }
                #global-search-results::-webkit-scrollbar {
                    width: 5px;
                }
                #global-search-results::-webkit-scrollbar-track {
                    background: transparent;
                }
                #global-search-results::-webkit-scrollbar-thumb {
                    background: rgba(156, 163, 175, 0.35);
                    border-radius: 9999px;
                }
                #global-search-results::-webkit-scrollbar-thumb:hover {
                    background: rgba(156, 163, 175, 0.6);
                }

                /* Category Filter Chips */
                .search-filter-chip {
                    cursor: pointer;
                    user-select: none;
                    white-space: nowrap;
                    border: 1px solid transparent;
                }
                .search-filter-chip.active {
                    background-color: #cfff45 !important;
                    color: #000000 !important;
                    font-weight: 700 !important;
                    border-color: #b8ee30 !important;
                    box-shadow: 0 2px 8px -1px rgba(207, 255, 69, 0.4);
                }

                .search-result-item.selected {
                    background-color: rgba(207, 255, 69, 0.15) !important;
                }
                .search-result-item.selected .search-item-icon {
                    background-color: #cfff45 !important;
                    color: black !important;
                }
                .search-result-item.selected .search-item-title {
                    color: #19352d !important;
                }
                .dark .search-result-item.selected .search-item-title {
                    color: #cfff45 !important;
                }
                
                /* Dynamic JS Tooltip styling */
                .sidebar-dynamic-tooltip {
                    position: fixed;
                    z-index: 9999;
                    background: black;
                    color: white;
                    font-size: 0.75rem;
                    font-weight: bold;
                    padding: 0.375rem 0.75rem;
                    border-radius: 0.5rem;
                    pointer-events: none;
                    white-space: nowrap;
                    opacity: 0;
                    transition: opacity 0.2s ease, transform 0.2s ease;
                    transform: translateX(-10px);
                    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
                }
                .sidebar-dynamic-tooltip.visible {
                    opacity: 1;
                    transform: translateX(0);
                }
            `;
      document.head.appendChild(style);
    }

    container.innerHTML = this.template;
    this.initMobileToggle();
    this.initTooltips();
    this.initSearch();

    // Use timeout to ensure DOM is ready and other scripts have settled
    setTimeout(() => {
      this.initActiveLink();
      this.initClickHandlers();
      this.initPendingOrdersBadge();
      this.initLowStockBadge();
      this.initManagerPermissions();
      if (window.lucide) {
        window.lucide.createIcons();
      }
    }, 50);
  },

  initManagerPermissions() {
    try {
      const userData = JSON.parse(localStorage.getItem("user_data") || "{}");
      const isFinancesMasked = !!(userData.finances_masked || (userData.manager_account && userData.manager_account.manage_finances === false));
      const isPayrollMasked = !!(userData.payroll_masked || (userData.manager_account && userData.manager_account.manage_payroll === false));

      if (isFinancesMasked) {
        const walletLinks = document.querySelectorAll('#sidebar a[href^="/wallet"]');
        walletLinks.forEach(link => {
          link.style.display = 'none';
        });
      }

      if (isPayrollMasked) {
        const payrollLinks = document.querySelectorAll('#sidebar a[href^="/payroll"], #sidebar a[href^="/add-payroll"]');
        payrollLinks.forEach(link => {
          link.style.display = 'none';
        });
      }
    } catch (e) {
      // Fail silently
    }
  },

  initClickHandlers() {
    const links = document.querySelectorAll("#sidebar .sidebar-link");
    links.forEach(link => {
      link.addEventListener("click", () => {
        // Drop focus so :focus-within state is removed immediately, closing the sidebar
        link.blur();
      });
    });
  },

  initPendingOrdersBadge() {
    try {
      const userData = JSON.parse(localStorage.getItem("user_data") || "{}");
      const business = userData.business_details?.[0];
      const count = business?.online_orders_pending_count || 0;
      SidebarComponent.updatePendingOrdersBadge(count);
    } catch (e) {
      // Fail silently — badge just stays hidden
    }
  },

  updatePendingOrdersBadge(count) {
    const dotBadge = document.getElementById("store-pending-badge");
    const textBadge = document.getElementById("store-pending-badge-text");
    if (!dotBadge || !textBadge) return;

    if (count > 0) {
      dotBadge.classList.remove("hidden");
      textBadge.classList.remove("hidden");
      textBadge.textContent = count > 99 ? "99+" : count;
    } else {
      dotBadge.classList.add("hidden");
      textBadge.classList.add("hidden");
    }
  },

  initLowStockBadge() {
    try {
      let count = 0;
      const cached = localStorage.getItem("low_stock_items");
      if (cached) {
        const items = JSON.parse(cached);
        if (Array.isArray(items)) count = items.length;
      }
      if (count === 0) {
        const userData = JSON.parse(localStorage.getItem("user_data") || "{}");
        if (Array.isArray(userData.low_stock_items)) {
          count = userData.low_stock_items.length;
        }
      }
      SidebarComponent.updateLowStockBadge(count);
    } catch (e) {
      // Fail silently — badge just stays hidden
    }
  },

  updateLowStockBadge(count) {
    const dotBadge = document.getElementById("products-low-stock-badge");
    const textBadge = document.getElementById("products-low-stock-badge-text");
    if (!dotBadge || !textBadge) return;

    if (count > 0) {
      dotBadge.classList.remove("hidden");
      textBadge.classList.remove("hidden");
      textBadge.textContent = count > 99 ? "99+" : count;
    } else {
      dotBadge.classList.add("hidden");
      textBadge.classList.add("hidden");
    }
  },

  initTooltips() {
    // Create tooltip element
    let tooltipEl = document.getElementById('sidebar-dynamic-tooltip');
    if (!tooltipEl) {
        tooltipEl = document.createElement('div');
        tooltipEl.id = 'sidebar-dynamic-tooltip';
        tooltipEl.className = 'sidebar-dynamic-tooltip';
        document.body.appendChild(tooltipEl);
    }

    const elements = document.querySelectorAll('#sidebar [data-tooltip]');
    
    elements.forEach(el => {
        el.addEventListener('mouseenter', (e) => {
            if (window.innerWidth < 1024 || document.getElementById('sidebar').matches(':hover')) return; // Disable tooltips on mobile or when expanded
            
            const rect = el.getBoundingClientRect();
            tooltipEl.textContent = el.getAttribute('data-tooltip');
            
            // Position to the right, perfectly centered vertically with the icon
            tooltipEl.style.top = Math.round(rect.top + (rect.height / 2) - 14) + 'px'; // 14 is half roughly expected tooltip height
            tooltipEl.style.left = Math.round(rect.right + 12) + 'px'; // 12px gap
            tooltipEl.classList.add('visible');
        });

        el.addEventListener('mouseleave', () => {
            tooltipEl.classList.remove('visible');
        });
        
        el.addEventListener('click', () => {
             tooltipEl.classList.remove('visible');
        });
    });
  },

  initActiveLink() {
    const path = window.location.pathname.replace(/\/$/, "") || "/dashboard";
    const links = document.querySelectorAll(".sidebar-link");

    links.forEach((link) => {
      const href = link.getAttribute("href");
      if (!href) return; // Skip buttons/non-links

      const normalizedHref = href.replace(/\/$/, "");
      if (
        normalizedHref === path ||
        (path === "/" && normalizedHref === "/dashboard") ||
        (normalizedHref !== "/" && path.startsWith(normalizedHref + "/"))
      ) {
        link.classList.add("active");
      } else {
        link.classList.remove("active");
      }
    });
  },

  initMobileToggle() {
    // Event delegation on document ensures the toggle works perfectly across SPA transitions
    // even when the #sidebar-toggle button is dynamically destroyed and re-created.
    if (!SidebarComponent._toggleBound) {
      SidebarComponent._toggleBound = true;
      
      document.addEventListener("click", (e) => {
        const toggleBtn = e.target.closest("#sidebar-toggle");
        const sidebar = document.getElementById("sidebar");
        
        if (toggleBtn && sidebar) {
          e.stopPropagation();
          sidebar.classList.toggle("-translate-x-full");
        }
      });
    }

    // Close sidebar when clicking outside on mobile.
    if (!SidebarComponent._outsideClickBound) {
      SidebarComponent._outsideClickBound = true;
      document.addEventListener("click", (e) => {
        const sb = document.getElementById("sidebar");
        const tb = e.target.closest("#sidebar-toggle");
        if (
          sb &&
          window.innerWidth < 1024 &&
          !sb.contains(e.target) &&
          !tb
        ) {
          sb.classList.add("-translate-x-full");
        }
      });
    }

    // Close sidebar when clicking a link inside it on mobile.
    if (!SidebarComponent._linkClickBound) {
      SidebarComponent._linkClickBound = true;
      document.addEventListener("click", (e) => {
        const link = e.target.closest(".sidebar-link");
        const sb = document.getElementById("sidebar");
        if (link && sb && window.innerWidth < 1024) {
          sb.classList.add("-translate-x-full");
        }
      });
    }
  },

  escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  },

  highlightMatch(text, query) {
    if (!query || !query.trim()) return SidebarComponent.escapeHtml(text);
    const q = query.trim();
    const escapedQ = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(`(${escapedQ})`, "gi");
    return SidebarComponent.escapeHtml(text).replace(
      regex,
      '<mark class="bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 font-bold px-0.5 rounded">$1</mark>'
    );
  },

  getCategoryBadgeClass(category) {
    switch (category) {
      case "Core":
        return "bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/20";
      case "Finance":
        return "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20";
      case "Store":
        return "bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/20";
      case "Sales":
        return "bg-violet-500/15 text-violet-600 dark:text-violet-400 border border-violet-500/20";
      case "Team":
        return "bg-cyan-500/15 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20";
      case "Growth":
        return "bg-pink-500/15 text-pink-600 dark:text-pink-400 border border-pink-500/20";
      case "AI":
        return "bg-purple-500/15 text-purple-600 dark:text-purple-400 border border-purple-500/20";
      case "Support":
        return "bg-teal-500/15 text-teal-600 dark:text-teal-400 border border-teal-500/20";
      case "Account":
      default:
        return "bg-slate-500/15 text-slate-600 dark:text-slate-400 border border-slate-500/20";
    }
  },

  filterNavItems(query, category = "all") {
    const q = (query || "").trim().toLowerCase();
    
    let isFinancesMasked = false;
    let isPayrollMasked = false;
    try {
      const userData = JSON.parse(localStorage.getItem("user_data") || "{}");
      isFinancesMasked = !!(userData.finances_masked || (userData.manager_account && userData.manager_account.manage_finances === false));
      isPayrollMasked = !!(userData.payroll_masked || (userData.manager_account && userData.manager_account.manage_payroll === false));
    } catch (e) {}

    let items = SidebarComponent.NAV_ITEMS || [];
    if (isFinancesMasked) {
      items = items.filter((item) => !item.url.startsWith("/wallet"));
    }
    if (isPayrollMasked) {
      items = items.filter((item) => !item.url.startsWith("/payroll") && !item.url.startsWith("/add-payroll"));
    }

    const catFilter = category ? category.toLowerCase() : "all";

    // Filter by category first if not 'all'
    let filtered = items;
    if (catFilter !== "all") {
      filtered = items.filter(
        (item) => (item.category || "").toLowerCase() === catFilter
      );
    }

    if (!q) {
      if (catFilter !== "all") {
        return filtered;
      }
      // Default suggested quick links for instant navigation
      const quickUrls = [
        "/dashboard",
        "/analytics",
        "/transactions",
        "/wallet?action=fund",
        "/wallet?action=withdraw",
        "/products",
        "/store",
        "/pos",
        "/tax-credit",
        "/payroll",
        "/growth",
        "/ai-manager",
        "/settings"
      ];
      return items.filter((item) => quickUrls.includes(item.url));
    }

    // Score and rank matches
    const scored = [];
    filtered.forEach((item) => {
      const titleLower = item.title.toLowerCase();
      const descLower = (item.desc || "").toLowerCase();
      const catLower = (item.category || "").toLowerCase();
      const urlLower = item.url.toLowerCase();
      const kwMatch = (item.keywords || []).some((kw) =>
        kw.toLowerCase().includes(q)
      );

      let score = 0;
      if (titleLower === q) score += 100;
      else if (titleLower.startsWith(q)) score += 60;
      else if (titleLower.includes(q)) score += 40;

      if (kwMatch) score += 30;
      if (catLower.includes(q)) score += 20;
      if (descLower.includes(q)) score += 15;
      if (urlLower.includes(q)) score += 10;

      if (score > 0) {
        scored.push({ item, score });
      }
    });

    scored.sort((a, b) => b.score - a.score);
    return scored.map((s) => s.item);
  },

  renderSearchResults(results, query, selectedIndex) {
    const resultsContainer = document.getElementById("global-search-results");
    const countLabel = document.getElementById("global-search-count");
    const hintLabel = document.getElementById("global-search-hint");
    if (!resultsContainer) return;

    if (countLabel) {
      if (!query || !query.trim()) {
        countLabel.textContent = "Quick Navigation";
        if (hintLabel) hintLabel.textContent = "Showing recommended pages";
      } else if (results.length === 0) {
        countLabel.textContent = "No Matches";
        if (hintLabel) hintLabel.textContent = "Try another search term";
      } else {
        countLabel.textContent = `Pages & Actions (${results.length})`;
        if (hintLabel) hintLabel.textContent = "Use ↑↓ to navigate, ↵ to open";
      }
    }

    if (results.length === 0) {
      resultsContainer.innerHTML = `
        <div class="px-6 py-12 text-center flex flex-col items-center justify-center">
          <div class="w-12 h-12 mx-auto rounded-2xl bg-slate-100 dark:bg-white/5 flex items-center justify-center text-slate-400 mb-3 border border-slate-200 dark:border-white/5">
            <i data-lucide="search-x" class="w-6 h-6 text-slate-400 dark:text-slate-500"></i>
          </div>
          <p class="text-[14px] font-semibold text-slate-700 dark:text-slate-200">No dashboard results found</p>
          <p class="text-[12px] text-slate-400 dark:text-slate-500 mt-1 max-w-sm">
            We couldn't find anything matching "<span class="text-emerald-500 font-medium">${SidebarComponent.escapeHtml(
              query
            )}</span>".
          </p>
          <div class="mt-4 flex flex-wrap justify-center gap-1.5 max-w-md">
            <span class="text-[11px] text-slate-400 self-center mr-1">Suggestions:</span>
            <button type="button" class="search-suggestion-chip px-2.5 py-1 text-[11px] rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 transition-colors" data-val="orders">orders</button>
            <button type="button" class="search-suggestion-chip px-2.5 py-1 text-[11px] rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 transition-colors" data-val="wallet">wallet</button>
            <button type="button" class="search-suggestion-chip px-2.5 py-1 text-[11px] rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 transition-colors" data-val="tax">tax</button>
            <button type="button" class="search-suggestion-chip px-2.5 py-1 text-[11px] rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 transition-colors" data-val="payroll">payroll</button>
          </div>
        </div>
      `;

      // Attach click listeners to suggestion chips
      const chips = resultsContainer.querySelectorAll(".search-suggestion-chip");
      chips.forEach((chip) => {
        chip.onclick = () => {
          const val = chip.getAttribute("data-val");
          const input = document.getElementById("global-search-input");
          if (input && val) {
            input.value = val;
            input.dispatchEvent(new Event("input"));
            input.focus();
          }
        };
      });

      if (window.lucide) window.lucide.createIcons();
      return;
    }

    resultsContainer.innerHTML = results
      .map((item, idx) => {
        const isSelected = idx === selectedIndex;
        return `
        <a
          href="${item.url}"
          data-index="${idx}"
          data-url="${item.url}"
          class="search-result-item flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-xl transition-all group cursor-pointer ${
            isSelected
              ? "selected bg-emerald-500/10 dark:bg-emerald-500/15"
              : "hover:bg-slate-100/80 dark:hover:bg-white/5"
          }"
          tabindex="-1"
        >
          <div class="flex items-center gap-3 min-w-0 flex-1">
            <div class="search-item-icon w-8 h-8 rounded-xl flex items-center justify-center shrink-0 transition-all ${
              isSelected
                ? "bg-emerald-500 text-black font-bold shadow-md shadow-emerald-500/20"
                : "bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400 group-hover:text-emerald-500 group-hover:bg-emerald-500/10"
            }">
              <i data-lucide="${item.icon}" class="w-4 h-4 shrink-0"></i>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="search-item-title text-[13px] font-semibold truncate transition-colors ${
                  isSelected
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-slate-800 dark:text-white group-hover:text-emerald-500"
                }">
                  ${SidebarComponent.highlightMatch(item.title, query)}
                </span>
                <span class="search-badge text-[9.5px] font-medium px-2 py-0.5 rounded-full shrink-0 ${SidebarComponent.getCategoryBadgeClass(
                  item.category
                )}">
                  ${item.category}
                </span>
              </div>
              <p class="text-[11px] text-slate-500 dark:text-slate-400 line-clamp-1 mt-0.5 leading-normal">
                ${SidebarComponent.highlightMatch(item.desc, query)}
              </p>
            </div>
          </div>
          <div class="search-item-action shrink-0 flex items-center pl-2">
            <kbd class="hidden sm:inline-flex items-center px-1.5 py-0.5 text-[9.5px] font-mono rounded bg-slate-200/60 dark:bg-white/5 text-slate-400 dark:text-slate-400 border border-slate-300/40 dark:border-white/5 ${
              isSelected
                ? "!border-emerald-500/40 !text-emerald-600 dark:!text-emerald-400 bg-emerald-500/10"
                : ""
            }">↵</kbd>
          </div>
        </a>
      `;
      })
      .join("");

    if (window.lucide) {
      window.lucide.createIcons();
    }
  },

  scrollSelectedItemIntoView(index) {
    const resultsContainer = document.getElementById("global-search-results");
    if (!resultsContainer) return;
    const item = resultsContainer.querySelector(`[data-index="${index}"]`);
    if (item) {
      item.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  },

  openSearch() {
    const modal = document.getElementById("global-search-modal");
    const input = document.getElementById("global-search-input");
    const sidebar = document.getElementById("sidebar");
    if (!modal) return;

    // Close mobile sidebar drawer if currently open
    if (sidebar && window.innerWidth < 1024) {
      sidebar.classList.add("-translate-x-full");
    }

    if (!modal.open) {
      modal.showModal();
      document.body.classList.add("overflow-hidden");
      requestAnimationFrame(() => {
        modal.classList.add("is-active");
      });
    }

    if (input) {
      input.focus();
      input.select();
    }

    const currentVal = input ? input.value : "";
    const activeChip = modal.querySelector(".search-filter-chip.active");
    const activeCategory = activeChip
      ? activeChip.getAttribute("data-category")
      : "all";
    const results = SidebarComponent.filterNavItems(currentVal, activeCategory);
    SidebarComponent._searchSelectedIndex = results.length > 0 ? 0 : -1;
    SidebarComponent.renderSearchResults(
      results,
      currentVal,
      SidebarComponent._searchSelectedIndex
    );
  },

  closeSearch() {
    const modal = document.getElementById("global-search-modal");
    const input = document.getElementById("global-search-input");
    if (!modal || !modal.open) return;

    modal.classList.remove("is-active");
    document.body.classList.remove("overflow-hidden");

    setTimeout(() => {
      if (modal.open) {
        modal.close();
      }
    }, 150);

    if (input) {
      input.blur();
    }
    SidebarComponent._searchSelectedIndex = 0;
  },

  navigateToResult(url) {
    if (!url) return;
    SidebarComponent.closeSearch();
    if (window.innerWidth < 1024) {
      const sidebar = document.getElementById("sidebar");
      if (sidebar) sidebar.classList.add("-translate-x-full");
    }

    if (url === "/logout") {
      if (typeof window.logout === "function") {
        window.logout();
        return;
      }
      window.location.href = "/logout";
      return;
    }

    // Special handling if already on /wallet and clicking wallet action link
    if (
      window.location.pathname === "/wallet" ||
      window.location.pathname === "/wallet/"
    ) {
      if (url.includes("action=withdraw")) {
        const withdrawBtn = document.getElementById("withdraw-btn");
        if (withdrawBtn) withdrawBtn.click();
        window.history.pushState({}, "", url);
        return;
      }
      if (url.includes("action=fund")) {
        const fundBtn = document.getElementById("fund-btn");
        if (fundBtn) fundBtn.click();
        window.history.pushState({}, "", url);
        return;
      }
    }

    if (window.flezSwup && typeof window.flezSwup.navigate === "function") {
      if (window.location.pathname + window.location.search !== url) {
        window.flezSwup.navigate(url);
      } else {
        window.location.href = url;
      }
    } else {
      window.location.href = url;
    }
  },

  initSearch() {
    const modal = document.getElementById("global-search-modal");
    const input = document.getElementById("global-search-input");
    const clearBtn = document.getElementById("sidebar-search-clear");
    const closeBtn = document.getElementById("global-search-close-btn");
    const searchTrigger = document.getElementById("sidebar-search-trigger");
    const resultsContainer = document.getElementById("global-search-results");
    const filterChips = document.querySelectorAll(".search-filter-chip");
    if (!modal || !input) return;

    let currentResults = [];
    SidebarComponent._searchSelectedIndex = 0;

    const getActiveCategory = () => {
      const chip = modal.querySelector(".search-filter-chip.active");
      return chip ? chip.getAttribute("data-category") : "all";
    };

    const updateResults = () => {
      const q = input.value || "";
      if (clearBtn) {
        if (q.trim().length > 0) {
          clearBtn.classList.remove("hidden");
        } else {
          clearBtn.classList.add("hidden");
        }
      }
      const category = getActiveCategory();
      currentResults = SidebarComponent.filterNavItems(q, category);
      SidebarComponent._searchSelectedIndex =
        currentResults.length > 0 ? 0 : -1;
      SidebarComponent.renderSearchResults(
        currentResults,
        q,
        SidebarComponent._searchSelectedIndex
      );
    };

    // Trigger button in sidebar
    if (searchTrigger) {
      searchTrigger.onclick = (e) => {
        e.preventDefault();
        SidebarComponent.openSearch();
      };
    }

    // Input events
    input.oninput = () => {
      updateResults();
    };

    if (clearBtn) {
      clearBtn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        input.value = "";
        clearBtn.classList.add("hidden");
        updateResults();
        input.focus();
      };
    }

    if (closeBtn) {
      closeBtn.onclick = (e) => {
        e.preventDefault();
        SidebarComponent.closeSearch();
      };
    }

    // Filter chip clicks
    filterChips.forEach((chip) => {
      chip.onclick = (e) => {
        e.preventDefault();
        filterChips.forEach((c) => {
          c.classList.remove("active");
          c.classList.remove("bg-emerald-500", "text-black", "font-semibold");
          c.classList.add("text-slate-600", "dark:text-slate-400");
        });
        chip.classList.add("active");
        chip.classList.add("bg-emerald-500", "text-black", "font-semibold");
        chip.classList.remove("text-slate-600", "dark:text-slate-400");
        updateResults();
        input.focus();
      };
    });

    // Keyboard navigation inside input
    input.onkeydown = (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (currentResults.length > 0) {
          SidebarComponent._searchSelectedIndex =
            (SidebarComponent._searchSelectedIndex + 1) %
            currentResults.length;
          SidebarComponent.renderSearchResults(
            currentResults,
            input.value,
            SidebarComponent._searchSelectedIndex
          );
          SidebarComponent.scrollSelectedItemIntoView(
            SidebarComponent._searchSelectedIndex
          );
        }
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (currentResults.length > 0) {
          SidebarComponent._searchSelectedIndex =
            (SidebarComponent._searchSelectedIndex -
              1 +
              currentResults.length) %
            currentResults.length;
          SidebarComponent.renderSearchResults(
            currentResults,
            input.value,
            SidebarComponent._searchSelectedIndex
          );
          SidebarComponent.scrollSelectedItemIntoView(
            SidebarComponent._searchSelectedIndex
          );
        }
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (
          SidebarComponent._searchSelectedIndex >= 0 &&
          currentResults[SidebarComponent._searchSelectedIndex]
        ) {
          SidebarComponent.navigateToResult(
            currentResults[SidebarComponent._searchSelectedIndex].url
          );
        } else if (currentResults.length > 0) {
          SidebarComponent.navigateToResult(currentResults[0].url);
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        SidebarComponent.closeSearch();
      }
    };

    // Dialog cancel event (e.g. Esc pressed natively on <dialog>)
    modal.oncancel = (e) => {
      e.preventDefault();
      SidebarComponent.closeSearch();
    };

    // Light-dismiss click outside card (on modal backdrop or outer container)
    modal.onclick = (e) => {
      const card = document.getElementById("global-search-dialog-card");
      if (card && !card.contains(e.target)) {
        SidebarComponent.closeSearch();
      }
    };

    // Hover sync on results
    if (resultsContainer) {
      resultsContainer.onmouseover = (e) => {
        const itemLink = e.target.closest(".search-result-item");
        if (itemLink) {
          const idx = parseInt(itemLink.getAttribute("data-index"), 10);
          if (
            !isNaN(idx) &&
            idx !== SidebarComponent._searchSelectedIndex
          ) {
            SidebarComponent._searchSelectedIndex = idx;
            const items =
              resultsContainer.querySelectorAll(".search-result-item");
            items.forEach((it, i) => {
              if (i === idx) {
                it.classList.add(
                  "selected",
                  "bg-emerald-500/10",
                  "dark:bg-emerald-500/15"
                );
                const icon = it.querySelector(".search-item-icon");
                if (icon) {
                  icon.classList.add(
                    "bg-emerald-500",
                    "text-black",
                    "font-bold",
                    "shadow-md",
                    "shadow-emerald-500/20"
                  );
                  icon.classList.remove(
                    "bg-slate-100",
                    "dark:bg-white/5",
                    "text-slate-500",
                    "dark:text-slate-400"
                  );
                }
                const title = it.querySelector(".search-item-title");
                if (title)
                  title.classList.add(
                    "text-emerald-600",
                    "dark:text-emerald-400"
                  );
                const actionKbd = it.querySelector(".search-item-action kbd");
                if (actionKbd)
                  actionKbd.classList.add(
                    "!border-emerald-500/40",
                    "!text-emerald-600",
                    "dark:!text-emerald-400",
                    "bg-emerald-500/10"
                  );
              } else {
                it.classList.remove(
                  "selected",
                  "bg-emerald-500/10",
                  "dark:bg-emerald-500/15"
                );
                const icon = it.querySelector(".search-item-icon");
                if (icon) {
                  icon.classList.remove(
                    "bg-emerald-500",
                    "text-black",
                    "font-bold",
                    "shadow-md",
                    "shadow-emerald-500/20"
                  );
                  icon.classList.add(
                    "bg-slate-100",
                    "dark:bg-white/5",
                    "text-slate-500",
                    "dark:text-slate-400"
                  );
                }
                const title = it.querySelector(".search-item-title");
                if (title)
                  title.classList.remove(
                    "text-emerald-600",
                    "dark:text-emerald-400"
                  );
                const actionKbd = it.querySelector(".search-item-action kbd");
                if (actionKbd)
                  actionKbd.classList.remove(
                    "!border-emerald-500/40",
                    "!text-emerald-600",
                    "dark:!text-emerald-400",
                    "bg-emerald-500/10"
                  );
              }
            });
          }
        }
      };

      // Result clicks via event delegation
      resultsContainer.onclick = (e) => {
        const itemLink = e.target.closest(".search-result-item");
        if (itemLink) {
          if (e.metaKey || e.ctrlKey) return; // Allow opening in new tab
          e.preventDefault();
          const url =
            itemLink.getAttribute("data-url") || itemLink.getAttribute("href");
          SidebarComponent.navigateToResult(url);
        }
      };
    }

    // Global document listeners (bound only once)
    if (!SidebarComponent._searchGlobalBound) {
      SidebarComponent._searchGlobalBound = true;

      // Global Ctrl+K / Cmd+K shortcut
      document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
          e.preventDefault();
          const modal = document.getElementById("global-search-modal");
          if (modal && modal.open) {
            SidebarComponent.closeSearch();
          } else {
            SidebarComponent.openSearch();
          }
        }
      });
    }
  },
};

// Expose globally for dashboard.js SPA re-initialization
window.SidebarComponent = SidebarComponent;

// Initialize as soon as possible
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    SidebarComponent.render();
    // Register Swup hook if dashboard.js already initialized it
    if (window.flezSwup) {
      window.flezSwup.hooks.on("page:view", () => {
        SidebarComponent.initActiveLink();
        SidebarComponent.initMobileToggle();
        SidebarComponent.initLowStockBadge();
        SidebarComponent.initPendingOrdersBadge();
        SidebarComponent.initSearch();
        SidebarComponent.closeSearch();
      });
    }
  });
} else {
  SidebarComponent.render();
  if (window.flezSwup) {
    window.flezSwup.hooks.on("page:view", () => {
      SidebarComponent.initActiveLink();
      SidebarComponent.initMobileToggle();
      SidebarComponent.initLowStockBadge();
      SidebarComponent.initPendingOrdersBadge();
      SidebarComponent.initSearch();
      SidebarComponent.closeSearch();
    });
  }
}
