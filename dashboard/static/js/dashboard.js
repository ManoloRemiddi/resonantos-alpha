/**
 * ResonantOS Dashboard - Main JavaScript
 */

// ============================================
// Theme Management
// ============================================

function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    // Update toggle button
    const themeIcon = document.querySelector('.theme-icon');
    const themeLabel = document.querySelector('.theme-label');
    
    if (themeIcon) {
        themeIcon.textContent = newTheme === 'dark' ? '🌙' : '☀️';
    }
    if (themeLabel) {
        themeLabel.textContent = newTheme === 'dark' ? 'Dark Mode' : 'Light Mode';
    }
}

function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    const themeIcon = document.querySelector('.theme-icon');
    const themeLabel = document.querySelector('.theme-label');
    
    if (themeIcon) {
        themeIcon.textContent = savedTheme === 'dark' ? '🌙' : '☀️';
    }
    if (themeLabel) {
        themeLabel.textContent = savedTheme === 'dark' ? 'Dark Mode' : 'Light Mode';
    }
}

// ============================================
// Data Refresh
// ============================================

let refreshInterval = null;

function refreshData() {
    // Show loading state
    const statusDot = document.querySelector('.status-dot');
    if (statusDot) {
        statusDot.style.animation = 'none';
        statusDot.style.background = 'var(--warning)';
    }
    
    // Trigger page-specific refresh
    if (typeof loadOverviewData === 'function') {
        loadOverviewData();
    } else if (typeof loadAgents === 'function') {
        loadAgents();
    } else if (typeof loadStatusData === 'function') {
        loadStatusData();
    } else if (typeof loadChatbots === 'function') {
        loadChatbots();
    } else if (typeof loadWalletData === 'function') {
        loadWalletData();
    }
    
    // Reset status indicator
    setTimeout(() => {
        if (statusDot) {
            statusDot.style.animation = 'pulse 2s infinite';
            statusDot.style.background = 'var(--success)';
        }
    }, 500);
}

function startAutoRefresh(intervalSeconds = 30) {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
    
    refreshInterval = setInterval(() => {
        refreshData();
    }, intervalSeconds * 1000);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// ============================================
// Utility Functions
// ============================================

function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'k';
    }
    return num.toString();
}

function formatTimeAgo(isoDate) {
    const date = new Date(isoDate);
    const now = new Date();
    const diff = (now - date) / 1000; // seconds
    
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + ' min ago';
    if (diff < 86400) return Math.floor(diff / 3600) + ' hours ago';
    if (diff < 604800) return Math.floor(diff / 86400) + ' days ago';
    return date.toLocaleDateString();
}

function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
}

// ============================================
// Toast Notifications
// ============================================

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Remove after delay
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================
// API Helpers
// ============================================

async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        showToast(`Error: ${error.message}`, 'error');
        throw error;
    }
}

async function postAPI(endpoint, data) {
    return fetchAPI(endpoint, {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

// ============================================
// Keyboard Shortcuts
// ============================================

function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + R: Refresh
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            e.preventDefault();
            refreshData();
        }
        
        // Escape: Close modals
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal.active').forEach(modal => {
                modal.classList.remove('active');
            });
        }
        
        // Ctrl/Cmd + K: Search (if available)
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            const searchInput = document.querySelector('#docsSearch, #searchInput');
            if (searchInput) {
                e.preventDefault();
                searchInput.focus();
            }
        }
    });
}

// ============================================
// Connection Status
// ============================================

let connectionCheckInterval = null;

function startConnectionCheck() {
    connectionCheckInterval = setInterval(checkConnection, 30000);
    checkConnection();
}

async function checkConnection() {
    // Handled by base.html updateGatewayStatus() — no-op here to avoid conflicts
}

// ============================================
// Initialization
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initKeyboardShortcuts();
    startConnectionCheck();
    
    // Start auto-refresh if enabled
    const autoRefresh = localStorage.getItem('autoRefresh') !== 'false';
    const interval = parseInt(localStorage.getItem('refreshInterval')) || 30;
    
    if (autoRefresh) {
        startAutoRefresh(interval);
    }
});

