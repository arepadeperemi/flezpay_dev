let currentPage = 1;
let selectedUsers = new Set();
let currentSearch = '';
let perPage = 10;

async function loadUsers(page = 1, search = '') {
    currentPage = page;
    currentSearch = search;
    
    const tbody = document.getElementById('usersTableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-12 text-center text-gray-500">Loading...</td></tr>';
    
    try {
        const url = `/admin/api/users?page=${page}&per_page=${perPage}${search ? `&search=${encodeURIComponent(search)}` : ''}`;
        const response = await fetch(url, {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status) {
            displayUsers(result.data);
            displayPagination(result.pagination);
        } else {
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-12 text-center text-red-500">Error loading users</td></tr>';
        }
    } catch (error) {
        console.error('Error loading users:', error);
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-12 text-center text-red-500">Error loading users</td></tr>';
    }
}

function displayUsers(users) {
    const tbody = document.getElementById('usersTableBody');
    
    if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="px-6 py-12 text-center text-gray-500">No users found</td></tr>';
        return;
    }
    
    // Update select all checkbox
    const selectAll = document.getElementById('selectAllCheckbox');
    if (selectAll) {
        selectAll.checked = users.length > 0 && users.every(u => selectedUsers.has(String(u.id)));
    }
    
    tbody.innerHTML = users.map(user => `
        <tr class="hover:bg-indigo-50 transition-colors">
            <td class="px-6 py-4 whitespace-nowrap">
                <input type="checkbox" value="${user.id}" 
                       ${selectedUsers.has(String(user.id)) ? 'checked' : ''}
                       onclick="toggleUserSelection(this, '${user.id}')"
                       class="user-checkbox rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer">
            </td>
            <td class="px-6 py-4 whitespace-nowrap cursor-pointer" onclick="viewUserDetails('${user.id}')">
                <div class="text-sm font-medium text-gray-900">${user.id}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap cursor-pointer" onclick="viewUserDetails('${user.id}')">
                <div class="text-sm text-gray-900">${user.first_name || ''} ${user.last_name || ''}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap cursor-pointer" onclick="viewUserDetails('${user.id}')">
                <div class="text-sm text-gray-900">${user.email || '-'}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap cursor-pointer" onclick="viewUserDetails('${user.id}')">
                <div class="text-sm text-gray-900">${user.phone || '-'}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap cursor-pointer" onclick="viewUserDetails('${user.id}')">
                <span class="px-2 py-1 text-xs font-semibold rounded-full ${user.account_type === 'business' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'}">
                    ${user.account_type || 'N/A'}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap cursor-pointer" onclick="viewUserDetails('${user.id}')">
                <div class="flex items-center space-x-2">
                    <span class="px-2 py-1 text-xs font-semibold rounded-full ${user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                        ${user.is_active ? 'Active' : 'Inactive'}
                    </span>
                    ${user.is_verified ? '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-indigo-100 text-indigo-800">Verified</span>' : ''}
                </div>
            </td>
        </tr>
    `).join('');
    
    // Refresh checkboxes if selection changed
    updateDeleteButton();
}

function toggleUserSelection(checkbox, userId) {
    if (event) {
        event.stopPropagation();
    }
    userId = String(userId);
    if (checkbox.checked) {
        selectedUsers.add(userId);
    } else {
        selectedUsers.delete(userId);
    }
    
    // Update select all state
    const checkboxes = document.querySelectorAll('.user-checkbox');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    const selectAll = document.getElementById('selectAllCheckbox');
    if (selectAll) {
        selectAll.checked = checkboxes.length > 0 && allChecked;
    }
    
    updateDeleteButton();
}

function toggleAllUsers(selectAllCheckbox) {
    const checkboxes = document.querySelectorAll('.user-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = selectAllCheckbox.checked;
        const userId = String(cb.value);
        if (selectAllCheckbox.checked) {
            selectedUsers.add(userId);
        } else {
            selectedUsers.delete(userId);
        }
    });
    updateDeleteButton();
}

function updateDeleteButton() {
    const btn = document.getElementById('deleteSelectedBtn');
    const count = document.getElementById('selectedCount');
    if (btn && count) {
        count.textContent = selectedUsers.size;
        if (selectedUsers.size > 0) {
            btn.classList.remove('hidden');
        } else {
            btn.classList.add('hidden');
        }
    }
}

