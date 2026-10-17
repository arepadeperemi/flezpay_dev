// Global utility functions for currency conversion and translation

// Currency conversion cache
let currencyRates = {};
let currencyCacheTime = null;
const CURRENCY_CACHE_DURATION = 3600000; // 1 hour in milliseconds

// Prevent multiple simultaneous API calls
let fetchCurrencyRatesPromise = null;
let lastFetchAttempt = null;
const MIN_FETCH_INTERVAL = 5000; // Minimum 5 seconds between API calls

// Language translation cache
let translationCache = {};
let currentLanguage = 'en';

// Currency symbols
const CURRENCY_SYMBOLS = {
    'NGN': '₦',
    'USD': '$',
    'EUR': '€'
};

// Fallback rates (approximate, will be used if API fails or rate limited)
const FALLBACK_RATES = {
    'NGN': { 'NGN': 1, 'USD': 0.0007, 'EUR': 0.0006 },
    'USD': { 'NGN': 1400, 'USD': 1, 'EUR': 0.85 },
    'EUR': { 'NGN': 1650, 'USD': 1.18, 'EUR': 1 }
};

/**
 * Fetch currency exchange rates from exchangerate-api.com (free tier)
 * Uses promise locking to prevent multiple simultaneous requests
 */
async function fetchCurrencyRates(baseCurrency = 'NGN') {
    const now = Date.now();
    
    // Return cached rates if still valid
    if (currencyCacheTime && (now - currencyCacheTime) < CURRENCY_CACHE_DURATION && currencyRates[baseCurrency]) {
        return currencyRates[baseCurrency];
    }
    
    // If there's already a fetch in progress, wait for it
    if (fetchCurrencyRatesPromise) {
        try {
            const rates = await fetchCurrencyRatesPromise;
            if (rates && rates[baseCurrency]) {
                return rates[baseCurrency];
            }
        } catch (error) {
            console.warn('Previous fetch failed, will retry or use fallback');
        }
    }
    
    // Check if we're making requests too frequently
    if (lastFetchAttempt && (now - lastFetchAttempt) < MIN_FETCH_INTERVAL) {
        console.warn('Rate limit protection: Using cached or fallback rates');
        // Return cached rates even if expired, or fallback
        if (currencyRates[baseCurrency]) {
            return currencyRates[baseCurrency];
        }
        return FALLBACK_RATES[baseCurrency] || FALLBACK_RATES['NGN'];
    }
    
    // Create a new fetch promise
    fetchCurrencyRatesPromise = (async () => {
        lastFetchAttempt = now;
        
        try {
            // Using exchangerate-api.com free tier (no API key required for basic usage)
            const response = await fetch(`https://api.exchangerate-api.com/v4/latest/${baseCurrency}`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                }
            });
            
            // Handle rate limiting
            if (response.status === 429) {
                const retryAfter = response.headers.get('Retry-After');
                console.warn(`Rate limited. Retry after: ${retryAfter} seconds`);
                throw new Error('RATE_LIMITED');
            }
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: Failed to fetch currency rates`);
            }
            
            const data = await response.json();
            
            // Validate response structure
            if (!data.rates || typeof data.rates !== 'object') {
                throw new Error('Invalid API response structure');
            }
            
            // Cache the rates for all currencies from this base
            currencyRates[baseCurrency] = data.rates;
            currencyCacheTime = now;
            
            // Also cache reverse rates if we got USD or EUR
            if (baseCurrency === 'NGN' && data.rates['USD']) {
                const usdRate = data.rates['USD'];
                currencyRates['USD'] = {
                    'NGN': 1 / usdRate,
                    'USD': 1,
                    'EUR': data.rates['EUR'] ? data.rates['EUR'] / usdRate : 0.85
                };
            }
            
            return data.rates;
        } catch (error) {
            console.error('Error fetching currency rates:', error);
            
            // Use fallback rates if API fails
            const fallbackRates = FALLBACK_RATES[baseCurrency] || FALLBACK_RATES['NGN'];
            
            // Cache fallback rates for a shorter duration (5 minutes)
            currencyRates[baseCurrency] = fallbackRates;
            currencyCacheTime = now - (CURRENCY_CACHE_DURATION - 300000); // Set cache time to expire in 5 minutes
            
            return fallbackRates;
        } finally {
            // Clear the promise after a delay to allow retries
            setTimeout(() => {
                fetchCurrencyRatesPromise = null;
            }, 1000);
        }
    })();
    
    try {
        return await fetchCurrencyRatesPromise;
    } catch (error) {
        // Return fallback rates if everything fails
        return FALLBACK_RATES[baseCurrency] || FALLBACK_RATES['NGN'];
    }
}

/**
 * Convert amount from one currency to another
 */
async function convertCurrency(amount, fromCurrency, toCurrency) {
    if (fromCurrency === toCurrency) {
        return amount;
    }
    
    // Validate inputs
    if (isNaN(amount) || amount === null || amount === undefined) {
        console.warn('Invalid amount for conversion:', amount);
        return 0;
    }
    
    try {
        const rates = await fetchCurrencyRates(fromCurrency);
        const rate = rates[toCurrency];
        
        if (rate === undefined || rate === null || isNaN(rate)) {
            console.warn(`Rate not found for ${toCurrency}, using fallback`);
            // Try to get rate from fallback
            const fallbackRates = FALLBACK_RATES[fromCurrency] || FALLBACK_RATES['NGN'];
            const fallbackRate = fallbackRates[toCurrency] || 1;
            return amount * fallbackRate;
        }
        
        return amount * rate;
    } catch (error) {
        console.error('Error converting currency:', error);
        // Use fallback rate
        const fallbackRates = FALLBACK_RATES[fromCurrency] || FALLBACK_RATES['NGN'];
        const fallbackRate = fallbackRates[toCurrency] || 1;
        return amount * fallbackRate;
    }
}

/**
 * Format currency amount with symbol
 */
function formatCurrency(amount, currency = 'NGN') {
    const symbol = CURRENCY_SYMBOLS[currency] || currency;
    const formatted = new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
    
    return `${symbol}${formatted}`;
}

/**
 * Get current admin currency from settings
 */
async function getCurrentCurrency() {
    try {
        const response = await fetch('/admin/api/admin/settings', {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status && result.data) {
            return result.data.currency || 'NGN';
        }
    } catch (error) {
        console.error('Error getting current currency:', error);
    }
    return 'NGN';
}

/**
 * Get current admin language from settings
 */
async function getCurrentLanguage() {
    try {
        const response = await fetch('/admin/api/admin/settings', {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.status && result.data) {
            return result.data.language || 'en';
        }
    } catch (error) {
        console.error('Error getting current language:', error);
    }
    return 'en';
}

/**
 * Translate text using Google Translate API (free tier)
 * Note: For production, you'll need a Google Cloud API key
 */
async function translateText(text, targetLanguage = 'en', sourceLanguage = 'en') {
    if (targetLanguage === sourceLanguage || !text) {
        return text;
    }
    
    // Check cache first
    const cacheKey = `${sourceLanguage}_${targetLanguage}_${text}`;
    if (translationCache[cacheKey]) {
        return translationCache[cacheKey];
    }
    
    try {
        // Using Google Translate API (free tier - requires API key in production)
        // For now, using a simple translation service that doesn't require API key
        // In production, use: https://translation.googleapis.com/language/translate/v2
        
        // Alternative: Using MyMemory Translation API (free, no key required)
        const response = await fetch(
            `https://api.mymemory.translated.net/get?q=${encodeURIComponent(text)}&langpair=${sourceLanguage}|${targetLanguage}`
        );
        
        if (!response.ok) {
            throw new Error('Translation API failed');
        }
        
        const data = await response.json();
        
        if (data.responseStatus === 200 && data.responseData) {
            let translated = data.responseData.translatedText;
            
            // Clean up common translation artifacts
            translated = translated.replace(/&quot;/g, '"');
            translated = translated.replace(/&#39;/g, "'");
            translated = translated.replace(/&amp;/g, '&');
            
            // Sometimes the API returns the original text if translation fails
            if (translated && translated !== text) {
                translationCache[cacheKey] = translated;
                return translated;
            }
        }
        
        return text;
    } catch (error) {
        console.error('Error translating text:', error);
        return text;
    }
}

