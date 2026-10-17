if (typeof window.getCookie !== 'function') {
    window.getCookie = function(name) {
        let v = null;
        if (document.cookie) {
            document.cookie.split(';').forEach((c) => {
                c = c.trim();
                if (c.startsWith(name + '=')) {
                    v = decodeURIComponent(c.substring(name.length + 1));
                }
            });
        }
        return v;
    };
}

window.initAiCreator = function() {
    // Only run if on the correct page
    if (!document.getElementById('state-initial')) return;

    // Load existing preferences from localStorage
    try {
        const savedPrefs = localStorage.getItem('aiCreatorPrefs');
        if (savedPrefs) {
            window.aiPreferences = JSON.parse(savedPrefs);
        } else {
            window.aiPreferences = {};
        }
    } catch(e) { window.aiPreferences = {}; }

    window.clearAiCreatorState = function() {
        localStorage.removeItem('aiCreatorPrefs');
        localStorage.removeItem('aiCreatorTaskId');
        localStorage.removeItem('aiCreatorUIProgress');
        localStorage.removeItem('aiCreatorGeneratedPlan');
        window.aiPreferences = {};
    };

    window.cancelAiCreator = function() {
        window.clearAiCreatorState();
        window.switchState('initial');
    };

    window.switchState = function(state) {
        const states = ['initial', 'generating', 'review'];
        const targetId = 'state-' + state;
        const targetEl = document.getElementById(targetId);
        if (!targetEl) return;
        
        let currentEl = null;
        for (let s of states) {
            const el = document.getElementById('state-' + s);
            if (el && !el.classList.contains('hidden') && el.id !== targetId) {
                currentEl = el;
                break;
            }
        }
        
        if (currentEl) {
            currentEl.style.transition = 'opacity 0.4s ease-in-out, transform 0.4s ease-in-out';
            currentEl.style.opacity = '0';
            currentEl.style.transform = 'translateY(-10px)';
            
            setTimeout(() => {
                currentEl.classList.add('hidden');
                currentEl.style.opacity = '';
                currentEl.style.transform = '';
                currentEl.style.transition = '';
                
                targetEl.classList.remove('hidden');
                // Temporarily disable the CSS animate-fade-in to use our own smooth JS transition
                targetEl.style.opacity = '0';
                targetEl.style.transform = 'translateY(10px)';
                targetEl.style.transition = 'opacity 0.4s ease-in-out, transform 0.4s ease-in-out';
                
                // Trigger reflow to ensure the transition applies
                void targetEl.offsetWidth;
                
                targetEl.style.opacity = '1';
                targetEl.style.transform = 'translateY(0)';
                
                setTimeout(() => {
                    targetEl.style.transition = '';
                    targetEl.style.opacity = '';
                    targetEl.style.transform = '';
                }, 400);
            }, 400);
        } else {
            states.forEach(s => {
                const el = document.getElementById('state-' + s);
                if (el && el.id !== targetId) el.classList.add('hidden');
            });
            targetEl.classList.remove('hidden');
        }
    };
    
    window.selectCard = function(groupName, value, element) {
        document.querySelectorAll(`.card-${groupName}`).forEach(el => {
            el.classList.remove('border-primary', 'bg-primary/5');
            el.classList.add('border-slate-200', 'dark:border-white/5');
            const check = el.querySelector('.check-indicator');
            if (check) check.classList.add('hidden');
        });
        element.classList.remove('border-slate-200', 'dark:border-white/5');
        element.classList.add('border-primary', 'bg-primary/5');
        const check = element.querySelector('.check-indicator');
        if (check) check.classList.remove('hidden');
        
        window.aiPreferences = window.aiPreferences || {};
        window.aiPreferences[groupName] = value;
        localStorage.setItem('aiCreatorPrefs', JSON.stringify(window.aiPreferences));
    };
    
    window.animateGeneratingUI = async function(startIndex = 0) {
        const steps = document.querySelectorAll('.gen-step');
        if (!steps.length) return;
        
        // Fast-forward completed steps
        for (let i = 0; i < startIndex; i++) {
            if (i >= steps.length) break;
            steps[i].classList.remove('opacity-30');
            let icon = steps[i].querySelector('svg, i');
            if (icon) {
                if (icon.tagName.toLowerCase() === 'svg') {
                    icon.outerHTML = '<i data-lucide="check-circle-2" class="w-4 h-4 text-primary shrink-0"></i>';
                } else {
                    icon.setAttribute('data-lucide', 'check-circle-2');
                    icon.classList.remove('animate-spin');
                }
            }
        }
        if (typeof lucide !== 'undefined') lucide.createIcons();

        // Animate remaining steps
        for (let i = startIndex; i < steps.length; i++) {
            localStorage.setItem('aiCreatorUIProgress', i);
            steps[i].classList.remove('opacity-30');
            let icon = steps[i].querySelector('svg, i');
            if (icon) {
                if (icon.tagName.toLowerCase() === 'svg') {
                    icon.outerHTML = '<i data-lucide="loader-2" class="w-4 h-4 text-primary animate-spin shrink-0"></i>';
                } else {
                    icon.setAttribute('data-lucide', 'loader-2');
                    icon.classList.add('animate-spin', 'text-primary');
                }
                if(typeof lucide !== 'undefined') lucide.createIcons();
            }
            
            if (i < steps.length - 1) {
                await new Promise(r => setTimeout(r, 1500));
                icon = steps[i].querySelector('svg, i');
                if (icon) {
                    if (icon.tagName.toLowerCase() === 'svg') {
                        icon.outerHTML = '<i data-lucide="check-circle-2" class="w-4 h-4 text-primary shrink-0"></i>';
                    } else {
                        icon.setAttribute('data-lucide', 'check-circle-2');
                        icon.classList.remove('animate-spin');
                    }
                    if(typeof lucide !== 'undefined') lucide.createIcons();
                }
            }
        }
    };
    
    window.startGeneration = async function() {
        window.switchState('generating');
        window.animateGeneratingUI(0);
        localStorage.removeItem('aiCreatorGeneratedPlan');
        
        try {
            const prefs = window.aiPreferences || {};
            const res = await fetch('/api/growth/ai-creator/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.getCookie('csrftoken')
                },
                body: JSON.stringify({ preferences: prefs })
            });
            const data = await res.json();
            
            if(data.success && data.task_id) {
                localStorage.setItem('aiCreatorTaskId', data.task_id);
                window.pollTaskStatus(data.task_id);
            } else {
                window.showToast("Failed to start generation: " + (data.error || "Unknown error"));
                window.switchState('initial');
            }
        } catch(err) {
            window.showToast("Network error.");
            window.switchState('initial');
        }
    };

    window.pollTaskStatus = async function(taskId) {
        window.switchState('generating');
        const savedProgress = parseInt(localStorage.getItem('aiCreatorUIProgress')) || 0;
        window.animateGeneratingUI(savedProgress);
        
        const pollInterval = setInterval(async () => {
            try {
                const res = await fetch('/api/growth/ai-creator/status/' + taskId);
                const data = await res.json();
                
                if (data.status === 'completed') {
                    clearInterval(pollInterval);
                    localStorage.removeItem('aiCreatorTaskId');
                    localStorage.removeItem('aiCreatorUIProgress');
                    localStorage.setItem('aiCreatorGeneratedPlan', JSON.stringify(data.plan));
                    window.populateReview(data.plan);
                    window.switchState('review');
                } else if (data.status === 'failed') {
                    clearInterval(pollInterval);
                    localStorage.removeItem('aiCreatorTaskId');
                    localStorage.removeItem('aiCreatorUIProgress');
                    window.showToast("Generation failed: " + data.error);
                    window.switchState('initial');
                }
                // If pending, keep polling
            } catch(err) {
                // Ignore transient network errors during polling
            }
        }, 3000);
    };

    // Restore UI selections if they exist
    setTimeout(() => {
        if (window.aiPreferences) {
            Object.keys(window.aiPreferences).forEach(key => {
                const val = window.aiPreferences[key];
                const card = document.querySelector(`.card-${key}[onclick*="'${val}'"]`);
                if (card) {
                    document.querySelectorAll(`.card-${key}`).forEach(el => {
                        el.classList.remove('border-primary', 'bg-primary/5');
                        el.classList.add('border-slate-200', 'dark:border-white/5');
                        const check = el.querySelector('.check-indicator');
                        if (check) check.classList.add('hidden');
                    });
                    card.classList.remove('border-slate-200', 'dark:border-white/5');
                    card.classList.add('border-primary', 'bg-primary/5');
                    const check = card.querySelector('.check-indicator');
                    if (check) check.classList.remove('hidden');
                }
            });
        }
    }, 100);

    // Check for ongoing task or completed plan
    const activeTaskId = localStorage.getItem('aiCreatorTaskId');
    const savedPlanStr = localStorage.getItem('aiCreatorGeneratedPlan');
    
    if (activeTaskId) {
        window.pollTaskStatus(activeTaskId);
    } else if (savedPlanStr) {
        try {
            const savedPlan = JSON.parse(savedPlanStr);
            // Delay slightly to allow DOM to be ready
            setTimeout(() => {
                window.populateReview(savedPlan);
                window.switchState('review');
            }, 150);
        } catch(e) {
            localStorage.removeItem('aiCreatorGeneratedPlan');
        }
    }
    
    window.populateReview = function(plan) {
        window.generatedPlan = plan;
        document.getElementById('rev-product').innerText = plan.suggested_product_name ? plan.suggested_product_name : 'Whole Store Catalog';
        document.getElementById('rev-goal').innerText = plan.action_type || 'visit';
        
        const audSel = document.getElementById('rev-audience-select');
        if (audSel) {
            audSel.value = plan.audience_type || 'near';
            window.handleAudienceChange();
        }
        
        const currencyEl = document.getElementById('rev-budget-currency');
        if (currencyEl) currencyEl.innerText = (window.getUserCurrencySymbol ? window.getUserCurrencySymbol() : (window.STORE_CURRENCY_SYMBOL || '₦'));
        
        const usdRate = window.usdExchangeRate || 1.0;
        const minBudget = Math.ceil(1 * usdRate);
        const maxBudget = Math.ceil(500 * usdRate);
        const stepBudget = Math.ceil(1 * usdRate);
        
        const defaultBudget = plan.daily_budget ? Math.max(minBudget, Math.min(maxBudget, plan.daily_budget)) : Math.ceil(5 * usdRate);

        const rangeInput = document.getElementById('rev-budget-range');
        if (rangeInput) {
            rangeInput.min = minBudget;
            rangeInput.max = maxBudget;
            rangeInput.step = stepBudget;
            rangeInput.value = defaultBudget;
            document.getElementById('rev-budget-display').innerText = parseInt(defaultBudget).toLocaleString();
        }
        
        const durInput = document.getElementById('rev-duration-input');
        if (durInput) {
            durInput.value = plan.duration_days ? Math.min(30, Math.max(1, plan.duration_days)) : 7;
            document.getElementById('rev-duration-display').innerText = durInput.value;
        }
        
        document.getElementById('promo-headline').value = plan.headline || '';
        document.getElementById('promo-message').value = plan.message || '';
        document.getElementById('ai-insight-text').innerText = plan.insight || 'Contextual parameters matched business trends.';
        
        const preview = document.getElementById('media-preview-container');
        if (plan.suggested_product_image) {
            window.uploadedMediaUrl = plan.suggested_product_image;
            preview.innerHTML = `<img src="${plan.suggested_product_image}" class="w-full h-48 object-cover rounded-xl mt-4">`;
            preview.classList.remove('hidden');
            
            // Still allow the user to see the change image options
            document.getElementById('media-options-grid').classList.remove('hidden');
        } else {
            window.uploadedMediaUrl = '';
            preview.innerHTML = '';
            preview.classList.add('hidden');
            document.getElementById('media-options-grid').classList.remove('hidden');
        }
        
        window.updateReach();
    };

    let estimateTimeout = null;
    window.updateReach = function() {
        const budgetRange = document.getElementById('rev-budget-range');
        if (!budgetRange) return;
        const budget = parseFloat(budgetRange.value) || 0;
        const durInput = document.getElementById('rev-duration-input');
        const duration = durInput ? (parseFloat(durInput.value) || 7) : 7;
        
        const audSel = document.getElementById('rev-audience-select');
        const audienceType = audSel ? audSel.value : 'near';
        
        document.getElementById('rev-reach').innerText = "Calculating...";
        
        if (estimateTimeout) clearTimeout(estimateTimeout);
        estimateTimeout = setTimeout(() => {
            const payload = {
                budget_per_day: budget,
                audience_type: audienceType
            };
            
            if (audienceType === "custom") {
                const mapSearch = document.getElementById("selected-custom-location");
                payload.custom_locations = mapSearch ? mapSearch.value : "";
            }
            
            fetch("/api/growth/estimate-reach", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": window.getCookie("csrftoken") || ""
                },
                body: JSON.stringify(payload)
            })
            .then(r => r.json())
            .then(data => {
                let reachText = "Unavailable";
                if (data.success) {
                    const minTotal = data.reach_min * duration;
                    const maxTotal = data.reach_max * duration;
                    reachText = `${minTotal.toLocaleString()} - ${maxTotal.toLocaleString()} people`;
                }
                
                document.getElementById('rev-reach').innerText = reachText;
                
                // Update Summary Card
                const summaryReach = document.getElementById('summary-reach');
                if (summaryReach) summaryReach.innerText = reachText;
                
                const summaryTotal = document.getElementById('summary-total-debit');
                if (summaryTotal) summaryTotal.innerText = (budget * duration).toLocaleString();
                
                const summaryAudience = document.getElementById('summary-audience');
                if (summaryAudience) {
                    summaryAudience.innerText = audSel ? audSel.options[audSel.selectedIndex].text : "Near Store";
                }
                
                const summaryLocRow = document.getElementById('summary-location-row');
                const summaryLoc = document.getElementById('summary-location');
                if (summaryLocRow && summaryLoc) {
                    if (audienceType === "custom" && payload.custom_locations) {
                        summaryLocRow.classList.remove('hidden');
                        summaryLoc.innerText = payload.custom_locations;
                    } else {
                        summaryLocRow.classList.add('hidden');
                    }
                }
            })
            .catch(() => {
                document.getElementById('rev-reach').innerText = "Error";
                const summaryReach = document.getElementById('summary-reach');
                if (summaryReach) summaryReach.innerText = "Error";
            });
        }, 600);
    };
    
    window.triggerMediaUpload = function() {
        document.getElementById('media-upload-input').click();
    };
    
    window.handleMediaUpload = async function(input) {
        if (!input.files || !input.files[0]) return;
        const file = input.files[0];
        
        document.getElementById('media-loading').classList.remove('hidden');
        document.getElementById('media-options-grid').classList.add('hidden');
        document.getElementById('ai-generator-pane').classList.add('hidden');
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch('/api/growth/upload-media', {
                method: 'POST',
                headers: { 'X-CSRFToken': window.getCookie('csrftoken') },
                body: formData,
            });
            const data = await res.json();
            
            if(data.success) {
                const isVideo = file.type.startsWith('video/');
                window.setMediaPreview(data.url, isVideo);
                document.getElementById('media-loading').classList.add('hidden');
            } else {
                window.showToast(data.error);
                document.getElementById('media-loading').classList.add('hidden');
                document.getElementById('media-options-grid').classList.remove('hidden');
            }
        } catch(err) {
            window.showToast("Upload failed.");
            document.getElementById('media-loading').classList.add('hidden');
            document.getElementById('media-options-grid').classList.remove('hidden');
        }
    };
    
    window.currentAiMediaType = 'image';

    window.switchAiMediaType = function(type) {
        window.currentAiMediaType = type;
        const imgBtn = document.getElementById('ai-type-image-btn');
        const vidBtn = document.getElementById('ai-type-video-btn');
        const badge = document.getElementById('ai-media-badge');
        const label = document.getElementById('btn-gen-ai-label');
        const promptBox = document.getElementById('ai-img-prompt');

        if (type === 'video') {
            if (imgBtn) imgBtn.className = "px-3 py-1 text-xs rounded-lg font-bold transition-all bg-slate-200 dark:bg-white/10 text-slate-600 dark:text-slate-300";
            if (vidBtn) vidBtn.className = "px-3 py-1 text-xs rounded-lg font-bold transition-all bg-primary text-black";
            if (badge) badge.innerText = "AI Veo 2.0";
            if (label) label.innerText = "Generate Video";
            if (promptBox) {
                promptBox.placeholder = "Describe the video (e.g. 'Dynamic 4K promotional commercial showcasing product with smooth camera pan and lighting...')";
                if (window.generatedPlan && (!promptBox.value || promptBox.value.includes('photo'))) {
                    promptBox.value = `Cinematic 4K commercial video showcasing: "${window.generatedPlan.headline}". ${window.generatedPlan.message} — smooth motion, elegant lighting, professional advertisement`;
                }
            }
        } else {
            if (vidBtn) vidBtn.className = "px-3 py-1 text-xs rounded-lg font-bold transition-all bg-slate-200 dark:bg-white/10 text-slate-600 dark:text-slate-300";
            if (imgBtn) imgBtn.className = "px-3 py-1 text-xs rounded-lg font-bold transition-all bg-primary text-black";
            if (badge) badge.innerText = "AI Imagen";
            if (label) label.innerText = "Generate Image";
            if (promptBox) {
                promptBox.placeholder = "Describe the image (e.g. 'A sleek commercial product photo on studio background...')";
                if (window.generatedPlan && (!promptBox.value || promptBox.value.includes('Cinematic'))) {
                    promptBox.value = `High quality commercial product photo for a campaign titled: "${window.generatedPlan.headline}". ${window.generatedPlan.message}`;
                }
            }
        }
        if (typeof lucide !== 'undefined') lucide.createIcons();
    };

    window.toggleAiGenerator = function(defaultType = 'image') {
        const pane = document.getElementById('ai-generator-pane');
        if (!pane) return;
        if (pane.classList.contains('hidden')) {
            pane.classList.remove('hidden');
            window.switchAiMediaType(defaultType);
        } else if (defaultType && defaultType !== window.currentAiMediaType) {
            window.switchAiMediaType(defaultType);
        } else {
            pane.classList.add('hidden');
        }
    };
    
    // Backward compatibility alias
    window.toggleAiImageGenerator = function() {
        window.toggleAiGenerator('image');
    };

    window.triggerAiMediaGeneration = function() {
        if (window.currentAiMediaType === 'video') {
            window.generateAiCoverVideo();
        } else {
            window.generateAiCoverImage();
        }
    };

    window.setMediaPreview = function(url, isVideo = false) {
        window.uploadedMediaUrl = url;
        if (!isVideo && url && url.match(/\.(mp4|webm|ogg|mov)(\?|#|$)/i)) {
            isVideo = true;
        }
        const preview = document.getElementById('media-preview-container');
        if (!preview) return;
        preview.innerHTML = '';
        preview.classList.remove('hidden');

        if (isVideo) {
            preview.innerHTML = `
                <div class="relative group rounded-xl overflow-hidden border border-slate-200 dark:border-white/10">
                    <video src="${url}" class="w-full h-48 object-cover rounded-xl" controls playsinline autoplay loop muted></video>
                    <div class="absolute top-2 right-2 flex gap-1">
                        <button type="button" onclick="window.removeMediaPreview()" class="px-2 py-1 bg-black/70 hover:bg-black text-white text-[10px] rounded-md backdrop-blur-sm transition-colors">
                            Change
                        </button>
                    </div>
                </div>
            `;
        } else {
            preview.innerHTML = `
                <div class="relative group rounded-xl overflow-hidden border border-slate-200 dark:border-white/10">
                    <img src="${url}" class="w-full h-48 object-cover rounded-xl">
                    <div class="absolute top-2 right-2 flex gap-1">
                        <button type="button" onclick="window.removeMediaPreview()" class="px-2 py-1 bg-black/70 hover:bg-black text-white text-[10px] rounded-md backdrop-blur-sm transition-colors">
                            Change
                        </button>
                    </div>
                </div>
            `;
        }
        if (typeof lucide !== 'undefined') lucide.createIcons();
    };

    window.removeMediaPreview = function() {
        window.uploadedMediaUrl = '';
        const preview = document.getElementById('media-preview-container');
        if (preview) {
            preview.innerHTML = '';
            preview.classList.add('hidden');
        }
    };
    
    window.generateAiCoverImage = async function() {
        const prompt = document.getElementById('ai-img-prompt').value.trim();
        if (!prompt) {
            window.showToast("Please enter an image description.");
            return;
        }
        
        const loading = document.getElementById('ai-img-loading');
        const loadingText = document.getElementById('ai-img-loading-text');
        const btn = document.getElementById('btn-gen-ai-img');

        if (loading) loading.classList.remove('hidden');
        if (loadingText) loadingText.innerText = "Generating AI Image with Imagen...";
        if (btn) btn.disabled = true;
        
        try {
            const res = await fetch('/api/growth/generate-image', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.getCookie('csrftoken')
                },
                body: JSON.stringify({ prompt })
            });
            const data = await res.json();
            
            if (data.success && (data.image_url || data.media_url)) {
                const url = data.image_url || data.media_url;
                window.setMediaPreview(url, false);
                window.showToast("AI Image generated successfully!");
            } else {
                window.showToast(data.error || "Image generation failed.");
            }
        } catch(err) {
            window.showToast("Failed to connect to image generator.");
        } finally {
            if (loading) loading.classList.add('hidden');
            if (btn) btn.disabled = false;
        }
    };

    window.generateAiCoverVideo = async function() {
        const prompt = document.getElementById('ai-img-prompt').value.trim();
        if (!prompt) {
            window.showToast("Please enter a video description.");
            return;
        }
        
        const loading = document.getElementById('ai-img-loading');
        const loadingText = document.getElementById('ai-img-loading-text');
        const btn = document.getElementById('btn-gen-ai-img');

        if (loading) loading.classList.remove('hidden');
        if (loadingText) loadingText.innerText = "Generating AI Video with Veo... (this can take up to 60s)";
        if (btn) btn.disabled = true;
        
        try {
            const res = await fetch('/api/growth/generate-video', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.getCookie('csrftoken')
                },
                body: JSON.stringify({ prompt })
            });
            const data = await res.json();
            
            if (data.success && (data.video_url || data.media_url)) {
                const url = data.video_url || data.media_url;
                window.setMediaPreview(url, true);
                window.showToast("AI Video generated successfully!");
            } else {
                window.showToast(data.error || "Video generation failed.");
            }
        } catch(err) {
            window.showToast("Failed to connect to video generator.");
        } finally {
            if (loading) loading.classList.add('hidden');
            if (btn) btn.disabled = false;
        }
    };

    window.publishPromotion = async function() {
        if (!window.uploadedMediaUrl) {
            window.showToast("A campaign media or cover image is required.");
            return;
        }

        const btn = document.getElementById('btn-publish');
        btn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Publishing...';
        btn.disabled = true;
        if(typeof lucide !== 'undefined') lucide.createIcons();
        
        const plan = window.generatedPlan;
        const editedBudget = parseFloat(document.getElementById('rev-budget-range').value) || plan.daily_budget || 5;
        const payload = {
            title: document.getElementById('promo-headline').value,
            message: document.getElementById('promo-message').value,
            cover_image: window.uploadedMediaUrl || '',
            product_id: plan.suggested_product_id,
            promote_type: plan.promote_type || 'store',
            action_type: plan.action_type || 'visit',
            audience_type: document.getElementById('rev-audience-select').value || 'near',
            custom_locations: document.getElementById('selected-custom-location').value || '',
            daily_budget: editedBudget,
            budget_per_day: editedBudget,
            duration_days: parseFloat(document.getElementById('rev-duration-input').value) || 7,
            status: 'active'
        };
        
        try {
            const res = await fetch('/api/growth/promotions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.getCookie('csrftoken')
                },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if(data.success) {
                if (data.warning) {
                    sessionStorage.setItem('promo_warning', data.warning);
                    if (data.billing_url) sessionStorage.setItem('promo_billing_url', data.billing_url);
                }
                window.clearAiCreatorState();
                window.location.href = '/growth/promotions';
            } else {
                window.showToast(data.error);
                btn.innerHTML = 'PUBLISH_CAMPAIGN';
                btn.disabled = false;
            }
        } catch (err) {
            window.showToast('Network error.');
            btn.innerHTML = 'PUBLISH_CAMPAIGN';
            btn.disabled = false;
        }
    };

    window.aiPreferences = {
        promote: 'Let AI choose',
        goal: 'Get more sales',
        style: 'Friendly'
    };

    const defaultPromote = document.querySelector('.card-promote');
    const defaultGoal = document.querySelector('.card-goal');
    const defaultStyle = document.querySelector('.card-style');
    
    if (defaultPromote) {
        defaultPromote.classList.add('border-primary', 'bg-primary/5');
        const check = defaultPromote.querySelector('.check-indicator');
        if (check) check.classList.remove('hidden');
    }
    if (defaultGoal) {
        defaultGoal.classList.add('border-primary', 'bg-primary/5');
        const check = defaultGoal.querySelector('.check-indicator');
        if (check) check.classList.remove('hidden');
    }
    if (defaultStyle) {
        defaultStyle.classList.add('border-primary', 'bg-primary/5');
    }
    if(typeof lucide !== 'undefined') lucide.createIcons();
};

