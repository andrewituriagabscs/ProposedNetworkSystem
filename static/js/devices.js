/**
 * Device discovery, device listing, pagination, and ping controls.
 */

window.monitorDevices = [];
window.monitorHistory = [];
let autoDiscoverTimer = null;
let autoDiscoverActive = false;
let allDiscoveredHosts = [];
let discoveryDeviceTypes = {};
let monitorCurrentPage = 1;
let monitorSearchQuery = '';
let monitorDeviceTypeFilter = '';
const itemsPerPage = 10;

async function discoverHosts(button, silent = false) {
    if (!silent) {
        button.disabled = true;
        setStatus('Discovering responding addresses...');
    }
    try {
        const limit = parseInt(document.querySelector('#discovery-limit')?.value) || 20;
        const subnetInput = document.querySelector('#subnet-input')?.value;
        const { hosts } = await requestJson('/api/discover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subnet: subnetInput, limit: limit }),
        });
        allDiscoveredHosts = hosts;
        filterDiscoveryRows();
        const discSec = document.querySelector('#discovery-section');
        if (discSec) discSec.hidden = false;
        const autoToggle = document.querySelector('#auto-discover-toggle');
        if (autoToggle) autoToggle.style.display = 'inline-block';
        if (!silent) {
            setStatus(`${hosts.length} responding address${hosts.length === 1 ? '' : 'es'} found.`);
        }
    } catch (error) {
        if (!silent) setStatus(error.message);
    } finally {
        if (!silent) button.disabled = false;
    }
}

function filterDiscoveryRows() {
    const showPhones = document.querySelector('#show-phones-toggle')?.checked ?? true;
    const selected = new Set(window.monitorDevices.map((d) => d.target));
    const tbody = document.querySelector('#discovered-rows');
    if (!tbody) return;

    const rows = allDiscoveredHosts
        .filter((host) => showPhones || host.device_type !== 'phone')
        .map((host) => {
            const icon = host.device_type === 'phone' ? '📱' : host.device_type === 'switch' ? '🔀' : '💻';
            const deviceClass = host.device_type === 'phone' ? ' class="phone-device"' : host.device_type === 'switch' ? ' class="switch-device"' : '';
            const currentType = discoveryDeviceTypes[host.target] || 'auto';
            return `<tr${deviceClass}>
                <td><input type="checkbox" value="${host.target}" ${selected.has(host.target) ? 'disabled' : ''}></td>
                <td>${icon} ${escapeHtml(host.name)}</td>
                <td>${host.target}</td>
                <td>
                    <select onchange="setDiscoveryDeviceType('${host.target}', this.value)" ${selected.has(host.target) ? 'disabled' : ''}>
                        <option value="auto" ${currentType === 'auto' ? 'selected' : ''}>🔍 Auto (${host.device_type})</option>
                        <option value="pc" ${currentType === 'pc' ? 'selected' : ''}>💻 PC</option>
                        <option value="phone" ${currentType === 'phone' ? 'selected' : ''}>📱 Phone</option>
                        <option value="switch" ${currentType === 'switch' ? 'selected' : ''}>🔀 Switch</option>
                    </select>
                </td>
            </tr>`;
        })
        .join('') || '<tr><td colspan="4">No responding devices found.</td></tr>';

    tbody.innerHTML = rows;
}

function toggleAutoDiscover(button) {
    autoDiscoverActive = !autoDiscoverActive;
    const subnetInput = document.querySelector('#subnet-input')?.value;

    if (autoDiscoverActive && subnetInput) {
        button.querySelector('span').textContent = 'Auto refresh: on';
        button.classList.add('active');
        discoverHosts(button, true);
        autoDiscoverTimer = setInterval(() => {
            if (autoDiscoverActive && document.querySelector('#subnet-input')?.value === subnetInput) {
                discoverHosts(button, true);
            }
        }, 10000);
    } else {
        stopDiscoveryRefresh(button);
    }
}

function stopDiscoveryRefresh(button) {
    autoDiscoverActive = false;
    if (autoDiscoverTimer) {
        clearInterval(autoDiscoverTimer);
        autoDiscoverTimer = null;
    }
    if (button) {
        const span = button.querySelector('span');
        if (span) span.textContent = 'Auto refresh: off';
        button.classList.remove('active');
    }
}

function setDiscoveryDeviceType(target, type) {
    discoveryDeviceTypes[target] = type;
}

