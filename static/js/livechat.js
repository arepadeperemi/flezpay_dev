window.livechatWs = null;
window.activeChats = {}; // chat_id -> data
window.currentChatId = null;
window.currentSessionId = null;
window.storeVisitors = {}; // session_id -> data
window.currentChatFilter = 'all';

window.setChatFilter = function(filter, btnEl) {
    window.currentChatFilter = filter;
    const btns = document.querySelectorAll('.chat-filter-btn');
    btns.forEach(btn => {
        btn.className = btn.className.replace('text-indigo-600 dark:text-indigo-400 font-bold', 'hover:text-slate-800 dark:hover:text-white transition-colors');
    });
    if (btnEl) {
        btnEl.className = btnEl.className.replace('hover:text-slate-800 dark:hover:text-white transition-colors', 'text-indigo-600 dark:text-indigo-400 font-bold');
    }
    window.renderChatList();
};

window.switchTab = function(tab) {
    const tabChats = document.getElementById('tab-active-chats');
    const tabVisitors = document.getElementById('tab-visitors');
    if (tabChats) tabChats.className = `flex-1 py-4 flex items-center justify-center gap-2 ${tab === 'chats' ? 'text-primary border-b-2 border-primary' : 'text-slate-400 border-b-2 border-transparent hover:text-white'}`;
    if (tabVisitors) tabVisitors.className = `flex-1 py-4 flex items-center justify-center gap-2 ${tab === 'visitors' ? 'text-primary border-b-2 border-primary' : 'text-slate-400 border-b-2 border-transparent hover:text-white'}`;
    
    const chatsList = document.getElementById('chats-list');
    const visitorsList = document.getElementById('visitors-list');
    if (chatsList) chatsList.classList.toggle('hidden', tab !== 'chats');
    if (visitorsList) visitorsList.classList.toggle('hidden', tab !== 'visitors');
};

window.updateTabCounters = function() {
    const chatCount = Object.keys(window.activeChats).length;
    const visitorCount = Object.keys(window.storeVisitors).length;
    let unreadCount = 0;
    Object.values(window.activeChats).forEach(chat => {
        if (chat.unread > 0 || (!chat.has_been_read && chat.messages && chat.messages.length > 0 && chat.messages[chat.messages.length - 1].sender_type === 'visitor')) {
            unreadCount++;
        }
    });

    const chatEl = document.getElementById('count-chats');
    const visitorEl = document.getElementById('count-visitors');
    const unreadBadge = document.getElementById('unread-chats-badge');
    if (chatEl) chatEl.textContent = chatCount;
    if (visitorEl) visitorEl.textContent = visitorCount;
    if (unreadBadge) {
        if (unreadCount > 0) {
            unreadBadge.textContent = unreadCount;
            unreadBadge.classList.remove('hidden');
        } else {
            unreadBadge.classList.add('hidden');
        }
    }
};