/**
 * Translate all text elements on the page
 */
async function translatePage(targetLanguage) {
    if (targetLanguage === 'en') {
        // If English, restore original texts
        restoreOriginalTexts();
        return;
    }
    
    currentLanguage = targetLanguage;
    
    // Get all translatable elements (elements with data-translate attribute)
    const elements = document.querySelectorAll('[data-translate]');
    
    // Batch translate for better performance
    const textsToTranslate = [];
    const elementMap = [];
    
    for (const element of elements) {
        const originalText = element.getAttribute('data-translate-original') || element.textContent.trim();
        if (originalText && originalText.length > 0 && originalText.length < 200) {
            element.setAttribute('data-translate-original', originalText);
            textsToTranslate.push(originalText);
            elementMap.push(element);
        }
    }
    
    // Batch translate
    if (textsToTranslate.length > 0) {
        const translatedTexts = await batchTranslateTexts(textsToTranslate, targetLanguage, 'en');
        translatedTexts.forEach((translated, index) => {
            if (translated && translated !== textsToTranslate[index] && elementMap[index]) {
                elementMap[index].textContent = translated;
            }
        });
    }
    
    // Translate placeholders
    const placeholderTexts = [];
    const placeholderMap = [];
    const inputs = document.querySelectorAll('input[placeholder], textarea[placeholder]');
    for (const input of inputs) {
        const originalPlaceholder = input.getAttribute('data-translate-placeholder') || input.placeholder;
        if (originalPlaceholder && originalPlaceholder.length > 0 && originalPlaceholder.length < 200) {
            input.setAttribute('data-translate-placeholder', originalPlaceholder);
            placeholderTexts.push(originalPlaceholder);
            placeholderMap.push(input);
        }
    }
    
    if (placeholderTexts.length > 0) {
        const translatedPlaceholders = await batchTranslateTexts(placeholderTexts, targetLanguage, 'en');
        translatedPlaceholders.forEach((translated, index) => {
            if (translated && translated !== placeholderTexts[index] && placeholderMap[index]) {
                placeholderMap[index].placeholder = translated;
            }
        });
    }
    
    // Translate button texts (only buttons without icons and not already translated)
    const buttonTexts = [];
    const buttonMap = [];
    const buttons = document.querySelectorAll('button:not([data-no-translate]):not([data-translate])');
    for (const button of buttons) {
        // Skip buttons with SVG icons or complex content
        if (button.querySelector('svg') || button.querySelector('img')) continue;
        const originalText = button.getAttribute('data-translate-original') || button.textContent.trim();
        if (originalText && originalText.length > 0 && originalText.length < 100) {
            button.setAttribute('data-translate-original', originalText);
            buttonTexts.push(originalText);
            buttonMap.push(button);
        }
    }
    
    if (buttonTexts.length > 0) {
        const translatedButtons = await batchTranslateTexts(buttonTexts, targetLanguage, 'en');
        translatedButtons.forEach((translated, index) => {
            if (translated && translated !== buttonTexts[index] && buttonMap[index]) {
                buttonMap[index].textContent = translated;
            }
        });
    }
    
    // Translate labels
    const labelTexts = [];
    const labelMap = [];
    const labels = document.querySelectorAll('label:not([data-no-translate]):not([data-translate])');
    for (const label of labels) {
        const originalText = label.getAttribute('data-translate-original') || label.textContent.trim();
        if (originalText && originalText.length > 0 && originalText.length < 200) {
            label.setAttribute('data-translate-original', originalText);
            labelTexts.push(originalText);
            labelMap.push(label);
        }
    }
    
    if (labelTexts.length > 0) {
        const translatedLabels = await batchTranslateTexts(labelTexts, targetLanguage, 'en');
        translatedLabels.forEach((translated, index) => {
            if (translated && translated !== labelTexts[index] && labelMap[index]) {
                labelMap[index].textContent = translated;
            }
        });
    }
    
    // Translate headings (h1, h2, h3, etc.) - only those without data-translate
    const headingTexts = [];
    const headingMap = [];
    const headings = document.querySelectorAll('h1:not([data-translate]), h2:not([data-translate]), h3:not([data-translate]), h4:not([data-translate]), h5:not([data-translate]), h6:not([data-translate])');
    for (const heading of headings) {
        const originalText = heading.getAttribute('data-translate-original') || heading.textContent.trim();
        if (originalText && originalText.length > 0 && originalText.length < 200) {
            heading.setAttribute('data-translate-original', originalText);
            headingTexts.push(originalText);
            headingMap.push(heading);
        }
    }
    
    if (headingTexts.length > 0) {
        const translatedHeadings = await batchTranslateTexts(headingTexts, targetLanguage, 'en');
        translatedHeadings.forEach((translated, index) => {
            if (translated && translated !== headingTexts[index] && headingMap[index]) {
                headingMap[index].textContent = translated;
            }
        });
    }
    
    // Translate paragraph texts
    const paragraphTexts = [];
    const paragraphMap = [];
    const paragraphs = document.querySelectorAll('p:not([data-no-translate]):not([data-translate])');
    for (const paragraph of paragraphs) {
        const originalText = paragraph.getAttribute('data-translate-original') || paragraph.textContent.trim();
        if (originalText && originalText.length > 0 && originalText.length < 200) {
            paragraph.setAttribute('data-translate-original', originalText);
            paragraphTexts.push(originalText);
            paragraphMap.push(paragraph);
        }
    }
    
    if (paragraphTexts.length > 0) {
        const translatedParagraphs = await batchTranslateTexts(paragraphTexts, targetLanguage, 'en');
        translatedParagraphs.forEach((translated, index) => {
            if (translated && translated !== paragraphTexts[index] && paragraphMap[index]) {
                paragraphMap[index].textContent = translated;
            }
        });
    }
    
    // Translate span texts (navigation items, etc.)
    const spanTexts = [];
    const spanMap = [];
    const spans = document.querySelectorAll('span:not([data-no-translate]):not([data-translate]):not(.text-gray-400):not(.text-gray-500)');
    for (const span of spans) {
        const originalText = span.getAttribute('data-translate-original') || span.textContent.trim();
        // Only translate short spans (likely navigation items, labels, etc.)
        if (originalText && originalText.length > 0 && originalText.length < 50 && !span.closest('table')) {
            span.setAttribute('data-translate-original', originalText);
            spanTexts.push(originalText);
            spanMap.push(span);
        }
    }
    
    if (spanTexts.length > 0) {
        const translatedSpans = await batchTranslateTexts(spanTexts, targetLanguage, 'en');
        translatedSpans.forEach((translated, index) => {
            if (translated && translated !== spanTexts[index] && spanMap[index]) {
                spanMap[index].textContent = translated;
            }
        });
    }
}

