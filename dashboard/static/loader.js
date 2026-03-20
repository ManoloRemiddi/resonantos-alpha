/**
 * ResonantOS Widget Loader - Thin SaaS Loader
 * 
 * This is the ONLY script customers embed on their sites.
 * Widget logic is served dynamically from our server with license enforcement.
 * 
 * Usage:
 * <script src="https://resonantos.com/widget/loader.js" data-chatbot-id="xxx"></script>
 */
(function() {
  'use strict';

  // Prevent double-initialization
  if (window.__ROS_INITIALIZED__) return;
  window.__ROS_INITIALIZED__ = true;

  // Get configuration from script tag
  var script = document.currentScript || (function() {
    var scripts = document.getElementsByTagName('script');
    for (var i = scripts.length - 1; i >= 0; i--) {
      if (scripts[i].src && scripts[i].src.indexOf('loader.js') !== -1) {
        return scripts[i];
      }
    }
    return scripts[scripts.length - 1];
  })();

  var chatbotId = script.getAttribute('data-chatbot-id') || script.dataset.chatbotId;
  
  if (!chatbotId) {
    console.error('[ResonantOS] Missing data-chatbot-id attribute');
    return;
  }

  // Determine API base URL from script src
  var scriptSrc = script.src;
  var apiBase = scriptSrc.replace(/\/widget\/loader\.js.*$/, '').replace(/\/static\/loader\.js.*$/, '') || window.location.origin;

  // Initialize: call server for widget config and code
  function init() {
    // Call server-side init endpoint - ALL feature gating happens here
    fetch(apiBase + '/api/widget/init/' + chatbotId, {
      method: 'GET',
      headers: { 
        'Accept': 'application/json',
        'X-Widget-Domain': window.location.hostname,
        'X-Widget-Origin': window.location.origin
      }
    })
    .then(function(r) { 
      if (!r.ok) throw new Error('Widget init failed: ' + r.status);
      return r.json(); 
    })
    .then(function(data) {
      if (data.error) {
        console.error('[ResonantOS] ' + data.error);
        return;
      }
      
      // Store config globally (widget will pick this up)
      window.__ROS_CONFIG__ = data.config;
      window.__ROS_LICENSE__ = data.license;
      
      // Load the widget script (served minified from server)
      loadWidgetScript(apiBase, data.widgetVersion || 'latest');
    })
    .catch(function(err) {
      console.error('[ResonantOS] Widget initialization failed:', err.message);
    });
  }

  function loadWidgetScript(base, version) {
    var widgetScript = document.createElement('script');
    // Widget is served from server - not bundled, not modifiable
    widgetScript.src = base + '/widget/v/' + version + '/widget.min.js';
    widgetScript.async = true;
    widgetScript.onerror = function() {
      console.error('[ResonantOS] Failed to load widget script');
    };
    document.head.appendChild(widgetScript);
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
