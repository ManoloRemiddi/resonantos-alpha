/**
 * ResonantOS Chat Widget - Loader Script
 * This script is loaded on customer websites to show the chat widget.
 * 
 * Usage:
 * <script src="https://yourdomain.com/static/js/widget.js" 
 *         data-widget-id="your-widget-id"
 *         data-api-url="https://yourdomain.com/api"
 *         data-position="bottom-right"
 *         data-theme="dark"
 *         data-primary-color="#4ade80">
 * </script>
 */
(function() {
  'use strict';
  
  // Get configuration from script tag
  const currentScript = document.currentScript || (function() {
    const scripts = document.getElementsByTagName('script');
    return scripts[scripts.length - 1];
  })();
  
  const CONFIG = {
    widgetId: currentScript.dataset.widgetId || 'demo',
    apiUrl: currentScript.dataset.apiUrl || window.location.origin + '/api',
    position: currentScript.dataset.position || 'bottom-right',
    theme: currentScript.dataset.theme || 'dark',
    primaryColor: currentScript.dataset.primaryColor || '#4ade80',
  };
  
  // State
  let widgetConfig = null;
  let isOpen = false;
  let sessionId = 'session_' + Math.random().toString(36).substr(2, 9);
  
  // Fetch widget configuration from server
  async function fetchConfig() {
    try {
      const response = await fetch(`${CONFIG.apiUrl}/chatbots/${CONFIG.widgetId}`);
      if (!response.ok) throw new Error('Widget not found');
      widgetConfig = await response.json();
      return widgetConfig;
    } catch (error) {
      console.error('ResonantOS Widget: Failed to load config', error);
      // Use defaults
      widgetConfig = {
        name: 'Assistant',
        greeting: 'Hi! How can I help you today?',
        show_watermark: true,
        primary_color: CONFIG.primaryColor,
        theme: CONFIG.theme,
        position: CONFIG.position,
      };
      return widgetConfig;
    }
  }
  
  // Create widget DOM
  function createWidget() {
    const config = widgetConfig || {};
    const primaryColor = config.primary_color || CONFIG.primaryColor;
    const theme = config.theme || CONFIG.theme;
    const position = config.position || CONFIG.position;
    const showWatermark = config.show_watermark !== false;
    
    // Create container
    const container = document.createElement('div');
    container.id = 'ros-widget-container';
    container.className = `ros-widget ros-${position} ros-${theme}`;
    
    // Create button
    const button = document.createElement('button');
    button.className = 'ros-widget-button';
    button.innerHTML = '💬';
    button.style.backgroundColor = primaryColor;
    button.onclick = toggleWidget;
    
    // Create chat window
    const chat = document.createElement('div');
    chat.className = 'ros-widget-chat';
    chat.innerHTML = `
      <div class="ros-chat-header" style="background: ${primaryColor}">
        <span class="ros-chat-title">${escapeHtml(config.name || 'Assistant')}</span>
        <button class="ros-chat-close" onclick="ROSWidget.close()">&times;</button>
      </div>
      <div class="ros-chat-messages" id="ros-messages">
        <div class="ros-message ros-message-bot">${escapeHtml(config.greeting || 'Hi! How can I help you?')}</div>
      </div>
      <div class="ros-chat-input">
        <input type="text" id="ros-input" placeholder="Type a message..." onkeypress="if(event.key==='Enter')ROSWidget.send()">
        <button onclick="ROSWidget.send()" style="background: ${primaryColor}">➤</button>
      </div>
      ${showWatermark ? '<div class="ros-chat-watermark">Powered by <a href="https://resonantos.com" target="_blank">ResonantOS</a></div>' : ''}
    `;
    
    container.appendChild(button);
    container.appendChild(chat);
    
    // Add styles
    addStyles(primaryColor, theme);
    
    // Add to page
    document.body.appendChild(container);
  }
  
  // Add widget styles
  function addStyles(primaryColor, theme) {
    const isDark = theme === 'dark';
    const bgColor = isDark ? '#1a1a2e' : '#ffffff';
    const textColor = isDark ? '#e0e0e0' : '#333333';
    const inputBg = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)';
    
    const style = document.createElement('style');
    style.id = 'ros-widget-styles';
    style.textContent = `
      .ros-widget {
        position: fixed;
        z-index: 999999;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      }
      .ros-bottom-right { bottom: 20px; right: 20px; }
      .ros-bottom-left { bottom: 20px; left: 20px; }
      
      .ros-widget-button {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        border: none;
        cursor: pointer;
        font-size: 26px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        transition: transform 0.2s, box-shadow 0.2s;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .ros-widget-button:hover {
        transform: scale(1.1);
        box-shadow: 0 6px 24px rgba(0,0,0,0.4);
      }
      
      .ros-widget-chat {
        position: absolute;
        bottom: 80px;
        right: 0;
        width: 380px;
        max-width: calc(100vw - 40px);
        height: 520px;
        max-height: calc(100vh - 120px);
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 8px 40px rgba(0,0,0,0.3);
        display: none;
        flex-direction: column;
        background: ${bgColor};
        color: ${textColor};
      }
      .ros-widget-chat.open { display: flex; }
      .ros-bottom-left .ros-widget-chat { right: auto; left: 0; }
      
      .ros-chat-header {
        padding: 16px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: white;
        font-weight: 600;
        font-size: 16px;
      }
      .ros-chat-close {
        background: none;
        border: none;
        color: white;
        font-size: 24px;
        cursor: pointer;
        padding: 0;
        line-height: 1;
        opacity: 0.8;
        transition: opacity 0.2s;
      }
      .ros-chat-close:hover { opacity: 1; }
      
      .ros-chat-messages {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      
      .ros-message {
        max-width: 85%;
        padding: 12px 16px;
        border-radius: 16px;
        word-wrap: break-word;
        line-height: 1.5;
        font-size: 14px;
      }
      .ros-message-bot {
        background: ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)'};
        align-self: flex-start;
        border-bottom-left-radius: 4px;
      }
      .ros-message-user {
        background: ${primaryColor};
        color: white;
        align-self: flex-end;
        border-bottom-right-radius: 4px;
      }
      .ros-message-typing {
        background: ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)'};
        align-self: flex-start;
      }
      .ros-typing-dots {
        display: inline-flex;
        gap: 4px;
      }
      .ros-typing-dots span {
        width: 8px;
        height: 8px;
        background: ${isDark ? '#888' : '#999'};
        border-radius: 50%;
        animation: ros-typing 1.4s infinite;
      }
      .ros-typing-dots span:nth-child(2) { animation-delay: 0.2s; }
      .ros-typing-dots span:nth-child(3) { animation-delay: 0.4s; }
      @keyframes ros-typing {
        0%, 60%, 100% { transform: translateY(0); }
        30% { transform: translateY(-6px); }
      }
      
      .ros-chat-input {
        display: flex;
        padding: 12px 16px;
        border-top: 1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'};
        gap: 8px;
      }
      .ros-chat-input input {
        flex: 1;
        padding: 12px 16px;
        border: none;
        border-radius: 24px;
        background: ${inputBg};
        color: ${textColor};
        font-size: 14px;
        outline: none;
      }
      .ros-chat-input input::placeholder {
        color: ${isDark ? '#888' : '#999'};
      }
      .ros-chat-input button {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        border: none;
        color: white;
        cursor: pointer;
        font-size: 18px;
        transition: transform 0.2s;
      }
      .ros-chat-input button:hover {
        transform: scale(1.05);
      }
      
      .ros-chat-watermark {
        text-align: center;
        padding: 10px;
        font-size: 11px;
        opacity: 0.7;
      }
      .ros-chat-watermark a {
        color: ${primaryColor};
        text-decoration: underline;
        cursor: pointer;
      }
      .ros-chat-watermark a:hover {
        opacity: 1;
      }
    `;
    document.head.appendChild(style);
  }
  
  // Toggle widget visibility
  function toggleWidget() {
    const chat = document.querySelector('.ros-widget-chat');
    if (chat) {
      isOpen = !isOpen;
      chat.classList.toggle('open', isOpen);
      if (isOpen) {
        document.getElementById('ros-input')?.focus();
      }
    }
  }
  
  // Send message
  async function sendMessage() {
    const input = document.getElementById('ros-input');
    const messages = document.getElementById('ros-messages');
    const message = input?.value?.trim();
    
    if (!message || !messages) return;
    
    // Add user message
    const userMsg = document.createElement('div');
    userMsg.className = 'ros-message ros-message-user';
    userMsg.textContent = message;
    messages.appendChild(userMsg);
    
    input.value = '';
    messages.scrollTop = messages.scrollHeight;
    
    // Show typing indicator
    const typingMsg = document.createElement('div');
    typingMsg.className = 'ros-message ros-message-typing';
    typingMsg.innerHTML = '<span class="ros-typing-dots"><span></span><span></span><span></span></span>';
    messages.appendChild(typingMsg);
    messages.scrollTop = messages.scrollHeight;
    
    try {
      const response = await fetch(`${CONFIG.apiUrl}/chat/${CONFIG.widgetId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message,
          sessionId: sessionId
        })
      });
      
      const data = await response.json();
      
      typingMsg.remove();
      
      const botMsg = document.createElement('div');
      botMsg.className = 'ros-message ros-message-bot';
      botMsg.textContent = data.response || 'Sorry, I could not process that.';
      messages.appendChild(botMsg);
      messages.scrollTop = messages.scrollHeight;
      
    } catch (error) {
      console.error('ResonantOS Widget: Send error', error);
      
      typingMsg.remove();
      
      const errorMsg = document.createElement('div');
      errorMsg.className = 'ros-message ros-message-bot';
      errorMsg.textContent = 'Sorry, there was an error. Please try again.';
      messages.appendChild(errorMsg);
      messages.scrollTop = messages.scrollHeight;
    }
  }
  
  // Utility: escape HTML
  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  // Initialize widget
  async function init() {
    await fetchConfig();
    createWidget();
  }
  
  // Expose global API
  window.ROSWidget = {
    open: () => {
      const chat = document.querySelector('.ros-widget-chat');
      if (chat) { chat.classList.add('open'); isOpen = true; }
    },
    close: () => {
      const chat = document.querySelector('.ros-widget-chat');
      if (chat) { chat.classList.remove('open'); isOpen = false; }
    },
    toggle: toggleWidget,
    send: sendMessage,
    destroy: () => {
      const container = document.getElementById('ros-widget-container');
      const styles = document.getElementById('ros-widget-styles');
      if (container) container.remove();
      if (styles) styles.remove();
    }
  };
  
  // Auto-initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