/**
 * Restore original English texts
 */
function restoreOriginalTexts() {
    const elements = document.querySelectorAll('[data-translate-original]');
    elements.forEach(element => {
        const original = element.getAttribute('data-translate-original');
        if (original) {
            element.textContent = original;
        }
    });
    
    const inputs = document.querySelectorAll('[data-translate-placeholder]');
    inputs.forEach(input => {
        const original = input.getAttribute('data-translate-placeholder');
        if (original) {
            input.placeholder = original;
        }
    });
}

/**
 * Batch translate multiple texts to reduce API calls
 */
async function batchTranslateTexts(texts, targetLanguage, sourceLanguage = 'en') {
    if (targetLanguage === sourceLanguage || texts.length === 0) {
        return texts;
    }
    
    // Translate texts individually to ensure accuracy
    // (Batch translation with delimiter can cause issues with the API)
    const translatedTexts = [];
    
    for (let i = 0; i < texts.length; i++) {
        try {
            const translated = await translateText(texts[i], targetLanguage, sourceLanguage);
            translatedTexts.push(translated || texts[i]);
            // Small delay to avoid rate limiting
            if (i < texts.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 50));
            }
        } catch (error) {
            console.error(`Error translating text ${i}:`, error);
            translatedTexts.push(texts[i]);
        }
    }
    
    return translatedTexts;
}

