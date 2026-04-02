(function() {
  'use strict';

  // Read config from script tag data attributes
  var script = document.currentScript;
  var config = {
    botId: script.dataset.widgetId || '',
    position: script.dataset.position || 'bottom-right',
    theme: script.dataset.theme || 'dark',
    primaryColor: script.dataset.primaryColor || '#10b981',
    bgColor: script.dataset.bgColor || '#09090b',
    textColor: script.dataset.textColor || '#d4d4d8',
    apiUrl: script.dataset.apiUrl || script.src.replace(/\/widget\.js.*$/, '')
  };

  var isOpen = false;
  var messages = [];
  var isLoading = false;

  // Inject styles
  var style = document.createElement('style');
  style.textContent = `
    .ros-widget-btn {
      position: fixed;
      ${config.position === 'bottom-left' ? 'left: 24px' : 'right: 24px'};
      bottom: 24px;
      width: 56px; height: 56px;
      border-radius: 50%;
      background: ${config.primaryColor};
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 16px rgba(0,0,0,0.3);
      display: flex; align-items: center; justify-content: center;
      z-index: 99999;
      transition: transform 0.2s;
    }
    .ros-widget-btn:hover { transform: scale(1.1); }
    .ros-widget-btn svg { width: 28px; height: 28px; fill: white; }

    .ros-widget-container {
      position: fixed;
      ${config.position === 'bottom-left' ? 'left: 24px' : 'right: 24px'};
      bottom: 96px;
      width: 380px;
      height: 520px;
      background: ${config.bgColor};
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
      display: none;
      flex-direction: column;
      z-index: 99999;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: ${config.textColor};
    }
    .ros-widget-container.open { display: flex; }

    .ros-widget-header {
      background: ${config.primaryColor};
      padding: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .ros-widget-header h3 {
      margin: 0; font-size: 16px; font-weight: 600; color: white;
    }
    .ros-widget-close {
      background: none; border: none; color: white;
      font-size: 20px; cursor: pointer; padding: 0 4px;
    }

    .ros-widget-messages {
      flex: 1;
      min-height: 0;
      overflow-y: auto;
      overscroll-behavior: contain;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .ros-msg {
      max-width: 85%;
      padding: 10px 14px;
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.5;
      word-wrap: break-word;
    }
    .ros-msg.user {
      align-self: flex-end;
      background: ${config.primaryColor};
      color: white;
      border-bottom-right-radius: 4px;
    }
    .ros-msg.assistant {
      align-self: flex-start;
      background: ${config.theme === 'dark' ? '#27272a' : '#f4f4f5'};
      color: ${config.textColor};
      border-bottom-left-radius: 4px;
    }
    .ros-msg.greeting {
      align-self: flex-start;
      background: ${config.theme === 'dark' ? '#27272a' : '#f4f4f5'};
      color: ${config.textColor};
      border-bottom-left-radius: 4px;
    }

    .ros-typing {
      align-self: flex-start;
      padding: 10px 14px;
      background: ${config.theme === 'dark' ? '#27272a' : '#f4f4f5'};
      border-radius: 12px;
      display: none;
    }
    .ros-typing.visible { display: block; }
    .ros-typing span {
      display: inline-block;
      width: 8px; height: 8px;
      background: ${config.textColor};
      border-radius: 50%;
      margin: 0 2px;
      opacity: 0.4;
      animation: ros-bounce 1.2s infinite;
    }
    .ros-typing span:nth-child(2) { animation-delay: 0.2s; }
    .ros-typing span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes ros-bounce {
      0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
      30% { transform: translateY(-6px); opacity: 1; }
    }

    .ros-widget-input {
      display: flex;
      padding: 12px;
      border-top: 1px solid ${config.theme === 'dark' ? '#3f3f46' : '#e4e4e7'};
      gap: 8px;
    }
    .ros-widget-input input {
      flex: 1;
      background: ${config.theme === 'dark' ? '#18181b' : '#fafafa'};
      border: 1px solid ${config.theme === 'dark' ? '#3f3f46' : '#d4d4d8'};
      border-radius: 8px;
      padding: 10px 12px;
      color: ${config.textColor};
      font-size: 14px;
      outline: none;
    }
    .ros-widget-input input::placeholder {
      color: ${config.theme === 'dark' ? '#71717a' : '#a1a1aa'};
    }
    .ros-widget-input button {
      background: ${config.primaryColor};
      border: none;
      border-radius: 8px;
      width: 40px; height: 40px;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
    }
    .ros-widget-input button svg { width: 18px; height: 18px; fill: white; }

    .ros-widget-footer {
      text-align: center;
      padding: 6px;
      font-size: 11px;
      opacity: 0.5;
    }
    .ros-widget-footer a { color: ${config.primaryColor}; text-decoration: none; }

    .ros-suggestions {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      padding: 0 16px 12px;
    }
    .ros-suggestions button {
      background: ${config.theme === 'dark' ? '#27272a' : '#f4f4f5'};
      border: 1px solid ${config.theme === 'dark' ? '#3f3f46' : '#d4d4d8'};
      border-radius: 16px;
      padding: 6px 12px;
      color: ${config.textColor};
      font-size: 12px;
      cursor: pointer;
      transition: background 0.2s;
    }
    .ros-suggestions button:hover {
      background: ${config.primaryColor};
      color: white;
      border-color: ${config.primaryColor};
    }
  `;
  document.head.appendChild(style);

  // Create toggle button
  var btn = document.createElement('button');
  btn.className = 'ros-widget-btn';
  btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>';
  document.body.appendChild(btn);

  // Create chat container
  var container = document.createElement('div');
  container.className = 'ros-widget-container';
  container.innerHTML = `
    <div class="ros-widget-header">
      <h3>ResonantOS Assistant</h3>
      <button class="ros-widget-close">&times;</button>
    </div>
    <div class="ros-widget-messages" id="ros-messages"></div>
    <div class="ros-suggestions" id="ros-suggestions"></div>
    <div class="ros-widget-input">
      <input type="text" placeholder="Type a message..." id="ros-input" />
      <button id="ros-send"><svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg></button>
    </div>
    <div class="ros-widget-footer">Powered by <a href="https://resonantos.com" target="_blank">ResonantOS</a></div>
  `;
  document.body.appendChild(container);

  var msgArea = container.querySelector('#ros-messages');

  // Prevent scroll events from leaking to the page
  container.addEventListener('wheel', function(e) {
    var el = msgArea;
    var atTop = el.scrollTop <= 0;
    var atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 1;
    if ((e.deltaY < 0 && atTop) || (e.deltaY > 0 && atBottom)) {
      // already at boundary — just stop, don't scroll page
      e.preventDefault();
    }
    e.stopPropagation();
  }, { passive: false });
  var input = container.querySelector('#ros-input');
  var sendBtn = container.querySelector('#ros-send');
  var suggestionsEl = container.querySelector('#ros-suggestions');
  var closeBtn = container.querySelector('.ros-widget-close');

  // Load chatbot config (greeting + suggestions)
  function loadConfig() {
    fetch(config.apiUrl + '/api/chatbots/' + config.botId)
      .then(function(r) { return r.json(); })
      .then(function(bot) {
        if (bot.greeting) {
          addMessage('assistant', bot.greeting, true);
        }
        if (bot.suggested_prompts) {
          var prompts = typeof bot.suggested_prompts === 'string'
            ? JSON.parse(bot.suggested_prompts) : bot.suggested_prompts;
          showSuggestions(prompts);
        }
      })
      .catch(function() {
        addMessage('assistant', 'Welcome! How can I help you?', true);
      });
  }

  function showSuggestions(prompts) {
    suggestionsEl.innerHTML = '';
    prompts.forEach(function(p) {
      var b = document.createElement('button');
      b.textContent = p;
      b.onclick = function() {
        suggestionsEl.innerHTML = '';
        sendMessage(p);
      };
      suggestionsEl.appendChild(b);
    });
  }

  function addMessage(role, text, isGreeting) {
    var div = document.createElement('div');
    div.className = 'ros-msg ' + (isGreeting ? 'greeting' : role);
    div.textContent = text;
    msgArea.appendChild(div);
    msgArea.scrollTop = msgArea.scrollHeight;
    if (!isGreeting) {
      messages.push({ role: role, content: text });
    }
  }

  function sendMessage(text) {
    if (!text.trim() || isLoading) return;
    addMessage('user', text);
    input.value = '';
    isLoading = true;

    // Show typing indicator
    var typing = document.createElement('div');
    typing.className = 'ros-typing visible';
    typing.innerHTML = '<span></span><span></span><span></span>';
    msgArea.appendChild(typing);
    msgArea.scrollTop = msgArea.scrollHeight;

    fetch(config.apiUrl + '/api/widget/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ botId: config.botId, messages: messages })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      typing.remove();
      if (data.reply) {
        addMessage('assistant', data.reply);
      } else {
        addMessage('assistant', 'Sorry, something went wrong.');
      }
      isLoading = false;
    })
    .catch(function() {
      typing.remove();
      addMessage('assistant', 'Connection error. Please try again.');
      isLoading = false;
    });
  }

  // Event listeners
  btn.onclick = function() {
    isOpen = !isOpen;
    container.classList.toggle('open', isOpen);
    if (isOpen && msgArea.children.length === 0) loadConfig();
    if (isOpen) input.focus();
  };

  closeBtn.onclick = function() {
    isOpen = false;
    container.classList.remove('open');
  };

  sendBtn.onclick = function() { sendMessage(input.value); };
  input.onkeydown = function(e) {
    if (e.key === 'Enter') sendMessage(input.value);
  };

  // Auto-load config
  loadConfig();
})();