window.initLivechat = function() {
    if (typeof window.checkLivechatStatus === 'function') window.checkLivechatStatus();
    if (window.livechatWs) {
        window.livechatWs.onclose = null;
        window.livechatWs.close();
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/livechat/agent/`;
    
    window.livechatWs = new WebSocket(wsUrl);
    
    window.livechatWs.onopen = () => {
        console.log("Agent Livechat connected");
    };
    
    window.livechatWs.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data.type === 'chat_message') {
                window.handleIncomingMessage(data.message);
            } else if (data.type === 'chat_closed') {
                window.handleChatClosed(data.chat_id);
            } else if (data.type === 'chat_deleted') {
                window.handleChatDeleted(data.chat_id);
            } else if (data.type === 'visitor_update') {
                window.handleVisitorUpdate(data);
            } else if (data.type === 'active_chats') {
                window.activeChats = {};
                data.chats.forEach(c => {
                    window.activeChats[c.id] = c;
                });
                window.renderChatList();
            }
        } catch (err) {
            console.error('Livechat WS message error:', err);
        }
    };
    
    window.livechatWs.onclose = () => {
        console.log("Livechat disconnected. Reconnecting in 5s...");
        setTimeout(window.initLivechat, 5000);
    };
};

window.selectedAttachment = null;

window.handleFileSelect = function(event) {
    const file = event.target.files[0];
    if (file) {
        const validTypes = ['image/jpeg', 'image/png', 'application/pdf'];
        const ext = file.name.split('.').pop().toLowerCase();
        const validExtensions = ['pdf', 'png', 'jpeg', 'jpg'];
        
        if (!validTypes.includes(file.type) || !validExtensions.includes(ext)) {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'Invalid File',
                    text: 'Only PDF, PNG, and JPEG files are allowed.',
                    background: '#0f0f0f', color: '#ffffff',
                    customClass: { popup: 'border border-white/10 rounded-2xl' }
                });
            } else {
                alert('Only PDF, PNG, and JPEG files are allowed.');
            }
            event.target.value = '';
            return;
        }
        
        if (file.size > 2 * 1024 * 1024) {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'File Too Large',
                    text: 'File size must be less than 2MB.',
                    background: '#0f0f0f', color: '#ffffff',
                    customClass: { popup: 'border border-white/10 rounded-2xl' }
                });
            } else {
                alert('File size must be less than 2MB.');
            }
            event.target.value = '';
            return;
        }

        window.selectedAttachment = file;
        
        const previewContainer = document.getElementById('attachment-preview-container');
        const filenameSpan = document.getElementById('attachment-filename');
        if (previewContainer && filenameSpan) {
            filenameSpan.textContent = file.name;
            previewContainer.classList.remove('hidden');
        }
        
        const btn = event.target.closest('button');
        const icon = btn.querySelector('i');
        if (icon) {
            icon.classList.remove('text-slate-400');
            icon.classList.add('text-primary');
        }
    }
};

window.clearAttachment = function() {
    window.selectedAttachment = null;
    const input = document.getElementById('chat-file-input');
    if (input) input.value = '';
    
    const previewContainer = document.getElementById('attachment-preview-container');
    if (previewContainer) {
        previewContainer.classList.add('hidden');
    }
    
    const icon = document.querySelector('[data-lucide="paperclip"]');
    if (icon) {
        icon.classList.add('text-slate-400');
        icon.classList.remove('text-primary');
    }
};

window.submitAgentMessage = function() {
    const input = document.getElementById('chat-input');
    if (!input) return;
    const text = input.value.trim();
    
    if (window.selectedAttachment) {
        const formData = new FormData();
        formData.append('file', window.selectedAttachment);
        
        fetch('/api/livechat/upload', {
            method: 'POST',
            body: formData
        }).then(res => res.json()).then(data => {
            if (data.status) {
                window.sendLivechatMessagePayload(text, data.url, data.type);
                window.clearAttachment();
            } else {
                if(typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'Upload Failed',
                        text: data.message || 'Failed to upload attachment.',
                        background: '#0f0f0f', color: '#ffffff',
                        customClass: { popup: 'border border-white/10 rounded-2xl' }
                    });
                } else {
                    alert(data.message || 'Failed to upload attachment.');
                }
            }
        }).catch(err => {
            console.error('Upload error', err);
        });
    } else if (text) {
        window.sendLivechatMessagePayload(text, null);
    }
};

window.sendLivechatMessagePayload = function(text, attachmentData, attachmentType = null) {
    if ((text || attachmentData) && (window.currentChatId || window.currentSessionId) && window.livechatWs && window.livechatWs.readyState === WebSocket.OPEN) {
        const payload = {
            type: 'agent_message',
            message: text
        };
        if (attachmentData) {
            payload.attachment = attachmentData;
            if (attachmentType) payload.attachment_type = attachmentType;
        }
        if (window.currentChatId && window.currentChatId.toString().startsWith('new_')) {
            payload.session_id = window.currentSessionId;
        } else if (window.currentChatId) {
            payload.chat_id = window.currentChatId;
        } else if (window.currentSessionId) {
            payload.session_id = window.currentSessionId;
        }
        
        window.livechatWs.send(JSON.stringify(payload));
        
        window.appendMessage({
            sender_type: 'agent',
            message_text: text,
            attachment: attachmentData,
            attachment_type: attachmentType,
            created_at: new Date().toISOString()
        });
        
        const input = document.getElementById('chat-input');
        if (input) input.value = '';
    }
};

window.handleIncomingMessage = function(msg) {
    const chatId = msg.chat_id;
    
    if (msg.visitor && 'new_' + msg.visitor.session_id === window.currentChatId) {
        delete window.activeChats[window.currentChatId];
        window.currentChatId = chatId;
        window.currentSessionId = null;
    } else if (msg.visitor && window.activeChats['new_' + msg.visitor.session_id]) {
        delete window.activeChats['new_' + msg.visitor.session_id];
    }
    
    if (!window.activeChats[chatId]) {
        window.activeChats[chatId] = {
            id: chatId,
            visitor_id: msg.visitor ? msg.visitor.session_id : 'Unknown',
            messages: []
        };
    }
    
    window.activeChats[chatId].messages.push(msg);
    
    if (String(window.currentChatId) === String(chatId) || (window.currentSessionId && msg.visitor && window.currentSessionId === msg.visitor.session_id)) {
        if (window.currentSessionId) {
            window.currentChatId = chatId;
            window.currentSessionId = null;
        }
        window.appendMessage(msg);
        window.activeChats[chatId].unread = 0;
        window.activeChats[chatId].has_been_read = true;
        if (window.livechatWs && window.livechatWs.readyState === WebSocket.OPEN) {
            window.livechatWs.send(JSON.stringify({
                type: 'mark_chat_read',
                chat_id: chatId
            }));
        }
    } else if (msg.sender_type !== 'agent') {
        window.activeChats[chatId].unread = (window.activeChats[chatId].unread || 0) + 1;
        window.activeChats[chatId].has_been_read = false;
    }
    
    if (msg.sender_type !== 'agent') {
        window.playNotificationSound();
    }
    
    window.renderChatList();
};

window.updateSidebarBadge = function() {
    const badge = document.getElementById('livechat-sidebar-badge');
    const badgeText = document.getElementById('livechat-sidebar-badge-text');
    
    let totalUnread = 0;
    Object.values(window.activeChats).forEach(chat => {
        if (chat.unread > 0) {
            totalUnread += chat.unread;
        } else if (!chat.has_been_read && chat.messages && chat.messages.length > 0) {
            const lastMsg = chat.messages[chat.messages.length - 1];
            if (lastMsg.sender_type === 'visitor') {
                totalUnread += 1;
            }
        }
    });
    
    const countLabel = totalUnread > 99 ? '99+' : totalUnread;

    if (totalUnread > 0) {
        if (badge) badge.classList.remove('hidden');
        if (badgeText) {
            badgeText.classList.remove('hidden');
            badgeText.textContent = countLabel;
        }
    } else {
        if (badge) badge.classList.add('hidden');
        if (badgeText) badgeText.classList.add('hidden');
    }
};

window.handleChatClosed = function(chatId) {
    delete window.activeChats[chatId];
    if (String(window.currentChatId) === String(chatId)) {
        const placeholder = document.getElementById('chat-placeholder');
        const activeContainer = document.getElementById('active-chat-container');
        if (placeholder) placeholder.classList.remove('hidden');
        if (activeContainer) activeContainer.classList.add('hidden');
        window.currentChatId = null;
    }
    window.renderChatList();
};

window.handleChatDeleted = function(chatId) {
    window.handleChatClosed(chatId);
};

window.deleteCurrentChat = function() {
    if (!window.currentChatId) return;
    Swal.fire({
        title: 'Delete Chat?',
        text: "Are you sure you want to delete this chat permanently? This action cannot be undone.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#e11d48',
        cancelButtonColor: '#334155',
        confirmButtonText: 'Yes, delete it',
        background: '#0f0f0f',
        color: '#ffffff',
        customClass: {
            popup: 'border border-white/10 rounded-2xl'
        }
    }).then((result) => {
        if (result.isConfirmed) {
            if (window.livechatWs && window.livechatWs.readyState === WebSocket.OPEN) {
                window.livechatWs.send(JSON.stringify({
                    type: 'delete_chat',
                    chat_id: window.currentChatId
                }));
            }
        }
    });
};

window.openChat = function(chatId) {
    window.currentChatId = chatId;
    window.currentSessionId = null;
    
    const sidebar = document.getElementById('chat-sidebar');
    const area = document.getElementById('chat-area');
    
    if (window.innerWidth < 768 && sidebar && area) {
        sidebar.classList.add('hidden');
        sidebar.classList.remove('flex');
        area.classList.remove('hidden');
        area.classList.add('flex');
    }
    
    const placeholder = document.getElementById('chat-placeholder');
    const activeContainer = document.getElementById('active-chat-container');
    if (placeholder) placeholder.classList.add('hidden');
    if (activeContainer) activeContainer.classList.remove('hidden');
    
    if (window.activeChats[chatId]) {
        window.activeChats[chatId].unread = 0;
        window.activeChats[chatId].has_been_read = true;
        if (window.livechatWs && window.livechatWs.readyState === WebSocket.OPEN) {
            window.livechatWs.send(JSON.stringify({
                type: 'mark_chat_read',
                chat_id: chatId
            }));
        }
    }
    
    const chat = window.activeChats[chatId];
    if (!chat) return; // safety
    
    const v = window.storeVisitors[chat.visitor_id];
    const displayName = chat.visitor_name || (v && v.visitor_name) || `Visitor #${chat.visitor_id.substring(0,8)}`;
    const flagHtml = (v && v.country_code) ? `<img src="https://flagcdn.com/w20/${v.country_code}.png" class="w-4 h-3 rounded-[2px] ml-2" alt="${v.country_code}">` : '';
    
    const titleEl = document.getElementById('active-chat-title');
    if (titleEl) titleEl.innerHTML = `${displayName} ${flagHtml}`;
    
    const isOnline = !!window.storeVisitors[chat.visitor_id];
    window.updateActiveChatStatus(chat.visitor_id, isOnline ? 'online' : 'offline');
    window.updateRightSidebar(chat.visitor_id, displayName, chat.custom_data);
    
    const emailStr = (chat.visitor_email || (v && v.visitor_email)) ? `<p class="text-[10px] text-slate-400 flex items-center gap-1">📧 ${chat.visitor_email || v.visitor_email}</p>` : '';
    const phoneStr = (chat.visitor_phone || (v && v.visitor_phone)) ? `<p class="text-[10px] text-slate-400 flex items-center gap-1">📞 ${chat.visitor_phone || v.visitor_phone}</p>` : '';
    
    const detailsEl = document.getElementById('active-chat-details');
    if (detailsEl) detailsEl.innerHTML = emailStr + phoneStr;
    
    const messagesContainer = document.getElementById('chat-messages');
    if (messagesContainer) {
        messagesContainer.innerHTML = '';
        chat.messages.forEach(window.appendMessage);
    }
    
    window.renderChatList();
};

window.appendMessage = function(msg) {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    const isAgent = msg.sender_type === 'agent';
    
    let attachmentHtml = '';
    if (msg.attachment) {
        if (msg.attachment_type === 'image' || msg.attachment.match(/\.(jpeg|jpg|gif|png)$/i) != null) {
            attachmentHtml = `<img src="${msg.attachment}" onclick="window.openLightbox('${msg.attachment}')" class="max-w-full rounded-xl mt-2 mb-1 cursor-pointer hover:opacity-90 transition-opacity" style="max-height: 200px; object-fit: contain;">`;
        } else {
            let ext = msg.attachment.split('.').pop().toUpperCase();
            if (ext.length > 5 || ext.includes('/')) ext = 'FILE'; // fallback if not URL ending in ext
            attachmentHtml = `<a href="${msg.attachment}" download target="_blank" class="flex items-center gap-2 bg-black/20 p-2 rounded-xl mt-2 mb-1 text-xs hover:bg-black/30 transition-colors"><i data-lucide="download" class="w-4 h-4 shrink-0"></i><span class="truncate">Download ${ext}</span></a>`;
        }
    }

    const html = `
        <div class="flex ${isAgent ? 'justify-end' : 'justify-start'} w-full">
            <div class="max-w-[70%] rounded-2xl px-4 py-2 ${isAgent ? 'bg-primary text-white rounded-br-none' : 'bg-white/10 text-white rounded-bl-none'} break-words flex flex-col">
                ${msg.message_text ? `<p class="text-sm">${msg.message_text}</p>` : ''}
                ${attachmentHtml}
                <p class="text-[10px] opacity-70 mt-1 text-right">${new Date(msg.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</p>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', html);
    if(window.lucide) lucide.createIcons();
    container.scrollTop = container.scrollHeight;
};

window.renderChatList = function() {
    window.updateTabCounters();
    window.updateSidebarBadge();
    
    const list = document.getElementById('chats-list');
    if (!list) return;
    
    list.innerHTML = '';
    
    let chats = Object.values(window.activeChats).sort((a, b) => {
        const aTime = a.messages.length ? new Date(a.messages[a.messages.length - 1].created_at).getTime() : 0;
        const bTime = b.messages.length ? new Date(b.messages[b.messages.length - 1].created_at).getTime() : 0;
        return bTime - aTime;
    });

    if (window.currentChatFilter === 'unread') {
        chats = chats.filter(c => c.unread > 0);
    }
    
    if (chats.length === 0) {
        list.innerHTML = '<div class="p-4 text-center text-slate-500 text-sm mt-4">No active chats</div>';
        window.updateTabCounters();
        return;
    }
    
    chats.forEach(chat => {
        const lastMsg = chat.messages[chat.messages.length - 1];
        const preview = lastMsg ? (lastMsg.message_text || 'Attachment') : 'New Chat';
        const v = window.storeVisitors[chat.visitor_id];
        const displayName = chat.visitor_name || (v && v.visitor_name) || `Visitor #${chat.visitor_id.substring(0,8)}`;
        const countryCode = chat.country_code || (v && v.country_code);
        const flagHtml = countryCode ? `<img src="https://flagcdn.com/w20/${countryCode}.png" class="w-4 h-3 rounded-[2px]" alt="${countryCode}">` : '';
        
        const isOnline = !!window.storeVisitors[chat.visitor_id];
        const onlineDot = isOnline ? `<span class="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" title="Online"></span>` : '';
        
        const unreadBadge = (chat.unread > 0) ? `<span class="bg-primary text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full ml-1">${chat.unread}</span>` : '';
        
        const html = `
            <div onclick="window.openChat('${chat.id}')" class="chat-tab cursor-pointer p-4 border-b border-white/5 transition-all ${String(window.currentChatId) === String(chat.id) ? 'bg-primary/10 border-l-[3px] border-primary' : 'hover:bg-white/5 border-l-[3px] border-transparent'}">
                <div class="flex justify-between items-start mb-1">
                    <h4 class="font-bold text-sm text-white truncate flex items-center gap-2">
                        ${displayName} ${flagHtml} ${onlineDot}
                    </h4>
                    <div class="flex items-center gap-2">
                        ${unreadBadge}
                        <span class="text-[10px] text-slate-500 whitespace-nowrap ml-1">Just now</span>
                    </div>
                </div>
                <p class="text-xs text-slate-400 truncate">${preview}</p>
            </div>
        `;
        list.insertAdjacentHTML('beforeend', html);
    });
    window.updateTabCounters();
    window.updateSidebarBadge();
};