/**
 * Convert and display all currency amounts on the page
 */
async function convertPageCurrencies(targetCurrency) {
    const currencyElements = document.querySelectorAll('[data-currency]');
    const baseCurrency = 'NGN'; // Assuming all amounts are stored in NGN
    
    for (const element of currencyElements) {
        const originalAmount = parseFloat(element.getAttribute('data-currency-amount') || element.textContent.replace(/[^0-9.-]+/g, ''));
        const originalCurrency = element.getAttribute('data-currency') || baseCurrency;
        
        if (!isNaN(originalAmount)) {
            element.setAttribute('data-currency-amount', originalAmount);
            element.setAttribute('data-currency', originalCurrency);
            
            const convertedAmount = await convertCurrency(originalAmount, originalCurrency, targetCurrency);
            element.textContent = formatCurrency(convertedAmount, targetCurrency);
        }
    }
}

/**
 * Initialize currency and language on page load
 */
async function initializeAdminLocalization() {
    try {
        const currency = await getCurrentCurrency();
        const language = await getCurrentLanguage();
        
        currentLanguage = language;
        
        // Convert currencies
        if (currency) {
            await convertPageCurrencies(currency);
        }
        
        // Translate page - always run to set up original texts
        if (language) {
            await translatePage(language);
        }
        
        // Set up event listeners for currency/language changes
        document.addEventListener('currencyChanged', async (e) => {
            if (e.detail && e.detail.currency) {
                await convertPageCurrencies(e.detail.currency);
            }
        });
        
        document.addEventListener('languageChanged', async (e) => {
            if (e.detail && e.detail.language) {
                await translatePage(e.detail.language);
            }
        });
    } catch (error) {
        console.error('Error initializing admin localization:', error);
    }
}

// Make functions globally accessible
window.convertCurrency = convertCurrency;
window.formatCurrency = formatCurrency;
window.fetchCurrencyRates = fetchCurrencyRates;
window.translateText = translateText;
window.translatePage = translatePage;
window.convertPageCurrencies = convertPageCurrencies;
window.initializeAdminLocalization = initializeAdminLocalization;
window.getCurrentCurrency = getCurrentCurrency;
window.getCurrentLanguage = getCurrentLanguage;
window.restoreOriginalTexts = restoreOriginalTexts;
window.batchTranslateTexts = batchTranslateTexts;

