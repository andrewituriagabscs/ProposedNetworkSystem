/**
 * Settings, database switching, building name, and reference configuration.
 */

async function saveBuildingName() {
    const input = document.querySelector('#building-name-input');
    const status = document.querySelector('#reference-setting-status');
    const building_name = input?.value.trim();
    if (!building_name) {
        alert('Please enter a building name');
        return;
    }
    try {
        const result = await requestJson('/api/settings/building-name', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ building_name }),
        });
        if (status) {
            status.textContent = `Building "${result.building_name}" database created and activated! New monitoring records will be stored in this building's database.`;
        }
        if (input) input.value = result.building_name;
        const bldgBadge = document.querySelector('#building-name');
        if (bldgBadge) bldgBadge.textContent = result.building_name;
        await loadDatabaseSelector();
        await refreshStatus();
        setTimeout(() => {
            if (status) status.textContent = '';
        }, 6000);
    } catch (error) {
        if (status) status.textContent = `Error: ${error.message}`;
    }
}

async function loadBuildingName() {
    try {
        const data = await requestJson('/api/settings/building-name');
        const bldgBadge = document.querySelector('#building-name');
        if (bldgBadge) bldgBadge.textContent = data.building_name;
        const input = document.querySelector('#building-name-input');
        if (input) input.value = data.building_name;
    } catch (error) {
        const bldgBadge = document.querySelector('#building-name');
        if (bldgBadge) bldgBadge.textContent = 'Location unavailable';
    }
}

async function loadDatabaseSelector() {
    const selector = document.querySelector('#database-selector');
    const status = document.querySelector('#reference-setting-status');
    if (!selector) return;
    try {
        const data = await requestJson('/api/settings/databases');
        const input = document.querySelector('#building-name-input');
        if (input) input.value = data.current_building || '';
        const bldgBadge = document.querySelector('#building-name');
        if (bldgBadge) bldgBadge.textContent = data.current_building || 'Unknown location';
        selector.innerHTML = data.databases.map((db) => `
            <option value="${escapeAttribute(db.name)}" ${db.name === data.current_building ? 'selected' : ''}>${escapeHtml(db.name)}</option>
        `).join('') || '<option value="">No databases found</option>';
    } catch (error) {
        if (status) status.textContent = error.message;
    }
}

async function switchDatabase() {
    const selector = document.querySelector('#database-selector');
    const status = document.querySelector('#reference-setting-status');
    const building_name = selector?.value;
    if (!building_name) {
        if (status) status.textContent = 'Select a database first.';
        return;
    }
    try {
        const result = await requestJson('/api/settings/databases/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ building_name }),
        });
        if (status) status.textContent = result.message || 'Database switched successfully!';
        const input = document.querySelector('#building-name-input');
        if (input) input.value = result.building_name;
        const bldgBadge = document.querySelector('#building-name');
        if (bldgBadge) bldgBadge.textContent = result.building_name;
        await loadDatabaseSelector();
        await refreshStatus();
        setTimeout(() => {
            if (status) status.textContent = '';
        }, 5000);
    } catch (error) {
        if (status) status.textContent = error.message;
    }
}

async function restartMonitoring() {
    const status = document.querySelector('#reference-setting-status');
    try {
        const result = await requestJson('/api/control/restart-monitoring', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        if (status) status.textContent = result.message || 'Monitoring service restarted successfully!';
    } catch (error) {
        if (status) status.textContent = error.message;
    }
}

async function saveExternalReference() {
    const input = document.querySelector('#external-reference-ip');
    const status = document.querySelector('#reference-setting-status');
    if (!input) return;
    try {
        const result = await requestJson('/api/settings/external-reference', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target: input.value }),
        });
        input.value = result.target;
        if (status) status.textContent = 'External reference saved.';
        await refreshMlPanel();
    } catch (error) {
        if (status) status.textContent = error.message;
    }
}

async function loadExternalReferenceSetting() {
    try {
        const data = await requestJson('/api/network-references');
        renderNetworkReferences(data);
    } catch (error) {
        const status = document.querySelector('#reference-setting-status');
        if (status) status.textContent = error.message;
    }
}
