let currentPage = 1;
let currentSearch = '';
let currentStatus = '';
let perPage = 20;

async function loadVerifications(page = 1, search = '', status = '') {
    currentPage = page;
    currentSearch = search;
    currentStatus = status;
    
    const tbody = document.getElementById('verificationsTableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-12 text-center text-gray-500">Loading...</td></tr>';
    
    try {
        let url = `/admin/api/verifications?page=${page}&per_page=${perPage}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;
        
        const response = await fetch(url, {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status) {
            displayVerifications(result.data);
            displayPagination(result.pagination);
        } else {
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-12 text-center text-red-500">Error loading verifications</td></tr>';
        }
    } catch (error) {
        console.error('Error loading verifications:', error);
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-12 text-center text-red-500">Error loading verifications</td></tr>';
    }
}

function displayVerifications(verifications) {
    const tbody = document.getElementById('verificationsTableBody');
    
    if (verifications.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-12 text-center text-gray-500">No verifications found</td></tr>';
        return;
    }
    
    tbody.innerHTML = verifications.map(ver => {
        // Ensure verification_status is a string and handle edge cases
        const status = String(ver.verification_status || '0');
        const statusBadge = status === '1' 
            ? '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">Approved</span>'
            : status === '2'
            ? '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">Rejected</span>'
            : '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800">Pending</span>';
        
        return `
            <tr onclick="viewVerificationDetails(${ver.id})" class="hover:bg-gray-50 transition-colors cursor-pointer" data-verification-id="${ver.id}">
                <td class="px-6 py-4 whitespace-nowrap">
                    <div>
                        <div class="text-sm font-medium text-gray-900">${ver.user_email || ver.user_id}</div>
                        <div class="text-xs text-gray-500">${ver.user_id}</div>
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm text-gray-900">${ver.verification_type || '-'}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm text-gray-900">${ver.account_type || '-'}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    ${statusBadge}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm text-gray-600">${formatDate(ver.timestamp)}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium" onclick="event.stopPropagation()">
                    ${status === '0' ? `
                        <div class="flex items-center space-x-2">
                            <button onclick="event.stopPropagation(); updateVerificationStatus(${ver.id}, '1')" 
                                    class="text-green-600 hover:text-green-900">
                                Approve
                            </button>
                            <span class="text-gray-300">|</span>
                            <button onclick="event.stopPropagation(); updateVerificationStatus(${ver.id}, '2')" 
                                    class="text-red-600 hover:text-red-900">
                                Reject
                            </button>
                        </div>
                    ` : '-'}
                </td>
            </tr>
        `;
    }).join('');
}

function displayPagination(pagination) {
    const paginationDiv = document.getElementById('pagination');
    
    if (!pagination || pagination.total_pages <= 1) {
        paginationDiv.innerHTML = '';
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
                onclick="loadVerifications(${pagination.current_page - 1}, '${currentSearch}', '${currentStatus}')"
                ${!pagination.has_previous ? 'disabled' : ''}
                class="px-4 py-2 border border-gray-300 rounded-lg ${pagination.has_previous ? 'hover:bg-gray-50 text-gray-700' : 'opacity-50 cursor-not-allowed text-gray-400'}"
            >
                Previous
            </button>
            
            ${pages.map(page => `
                <button 
                    onclick="loadVerifications(${page}, '${currentSearch}', '${currentStatus}')"
                    class="px-4 py-2 border rounded-lg ${page === pagination.current_page ? 'bg-indigo-600 text-white border-indigo-600' : 'border-gray-300 text-gray-700 hover:bg-gray-50'}"
                >
                    ${page}
                </button>
            `).join('')}
            
            <button 
                onclick="loadVerifications(${pagination.current_page + 1}, '${currentSearch}', '${currentStatus}')"
                ${!pagination.has_next ? 'disabled' : ''}
                class="px-4 py-2 border border-gray-300 rounded-lg ${pagination.has_next ? 'hover:bg-gray-50 text-gray-700' : 'opacity-50 cursor-not-allowed text-gray-400'}"
            >
                Next
            </button>
        </div>
        
        <div class="text-sm text-gray-600">
            Showing ${(pagination.current_page - 1) * pagination.per_page + 1} to ${Math.min(pagination.current_page * pagination.per_page, pagination.total_items)} of ${pagination.total_items} verifications
        </div>
    `;
}

// Debounce function for search input
let searchTimeout;
function debounceSearch(func, delay = 500) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(func, delay);
}

function searchVerifications() {
    const searchInput = document.getElementById('searchInput');
    const statusFilter = document.getElementById('statusFilter');
    loadVerifications(1, searchInput.value, statusFilter.value);
}

function resetSearch() {
    document.getElementById('searchInput').value = '';
    document.getElementById('statusFilter').value = '';
    loadVerifications(1, '', '');
}

// Add real-time search and filter
function setupRealTimeSearch() {
    const searchInput = document.getElementById('searchInput');
    const statusFilter = document.getElementById('statusFilter');
    
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            debounceSearch(() => {
                loadVerifications(1, e.target.value, statusFilter ? statusFilter.value : '');
            }, 500);
        });
    }
    
    if (statusFilter) {
        statusFilter.addEventListener('change', (e) => {
            loadVerifications(1, searchInput ? searchInput.value : '', e.target.value);
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

function showVerificationActionModal(verification) {
    const modalContent = `
        <div class="max-w-3xl mx-auto bg-white rounded-lg shadow-xl">
            <div class="p-6 border-b border-gray-200">
                <div class="flex items-center justify-between">
                    <h2 class="text-2xl font-bold text-gray-900">Review Verification</h2>
                    <button onclick="closeVerificationModal()" class="text-gray-400 hover:text-gray-600">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
            </div>
            
            <div class="p-6 overflow-y-auto max-h-[80vh]">
                <!-- Verification Details Summary -->
                <div class="mb-6 p-4 bg-gray-50 rounded-lg">
                    <h3 class="text-lg font-semibold text-gray-900 mb-3">Verification Information</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">User</label>
                            <p class="text-sm text-gray-900">${verification.user_email || verification.user_id || '-'}</p>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Account Type</label>
                            <p class="text-sm text-gray-900">${verification.account_type || '-'}</p>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Verification Type</label>
                            <p class="text-sm text-gray-900">${verification.verification_type || '-'}</p>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Date Submitted</label>
                            <p class="text-sm text-gray-900">${formatDate(verification.timestamp)}</p>
                        </div>
                    </div>
                </div>
                
                <!-- Action Form -->
                <form id="verificationActionForm" onsubmit="handleVerificationAction(event, ${verification.id})">
                    <div class="mb-6">
                        <label for="verificationReason" class="block text-sm font-medium text-gray-700 mb-2">
                            Reason (Optional)
                        </label>
                        <textarea 
                            id="verificationReason" 
                            name="reason"
                            rows="4" 
                            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none resize-none"
                            placeholder="Enter reason for approval or rejection (optional)"
                        ></textarea>
                    </div>
                    
                    <div class="flex items-center justify-end space-x-3 pt-6 border-t border-gray-200">
                        <button 
                            type="button"
                            onclick="closeVerificationModal()" 
                            class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition-colors">
                            Cancel
                        </button>
                        <button 
                            type="button"
                            onclick="handleVerificationAction(null, ${verification.id}, '2')" 
                            class="px-4 py-2 bg-red-100 text-red-700 rounded-lg font-medium hover:bg-red-200 transition-colors">
                            Decline
                        </button>
                        <button 
                            type="button"
                            onclick="handleVerificationAction(null, ${verification.id}, '1')" 
                            class="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors">
                            Approve
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    // Create modal overlay
    const modalOverlay = document.createElement('div');
    modalOverlay.id = 'verificationModalOverlay';
    modalOverlay.className = 'fixed inset-0 z-50 overflow-y-auto bg-black bg-opacity-50 flex items-center justify-center p-4';
    modalOverlay.innerHTML = modalContent;
    modalOverlay.onclick = function(e) {
        if (e.target === modalOverlay) {
            closeVerificationModal();
        }
    };
    
    document.body.appendChild(modalOverlay);
    document.body.style.overflow = 'hidden';
}

async function handleVerificationAction(event, verificationId, status) {
    if (event) {
        event.preventDefault();
    }
    
    if (!status) {
        return;
    }
    
    const reason = document.getElementById('verificationReason')?.value || '';
    const action = status === '1' ? 'approve' : 'decline';
    
    try {
        const response = await fetch(`/admin/api/verifications/${verificationId}/update`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            credentials: 'include',
            body: JSON.stringify({ 
                verification_status: status,
                reason: reason
            })
        });
        
        const result = await response.json();
        
        if (result.status) {
            closeVerificationModal();
            Swal.fire({
                icon: 'success',
                title: 'Success!',
                text: `Verification ${action}d successfully`,
                confirmButtonColor: '#4f46e5',
                timer: 2000,
                showConfirmButton: false
            });
            loadVerifications(currentPage, currentSearch, currentStatus);
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.message || 'Failed to update verification status',
                confirmButtonColor: '#4f46e5'
            });
        }
    } catch (error) {
        console.error('Error updating verification status:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'An error occurred. Please try again.',
            confirmButtonColor: '#4f46e5'
        });
    }
}

async function updateVerificationStatus(verificationId, status) {
    // This function is kept for backward compatibility but now uses the new modal
    const verification = await fetch(`/admin/api/verifications/${verificationId}`, {
        credentials: 'include'
    }).then(r => r.json());
    
    if (verification.status) {
        showVerificationActionModal(verification.data);
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

async function viewVerificationDetails(verificationId) {
    if (!verificationId) {
        console.error('Verification ID is required');
        return;
    }
    
    try {
        const response = await fetch(`/admin/api/verifications/${verificationId}`, {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status) {
            showVerificationModal(result.data);
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.message || 'Failed to load verification details',
                confirmButtonColor: '#4f46e5'
            });
        }
    } catch (error) {
        console.error('Error loading verification details:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'An error occurred. Please try again.',
            confirmButtonColor: '#4f46e5'
        });
    }
}

function showVerificationModal(verification) {
    const statusLabels = {
        '0': { text: 'Pending', class: 'bg-yellow-100 text-yellow-800' },
        '1': { text: 'Approved', class: 'bg-green-100 text-green-800' },
        '2': { text: 'Rejected', class: 'bg-red-100 text-red-800' }
    };
    
    const status = statusLabels[verification.verification_status] || statusLabels['0'];
    const isPending = verification.verification_status === '0';
    
    // For pending verifications, show approve/decline form
    if (isPending) {
        showVerificationActionModal(verification);
        return;
    }
    
    // For approved/rejected, show details
    const modalContent = `
        <div class="max-w-4xl mx-auto bg-white rounded-lg shadow-xl">
            <div class="p-6 border-b border-gray-200">
                <div class="flex items-center justify-between">
                    <h2 class="text-2xl font-bold text-gray-900">Verification Details</h2>
                    <button onclick="closeVerificationModal()" class="text-gray-400 hover:text-gray-600">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
            </div>
            
            <div class="p-6 overflow-y-auto max-h-[80vh]">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">User ID</label>
                        <p class="text-sm text-gray-900">${verification.user_id || '-'}</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">User Email</label>
                        <p class="text-sm text-gray-900">${verification.user_email || '-'}</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Verification Type</label>
                        <p class="text-sm text-gray-900">${verification.verification_type || '-'}</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Verification ID</label>
                        <p class="text-sm text-gray-900">${verification.verification_id || '-'}</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Account Type</label>
                        <p class="text-sm text-gray-900">${verification.account_type || '-'}</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Status</label>
                        <span class="px-2 py-1 text-xs font-semibold rounded-full ${status.class}">${status.text}</span>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Legal ID</label>
                        <p class="text-sm text-gray-900">${verification.legal_id || '-'}</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Date Submitted</label>
                        <p class="text-sm text-gray-900">${formatDate(verification.timestamp)}</p>
                    </div>
                    ${verification.user_address ? `
                    <div class="md:col-span-2">
                        <label class="block text-sm font-medium text-gray-700 mb-1">Address</label>
                        <p class="text-sm text-gray-900">${verification.user_address}</p>
                    </div>
                    ` : ''}
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                    ${verification.user_image ? `
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">User Image</label>
                        <div class="border border-gray-200 rounded-lg overflow-hidden">
                            <img src="${verification.user_image}" alt="User Image" class="w-full h-auto cursor-pointer hover:opacity-90" onclick="window.open('${verification.user_image}', '_blank')">
                        </div>
                    </div>
                    ` : ''}
                    ${verification.driver_licence ? `
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Driver's Licence</label>
                        <div class="border border-gray-200 rounded-lg overflow-hidden">
                            <img src="${verification.driver_licence}" alt="Driver's Licence" class="w-full h-auto cursor-pointer hover:opacity-90" onclick="window.open('${verification.driver_licence}', '_blank')">
                        </div>
                    </div>
                    ` : ''}
                    ${verification.proof_of_address ? `
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Proof of Address</label>
                        <div class="border border-gray-200 rounded-lg overflow-hidden">
                            <img src="${verification.proof_of_address}" alt="Proof of Address" class="w-full h-auto cursor-pointer hover:opacity-90" onclick="window.open('${verification.proof_of_address}', '_blank')">
                        </div>
                    </div>
                    ` : ''}
                    ${verification.user_video ? `
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">User Video</label>
                        <div class="border border-gray-200 rounded-lg overflow-hidden">
                            <video controls class="w-full" src="${verification.user_video}"></video>
                        </div>
                    </div>
                    ` : ''}
                </div>
                
                ${verification.reason ? `
                <div class="mt-6 pt-6 border-t border-gray-200">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Reason</label>
                    <p class="text-sm text-gray-900 bg-gray-50 p-3 rounded-lg">${verification.reason}</p>
                </div>
                ` : ''}
            </div>
        </div>
    `;
    
    // Create modal overlay
    const modalOverlay = document.createElement('div');
    modalOverlay.id = 'verificationModalOverlay';
    modalOverlay.className = 'fixed inset-0 z-50 overflow-y-auto bg-black bg-opacity-50 flex items-center justify-center p-4';
    modalOverlay.innerHTML = modalContent;
    modalOverlay.onclick = function(e) {
        if (e.target === modalOverlay) {
            closeVerificationModal();
        }
    };
    
    document.body.appendChild(modalOverlay);
    document.body.style.overflow = 'hidden';
}

function closeVerificationModal() {
    const modal = document.getElementById('verificationModalOverlay');
    if (modal) {
        modal.remove();
        document.body.style.overflow = '';
    }
}

// Make functions globally accessible
window.viewVerificationDetails = viewVerificationDetails;
window.closeVerificationModal = closeVerificationModal;
window.showVerificationModal = showVerificationModal;
window.showVerificationActionModal = showVerificationActionModal;
window.handleVerificationAction = handleVerificationAction;