window.closeCurrentChatMobile = function() {
    const sidebar = document.getElementById('chat-sidebar');
    const area = document.getElementById('chat-area');
    const rightSidebar = document.getElementById('user-sidebar');
    if (window.innerWidth < 768) {
        if (sidebar && area) {
            sidebar.classList.remove('hidden');
            sidebar.classList.add('flex');
            area.classList.add('hidden');
            area.classList.remove('flex');
        }
        if (rightSidebar) rightSidebar.classList.add('translate-x-full');
    }
};

window.closeCurrentChat = function() {
    if(typeof Swal === 'undefined') return;
    Swal.fire({
        title: 'End Chat Session?',
        text: "Are you sure you want to end and delete this chat session? This action cannot be undone.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#10b981',
        cancelButtonColor: '#334155',
        confirmButtonText: 'Yes, end it',
        background: '#0f0f0f',
        color: '#ffffff',
        customClass: {
            popup: 'border border-white/10 rounded-2xl'
        }
    }).then((result) => {
        if (result.isConfirmed) {
            if (window.currentChatId && window.livechatWs) {
                window.livechatWs.send(JSON.stringify({
                    type: 'close_chat',
                    chat_id: window.currentChatId
                }));
            }
            window.closeCurrentChatMobile();
        }
    });
};