async function addSelectedHosts() {
    const selected = [...document.querySelectorAll('#discovered-rows input:checked')].map((checkbox) => {
        const row = checkbox.closest('tr');
        const target = checkbox.value;
        const host = allDiscoveredHosts.find((h) => h.target === target);
        const userSelectedType = discoveryDeviceTypes[target] || 'auto';
        const finalType = userSelectedType === 'auto' ? host?.device_type : userSelectedType;
        return { target: target, name: row.cells[1].textContent.trim(), device_type: finalType };
    });
    if (!selected.length) {
        setStatus('Select at least one device.');
        return;
    }
    try {
        stopDiscoveryRefresh(document.querySelector('#auto-discover-toggle'));
        await requestJson('/api/devices', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ devices: selected }),
        });
        discoveryDeviceTypes = {};
        setStatus(`${selected.length} device${selected.length === 1 ? '' : 's'} added. Start monitoring when ready.`);
        await refreshStatus();
    } catch (error) {
        setStatus(error.message);
    }
}

async function setMonitoring(id, active) {
    try {
        await requestJson(`/api/devices/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active }),
        });
        await refreshStatus();
    } catch (error) {
        setStatus(error.message);
    }
}

async function setDeviceType(id, device_type) {
    try {
        await requestJson(`/api/devices/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_type }),
        });
        await refreshStatus();
    } catch (error) {
        setStatus(error.message);
    }
}

async function reclassifyAllDevices() {
    try {
        setStatus('Re-detecting device types across network...');
        const res = await requestJson('/api/devices/reclassify', { method: 'POST' });
        const count = res.reclassified ? res.reclassified.length : 0;
        setStatus(`Re-detected types for ${count} device${count === 1 ? '' : 's'}.`);
        await refreshStatus();
    } catch (error) {
        setStatus(error.message);
    }
}

