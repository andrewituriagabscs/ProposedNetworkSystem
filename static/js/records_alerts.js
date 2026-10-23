/**
 * Alerts and Ping Records table rendering and pagination.
 */

let allTelemetry = [];
let allAlerts = [];
let pingRecordsCurrentPage = 1;
let alertsCurrentPage = 1;
const recordsPerPage = 10;

function renderPaginationForTable(containerId, currentPage, totalItems, pageChangeHandler) {
    const totalPages = Math.ceil(totalItems / recordsPerPage);
    const container = document.querySelector(containerId);
    if (!container) return;

    if (totalPages <= 1) {
        container.replaceChildren();
        return;
    }

    const makeButton = (label, page, { active = false, disabled = false } = {}) => {
        const button = document.createElement('button');
        button.className = `range-button${active ? ' active' : ''}`;
        button.type = 'button';
        button.textContent = label;
        button.disabled = disabled;
        if (active) button.setAttribute('aria-current', 'page');
        button.addEventListener('click', () => pageChangeHandler(page));
        return button;
    };

    const controls = [makeButton('← Previous', currentPage - 1, { disabled: currentPage === 1 })];
    for (let i = 1; i <= totalPages; i++) {
        controls.push(makeButton(String(i), i, { active: i === currentPage }));
    }
    controls.push(makeButton('Next →', currentPage + 1, { disabled: currentPage === totalPages }));

    const pageLabel = document.createElement('span');
    pageLabel.style.marginLeft = '16px';
    pageLabel.style.color = '#666';
    pageLabel.style.fontSize = '0.9em';
    pageLabel.textContent = `Page ${currentPage} of ${totalPages}`;
    controls.push(pageLabel);

    container.replaceChildren(...controls);
}

function renderPingRecords(telemetry) {
    allTelemetry = telemetry.slice().reverse();
    const startIndex = (pingRecordsCurrentPage - 1) * recordsPerPage;
    const endIndex = startIndex + recordsPerPage;
    const pageRecords = allTelemetry.slice(startIndex, endIndex);

    const tbody = document.querySelector('#reports-table tbody');
    if (tbody) {
        tbody.innerHTML = pageRecords.map((sample) => `
            <tr data-recorded-at="${sample.recorded_at}">
                <td>${sample.recorded_at}</td>
                <td>${escapeHtml(sample.device_name)}</td>
                <td>${sample.target}</td>
                <td>${sample.ping_received}/${sample.ping_sent}</td>
                <td>${sample.packet_loss}%</td>
                <td>${sample.latency_min_display}</td>
                <td>${sample.latency_median_display}</td>
                <td>${sample.latency_max_display}</td>
            </tr>
        `).join('') || '<tr><td colspan="8">No ping records yet.</td></tr>';
    }

    renderPaginationForTable('#ping-records-pagination', pingRecordsCurrentPage, allTelemetry.length, goToPingRecordsPage);
}

function renderAlertsTable(alerts) {
    allAlerts = alerts;
    const startIndex = (alertsCurrentPage - 1) * recordsPerPage;
    const endIndex = startIndex + recordsPerPage;
    const pageAlerts = allAlerts.slice(startIndex, endIndex);

    const rows = pageAlerts.map((alert) => `<tr><td>${alert.recorded_at}</td><td>${escapeHtml(alert.device_name)}</td><td>${escapeHtml(alert.message)}</td></tr>`).join('');
    const allRows = pageAlerts.map((alert) => `<tr><td>${alert.recorded_at}</td><td>${escapeHtml(alert.device_name)}</td><td>${escapeHtml(alert.message)}</td><td><span class="status-pill status-warning">Open</span></td></tr>`).join('');

    const alertRows = document.querySelector('#alert-rows');
    if (alertRows) alertRows.innerHTML = rows || '<tr><td colspan="3">No ping alerts.</td></tr>';
    const allAlertRows = document.querySelector('#all-alerts-rows');
    if (allAlertRows) allAlertRows.innerHTML = allRows || '<tr><td colspan="4">No ping alerts.</td></tr>';

    renderPaginationForTable('#alerts-pagination', alertsCurrentPage, allAlerts.length, goToAlertsPage);
    renderPaginationForTable('#all-alerts-pagination', alertsCurrentPage, allAlerts.length, goToAlertsPage);
}

function goToPingRecordsPage(pageNum) {
    pingRecordsCurrentPage = pageNum;
    renderPingRecords(allTelemetry.slice().reverse());
}

function goToAlertsPage(pageNum) {
    alertsCurrentPage = pageNum;
    renderAlertsTable(allAlerts);
}

function initHistoryRangeControls() {
    document.querySelectorAll('.range-button[data-hours]').forEach((button) => {
        button.addEventListener('click', () => {
            const cutoff = Date.now() - Number(button.dataset.hours) * 3600000;
            document.querySelectorAll('.range-button[data-hours]').forEach((item) => {
                item.classList.toggle('active', item === button);
            });
            document.querySelectorAll('#reports-table tbody tr[data-recorded-at]').forEach((row) => {
                row.hidden = Date.parse(row.dataset.recordedAt) < cutoff;
            });
        });
    });
}