window.handleVisitorUpdate = function(data) {
    if (data.status === 'online') {
        window.storeVisitors[data.session_id] = data;
    } else {
        delete window.storeVisitors[data.session_id];
    }
    window.updateActiveChatStatus(data.session_id, data.status);
    window.renderVisitorsList();
    window.renderChatList();
};

window.updateActiveChatStatus = function(sessionId, status) {
    const isCurrentVisitor = (
        window.currentSessionId === sessionId ||
        (window.currentChatId && window.activeChats[window.currentChatId] && window.activeChats[window.currentChatId].visitor_id === sessionId)
    );
    if (!isCurrentVisitor) return;

    const statusEl = document.getElementById('active-chat-status');
    const dotEl = document.getElementById('active-chat-status-dot');
    const textEl = document.getElementById('active-chat-status-text');
    
    const sidebarDot = document.getElementById('user-sidebar-status-dot');
    const sidebarText = document.getElementById('user-sidebar-status-text');

    if (status === 'online') {
        if (statusEl) statusEl.className = 'text-xs text-emerald-400 flex items-center gap-1';
        if (dotEl) dotEl.className = 'w-1.5 h-1.5 rounded-full bg-emerald-400';
        if (textEl) textEl.textContent = 'Online';
        if (sidebarDot) sidebarDot.className = 'w-1.5 h-1.5 rounded-full bg-emerald-500';
        if (sidebarText) { sidebarText.textContent = 'Online'; sidebarText.className = 'text-emerald-500'; }
    } else {
        if (statusEl) statusEl.className = 'text-xs text-slate-500 flex items-center gap-1';
        if (dotEl) dotEl.className = 'w-1.5 h-1.5 rounded-full bg-slate-500';
        if (textEl) textEl.textContent = 'Offline';
        if (sidebarDot) sidebarDot.className = 'w-1.5 h-1.5 rounded-full bg-slate-500';
        if (sidebarText) { sidebarText.textContent = 'Offline'; sidebarText.className = 'text-slate-500'; }
    }
};

