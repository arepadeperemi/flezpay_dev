/**
 * header.js - Dynamic Header Component for FlezPay Enterprise
 * Standardizes the page header layout and styling across all dashboard pages.
 */

const HeaderComponent = {
  render: function (title, subtitle) {
    let subtitleHtml = subtitle
      ? `<p class="text-sm text-slate-500 dark:text-slate-400 mt-1 truncate">${subtitle}</p>`
      : "";

    // Hide the title block entirely if there's no title or subtitle (e.g., when the search bar replaces them)
    let titleBlockHtml =
      title || subtitle
        ? `
            <div class="min-w-0 flex-1 hidden sm:block">
                <h2 class="text-xl font-display font-bold text-slate-900 dark:text-white leading-tight truncate">${title}</h2>
                ${subtitleHtml}
            </div>
        `
        : "";

    // Added header-center for dashboard.html search bar injection
    let headerHtml = `
            <header class="h-20 border-b border-slate-200 dark:border-white/5 flex items-center justify-between px-4 lg:px-8 shrink-0 bg-white/50 dark:bg-bg-dark/50 backdrop-blur-md z-50 sticky top-0 relative">
                <div class="flex items-center gap-4 flex-1 min-w-0">
                    <button id="sidebar-toggle" class="p-2 hover:bg-slate-100 dark:bg-white/5 rounded-lg lg:hidden">
                        <i data-lucide="menu" class="w-5 h-5"></i>
                    </button>
                    <div id="header-left" class="flex items-center gap-2"></div>
                    ${titleBlockHtml}
                    <div id="header-center" class="flex-1 min-w-0"></div>
                </div>
                <div id="header-actions" class="flex items-center gap-4 shrink-0"></div>
            </header>
        `;

    return headerHtml;
  },

  /**
   * Attaches the profile dropdown to any avatar found in the page's <header> elements.
   * Called independently so it works on both dynamic (header-mount) and hardcoded headers.
   */
  attachAvatarDropdowns: function () {
    const attachAvatarDropdown = (avatarEl) => {
      if (!avatarEl || !avatarEl.parentNode) return;
      if (avatarEl.hasAttribute("data-dropdown-attached")) return;
      avatarEl.setAttribute("data-dropdown-attached", "true");

      const wrapper = document.createElement("div");
      wrapper.className = "relative group cursor-pointer flex-shrink-0";
      avatarEl.parentNode.insertBefore(wrapper, avatarEl);
      wrapper.appendChild(avatarEl);

      const dropdown = document.createElement("div");
      dropdown.className =
        "absolute right-0 top-full pt-2 w-48 z-[100] opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200";
      dropdown.innerHTML = `
                <div class="bg-white dark:bg-bg-card border border-slate-200 dark:border-white/10 rounded-xl shadow-2xl overflow-hidden p-2 flex flex-col text-left">
                    <a href="/profile" class="flex items-center gap-3 px-3 py-2 text-sm font-medium text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-50 dark:hover:bg-white/5 rounded-lg transition-colors">
                        <i data-lucide="user" class="w-4 h-4"></i> Profile
                    </a>
                    <div class="h-px w-full bg-slate-100 dark:bg-white/10 my-1"></div>
                    <a href="/logout" class="flex items-center gap-3 px-3 py-2 text-sm font-medium text-red-500 dark:text-red-400 hover:text-red-600 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-white/5 rounded-lg transition-colors">
                        <i data-lucide="log-out" class="w-4 h-4"></i> Logout
                    </a>
                </div>
            `;
      wrapper.appendChild(dropdown);
    };

    const headerEls = document.querySelectorAll("header");
    headerEls.forEach((headerEl) => {
      // Handle initials-based avatar divs
      const allDivs = headerEl.querySelectorAll("div");
      const avatarDivs = Array.from(allDivs).filter((el) => {
        const text = el.textContent.trim();
        const isInitials =
          text === "JF" ||
          (window.USER_INITIALS && text === window.USER_INITIALS);
        return (
          isInitials &&
          (el.children.length === 0 || el.classList.contains("w-10"))
        );
      });

      avatarDivs.forEach((avatarDiv) => {
        if (window.USER_AVATAR_URL) {
          avatarDiv.innerHTML = `<img src="${window.USER_AVATAR_URL}" alt="User Avatar" class="w-full h-full object-cover rounded-[inherit]" style="border-radius: inherit;" />`;
          avatarDiv.classList.add("overflow-hidden", "p-0");
          avatarDiv.classList.remove(
            "font-bold",
            "font-display",
            "text-primary",
          );
        } else if (window.USER_INITIALS) {
          avatarDiv.textContent = window.USER_INITIALS;
        }
        const container =
          avatarDiv.closest(".w-10.h-10") ||
          avatarDiv.closest(".h-10.w-10") ||
          avatarDiv;
        attachAvatarDropdown(container);
      });

      // Handle hardcoded image avatars
      const imgAvatars = headerEl.querySelectorAll('img[alt="User Avatar"]');
      imgAvatars.forEach((img) => {
        if (img.src.includes("ui-avatars.com")) {
          if (window.USER_AVATAR_URL) {
            img.src = window.USER_AVATAR_URL;
          } else if (window.USER_INITIALS) {
            img.src = `https://ui-avatars.com/api/?name=${window.USER_INITIALS.split("").join("+")}&background=16a34a&color=fff`;
          }
        }
        const container =
          img.closest(".w-10.h-10") ||
          img.closest(".h-10.w-10") ||
          img.parentElement;
        attachAvatarDropdown(container || img);
      });
    });

    // Re-initialize lucide icons for the dropdown icons
    if (typeof lucide !== "undefined") {
      lucide.createIcons();
    }
  },

  init: function () {
    console.log("HeaderComponent INIT STARTED");
    const mountPoint = document.getElementById("header-mount");

    if (!mountPoint) {
      console.log(
        "HeaderComponent: No mount point — attaching avatar dropdown to hardcoded header.",
      );
      // Still attach the avatar dropdown even on pages without header-mount
      this.attachAvatarDropdowns();
      return;
    }
    if (mountPoint.hasAttribute("data-initialized")) {
      console.log("HeaderComponent: Already initialized!");
      return;
    }
    mountPoint.setAttribute("data-initialized", "true");
    console.log("HeaderComponent: Mount point found!");

    const title = mountPoint.getAttribute("data-title") || "";
    const subtitle = mountPoint.getAttribute("data-subtitle") || "";

    // Inject header HTML into the mount point
    mountPoint.innerHTML = this.render(title, subtitle);

    // Inject custom actions if a template exists
    const actionsContainer = document.getElementById("header-actions");
    const actionsTemplate = document.getElementById("header-actions-template");
    if (actionsTemplate && actionsContainer) {
      const clone = actionsTemplate.content.cloneNode(true);
      actionsContainer.appendChild(clone);
    }

    // Inject center content (e.g. search bar) if a template exists
    const centerContainer = document.getElementById("header-center");
    const centerTemplate = document.getElementById("header-center-template");
    if (centerTemplate && centerContainer) {
      const clone = centerTemplate.content.cloneNode(true);
      centerContainer.appendChild(clone);
    }

    const leftContainer = document.getElementById("header-left");
    const leftTemplate = document.getElementById("header-left-template");
    if (leftTemplate && leftContainer) {
      const clone = leftTemplate.content.cloneNode(true);
      leftContainer.appendChild(clone);
    }

    // Attach avatar dropdown (works for both dynamic and hardcoded headers)
    this.attachAvatarDropdowns();

    // Sidebar toggle logic is handled globally by SidebarComponent.initMobileToggle()

    // Re-initialize theme toggle listeners (for Swup page views)
    if (typeof initTheme === "function") {
      initTheme();
    }

    // Re-inject notification bell (for Swup page views)
    if (window.NotificationComponent) {
      window.NotificationComponent.injectBell();
    }
  },
};

// Initialize on DOM load
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    HeaderComponent.init();
  });
} else {
  HeaderComponent.init();
}

// Initialize on Swup page transition
const registerHeaderSwupHook = () => {
  if (window.flezSwup) {
    // On content:replace, clear the stale data-initialized flag so
    // the header is properly re-built with the new page's template
    window.flezSwup.hooks.on("content:replace", () => {
      const oldMount = document.getElementById("header-mount");
      if (oldMount) oldMount.removeAttribute("data-initialized");
      HeaderComponent.init();
    });
    window.flezSwup.hooks.on("page:view", () => {
      // page:view fires after content:replace; only re-init if somehow
      // the header wasn't initialized yet (shouldn't normally happen)
      const mount = document.getElementById("header-mount");
      if (mount && !mount.hasAttribute("data-initialized")) {
        HeaderComponent.init();
      }
    });
    return true;
  }
  return false;
};

if (!registerHeaderSwupHook()) {
  const interval = setInterval(() => {
    if (registerHeaderSwupHook()) clearInterval(interval);
  }, 100);
  setTimeout(() => clearInterval(interval), 5000);
}
