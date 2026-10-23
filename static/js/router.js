/**
 * Client-side Router for Ping Monitoring System.
 * Supports separated URLs (/dashboard, /ping, /alerts, /records, /ml-insights, /settings, /about)
 * with seamless history.pushState and popstate support.
 */

const ROUTE_VIEW_MAP = {
    '/': 'dashboard',
    '/dashboard': 'dashboard',
    '/ping': 'ping',
    '/monitor': 'ping',
    '/alerts': 'alerts',
    '/records': 'records',
    '/reports': 'records',
    '/ping-records': 'records',
    '/ml-insights': 'ml-insights',
    '/settings': 'settings',
    '/about': 'about',
};

const VIEW_ROUTE_MAP = {
    'dashboard': '/dashboard',
    'ping': '/ping',
    'alerts': '/alerts',
    'records': '/records',
    'ml-insights': '/ml-insights',
    'settings': '/settings',
    'about': '/about',
};

function navigateTo(viewName, pushState = true) {
    if (!viewName) return;

    // Normalize monitor -> ping, reports -> records
    if (viewName === 'monitor') viewName = 'ping';
    if (viewName === 'reports') viewName = 'records';

    const targetUrl = VIEW_ROUTE_MAP[viewName] || '/dashboard';

    // Update browser URL if requested and different
    if (pushState && window.location.pathname !== targetUrl) {
        window.history.pushState({ view: viewName }, '', targetUrl);
    }

    // Update navigation sidebar active state
    document.querySelectorAll('.nav-item').forEach((item) => {
        const itemTarget = item.dataset.view;
        const isMatch = itemTarget === viewName || 
                       (viewName === 'ping' && itemTarget === 'monitor') ||
                       (viewName === 'records' && itemTarget === 'reports');
        item.classList.toggle('active', isMatch);
        if (isMatch) {
            item.setAttribute('aria-current', 'page');
        } else {
            item.removeAttribute('aria-current');
        }
    });

    // Show active panel, hide others
    document.querySelectorAll('[data-panel]').forEach((panel) => {
        const panelKey = panel.dataset.panel;
        const isMatch = panelKey === viewName ||
                       (viewName === 'ping' && panelKey === 'monitor') ||
                       (viewName === 'records' && panelKey === 'reports');
        panel.hidden = !isMatch;
        panel.classList.toggle('active', isMatch);
    });

    // View-specific trigger hooks
    if (viewName === 'ping') {
        if (typeof drawPingChart === 'function') drawPingChart();
        if (typeof refreshStatus === 'function') refreshStatus();
    } else if (viewName === 'ml-insights') {
        if (typeof refreshMlPanel === 'function') refreshMlPanel();
    } else if (viewName === 'settings') {
        if (typeof loadExternalReferenceSetting === 'function') loadExternalReferenceSetting();
        if (typeof loadDatabaseSelector === 'function') loadDatabaseSelector();
    }
}

function initRouter() {
    // Intercept navigation link clicks
    document.addEventListener('click', (event) => {
        const navItem = event.target.closest('.nav-item');
        if (!navItem) return;

        // Allow opening in new tab/window if modifier keys are pressed
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.which === 2) {
            return;
        }

        event.preventDefault();
        const viewName = navItem.dataset.view;
        if (viewName) {
            navigateTo(viewName, true);
        }
    });

    // Handle browser Back / Forward history buttons
    window.addEventListener('popstate', (event) => {
        const path = window.location.pathname;
        const viewName = ROUTE_VIEW_MAP[path] || 'dashboard';
        navigateTo(viewName, false);
    });

    // Initialize initial view from current URL path
    const initialPath = window.location.pathname;
    const initialView = ROUTE_VIEW_MAP[initialPath] || 'dashboard';
    navigateTo(initialView, false);
}