window.renderVisitorsList = function() {
    window.updateTabCounters();
    
    const list = document.getElementById('visitors-list');
    if (!list) return;
    list.innerHTML = '';
    
    const visitors = Object.values(window.storeVisitors);
    if (visitors.length === 0) {
        list.innerHTML = '<div class="p-4 text-center text-slate-500 text-sm mt-4">No visitors online</div>';
        window.updateTabCounters();
        return;
    }
    
    visitors.forEach(v => {
        const nameStr = v.visitor_name ? `${v.visitor_name}` : `Visitor #${v.session_id.substring(0,8)}`;
        const flagHtml = v.country_code ? `<img src="https://flagcdn.com/w20/${v.country_code}.png" class="w-4 h-3 rounded-[2px]" alt="${v.country_code}">` : '';
        const phoneHtml = v.visitor_phone ? `<p class="text-[10px] text-slate-500 mt-0.5">📞 ${v.visitor_phone}</p>` : '';
        
        const html = `
            <div id="visitor-tab-${v.session_id}" onclick="window.startChatWithVisitor('${v.session_id}')" class="visitor-tab p-4 border-b border-white/5 transition-all flex justify-between items-center cursor-pointer ${window.currentSessionId === v.session_id ? 'bg-primary/10 border-l-[3px] border-primary' : 'hover:bg-white/5 border-l-[3px] border-transparent'}">
                <div>
                    <h4 class="font-bold text-sm text-white truncate flex items-center gap-2">
                        ${nameStr}
                        ${flagHtml}
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                    </h4>
                    <p class="text-[10px] text-slate-400 truncate mt-1">Viewing: ${v.current_url || 'Store Home'}</p>
                    ${v.visitor_email ? `<p class="text-[10px] text-slate-500 mt-0.5">${v.visitor_email}</p>` : ''}
                    ${phoneHtml}
                </div>
            </div>
        `;
        list.insertAdjacentHTML('beforeend', html);
    });
    window.updateTabCounters();
};

