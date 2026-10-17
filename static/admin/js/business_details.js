// Extract user_id from URL: /admin/users/<user_id>/business/
let userId = '';

// Try to get from window.templateUserId first (set by template)
if (typeof window !== 'undefined' && window.templateUserId) {
    userId = window.templateUserId;
}

// Fallback to extracting from URL if not set from template
if (!userId) {
    const pathParts = window.location.pathname.split('/').filter(p => p);
    const usersIndex = pathParts.indexOf('users');
    if (usersIndex !== -1 && pathParts[usersIndex + 1]) {
        userId = pathParts[usersIndex + 1];
    }
}

console.log('Business Details - User ID:', userId);

let currentTab = 'overview';
let searchTimeouts = {};

// Tab switching
function switchTab(tabName) {
    currentTab = tabName;
    
    // Update tab buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('border-indigo-600', 'text-indigo-600');
        btn.classList.add('border-transparent', 'text-gray-500');
    });
    
    const activeTab = document.getElementById(`tab-${tabName}`);
    if (activeTab) {
        activeTab.classList.remove('border-transparent', 'text-gray-500');
        activeTab.classList.add('border-indigo-600', 'text-indigo-600');
    }
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.add('hidden');
    });
    
    const activeContent = document.getElementById(`tab-content-${tabName}`);
    if (activeContent) {
        activeContent.classList.remove('hidden');
    }
    
    // Load data for the tab
    switch(tabName) {
        case 'overview':
            loadOverview();
            break;
        case 'cashiers':
            loadCashiers();
            break;
        case 'managers':
            loadManagers();
            break;
        case 'stocks':
            loadStocks();
            break;
        case 'sales':
            loadSales();
            break;
        case 'sales-by-cashier':
            loadSalesByCashier();
            break;
        case 'ai-usage':
            loadAIUsage();
            break;
    }
}

