/**
 * Application entrypoint and periodic status polling.
 */

let latestSampleId = null;

async function refreshStatus() {
    try {
        const data = await requestJson('/api/status');
        const devices = data.devices || [];
        const telemetry = data.telemetry || [];
        const alerts = data.alerts || [];
        const latestByTarget = new Map();
        telemetry.forEach((sample) => {
            if (!latestByTarget.has(sample.target)) latestByTarget.set(sample.target, sample);
        });

        renderDevices(devices.map((device) => ({
            ...device,
            latest: latestByTarget.get(device.target) || null,
        })));

        const activeDevices = devices.filter((d) => d.active);
        const reachableDevices = activeDevices.filter((d) => latestByTarget.get(d.target)?.online);
        const networkHealth = activeDevices.length === 0
            ? 'Waiting'
            : reachableDevices.length === activeDevices.length
                ? 'Good'
                : reachableDevices.length > 0 ? 'Degraded' : 'Offline';

        const latencies = [...latestByTarget.values()]
            .map((sample) => sample.latency_median_ms ?? sample.latency_ms)
            .filter((value) => value !== null && value !== undefined && Number.isFinite(Number(value)));

        const averageLatency = latencies.length
            ? `${Math.round(latencies.reduce((total, val) => total + Number(val), 0) / latencies.length * 10) / 10} ms`
            : 'N/A';

        const healthEl = document.querySelector('#network-health');
        if (healthEl) healthEl.textContent = networkHealth;
        const alertsEl = document.querySelector('#open-alerts');
        if (alertsEl) alertsEl.textContent = alerts.length;
        const avgLatEl = document.querySelector('#metric-average-latency');
        if (avgLatEl) avgLatEl.textContent = averageLatency;
        const reachEl = document.querySelector('#metric-reachable');
        if (reachEl) reachEl.textContent = `${reachableDevices.length} / ${latestByTarget.size}`;
        const monEl = document.querySelector('#metric-monitoring');
        if (monEl) monEl.textContent = activeDevices.length;
        const samplesEl = document.querySelector('#metric-samples');
        if (samplesEl) samplesEl.textContent = telemetry.filter((s) => s.protocol === 'icmp').length;
        const updatedEl = document.querySelector('#dashboard-updated');
        if (updatedEl) updatedEl.textContent = new Date().toLocaleString();

        const fresh = telemetry.slice().reverse();
        if (fresh.length && fresh[fresh.length - 1].id !== latestSampleId) {
            latestSampleId = fresh[fresh.length - 1].id;
            window.monitorHistory = fresh.map((sample) => ({
                time: sample.recorded_at,
                device: sample.target,
                latency: sample.latency_median_ms ?? sample.latency_ms,
                latency_min_display: sample.latency_min_display,
                latency_median_display: sample.latency_median_display,
                latency_max_display: sample.latency_max_display,
                ping_received: sample.ping_received,
                ping_sent: sample.ping_sent,
                online: Boolean(sample.online),
                packet_loss: sample.packet_loss,
            }));
            renderPingRecords(fresh);
            if (typeof drawPingChart === 'function') drawPingChart();
        }
        renderAlertsTable(alerts);
    } catch (error) {
        setStatus(error.message);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initRouter();
    initHistoryRangeControls();

    const mlRecRows = document.querySelector('#ml-recommendation-rows');
    if (mlRecRows) {
        mlRecRows.addEventListener('click', (event) => {
            const button = event.target.closest('[data-select-suggestion]');
            if (button) {
                selectMlRecommendation(Number(button.dataset.selectTelemetry), button.dataset.selectSuggestion, button);
            }
        });
    }

    requestJson('/api/devices')
        .then((data) => {
            const subnetInput = document.querySelector('#subnet-input');
            if (subnetInput && data.local_network?.suggested_subnet) {
                subnetInput.value = data.local_network.suggested_subnet;
            }
        })
        .catch((error) => setStatus(error.message));

    loadBuildingName();
    refreshMlPanel();
    refreshStatus();
    window.setInterval(refreshStatus, 5000);
});
