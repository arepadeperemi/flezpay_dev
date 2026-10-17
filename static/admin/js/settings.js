async function loadAssets() {
    const assetsList = document.getElementById('assetsList');
    assetsList.innerHTML = '<div class="p-6 text-center text-gray-500">Loading assets...</div>';
    
    try {
        const response = await fetch('/admin/api/crypto-assets', {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status) {
            displayAssets(result.data);
        } else {
            assetsList.innerHTML = '<div class="p-6 text-center text-red-500">Error loading assets</div>';
        }
    } catch (error) {
        console.error('Error loading assets:', error);
        assetsList.innerHTML = '<div class="p-6 text-center text-red-500">Error loading assets</div>';
    }
}

function displayAssets(assets) {
    const assetsList = document.getElementById('assetsList');
    
    if (assets.length === 0) {
        assetsList.innerHTML = '<div class="p-6 text-center text-gray-500">No crypto assets found. Add your first asset above.</div>';
        return;
    }
    
    assetsList.innerHTML = assets.map(asset => `
        <div class="border border-gray-200 rounded-lg overflow-hidden mb-4">
            <!-- Accordion Header -->
            <div class="flex items-center bg-white hover:bg-gray-50 transition-colors">
                <button onclick="toggleAccordion('asset-${asset.id}')" 
                        class="flex-1 flex items-center p-6 text-left relative">
                    <div class="flex items-center space-x-4 flex-1">
                        ${asset.icon ? `<img src="${asset.icon}" alt="${asset.name}" class="w-12 h-12 rounded-full">` : '<div class="w-12 h-12 bg-gray-200 rounded-full flex items-center justify-center"><span class="text-gray-500 text-xs">No Icon</span></div>'}
                        <div class="flex-1">
                            <h3 class="text-lg font-semibold text-gray-900">${asset.name}</h3>
                            <p class="text-sm text-gray-500">ID: ${asset.asset_id} • ${asset.chains.length} Network${asset.chains.length !== 1 ? 's' : ''}</p>
                        </div>
                    </div>
                </button>
                <div class="flex items-center space-x-2 pr-6">
                    <button onclick="event.stopPropagation(); showAddChainModal(${asset.id})" 
                            class="p-2 text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                            title="Add Network">
                        <img src="/static/assets/icons/add-asset.svg" alt="Add Network" class="w-5 h-5">
                    </button>
                    <button onclick="event.stopPropagation(); deleteAsset(${asset.id})" 
                            class="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            title="Delete Asset">
                        <img src="/static/assets/icons/delete-network.svg" alt="Delete Asset" class="w-5 h-5">
                    </button>
                </div>
            </div>
            
            <!-- Accordion Content -->
            <div id="asset-${asset.id}" class="hidden border-t border-gray-200 bg-gray-50">
                <div class="p-6">
                    ${asset.chains.length > 0 ? `
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            ${asset.chains.map(chain => `
                                <div class="border border-gray-200 rounded-lg p-4 bg-white hover:border-indigo-300 transition-colors">
                                    <div class="flex items-center justify-between mb-2">
                                        <div class="flex items-center space-x-2">
                                            ${chain.icon ? `<img src="${chain.icon}" alt="${chain.name}" class="w-8 h-8 rounded-full">` : '<div class="w-8 h-8 bg-gray-200 rounded-full"></div>'}
                                            <div>
                                                <p class="text-sm font-medium text-gray-900">${chain.name}</p>
                                                <p class="text-xs text-gray-500">${chain.chain_id}</p>
                                            </div>
                                        </div>
                                        <button onclick="deleteChain(${chain.id})" 
                                                class="text-red-600 hover:text-red-800 text-sm font-bold">
                                            ×
                                        </button>
                                    </div>
                                    ${chain.description ? `<p class="text-xs text-gray-600 mt-2">${chain.description}</p>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : `
                        <div class="text-center py-8">
                            <svg class="w-12 h-12 text-gray-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                            </svg>
                            <p class="text-sm text-gray-500 mb-4">No networks added yet</p>
                            <button onclick="showAddChainModal(${asset.id})" 
                                    class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-medium">
                                Add First Network
                            </button>
                        </div>
                    `}
                </div>
            </div>
        </div>
    `).join('');
}

// Add Asset Form Handler
document.getElementById('addAssetForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData();
    formData.append('asset_id', document.getElementById('assetId').value);
    formData.append('name', document.getElementById('assetName').value);
    
    const iconFile = document.getElementById('assetIcon').files[0];
    if (iconFile) {
        formData.append('icon', iconFile);
    }
    
    try {
        const response = await fetch('/admin/api/crypto-assets/add', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            credentials: 'include',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.status) {
            Swal.fire({
                icon: 'success',
                title: 'Success!',
                text: 'Crypto asset added successfully!',
                confirmButtonColor: '#4f46e5',
                timer: 2000,
                showConfirmButton: false
            });
            document.getElementById('addAssetForm').reset();
            loadAssets();
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.message || 'Failed to add asset',
                confirmButtonColor: '#4f46e5'
            });
        }
    } catch (error) {
        console.error('Error adding asset:', error);
        alert('An error occurred. Please try again.');
    }
});

function showAddChainModal(assetId) {
    // Call the modal function from the HTML
    if (typeof showAddNetworkModal === 'function') {
        showAddNetworkModal(assetId);
    }
}

async function addChain(assetId, chainId, name, description, iconFile) {
    const formData = new FormData();
    formData.append('asset_id', assetId);
    formData.append('chain_id', chainId);
    formData.append('name', name);
    if (description) {
        formData.append('description', description);
    }
    if (iconFile) {
        formData.append('icon', iconFile);
    }
    
    try {
        const response = await fetch('/admin/api/crypto-chains/add', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            credentials: 'include',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.status) {
            Swal.fire({
                icon: 'success',
                title: 'Success!',
                text: 'Network added successfully!',
                confirmButtonColor: '#4f46e5',
                timer: 2000,
                showConfirmButton: false
            });
            loadAssets();
            // Close modal if it exists
            if (typeof closeAddNetworkModal === 'function') {
                closeAddNetworkModal();
            }
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.message || 'Failed to add network',
                confirmButtonColor: '#4f46e5'
            });
        }
    } catch (error) {
        console.error('Error adding chain:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'An error occurred. Please try again.',
            confirmButtonColor: '#4f46e5'
        });
    }
}

// Handle add network form submission
document.addEventListener('DOMContentLoaded', () => {
    const addNetworkForm = document.getElementById('addNetworkForm');
    if (addNetworkForm) {
        addNetworkForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const assetId = document.getElementById('networkAssetId').value;
            const chainId = document.getElementById('networkChainId').value;
            const name = document.getElementById('networkName').value;
            const description = document.getElementById('networkDescription').value;
            const iconFile = document.getElementById('networkIcon').files[0];
            
            if (!assetId || !chainId || !name) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Required Fields',
                    text: 'Chain ID and Network Name are required',
                    confirmButtonColor: '#4f46e5'
                });
                return;
            }
            
            await addChain(assetId, chainId, name, description, iconFile);
        });
    }
});

async function deleteAsset(assetId) {
    const result = await Swal.fire({
        title: 'Delete Asset?',
        text: 'This will also delete all associated networks. This action cannot be undone.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Yes, delete it'
    });
    
    if (!result.isConfirmed) {
        return;
    }
    
    try {
        const response = await fetch(`/admin/api/crypto-assets/${assetId}/delete`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            credentials: 'include'
        });
        
        const result = await response.json();
        
        if (result.status) {
            Swal.fire({
                icon: 'success',
                title: 'Deleted!',
                text: 'Asset deleted successfully!',
                confirmButtonColor: '#4f46e5',
                timer: 2000,
                showConfirmButton: false
            });
            loadAssets();
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.message || 'Failed to delete asset',
                confirmButtonColor: '#4f46e5'
            });
        }
    } catch (error) {
        console.error('Error deleting asset:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'An error occurred. Please try again.',
            confirmButtonColor: '#4f46e5'
        });
    }
}

async function deleteChain(chainId) {
    const result = await Swal.fire({
        title: 'Delete Network?',
        text: 'Are you sure you want to delete this network?',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Yes, delete it'
    });
    
    if (!result.isConfirmed) {
        return;
    }
    
    try {
        const response = await fetch(`/admin/api/crypto-chains/${chainId}/delete`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            credentials: 'include'
        });
        
        const result = await response.json();
        
        if (result.status) {
            Swal.fire({
                icon: 'success',
                title: 'Deleted!',
                text: 'Network deleted successfully!',
                confirmButtonColor: '#4f46e5',
                timer: 2000,
                showConfirmButton: false
            });
            loadAssets();
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.message || 'Failed to delete network',
                confirmButtonColor: '#4f46e5'
            });
        }
    } catch (error) {
        console.error('Error deleting chain:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'An error occurred. Please try again.',
            confirmButtonColor: '#4f46e5'
        });
    }
}

// Admin User Management Functions
let currentAdminId = null;

async function loadAdmins() {
    const adminsList = document.getElementById('adminsList');
    adminsList.innerHTML = '<div class="p-6 text-center text-gray-500">Loading admins...</div>';
    
    try {
        // Get current admin info
        const currentResponse = await fetch('/admin/api/admins/current', {
            credentials: 'include'
        });
        const currentResult = await currentResponse.json();
        if (currentResult.status) {
            currentAdminId = currentResult.data.id;
        }
        
        // Get all admins
        const response = await fetch('/admin/api/admins', {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status) {
            displayAdmins(result.data);
        } else {
            adminsList.innerHTML = '<div class="p-6 text-center text-red-500">Error loading admins</div>';
        }
    } catch (error) {
        console.error('Error loading admins:', error);
        adminsList.innerHTML = '<div class="p-6 text-center text-red-500">Error loading admins</div>';
    }
}

function displayAdmins(admins) {
    const adminsList = document.getElementById('adminsList');
    
    if (admins.length === 0) {
        adminsList.innerHTML = '<div class="p-6 text-center text-gray-500">No admin users found.</div>';
        return;
    }
    
    adminsList.innerHTML = admins.map(admin => {
        const permissions = admin.permissions || {};
        const permissionLabels = {
            'permission_users': 'Users',
            'permission_transactions': 'Transactions',
            'permission_verifications': 'Verifications',
            'permission_crypto': 'Crypto Assets',
            'permission_analytics': 'Analytics',
            'permission_settings': 'Settings'
        };
        const activePermissions = Object.keys(permissions).filter(key => permissions[key] === true);
        const permissionsText = activePermissions.length > 0 
            ? activePermissions.map(key => permissionLabels[key] || key).join(', ')
            : 'No permissions';
        
        return `
        <div class="p-6 hover:bg-gray-50 transition-colors border-b border-gray-200 last:border-b-0">
            <div class="flex items-center justify-between">
                <div class="flex-1">
                    <div class="flex items-center space-x-4">
                        <div class="w-12 h-12 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-full flex items-center justify-center">
                            <span class="text-white font-semibold text-lg">${admin.email.charAt(0).toUpperCase()}</span>
                        </div>
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900">${admin.email}</h3>
                            <p class="text-sm text-gray-500">User ID: ${admin.user_id}</p>
                            <p class="text-xs text-gray-400 mt-1">Permissions: ${permissionsText}</p>
                        </div>
                    </div>
                </div>
                <div class="flex items-center space-x-4">
                    <span class="px-3 py-1 rounded-full text-sm font-semibold ${
                        admin.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }">
                        ${admin.is_active ? 'Active' : 'Inactive'}
                    </span>
                    ${admin.id === currentAdminId ? '<span class="px-3 py-1 rounded-full text-sm font-semibold bg-indigo-100 text-indigo-800">You</span>' : ''}
                    <div class="flex items-center space-x-2">
                        <button onclick="editAdmin('${admin.id}', '${admin.email}', ${admin.is_active}, ${JSON.stringify(permissions).replace(/"/g, '&quot;')})" 
                                class="px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition-colors text-sm font-medium">
                            Edit
                        </button>
                        ${admin.id !== currentAdminId ? `
                            <button onclick="deleteAdmin('${admin.id}')" 
                                    class="px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors text-sm font-medium">
                                Delete
                            </button>
                        ` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
    }).join('');
}

