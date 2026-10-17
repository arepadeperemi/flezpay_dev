document.addEventListener('DOMContentLoaded', () => {
    const templates = [
        { id: 'grid', name: 'Aura Grid', category: 'Store', desc: 'Product-centric minimalist layout', icon: 'layout-grid' },
        { id: 'list', name: 'Nebula Flow', category: 'Store', desc: 'Content-rich sequential flow', icon: 'list' }
    ];

    const grid = document.getElementById('templates-grid');
    const template = document.getElementById('layout-card-template');

    if (!grid || !template) return;

    templates.forEach(t => {
        const clone = template.content.cloneNode(true);
        clone.querySelector('.template-title').textContent = t.name;
        clone.querySelector('.template-category').textContent = t.category;
        clone.querySelector('.template-desc').textContent = t.desc;
        clone.querySelector('.icon-class').setAttribute('data-lucide', t.icon);
        
        // Setup select button
        const selectBtn = clone.querySelector('button:last-child');
        selectBtn.addEventListener('click', () => {
            selectLayout(t.id, selectBtn);
        });

        // Setup preview button
        const previewBtn = clone.querySelector('button:first-child');
        previewBtn.addEventListener('click', () => {
            if (typeof showToast === 'function') {
                showToast('Info', 'Preview for ' + t.name + ' is coming soon!');
            }
        });

        grid.appendChild(clone);
    });

    if (window.lucide) {
        lucide.createIcons();
    }
});

function selectLayout(id, btn) {
    const originalText = btn.innerHTML;
    btn.innerHTML = '<div class="w-4 h-4 rounded-full border-2 border-primary border-t-transparent animate-spin"></div> Saving...';
    
    const formData = new FormData();
    formData.append('store_layout_template', id);
    
    // We don't send other fields to avoid overwriting them with blanks
    // The backend api/user/data/update/settings supports partial updates
    
    fetch('/api/user/data/update/settings', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Accept': 'application/json'
        },
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            // Reset other buttons
            document.querySelectorAll('#templates-grid button:last-child').forEach(b => {
                b.innerHTML = '<i data-lucide="check" class="w-3.5 h-3.5"></i> Select';
                b.className = 'flex-1 py-2.5 bg-primary/10 hover:bg-primary/20 text-primary text-xs font-bold rounded-xl transition-all border border-primary/20 flex items-center justify-center gap-1.5';
            });
            
            btn.innerHTML = '<i data-lucide="check-check" class="w-3.5 h-3.5"></i> Selected';
            btn.className = 'flex-1 py-2.5 bg-primary hover:bg-primary/90 text-white text-xs font-bold rounded-xl transition-all border border-primary flex items-center justify-center gap-1.5';
            if (window.lucide) lucide.createIcons();
            
            if (typeof showToast === 'function') {
                showToast('Success', 'Store layout updated successfully');
            }
        } else {
            throw new Error(data.message || 'Failed to update layout');
        }
    })
    .catch(err => {
        console.error(err);
        btn.innerHTML = originalText;
        if (typeof showToast === 'function') {
            showToast('Error', err.message, 'error');
        }
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
