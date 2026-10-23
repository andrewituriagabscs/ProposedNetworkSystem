/**
 * API client and common utility functions.
 */

async function requestJson(url, options = {}) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const headers = { ...(options.headers || {}) };
    if (csrfToken && !headers['X-CSRF-TOKEN']) {
        headers['X-CSRF-TOKEN'] = csrfToken;
    }
    const response = await fetch(url, { ...options, headers });
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.error || payload.message || `Request failed (${response.status})`);
    }
    return payload;
}

function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    const element = document.createElement('span');
    element.textContent = String(value);
    return element.innerHTML;
}

function escapeAttribute(value) {
    return escapeHtml(value).replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}

function setStatus(message) {
    const el = document.querySelector('#discovery-status');
    if (el) el.textContent = message;
}

// Theme handling
function initTheme() {
    const themeToggle = document.querySelector('#theme-toggle');
    if (!themeToggle) return;

    function setTheme(isDark) {
        document.body.classList.toggle('dark-mode', isDark);
        themeToggle.checked = isDark;
        const label = document.querySelector('#theme-label');
        if (label) label.textContent = isDark ? 'Dark mode' : 'Light mode';
        localStorage.setItem('network-monitor-theme', isDark ? 'dark' : 'light');
    }

    setTheme(localStorage.getItem('network-monitor-theme') === 'dark');
    themeToggle.addEventListener('change', () => {
        setTheme(themeToggle.checked);
        if (typeof drawPingChart === 'function') drawPingChart();
    });
}