// Load business overview
async function loadOverview() {
    const loadingState = document.getElementById('loadingState');
    const errorState = document.getElementById('errorState');
    const businessDetailsContent = document.getElementById('businessDetailsContent');
    
    try {
        loadingState.classList.remove('hidden');
        errorState.classList.add('hidden');
        businessDetailsContent.classList.add('hidden');
        
        const response = await fetch(`/admin/api/business/${userId}/data`, {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status && result.data) {
            loadingState.classList.add('hidden');
            businessDetailsContent.classList.remove('hidden');
            const data = result.data;
            const plan = data.subscription_plan;
            
            const currency = await (window.getCurrentCurrency ? window.getCurrentCurrency() : Promise.resolve('NGN'));
            
            let html = `
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    <!-- Business Info Card -->
                    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                        <h3 class="text-lg font-semibold text-gray-900 mb-4" data-translate>Business Information</h3>
                        <div class="space-y-3">
                            <div>
                                <label class="block text-sm font-medium text-gray-500 mb-1" data-translate>Business Name</label>
                                <p class="text-lg text-gray-900">${data.business_name || 'N/A'}</p>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-500 mb-1" data-translate>VAT Percentage</label>
                                <p class="text-lg text-gray-900">${data.vat_percentage || 0}%</p>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-500 mb-1" data-translate>Loyalty Points Equivalent</label>
                                <p class="text-lg text-gray-900">${data.loyalty_point_equivalent || 0}</p>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-500 mb-1" data-translate>Loyalty Enabled</label>
                                <span class="inline-block px-3 py-1 rounded-full text-sm font-semibold ${
                                    data.enable_loyalty ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                                }">
                                    ${data.enable_loyalty ? 'Yes' : 'No'}
                                </span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Subscription Card -->
                    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                        <h3 class="text-lg font-semibold text-gray-900 mb-4" data-translate>Subscription Status</h3>
                        ${plan ? `
                            <div class="space-y-3">
                                <div>
                                    <label class="block text-sm font-medium text-gray-500 mb-1" data-translate>Plan Name</label>
                                    <p class="text-lg text-gray-900">${plan.plan_name}</p>
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-500 mb-1" data-translate>Subscription Expiry</label>
                                    <p class="text-lg text-gray-900">${data.subscription_expiry ? new Date(data.subscription_expiry).toLocaleDateString() : 'N/A'}</p>
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-500 mb-1" data-translate>Features</label>
                                    <div class="mt-2 space-y-1">
                                        <div class="flex items-center">
                                            <span class="text-sm text-gray-700">${plan.inventory ? '✓' : '✗'}</span>
                                            <span class="ml-2 text-sm text-gray-700" data-translate>Inventory Management</span>
                                        </div>
                                        <div class="flex items-center">
                                            <span class="text-sm text-gray-700">${plan.ai_manager ? '✓' : '✗'}</span>
                                            <span class="ml-2 text-sm text-gray-700" data-translate>AI Manager</span>
                                        </div>
                                        <div class="flex items-center">
                                            <span class="text-sm text-gray-700">${plan.ai_calls ? '✓' : '✗'}</span>
                                            <span class="ml-2 text-sm text-gray-700" data-translate>AI Calls</span>
                                        </div>
                                        <div class="flex items-center">
                                            <span class="text-sm text-gray-700">${plan.support ? '✓' : '✗'}</span>
                                            <span class="ml-2 text-sm text-gray-700" data-translate>Support</span>
                                        </div>
                                    </div>
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-500 mb-1" data-translate>Limits</label>
                                    <div class="mt-2 space-y-1 text-sm text-gray-700">
                                        <p data-translate>Cashiers: ${plan.cashiers}</p>
                                        <p data-translate>Collection Accounts: ${plan.collection_accounts}</p>
                                        <p data-translate>Payroll: ${plan.payroll}</p>
                                    </div>
                                </div>
                            </div>
                        ` : '<p class="text-gray-500" data-translate>No subscription plan found</p>'}
                    </div>
                </div>
            `;
            
            document.getElementById('overviewContent').innerHTML = html;
            
            // Initialize translation if available
            if (window.translatePage) {
                const language = await (window.getCurrentLanguage ? window.getCurrentLanguage() : Promise.resolve('en'));
                if (language && language !== 'en') {
                    await window.translatePage(language);
                }
            }
        } else {
            if (loadingState) loadingState.classList.add('hidden');
            if (errorState) {
                errorState.classList.remove('hidden');
                const errorMsg = document.getElementById('errorMessage');
                if (errorMsg) errorMsg.textContent = result.message || 'Failed to load business data';
            }
        }
    } catch (error) {
        console.error('Error loading overview:', error);
        if (loadingState) loadingState.classList.add('hidden');
        if (errorState) {
            errorState.classList.remove('hidden');
            const errorMsg = document.getElementById('errorMessage');
            if (errorMsg) errorMsg.textContent = `An error occurred: ${error.message || 'Unknown error'}`;
        }
    }
}

// Load cashiers with pagination
let cashiersPage = 1;
async function loadCashiers(page = 1) {
    cashiersPage = page;
    const search = document.getElementById('cashierSearch')?.value || '';
    
    try {
        const response = await fetch(`/admin/api/business/${userId}/cashiers?page=${page}&per_page=10&search=${encodeURIComponent(search)}`, {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status) {
            const tbody = document.getElementById('cashiersTableBody');
            if (result.data.length > 0) {
                tbody.innerHTML = result.data.map(cashier => `
                    <tr class="border-b border-gray-100 hover:bg-gray-50">
                        <td class="py-3 px-4">${cashier.account_name || 'N/A'}</td>
                        <td class="py-3 px-4">${cashier.account_email || 'N/A'}</td>
                        <td class="py-3 px-4">${cashier.account_department || 'N/A'}</td>
                        <td class="py-3 px-4">
                            <span class="px-2 py-1 text-xs font-medium rounded-full ${
                                cashier.account_status ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                            }">
                                ${cashier.account_status ? 'Active' : 'Inactive'}
                            </span>
                        </td>
                        <td class="py-3 px-4 text-sm text-gray-500">${cashier.timestamp ? new Date(cashier.timestamp).toLocaleDateString() : 'N/A'}</td>
                    </tr>
                `).join('');
            } else {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center py-8 text-gray-500" data-translate>No cashiers found</td></tr>';
            }
            
            displayPagination('cashiersPagination', result.pagination, loadCashiers);
        }
    } catch (error) {
        console.error('Error loading cashiers:', error);
    }
}

// Load managers with pagination
let managersPage = 1;
async function loadManagers(page = 1) {
    managersPage = page;
    const search = document.getElementById('managerSearch')?.value || '';
    
    try {
        const response = await fetch(`/admin/api/business/${userId}/managers?page=${page}&per_page=10&search=${encodeURIComponent(search)}`, {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status) {
            const tbody = document.getElementById('managersTableBody');
            if (result.data.length > 0) {
                tbody.innerHTML = result.data.map(manager => {
                    const permissions = [];
                    if (manager.add_stock) permissions.push('Add Stock');
                    if (manager.edit_stock) permissions.push('Edit Stock');
                    if (manager.add_cashier) permissions.push('Add Cashier');
                    if (manager.edit_cashier) permissions.push('Edit Cashier');
                    
                    return `
                        <tr class="border-b border-gray-100 hover:bg-gray-50">
                            <td class="py-3 px-4">${manager.manager_name || 'N/A'}</td>
                            <td class="py-3 px-4">${manager.manager_email || 'N/A'}</td>
                            <td class="py-3 px-4">${manager.manager_department || 'N/A'}</td>
                            <td class="py-3 px-4">
                                <div class="flex flex-wrap gap-1">
                                    ${permissions.map(p => `<span class="px-2 py-1 text-xs font-medium rounded-full bg-indigo-100 text-indigo-700">${p}</span>`).join('')}
                                    ${permissions.length === 0 ? '<span class="text-sm text-gray-500">No permissions</span>' : ''}
                                </div>
                            </td>
                        </tr>
                    `;
                }).join('');
            } else {
                tbody.innerHTML = '<tr><td colspan="4" class="text-center py-8 text-gray-500" data-translate>No managers found</td></tr>';
            }
            
            displayPagination('managersPagination', result.pagination, loadManagers);
        }
    } catch (error) {
        console.error('Error loading managers:', error);
    }
}

// Load stocks with pagination
let stocksPage = 1;
async function loadStocks(page = 1) {
    stocksPage = page;
    const search = document.getElementById('stockSearch')?.value || '';
    
    try {
        const response = await fetch(`/admin/api/business/${userId}/stocks?page=${page}&per_page=10&search=${encodeURIComponent(search)}`, {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status) {
            const tbody = document.getElementById('stocksTableBody');
            const currency = await (window.getCurrentCurrency ? window.getCurrentCurrency() : Promise.resolve('NGN'));
            
            if (result.data.length > 0) {
                tbody.innerHTML = await Promise.all(result.data.map(async stock => {
                    const convertedAmount = await (window.convertCurrency ? window.convertCurrency(stock.item_amount, 'NGN', currency) : Promise.resolve(stock.item_amount));
                    return `
                        <tr class="border-b border-gray-100 hover:bg-gray-50">
                            <td class="py-3 px-4">${stock.item_name || 'N/A'}</td>
                            <td class="py-3 px-4">${stock.item_quantity || 0}</td>
                            <td class="py-3 px-4">${window.formatCurrency ? window.formatCurrency(convertedAmount, currency) : `${currency} ${convertedAmount.toFixed(2)}`}</td>
                            <td class="py-3 px-4">${stock.item_department || 'N/A'}</td>
                            <td class="py-3 px-4 text-sm text-gray-500">${stock.timestamp ? new Date(stock.timestamp).toLocaleDateString() : 'N/A'}</td>
                        </tr>
                    `;
                })).then(rows => rows.join(''));
            } else {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center py-8 text-gray-500" data-translate>No stocks found</td></tr>';
            }
            
            displayPagination('stocksPagination', result.pagination, loadStocks);
        }
    } catch (error) {
        console.error('Error loading stocks:', error);
    }
}

// Load sales with pagination
let salesPage = 1;
async function loadSales(page = 1) {
    salesPage = page;
    const search = document.getElementById('salesSearch')?.value || '';
    const statusFilter = document.getElementById('salesStatusFilter')?.value || '';
    
    try {
        const response = await fetch(`/admin/api/business/${userId}/sales?page=${page}&per_page=10&search=${encodeURIComponent(search)}&status=${encodeURIComponent(statusFilter)}`, {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status) {
            const tbody = document.getElementById('salesTableBody');
            const currency = await (window.getCurrentCurrency ? window.getCurrentCurrency() : Promise.resolve('NGN'));
            
            if (result.data.length > 0) {
                tbody.innerHTML = await Promise.all(result.data.map(async sale => {
                    const convertedAmount = await (window.convertCurrency ? window.convertCurrency(sale.total_amount, 'NGN', currency) : Promise.resolve(sale.total_amount));
                    return `
                        <tr class="border-b border-gray-100 hover:bg-gray-50">
                            <td class="py-3 px-4">${sale.id || 'N/A'}</td>
                            <td class="py-3 px-4">
                                <span class="px-2 py-1 text-xs font-medium rounded-full ${
                                    sale.invoice_status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                                }">
                                    ${sale.invoice_status || 'N/A'}
                                </span>
                            </td>
                            <td class="py-3 px-4 font-medium">${window.formatCurrency ? window.formatCurrency(convertedAmount, currency) : `${currency} ${convertedAmount.toFixed(2)}`}</td>
                            <td class="py-3 px-4">${sale.cashier_id || 'N/A'}</td>
                            <td class="py-3 px-4 text-sm text-gray-500">${sale.timestamp ? new Date(sale.timestamp).toLocaleDateString() : 'N/A'}</td>
                        </tr>
                    `;
                })).then(rows => rows.join(''));
            } else {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center py-8 text-gray-500" data-translate>No sales found</td></tr>';
            }
            
            displayPagination('salesPagination', result.pagination, loadSales);
        }
    } catch (error) {
        console.error('Error loading sales:', error);
    }
}

// Load sales by cashier
async function loadSalesByCashier() {
    try {
        const response = await fetch(`/admin/api/business/${userId}/sales-by-cashier`, {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status) {
            const tbody = document.getElementById('salesByCashierTableBody');
            const currency = await (window.getCurrentCurrency ? window.getCurrentCurrency() : Promise.resolve('NGN'));
            
            if (result.data.length > 0) {
                tbody.innerHTML = await Promise.all(result.data.map(async item => {
                    const convertedAmount = await (window.convertCurrency ? window.convertCurrency(item.total_sales, 'NGN', currency) : Promise.resolve(item.total_sales));
                    return `
                        <tr class="border-b border-gray-100 hover:bg-gray-50">
                            <td class="py-3 px-4 font-medium">${item.cashier_name || `Cashier ${item.cashier_id}`}</td>
                            <td class="py-3 px-4 font-medium">${window.formatCurrency ? window.formatCurrency(convertedAmount, currency) : `${currency} ${convertedAmount.toFixed(2)}`}</td>
                            <td class="py-3 px-4">${item.total_invoices || 0}</td>
                            <td class="py-3 px-4">
                                <span class="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-700">${item.completed_invoices || 0}</span>
                            </td>
                            <td class="py-3 px-4">
                                <span class="px-2 py-1 text-xs font-medium rounded-full bg-yellow-100 text-yellow-700">${item.pending_invoices || 0}</span>
                            </td>
                        </tr>
                    `;
                })).then(rows => rows.join(''));
            } else {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center py-8 text-gray-500" data-translate>No sales data found</td></tr>';
            }
        }
    } catch (error) {
        console.error('Error loading sales by cashier:', error);
    }
}

// Load AI usage
async function loadAIUsage() {
    try {
        const response = await fetch(`/admin/api/business/${userId}/ai-usage`, {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status && result.data) {
            const data = result.data;
            const usagePercentage = data.ai_usage_percentage || 0;
            
            let html = `
                <div class="space-y-6">
                    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                        <h3 class="text-lg font-semibold text-gray-900 mb-4" data-translate>AI Usage Statistics</h3>
                        <div class="space-y-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-500 mb-1" data-translate>AI Enabled</label>
                                <span class="inline-block px-3 py-1 rounded-full text-sm font-semibold ${
                                    data.ai_enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                                }">
                                    ${data.ai_enabled ? 'Yes' : 'No'}
                                </span>
                            </div>
                            
                            ${data.ai_enabled ? `
                                <div>
                                    <label class="block text-sm font-medium text-gray-500 mb-2" data-translate>Usage Percentage</label>
                                    <div class="w-full bg-gray-200 rounded-full h-8 relative overflow-hidden">
                                        <div class="bg-gradient-to-r from-indigo-500 to-purple-600 h-8 rounded-full flex items-center justify-center text-white text-sm font-semibold transition-all duration-500" 
                                             style="width: ${usagePercentage}%">
                                            ${usagePercentage}%
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div>
                                        <label class="block text-sm font-medium text-gray-500 mb-1" data-translate>Total AI Calls</label>
                                        <p class="text-2xl font-bold text-gray-900">${data.total_ai_calls || 0}</p>
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-500 mb-1" data-translate>AI Calls This Month</label>
                                        <p class="text-2xl font-bold text-gray-900">${data.ai_calls_this_month || 0}</p>
                                    </div>
                                </div>
                            ` : '<p class="text-gray-500" data-translate>AI features are not enabled for this business</p>'}
                        </div>
                    </div>
                </div>
            `;
            
            document.getElementById('aiUsageContent').innerHTML = html;
            
            // Initialize translation if available
            if (window.translatePage) {
                const language = await (window.getCurrentLanguage ? window.getCurrentLanguage() : Promise.resolve('en'));
                if (language && language !== 'en') {
                    await window.translatePage(language);
                }
            }
        }
    } catch (error) {
        console.error('Error loading AI usage:', error);
    }
}

// Pagination helper
function displayPagination(containerId, pagination, loadFunction) {
    const container = document.getElementById(containerId);
    if (!container || !pagination) return;
    
    if (pagination.total_pages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    let html = '<div class="flex items-center justify-between">';
    html += `<div class="text-sm text-gray-700" data-translate>Showing page ${pagination.page} of ${pagination.total_pages} (${pagination.total_count} total)</div>`;
    html += '<div class="flex space-x-2">';
    
    if (pagination.has_previous) {
        html += `<button onclick="${loadFunction.name}(${pagination.page - 1})" class="px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors" data-translate>Previous</button>`;
    }
    
    if (pagination.has_next) {
        html += `<button onclick="${loadFunction.name}(${pagination.page + 1})" class="px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors" data-translate>Next</button>`;
    }
    
    html += '</div></div>';
    container.innerHTML = html;
}

// Debounced search
function debounceSearch(type) {
    if (searchTimeouts[type]) {
        clearTimeout(searchTimeouts[type]);
    }
    
    searchTimeouts[type] = setTimeout(() => {
        switch(type) {
            case 'cashiers':
                loadCashiers(1);
                break;
            case 'managers':
                loadManagers(1);
                break;
            case 'stocks':
                loadStocks(1);
                break;
            case 'sales':
                loadSales(1);
                break;
        }
    }, 500);
}

// Notifications
let currentNotificationTab = 'unread';

function switchNotificationTab(tab) {
    currentNotificationTab = tab;
    const unreadTab = document.getElementById('tabUnread');
    const readTab = document.getElementById('tabRead');
    
    if (tab === 'unread') {
        unreadTab.classList.add('border-indigo-600', 'text-indigo-600', 'bg-indigo-50');
        unreadTab.classList.remove('border-transparent', 'text-gray-500');
        readTab.classList.add('border-transparent', 'text-gray-500');
        readTab.classList.remove('border-indigo-600', 'text-indigo-600', 'bg-indigo-50');
    } else {
        readTab.classList.add('border-indigo-600', 'text-indigo-600', 'bg-indigo-50');
        readTab.classList.remove('border-transparent', 'text-gray-500');
        unreadTab.classList.add('border-transparent', 'text-gray-500');
        unreadTab.classList.remove('border-indigo-600', 'text-indigo-600', 'bg-indigo-50');
    }
    
    loadNotifications();
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

async function markNotificationRead(notificationId) {
    try {
        const response = await fetch('/admin/api/dashboard/notifications/mark-read', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            credentials: 'include',
            body: JSON.stringify({ notification_id: notificationId })
        });
        
        const result = await response.json();
        if (result.status) {
            loadNotifications();
            updateNotificationBadge();
        }
    } catch (error) {
        console.error('Error marking notification as read:', error);
    }
}

async function markAllNotificationsRead() {
    try {
        const response = await fetch('/admin/api/dashboard/notifications/mark-read', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            credentials: 'include',
            body: JSON.stringify({})
        });
        
        const result = await response.json();
        if (result.status) {
            loadNotifications();
            updateNotificationBadge();
        }
    } catch (error) {
        console.error('Error marking all notifications as read:', error);
    }
}

async function updateNotificationBadge() {
    try {
        const response = await fetch('/admin/api/dashboard/notifications?limit=1&filter=unread', {
            credentials: 'include'
        });
        const result = await response.json();
        
        const badge = document.getElementById('notificationBadge');
        const unreadCountBadge = document.getElementById('unreadCount');
        
        if (result.status && result.unread_count > 0) {
            if (badge) badge.classList.remove('hidden');
            if (unreadCountBadge) {
                unreadCountBadge.textContent = result.unread_count;
                unreadCountBadge.classList.remove('hidden');
            }
        } else {
            if (badge) badge.classList.add('hidden');
            if (unreadCountBadge) {
                unreadCountBadge.textContent = '0';
            }
        }
    } catch (error) {
        console.error('Error updating notification badge:', error);
    }
}

async function loadPendingVerificationsCount() {
    try {
        const response = await fetch('/admin/api/dashboard/pending-verifications-count', {
            credentials: 'include'
        });
        const result = await response.json();
        
        const badge = document.getElementById('pendingVerificationsBadge');
        if (result.status && result.count > 0) {
            if (badge) {
                badge.textContent = result.count;
                badge.classList.remove('hidden');
            }
        } else {
            if (badge) {
                badge.classList.add('hidden');
            }
        }
    } catch (error) {
        console.error('Error loading pending verifications count:', error);
    }
}

function toggleNotifications() {
    const overlay = document.getElementById('notificationsOverlay');
    overlay.classList.toggle('hidden');
    
    if (!overlay.classList.contains('hidden')) {
        loadNotifications();
        updateNotificationBadge();
    }
}

async function loadNotifications() {
    try {
        const filter = currentNotificationTab === 'unread' ? 'unread' : 'read';
        const response = await fetch(`/admin/api/dashboard/notifications?limit=50&filter=${filter}`, {
            credentials: 'include'
        });
        const result = await response.json();
        
        const list = document.getElementById('notificationsList');
        const unreadCountBadge = document.getElementById('unreadCount');
        
        if (result.status) {
            // Update unread count badge
            if (unreadCountBadge && result.unread_count !== undefined) {
                unreadCountBadge.textContent = result.unread_count;
                if (result.unread_count === 0) {
                    unreadCountBadge.classList.add('hidden');
                } else {
                    unreadCountBadge.classList.remove('hidden');
                }
            }
            
            if (result.data.length > 0) {
                list.innerHTML = result.data.map(notif => `
                    <div class="p-4 ${notif.is_read ? 'bg-white' : 'bg-blue-50'} rounded-lg border ${notif.is_read ? 'border-gray-200' : 'border-blue-200'} hover:bg-gray-100 transition-colors">
                        <div class="flex items-start justify-between mb-2">
                            <h3 class="text-sm font-medium text-gray-900">${notif.title || 'Notification'}</h3>
                            <div class="flex items-center space-x-2">
                                ${!notif.is_read && !notif.id.toString().startsWith('verification_') ? `<button onclick="markNotificationRead(${notif.id})" class="p-1 text-gray-400 hover:text-indigo-600 rounded" title="Mark as read">
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                                    </svg>
                                </button>` : ''}
                                <span class="px-2 py-1 text-xs font-medium rounded-full ${
                                    notif.type === 'tranc_success' ? 'bg-green-100 text-green-700' :
                                    notif.type === 'tranc_error' ? 'bg-red-100 text-red-700' :
                                    notif.type === 'verification' ? 'bg-blue-100 text-blue-700' :
                                    'bg-indigo-100 text-indigo-700'
                                }">${notif.type}</span>
                            </div>
                        </div>
                        <p class="text-sm text-gray-600 mb-2">${notif.description || ''}</p>
                        <p class="text-xs text-gray-400">${formatDate(notif.timestamp)}</p>
                    </div>
                `).join('');
            } else {
                list.innerHTML = `<div class="text-center py-8 text-gray-500" data-translate>No ${currentNotificationTab} notifications</div>`;
            }
        } else {
            list.innerHTML = '<div class="text-center py-8 text-gray-500" data-translate>Error loading notifications</div>';
        }
    } catch (error) {
        console.error('Error loading notifications:', error);
        document.getElementById('notificationsList').innerHTML = '<div class="text-center py-8 text-red-500" data-translate>Error loading notifications</div>';
    }
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function logout() {
    Swal.fire({
        title: 'Logout?',
        text: 'Are you sure you want to logout?',
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#4f46e5',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Yes, logout'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch('/admin/api/logout', {
                method: 'POST',
                credentials: 'include'
            }).then(() => {
                window.location.href = '/admin/login/';
            }).catch(() => {
                window.location.href = '/admin/login/';
            });
        }
    });
}

// Initialize on page load
window.addEventListener('DOMContentLoaded', async () => {
    // Initialize notifications
    updateNotificationBadge();
    loadPendingVerificationsCount();
    
    // Re-extract userId in case it wasn't set correctly
    if (!userId) {
        const pathParts = window.location.pathname.split('/').filter(p => p);
        const usersIndex = pathParts.indexOf('users');
        if (usersIndex !== -1 && pathParts[usersIndex + 1]) {
            userId = pathParts[usersIndex + 1];
        }
    }
    
    if (!userId) {
        const loadingState = document.getElementById('loadingState');
        const errorState = document.getElementById('errorState');
        if (loadingState) loadingState.classList.add('hidden');
        if (errorState) {
            errorState.classList.remove('hidden');
            document.getElementById('errorMessage').textContent = 'Invalid user ID';
        }
        return;
    }
    
    // Load overview by default
    switchTab('overview');
    
    // Initialize localization
    if (window.initializeAdminLocalization) {
        await window.initializeAdminLocalization();
    }
});

// Close notifications overlay on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const overlay = document.getElementById('notificationsOverlay');
        if (overlay && !overlay.classList.contains('hidden')) {
            toggleNotifications();
        }
    }
});

