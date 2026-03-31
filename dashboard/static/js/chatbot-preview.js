/**
 * ResonantOS Chatbot Preview Module
 * Handles real-time preview updates for widget customization
 * Fixes: #35, #36, #37, #38, #39, #40
 */

(function() {
    'use strict';

    // Widget state management
    const widgetState = {
        name: 'ResonantOS Assistant',
        position: 'bottom-right',
        theme: 'dark',
        primaryColor: '#4ade80',
        bgColor: '#1a1a1a',
        textColor: '#e0e0e0',
        greeting: 'Hi! How can I help you today?',
        showWatermark: true,
        isEditing: false,
        widgetId: null
    };

    // System theme detection for Auto mode
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)');

    /**
     * Get all preview containers (Appearance + Deploy tabs)
     */
    function getPreviewContainers() {
        return document.querySelectorAll('.widget-preview-container');
    }

    /**
     * Update all preview instances with current state
     */
    function updateAllPreviews() {
        const containers = getPreviewContainers();
        containers.forEach(container => {
            updatePreviewInstance(container);
        });
        updateEmbedCode();
        updateButtonLabel();
    }

    /**
     * Update a single preview instance
     */
    function updatePreviewInstance(container) {
        const widget = container.querySelector('.preview-widget');
        const chat = container.querySelector('.widget-chat');
        const button = container.querySelector('.widget-button');
        const title = container.querySelector('.chat-title');
        const greeting = container.querySelector('.preview-greeting');
        const watermark = container.querySelector('.chat-watermark');

        if (!widget) return;

        // Position (#35)
        widget.classList.remove('position-bottom-left', 'position-bottom-right');
        widget.classList.add(`position-${widgetState.position}`);

        // Theme (#38)
        let effectiveTheme = widgetState.theme;
        if (effectiveTheme === 'auto') {
            effectiveTheme = systemPrefersDark.matches ? 'dark' : 'light';
        }
        
        widget.classList.remove('theme-dark', 'theme-light');
        widget.classList.add(`theme-${effectiveTheme}`);
        
        // Apply theme colors to chat container
        if (chat) {
            if (effectiveTheme === 'dark') {
                chat.style.setProperty('--chat-bg', widgetState.bgColor);
                chat.style.setProperty('--chat-text', widgetState.textColor);
                chat.style.setProperty('--chat-header-bg', darkenColor(widgetState.bgColor, 10));
                chat.style.setProperty('--chat-input-bg', darkenColor(widgetState.bgColor, 5));
            } else {
                // Light theme
                chat.style.setProperty('--chat-bg', '#ffffff');
                chat.style.setProperty('--chat-text', '#1a1a1a');
                chat.style.setProperty('--chat-header-bg', '#f5f5f5');
                chat.style.setProperty('--chat-input-bg', '#fafafa');
            }
            chat.style.setProperty('--chat-primary', widgetState.primaryColor);
        }

        // Colors (#37)
        if (button) {
            button.style.backgroundColor = widgetState.primaryColor;
            button.style.color = getContrastColor(widgetState.primaryColor);
        }

        // Name
        if (title) {
            title.textContent = widgetState.name || 'Assistant';
        }

        // Greeting (#39)
        if (greeting) {
            greeting.textContent = widgetState.greeting || 'Hi! How can I help you today?';
        }

        // Watermark
        if (watermark) {
            watermark.style.display = widgetState.showWatermark ? 'block' : 'none';
        }
    }

    /**
     * Update button label based on edit/create mode (#40)
     */
    function updateButtonLabel() {
        const generateBtn = document.getElementById('generateWidgetBtn');
        if (generateBtn) {
            if (widgetState.isEditing && widgetState.widgetId) {
                generateBtn.innerHTML = '💾 Save & Update';
                generateBtn.title = 'Update existing chatbot';
            } else {
                generateBtn.innerHTML = '🚀 Generate Widget';
                generateBtn.title = 'Create new chatbot';
            }
        }
    }

    /**
     * Update embed code with current settings
     */
    function updateEmbedCode() {
        const embedCodeEl = document.getElementById('embedCode');
        if (!embedCodeEl) return;

        const widgetId = widgetState.widgetId || 'YOUR_WIDGET_ID';
        const code = `<!-- ResonantOS Chat Widget -->
<script>
  (function() {
    var widget = document.createElement('script');
    widget.src = 'https://resonantos.com/widget.js';
    widget.dataset.widgetId = '${widgetId}';
    widget.dataset.position = '${widgetState.position}';
    widget.dataset.theme = '${widgetState.theme}';
    widget.dataset.primaryColor = '${widgetState.primaryColor}';
    widget.dataset.bgColor = '${widgetState.bgColor}';
    widget.dataset.textColor = '${widgetState.textColor}';
    document.body.appendChild(widget);
  })();
</script>`;
        
        embedCodeEl.textContent = code;
    }

    /**
     * Set widget to editing mode
     */
    function setEditMode(widgetId, config) {
        widgetState.isEditing = true;
        widgetState.widgetId = widgetId;
        
        if (config) {
            Object.assign(widgetState, {
                name: config.name || widgetState.name,
                position: config.position || widgetState.position,
                theme: config.theme || widgetState.theme,
                primaryColor: config.primary_color || config.primaryColor || widgetState.primaryColor,
                bgColor: config.bg_color || config.bgColor || widgetState.bgColor,
                textColor: config.text_color || config.textColor || widgetState.textColor,
                greeting: config.greeting || widgetState.greeting,
                showWatermark: config.show_watermark !== undefined ? config.show_watermark : widgetState.showWatermark
            });
        }
        
        updateAllPreviews();
    }

    /**
     * Reset to create mode
     */
    function setCreateMode() {
        widgetState.isEditing = false;
        widgetState.widgetId = null;
        updateButtonLabel();
    }

    /**
     * Get contrast color (black or white) for text on a given background
     */
    function getContrastColor(hexColor) {
        const r = parseInt(hexColor.slice(1, 3), 16);
        const g = parseInt(hexColor.slice(3, 5), 16);
        const b = parseInt(hexColor.slice(5, 7), 16);
        const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        return luminance > 0.5 ? '#000000' : '#ffffff';
    }

    /**
     * Darken a hex color by a percentage
     */
    function darkenColor(hexColor, percent) {
        const num = parseInt(hexColor.replace('#', ''), 16);
        const amt = Math.round(2.55 * percent);
        const R = Math.max(0, (num >> 16) - amt);
        const G = Math.max(0, ((num >> 8) & 0x00FF) - amt);
        const B = Math.max(0, (num & 0x0000FF) - amt);
        return '#' + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
    }

    /**
     * Initialize event listeners for all inputs
     */
    function initEventListeners() {
        // Position radios (#35)
        document.querySelectorAll('input[name="position"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                widgetState.position = e.target.value;
                updateAllPreviews();
            });
        });

        // Theme radios (#38)
        document.querySelectorAll('input[name="theme"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                widgetState.theme = e.target.value;
                updateAllPreviews();
            });
        });

        // Color pickers (#37)
        const primaryColor = document.getElementById('primaryColor');
        const bgColor = document.getElementById('bgColor');
        const textColor = document.getElementById('textColor');

        if (primaryColor) {
            primaryColor.addEventListener('input', (e) => {
                widgetState.primaryColor = e.target.value;
                updateAllPreviews();
            });
        }

        if (bgColor) {
            bgColor.addEventListener('input', (e) => {
                widgetState.bgColor = e.target.value;
                updateAllPreviews();
            });
        }

        if (textColor) {
            textColor.addEventListener('input', (e) => {
                widgetState.textColor = e.target.value;
                updateAllPreviews();
            });
        }

        // Greeting (#39)
        const greeting = document.getElementById('greeting');
        if (greeting) {
            greeting.addEventListener('input', (e) => {
                widgetState.greeting = e.target.value;
                updateAllPreviews();
            });
        }

        // Widget name
        const widgetName = document.getElementById('widgetName');
        if (widgetName) {
            widgetName.addEventListener('input', (e) => {
                widgetState.name = e.target.value;
                updateAllPreviews();
            });
        }

        // Watermark toggle
        const showWatermark = document.getElementById('showWatermark');
        if (showWatermark) {
            showWatermark.addEventListener('change', (e) => {
                widgetState.showWatermark = e.target.checked;
                updateAllPreviews();
            });
        }

        // Listen for system theme changes (for Auto mode)
        systemPrefersDark.addEventListener('change', () => {
            if (widgetState.theme === 'auto') {
                updateAllPreviews();
            }
        });
    }

    /**
     * Toggle preview chat open/closed
     */
    function togglePreviewChat(container) {
        const chat = container ? container.querySelector('.widget-chat') : document.querySelector('.widget-chat');
        if (chat) {
            chat.classList.toggle('open');
        }
    }

    /**
     * Create the preview HTML component
     */
    function createPreviewHTML() {
        return `
            <div class="widget-preview-container">
                <div class="preview-frame">
                    <div class="preview-website-mock">
                        <div class="mock-header">
                            <div class="mock-dots">
                                <span></span><span></span><span></span>
                            </div>
                            <div class="mock-url">yourwebsite.com</div>
                        </div>
                        <div class="mock-content">
                            <div class="mock-line w60"></div>
                            <div class="mock-line w80"></div>
                            <div class="mock-line w40"></div>
                        </div>
                    </div>
                    <div class="preview-widget position-${widgetState.position} theme-${widgetState.theme}">
                        <div class="widget-button" onclick="window.ChatbotPreview.toggleChat(this.parentElement.parentElement)">
                            <span>💬</span>
                        </div>
                        <div class="widget-chat">
                            <div class="chat-header">
                                <span class="chat-title">${widgetState.name}</span>
                                <button class="chat-close" onclick="window.ChatbotPreview.toggleChat(this.closest('.widget-preview-container'))">×</button>
                            </div>
                            <div class="chat-messages">
                                <div class="message bot preview-greeting">${widgetState.greeting}</div>
                            </div>
                            <div class="chat-input">
                                <input type="text" placeholder="Type a message..." readonly>
                                <button>→</button>
                            </div>
                            <div class="chat-watermark" style="display: ${widgetState.showWatermark ? 'block' : 'none'}">Powered by ResonantOS</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Initialize the module
     */
    function init() {
        // Sync state from DOM
        const positionEl = document.querySelector('input[name="position"]:checked');
        const themeEl = document.querySelector('input[name="theme"]:checked');
        const primaryColorEl = document.getElementById('primaryColor');
        const bgColorEl = document.getElementById('bgColor');
        const textColorEl = document.getElementById('textColor');
        const greetingEl = document.getElementById('greeting');
        const widgetNameEl = document.getElementById('widgetName');
        const showWatermarkEl = document.getElementById('showWatermark');

        if (positionEl) widgetState.position = positionEl.value;
        if (themeEl) widgetState.theme = themeEl.value;
        if (primaryColorEl) widgetState.primaryColor = primaryColorEl.value;
        if (bgColorEl) widgetState.bgColor = bgColorEl.value;
        if (textColorEl) widgetState.textColor = textColorEl.value;
        if (greetingEl) widgetState.greeting = greetingEl.value;
        if (widgetNameEl) widgetState.name = widgetNameEl.value;
        if (showWatermarkEl) widgetState.showWatermark = showWatermarkEl.checked;

        initEventListeners();
        updateAllPreviews();
    }

    // Expose public API
    window.ChatbotPreview = {
        init,
        updateAllPreviews,
        setEditMode,
        setCreateMode,
        toggleChat: togglePreviewChat,
        createPreviewHTML,
        getState: () => ({ ...widgetState }),
        setState: (newState) => {
            Object.assign(widgetState, newState);
            updateAllPreviews();
        }
    };

})();