// Handle visibility changes
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        refreshData();
    }
});

// ============================================
// Session Timer
// ============================================

const SESSION_RESET_HOURS = [4, 9, 14, 19, 23]; // Claude API reset schedule

function initSessionTimer() {
    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        const menu = document.getElementById('sessionMenu');
        const container = document.getElementById('sessionTimerContainer');
        if (menu && !container?.contains(e.target)) {
            menu.classList.remove('show');
        }
    });
    
    updateSessionCountdown();
    setInterval(updateSessionCountdown, 30000); // Update every 30 seconds
}

function toggleSessionMenu(event) {
    if (event) event.stopPropagation();
    const menu = document.getElementById('sessionMenu');
    if (menu) {
        menu.classList.toggle('show');
        updateSessionMenuInfo();
    }
}

function updateSessionCountdown() {
    const countdownEl = document.getElementById('sessionCountdown');
    if (!countdownEl) return;
    
    const now = new Date();
    const currentHour = now.getHours();
    const currentMinutes = now.getMinutes();
    const currentTimeInMinutes = currentHour * 60 + currentMinutes;
    
    // Find next reset time
    let nextResetHour = null;
    for (const hour of SESSION_RESET_HOURS) {
        if (hour * 60 > currentTimeInMinutes) {
            nextResetHour = hour;
            break;
        }
    }
    
    // If no reset left today, next is first reset tomorrow
    let nextReset;
    if (nextResetHour === null) {
        nextResetHour = SESSION_RESET_HOURS[0];
        nextReset = new Date(now);
        nextReset.setDate(nextReset.getDate() + 1);
        nextReset.setHours(nextResetHour, 0, 0, 0);
    } else {
        nextReset = new Date(now);
        nextReset.setHours(nextResetHour, 0, 0, 0);
    }
    
    const remaining = nextReset.getTime() - now.getTime();
    const hours = Math.floor(remaining / (60 * 60 * 1000));
    const minutes = Math.floor((remaining % (60 * 60 * 1000)) / (60 * 1000));
    
    countdownEl.textContent = `Resets in ${hours}h ${minutes}m`;
    
    // Color coding
    countdownEl.className = 'timer-text';
    if (remaining < 30 * 60 * 1000) {
        countdownEl.classList.add('critical');
    } else if (remaining < 60 * 60 * 1000) {
        countdownEl.classList.add('warning');
    } else {
        countdownEl.classList.add('ok');
    }
}

function updateSessionMenuInfo() {
    const infoEl = document.getElementById('sessionMenuInfo');
    if (!infoEl) return;
    
    const sessionStart = localStorage.getItem('claudeSessionStart');
    
    if (!sessionStart) {
        infoEl.textContent = 'No session set - click to start tracking';
        return;
    }
    
    const startTime = parseInt(sessionStart, 10);
    const startDate = new Date(startTime);
    const elapsed = Date.now() - startTime;
    const elapsedHours = Math.floor(elapsed / (60 * 60 * 1000));
    const elapsedMinutes = Math.floor((elapsed % (60 * 60 * 1000)) / (60 * 1000));
    
    infoEl.textContent = `Started: ${startDate.toLocaleTimeString()} (${elapsedHours}h ${elapsedMinutes}m ago)`;
}

function setSessionStartNow() {
    localStorage.setItem('claudeSessionStart', Date.now().toString());
    updateSessionCountdown();
    updateSessionMenuInfo();
    closeSessionMenu();
}

function setSessionStart30MinAgo() {
    localStorage.setItem('claudeSessionStart', (Date.now() - 30 * 60 * 1000).toString());
    updateSessionCountdown();
    updateSessionMenuInfo();
    closeSessionMenu();
}

function setSessionStart1HrAgo() {
    localStorage.setItem('claudeSessionStart', (Date.now() - 60 * 60 * 1000).toString());
    updateSessionCountdown();
    updateSessionMenuInfo();
    closeSessionMenu();
}