window.handleAudienceChange = function() {
    const val = document.getElementById('rev-audience-select').value;
    const inlineMap = document.getElementById('inline-map-container');
    if (val === 'custom') {
        if(inlineMap) inlineMap.classList.remove('hidden');
        window.initMap();
    } else {
        if(inlineMap) inlineMap.classList.add('hidden');
    }
};

var mapInstance = null;
var mapMarkers = [];

window.initMap = function() {
    function setupMap() {
        if (!mapInstance) {
            setTimeout(() => {
                mapInstance = L.map('leaflet-map').setView([9.0820, 8.6753], 5);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    maxZoom: 19,
                    attribution: '© OpenStreetMap'
                }).addTo(mapInstance);
                
                mapInstance.on('click', async function(e) {
                    const marker = L.marker(e.latlng).addTo(mapInstance);
                    mapMarkers.push(marker);
                    window.updateSelectedLocations();
                    
                    document.getElementById('selected-location-text').innerText = "Fetching address...";
                    const lat = e.latlng.lat.toFixed(6);
                    const lon = e.latlng.lng.toFixed(6);
                    
                    try {
                        const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
                        const data = await res.json();
                        if (data && data.display_name) {
                            marker.bindPopup(data.display_name).openPopup();
                            document.getElementById('selected-location-text').innerText = `Added: ${data.display_name}`;
                        } else {
                            document.getElementById('selected-location-text').innerText = `Added Coordinate: ${lat}, ${lon}`;
                        }
                    } catch (err) {
                        document.getElementById('selected-location-text').innerText = `Added Coordinate: ${lat}, ${lon}`;
                    }
                });
            }, 100);
        } else {
            // Force resize in case it was initialized while hidden
            setTimeout(() => { mapInstance.invalidateSize(); }, 100);
        }
    }

    if (typeof L === 'undefined') {
        if (!document.getElementById('leaflet-css')) {
            const link = document.createElement('link');
            link.id = 'leaflet-css';
            link.rel = 'stylesheet';
            link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
            document.head.appendChild(link);
        }
        if (!document.getElementById('leaflet-js')) {
            const script = document.createElement('script');
            script.id = 'leaflet-js';
            script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
            script.onload = setupMap;
            document.head.appendChild(script);
        } else {
            document.getElementById('leaflet-js').addEventListener('load', setupMap);
        }
    } else {
        setupMap();
    }
};