// Change Password Form Handler
document.getElementById('changePasswordForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const currentPassword = document.getElementById('currentPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    
    if (!currentPassword || !newPassword) {
        Swal.fire({
            icon: 'warning',
            title: 'Required Fields',
            text: 'Please fill in all fields',
            confirmButtonColor: '#4f46e5'
        });
        return;
    }
    
    try {
        const currentResponse = await fetch('/admin/api/admins/current', {
            credentials: 'include'
        });
        const currentResult = await currentResponse.json();
        
        if (!currentResult.status) {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Could not get current admin info',
                confirmButtonColor: '#4f46e5'
            });
            return;
        }
        
        const response = await fetch('/admin/api/admins/update-password', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            credentials: 'include',
            body: JSON.stringify({
                user_id: currentResult.data.id,
                current_password: currentPassword,
                new_password: newPassword
            })
        });
        
        const result = await response.json();
        
        if (result.status) {
            Swal.fire({
                icon: 'success',
                title: 'Success!',
                text: 'Password updated successfully!',
                confirmButtonColor: '#4f46e5',
                timer: 2000,
                showConfirmButton: false
            });
            document.getElementById('changePasswordForm').reset();
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.message || 'Failed to update password',
                confirmButtonColor: '#4f46e5'
            });
        }
    } catch (error) {
        console.error('Error updating password:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'An error occurred. Please try again.',
            confirmButtonColor: '#4f46e5'
        });
    }
});

