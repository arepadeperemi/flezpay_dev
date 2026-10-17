/**
 * AI Manager - Optimized Frontend Interaction with Dynamic Action Button
 */

function initAiChat() {
    const chatMessages = $('#chat-messages');
    const chatInput = $('#chat-input');
    const sendBtn = $('#send-btn');
    const suggestionBtns = $('.suggestion-btn');
    const micBtn = $('#mic-btn');


    if (!chatMessages.length) return;

    let chatHistory = [];
    let isHandsFree = false;
    let recognition = null;
    let isProcessing = false;
    let currentSessionId = sessionStorage.getItem('ai_session_id');
    if (!currentSessionId) {
        currentSessionId = 'sess_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
        sessionStorage.setItem('ai_session_id', currentSessionId);
    }


    // Initialization
    setupVoiceRecognition();
    updateButtonState();
    loadChatHistory();

    // Synchronize viewport height accounting for the 80px header
    function updateAiViewport() {
        const vh = window.visualViewport ? window.visualViewport.height : window.innerHeight;
        document.documentElement.style.setProperty('--ai-viewport-height', `${vh}px`);
    }
    updateAiViewport();
    $(window).off('resize.aiviewport').on('resize.aiviewport', updateAiViewport);
    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', updateAiViewport);
        window.visualViewport.addEventListener('scroll', updateAiViewport);
    }
    chatInput.off('focus.aiviewport').on('focus.aiviewport', function() {
        setTimeout(() => {
            updateAiViewport();
            if (chatMessages && chatMessages[0]) {
                chatMessages.scrollTop(chatMessages[0].scrollHeight);
            }
        }, 300);
    });

    // Interactive ripple effect for buttons and action cards
    $(document).off('click.airipple', '.ai-ripple-container, .ai-action-btn, .ai-action-link-card')
               .on('click.airipple', '.ai-ripple-container, .ai-action-btn, .ai-action-link-card', function(e) {
        const el = this;
        const circle = document.createElement('span');
        const diameter = Math.max(el.clientWidth, el.clientHeight);
        const radius = diameter / 2;
        const rect = el.getBoundingClientRect();
        circle.style.width = circle.style.height = `${diameter}px`;
        circle.style.left = `${e.clientX - rect.left - radius}px`;
        circle.style.top = `${e.clientY - rect.top - radius}px`;
        circle.classList.add('ai-ripple-circle');
        const prev = el.getElementsByClassName('ai-ripple-circle')[0];
        if (prev) prev.remove();
        el.appendChild(circle);
        setTimeout(() => circle.remove(), 600);
    });

    async function loadChatHistory() {
        try {
            const response = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/chat?session_id=${currentSessionId}`);
            if (response.ok) {
                const result = await response.json();
                if (result.status && result.data) {
                    chatMessages.empty();
                    chatHistory = result.data.map(chat => ({
                        role: chat.role === 'assistant' ? 'assistant' : 'user',
                        content: chat.content
                    }));
                    
                    chatHistory.forEach(msg => {
                        const role = msg.role === 'assistant' ? 'bot' : 'user';
                        const chatMsg = addChatMessage(msg.content, role);
                        if (role === 'bot') {
                            const formattedHtml = sanitizeHTML(markdownToHtml(msg.content, null, null, false));
                            chatMsg.target.html(formattedHtml);
                            setTimeout(() => {
                                mountChartsAndRipples(chatMsg.id);
                                injectActionButtons(chatMsg.id, msg.content);
                            }, 50);
                        }
                    });
                }
            }
        } catch (err) {
            console.error('Failed to load chat history:', err);
        } finally {
            // Check for incoming question parameter (e.g. from Business Analytics)
            const urlParams = new URLSearchParams(window.location.search);
            const initialQuestion = urlParams.get('question') || urlParams.get('q');
            if (initialQuestion && initialQuestion.trim()) {
                chatInput.val(initialQuestion.trim());
                updateButtonState();
                window.history.replaceState({}, document.title, window.location.pathname);
                setTimeout(() => {
                    handleRealSend();
                }, 250);
            }
        }
    }



    // Event Bindings
    sendBtn.off('click').on('click', handleActionButtonClick);
    const thinkBtn = $('#think-btn');
    let isThinkMode = false;
    thinkBtn.off('click').on('click', function(e) {
        e.preventDefault();
        isThinkMode = !isThinkMode;
        if (isThinkMode) {
            thinkBtn.addClass('bg-primary text-black border-primary ring-2 ring-primary/30 shadow-md shadow-primary/20').removeClass('bg-primary/10 hover:bg-primary/20 dark:bg-primary/15 dark:hover:bg-primary/25 text-primary border-primary/30');
            thinkBtn.find('i, svg').addClass('text-black').removeClass('text-primary');
        } else {
            thinkBtn.removeClass('bg-primary text-black border-primary ring-2 ring-primary/30 shadow-md shadow-primary/20').addClass('bg-primary/10 hover:bg-primary/20 dark:bg-primary/15 dark:hover:bg-primary/25 text-primary border-primary/30');
            thinkBtn.find('i, svg').removeClass('text-black').addClass('text-primary');
        }
    });

    const sessionsDropdownBtn = $('#sessions-dropdown-btn');
    const sessionsDropdown = $('#sessions-dropdown');
    const sessionsList = $('#sessions-list');

    // Toggle dropdown
    sessionsDropdownBtn.off('click').on('click', (e) => {
        e.stopPropagation();
        sessionsDropdown.toggleClass('hidden');
        if (!sessionsDropdown.hasClass('hidden')) {
            loadSessionsList();
        }
    });

    // Close on click outside
    $(document).on('click', (e) => {
        if (!$(e.target).closest('#sessions-dropdown-btn').length && !$(e.target).closest('#sessions-dropdown').length) {
            sessionsDropdown.addClass('hidden');
        }
    });

    async function loadSessionsList() {
        try {
            const response = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/chat?sessions=true`);
            if (response.ok) {
                const result = await response.json();
                if (result.status && result.data) {
                    sessionsList.empty();
                    if (result.data.length === 0) {
                        sessionsList.html('<div class="text-xs text-slate-500 text-center py-4">No past sessions</div>');
                        return;
                    }
                    result.data.forEach(session => {
                        const isCurrent = session.session_id === currentSessionId;
                        const date = new Date(session.timestamp).toLocaleDateString();
                        const btn = $(`
                            <button class="w-full text-left p-2 hover:bg-slate-100 dark:hover:bg-white/5 rounded-lg mb-1 transition-all flex flex-col gap-1 ${isCurrent ? 'bg-primary/5 dark:bg-white/10 ring-1 ring-primary/30' : ''}">
                                <span class="text-sm text-slate-800 dark:text-slate-200 truncate w-full">${session.preview || 'Empty Session'}</span>
                                <span class="text-[10px] text-slate-500">${date}</span>
                            </button>
                        `);
                        btn.on('click', () => {
                            sessionsDropdown.addClass('hidden');
                            if (!isCurrent) {
                                sessionStorage.setItem('ai_session_id', session.session_id);
                                currentSessionId = session.session_id;
                                chatHistory = [];
                                chatMessages.empty();
                                loadChatHistory();
                            }
                        });
                        sessionsList.append(btn);
                    });
                }
            }
        } catch (err) {
            sessionsList.html('<div class="text-xs text-rose-500 text-center py-4">Failed to load</div>');
        }
    }

    $('#new-chat-btn').off('click').on('click', () => {
        $('#sessions-dropdown').addClass('hidden');
        sessionStorage.removeItem('ai_session_id');
        chatHistory = [];
        $('#chat-messages').empty();
        currentSessionId = 'sess_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
        sessionStorage.setItem('ai_session_id', currentSessionId);
        const msgText = "Hello! I'm your AI Business Manager. How can I assist you today?";
        const msg = addChatMessage('', 'bot', false);
        const formattedHtml = sanitizeHTML(markdownToHtml(msgText, null, null, false));
        msg.target.html(formattedHtml);
        setTimeout(() => {
            mountChartsAndRipples(msg.id);
            injectActionButtons(msg.id, msgText);
        }, 50);
    });

    
    chatInput.off('keypress').on('keypress', (e) => {
        if (e.which === 13) {
            const container = $('#chat-input-container');
            const state = container.attr('data-state');
            if (state === 'send') handleRealSend();
        }
    });

    chatInput.on('input', updateButtonState);

    suggestionBtns.off('click').on('click', function() {
        const text = $(this).text().replace(/[📊🚀👥"]/g, '').trim();
        chatInput.val(text);
        updateButtonState();
        handleRealSend();
    });

    // Style for action button slight transparency bg (not in Tailwind by default)
    const actionBtnStyle = document.createElement('style');
    actionBtnStyle.textContent = `
        .ai-action-btn { background-color: rgba(34,197,94,0.08); }
        .ai-action-btn:hover { background-color: rgba(34,197,94,0.18); }
        .ai-action-buttons:empty { display: none; }
    `;
    document.head.appendChild(actionBtnStyle);

    function updateButtonState() {
        const text = chatInput.val().trim();
        const container = $('#chat-input-container');
        if (text) {
            container.attr('data-state', 'send');
        } else if (isHandsFree) {
            container.attr('data-state', 'cancel');
        } else {
            container.attr('data-state', 'hands-free');
        }
    }

    function handleActionButtonClick() {
        const container = $('#chat-input-container');
        const state = container.attr('data-state');
        if (state === 'send') {
            handleRealSend();
        } else if (state === 'hands-free') {
            enableHandsFree();
        } else if (state === 'cancel') {
            disableHandsFree();
        }
    }

    function enableHandsFree() {
        isHandsFree = true;
        updateButtonState();
        startListening();
    }

    function disableHandsFree() {
        isHandsFree = false;
        updateButtonState();
        stopListening();
    }

    function setupVoiceRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            micBtn.hide(); return;
        }

        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
            micBtn.addClass('listening');
            chatInput.attr('placeholder', 'Listening...');
        };

        recognition.onend = () => {
            micBtn.removeClass('listening');
            chatInput.attr('placeholder', 'Ask anything');
            const text = chatInput.val().trim();
            if (text && !isProcessing) {
                handleRealSend();
            } else if (isHandsFree && !isProcessing) {
                setTimeout(startListening, 1000);
            }
        };

        recognition.onresult = (event) => {
            let transcript = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                transcript += event.results[i][0].transcript;
            }
            chatInput.val(transcript);
            updateButtonState();
        };

        micBtn.off('click').on('click', () => {
            if (micBtn.hasClass('listening')) stopListening(); else startListening();
        });
    }



    function startListening() { if (recognition && !isProcessing) try { recognition.start(); } catch(e) {} }
    function stopListening() { if (recognition) try { recognition.stop(); } catch(e) {} }

    async function handleRealSend() {
        const text = chatInput.val().trim();
        if (!text || isProcessing) return;

        isProcessing = true;
        stopListening();
        chatInput.val('');
        updateButtonState();

        addChatMessage(text, 'user');
        addTypingIndicator();
        chatHistory.push({ role: 'user', content: text });

        const payload = { messages: chatHistory.slice(-10), session_id: currentSessionId };

        try {
            const response = await apiFetch(`${window.FLEZ_API_BASE || ''}/api/user/chat?session_id=${currentSessionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                let errMsg = 'AI connection failed';
                try {
                    const errData = await response.json();
                    if (errData.message) errMsg = errData.message;
                } catch(e) {}
                throw new Error(errMsg);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullAiResponse = "";
            let aiMsgId = null;
            let aiMsgTarget = null;
            let firstChunkReceived = false;
            let thinkStartTime = null;
            let thinkEndTime = null;
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    removeTypingIndicator();
                    if (!firstChunkReceived) {
                        addChatMessage("I couldn't process that response. Please try again.", 'bot');
                    }
                    if (aiMsgTarget && fullAiResponse) {
                        const formattedHtml = sanitizeHTML(markdownToHtml(fullAiResponse, thinkStartTime, thinkEndTime, false));
                        const realTarget = document.querySelector(`#${aiMsgId} .ai-text-target`);
                        if (realTarget) {
                            realTarget.innerHTML = formattedHtml;
                        }
                    }
                    if (aiMsgId) {
                        setTimeout(() => {
                            mountChartsAndRipples(aiMsgId);
                            injectActionButtons(aiMsgId, fullAiResponse);
                        }, 50);
                        $(`#${aiMsgId} .ai-bubble-wrapper`).removeClass('streaming-border');
                    }
                    isProcessing = false;
                    
                    // Scroll to bottom after final render to prevent text cutoff
                    chatMessages.scrollTop(chatMessages[0].scrollHeight);
                    
                    if (isHandsFree) setTimeout(startListening, 500);
                    else updateButtonState();
                    break;
                }
                
                const chunk = decoder.decode(value, { stream: true });
                fullAiResponse += chunk;
                
                if (!firstChunkReceived) {
                    removeTypingIndicator();
                    const result = addChatMessage('', 'bot');
                    aiMsgId = result.id;
                    aiMsgTarget = result.target;
                    firstChunkReceived = true;
                }
                
                // Determine if we are still reasoning (has open <think> without close)
                const isReasoning = fullAiResponse.includes('<think>') && !fullAiResponse.includes('</think>');
                
                if (fullAiResponse.includes('<think>') && !thinkStartTime) {
                    thinkStartTime = Date.now();
                }
                if (fullAiResponse.includes('</think>') && !thinkEndTime) {
                    thinkEndTime = Date.now();
                }
                
                removeTypingIndicator();
                
                // Parse the full accumulated response to prevent broken HTML tags during stream
                const currentHtml = sanitizeHTML(markdownToHtml(fullAiResponse, thinkStartTime, thinkEndTime, true));
                aiMsgTarget.html(currentHtml);
                chatMessages.scrollTop(chatMessages[0].scrollHeight);
            }

            chatHistory.push({ role: 'assistant', content: fullAiResponse });

        } catch (err) {
            console.error('AI Error:', err);
            removeTypingIndicator();
            if (err.message && err.message.includes('AI Business Manager not included')) {
                addChatMessage(`Your active subscription plan doesn't include the AI Business Manager. <a href="/settings" class="text-indigo-600 underline">Upgrade your plan</a> to unlock this feature.`, 'bot');
            } else {
                addChatMessage("I'm having a technical glitch. Please try again.", 'bot');
            }
            isProcessing = false;
            updateButtonState();
            if (isHandsFree) setTimeout(startListening, 2000);
        }
    }

    /**
     * Converts a Markdown string to safe, styled HTML.
     * Handles: headings (h1-h6), bold, italic, strikethrough, inline code,
     * fenced code blocks, blockquotes, ordered & unordered lists, horizontal
     * rules, and plain paragraphs. The result is then run through sanitizeHTML.
     */
    function markdownToHtml(md, thinkStartTime = null, thinkEndTime = null, isStreaming = false) {
        if (!md) return '';
        let html = md;

        // ── Normalise line endings ──────────────────────────────────────────────
        html = html.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

        // ── Handle <channel|> tags for models (e.g. Gemma 3/4 reasoning separator) ─
        if (html.includes('<channel|>')) {
            const channelParts = html.split('<channel|>');
            let thoughtPart = channelParts[0].trim();
            if (!thoughtPart.startsWith('<think>')) {
                thoughtPart = '<think>\n' + thoughtPart;
            }
            if (!thoughtPart.endsWith('</think>')) {
                thoughtPart = thoughtPart + '\n</think>';
            }
            const responsePart = channelParts.slice(1).join('\n\n').trim();
            html = thoughtPart + '\n\n' + responsePart;
        }

        // ── Handle <think> tags for reasoning models ────────────────────────────
        // Merge adjacent <think> blocks (e.g. backend faux loading block + model's native reasoning block)
        html = html.replace(/<\/think>\s*<think>/g, '\n\n');

        let thinkCount = (html.match(/<think>/g) || []).length;
        let endThinkCount = (html.match(/<\/think>/g) || []).length;
        let isReasoning = thinkCount > endThinkCount;
        
        let savedThoughtTime = null;
        const timeMatch = html.match(/<!-- THOUGHT_TIME:\s*([\d.]+) -->/);
        if (timeMatch) {
            savedThoughtTime = parseFloat(timeMatch[1]);
            html = html.replace(timeMatch[0], '');
        }
        
        if (isReasoning) {
            html += '</think>';
        }
        
        function formatThoughtContent(thinking, isReasoning) {
            if (!thinking) return '<span class="opacity-50 animate-pulse">...</span>';

            // Strip HTML comments (e.g. keepalive / heartbeats)
            let raw = thinking.replace(/<!--[\s\S]*?-->/g, '').trim();
            if (!raw) return '<span class="opacity-50 animate-pulse">...</span>';

            // Split into lines
            const rawLines = raw.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
            
            const statusPrefixes = [
                "Evaluating business context",
                "Analyzing performance data",
                "Reviewing financial history",
                "Structuring recommendations",
                "Finalizing insights",
                "Still processing",
                "Fetching requested business records",
                "Formatting response"
            ];

            const isStatusLine = (line) => statusPrefixes.some(p => line.startsWith(p));

            const statusSteps = [];
            const reasoningLines = [];

            for (let i = 0; i < rawLines.length; i++) {
                const line = rawLines[i];
                if (isStatusLine(line)) {
                    // Deduplicate repeated "Still processing..." lines so it appears at most once
                    if (line.startsWith("Still processing")) {
                        if (!statusSteps.some(s => s.startsWith("Still processing"))) {
                            statusSteps.push(line);
                        }
                    } else {
                        // Deduplicate consecutive identical status steps
                        if (statusSteps.length === 0 || statusSteps[statusSteps.length - 1] !== line) {
                            statusSteps.push(line);
                        }
                    }
                } else {
                    reasoningLines.push(line);
                }
            }

            let outputHtml = '';

            if (statusSteps.length > 0) {
                outputHtml += '<div class="space-y-1.5 py-1 font-sans text-xs sm:text-sm">';
                
                statusSteps.forEach((step, idx) => {
                    const isLastStep = (idx === statusSteps.length - 1) && (reasoningLines.length === 0);
                    const isCompleted = !isReasoning || !isLastStep;

                    const escapedStep = step
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;');

                    if (isCompleted) {
                        outputHtml += `
                            <div class="flex items-center gap-2 text-slate-500 dark:text-slate-400">
                                <svg class="w-3.5 h-3.5 text-emerald-500 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                    <polyline points="20 6 9 17 4 12"></polyline>
                                </svg>
                                <span>${escapedStep}</span>
                            </div>
                        `;
                    } else {
                        // Active step: rotating cog
                        outputHtml += `
                            <div class="flex items-center gap-2 text-emerald-600 dark:text-primary font-medium">
                                <svg class="w-3.5 h-3.5 animate-spin text-emerald-600 dark:text-primary shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <circle cx="12" cy="12" r="3"></circle>
                                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                                </svg>
                                <span>${escapedStep}</span>
                            </div>
                        `;
                    }
                });

                outputHtml += '</div>';
            }

            if (reasoningLines.length > 0) {
                const escapedReasoning = reasoningLines.join('\n')
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/\n+/g, '<br>');

                outputHtml += `<div class="mt-2 text-slate-600 dark:text-slate-300 leading-relaxed text-xs sm:text-sm font-sans">${escapedReasoning}</div>`;
            }

            return outputHtml || '<span class="opacity-50">...</span>';
        }

        // Extract thinking block vs body BEFORE card formatting
        let thoughtHtml = '';
        const thinkMatch = html.match(/<think>([\s\S]*?)<\/think>/);
        if (thinkMatch) {
            const thinking = thinkMatch[1];
            html = html.replace(thinkMatch[0], '').trim();

            const cogIcon = `<svg class="w-4 h-4 animate-spin shrink-0 mr-2 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>`;
            const lightbulbIcon = `<svg class="w-[18px] h-[18px] shrink-0 mr-2 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path></svg>`;
            const contentHtml = formatThoughtContent(thinking, isReasoning);

            if (isReasoning) {
                thoughtHtml = `<div class="ai-thought-block streaming">
                    <div class="ai-thought-header flex items-center text-slate-800 dark:text-slate-200 font-semibold">
                        ${cogIcon}
                        <span>Thinking...</span>
                    </div>
                    <div class="ai-thought-content">${contentHtml}</div>
                </div>`;
            } else {
                let secondsText = "Thought Process";
                if (thinkStartTime && thinkEndTime) {
                    const seconds = ((thinkEndTime - thinkStartTime) / 1000).toFixed(1);
                    secondsText = `Thought for ${seconds} seconds`;
                } else if (savedThoughtTime) {
                    secondsText = `Thought for ${savedThoughtTime.toFixed(1)} seconds`;
                } else {
                    const estimatedSeconds = Math.max(1.0, (thinking.length / 60)).toFixed(1);
                    secondsText = `Thought for ${estimatedSeconds} seconds`;
                }
                thoughtHtml = `<details class="ai-thought-block collapsed">
                    <summary class="ai-thought-header cursor-pointer select-none outline-none flex items-center text-slate-800 dark:text-slate-200 hover:text-slate-950 dark:hover:text-white font-semibold transition-colors">
                        ${lightbulbIcon}
                        <span class="text-slate-800 dark:text-slate-200 font-semibold">${secondsText}</span>
                    </summary>
                    <div class="ai-thought-content mt-3">${contentHtml}</div>
                </details>`;
            }
        }

        if (!html) {
            return thoughtHtml;
        }

        const cardsHtml = renderMarkdownBodyToCards(html, isStreaming);
        return thoughtHtml ? `${thoughtHtml}\n${cardsHtml}` : cardsHtml;
    }

    /**
     * Formats markdown elements (tables, code, typography, lists) inside cards.
     */
    function formatMarkdownElements(md) {
        if (!md) return '';
        let html = md;

        // ── Normalize bold/italic numbered lists BEFORE any formatting ─────────
        // e.g. "**1. Title**" -> "1. **Title**", "**1.** Title" -> "1. Title"
        html = html.replace(/^\*\*(\d+)\.\s*([^*]+)\*\*/gm, '$1. **$2**');
        html = html.replace(/^\*\*(\d+)\.\*\*\s*/gm, '$1. ');
        html = html.replace(/^\*(\d+)\.\s*([^*]+)\*/gm, '$1. *$2*');
        html = html.replace(/^(\d+)\.\s+(?:\1|\d+)\.\s+/gm, '$1. ');
        html = html.replace(/^(\d+)\.\s+\*\*(?:\1|\d+)\.\*\*\s*/gm, '$1. ');
        html = html.replace(/^\*\*(\d+)\.\*\*\s+(?:\1|\d+)\.\s*/gm, '$1. ');

        // ── Tables ─────────────────────────────────────────────────────────────
        html = html.replace(/((?:\|[^\n]+\|\n?)+)/g, (tableMatch) => {
            const rows = tableMatch.trim().split('\n').filter(r => r.includes('|'));
            if (rows.length < 2) return tableMatch;
            let headerRow = rows[0];
            let dataRows = rows.slice(1);
            if (dataRows[0] && /^\|[\s-:]+\|$/.test(dataRows[0].replace(/\|/g, '|').trim())) {
                dataRows = dataRows.slice(1);
            }
            const ths = headerRow.split('|').map(c => c.trim()).filter((c, i, a) => i > 0 && i < a.length - 1);
            const thHtml = ths.map(h => `<th class="px-3 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-white/10 uppercase tracking-wider">${h}</th>`).join('');
            
            const trsHtml = dataRows.map(row => {
                const tds = row.split('|').map(c => c.trim()).filter((c, i, a) => i > 0 && i < a.length - 1);
                return `<tr class="border-b border-slate-100 dark:border-white/5 hover:bg-white/5 transition-colors">${tds.map(d => `<td class="px-3 py-2 text-xs sm:text-sm text-slate-700 dark:text-slate-300">${d}</td>`).join('')}</tr>`;
            }).join('');

            return `<div class="overflow-x-auto my-3 rounded-xl border border-slate-200/80 dark:border-white/10 bg-white/40 dark:bg-black/20"><table class="w-full text-left border-collapse"><thead><tr class="bg-slate-50/50 dark:bg-white/5">${thHtml}</tr></thead><tbody>${trsHtml}</tbody></table></div>`;
        });

        // ── Fenced code blocks (``` … ```) ─────────────────────────────────────
        html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
            const escaped = code.trim()
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            const langLabel = lang ? `<span class="ai-code-lang">${lang}</span>` : '';
            return `<div class="ai-code-block">${langLabel}<pre><code>${escaped}</code></pre></div>`;
        });

        // ── Inline code (`…`) ───────────────────────────────────────────────────
        html = html.replace(/`([^`]+)`/g, '<code class="ai-inline-code">$1</code>');

        // ── Headings (# … ######) ───────────────────────────────────────────────
        html = html.replace(/^#{6}\s+(.+)$/gm, '<h6 class="ai-h6 font-display font-semibold text-slate-800 dark:text-slate-100 text-xs mt-2 mb-1">$1</h6>');
        html = html.replace(/^#{5}\s+(.+)$/gm, '<h5 class="ai-h5 font-display font-semibold text-slate-800 dark:text-slate-100 text-xs mt-2 mb-1">$1</h5>');
        html = html.replace(/^#{4}\s+(.+)$/gm, '<h4 class="ai-h4 font-display font-semibold text-slate-800 dark:text-slate-100 text-sm mt-2.5 mb-1">$1</h4>');
        html = html.replace(/^#{3}\s+(.+)$/gm, '<h3 class="ai-h3 font-display font-bold text-slate-900 dark:text-white text-base mt-3 mb-1.5">$1</h3>');
        html = html.replace(/^#{2}\s+(.+)$/gm, '<h2 class="ai-h2 font-display font-bold text-slate-900 dark:text-white text-lg mt-3 mb-1.5">$1</h2>');
        html = html.replace(/^#{1}\s+(.+)$/gm, '<h1 class="ai-h1 font-display font-bold text-slate-900 dark:text-white text-xl mt-3.5 mb-2">$1</h1>');

        // ── Horizontal rule (---, ***, ___) ────────────────────────────────────
        html = html.replace(/^(\-{3,}|\*{3,}|_{3,})$/gm, '<hr class="ai-hr my-3 border-slate-200/70 dark:border-white/10">');

        // ── Blockquotes (> …) ───────────────────────────────────────────────────
        html = html.replace(/^>\s?(.+)$/gm, '<blockquote class="ai-blockquote border-l-2 border-primary/60 pl-3 py-1 my-2 text-slate-500 dark:text-slate-400 italic text-sm">$1</blockquote>');
        html = html.replace(/<\/blockquote>\n<blockquote class="ai-blockquote[^>]*">/g, '\n');

        // ── Bold + Italic (***…***) ─────────────────────────────────────────────
        html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');

        // ── Bold (**…** or __…__) ───────────────────────────────────────────────
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="font-bold text-slate-900 dark:text-white">$1</strong>');
        html = html.replace(/__(.+?)__/g, '<strong class="font-bold text-slate-900 dark:text-white">$1</strong>');

        // ── Italic (*…* or _…_) ─────────────────────────────────────────────────
        html = html.replace(/\*([^\s*][^*]*)\*/g, '<em class="italic text-slate-600 dark:text-slate-300">$1</em>');
        html = html.replace(/_([^\s_][^_]*)_/g, '<em class="italic text-slate-600 dark:text-slate-300">$1</em>');

        // ── Strikethrough (~~…~~) ───────────────────────────────────────────────
        html = html.replace(/~~(.+?)~~/g, '<del class="line-through text-slate-400">$1</del>');

        // ── Lists Design: Colorful Inline Backgrounds & Compact Line Height ─────
        const listThemes = [
            {
                badge: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/25',
                pill: 'bg-emerald-500/[0.08] dark:bg-emerald-500/[0.14] border-emerald-500/20 text-slate-800 dark:text-slate-100',
                dot: 'bg-emerald-500'
            },
            {
                badge: 'bg-violet-500/15 text-violet-600 dark:text-violet-400 border-violet-500/25',
                pill: 'bg-violet-500/[0.08] dark:bg-violet-500/[0.14] border-violet-500/20 text-slate-800 dark:text-slate-100',
                dot: 'bg-violet-500'
            },
            {
                badge: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/25',
                pill: 'bg-amber-500/[0.08] dark:bg-amber-500/[0.14] border-amber-500/20 text-slate-800 dark:text-slate-100',
                dot: 'bg-amber-500'
            },
            {
                badge: 'bg-cyan-500/15 text-cyan-600 dark:text-cyan-400 border-cyan-500/25',
                pill: 'bg-cyan-500/[0.08] dark:bg-cyan-500/[0.14] border-cyan-500/20 text-slate-800 dark:text-slate-100',
                dot: 'bg-cyan-500'
            },
            {
                badge: 'bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/25',
                pill: 'bg-rose-500/[0.08] dark:bg-rose-500/[0.14] border-rose-500/20 text-slate-800 dark:text-slate-100',
                dot: 'bg-rose-500'
            }
        ];

        // ── Lists: Robust Multi-line Processing & Colorful Inline Backgrounds ──
        // Step 1: Clean duplicate numbers like "1. 1. "
        html = html.replace(/^(\d+)\.\s+(?:\1|\d+)\.\s+/gm, '$1. ');

        const rawLines = html.split('\n');
        const processedLines = [];
        let inList = false;
        let listType = null; // 'ol' or 'ul'
        let currentListItem = null;
        let itemIndex = 0;

        for (let i = 0; i < rawLines.length; i++) {
            const line = rawLines[i];
            const trimmed = line.trim();

            const olMatch = trimmed.match(/^(\d+)\.\s+(.+)$/);
            const ulMatch = !olMatch && trimmed.match(/^[\*\-\+]\s+(.+)$/);

            if (olMatch) {
                if (currentListItem) {
                    processedLines.push(currentListItem);
                    currentListItem = null;
                }
                if (!inList || listType !== 'ol') {
                    if (inList) processedLines.push(listType === 'ol' ? '</ol>' : '</ul>');
                    processedLines.push('<ol class="ai-ol my-2.5 space-y-2">');
                    inList = true;
                    listType = 'ol';
                    itemIndex = 0;
                }
                const content = olMatch[2];
                const t = listThemes[itemIndex % listThemes.length];
                itemIndex++;
                currentListItem = { type: 'ol', num: itemIndex, theme: t, contentParts: [content] };
            } else if (ulMatch) {
                if (currentListItem) {
                    processedLines.push(currentListItem);
                    currentListItem = null;
                }
                if (!inList || listType !== 'ul') {
                    if (inList) processedLines.push(listType === 'ol' ? '</ol>' : '</ul>');
                    processedLines.push('<ul class="ai-ul my-2.5 space-y-2">');
                    inList = true;
                    listType = 'ul';
                    itemIndex = 0;
                }
                const content = ulMatch[1];
                const t = listThemes[itemIndex % listThemes.length];
                itemIndex++;
                currentListItem = { type: 'ul', num: itemIndex, theme: t, contentParts: [content] };
            } else if (inList && !trimmed) {
                // Check if subsequent non-empty line continues this list
                let hasNextItem = false;
                for (let j = i + 1; j < rawLines.length; j++) {
                    const nextTrim = rawLines[j].trim();
                    if (!nextTrim) continue;
                    if ((listType === 'ol' && /^\d+\.\s+/.test(nextTrim)) || (listType === 'ul' && /^[\*\-\+]\s+/.test(nextTrim))) {
                        hasNextItem = true;
                    }
                    break;
                }
                if (hasNextItem) {
                    if (currentListItem) {
                        processedLines.push(currentListItem);
                        currentListItem = null;
                    }
                } else {
                    if (currentListItem) {
                        processedLines.push(currentListItem);
                        currentListItem = null;
                    }
                    processedLines.push(listType === 'ol' ? '</ol>' : '</ul>');
                    inList = false;
                    listType = null;
                    processedLines.push(line);
                }
            } else if (inList && trimmed && !/^<(?:h[1-6]|table|div|blockquote|pre|hr)/i.test(trimmed) && !/^(?:###|##|#|```|---|===)/.test(trimmed) && !/^(?:How about|Would you|Shall I|Do you want)/i.test(trimmed)) {
                if (currentListItem) {
                    currentListItem.contentParts.push(trimmed);
                } else {
                    processedLines.push(line);
                }
            } else {
                if (currentListItem) {
                    processedLines.push(currentListItem);
                    currentListItem = null;
                }
                if (inList) {
                    processedLines.push(listType === 'ol' ? '</ol>' : '</ul>');
                    inList = false;
                    listType = null;
                }
                processedLines.push(line);
            }
        }
        if (currentListItem) processedLines.push(currentListItem);
        if (inList) processedLines.push(listType === 'ol' ? '</ol>' : '</ul>');

        html = processedLines.map(it => {
            if (typeof it === 'string') return it;
            const formattedContent = it.contentParts.map((part, idx) => {
                part = part.trim();
                if (idx === 0) return part;
                return `<span class="block mt-0.5 text-xs sm:text-[13px] opacity-90 leading-snug">${part}</span>`;
            }).join('');

            if (it.type === 'ol') {
                return `<li class="ai-li ai-oli flex items-start gap-2 my-1 leading-snug"><span class="ai-li-badge shrink-0 flex items-center justify-center w-5 h-5 mt-0.5 rounded-md text-[11px] font-bold border ${it.theme.badge}">${it.num}</span><div class="ai-li-text flex-1 px-2.5 py-1 rounded-lg text-xs sm:text-[13px] leading-snug border ${it.theme.pill}">${formattedContent}</div></li>`;
            } else {
                return `<li class="ai-li flex items-start gap-2 my-1 leading-snug"><span class="ai-li-badge shrink-0 flex items-center justify-center w-5 h-5 mt-0.5 rounded-md border ${it.theme.badge}"><span class="w-1.5 h-1.5 rounded-full ${it.theme.dot}"></span></span><div class="ai-li-text flex-1 px-2.5 py-1 rounded-lg text-xs sm:text-[13px] leading-snug border ${it.theme.pill}">${formattedContent}</div></li>`;
            }
        }).join('\n');

        // ── Paragraphs ──────────────────────────────────────────────────────────
        const blockTags = /^<(h[1-6]|ul|ol|li|blockquote|div|pre|hr|table)/;
        const lines = html.split(/\n\n+/);
        html = lines.map(block => {
            block = block.trim();
            if (!block) return '';
            if (blockTags.test(block)) return block;
            const withBr = block.replace(/\n/g, '<br>');
            return `<p class="ai-p text-sm sm:text-[15px] leading-relaxed text-slate-700 dark:text-slate-300 mb-2.5 last:mb-0">${withBr}</p>`;
        }).join('\n');

        return html;
    }

    /**
     * Transforms raw body markdown into beautiful, colorful minimal cards with ripple entrance animations.
     */
    function renderMarkdownBodyToCards(bodyMd, isStreaming = false) {
        if (!bodyMd || !bodyMd.trim()) return '';

        let text = bodyMd.trim();
        // Clean out developer preamble or mechanical labels if present
        text = text.replace(/^(?:Executing Tool|The AI will execute|Executing tool call)[\s\S]*?(?:Executing tool call\.\.\.|\n\n)/i, '').trim();
        text = text.replace(/\bDelivery Confirmation:\s*/gi, '');
        text = text.replace(/\bExecuting tool call\.\.\.\s*/gi, '');

        let cardIndex = 0;
        const cardsHtml = [];

        // 1. Detect and extract chart blocks: ```chart ... ``` or ```json with type/data
        const chartRegex = /```(?:chart|json)\s*([\s\S]*?)\s*```/gi;
        const extractedCharts = [];

        text = text.replace(chartRegex, (fullMatch, jsonStr) => {
            try {
                const parsed = JSON.parse(jsonStr.trim());
                if (parsed && (parsed.data || parsed.datasets) && (parsed.labels || parsed.data)) {
                    extractedCharts.push(parsed);
                    return `\n<!-- CHART_PLACEHOLDER_${extractedCharts.length - 1} -->\n`;
                }
            } catch(e) {}
            return fullMatch;
        });

        // If streaming and there is an unclosed chart block
        if (isStreaming && /```(?:chart|json)\s*\{/i.test(text)) {
            text = text.replace(/```(?:chart|json)\s*\{[\s\S]*$/i, '\n<!-- CHART_STREAMING -->\n');
        }

        // 2. Scan text for actionable deep links
        const detectedActions = [];
        const lowerText = text.toLowerCase();

        // Suppress action buttons when user or assistant dispatched emails directly from chat
        const isDirectEmailConfirmation = lowerText.includes('sent payment follow-up email') ||
            lowerText.includes('dispatched custom promotional emails') ||
            (lowerText.includes('successfully sent') && lowerText.includes('email')) ||
            lowerText.includes('sent promotional email');

        if (!isDirectEmailConfirmation) {
            const ACTION_CATALOG = [
                { key: 'analytics', label: 'View Analytics', desc: 'Inspect trends & sales volume', icon: 'bar-chart-3', target: '/analytics', color: 'emerald', match: ['analytic', 'sales report', 'performance data', 'revenue breakdown', 'sales trend'] },
                { key: 'pos', label: 'Open POS', desc: 'Fast checkout & register', icon: 'monitor', target: '/pos', color: 'cyan', match: ['pos', 'point of sale', 'cashier', 'checkout', 'register'] },
                { key: 'products', label: 'Manage Products', desc: 'Stock inventory & pricing', icon: 'shopping-bag', target: '/products', color: 'cyan', match: ['product inventory', 'stock levels', 'cost price', 'low stock items'] },
                { key: 'invoices', label: 'Invoices & Billing', desc: 'Track pending & overdue bills', icon: 'file-text', target: '/invoices', color: 'amber', match: ['unpaid invoices', 'overdue bills', 'track debts'] },
                { key: 'payroll', label: 'Run Payroll', desc: 'Disburse staff wages', icon: 'banknote', target: '/payroll', color: 'violet', match: ['payroll', 'salary', 'salaries', 'wages', 'disbursement'] },
                { key: 'wallet', label: 'My Wallet', desc: 'Balances & fund transfers', icon: 'wallet-2', target: '/wallet', color: 'emerald', match: ['wallet', 'balance', 'withdraw', 'fund wallet'] },
                { key: 'staff', label: 'Staff & Roles', desc: 'Team members directory', icon: 'users', target: '/organization', color: 'violet', match: ['staff directory', 'employee roles', 'cashiers directory'] },
                { key: 'growth', label: 'Campaigns', desc: 'Promotions & customer reach', icon: 'zap', target: '/growth', color: 'rose', match: ['growth campaigns', 'marketing campaigns'] },
                { key: 'settings', label: 'VAT / Tax Settings', desc: 'Configure business tax rate', icon: 'settings', target: '/settings', color: 'violet', match: ['tax settings', 'configure vat', 'vat percentage', 'tax rate'] }
            ];

            for (const act of ACTION_CATALOG) {
                if (act.match.some(m => lowerText.includes(m))) {
                    if (!detectedActions.some(a => a.key === act.key)) {
                        detectedActions.push(act);
                    }
                }
                if (detectedActions.length >= 3) break;
            }
        }

        // 3. Extract KPI items if present (e.g. bullet points highlighting numbers/currency)
        const lines = text.split('\n');
        const kpiItems = [];
        const remainingLines = [];

        const kpiPattern = /^[\*\-\+]\s*([^:*]+)[:–-]\s*\*\*([^*]+)\*\*(?:\s*\(([^*]+)\))?/i;
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            const m = line.match(kpiPattern);
            if (m && (m[2].includes('₦') || m[2].includes('$') || m[2].includes('%') || !isNaN(m[2].replace(/,/g, '')))) {
                kpiItems.push({
                    label: m[1].trim(),
                    value: m[2].trim(),
                    badge: m[3] ? m[3].trim() : ''
                });
            } else {
                remainingLines.push(lines[i]);
            }
        }

        let processedText = remainingLines.join('\n');
        if (kpiItems.length < 2) {
            processedText = text;
            kpiItems.length = 0;
        }

        // 4. Render Extracted Charts into Chart Cards
        extractedCharts.forEach((chartCfg, idx) => {
            const canvasId = `ai-chart-${Date.now()}-${idx}-${Math.floor(Math.random()*1000)}`;
            const themeColor = chartCfg.color || 'emerald';
            const chartType = chartCfg.type || 'bar';
            const chartTitle = chartCfg.title || 'Performance Metric';
            const typeIcon = chartType === 'line' ? 'trending-up' : (chartType === 'doughnut' || chartType === 'pie' ? 'pie-chart' : 'bar-chart-2');
            const cardClass = isStreaming ? 'ai-card-streaming' : 'ai-card-animated';
            const cardStyle = isStreaming ? '' : `style="--card-index: ${cardIndex++};"`;

            const chartCardHtml = `
                <div class="${cardClass} ai-card-${themeColor} p-4 sm:p-5" ${cardStyle}>
                    <div class="flex items-center justify-between gap-3 mb-2">
                        <div class="flex items-center gap-2">
                            <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold tracking-wide uppercase bg-${themeColor}-500/15 text-${themeColor}-600 dark:text-${themeColor}-400 border border-${themeColor}-500/25">
                                <i data-lucide="${typeIcon}" class="w-3.5 h-3.5"></i>
                                ${chartTitle}
                            </span>
                        </div>
                        <span class="text-[10px] text-slate-400 dark:text-slate-500 font-medium uppercase tracking-wider">${chartType} chart</span>
                    </div>
                    <div class="ai-chart-canvas-wrap">
                        <canvas id="${canvasId}" data-chart-config="${encodeURIComponent(JSON.stringify(chartCfg))}"></canvas>
                    </div>
                </div>
            `;
            processedText = processedText.replace(`<!-- CHART_PLACEHOLDER_${idx} -->`, chartCardHtml);
        });

        if (processedText.includes('<!-- CHART_STREAMING -->')) {
            const streamingChartPlaceholder = `
                <div class="ai-card-streaming ai-card-emerald p-4 sm:p-5 flex items-center gap-3 text-xs font-semibold text-emerald-500">
                    <svg class="w-4 h-4 animate-spin text-emerald-500 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle><path d="M12 2a10 10 0 0 1 10 10"></path></svg>
                    <span>Generating visual chart...</span>
                </div>
            `;
            processedText = processedText.replace('<!-- CHART_STREAMING -->', streamingChartPlaceholder);
        }

        // 5. Render KPI Card if extracted
        if (kpiItems.length >= 2) {
            const cardClass = isStreaming ? 'ai-card-streaming' : 'ai-card-animated';
            const cardStyle = isStreaming ? '' : `style="--card-index: ${cardIndex++};"`;
            cardsHtml.push(`
                <div class="${cardClass} ai-card-emerald p-4 sm:p-5" ${cardStyle}>
                    <div class="flex items-center justify-between gap-3 mb-3">
                        <div class="flex items-center gap-2">
                            <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold tracking-wide uppercase bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25">
                                <i data-lucide="trending-up" class="w-3.5 h-3.5"></i>
                                Key Metrics Overview
                            </span>
                        </div>
                    </div>
                    <div class="ai-kpi-grid">
                        ${kpiItems.map(item => `
                            <div class="ai-kpi-pill flex flex-col justify-between">
                                <span class="text-xs text-slate-500 dark:text-slate-400 truncate mb-1">${item.label}</span>
                                <div class="flex items-baseline gap-2 flex-wrap">
                                    <span class="text-base sm:text-lg font-bold text-slate-900 dark:text-white font-display tracking-tight">${item.value}</span>
                                    ${item.badge ? `<span class="text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">${item.badge}</span>` : ''}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `);
        }

        // 6. Convert remaining markdown and separate chart cards from text cards
        const standardHtml = formatMarkdownElements(processedText);
        const parts = standardHtml.split(/(<div class="(?:ai-card-animated|ai-card-streaming)[\s\S]*?<\/div>\s*<\/div>)/g);

        for (let part of parts) {
            part = part.trim();
            if (!part) continue;

            if (part.startsWith('<div class="ai-card-animated') || part.startsWith('<div class="ai-card-streaming')) {
                cardsHtml.push(part);
            } else {
                let themeColor = 'violet';
                let badgeText = 'Strategic Insight';
                let badgeIcon = 'zap';

                const lowerPart = part.toLowerCase();
                if (lowerPart.includes('sale') || lowerPart.includes('revenue') || lowerPart.includes('profit') || lowerPart.includes('growth')) {
                    themeColor = 'emerald';
                    badgeText = 'Financial Insight';
                    badgeIcon = 'trending-up';
                } else if (lowerPart.includes('inventory') || lowerPart.includes('stock') || lowerPart.includes('product')) {
                    themeColor = 'cyan';
                    badgeText = 'Inventory & Catalog';
                    badgeIcon = 'shopping-bag';
                } else if (lowerPart.includes('overdue') || lowerPart.includes('debt') || lowerPart.includes('risk') || lowerPart.includes('warning') || lowerPart.includes('alert')) {
                    themeColor = 'amber';
                    badgeText = 'Attention Required';
                    badgeIcon = 'alert-triangle';
                }

                const cardClass = isStreaming ? 'ai-card-streaming' : 'ai-card-animated';
                const cardStyle = isStreaming ? '' : `style="--card-index: ${cardIndex++};"`;

                cardsHtml.push(`
                    <div class="${cardClass} ai-card-${themeColor} p-4 sm:p-5" ${cardStyle}>
                        <div class="flex items-center justify-between gap-3 mb-2.5">
                            <div class="flex items-center gap-2">
                                <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold tracking-wide uppercase bg-${themeColor}-500/15 text-${themeColor}-600 dark:text-${themeColor}-400 border border-${themeColor}-500/25">
                                    <i data-lucide="${badgeIcon}" class="w-3.5 h-3.5"></i>
                                    ${badgeText}
                                </span>
                            </div>
                        </div>
                        <div class="ai-prose text-sm sm:text-[15px] leading-relaxed text-slate-700 dark:text-slate-200">
                            ${part}
                        </div>
                    </div>
                `);
            }
        }

        // 7. Append Actionable Links Card if actions were detected
        if (detectedActions.length > 0 && !isStreaming) {
            cardsHtml.push(`
                <div class="ai-card-animated ai-card-cyan p-4 sm:p-5" style="--card-index: ${cardIndex++};">
                    <div class="flex items-center justify-between gap-3 mb-2.5">
                        <div class="flex items-center gap-2">
                            <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold tracking-wide uppercase bg-cyan-500/15 text-cyan-600 dark:text-cyan-400 border border-cyan-500/25">
                                <i data-lucide="zap" class="w-3.5 h-3.5"></i>
                                Actionable Next Steps
                            </span>
                        </div>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
                        ${detectedActions.map(act => `
                            <a href="${act.target}" class="ai-action-link-card ai-ripple-container p-2.5 sm:p-3 rounded-xl bg-white/60 dark:bg-white/5 hover:bg-cyan-500/10 dark:hover:bg-cyan-500/15 border border-slate-200 dark:border-white/10 hover:border-cyan-500/30 flex items-center justify-between gap-3 group/act">
                                <div class="flex items-center gap-2.5 min-w-0">
                                    <div class="w-8 h-8 rounded-lg bg-cyan-500/15 text-cyan-600 dark:text-cyan-400 flex items-center justify-center shrink-0">
                                        <i data-lucide="${act.icon}" class="w-4 h-4"></i>
                                    </div>
                                    <div class="flex flex-col min-w-0">
                                        <span class="text-xs font-bold text-slate-800 dark:text-slate-200 truncate group-hover/act:text-cyan-600 dark:group-hover/act:text-cyan-400 transition-colors">${act.label}</span>
                                        <span class="text-[10px] text-slate-400 dark:text-slate-500 truncate">${act.desc}</span>
                                    </div>
                                </div>
                                <i data-lucide="arrow-up-right" class="w-4 h-4 text-slate-400 group-hover/act:text-cyan-400 action-arrow-icon shrink-0"></i>
                            </a>
                        `).join('')}
                    </div>
                </div>
            `);
        }

        return cardsHtml.join('\n');
    }

    /**
     * Mounts Chart.js instances on all canvas elements with data-chart-config inside scope,
     * and refreshes Lucide icons.
     */
    window.aiChartInstances = window.aiChartInstances || {};

    function mountChartsAndRipples(scopeId) {
        const scope = scopeId ? document.getElementById(scopeId) : document;
        if (!scope) return;

        const canvases = scope.querySelectorAll('canvas[data-chart-config]');
        canvases.forEach(canvas => {
            const rawConfig = canvas.getAttribute('data-chart-config');
            if (!rawConfig) return;
            try {
                const config = JSON.parse(decodeURIComponent(rawConfig));
                const canvasId = canvas.id;
                if (window.aiChartInstances[canvasId]) {
                    window.aiChartInstances[canvasId].destroy();
                }
                if (typeof Chart === 'undefined') return;

                const isDark = document.documentElement.classList.contains('dark');
                const colorName = config.color || 'emerald';
                
                const colorMap = {
                    emerald: { stroke: '#10b981', fill: isDark ? 'rgba(16, 185, 129, 0.2)' : 'rgba(16, 185, 129, 0.15)' },
                    violet: { stroke: '#8b5cf6', fill: isDark ? 'rgba(139, 92, 246, 0.2)' : 'rgba(139, 92, 246, 0.15)' },
                    cyan: { stroke: '#06b6d4', fill: isDark ? 'rgba(6, 182, 212, 0.2)' : 'rgba(6, 182, 212, 0.15)' },
                    amber: { stroke: '#f59e0b', fill: isDark ? 'rgba(245, 158, 11, 0.2)' : 'rgba(245, 158, 11, 0.15)' },
                    rose: { stroke: '#f43f5e', fill: isDark ? 'rgba(244, 63, 94, 0.2)' : 'rgba(244, 63, 94, 0.15)' }
                };
                const theme = colorMap[colorName] || colorMap.emerald;
                const chartType = config.type || 'bar';

                const dataset = {
                    label: config.title || 'Revenue',
                    data: config.data || [],
                    borderColor: theme.stroke,
                    backgroundColor: chartType === 'line' ? theme.fill : (config.data || []).map((_, i) => {
                        const palettes = ['#10b981', '#06b6d4', '#8b5cf6', '#f59e0b', '#f43f5e', '#3b82f6'];
                        return chartType === 'doughnut' ? palettes[i % palettes.length] : theme.stroke;
                    }),
                    borderWidth: chartType === 'line' ? 2.5 : 0,
                    borderRadius: chartType === 'bar' ? 6 : 0,
                    fill: chartType === 'line',
                    tension: 0.35,
                    pointRadius: chartType === 'line' ? 3 : 0,
                    pointHoverRadius: chartType === 'line' ? 5 : 0,
                };

                window.aiChartInstances[canvasId] = new Chart(canvas.getContext('2d'), {
                    type: chartType,
                    data: {
                        labels: config.labels || [],
                        datasets: [dataset]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: { duration: 650, easing: 'easeOutQuart' },
                        plugins: {
                            legend: {
                                display: chartType === 'doughnut' || chartType === 'pie',
                                position: 'bottom',
                                labels: {
                                    color: isDark ? '#94a3b8' : '#475569',
                                    font: { family: 'Inter', size: 11 },
                                    boxWidth: 10,
                                    padding: 10
                                }
                            },
                            tooltip: {
                                backgroundColor: isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.95)',
                                titleColor: isDark ? '#f8fafc' : '#0f172a',
                                bodyColor: isDark ? '#cbd5e1' : '#334155',
                                borderColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                                borderWidth: 1,
                                padding: 8,
                                cornerRadius: 8,
                                callbacks: {
                                    label: function(ctx) {
                                        let val = ctx.parsed.y !== undefined ? ctx.parsed.y : ctx.parsed;
                                        let cur = (window.getUserCurrencySymbol ? window.getUserCurrencySymbol() : (window.STORE_CURRENCY_SYMBOL || '₦'));
                                        return (ctx.dataset.label ? ctx.dataset.label + ': ' : '') + cur + Number(val).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                                    }
                                }
                            }
                        },
                        scales: (chartType === 'doughnut' || chartType === 'pie') ? {} : {
                            x: {
                                grid: { display: false },
                                ticks: {
                                    color: isDark ? '#64748b' : '#94a3b8',
                                    font: { family: 'Inter', size: 11 }
                                }
                            },
                            y: {
                                grid: {
                                    color: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
                                    drawBorder: false
                                },
                                ticks: {
                                    color: isDark ? '#64748b' : '#94a3b8',
                                    font: { family: 'Inter', size: 10 },
                                    callback: function(val) {
                                        if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
                                        if (val >= 1000) return (val / 1000).toFixed(0) + 'k';
                                        return val;
                                    }
                                }
                            }
                        }
                    }
                });
            } catch (err) {
                console.error('Failed to render AI Chart:', err);
            }
        });

        if (typeof lucide !== 'undefined') {
            lucide.createIcons({ root: scope });
        }
    }

    function sanitizeHTML(html) {
        const temp = document.createElement('div');
        temp.innerHTML = html;

        // Remove dangerous tags
        const forbidden = temp.querySelectorAll('script, iframe, object, embed');
        forbidden.forEach(el => el.remove());

        // Remove inline event handlers (onclick, etc.)
        temp.querySelectorAll('*').forEach(el => {
            [...el.attributes].forEach(attr => {
                if (attr.name.startsWith('on')) {
                    el.removeAttribute(attr.name);
                }
            });
        });

        return temp.innerHTML;
    }

    function addChatMessage(text, role = 'user', isSystem = false) {
        const messageId = `msg-${Date.now()}-${Math.floor(Math.random()*1000)}`;
        const messageHtml = role === 'user' ? `
            <div id="${messageId}" class="flex items-start gap-2 justify-end user-message animate-in fade-in slide-in-from-right-5 duration-500 group">
                <button onclick="copyToClipboard(this.nextElementSibling.innerText)" class="mt-4 opacity-0 group-hover:opacity-100 transition-opacity p-2 text-slate-400 hover:text-primary rounded-lg shrink-0" title="Copy to clipboard">
                    <i data-lucide="copy" class="w-4 h-4"></i>
                </button>
                <div class="message-bubble bg-primary text-black font-medium p-4 sm:p-5 rounded-[2rem] rounded-tr-none shadow-xl shadow-primary/10 border border-primary/20">
                    <p class="text-[15px] font-semibold leading-relaxed">${text}</p>
                </div>
            </div>
        ` : `
            <div id="${messageId}" class="flex items-start gap-3 sm:gap-4 ai-message animate-in fade-in slide-in-from-left-5 duration-500 w-full">
                ${isSystem ? `<div class="shrink-0 animate-pulse"><img src="assets/image/voice-chat.png" class="w-10 h-10 object-contain voice-chat-icon"></div>` : ''}
                <div class="flex flex-col gap-3 flex-1 min-w-0 w-full">
                    <div class="ai-cards-container flex flex-col gap-3.5 w-full min-w-0 ai-text-target">
                        ${text}
                    </div>
                    <div class="ai-action-buttons flex flex-wrap gap-2 pl-1"></div>
                </div>
            </div>
        `;
        
        chatMessages.append(messageHtml);
        chatMessages.scrollTop(chatMessages[0].scrollHeight);
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }

        // Return both the message ID and the text target element
        const target = chatMessages.find(`#${messageId} .ai-text-target`);
        return { id: messageId, target };
    }

    /**
     * Injects Copy and Share buttons below the AI message.
     */
    function injectActionButtons(messageId, responseText) {
        const container = $(`#${messageId} .ai-action-buttons`);
        if (!container.length) return;

        // Leave only the share and copy buttons
        const utilityBtns = $(`
            <button
                class="ai-utility-btn flex items-center justify-center w-8 h-8 rounded-xl text-slate-400
                       hover:bg-slate-100 dark:hover:bg-white/10 hover:text-slate-600 dark:hover:text-slate-200
                       transition-all duration-200"
                title="Copy to clipboard"
            >
                <i data-lucide="copy" class="w-4 h-4"></i>
            </button>
            <button
                class="ai-utility-btn flex items-center justify-center w-8 h-8 rounded-xl text-slate-400
                       hover:bg-slate-100 dark:hover:bg-white/10 hover:text-slate-600 dark:hover:text-slate-200
                       transition-all duration-200"
                title="Share"
            >
                <i data-lucide="share-2" class="w-4 h-4"></i>
            </button>
        `);

        // Copy logic
        utilityBtns.eq(0).on('click', async function() {
            try {
                if (window.copyToClipboard) {
                    window.copyToClipboard(responseText, 'AI response copied to clipboard');
                } else if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(responseText);
                    if (window.showToast) window.showToast('Copied!', 'AI response copied to clipboard', 'info');
                } else {
                    const textArea = document.createElement("textarea");
                    textArea.value = responseText;
                    document.body.appendChild(textArea);
                    textArea.select();
                    document.execCommand("copy");
                    textArea.remove();
                    if (window.showToast) window.showToast('Copied!', 'AI response copied to clipboard', 'info');
                }
                const icon = $(this).find('i');
                const origIcon = icon.attr('data-lucide');
                icon.attr('data-lucide', 'check');
                if (typeof lucide !== 'undefined') lucide.createIcons({ root: this });
                setTimeout(() => {
                    icon.attr('data-lucide', origIcon);
                    if (typeof lucide !== 'undefined') lucide.createIcons({ root: this });
                }, 2000);
            } catch(e) {
                console.error("Copy failed", e);
            }
        });

        // Share logic
        utilityBtns.eq(1).on('click', async function() {
            if (navigator.share) {
                try {
                    await navigator.share({
                        title: 'AI Insight from FlezPay',
                        text: responseText,
                    });
                } catch(e) {
                    console.error("Share failed", e);
                }
            } else {
                utilityBtns.eq(0).click();
            }
        });

        container.append(utilityBtns);

        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }

        chatMessages.scrollTop(chatMessages[0].scrollHeight);
    }

    function addTypingIndicator() {
        if ($('#typing-indicator').length) return;
        const indicatorId = 'typing-indicator';
        const indicatorHtml = `
            <div id="${indicatorId}" class="flex items-start gap-5 animate-in fade-in duration-300">
                <div class="message-bubble glass-card px-4 py-3 rounded-[2rem] rounded-tl-none border-primary/10 flex gap-3 items-center bg-white/5">
                    <div class="flex gap-1.5 items-center">
                        <div class="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style="animation-delay: 0s"></div>
                        <div class="w-1.5 h-1.5 rounded-full bg-primary/80 animate-bounce" style="animation-delay: 0.15s"></div>
                        <div class="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce" style="animation-delay: 0.3s"></div>
                    </div>
                </div>
            </div>
        `;
        chatMessages.append(indicatorHtml);
        chatMessages.scrollTop(chatMessages[0].scrollHeight);
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons({
                root: document.getElementById(indicatorId)
            });
        }
    }

    function removeTypingIndicator() {
        $('#typing-indicator').remove();
    }
}