window.startChatWithVisitor = function(sessionId) {
    const existingChat = Object.values(window.activeChats).find(c => c.visitor_id === sessionId && !c.id.toString().startsWith('new_'));
    if (existingChat) {
        window.switchTab('chats');
        window.openChat(existingChat.id);
    } else {
        window.currentChatId = 'new_' + sessionId;
        window.currentSessionId = sessionId;
        
        window.activeChats[window.currentChatId] = {
            id: window.currentChatId,
            visitor_id: sessionId,
            messages: [],
            is_new: true
        };
        
        window.switchTab('chats');
        window.renderChatList();
        
        const sidebar = document.getElementById('chat-sidebar');
        const area = document.getElementById('chat-area');
        if (window.innerWidth < 768 && sidebar && area) {
            sidebar.classList.add('hidden');
            sidebar.classList.remove('flex');
            area.classList.remove('hidden');
            area.classList.add('flex');
        }
        
        const placeholder = document.getElementById('chat-placeholder');
        const activeContainer = document.getElementById('active-chat-container');
        if (placeholder) placeholder.classList.add('hidden');
        if (activeContainer) activeContainer.classList.remove('hidden');
        
        const v = window.storeVisitors[sessionId];
        const flagHtml = (v && v.country_code) ? `<img src="https://flagcdn.com/w20/${v.country_code}.png" class="w-4 h-3 rounded-[2px] ml-2" alt="${v.country_code}">` : '';
        const titleEl = document.getElementById('active-chat-title');
        const displayName = v?.visitor_name || `Visitor #${sessionId.substring(0,8)}`;
        if(titleEl) titleEl.innerHTML = `<span class="flex items-center">${displayName} ${flagHtml}</span>`;
        
        const emailStr = (v && v.visitor_email) ? `<p class="text-[10px] text-slate-400 flex items-center gap-1">📧 ${v.visitor_email}</p>` : '';
        const phoneStr = (v && v.visitor_phone) ? `<p class="text-[10px] text-slate-400 flex items-center gap-1">📞 ${v.visitor_phone}</p>` : '';
        const detailsEl = document.getElementById('active-chat-details');
        if(detailsEl) detailsEl.innerHTML = emailStr + phoneStr;
        
        window.updateActiveChatStatus(sessionId, 'online');
        window.updateRightSidebar(sessionId, displayName);
        const messagesEl = document.getElementById('chat-messages');
        if(messagesEl) messagesEl.innerHTML = '<div class="text-center text-xs text-slate-500 my-4">Chat started</div>';
    }
};

window.playNotificationSound = function() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(800, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(1200, ctx.currentTime + 0.1);
        gain.gain.setValueAtTime(0, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(0.3, ctx.currentTime + 0.05);
        gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.2);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.2);
    } catch(e) {}
};