// Edit Admin Form Handler
document.getElementById('editAdminForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const adminId = document.getElementById('editAdminId').value;
    const email = document.getElementById('editAdminEmail').value;
    const isActive = document.getElementById('editAdminStatus').value === 'true';
    
    // Collect permissions
    const permissions = {};
    const permissionCheckboxes = document.querySelectorAll('#editAdminForm input[type="checkbox"][name^="permission_"]');
    permissionCheckboxes.forEach(checkbox => {
        if (checkbox.checked) {
            permissions[checkbox.name] = true;
        }
    });
    
    if (!email) {
        Swal.fire({
            icon: 'warning',
            title: 'Required Fields',
            text: 'Email is required',
            confirmButtonColor: '#4f46e5'
        });
        return;
    }
    
    try {
        const response = await fetch(`/admin/api/admins/${adminId}/update`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            credentials: 'include',
            body: JSON.stringify({
                email: email,
                is_active: isActive,
                permissions: permissions
            })
        });
        
        const result = await response.json();
        
        if (result.status) {
            Swal.fire({
                icon: 'success',
                title: 'Success!',
                text: 'Admin user updated successfully!',
                confirmButtonColor: '#4f46e5',
                timer: 2000,
                showConfirmButton: false
            });
            closeEditAdminModal();
            loadAdmins();
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.message || 'Failed to update admin user',
                confirmButtonColor: '#4f46e5'
            });
        }
    } catch (error) {
        console.error('Error updating admin:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'An error occurred. Please try again.',
            confirmButtonColor: '#4f46e5'
        });
    }
});