(function () {
  const canvas = document.getElementById("ai-bg-canvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");

  let width, height;
  let particles = [];
  const PARTICLE_COUNT = 120;

  // Resize canvas
  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener("resize", resize);

  // Simple noise (smooth wave motion)
  function noise(x, y, t) {
    return Math.sin(x * 0.002 + t) + Math.cos(y * 0.002 + t);
  }

  // Particle class
  class Particle {
    constructor() {
      this.reset();
    }

    reset() {
      this.x = Math.random() * width;
      this.y = Math.random() * height;
      this.vx = 0;
      this.vy = 0;
    }

    update(t) {
      const n = noise(this.x, this.y, t);

      const angle = n * Math.PI * 2;

      this.vx += Math.cos(angle) * 0.1;
      this.vy += Math.sin(angle) * 0.1;

      this.vx *= 0.92;
      this.vy *= 0.92;

      this.x += this.vx;
      this.y += this.vy;

      // Wrap edges
      if (this.x < 0) this.x = width;
      if (this.x > width) this.x = 0;
      if (this.y < 0) this.y = height;
      if (this.y > height) this.y = 0;
    }

    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, 1.2, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Create particles
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    particles.push(new Particle());
  }

  // Draw connections (neural feel)
  function drawConnections() {
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = dx * dx + dy * dy;

        if (dist < 12000) {
          ctx.strokeStyle = "rgba(34,197,94,0.05)";
          ctx.lineWidth = 0.5;

          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.stroke();
        }
      }
    }
  }

  // Animation loop
  let time = 0;

  function animate() {
    time += 0.003;

    ctx.fillStyle = "rgba(10, 15, 25, 0.25)";
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = "rgba(34,197,94,0.7)";

    particles.forEach((p) => {
      p.update(time);
      p.draw();
    });

    drawConnections();

    requestAnimationFrame(animate);
  }

  animate();
})();

/**
 * NOTE: initAiChat() is now called by dashboard.js's initApp() on both
 * initial page load and every Swup navigation. No $(document).ready call
 * needed here to avoid double initialization.
 */