window.checkLivechatStatus = async function() {
    try {
        const response = await window.apiFetch(`${window.CONFIG?.API_BASE || ''}/api/user/data`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (response.ok) {
            const res = await response.json();
            if (res.status && res.data && res.data.business_details && res.data.business_details[0]) {
                const business = res.data.business_details[0];
                const isStoreSetup = business.store_setup === true || business.store_setup === 'true' || business.store_setup === 1 || business.store_setup === '1';
                const isLivechatEnabled = business.enable_livechat === true || business.enable_livechat === 'true' || business.enable_livechat === 1 || business.enable_livechat === '1';
                
                const overlay = document.getElementById('livechat-disabled-overlay');
                if (overlay) {
                    const titleEl = overlay.querySelector('h2');
                    const descEl = overlay.querySelector('p');
                    const btn = overlay.querySelector('button');

                    if (!isStoreSetup) {
                        if (titleEl) titleEl.innerText = 'Online Store Not Created';
                        if (descEl) descEl.innerText = 'You must create and set up your online store first before you can use livechat support for your customers.';
                        if (btn) {
                            btn.innerHTML = '<i data-lucide="store" class="w-5 h-5"></i> Create Online Store';
                            btn.onclick = function() { window.location.href = '/store'; };
                        }
                        overlay.classList.remove('hidden');
                        overlay.classList.add('flex');
                    } else if (!isLivechatEnabled) {
                        if (titleEl) titleEl.innerText = 'Livechat is Disabled';
                        if (descEl) descEl.innerText = 'Your online store livechat support is currently disabled. Enable it to start receiving messages from your store visitors directly here.';
                        if (btn) {
                            btn.innerHTML = '<i data-lucide="power" class="w-5 h-5"></i> Enable Livechat Support';
                            btn.onclick = function() { window.enableLivechatFromOverlay(); };
                        }
                        overlay.classList.remove('hidden');
                        overlay.classList.add('flex');
                    } else {
                        overlay.classList.add('hidden');
                        overlay.classList.remove('flex');
                    }
                    if (window.lucide) lucide.createIcons();
                }
            }
        }
    } catch (error) {
        console.error("Failed to fetch business data:", error);
    }
};

window.enableLivechatFromOverlay = async function() {
    try {
        const btn = document.querySelector('#livechat-disabled-overlay button');
        if (btn) btn.innerHTML = '<i data-lucide="loader-2" class="w-5 h-5 animate-spin"></i> Enabling...';
        
        const formData = new FormData();
        formData.append('enable_livechat', 'true');
        
        const response = await window.apiFetch(`${window.CONFIG?.API_BASE || ''}/api/user/store/setup`, {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const overlay = document.getElementById('livechat-disabled-overlay');
            if(overlay) {
                overlay.classList.add('hidden');
                overlay.classList.remove('flex');
            }
            if(typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'success',
                    title: 'Livechat Enabled',
                    text: 'Your store livechat support is now active.',
                    background: '#0f0f0f',
                    color: '#ffffff',
                    customClass: { popup: 'border border-white/10 rounded-2xl' }
                });
            }
        } else {
            throw new Error('Failed to enable');
        }
    } catch (error) {
        if(typeof Swal !== 'undefined') {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Failed to enable livechat. Please try again or check store settings.',
                background: '#0f0f0f',
                color: '#ffffff',
                customClass: { popup: 'border border-white/10 rounded-2xl' }
            });
        }
        const btn = document.querySelector('#livechat-disabled-overlay button');
        if (btn) {
            btn.innerHTML = '<i data-lucide="power" class="w-5 h-5"></i> Enable Livechat Support';
            if(window.lucide) lucide.createIcons();
        }
    }
};