async function setIntervalSeconds(id, input) {
    const interval_seconds = Number(input.value);
    try {
        await requestJson(`/api/devices/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ interval_seconds }),
        });
        input.value = Math.max(5, Math.min(3600, interval_seconds));
    } catch (error) {
        setStatus(error.message);
    }
}

async function removeDevice(id) {
    try {
        await requestJson(`/api/devices/${id}`, { method: 'DELETE' });
        await refreshStatus();
    } catch (error) {
        setStatus(error.message);
    }
}

function getFilteredDevices() {
    const query = monitorSearchQuery.toLowerCase().trim();
    const typeFilter = document.querySelector('#device-type-filter')?.value || '';
    monitorDeviceTypeFilter = typeFilter;

    return window.monitorDevices.filter((device) => {
        if (typeFilter && device.device_type !== typeFilter) return false;
        if (!query) return true;
        return device.name.toLowerCase().includes(query) || device.target.toLowerCase().includes(query);
    });
}

function renderPagination(filteredCount) {
    const totalPages = Math.ceil(filteredCount / itemsPerPage);
    const container = document.querySelector('#pagination-controls');
    if (!container) return;

    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = `<button class="range-button" type="button" onclick="previousPage()" ${monitorCurrentPage === 1 ? 'disabled' : ''}>← Previous</button>`;
    for (let i = 1; i <= totalPages; i++) {
        const isCurrentPage = i === monitorCurrentPage;
        const activeClass = isCurrentPage ? 'active' : '';
        html += `<button class="range-button ${activeClass}" type="button" onclick="goToPage(${i})">${i}</button>`;
    }
    html += `<button class="range-button" type="button" onclick="nextPage()" ${monitorCurrentPage === totalPages ? 'disabled' : ''}>Next →</button>`;
    html += `<span style="margin-left: 16px; color: #666; font-size: 0.9em;">Page ${monitorCurrentPage} of ${totalPages}</span>`;
    container.innerHTML = html;
}

function renderDevices(devices) {
    window.monitorDevices = devices;
    const filteredDevices = getFilteredDevices();
    const totalFiltered = filteredDevices.length;
    const startIndex = (monitorCurrentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const pageDevices = filteredDevices.slice(startIndex, endIndex);

    const tbody = document.querySelector('#monitored-rows');
    if (tbody) {
        tbody.innerHTML = pageDevices.map((device) => {
            const icon = device.device_type === 'phone' ? '📱' : device.device_type === 'switch' ? '🔀' : '💻';
            const deviceClass = device.device_type === 'phone' ? ' class="phone-device"' : device.device_type === 'switch' ? ' class="switch-device"' : '';
            return `<tr${deviceClass}>
                <td>${icon} ${escapeHtml(device.name)}</td>
                <td>${device.target}</td>
                <td>${device.mac_address || '-'}</td>
                <td>
                    <select onchange="setDeviceType(${device.id}, this.value)" style="padding: 4px; min-width: 100px;">
                        <option value="pc" ${device.device_type === 'pc' ? 'selected' : ''}>💻 PC</option>
                        <option value="phone" ${device.device_type === 'phone' ? 'selected' : ''}>📱 Phone</option>
                        <option value="switch" ${device.device_type === 'switch' ? 'selected' : ''}>🔀 Switch</option>
                    </select>
                </td>
                <td>${device.latest?.online ? 'Online' : device.latest ? 'Offline' : 'Not checked'}</td>
                <td>${device.latest?.latency_min_display || '-'}</td>
                <td>${device.latest?.latency_median_display || '-'}</td>
                <td>${device.latest?.latency_max_display || '-'}</td>
                <td>${device.latest ? `${device.latest.packet_loss}%` : '-'}</td>
                <td><input type="number" min="5" max="3600" value="${device.interval_seconds}" aria-label="Ping interval seconds" onchange="setIntervalSeconds(${device.id}, this)"></td>
                <td>
                    <button class="range-button" type="button" onclick="setMonitoring(${device.id}, ${!device.active})">${device.active ? 'Pause' : 'Start'}</button>
                    <button class="range-button" type="button" onclick="removeDevice(${device.id})" aria-label="Remove ${escapeHtml(device.name)}">Remove</button>
                </td>
            </tr>`;
        }).join('') || '<tr><td colspan="11">Discover and add devices to monitor.</td></tr>';
    }

    const savedCount = document.querySelector('#saved-count');
    if (savedCount) savedCount.textContent = devices.length;
    const activeCount = document.querySelector('#active-count');
    if (activeCount) activeCount.textContent = devices.filter((d) => d.active).length;
    const monSummary = document.querySelector('#monitor-summary');
    if (monSummary) monSummary.textContent = `${devices.filter((d) => d.active).length} active (${totalFiltered} shown)`;

    const chartSelect = document.querySelector('#chart-device');
    if (chartSelect) {
        const current = chartSelect.value;
        chartSelect.innerHTML = devices.map((d) => `<option value="${d.target}">${escapeHtml(d.name)}</option>`).join('');
        if (devices.some((d) => d.target === current)) chartSelect.value = current;
    }

    renderPagination(totalFiltered);
}

function applySearchAndPagination() {
    monitorSearchQuery = document.querySelector('#monitor-search')?.value || '';
    monitorCurrentPage = 1;
    renderDevices(window.monitorDevices);
}

function clearMonitorSearch() {
    monitorSearchQuery = '';
    const searchInput = document.querySelector('#monitor-search');
    if (searchInput) searchInput.value = '';
    const typeFilter = document.querySelector('#device-type-filter');
    if (typeFilter) typeFilter.value = '';
    monitorCurrentPage = 1;
    renderDevices(window.monitorDevices);
}

function previousPage() {
    if (monitorCurrentPage > 1) {
        monitorCurrentPage--;
        renderDevices(window.monitorDevices);
    }
}

function nextPage() {
    const filteredDevices = getFilteredDevices();
    const totalPages = Math.ceil(filteredDevices.length / itemsPerPage);
    if (monitorCurrentPage < totalPages) {
        monitorCurrentPage++;
        renderDevices(window.monitorDevices);
    }
}

function goToPage(pageNum) {
    monitorCurrentPage = pageNum;
    renderDevices(window.monitorDevices);
}

async function bulkStartAll() {
    const filteredDevices = getFilteredDevices();
    if (!confirm(`Start monitoring on all ${filteredDevices.length} device${filteredDevices.length === 1 ? '' : 's'}?`)) return;
    try {
        for (const device of filteredDevices) {
            if (!device.active) {
                await requestJson(`/api/devices/${device.id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ active: true }),
                });
            }
        }
        setStatus(`✓ Started monitoring on ${filteredDevices.length} device${filteredDevices.length === 1 ? '' : 's'}`);
        await refreshStatus();
    } catch (error) {
        setStatus(error.message);
    }
}

async function bulkPauseAll() {
    const filteredDevices = getFilteredDevices();
    if (!confirm(`Pause monitoring on all ${filteredDevices.length} device${filteredDevices.length === 1 ? '' : 's'}?`)) return;
    try {
        for (const device of filteredDevices) {
            if (device.active) {
                await requestJson(`/api/devices/${device.id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ active: false }),
                });
            }
        }
        setStatus(`✓ Paused monitoring on ${filteredDevices.length} device${filteredDevices.length === 1 ? '' : 's'}`);
        await refreshStatus();
    } catch (error) {
        setStatus(error.message);
    }
}

async function pollNow(button) {
    button.disabled = true;
    try {
        await requestJson('/api/monitor-now', { method: 'POST' });
        await refreshStatus();
    } catch (error) {
        setStatus(error.message);
    } finally {
        button.disabled = false;
    }
}