window.updateSelectedLocations = function() {
    const locs = mapMarkers.map(m => {
        const ll = m.getLatLng();
        return `${ll.lat.toFixed(6)},${ll.lng.toFixed(6)}`;
    });
    document.getElementById('selected-custom-location').value = locs.join('|');
};

window.clearMapMarkers = function() {
    mapMarkers.forEach(m => {
        if (mapInstance) mapInstance.removeLayer(m);
    });
    mapMarkers = [];
    window.updateSelectedLocations();
    document.getElementById('selected-location-text').innerText = "Cleared all markers. Click map to drop pins.";
};

window.searchMap = async function() {
    const query = document.getElementById('map-search-input').value;
    if (!query) return;
    try {
        const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`);
        const data = await res.json();
        if (data && data.length > 0) {
            const lat = parseFloat(data[0].lat);
            const lon = parseFloat(data[0].lon);
            mapInstance.setView([lat, lon], 12);
            
            const marker = L.marker([lat, lon]).addTo(mapInstance);
            mapMarkers.push(marker);
            window.updateSelectedLocations();
            
            marker.bindPopup(data[0].display_name).openPopup();
            document.getElementById('selected-location-text').innerText = `Added: ${data[0].display_name}`;
        } else {
            window.showToast("Location not found");
        }
    } catch (e) {
        window.showToast("Search failed");
    }
};

// Initialize immediately in case of hard load
document.addEventListener("DOMContentLoaded", () => {
    window.initAiCreator();
});