// Add Admin Form Handler
document.getElementById('addAdminForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const email = document.getElementById('adminEmail').value;
    const password = document.getElementById('adminPassword').value;
    const user_id = document.getElementById('adminUserId').value;
    
    // Collect permissions
    const permissions = {};
    const permissionCheckboxes = document.querySelectorAll('#addAdminForm input[type="checkbox"][name^="permission_"]');
    permissionCheckboxes.forEach(checkbox => {
        if (checkbox.checked) {
            permissions[checkbox.name] = true;
        }
    });
    
    if (!email || !password) {
        Swal.fire({
            icon: 'warning',
            title: 'Required Fields',
            text: 'Email and password are required',
            confirmButtonColor: '#4f46e5'
        });
        return;
    }
    
    try {
        const response = await fetch('/admin/api/admins/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            credentials: 'include',
            body: JSON.stringify({
                email: email,
                password: password,
                user_id: user_id || null,
                permissions: permissions
            })
        });
        
        const result = await response.json();
        
        if (result.status) {
            Swal.fire({
                icon: 'success',
                title: 'Success!',
                text: 'Admin user created successfully!',
                confirmButtonColor: '#4f46e5',
                timer: 2000,
                showConfirmButton: false
            });
            document.getElementById('addAdminForm').reset();
            closeAddAdminModal();
            loadAdmins();
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.message || 'Failed to create admin user',
                confirmButtonColor: '#4f46e5'
            });
        }
    } catch (error) {
        console.error('Error creating admin:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'An error occurred. Please try again.',
            confirmButtonColor: '#4f46e5'
        });
    }
});