function clearSessionTimer() {
    localStorage.removeItem('claudeSessionStart');
    updateSessionCountdown();
    updateSessionMenuInfo();
    closeSessionMenu();
}

function closeSessionMenu() {
    const menu = document.getElementById('sessionMenu');
    if (menu) menu.classList.remove('show');
}

// ============================================
// Kanban Board
// ============================================

let tasksData = [];

async function loadTasks() {
    try {
        const response = await fetch('/api/tasks');
        if (!response.ok) throw new Error('Failed to fetch tasks');
        
        const data = await response.json();
        tasksData = data.tasks || [];
        renderKanban();
    } catch (error) {
        console.error('Error loading tasks:', error);
        // Show empty state
        renderKanban();
    }
}

function renderKanban() {
    const grouped = {
        todo: [],
        in_progress: [],
        done: []
    };
    
    tasksData.forEach(task => {
        if (task.status === 'archived') return;
        const status = task.status || 'todo';
        if (grouped[status]) {
            grouped[status].push(task);
        } else {
            grouped.todo.push(task);
        }
    });
    
    for (const [status, tasks] of Object.entries(grouped)) {
        const containerId = status === 'in_progress' ? 'tasks-inprogress' : `tasks-${status}`;
        const countId = status === 'in_progress' ? 'count-inprogress' : `count-${status}`;
        
        const container = document.getElementById(containerId);
        const countEl = document.getElementById(countId);
        
        if (container && countEl) {
            countEl.textContent = tasks.length;
            
            if (tasks.length === 0) {
                container.innerHTML = '<div class="kanban-empty">No tasks</div>';
            } else {
                container.innerHTML = tasks.map(task => `
                    <div class="kanban-task" data-task-id="${task.task_id || task.id}" draggable="true">
                        <div class="kanban-task-title">${escapeHtml(task.title)}</div>
                        <div class="kanban-task-meta">
                            ${task.priority ? `<span class="kanban-task-priority ${task.priority}">${task.priority}</span>` : ''}
                            ${task.category ? `<span>${task.category}</span>` : ''}
                        </div>
                    </div>
                `).join('');
            }
        }
    }
    
    setupKanbanDragDrop();
}

function setupKanbanDragDrop() {
    // Task drag handlers
    document.querySelectorAll('.kanban-task').forEach(task => {
        task.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('text/plain', task.dataset.taskId);
            task.classList.add('dragging');
        });
        
        task.addEventListener('dragend', () => {
            task.classList.remove('dragging');
            document.querySelectorAll('.kanban-column').forEach(col => {
                col.classList.remove('drag-over');
            });
        });
    });
    
    // Column drop handlers
    document.querySelectorAll('.kanban-column').forEach(column => {
        column.addEventListener('dragover', (e) => {
            e.preventDefault();
            column.classList.add('drag-over');
        });
        
        column.addEventListener('dragleave', () => {
            column.classList.remove('drag-over');
        });
        
        column.addEventListener('drop', async (e) => {
            e.preventDefault();
            column.classList.remove('drag-over');
            
            const taskId = e.dataTransfer.getData('text/plain');
            if (!taskId) return;
            
            const newStatus = column.dataset.status;
            if (!newStatus) return;
            
            await updateTaskStatus(taskId, newStatus);
        });
    });
}

async function updateTaskStatus(taskId, newStatus) {
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        
        if (!response.ok) throw new Error('Failed to update task');
        
        await loadTasks();
        showToast('Task updated', 'success');
    } catch (error) {
        console.error('Failed to update task:', error);
        showToast('Failed to update task', 'error');
    }
}

async function addQuickTask() {
    const input = document.getElementById('quickTaskInput');
    const title = input?.value?.trim();
    
    if (!title) return;
    
    try {
        const response = await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: title,
                status: 'todo',
                priority: 'medium'
            })
        });
        
        if (!response.ok) throw new Error('Failed to create task');
        
        input.value = '';
        await loadTasks();
        showToast('Task added', 'success');
    } catch (error) {
        console.error('Failed to create task:', error);
        showToast('Failed to create task', 'error');
    }
}

