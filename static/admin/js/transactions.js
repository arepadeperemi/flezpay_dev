let currentPage = 1;
let currentSearch = '';
let currentType = '';
let currentStatus = '';
let perPage = 20;

async function loadTransactions(page = 1, search = '', type = '', status = '') {
    currentPage = page;
    currentSearch = search;
    currentType = type;
    currentStatus = status;
    
    const tbody = document.getElementById('transactionsTableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-12 text-center text-gray-500">Loading...</td></tr>';
    
    try {
        let url = `/admin/api/transactions?page=${page}&per_page=${perPage}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (type) url += `&type=${encodeURIComponent(type)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;
        
        const response = await fetch(url, {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status) {
            displayTransactions(result.data);
            displayPagination(result.pagination);
        } else {
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-12 text-center text-red-500">Error loading transactions</td></tr>';
        }
    } catch (error) {
        console.error('Error loading transactions:', error);
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-12 text-center text-red-500">Error loading transactions</td></tr>';
    }
}

function displayTransactions(transactions) {
    const tbody = document.getElementById('transactionsTableBody');
    
    if (transactions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-12 text-center text-gray-500">No transactions found</td></tr>';
        return;
    }
    
    tbody.innerHTML = transactions.map(trx => {
        const typeBadge = trx.type === 'credit' 
            ? '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">Credit</span>'
            : trx.type === 'withdrawal'
            ? '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">Withdrawal</span>'
            : '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800">' + trx.type + '</span>';
        
        const statusBadge = trx.status === 'completed' 
            ? '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">Completed</span>'
            : trx.status === 'pending'
            ? '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800">Pending</span>'
            : '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">Failed</span>';
        
        return `
            <tr class="hover:bg-gray-50 transition-colors">
                <td class="px-6 py-4 whitespace-nowrap">
                    <div>
                        <div class="text-sm font-medium text-gray-900">${trx.user_email || trx.user_id}</div>
                        <div class="text-xs text-gray-500">${trx.user_id}</div>
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    ${typeBadge}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm font-medium text-gray-900">${formatCurrency(trx.amount)} ${trx.currency}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    ${statusBadge}
                </td>
                <td class="px-6 py-4 max-w-xs sm:max-w-sm">
                    <div class="text-sm text-gray-600 truncate" title="${(trx.description || '').replace(/"/g, '&quot;')}">${trx.description || '-'}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm text-gray-600">${formatDate(trx.timestamp)}</div>
                </td>
            </tr>
        `;
    }).join('');
}

function displayPagination(pagination) {
    const paginationDiv = document.getElementById('pagination');
    
    if (!pagination) {
        paginationDiv.innerHTML = '';
        return;
    }
    
    // Always show pagination info, even if only one page
    if (pagination.total_pages <= 1) {
        paginationDiv.innerHTML = `
            <div class="text-sm text-gray-600">
                Showing ${pagination.total_items} of ${pagination.total_items} transactions
            </div>
        `;
        return;
    }
    
    const pages = [];
    const maxPages = 5;
    let startPage = Math.max(1, pagination.current_page - Math.floor(maxPages / 2));
    let endPage = Math.min(pagination.total_pages, startPage + maxPages - 1);
    
    if (endPage - startPage < maxPages - 1) {
        startPage = Math.max(1, endPage - maxPages + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        pages.push(i);
    }
    
    paginationDiv.innerHTML = `
        <div class="flex items-center space-x-2">
            <button 
                onclick="loadTransactions(${pagination.current_page - 1}, '${currentSearch}', '${currentType}', '${currentStatus}')"
                ${!pagination.has_previous ? 'disabled' : ''}
                class="px-4 py-2 border border-gray-300 rounded-lg ${pagination.has_previous ? 'hover:bg-gray-50 text-gray-700' : 'opacity-50 cursor-not-allowed text-gray-400'}"
            >
                Previous
            </button>
            
            ${pages.map(page => `
                <button 
                    onclick="loadTransactions(${page}, '${currentSearch}', '${currentType}', '${currentStatus}')"
                    class="px-4 py-2 border rounded-lg ${page === pagination.current_page ? 'bg-indigo-600 text-white border-indigo-600' : 'border-gray-300 text-gray-700 hover:bg-gray-50'}"
                >
                    ${page}
                </button>
            `).join('')}
            
            <button 
                onclick="loadTransactions(${pagination.current_page + 1}, '${currentSearch}', '${currentType}', '${currentStatus}')"
                ${!pagination.has_next ? 'disabled' : ''}
                class="px-4 py-2 border border-gray-300 rounded-lg ${pagination.has_next ? 'hover:bg-gray-50 text-gray-700' : 'opacity-50 cursor-not-allowed text-gray-400'}"
            >
                Next
            </button>
        </div>
        
        <div class="text-sm text-gray-600">
            Showing ${(pagination.current_page - 1) * pagination.per_page + 1} to ${Math.min(pagination.current_page * pagination.per_page, pagination.total_items)} of ${pagination.total_items} transactions
        </div>
    `;
}

// Debounce function for search input
let searchTimeout;
function debounceSearch(func, delay = 500) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(func, delay);
}

function searchTransactions() {
    const searchInput = document.getElementById('searchInput');
    const typeFilter = document.getElementById('typeFilter');
    const statusFilter = document.getElementById('statusFilter');
    loadTransactions(1, searchInput.value, typeFilter.value, statusFilter.value);
}

function resetSearch() {
    document.getElementById('searchInput').value = '';
    document.getElementById('typeFilter').value = '';
    document.getElementById('statusFilter').value = '';
    loadTransactions(1, '', '', '');
}

// Add real-time search and filter
function setupRealTimeSearch() {
    const searchInput = document.getElementById('searchInput');
    const typeFilter = document.getElementById('typeFilter');
    const statusFilter = document.getElementById('statusFilter');
    
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            debounceSearch(() => {
                loadTransactions(1, e.target.value, typeFilter ? typeFilter.value : '', statusFilter ? statusFilter.value : '');
            }, 500);
        });
    }
    
    if (typeFilter) {
        typeFilter.addEventListener('change', (e) => {
            loadTransactions(1, searchInput ? searchInput.value : '', e.target.value, statusFilter ? statusFilter.value : '');
        });
    }
    
    if (statusFilter) {
        statusFilter.addEventListener('change', (e) => {
            loadTransactions(1, searchInput ? searchInput.value : '', typeFilter ? typeFilter.value : '', e.target.value);
        });
    }
}

// Initialize real-time search on page load
function initRealTimeSearch() {
    // Wait a bit to ensure DOM is fully ready
    setTimeout(() => {
        setupRealTimeSearch();
    }, 100);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRealTimeSearch);
} else {
    initRealTimeSearch();
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-NG', {
        style: 'currency',
        currency: 'NGN',
        minimumFractionDigits: 2
    }).format(amount);
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