async function deleteSelectedUsers() {
    if (selectedUsers.size === 0) return;
    
    const result = await Swal.fire({
        title: 'Delete Selected Users?',
        text: `Are you sure you want to permanently delete ${selectedUsers.size} user(s)? This action cannot be undone.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Yes, delete users'
    });
    
    if (!result.isConfirmed) {
        return;
    }
    
    try {
        const response = await fetch('/admin/api/users/delete-batch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            credentials: 'include',
            body: JSON.stringify({ user_ids: Array.from(selectedUsers) })
        });
        
        const result = await response.json();
        
        if (result.status) {
            await Swal.fire({
                icon: 'success',
                title: 'Deleted!',
                text: result.message || 'Users deleted successfully!',
                confirmButtonColor: '#4f46e5',
                timer: 2000,
                showConfirmButton: false
            });
            selectedUsers.clear();
            const selectAll = document.getElementById('selectAllCheckbox');
            if (selectAll) selectAll.checked = false;
            updateDeleteButton();
            loadUsers(currentPage, currentSearch);
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.message || 'Failed to delete users',
                confirmButtonColor: '#4f46e5'
            });
        }
    } catch (error) {
        console.error('Error deleting users:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'An error occurred. Please try again.',
            confirmButtonColor: '#4f46e5'
        });
    }
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
                onclick="loadUsers(${pagination.current_page - 1}, '${currentSearch}')"
                ${!pagination.has_previous ? 'disabled' : ''}
                class="px-4 py-2 border border-gray-300 rounded-lg ${pagination.has_previous ? 'hover:bg-gray-50 text-gray-700' : 'opacity-50 cursor-not-allowed text-gray-400'}"
            >
                Previous
            </button>
            
            ${pages.map(page => `
                <button 
                    onclick="loadUsers(${page}, '${currentSearch}')"
                    class="px-4 py-2 border rounded-lg ${page === pagination.current_page ? 'bg-indigo-600 text-white border-indigo-600' : 'border-gray-300 text-gray-700 hover:bg-gray-50'}"
                >
                    ${page}
                </button>
            `).join('')}
            
            <button 
                onclick="loadUsers(${pagination.current_page + 1}, '${currentSearch}')"
                ${!pagination.has_next ? 'disabled' : ''}
                class="px-4 py-2 border border-gray-300 rounded-lg ${pagination.has_next ? 'hover:bg-gray-50 text-gray-700' : 'opacity-50 cursor-not-allowed text-gray-400'}"
            >
                Next
            </button>
        </div>
        
        <div class="text-sm text-gray-600">
            Showing ${(pagination.current_page - 1) * pagination.per_page + 1} to ${Math.min(pagination.current_page * pagination.per_page, pagination.total_items)} of ${pagination.total_items} users
        </div>
    `;
}

// Debounce function for search input
let searchTimeout;
function debounceSearch(func, delay = 500) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(func, delay);
}

function searchUsers() {
    const searchInput = document.getElementById('searchInput');
    loadUsers(1, searchInput.value);
}

function resetSearch() {
    document.getElementById('searchInput').value = '';
    loadUsers(1, '');
}

// Add real-time search on input
function setupRealTimeSearch() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            debounceSearch(() => {
                loadUsers(1, e.target.value);
            }, 500);
        });
    }
}

async function toggleUserStatus(userId, isActive) {
    const result = await Swal.fire({
        title: `${isActive ? 'Activate' : 'Deactivate'} User?`,
        text: `Are you sure you want to ${isActive ? 'activate' : 'deactivate'} this user?`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#4f46e5',
        cancelButtonColor: '#6b7280',
        confirmButtonText: `Yes, ${isActive ? 'activate' : 'deactivate'}`
    });
    
    if (!result.isConfirmed) {
        return;
    }
    
    try {
        const response = await fetch(`/admin/api/users/${userId}/update`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            credentials: 'include',
            body: JSON.stringify({ is_active: isActive })
        });
        
        const result = await response.json();
        
        if (result.status) {
            Swal.fire({
                icon: 'success',
                title: 'Success!',
                text: 'User status updated successfully',
                confirmButtonColor: '#4f46e5',
                timer: 2000,
                showConfirmButton: false
            });
            loadUsers(currentPage, currentSearch);
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.message || 'Failed to update user status',
                confirmButtonColor: '#4f46e5'
            });
        }
    } catch (error) {
        console.error('Error updating user status:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'An error occurred. Please try again.',
            confirmButtonColor: '#4f46e5'
        });
    }
}

function viewUserDetails(userId) {
    // Prevent event bubbling if called from a button
    if (event) {
        event.stopPropagation();
    }
    window.location.href = `/admin/users/${userId}/`;
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