function showEditAdminModal(adminId, email, isActive, permissions = {}) {
    // Set form values
    document.getElementById('editAdminId').value = adminId;
    document.getElementById('editAdminEmail').value = email;
    document.getElementById('editAdminStatus').value = isActive ? 'true' : 'false';
    
    // Set permissions checkboxes
    const permissionKeys = ['permission_users', 'permission_transactions', 'permission_verifications', 'permission_crypto', 'permission_analytics', 'permission_settings'];
    permissionKeys.forEach(key => {
        const checkbox = document.getElementById(`edit-${key}`);
        if (checkbox) {
            checkbox.checked = permissions[key] === true;
        }
    });
    
    // Show modal
    document.getElementById('editAdminModal').classList.remove('hidden');
}

function closeEditAdminModal() {
    document.getElementById('editAdminModal').classList.add('hidden');
    document.getElementById('editAdminForm').reset();
}

async function editAdmin(adminId, email, isActive, permissions = {}) {
    showEditAdminModal(adminId, email, isActive, permissions);
}

async function deleteAdmin(adminId) {
    const result = await Swal.fire({
        title: 'Delete Admin?',
        text: 'This action cannot be undone. Are you sure?',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Yes, delete it'
    });
    
    if (!result.isConfirmed) {
        return;
    }
    
    try {
        const response = await fetch(`/admin/api/admins/${adminId}/delete`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            credentials: 'include'
        });
        
        const result = await response.json();
        
        if (result.status) {
            Swal.fire({
                icon: 'success',
                title: 'Deleted!',
                text: 'Admin user deleted successfully!',
                confirmButtonColor: '#4f46e5',
                timer: 2000,
                showConfirmButton: false
            });
            loadAdmins();
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.message || 'Failed to delete admin user',
                confirmButtonColor: '#4f46e5'
            });
        }
    } catch (error) {
        console.error('Error deleting admin:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'An error occurred. Please try again.',
            confirmButtonColor: '#4f46e5'
        });
    }
}