// ============================================
// Activity Feed (Terminal Style)
// ============================================

let activityFeedData = [];

async function loadActivityFeed() {
    try {
        const response = await fetch('/api/activity?limit=50');
        if (!response.ok) throw new Error('Failed to fetch activity');
        
        const data = await response.json();
        activityFeedData = data.activities || data.events || [];
        renderActivityFeed();
    } catch (error) {
        console.error('Error loading activity feed:', error);
    }
}

function renderActivityFeed() {
    const container = document.getElementById('activityFeed');
    if (!container) return;
    
    const filter = document.getElementById('activityFilter')?.value || '';
    
    let filtered = activityFeedData;
    if (filter) {
        filtered = activityFeedData.filter(a => a.type === filter || a.event_type === filter);
    }
    
    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="activity-log-line info">
                <span class="log-time">--:--:--</span>
                <span class="log-type">[INFO]</span>
                <span class="log-agent">system</span>
                <span class="log-message">No activity recorded yet</span>
            </div>
        `;
        return;
    }
    
    container.innerHTML = filtered.map(event => {
        const time = formatLogTime(event.timestamp || event.time);
        const type = (event.type || event.event_type || 'info').toLowerCase();
        const agent = event.agent || event.agent_type || 'system';
        const message = event.message || event.display_text || event.description || '';
        
        return `
            <div class="activity-log-line ${type}">
                <span class="log-time">${time}</span>
                <span class="log-type">[${type.toUpperCase()}]</span>
                <span class="log-agent">${escapeHtml(agent)}</span>
                <span class="log-message">${escapeHtml(message)}</span>
            </div>
        `;
    }).join('');
    
    // Auto-scroll if enabled
    const autoScroll = document.getElementById('autoScrollToggle')?.checked ?? true;
    if (autoScroll) {
        container.scrollTop = container.scrollHeight;
    }
}

function filterActivityFeed() {
    renderActivityFeed();
}

function formatLogTime(timestamp) {
    if (!timestamp) return '--:--:--';
    
    let date;
    if (typeof timestamp === 'number') {
        date = new Date(timestamp);
    } else if (typeof timestamp === 'string') {
        date = new Date(timestamp);
    } else {
        return '--:--:--';
    }
    
    return date.toLocaleTimeString('en-US', { hour12: false });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// Initialization (Extended)
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initKeyboardShortcuts();
    startConnectionCheck();
    
    // Initialize session timer
    initSessionTimer();
    
    // Load tasks and activity if on overview page
    if (document.getElementById('tasks-todo')) {
        loadTasks();
        setInterval(loadTasks, 60000); // Refresh every minute
    }
    
    if (document.getElementById('activityFeed')) {
        loadActivityFeed();
        setInterval(loadActivityFeed, 10000); // Refresh every 10 seconds
    }
    
    // Quick task enter key
    const quickTaskInput = document.getElementById('quickTaskInput');
    if (quickTaskInput) {
        quickTaskInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') addQuickTask();
        });
    }
    
    // Start auto-refresh if enabled
    const autoRefresh = localStorage.getItem('autoRefresh') !== 'false';
    const interval = parseInt(localStorage.getItem('refreshInterval')) || 30;
    
    if (autoRefresh) {
        startAutoRefresh(interval);
    }
});

// Handle visibility changes
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        refreshData();
        if (document.getElementById('activityFeed')) {
            loadActivityFeed();
        }
    }
});

// Export for use in other scripts
window.Dashboard = {
    toggleTheme,
    refreshData,
    startAutoRefresh,
    stopAutoRefresh,
    showToast,
    fetchAPI,
    postAPI,
    formatNumber,
    formatTimeAgo,
    formatBytes,
    // Session timer exports
    toggleSessionMenu,
    setSessionStartNow,
    setSessionStart30MinAgo,
    setSessionStart1HrAgo,
    clearSessionTimer,
    // Task exports
    loadTasks,
    addQuickTask
};
