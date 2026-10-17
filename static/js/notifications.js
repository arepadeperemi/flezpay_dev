/**
 * notifications.js - Premium Dashboard Notification Component
 * Self-contained component for FlezPay Enterprise.
 */

const NotificationComponent = {
    isOpen: false,
    notifications: [],
    activeTab: 'unread',

    template: `
        <div id="notification-overlay" class="fixed inset-0 bg-black/20 dark:bg-black/40 backdrop-blur-[2px] z-[60] transition-opacity duration-300 opacity-0 pointer-events-none"></div>
        <aside id="notification-panel" class="fixed inset-y-0 right-0 w-80 sm:w-96 bg-white/95 dark:bg-bg-dark/95 backdrop-blur-xl border-l border-black/10 dark:border-white/10 z-[70] shadow-2xl transition-transform duration-500 translate-x-full flex flex-col">
            <div class="p-6 border-b border-white/5 flex items-center justify-between">
                <div>
                    <h2 class="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                        Notifications
                        <span id="unread-count" class="w-5 h-5 flex items-center justify-center text-[10px] bg-primary text-white rounded-full">2</span>
                    </h2>
                    <p class="text-xs text-slate-500 mt-1">Stay updated with your business activity</p>
                </div>
                <button onclick="NotificationComponent.toggle()" class="p-2 hover:bg-black/5 dark:hover:bg-white/5 rounded-full text-slate-400 hover:text-slate-900 dark:hover:text-white transition-all">
                    <i data-lucide="x" class="w-5 h-5"></i>
                </button>
            </div>

            <div class="flex items-center gap-6 px-6 pt-2 border-b border-black/5 dark:border-white/5">
                <button onclick="NotificationComponent.setTab('unread')" id="tab-unread" class="pb-3 text-sm font-bold border-b-2 transition-all border-primary text-primary">Unread</button>
                <button onclick="NotificationComponent.setTab('read')" id="tab-read" class="pb-3 text-sm font-bold border-b-2 border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white transition-all">Read</button>
            </div>

            <div class="flex-1 overflow-y-auto p-4 space-y-3" id="notifications-list">
                <!-- Notifications will be injected here -->
            </div>

            <div class="p-4 border-t border-black/5 dark:border-white/5 bg-black/[0.01] dark:bg-white/[0.02]">
                <button onclick="NotificationComponent.markAllRead()" class="w-full py-3 bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 text-sm font-bold rounded-xl transition-all border border-black/10 dark:border-white/10">
                    Mark all as read
                </button>
            </div>
        </aside>
    `,

    bellTemplate: `
        <button id="notification-bell" onclick="NotificationComponent.toggle()" class="relative h-10 w-10 flex items-center justify-center bg-white dark:bg-bg-card border border-slate-200 dark:border-white/10 hover:bg-slate-50 dark:hover:bg-white/5 rounded-xl text-slate-500 dark:text-slate-400 transition-all group shrink-0">
            <i data-lucide="bell" class="w-5 h-5"></i>
            <span id="bell-dot" class="absolute top-2 right-2 w-2 h-2 bg-primary rounded-full border-2 border-white dark:border-bg-dark ring-4 ring-primary/20 animate-pulse hidden"></span>
        </button>
    `,

    render() {
        // 1. Inject Style
        if (!document.getElementById('notification-styles')) {
            const style = document.createElement('style');
            style.id = 'notification-styles';
            style.textContent = `
                #notification-panel { overflow: hidden; }
                .notification-item { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
                .notification-item:hover { background: rgba(0, 0, 0, 0.03); }
                html.dark .notification-item:hover { background: rgba(255, 255, 255, 0.05); }
                .notification-item.unread::before {
                    content: '';
                    position: absolute;
                    left: 0;
                    top: 0;
                    bottom: 0;
                    width: 3px;
                    background: #cfff45;
                }
                #notification-panel-overlay.active { opacity: 1; pointer-events: auto; }
                #notification-panel.open { transform: translateX(0); }
                
                /* Icon Colors */
                .n-icon-transaction, .n-icon-tranc_success { color: #10b981; background: rgba(16, 185, 129, 0.1); }
                .n-icon-security, .n-icon-auth { color: #f59e0b; background: rgba(245, 158, 11, 0.1); }
                .n-icon-system, .n-icon-basic { color: #3b82f6; background: rgba(59, 130, 246, 0.1); }
                .n-icon-payroll { color: #8b5cf6; background: rgba(139, 92, 246, 0.1); }
                .n-icon-tranc_error { color: #ef4444; background: rgba(239, 68, 68, 0.1); }
            `;
            document.head.appendChild(style);
        }

        // 2. Inject Panel to Body
        let container = document.getElementById('notifications-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notifications-container';
            document.body.appendChild(container);
        }
        container.innerHTML = this.template;

        // 3. Auto-inject Bell Icon to Top Bar
        this.injectBell();

        // 4. Initial Load
        this.updateList();
    },

    injectBell() {
        // 1. Prioritize a dedicated container if it exists
        const dedicatedContainer = document.getElementById('notifications-bell');
        if (dedicatedContainer) {
            dedicatedContainer.innerHTML = this.bellTemplate;
            if (window.lucide) lucide.createIcons();
            return;
        }

        // 2. Identify all potential flex containers in the header
        const header = document.querySelector('header');
        if (!header) return;

        // 3. Look for the best container (ideally one with theme-toggle or specific ID, otherwise the right-most flex div)
        let topBarActions = document.querySelector('header #theme-toggle')?.parentElement;
        
        if (!topBarActions) {
            // Find all flex containers and filter out the one that likely contains the title (left side)
            const containers = Array.from(header.querySelectorAll('.flex.items-center'));
            if (containers.length > 0) {
                // Return the last one (furthest right in horizontal flex/grid)
                topBarActions = containers[containers.length - 1];
            }
        }

        // 3. Fallback to header's last child if no specific flex container found
        if (!topBarActions) {
            topBarActions = header.lastElementChild;
        }
        
        // Prevent duplicate bell injection
        if (topBarActions && !document.getElementById('notification-bell')) {
            const bellWrapper = document.createElement('div');
            bellWrapper.innerHTML = this.bellTemplate;
            const bellElement = bellWrapper.firstElementChild;
            
            // If the target is a flex container, prepend/append based on its content
            if (topBarActions.classList.contains('flex')) {
                // If it contains the theme toggle, insert before/after based on preference
                const themeToggle = topBarActions.querySelector('#theme-toggle');
                if (themeToggle) {
                    themeToggle.parentNode.insertBefore(bellElement, themeToggle.nextSibling);
                } else {
                    topBarActions.prepend(bellElement);
                }
            } else {
                // Otherwise insert before the target actions
                topBarActions.parentNode.insertBefore(bellElement, topBarActions);
            }
            if (window.lucide) lucide.createIcons();
        }
    },




    toggle() {
        this.isOpen = !this.isOpen;
        const panel = document.getElementById('notification-panel');
        const overlay = document.getElementById('notification-overlay');
        
        if (this.isOpen) {
            panel?.classList.add('open');
            overlay?.classList.add('opacity-100', 'pointer-events-auto');
            overlay?.classList.remove('opacity-0', 'pointer-events-none');
        } else {
            panel?.classList.remove('open');
            overlay?.classList.remove('opacity-100', 'pointer-events-auto');
            overlay?.classList.add('opacity-0', 'pointer-events-none');
        }
    },

    setTab(tab) {
        this.activeTab = tab;
        this.updateList();
    },

    updateList() {
        const list = document.getElementById('notifications-list');
        const unreadCountEl = document.getElementById('unread-count');
        const bellDot = document.getElementById('bell-dot');
        const tabUnread = document.getElementById('tab-unread');
        const tabRead = document.getElementById('tab-read');
        if (!list) return;

        const userData = JSON.parse(localStorage.getItem('user_data') || '{}');
        const notifs = userData.notifications || this.notifications;

        const unreadCount = notifs.filter(n => !(n.is_read || n.read)).length;
        if (unreadCountEl) unreadCountEl.textContent = unreadCount;
        if (unreadCountEl) unreadCountEl.style.display = unreadCount > 0 ? 'inline-flex' : 'none';
        if (bellDot) bellDot.classList.toggle('hidden', unreadCount === 0);

        if (tabUnread && tabRead) {
            if (this.activeTab === 'unread') {
                tabUnread.className = "pb-3 text-sm font-bold border-b-2 border-primary text-primary transition-all";
                tabRead.className = "pb-3 text-sm font-bold border-b-2 border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white transition-all";
            } else {
                tabRead.className = "pb-3 text-sm font-bold border-b-2 border-primary text-primary transition-all";
                tabUnread.className = "pb-3 text-sm font-bold border-b-2 border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white transition-all";
            }
        }

        const filteredNotifs = notifs.filter(n => {
            const isRead = n.is_read || n.read;
            return this.activeTab === 'unread' ? !isRead : isRead;
        });

        const icons = {
            transaction: 'arrow-down-left',
            security: 'shield-alert',
            system: 'info',
            payroll: 'banknote',
            tranc_success: 'check-circle',
            tranc_error: 'x-circle',
            auth: 'shield-alert',
            basic: 'info'
        };

        if (filteredNotifs.length === 0) {
            list.innerHTML = `<div class="text-center p-8 text-slate-500 text-sm font-medium">No ${this.activeTab} notifications</div>`;
            if (window.lucide) lucide.createIcons();
            return;
        }

        list.innerHTML = filteredNotifs.map((n, idx) => {
            const isRead = n.is_read || n.read;
            const type = n.notification_type || n.type;
            const msg = n.description || n.message;
            let timeStr = n.time;
            if (n.timestamp) {
                const date = new Date(n.timestamp);
                timeStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            }
            const isLast = idx === notifs.length - 1;
            const actionUrlEscaped = (n.action_url || '').replace(/'/g, "\\'");

            return `
            <div class="notification-item relative p-4 bg-transparent ${isLast ? '' : 'border-b'} border-black/5 dark:border-white/5 cursor-pointer flex gap-4 ${isRead ? '' : 'unread'}" onclick="NotificationComponent.handleNotificationClick('${n.id}', '${actionUrlEscaped}')">
                <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 n-icon-${type}">
                    <i data-lucide="${icons[type] || 'bell'}" class="w-5 h-5"></i>
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between mb-0.5">
                        <p class="text-sm font-bold text-slate-900 dark:text-white truncate">${n.title}</p>
                        <span class="text-[10px] text-slate-500 shrink-0">${timeStr}</span>
                    </div>
                    <p class="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed">${msg}</p>
                </div>
            </div>
            `;
        }).join('');

        if (window.lucide) lucide.createIcons();
    },

    handleNotificationClick(id, actionUrl) {
        this.markRead(id);
        if (actionUrl && actionUrl !== 'null' && actionUrl !== 'undefined') {
            this.toggle(); // Close the panel
            if (window.swup) {
                window.swup.navigate(actionUrl);
            } else {
                window.location.href = actionUrl;
            }
        }
    },

    markRead(id) {
        const userData = JSON.parse(localStorage.getItem('user_data') || '{}');
        let notifs = userData.notifications || this.notifications;
        const n = notifs.find(n => String(n.id) === String(id));
        if (n) {
            n.is_read = true;
            n.read = true;
            if (userData.notifications) {
                localStorage.setItem('user_data', JSON.stringify(userData));
            } else {
                this.notifications = notifs;
            }
            this.updateList();
            
            // Persist to backend
            if (window.apiFetch) {
                window.apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/notifications/mark-read`, {
                    method: 'POST',
                    body: JSON.stringify({ notification_id: id })
                }).catch(err => console.error("Failed to mark read on backend", err));
            }
        }
    },

    markAllRead() {
        const userData = JSON.parse(localStorage.getItem('user_data') || '{}');
        let notifs = userData.notifications || this.notifications;
        notifs.forEach(n => { n.is_read = true; n.read = true; });
        if (userData.notifications) {
            localStorage.setItem('user_data', JSON.stringify(userData));
        } else {
            this.notifications = notifs;
        }
        this.updateList();

        // Persist to backend
        if (window.apiFetch) {
            window.apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/notifications/mark-read`, {
                method: 'POST',
                body: JSON.stringify({ mark_all: true })
            }).catch(err => console.error("Failed to mark all read on backend", err));
        }
    }
};

// Attach to window for global access (especially for Swup lifecycle in dashboard.js)
window.NotificationComponent = NotificationComponent;

// Initialize after Swup or DOM load
function initNotificationSystem() {
    window.NotificationComponent.render();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNotificationSystem);
} else {
    initNotificationSystem();
}

// Ensure Swup compatibility - even if Swup is initialized after this script
const registerSwupHook = () => {
    if (window.flezSwup) {
        window.flezSwup.hooks.on('page:view', () => {
            console.log('SPA: Re-injecting notification bell...');
            window.NotificationComponent.injectBell();
        });
        return true;
    }
    return false;
};

if (!registerSwupHook()) {
    const interval = setInterval(() => {
        if (registerSwupHook()) clearInterval(interval);
    }, 100);
    setTimeout(() => clearInterval(interval), 5000); // Stop after 5s
}