function toggleAccordion(assetId) {
    const content = document.getElementById(assetId);
    const icon = document.getElementById(`icon-${assetId}`);
    
    if (content.classList.contains('hidden')) {
        content.classList.remove('hidden');
        if (icon) {
            icon.classList.add('rotate-180');
        }
    } else {
        content.classList.add('hidden');
        if (icon) {
            icon.classList.remove('rotate-180');
        }
    }
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

// Admin Settings Functions
async function loadAdminSettings() {
    try {
        const response = await fetch('/admin/api/admin/settings', {
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const text = await response.text();
            console.error('HTTP error response:', text);
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('Non-JSON response:', text.substring(0, 200));
            throw new Error('Response is not JSON');
        }
        
        const result = await response.json();
        
        if (result.status) {
            const settings = result.data;
            
            // Set language
            const languageSelect = document.getElementById('languageSelect');
            if (languageSelect) {
                languageSelect.value = settings.language || 'en';
            }
            
            // Set email notifications
            const emailToggle = document.getElementById('emailNotificationsToggle');
            if (emailToggle) {
                emailToggle.checked = settings.email_notifications !== false;
            }
            
            // Set currency
            const currencySelect = document.getElementById('currencySelect');
            if (currencySelect) {
                currencySelect.value = settings.currency || 'NGN';
            }
            
            // Set crypto sweep fee
            const cryptoSweepFeeInput = document.getElementById('cryptoSweepFeeInput');
            if (cryptoSweepFeeInput) {
                // Use nullish coalescing to allow 0 as a valid value
                cryptoSweepFeeInput.value = settings.crypto_sweep_fee_usd ?? 1.0;
            }

            // Set system delivery markup
            const systemDeliveryMarkupInput = document.getElementById('systemDeliveryMarkupInput');
            if (systemDeliveryMarkupInput) {
                systemDeliveryMarkupInput.value = settings.system_delivery_markup_ngn ?? 200;
            }
        }
    } catch (error) {
        console.error('Error loading admin settings:', error);
        // Don't show error to user on initial load, just use defaults
    }
}

async function updateAdminSettings() {
    const language = document.getElementById('languageSelect')?.value;
    const emailNotifications = document.getElementById('emailNotificationsToggle')?.checked;
    const currency = document.getElementById('currencySelect')?.value;
    const cryptoSweepFee = document.getElementById('cryptoSweepFeeInput')?.value;
    const systemDeliveryMarkup = document.getElementById('systemDeliveryMarkupInput')?.value;
    
    try {
        const response = await fetch('/admin/api/admin/settings', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            credentials: 'include',
            body: JSON.stringify({
                language: language,
                email_notifications: emailNotifications,
                currency: currency,
                crypto_sweep_fee_usd: cryptoSweepFee ? parseFloat(cryptoSweepFee) : null,
                system_delivery_markup_ngn: systemDeliveryMarkup ? parseFloat(systemDeliveryMarkup) : 0
            })
        });
        
        if (!response.ok) {
            const text = await response.text();
            console.error('HTTP error response:', text);
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('Non-JSON response:', text.substring(0, 200));
            throw new Error('Response is not JSON');
        }
        
        const result = await response.json();
        
        if (result.status) {
            // Update input fields with the response data to reflect what was actually saved
            if (result.data) {
                const settings = result.data;
                
                // Update language select
                const languageSelect = document.getElementById('languageSelect');
                if (languageSelect && settings.language) {
                    languageSelect.value = settings.language;
                }
                
                // Update email notifications toggle
                const emailToggle = document.getElementById('emailNotificationsToggle');
                if (emailToggle) {
                    emailToggle.checked = settings.email_notifications !== false;
                }
                
                // Update currency select
                const currencySelect = document.getElementById('currencySelect');
                if (currencySelect && settings.currency) {
                    currencySelect.value = settings.currency;
                }
                
                // Update crypto sweep fee input
                const cryptoSweepFeeInput = document.getElementById('cryptoSweepFeeInput');
                if (cryptoSweepFeeInput && settings.crypto_sweep_fee_usd !== undefined) {
                    cryptoSweepFeeInput.value = settings.crypto_sweep_fee_usd;
                }

                // Update system delivery markup input
                const systemDeliveryMarkupInput = document.getElementById('systemDeliveryMarkupInput');
                if (systemDeliveryMarkupInput && settings.system_delivery_markup_ngn !== undefined) {
                    systemDeliveryMarkupInput.value = settings.system_delivery_markup_ngn;
                }
            }
            
            // Trigger currency conversion if currency changed
            if (currency && window.convertPageCurrencies) {
                document.dispatchEvent(new CustomEvent('currencyChanged', { detail: { currency } }));
                await window.convertPageCurrencies(currency);
            }
            
            // Trigger translation if language changed
            if (language && window.translatePage) {
                document.dispatchEvent(new CustomEvent('languageChanged', { detail: { language } }));
                await window.translatePage(language);
            }
            
            Swal.fire({
                icon: 'success',
                title: 'Success!',
                text: 'Settings updated successfully',
                confirmButtonColor: '#4f46e5',
                timer: 2000,
                showConfirmButton: false
            });
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.message || 'Failed to update settings',
                confirmButtonColor: '#4f46e5'
            });
        }
    } catch (error) {
        console.error('Error updating admin settings:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'An error occurred. Please try again.',
            confirmButtonColor: '#4f46e5'
        });
    }
}

// Make functions globally accessible
window.loadAdminSettings = loadAdminSettings;
window.updateAdminSettings = updateAdminSettings;