window.openLightbox = function(url) {
    const html = `
        <div id="image-lightbox" class="fixed inset-0 z-[9999] bg-black/90 flex items-center justify-center p-4 backdrop-blur-sm cursor-zoom-out" onclick="this.remove()">
            <img src="${url}" class="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl cursor-default" onclick="event.stopPropagation()">
            <button onclick="this.parentElement.remove()" class="absolute top-4 right-4 text-white hover:text-rose-500 bg-black/50 p-2 rounded-full transition-colors cursor-pointer">
                <i data-lucide="x" class="w-6 h-6"></i>
            </button>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', html);
    if(window.lucide) lucide.createIcons();
};

window.toggleRightSidebar = function() {
    const sidebar = document.getElementById('user-sidebar');
    if (sidebar) {
        sidebar.classList.toggle('translate-x-full');
    }
};

window.saveCustomData = function() {
    const textInput = document.getElementById('custom-data-textarea');
    if (!textInput) return;
    
    const value = textInput.value.trim();
    if (!value || !window.currentChatId) return;

    if (window.livechatWs && window.livechatWs.readyState === WebSocket.OPEN) {
        window.livechatWs.send(JSON.stringify({
            type: 'save_custom_data',
            chat_id: window.currentChatId,
            session_id: window.currentSessionId,
            data: value
        }));
        
        // Optimistic UI update
        const list = document.getElementById('custom-data-list');
        if (list) {
            if (list.querySelector('.italic')) list.innerHTML = '';
            list.insertAdjacentHTML('beforeend', `<div class="p-2 bg-slate-50 dark:bg-white/5 rounded text-xs whitespace-pre-wrap text-slate-700 dark:text-slate-300 mb-1 border border-slate-200 dark:border-white/10">${value}</div>`);
        }
        
        // Update local state
        const chat = window.activeChats[window.currentChatId];
        if (chat) {
            if (chat.custom_data) chat.custom_data += '\n\n' + value;
            else chat.custom_data = value;
        }
        
        textInput.value = '';
    }
};

window.parseUserAgent = function(ua) {
    let browser = 'Unknown';
    let os = 'Unknown';
    if (!ua) return { browser, os };
    
    if (ua.includes('Firefox')) browser = 'Firefox';
    else if (ua.includes('Edg')) browser = 'Edge';
    else if (ua.includes('OPR') || ua.includes('Opera')) browser = 'Opera';
    else if (ua.includes('Chrome')) browser = 'Chrome';
    else if (ua.includes('Safari')) browser = 'Safari';
    else browser = 'Other';
    
    if (ua.includes('Windows')) os = 'Windows';
    else if (ua.includes('Mac OS') || ua.includes('Macintosh')) os = 'macOS';
    else if (ua.includes('Android')) os = 'Android';
    else if (ua.includes('Linux')) os = 'Linux';
    else if (ua.includes('iOS') || ua.includes('iPhone') || ua.includes('iPad')) os = 'iOS';
    else os = 'Other';
    
    return { browser, os };
};

window.updateRightSidebar = function(visitorId, fallbackName, customData) {
    const placeholder = document.getElementById('user-sidebar-placeholder');
    const details = document.getElementById('active-user-details');
    if (placeholder) placeholder.classList.add('hidden');
    if (details) details.classList.remove('hidden');
    if (details) details.classList.add('flex');

    const v = window.storeVisitors[visitorId] || {};
    const displayName = v.visitor_name || fallbackName || `Visitor #${visitorId.substring(0,8)}`;
    
    const nameEl = document.getElementById('user-sidebar-name');
    if (nameEl) nameEl.textContent = displayName;
    
    const avatarEl = document.getElementById('user-avatar-large');
    if (avatarEl) avatarEl.textContent = displayName.charAt(0).toUpperCase();

    const emailEl = document.getElementById('user-sidebar-email');
    if (emailEl) {
        if (v.visitor_email) {
            emailEl.innerHTML = `<a href="mailto:${v.visitor_email}" class="flex items-center gap-1.5 hover:text-primary transition-colors"><i data-lucide="mail" class="w-3.5 h-3.5 text-slate-500"></i> <span class="truncate">${v.visitor_email}</span></a>`;
        } else {
            emailEl.innerHTML = `<div class="flex items-center gap-1.5 text-slate-400"><i data-lucide="mail" class="w-3.5 h-3.5"></i> <span class="truncate italic">No email</span></div>`;
        }
    }
    
    const phoneEl = document.getElementById('user-sidebar-phone');
    if (phoneEl) {
        if (v.visitor_phone) {
            phoneEl.innerHTML = `<a href="tel:${v.visitor_phone}" class="flex items-center gap-1.5 hover:text-primary transition-colors"><i data-lucide="phone" class="w-3.5 h-3.5 text-slate-500"></i> <span class="truncate">${v.visitor_phone}</span></a>`;
        } else {
            phoneEl.innerHTML = `<div class="flex items-center gap-1.5 text-slate-400"><i data-lucide="phone" class="w-3.5 h-3.5"></i> <span class="truncate italic">No phone</span></div>`;
        }
    }

    const locEl = document.getElementById('user-sidebar-location');
    if (locEl) {
        if (v.country_code) {
            let countryName = v.country_code.toUpperCase();
            try {
                const regionNames = new Intl.DisplayNames(['en'], {type: 'region'});
                countryName = regionNames.of(v.country_code.toUpperCase()) || countryName;
            } catch (e) {}
            
            let locStr = '';
            if (v.state) locStr += v.state + ', ';
            locStr += countryName;
            locEl.innerHTML = `<img src="https://flagcdn.com/w20/${v.country_code.toLowerCase()}.png" class="w-4 h-3 rounded-[2px]" alt="${v.country_code}"> ${locStr}`;
        } else {
            locEl.innerHTML = 'Unknown Location';
        }
    }

    const parsedUa = window.parseUserAgent(v.user_agent);

    const browserEl = document.getElementById('user-sidebar-browser');
    if (browserEl) browserEl.textContent = `Browser: ${parsedUa.browser}`;
    
    const osEl = document.getElementById('user-sidebar-os');
    if (osEl) osEl.textContent = `OS: ${parsedUa.os}`;

    const langEl = document.getElementById('user-sidebar-lang');
    if (langEl) langEl.textContent = `Language: ${v.language ? v.language.toUpperCase() : 'Unknown'}`;
    
    const timeEl = document.getElementById('user-sidebar-time');
    if (timeEl) timeEl.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

    const urlEl = document.getElementById('user-sidebar-url');
    if (urlEl) urlEl.textContent = v.current_url || '/';

    const customDataList = document.getElementById('custom-data-list');
    if (customDataList) {
        if (customData && customData.trim() !== '') {
            const parts = customData.split('\n\n');
            customDataList.innerHTML = parts.map(p => `<div class="p-2 bg-slate-50 dark:bg-white/5 rounded text-xs whitespace-pre-wrap text-slate-700 dark:text-slate-300 mb-1 border border-slate-200 dark:border-white/10">${p}</div>`).join('');
        } else {
            customDataList.innerHTML = `<div class="text-xs text-slate-400 italic">No custom data yet</div>`;
        }
    }
};
