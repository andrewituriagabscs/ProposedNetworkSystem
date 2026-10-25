<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ping Monitoring System</title>
    <link rel="stylesheet" href="/style.css">
</head>
<body>
    <div class="app-shell">
        <aside class="sidebar" aria-label="Main navigation">
            <div class="brand"><span class="brand-mark" aria-hidden="true">P</span><span>PingWatch</span></div>
@php
    $currentView = $activeView ?? 'dashboard';
@endphp
            <nav class="nav-list">
                <a href="/dashboard" class="nav-item {{ $currentView === 'dashboard' ? 'active' : '' }}" data-view="dashboard" {{ $currentView === 'dashboard' ? 'aria-current="page"' : '' }}><span class="nav-icon" aria-hidden="true">⌂</span><span>Dashboard</span></a>
                <a href="/ping" class="nav-item {{ $currentView === 'monitor' ? 'active' : '' }}" data-view="monitor" {{ $currentView === 'monitor' ? 'aria-current="page"' : '' }}><span class="nav-icon" aria-hidden="true">◉</span><span>Ping</span></a>
                <a href="/alerts" class="nav-item {{ $currentView === 'alerts' ? 'active' : '' }}" data-view="alerts" {{ $currentView === 'alerts' ? 'aria-current="page"' : '' }}><span class="nav-icon" aria-hidden="true">!</span><span>Alerts</span></a>
                <a href="/records" class="nav-item {{ $currentView === 'reports' ? 'active' : '' }}" data-view="reports" {{ $currentView === 'reports' ? 'aria-current="page"' : '' }}><span class="nav-icon" aria-hidden="true">▤</span><span>Ping Records</span></a>
                <a href="/ml-insights" class="nav-item {{ $currentView === 'ml-insights' ? 'active' : '' }}" data-view="ml-insights" {{ $currentView === 'ml-insights' ? 'aria-current="page"' : '' }}><span class="nav-icon" aria-hidden="true">⌁</span><span>ML Insights</span></a>
            </nav>
            <nav class="nav-list nav-list-bottom" aria-label="Preferences">
                <a href="/settings" class="nav-item {{ $currentView === 'settings' ? 'active' : '' }}" data-view="settings" {{ $currentView === 'settings' ? 'aria-current="page"' : '' }}><span class="nav-icon" aria-hidden="true">⚙</span><span>Settings</span></a>
                <a href="/about" class="nav-item {{ $currentView === 'about' ? 'active' : '' }}" data-view="about" {{ $currentView === 'about' ? 'aria-current="page"' : '' }}><span class="nav-icon" aria-hidden="true">?</span><span>About</span></a>
            </nav>
        </aside>

        <main class="page">
            <section class="view-panel {{ $currentView === 'dashboard' ? 'active' : '' }}" data-panel="dashboard" {{ $currentView === 'dashboard' ? '' : 'hidden' }}>
                <header><div><p class="eyebrow">ICMP network status</p><h1>Ping Monitoring System<small id="building-name" style="font-size: 0.6em; color: #666; display: block; margin-top: 0.25em;">Loading location...</small></h1><p>Updated <span id="dashboard-updated">Waiting for live samples</span></p></div><button class="refresh-button" type="button" onclick="refreshStatus()">↻ <span>Refresh</span></button></header>
                <section class="summary-cards">
                    <div class="card"><h2>Saved PCs</h2><p id="saved-count">0</p></div>
                    <div class="card"><h2>Monitoring</h2><p id="active-count">0</p></div>
                    <div class="card"><h2>Network status</h2><p id="network-health">Waiting</p></div>
                    <div class="card"><h2>Open alerts</h2><p id="open-alerts">0</p></div>
                </section>
                <section class="metrics"><h2>Ping metrics</h2><div class="metric-grid">
                    <div class="metric-card"><strong>Average Latency</strong><span id="metric-average-latency">Loading</span><small>Live ping</small></div><div class="metric-card"><strong>Reachable</strong><span id="metric-reachable">0</span><small>Latest ping per PC</small></div><div class="metric-card"><strong>Monitoring</strong><span id="metric-monitoring">0</span><small>Selected PCs</small></div><div class="metric-card"><strong>Ping Samples</strong><span id="metric-samples">0</span><small>Recent records</small></div>
                </div></section>
                <section class="ml-overview"><div class="section-heading"><div><p class="eyebrow">SYSTEM 2: Proposed / Enhanced Approach</p><h2>Machine learning pipeline</h2></div><span class="status-pill status-normal">5-Probe Burst &bull; 12 Temporal Features &bull; Admin-Reviewed Labels</span></div>
                    <div class="summary-cards ml-cards">
                        <div class="card"><h2>1. Basic Ping Collection</h2><p class="small-value">Min/Median/Max RTT + Dual Ref</p><small>Gateway &amp; 1.1.1.1 + Switch OUI/Ports</small></div>
                        <div class="card"><h2>2. Static Feature Extraction</h2><p class="small-value">12 Temporal Features</p><small>Jitter, &Delta;Latency, &Delta;Loss, 5-Sample Trend, Streak, &Delta;Time</small></div>
                        <div class="card"><h2>3. Human-in-the-Loop Labeling</h2><p id="dashboard-labeled-samples">0</p><small>Admin-Reviewed Condition Labels (<span id="dashboard-valid-samples">0</span> samples)</small></div>
                        <div class="card"><h2>4. Train &amp; Run 3 Models</h2><p id="dashboard-ml-model" class="small-value">Isolation Forest, GRU, XGBoost</p><small id="dashboard-ml-version">Loading readiness</small></div>
                    </div>
                </section>
                <section class="alerts"><h2>Recent alerts</h2><table><thead><tr><th>Time</th><th>PC</th><th>Ping event</th></tr></thead><tbody id="alert-rows"><tr><td colspan="3">Waiting for live status...</td></tr></tbody></table><div id="alerts-pagination" style="display: flex; gap: 8px; justify-content: center; align-items: center; margin-top: 16px;"></div></section>
            </section>

            <section class="view-panel data-panel {{ $currentView === 'monitor' ? 'active' : '' }}" data-panel="monitor" {{ $currentView === 'monitor' ? '' : 'hidden' }}>
                <div class="monitor-heading"><div><p class="eyebrow">Local network</p><h1>Monitor Devices</h1><p class="panel-intro">Discover responding devices (PCs and phones), select the ones to monitor, and start ping checks.</p></div><button class="refresh-button" type="button" onclick="pollNow(this)">↻ <span>Ping now</span></button></div>
                <section class="discovery-controls">
                    <label for="subnet-input">Subnet to discover</label>
                    <div class="discovery-row"><input id="subnet-input" type="text" inputmode="decimal" aria-label="Local IPv4 subnet in CIDR notation"><button class="refresh-button" id="discover-button" type="button" onclick="discoverHosts(this)">⌕ <span>Discover PCs</span></button><button class="refresh-button" id="auto-discover-toggle" type="button" onclick="toggleAutoDiscover(this)" style="display: none;">⟳ <span>Auto refresh: off</span></button></div>
                    <div class="discovery-options">
                        <div><label for="discovery-limit">Discover up to:</label><input id="discovery-limit" type="number" value="20" min="1" max="999" style="width: 60px; padding: 6px;"><select id="limit-presets" onchange="document.querySelector('#discovery-limit').value = this.value;" style="padding: 6px; margin-left: 8px;"><option value="">Presets:</option><option value="10">10</option><option value="20">20</option><option value="50">50</option><option value="100">100</option><option value="256">All</option></select></div>
                        <div style="margin-top: 8px;"><label><input type="checkbox" id="show-phones-toggle" checked onchange="filterDiscoveryRows()"> Show phones (📱)</label></div>
                    </div>
                    <p id="discovery-status" role="status"></p>
                </section>
                <section id="discovery-section" hidden><div class="section-heading"><h2>Available Devices</h2><button class="refresh-button" type="button" onclick="addSelectedHosts()">＋ <span>Add selected</span></button></div><div class="table-wrap"><table><thead><tr><th>Select</th><th>Device / hostname</th><th>IPv4 address</th><th>Device Type</th></tr></thead><tbody id="discovered-rows"></tbody></table></div></section>
                <section><div class="section-heading"><h2>Selected Devices</h2><span id="monitor-summary"></span></div>
                    <div style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; align-items: center;">
                        <input id="monitor-search" type="text" placeholder="Search by IP or hostname..." style="flex: 1; min-width: 200px; padding: 8px; border: 1px solid #ccc; border-radius: 4px;" onkeyup="applySearchAndPagination()">
                        <select id="device-type-filter" style="padding: 8px; border: 1px solid #ccc; border-radius: 4px;" onchange="applySearchAndPagination()">
                            <option value="">All devices</option>
                            <option value="pc">💻 PCs only</option>
                            <option value="phone">📱 Phones only</option>
                            <option value="switch">🔀 Switches only</option>
                        </select>
                        <button class="refresh-button" type="button" onclick="clearMonitorSearch()" style="padding: 6px 12px;">✕ <span>Clear</span></button>
                        <button class="refresh-button" type="button" onclick="reclassifyAllDevices()" style="padding: 6px 12px; background: #2196F3;" title="Re-detect PC / Phone / Switch for all monitored devices">🔀 <span>Re-detect types</span></button>
                        <button class="refresh-button" type="button" onclick="bulkStartAll()" style="padding: 6px 12px; background: #4CAF50;">▶ <span>Start All</span></button>
                        <button class="refresh-button" type="button" onclick="bulkPauseAll()" style="padding: 6px 12px; background: #FF9800;">⏸ <span>Pause All</span></button>
                    </div>
                    <div class="chart-card"><div class="chart-heading"><div><h2>Ping latency</h2><small>Median of 5-probe ICMP burst per check (System 2 Proposed); Windows may report values as &lt;1 ms.</small></div><label for="chart-device">Device</label><select id="chart-device" aria-label="Select device for latency chart" onchange="drawPingChart()"></select></div><canvas id="ping-chart" height="220"></canvas></div>
                    <div class="table-wrap"><table><thead><tr><th>Device</th><th>IPv4 address</th><th>Mac Address</th><th>Type</th><th>Latest ping</th><th>Min</th><th>Median</th><th>Max</th><th>Loss</th><th>Interval (sec)</th><th>Control</th></tr></thead><tbody id="monitored-rows"></tbody></table></div>
                    <div id="pagination-controls" style="display: flex; gap: 8px; justify-content: center; align-items: center; margin-top: 16px;"></div>
                </section>
            </section>

            <section class="view-panel data-panel {{ $currentView === 'alerts' ? 'active' : '' }}" data-panel="alerts" {{ $currentView === 'alerts' ? '' : 'hidden' }}><p class="eyebrow">Ping events</p><h1>Alerts</h1><p class="panel-intro">Unreachable PCs and high-latency ping results.</p><div class="table-wrap"><table><thead><tr><th>Time</th><th>PC</th><th>Event</th><th>Status</th></tr></thead><tbody id="all-alerts-rows"><tr><td colspan="4">Waiting for live status...</td></tr></tbody></table></div><div id="all-alerts-pagination" style="display:flex;gap:8px;justify-content:center;align-items:center;margin-top:16px"></div></section>

            <section class="view-panel data-panel {{ $currentView === 'reports' ? 'active' : '' }}" data-panel="reports" {{ $currentView === 'reports' ? '' : 'hidden' }}><p class="eyebrow">ICMP history</p><h1>Ping Records</h1><p class="panel-intro">Saved ping replies, packet loss, and latency statistics.</p><p><a class="refresh-button" href="/api/dataset.csv">Download ping dataset</a> <a class="refresh-button" href="/api/model-records.csv">Download ping records</a></p><div class="history-toolbar"><strong>History range</strong><div class="range-buttons"><button type="button" class="range-button active" data-hours="1">1 hour</button><button type="button" class="range-button" data-hours="24">24 hours</button><button type="button" class="range-button" data-hours="168">7 days</button></div></div><div class="table-wrap"><table id="reports-table"><thead><tr><th>Time</th><th>PC</th><th>IP</th><th>Replies</th><th>Loss</th><th>Min</th><th>Median</th><th>Max</th></tr></thead><tbody><tr><td colspan="8">Waiting for live ping records...</td></tr></tbody></table></div><div id="ping-records-pagination" style="display: flex; gap: 8px; justify-content: center; align-items: center; margin-top: 16px;"></div></section>

            <section class="view-panel data-panel {{ $currentView === 'ml-insights' ? 'active' : '' }}" data-panel="ml-insights" {{ $currentView === 'ml-insights' ? '' : 'hidden' }}>
                <header class="ml-heading">
                    <div>
                        <p class="eyebrow">SYSTEM 1: Existing / Baseline Approach</p>
                        <h1>ML Insights</h1>
                        <p class="panel-intro">1. Basic Ping Collection (Min/Median/Max RTT + Dual Ref) &rarr; 2. Static Feature Extraction (12 Temporal Features: Jitter, &Delta;Latency, &Delta;Loss, 5-Sample Trend, Streak, &Delta;Time) &rarr; 3. Human-in-the-Loop Labeling (Rigid &gt;150ms Threshold) &rarr; 4. Train &amp; Run the 3 Models (Isolation Forest, GRU, XGBoost).</p>
                    </div>
                    <span class="status-pill status-normal">CLI-Trained Models</span>
                </header>
                <p id="ml-status-line" class="ml-status-line" role="status">Loading model readiness...</p>
                <div id="ml-condition-readiness-badges" style="display:flex;gap:10px;flex-wrap:wrap;margin:8px 0 14px 0;"></div>
                <p id="ml-action-status" role="status"></p>
                <section class="summary-cards ml-cards">
                    <div class="card">
                        <h2>Isolation Forest</h2>
                        <p id="if-model-state">Checking</p>
                        <small id="if-model-detail">Unsupervised anomaly detection</small>
                    </div>
                    <div class="card">
                        <h2>GRU (Seq2Seq Attention Autoencoder)</h2>
                        <p id="gru-model-state">Checking</p>
                        <small id="gru-model-detail">Unsupervised sequence reconstruction &amp; forecast (13.1ms edge inference)</small>
                    </div>
                    <div class="card">
                        <h2>XGBoost (Active Recommender)</h2>
                        <p id="xgb-model-state">Checking</p>
                        <small id="xgb-model-detail">Supervised condition classification &amp; recommendations</small>
                    </div>
                </section>
                <!-- SPOT 1: CRITICAL OUTAGES (UNREACHABLE DEVICES) -->
                <section class="ml-results-section" style="border-left: 4px solid #c62828; margin-bottom: 24px; padding-left: 16px;">
                    <div class="section-heading" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                        <div>
                            <div style="display:flex;align-items:center;gap:10px;">
                                <h2 style="margin:0;">🚨 Spot 1: Critical Outages (Unreachable Devices)</h2>
                                <span class="status-pill status-down" id="ml-unreachable-count-pill">0 Unreachable</span>
                            </div>
                            <p class="panel-intro" style="margin-bottom:0;">Immediate intervention required. Monitored endpoints failing ICMP ping responses (100% loss / host down).</p>
                        </div>
                        <div style="display:flex;gap:14px;align-items:center;">
                            <button class="range-button" type="button" onclick="refreshMlPanel()">↻ Refresh</button>
                        </div>
                    </div>
                    <div class="table-wrap" style="margin-top:12px;">
                        <table>
                            <thead>
                                <tr>
                                    <th style="min-width:160px;">PC / Device</th>
                                    <th style="min-width:120px;">Latest Ping</th>
                                    <th style="min-width:160px;">Supervised Diagnosis</th>
                                    <th style="min-width:240px;">Possible Cause / Threat</th>
                                </tr>
                            </thead>
                            <tbody id="ml-unreachable-rows">
                                <tr><td colspan="4">Loading unreachable devices...</td></tr>
                            </tbody>
                        </table>
                    </div>
                    <div id="ml-unreachable-pagination" style="display: flex; gap: 8px; justify-content: center; align-items: center; margin-top: 16px;"></div>
                </section>

                <!-- SPOT 2: PERFORMANCE ANOMALIES (HIGH LATENCY & PACKET LOSS) -->
                <section class="ml-results-section" style="border-left: 4px solid #ef6c00; padding-left: 16px;">
                    <div class="section-heading" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                        <div>
                            <div style="display:flex;align-items:center;gap:10px;">
                                <h2 style="margin:0;">⚠️ Spot 2: Performance Anomalies (High Latency &amp; Packet Loss)</h2>
                                <span class="status-pill status-warning" id="ml-performance-count-pill">0 Anomalies</span>
                            </div>
                            <p class="panel-intro" style="margin-bottom:0;">Network degradation and congestion detected. Requires bandwidth inspection, port error checks, or QoS tuning.</p>
                        </div>
                        <div style="display:flex;gap:14px;align-items:center;">
                            <label style="font-size:0.9rem;cursor:pointer;display:flex;align-items:center;gap:6px;">
                                <input type="checkbox" id="show-normal-recommendations" onchange="renderMlRecommendationsPage()">
                                Show healthy (Normal) devices
                            </label>
                            <button class="range-button" type="button" onclick="refreshMlPanel()">↻ Refresh</button>
                        </div>
                    </div>
                    <div class="table-wrap" style="margin-top:12px;">
                        <table>
                            <thead>
                                <tr>
                                    <th style="min-width:140px;">PC / Device</th>
                                    <th style="min-width:110px;">Latest Ping</th>
                                    <th style="min-width:140px;">Supervised Diagnosis</th>
                                    <th style="min-width:180px;">Possible Cause / Threat</th>
                                    <th style="min-width:320px;">Prioritized Remediation &amp; Action Steps</th>
                                </tr>
                            </thead>
                            <tbody id="ml-performance-rows">
                                <tr><td colspan="5">Loading performance anomalies...</td></tr>
                            </tbody>
                        </table>
                    </div>
                    <div id="ml-performance-pagination" style="display: flex; gap: 8px; justify-content: center; align-items: center; margin-top: 16px;"></div>
                    <details style="margin-top:18px;border:1px solid rgba(128,128,128,0.25);border-radius:10px;padding:12px 16px;">
                        <summary style="cursor:pointer;font-weight:600;">1. 5-Probe ICMP Burst + Dual Reference Status (Local Gateway &amp; 1.1.1.1)</summary>
                        <div style="margin-top:12px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                                <small>Compares 5-probe burst latency &amp; jitter against the Local Gateway and External Reference (1.1.1.1).</small>
                                <button class="range-button" type="button" onclick="pollNetworkReferences(this)">↻ Ping Dual Reference</button>
                            </div>
                            <div class="table-wrap">
                                <table>
                                    <thead>
                                        <tr><th>Reference</th><th>Target</th><th>Status</th><th>Packet Loss</th><th>Median RTT</th><th>Burst Jitter</th></tr>
                                    </thead>
                                    <tbody id="reference-rows"><tr><td colspan="6">Loading Dual Reference status...</td></tr></tbody>
                                </table>
                            </div>
                            <div class="table-wrap" style="margin-top:10px;">
                                <table>
                                    <thead>
                                        <tr><th>Monitored Device</th><th>Packet Loss</th><th>Median RTT</th><th>Burst Jitter</th><th>Dual Reference Comparison</th></tr>
                                    </thead>
                                    <tbody id="reference-device-rows"><tr><td colspan="5">Loading device comparisons...</td></tr></tbody>
                                </table>
                            </div>
                        </div>
                    </details>
                    <details style="margin-top:12px;border:1px solid rgba(128,128,128,0.25);border-radius:10px;padding:12px 16px;">
                        <summary style="cursor:pointer;font-weight:600;">3. Human-in-the-Loop Labeling (Admin-Reviewed Condition Labels)</summary>
                        <div style="margin-top:12px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                                <small>Review and save condition labels (Normal, High Latency, Packet Loss, Unreachable) for 5-probe burst samples.</small>
                                <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
                                    <label style="font-size:0.85rem;cursor:pointer;display:inline-flex;align-items:center;gap:6px;font-weight:600;">
                                        <input type="checkbox" id="toggle-uncertain-labels" onchange="toggleUncertainLabelsFilter(this)">
                                        ⚡ Active Learning (Uncertain Samples)
                                    </label>
                                    <button class="range-button" type="button" onclick="applyAutoRuleLabels(this)">✓ Confirm Suggested Labels</button>
                                </div>
                            </div>
                            <div class="table-wrap">
                                <table>
                                    <thead>
                                        <tr><th>Recorded At</th><th>Device</th><th>5-Probe Median RTT</th><th>Packet Loss</th><th>Admin-Reviewed Condition Label</th><th>Action</th></tr>
                                    </thead>
                                    <tbody id="ml-label-rows"><tr><td colspan="6">Loading samples for Human-in-the-Loop review...</td></tr></tbody>
                                </table>
                            </div>
                            <div id="ml-labels-pagination" style="display:flex;gap:8px;justify-content:center;align-items:center;margin-top:12px;"></div>
                        </div>
                    </details>
                </section>
            </section>

            <section class="view-panel data-panel {{ $currentView === 'settings' ? 'active' : '' }}" data-panel="settings" {{ $currentView === 'settings' ? '' : 'hidden' }}><p class="eyebrow">Display and monitoring</p><h1>Settings</h1><div class="settings-list"><div class="appearance-setting"><div class="theme-logo" aria-hidden="true"><span class="theme-sun">☀</span><span class="theme-moon">☾</span></div><div><strong>Appearance</strong><small id="theme-label">Light mode</small></div><label class="switch-control" for="theme-toggle"><span class="sr-only">Turn dark mode on or off</span><input id="theme-toggle" type="checkbox"><span class="switch-slider"></span></label></div><div class="building-setting"><div><strong>Building/Location name</strong><small>Identifies this monitoring instance.</small></div><div class="building-controls"><input id="building-name-input" type="text" placeholder="Building 1" value="Loading location..." aria-label="Building name"><button class="range-button" type="button" onclick="saveBuildingName()">Save</button></div></div><div class="building-setting"><div><strong>Saved databases</strong><small>Switch to a different building's database.</small></div><div class="building-controls"><select id="database-selector" aria-label="Select database"><option value="">Loading...</option></select><button class="range-button" type="button" onclick="switchDatabase()">Switch</button></div></div><div class="building-setting"><div><strong>Restart monitoring</strong><small>Restart the polling and recording service.</small></div><div class="building-controls"><button class="range-button" type="button" onclick="restartMonitoring()">Restart</button></div></div><div class="reference-setting"><div><strong>External ping reference</strong><small>IPv4 address; some hosts may block ICMP.</small></div><div class="reference-controls"><input id="external-reference-ip" type="text" inputmode="decimal" placeholder="1.1.1.1" aria-label="External reference IPv4 address"><button class="range-button" type="button" onclick="saveExternalReference()">Save</button></div></div></div><p id="reference-setting-status" role="status"></p></section>

            <section class="view-panel data-panel {{ $currentView === 'about' ? 'active' : '' }}" data-panel="about" {{ $currentView === 'about' ? '' : 'hidden' }}><p class="eyebrow">ICMP monitoring</p><h1>About</h1><p class="panel-intro">This system checks PC reachability, packet loss, and round-trip latency using ping.</p></section>
        </main>
    </div>
    <script>
        let monitorDevices = [];
        let monitorHistory = [];
        let latestSampleId = null;
        let autoDiscoverTimer = null;
        let autoDiscoverActive = false;
        let allDiscoveredHosts = [];
        let discoveryDeviceTypes = {};  // Track device type overrides: {target: 'pc'|'phone'|'auto'}
        let monitorCurrentPage = 1;
        let monitorSearchQuery = '';
        let monitorDeviceTypeFilter = '';
        let allTelemetry = [];
        let allMlRecords = [];
        let allAlerts = [];
        let pingRecordsCurrentPage = 1;
        let mlInsightsCurrentPage = 1;
        let alertsCurrentPage = 1;
        let mlLabelsCurrentPage = 1;
        let mlRecommendationsCurrentPage = 1;
        let mlUnreachableCurrentPage = 1;
        let mlPerformanceCurrentPage = 1;
        let allMlLabels = [];
        let allMlRecommendations = [];
        const itemsPerPage = 10;

        async function requestJson(url, options = {}) {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
            const headers = {...(options.headers || {})};
            if (csrfToken && !headers['X-CSRF-TOKEN']) {
                headers['X-CSRF-TOKEN'] = csrfToken;
            }
            const response = await fetch(url, {...options, headers});
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error || payload.message || `Request failed (${response.status})`);
            return payload;
        }

        function setStatus(message) {
            document.querySelector('#discovery-status').textContent = message;
        }

        async function saveBuildingName() {
            const input = document.querySelector('#building-name-input');
            const building_name = input.value.trim();
            if (!building_name) {
                alert('Please enter a building name');
                return;
            }
            try {
                const result = await requestJson('/api/settings/building-name', {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ building_name })
                });
                document.querySelector('#reference-setting-status').textContent = `Building "${result.building_name}" database created and activated! New monitoring records will be stored in this building's database.`;
                input.value = result.building_name;
                const bldgBadge = document.querySelector('#building-name');
                if (bldgBadge) bldgBadge.textContent = result.building_name;
                await loadDatabaseSelector();
                await refreshStatus();
                setTimeout(() => { document.querySelector('#reference-setting-status').textContent = ''; }, 6000);
            } catch (error) {
                document.querySelector('#reference-setting-status').textContent = `Error: ${error.message}`;
            }
        }

        async function discoverHosts(button, silent = false) {
            if (!silent) {
                button.disabled = true;
                setStatus('Discovering responding addresses...');
            }
            try {
                const limit = parseInt(document.querySelector('#discovery-limit').value) || 20;
                const {hosts} = await requestJson('/api/discover', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({subnet: document.querySelector('#subnet-input').value, limit: limit})});
                allDiscoveredHosts = hosts;
                const selected = new Set(monitorDevices.map((device) => device.target));
                filterDiscoveryRows();
                document.querySelector('#discovery-section').hidden = false;
                document.querySelector('#auto-discover-toggle').style.display = 'inline-block';
                if (!silent) {
                    setStatus(`${hosts.length} responding address${hosts.length === 1 ? '' : 'es'} found.`);
                }
            } catch (error) { if (!silent) { setStatus(error.message); } }
            finally { if (!silent) { button.disabled = false; } }
        }

        function filterDiscoveryRows() {
            const showPhones = document.querySelector('#show-phones-toggle').checked;
            const selected = new Set(monitorDevices.map((device) => device.target));
            const rows = allDiscoveredHosts
                .filter(host => showPhones || host.device_type !== 'phone')
                .map((host) => {
                    const icon = host.device_type === 'phone' ? '📱' : host.device_type === 'switch' ? '🔀' : '💻';
                    const deviceClass = host.device_type === 'phone' ? ' class="phone-device"' : host.device_type === 'switch' ? ' class="switch-device"' : '';
                    const currentType = discoveryDeviceTypes[host.target] || 'auto';
                    return `<tr${deviceClass}><td><input type="checkbox" value="${host.target}" ${selected.has(host.target) ? 'disabled' : ''}></td><td>${icon} ${escapeHtml(host.name)}</td><td>${host.target}</td><td><select onchange="setDiscoveryDeviceType('${host.target}', this.value)" ${selected.has(host.target) ? 'disabled' : ''}><option value="auto" ${currentType === 'auto' ? 'selected' : ''}>🔍 Auto (${host.device_type})</option><option value="pc" ${currentType === 'pc' ? 'selected' : ''}>💻 PC</option><option value="phone" ${currentType === 'phone' ? 'selected' : ''}>📱 Phone</option><option value="switch" ${currentType === 'switch' ? 'selected' : ''}>🔀 Switch</option></select></td></tr>`;
                })
                .join('') || '<tr><td colspan="4">No responding devices found.</td></tr>';
            document.querySelector('#discovered-rows').innerHTML = rows;
        }

        function toggleAutoDiscover(button) {
            autoDiscoverActive = !autoDiscoverActive;
            const subnetInput = document.querySelector('#subnet-input').value;
            
            if (autoDiscoverActive && subnetInput) {
                button.querySelector('span').textContent = 'Auto refresh: on';
                button.classList.add('active');
                discoverHosts(button, true);
                autoDiscoverTimer = setInterval(() => {
                    if (autoDiscoverActive && document.querySelector('#subnet-input').value === subnetInput) {
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
            button.querySelector('span').textContent = 'Auto refresh: off';
            button.classList.remove('active');
        }

        function setDiscoveryDeviceType(target, type) {
            discoveryDeviceTypes[target] = type;
        }

        async function addSelectedHosts() {
            const selected = [...document.querySelectorAll('#discovered-rows input:checked')].map((checkbox) => {
                const row = checkbox.closest('tr');
                const target = checkbox.value;
                // Find the host data from allDiscoveredHosts to get device_type
                const host = allDiscoveredHosts.find(h => h.target === target);
                const userSelectedType = discoveryDeviceTypes[target] || 'auto';
                const finalType = userSelectedType === 'auto' ? host?.device_type : userSelectedType;
                return {target: target, name: row.cells[1].textContent, device_type: finalType};
            });
            if (!selected.length) { setStatus('Select at least one device.'); return; }
            try {
                stopDiscoveryRefresh(document.querySelector('#auto-discover-toggle'));
                await requestJson('/api/devices', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({devices: selected})});
                discoveryDeviceTypes = {};  // Reset device type selections after adding
                setStatus(`${selected.length} device${selected.length === 1 ? '' : 's'} added. Start monitoring when ready.`);
                await refreshStatus();
            } catch (error) { setStatus(error.message); }
        }

        function escapeHtml(value) {
            const element = document.createElement('span');
            element.textContent = value;
            return element.innerHTML;
        }

        function escapeAttribute(value) {
            return escapeHtml(value).replaceAll('"', '&quot;').replaceAll("'", '&#39;');
        }

        async function setMonitoring(id, active) {
            try {
                await requestJson(`/api/devices/${id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({active})});
                await refreshStatus();
            } catch (error) { setStatus(error.message); }
        }

        async function setDeviceType(id, device_type) {
            try {
                await requestJson(`/api/devices/${id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({device_type})});
                await refreshStatus();
            } catch (error) { setStatus(error.message); }
        }

        async function reclassifyAllDevices() {
            try {
                setStatus('Re-detecting device types across network...');
                const res = await requestJson('/api/devices/reclassify', {method: 'POST'});
                const count = res.reclassified ? res.reclassified.length : 0;
                setStatus(`Re-detected types for ${count} device${count === 1 ? '' : 's'}.`);
                await refreshStatus();
            } catch (error) { setStatus(error.message); }
        }

        async function setIntervalSeconds(id, input) {
            const interval_seconds = Number(input.value);
            try {
                await requestJson(`/api/devices/${id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({interval_seconds})});
                input.value = Math.max(5, Math.min(3600, interval_seconds));
            } catch (error) { setStatus(error.message); }
        }

        async function removeDevice(id) {
            try { await requestJson(`/api/devices/${id}`, {method: 'DELETE'}); await refreshStatus(); }
            catch (error) { setStatus(error.message); }
        }

        function getFilteredDevices() {
            const query = monitorSearchQuery.toLowerCase().trim();
            const deviceTypeFilter = document.querySelector('#device-type-filter')?.value || '';
            monitorDeviceTypeFilter = deviceTypeFilter;
            
            return monitorDevices.filter(device => {
                // Filter by device type
                if (deviceTypeFilter && device.device_type !== deviceTypeFilter) {
                    return false;
                }
                // Filter by search query
                if (!query) return true;
                return device.name.toLowerCase().includes(query) || 
                       device.target.toLowerCase().includes(query);
            });
        }

        function renderPagination(filteredCount) {
            const totalPages = Math.ceil(filteredCount / itemsPerPage);
            const container = document.querySelector('#pagination-controls');
            
            if (totalPages <= 1) {
                container.innerHTML = '';
                return;
            }

            let html = '<button class="range-button" type="button" onclick="previousPage()" ' + (monitorCurrentPage === 1 ? 'disabled' : '') + '>← Previous</button>';
            
            for (let i = 1; i <= totalPages; i++) {
                const isCurrentPage = i === monitorCurrentPage;
                const activeClass = isCurrentPage ? 'active' : '';
                html += `<button class="range-button ${activeClass}" type="button" onclick="goToPage(${i})">${i}</button>`;
            }
            
            html += '<button class="range-button" type="button" onclick="nextPage()" ' + (monitorCurrentPage === totalPages ? 'disabled' : '') + '>Next →</button>';
            html += `<span style="margin-left: 16px; color: #666; font-size: 0.9em;">Page ${monitorCurrentPage} of ${totalPages}</span>`;
            
            container.innerHTML = html;
        }

        function renderDevices(devices) {
            monitorDevices = devices;
            const filteredDevices = getFilteredDevices();
            const totalFiltered = filteredDevices.length;
            const startIndex = (monitorCurrentPage - 1) * itemsPerPage;
            const endIndex = startIndex + itemsPerPage;
            const pageDevices = filteredDevices.slice(startIndex, endIndex);
            
            const tbody = document.querySelector('#monitored-rows');
            tbody.innerHTML = pageDevices.map((device) => {
                const icon = device.device_type === 'phone' ? '📱' : device.device_type === 'switch' ? '🔀' : '💻';
                const typeLabel = device.device_type === 'phone' ? 'Phone' : device.device_type === 'switch' ? 'Switch' : 'PC';
                const deviceClass = device.device_type === 'phone' ? ' class="phone-device"' : device.device_type === 'switch' ? ' class="switch-device"' : '';
                return `<tr${deviceClass}><td>${escapeHtml(device.name)}</td><td>${device.target}</td><td>${device.mac_address || '-'}</td><td><select onchange="setDeviceType(${device.id}, this.value)" style="padding: 4px; min-width: 100px;"><option value="pc" ${device.device_type === 'pc' ? 'selected' : ''}>💻 PC</option><option value="phone" ${device.device_type === 'phone' ? 'selected' : ''}>📱 Phone</option><option value="switch" ${device.device_type === 'switch' ? 'selected' : ''}>🔀 Switch</option></select></td><td>${device.latest?.online ? 'Online' : device.latest ? 'Offline' : 'Not checked'}</td><td>${device.latest?.latency_min_display || '-'}</td><td>${device.latest?.latency_median_display || '-'}</td><td>${device.latest?.latency_max_display || '-'}</td><td>${device.latest ? `${device.latest.packet_loss}%` : '-'}</td><td><input type="number" min="5" max="3600" value="${device.interval_seconds}" aria-label="Ping interval seconds" onchange="setIntervalSeconds(${device.id}, this)"></td><td><button class="range-button" type="button" onclick="setMonitoring(${device.id}, ${!device.active})">${device.active ? 'Pause' : 'Start'}</button> <button class="range-button" type="button" onclick="removeDevice(${device.id})" aria-label="Remove ${escapeHtml(device.name)}">Remove</button></td></tr>`;
            }).join('') || '<tr><td colspan="11">Discover and add devices to monitor.</td></tr>';
            
            document.querySelector('#saved-count').textContent = devices.length;
            document.querySelector('#active-count').textContent = devices.filter((device) => device.active).length;
            document.querySelector('#monitor-summary').textContent = `${devices.filter((device) => device.active).length} active (${totalFiltered} shown)`;
            
            const chartSelect = document.querySelector('#chart-device');
            const current = chartSelect.value;
            chartSelect.innerHTML = devices.map((device) => `<option value="${device.target}">${escapeHtml(device.name)}</option>`).join('');
            if (devices.some((device) => device.target === current)) chartSelect.value = current;
            
            renderPagination(totalFiltered);
        }

        function applySearchAndPagination() {
            monitorSearchQuery = document.querySelector('#monitor-search').value;
            monitorCurrentPage = 1;
            renderDevices(monitorDevices);
        }

        function clearMonitorSearch() {
            monitorSearchQuery = '';
            document.querySelector('#monitor-search').value = '';
            document.querySelector('#device-type-filter').value = '';
            monitorCurrentPage = 1;
            renderDevices(monitorDevices);
        }

        function previousPage() {
            if (monitorCurrentPage > 1) {
                monitorCurrentPage--;
                renderDevices(monitorDevices);
            }
        }

        function nextPage() {
            const filteredDevices = getFilteredDevices();
            const totalPages = Math.ceil(filteredDevices.length / itemsPerPage);
            if (monitorCurrentPage < totalPages) {
                monitorCurrentPage++;
                renderDevices(monitorDevices);
            }
        }

        function goToPage(pageNum) {
            monitorCurrentPage = pageNum;
            renderDevices(monitorDevices);
        }

        async function bulkStartAll() {
            const filteredDevices = getFilteredDevices();
            if (!confirm(`Start monitoring on all ${filteredDevices.length} device${filteredDevices.length === 1 ? '' : 's'}?`)) return;
            try {
                for (const device of filteredDevices) {
                    if (!device.active) {
                        await requestJson(`/api/devices/${device.id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({active: true})});
                    }
                }
                setStatus(`✓ Started monitoring on ${filteredDevices.length} device${filteredDevices.length === 1 ? '' : 's'}`);
                await refreshStatus();
            } catch (error) { setStatus(error.message); }
        }

        async function bulkPauseAll() {
            const filteredDevices = getFilteredDevices();
            if (!confirm(`Pause monitoring on all ${filteredDevices.length} device${filteredDevices.length === 1 ? '' : 's'}?`)) return;
            try {
                for (const device of filteredDevices) {
                    if (device.active) {
                        await requestJson(`/api/devices/${device.id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({active: false})});
                    }
                }
                setStatus(`✓ Paused monitoring on ${filteredDevices.length} device${filteredDevices.length === 1 ? '' : 's'}`);
                await refreshStatus();
            } catch (error) { setStatus(error.message); }
        }

        function renderPaginationForTable(containerId, currentPage, totalItems, pageChangeHandler) {
            const totalPages = Math.ceil(totalItems / itemsPerPage);
            const container = document.querySelector(containerId);
            if (!container) return;
            
            if (totalPages <= 1) {
                container.replaceChildren();
                return;
            }

            const makeButton = (label, page, {active = false, disabled = false} = {}) => {
                const button = document.createElement('button');
                button.className = `range-button${active ? ' active' : ''}`;
                button.type = 'button';
                button.textContent = label;
                button.disabled = disabled;
                if (active) {
                    button.setAttribute('aria-current', 'page');
                }
                button.addEventListener('click', () => pageChangeHandler(page));
                return button;
            };

            const controls = [makeButton('← Previous', currentPage - 1, {disabled: currentPage === 1})];
            for (let i = 1; i <= totalPages; i++) {
                controls.push(makeButton(String(i), i, {active: i === currentPage}));
            }
            controls.push(makeButton('Next →', currentPage + 1, {disabled: currentPage === totalPages}));

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
            const startIndex = (pingRecordsCurrentPage - 1) * itemsPerPage;
            const endIndex = startIndex + itemsPerPage;
            const pageRecords = allTelemetry.slice(startIndex, endIndex);
            
            const tbody = document.querySelector('#reports-table tbody');
            tbody.innerHTML = pageRecords.map((sample) => `<tr data-recorded-at="${sample.recorded_at}"><td>${sample.recorded_at}</td><td>${escapeHtml(sample.device_name)}</td><td>${sample.target}</td><td>${sample.ping_received}/${sample.ping_sent}</td><td>${sample.packet_loss}%</td><td>${sample.latency_min_display}</td><td>${sample.latency_median_display}</td><td>${sample.latency_max_display}</td></tr>`).join('') || '<tr><td colspan="8">No ping records yet.</td></tr>';
            
            renderPaginationForTable('#ping-records-pagination', pingRecordsCurrentPage, allTelemetry.length, goToPingRecordsPage);
        }

        function renderAlertsTable(alerts) {
            allAlerts = alerts;
            const startIndex = (alertsCurrentPage - 1) * itemsPerPage;
            const endIndex = startIndex + itemsPerPage;
            const pageAlerts = allAlerts.slice(startIndex, endIndex);

            const rows = pageAlerts.map((alert) => `<tr><td>${alert.recorded_at}</td><td>${escapeHtml(alert.device_name)}</td><td>${escapeHtml(alert.message)}</td></tr>`).join('');
            const allRows = pageAlerts.map((alert) => `<tr><td>${alert.recorded_at}</td><td>${escapeHtml(alert.device_name)}</td><td>${escapeHtml(alert.message)}</td><td><span class="status-pill status-warning">Open</span></td></tr>`).join('');
            document.querySelector('#alert-rows').innerHTML = rows || '<tr><td colspan="3">No ping alerts.</td></tr>';
            document.querySelector('#all-alerts-rows').innerHTML = allRows || '<tr><td colspan="4">No ping alerts.</td></tr>';
            renderPaginationForTable('#alerts-pagination', alertsCurrentPage, allAlerts.length, goToAlertsPage);
            renderPaginationForTable('#all-alerts-pagination', alertsCurrentPage, allAlerts.length, goToAlertsPage);
        }

        function renderMlInsightsWithPagination(devices) {
            allMlRecords = devices;
            const startIndex = (mlInsightsCurrentPage - 1) * itemsPerPage;
            const endIndex = startIndex + itemsPerPage;
            const pageDevices = allMlRecords.slice(startIndex, endIndex);
            
            const body = document.querySelector('#ml-insight-rows');
            body.innerHTML = pageDevices.map((device) => `<tr><td>${escapeHtml(device.device_name)}<br><small>${escapeHtml(device.target)}</small></td><td>${device.current.online ? `${device.current.latency_median_ms ?? '-'} ms` : 'Unreachable'}<br><small>${device.current.packet_loss}% loss</small></td><td>${escapeHtml(modelOutputText(device.isolation_forest, 'isolation_forest'))}</td><td>${escapeHtml(modelOutputText(device.gru, 'gru'))}</td><td>${escapeHtml(modelOutputText(device.xgboost, 'xgboost'))}</td><td>${escapeHtml(riskOutputText(device.gru))}</td></tr>`).join('') || '<tr><td colspan="6">No valid ping samples yet.</td></tr>';
            
            renderPaginationForTable('#ml-insights-pagination', mlInsightsCurrentPage, allMlRecords.length, goToMlInsightsPage);
        }

        function goToPingRecordsPage(pageNum) {
            pingRecordsCurrentPage = pageNum;
            renderPingRecords(allTelemetry.slice().reverse());
        }

        function goToAlertsPage(pageNum) {
            alertsCurrentPage = pageNum;
            renderAlertsTable(allAlerts);
        }

        function goToMlInsightsPage(pageNum) {
            mlInsightsCurrentPage = pageNum;
            renderMlInsightsWithPagination(allMlRecords);
        }

        function renderMlLabels(labelData) {
            allMlLabels = labelData.samples || [];
            const startIndex = (mlLabelsCurrentPage - 1) * itemsPerPage;
            const endIndex = startIndex + itemsPerPage;
            const pageLabels = allMlLabels.slice(startIndex, endIndex);
            
            const labels = labelData.labels || [];
            const body = document.querySelector('#ml-label-rows');
            body.innerHTML = pageLabels.map((sample) => `<tr><td>${escapeHtml(sample.recorded_at)}</td><td>${escapeHtml(sample.device_name)}<br><small>${escapeHtml(sample.target)}</small></td><td>${sample.online ? `${sample.latency_median_ms ?? sample.latency_ms ?? '-'} ms` : 'Unreachable'}</td><td>${sample.packet_loss}%</td><td><select class="ml-label-select" aria-label="Condition label for sample ${sample.id}"><option value="">Choose label</option>${labels.map((label) => `<option value="${escapeHtml(label)}" ${sample.condition_label === label ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('')}</select></td><td><button class="range-button" type="button" onclick="saveMlLabel(${sample.id}, this)">Save</button></td></tr>`).join('') || '<tr><td colspan="6">No valid ping samples available to label.</td></tr>';            
            renderPaginationForTable('#ml-labels-pagination', mlLabelsCurrentPage, allMlLabels.length, goToMlLabelsPage);
        }

        function renderMlRecommendations(devices) {
            allMlRecommendations = (devices || []).map((device) => {
                const rec = device.supervised_recommendation || {
                    trained: device.xgboost?.state === 'ready',
                    condition: device.xgboost?.condition || device.current?.auto_rule_label || 'Normal',
                    confidence: device.xgboost?.confidence ?? null,
                    severity: (device.xgboost?.condition || device.current?.auto_rule_label) === 'Unreachable' ? 'critical' : ((device.xgboost?.condition || device.current?.auto_rule_label) === 'Normal' ? 'normal' : 'warning'),
                    possible_cause: 'Observed Ping Condition',
                    recommended_action: (device.suggestions && device.suggestions[0]?.action) || 'Continue monitoring.',
                    action_steps: [],
                };
                return {
                    telemetry_id: device.telemetry_id,
                    device_name: device.device_name,
                    target: device.target,
                    current: device.current || {},
                    ...rec,
                };
            });
            mlUnreachableCurrentPage = 1;
            mlPerformanceCurrentPage = 1;
            renderMlRecommendationsPage();
        }

        function getConditionActionSteps(row) {
            if (Array.isArray(row.action_steps) && row.action_steps.length > 0) {
                return row.action_steps;
            }
            const condition = row.condition;
            const latency = Number(row.current?.latency_median_ms || row.current?.latency_ms || 0);

            if (condition === 'Unreachable') {
                return [
                    'Verify hardware power and physical RJ-45 Ethernet link lights (PC & switch).',
                    'Check router DHCP client lease table to confirm IP assignment & verify no IP collision.',
                    'Verify endpoint Windows Firewall allows incoming ICMP Echo requests.',
                    'Compare with Dual Reference (Gateway & 1.1.1.1) and check upstream switch port state.'
                ];
            }
            if (condition === 'High Latency') {
                if (latency >= 300) {
                    return [
                        'Inspect top bandwidth-consuming processes or burst traffic on host.',
                        'Enable switch port rate-limiting or ICMP flood protection.',
                        'Compare latency with Dual Reference (Gateway & 1.1.1.1) to isolate host vs uplink.'
                    ];
                }
                return [
                    'Compare 5-probe burst jitter and 5-sample trend against Local Gateway & 1.1.1.1.',
                    'Check for heavy downloads, backups, or cloud sync on this host.',
                    'Apply QoS traffic prioritization on switch port.'
                ];
            }
            if (condition === 'Packet Loss') {
                return [
                    'Compare packet loss against Dual Reference (Gateway & 1.1.1.1) to isolate link vs ISP drop.',
                    'Inspect physical RJ-45 cable, connector, or Wi-Fi signal strength.',
                    'Check switch port statistics for duplex mismatch or CRC errors.'
                ];
            }
            return [
                'Healthy 5-probe burst response verified (low jitter, 0% packet loss).',
                'Continue routine monitoring.'
            ];
        }

        function buildRecommendationRowHtml(row, includeRemediation = true) {
            const badgeStyle = (severity) => {
                if (severity === 'critical') return 'background:rgba(211,47,47,0.14);color:#c62828;border:1px solid #c62828;';
                if (severity === 'warning') return 'background:rgba(237,108,2,0.14);color:#ef6c00;border:1px solid #ef6c00;';
                return 'background:rgba(46,125,50,0.14);color:#2e7d32;border:1px solid #2e7d32;';
            };

            const pingText = row.current.online
                ? `${row.current.latency_median_ms ?? row.current.latency_ms ?? '-'} ms`
                : 'No reply (Offline)';
            const lossText = `${row.current.packet_loss ?? (row.current.online ? 0 : 100)}% loss`;
            const confidenceText = row.confidence != null
                ? `${Math.round(Number(row.confidence) * 100)}% confidence`
                : (row.trained ? 'Trained XGBoost' : '5-probe preview (>150ms)');

            let remediationCellHtml = '';
            if (includeRemediation) {
                const steps = getConditionActionSteps(row);
                const stepsListHtml = `<ol style="margin:0 0 10px 0;padding-left:18px;font-size:0.87rem;line-height:1.45;">` +
                    steps.map((step, idx) => `<li><strong>Step ${idx + 1}:</strong> ${escapeHtml(step)}</li>`).join('') +
                    `</ol>`;

                const dropdownOptionsHtml = steps.map((step, idx) => {
                    const shortText = step.length > 55 ? step.slice(0, 52) + '...' : step;
                    return `<option value="Step ${idx + 1}: ${escapeHtml(step)}">Step ${idx + 1}: ${escapeHtml(shortText)}</option>`;
                }).join('');

                const actionControlsHtml = `
                    <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                        <select class="ml-step-dropdown" style="padding:4px 8px;border-radius:4px;font-size:0.82rem;border:1px solid var(--border-color);background:var(--bg-surface);color:inherit;max-width:260px;" aria-label="Select Action Step">
                            <option value="">-- Choose step to record --</option>
                            ${dropdownOptionsHtml}
                        </select>
                        <button type="button" class="range-button" onclick="recordActionStep(this, ${row.telemetry_id || 0})" style="padding:4px 10px;font-size:0.82rem;">Record</button>
                        <span class="ml-step-status" style="font-size:0.8rem;font-weight:600;"></span>
                    </div>
                `;
                remediationCellHtml = `<td>${stepsListHtml}${actionControlsHtml}</td>`;
            }

            return `<tr>
                <td><strong>${escapeHtml(row.device_name)}</strong><br><small>${escapeHtml(row.target)}</small></td>
                <td>${escapeHtml(pingText)}<br><small>${escapeHtml(lossText)}</small></td>
                <td><span style="display:inline-block;padding:3px 10px;border-radius:999px;font-weight:600;font-size:0.85rem;${badgeStyle(row.severity)}">${escapeHtml(row.condition)}</span><br><small>${escapeHtml(confidenceText)}</small></td>
                <td><strong>${escapeHtml(row.possible_cause)}</strong></td>
                ${remediationCellHtml}
            </tr>`;
        }

        function renderMlRecommendationsPage() {
            const bodyUnreachable = document.querySelector('#ml-unreachable-rows');
            const bodyPerf = document.querySelector('#ml-performance-rows');
            if (!bodyUnreachable || !bodyPerf) return;

            const showNormal = document.querySelector('#show-normal-recommendations')?.checked || false;

            // Separate Outages (Unreachable) from Performance Anomalies (High Latency & Packet Loss)
            const unreachableList = allMlRecommendations.filter((row) => row.condition === 'Unreachable' || (!row.current.online && row.condition !== 'Normal'));
            const perfList = showNormal
                ? allMlRecommendations.filter((row) => row.condition !== 'Unreachable' && row.current.online)
                : allMlRecommendations.filter((row) => (row.condition === 'High Latency' || row.condition === 'Packet Loss' || row.condition?.includes('Early Warning')) && row.current.online);

            // Update Header Count Badges
            const unreachablePill = document.querySelector('#ml-unreachable-count-pill');
            if (unreachablePill) {
                unreachablePill.textContent = `${unreachableList.length} Unreachable`;
                unreachablePill.className = `status-pill ${unreachableList.length > 0 ? 'status-down' : 'status-normal'}`;
            }

            const rawPerfCount = allMlRecommendations.filter((row) => (row.condition === 'High Latency' || row.condition === 'Packet Loss' || row.condition?.includes('Early Warning')) && row.current.online).length;
            const perfPill = document.querySelector('#ml-performance-count-pill');
            if (perfPill) {
                perfPill.textContent = `${rawPerfCount} Anomalies`;
                perfPill.className = `status-pill ${rawPerfCount > 0 ? 'status-warning' : 'status-normal'}`;
            }

            // Spot 1: Render Unreachable Devices (4 columns)
            if (!allMlRecommendations.length) {
                bodyUnreachable.innerHTML = '<tr><td colspan="4">No monitored device ping samples yet.</td></tr>';
                renderPaginationForTable('#ml-unreachable-pagination', 1, 0, goToMlUnreachablePage);
            } else if (!unreachableList.length) {
                bodyUnreachable.innerHTML = '<tr><td colspan="4" style="color:#2e7d32;font-weight:600;">✓ No unreachable devices. All monitored endpoints are responding to ICMP pings.</td></tr>';
                renderPaginationForTable('#ml-unreachable-pagination', 1, 0, goToMlUnreachablePage);
            } else {
                const startIndex = (mlUnreachableCurrentPage - 1) * itemsPerPage;
                const endIndex = startIndex + itemsPerPage;
                const pageRows = unreachableList.slice(startIndex, endIndex);
                bodyUnreachable.innerHTML = pageRows.map((r) => buildRecommendationRowHtml(r, false)).join('');
                renderPaginationForTable('#ml-unreachable-pagination', mlUnreachableCurrentPage, unreachableList.length, goToMlUnreachablePage);
            }

            // Spot 2: Render Performance Anomalies (High Latency & Packet Loss, 5 columns)
            if (!allMlRecommendations.length) {
                bodyPerf.innerHTML = '<tr><td colspan="5">No monitored device ping samples yet.</td></tr>';
                renderPaginationForTable('#ml-performance-pagination', 1, 0, goToMlPerformancePage);
            } else if (!perfList.length) {
                bodyPerf.innerHTML = '<tr><td colspan="5" style="color:#2e7d32;font-weight:600;">✓ No performance anomalies detected. All active devices are Normal (&le;150ms, 0% loss).</td></tr>';
                renderPaginationForTable('#ml-performance-pagination', 1, 0, goToMlPerformancePage);
            } else {
                const startIndex = (mlPerformanceCurrentPage - 1) * itemsPerPage;
                const endIndex = startIndex + itemsPerPage;
                const pageRows = perfList.slice(startIndex, endIndex);
                bodyPerf.innerHTML = pageRows.map((r) => buildRecommendationRowHtml(r, true)).join('');
                renderPaginationForTable('#ml-performance-pagination', mlPerformanceCurrentPage, perfList.length, goToMlPerformancePage);
            }
        }

        function goToMlUnreachablePage(pageNum) {
            mlUnreachableCurrentPage = pageNum;
            renderMlRecommendationsPage();
        }

        function goToMlPerformancePage(pageNum) {
            mlPerformanceCurrentPage = pageNum;
            renderMlRecommendationsPage();
        }

        function goToMlRecommendationsPage(pageNum) {
            mlPerformanceCurrentPage = pageNum;
            renderMlRecommendationsPage();
        }

        async function recordActionStep(button, telemetryId) {
            const container = button.closest('div');
            const select = container ? container.querySelector('.ml-step-dropdown') : null;
            const statusSpan = container ? container.querySelector('.ml-step-status') : null;
            const selectedStep = select ? select.value : '';

            if (!selectedStep) {
                if (statusSpan) {
                    statusSpan.style.color = '#ef6c00';
                    statusSpan.textContent = 'Select step first';
                }
                return;
            }

            button.disabled = true;
            if (statusSpan) {
                statusSpan.style.color = 'var(--text-muted)';
                statusSpan.textContent = 'Recording...';
            }

            try {
                await requestJson(`/api/ml/recommendation-feedback/${telemetryId}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        suggestion_id: selectedStep,
                        action: selectedStep
                    })
                });
                if (statusSpan) {
                    statusSpan.style.color = '#2e7d32';
                    statusSpan.textContent = '✓ Recorded';
                }
                const actionStatus = document.querySelector('#ml-action-status');
                if (actionStatus) {
                    actionStatus.textContent = `Action step recorded (${selectedStep}). Perform remediation check.`;
                }
                setTimeout(() => {
                    if (statusSpan) statusSpan.textContent = '';
                }, 4000);
            } catch (error) {
                if (statusSpan) {
                    statusSpan.style.color = '#c62828';
                    statusSpan.textContent = 'Failed';
                }
                const actionStatus = document.querySelector('#ml-action-status');
                if (actionStatus) {
                    actionStatus.textContent = error.message;
                }
            } finally {
                button.disabled = false;
            }
        }

        function goToMlLabelsPage(pageNum) {
            mlLabelsCurrentPage = pageNum;
            renderMlLabels({samples: allMlLabels, labels: document.querySelector('#ml-label-rows') ? Array.from(document.querySelectorAll('#ml-label-rows select option')).filter((o, i) => i > 0 && !o.disabled).map(o => o.value).filter((v, i, a) => a.indexOf(v) === i) : []});
        }

        async function refreshStatus() {
            try {
                const data = await requestJson('/api/status');
                const devices = data.devices || [];
                const telemetry = data.telemetry || [];
                const alerts = data.alerts || [];
                const latestByTarget = new Map();
                telemetry.forEach((sample) => { if (!latestByTarget.has(sample.target)) latestByTarget.set(sample.target, sample); });
                renderDevices(devices.map((device) => ({...device, latest: latestByTarget.get(device.target) || null})));
                const activeDevices = devices.filter((device) => device.active);
                const reachableDevices = activeDevices.filter((device) => latestByTarget.get(device.target)?.online);
                const networkHealth = activeDevices.length === 0
                    ? 'Waiting'
                    : reachableDevices.length === activeDevices.length
                        ? 'Good'
                        : reachableDevices.length > 0 ? 'Degraded' : 'Offline';
                const latencies = [...latestByTarget.values()]
                    .map((sample) => sample.latency_median_ms ?? sample.latency_ms)
                    .filter((value) => value !== null && value !== undefined && Number.isFinite(Number(value)));
                const averageLatency = latencies.length
                    ? `${Math.round(latencies.reduce((total, value) => total + Number(value), 0) / latencies.length * 10) / 10} ms`
                    : 'N/A';
                document.querySelector('#network-health').textContent = networkHealth;
                document.querySelector('#open-alerts').textContent = alerts.length;
                document.querySelector('#metric-average-latency').textContent = averageLatency;
                document.querySelector('#metric-reachable').textContent = `${reachableDevices.length} / ${latestByTarget.size}`;
                document.querySelector('#metric-monitoring').textContent = activeDevices.length;
                document.querySelector('#metric-samples').textContent = telemetry.filter((sample) => sample.protocol === 'icmp').length;
                document.querySelector('#dashboard-updated').textContent = new Date().toLocaleString();
                const fresh = telemetry.slice().reverse();
                if (fresh.length && fresh[fresh.length - 1].id !== latestSampleId) {
                    latestSampleId = fresh[fresh.length - 1].id;
                    monitorHistory = fresh.map((sample) => ({time: sample.recorded_at, device: sample.target, latency: sample.latency_median_ms ?? sample.latency_ms, latency_min_display:sample.latency_min_display, latency_median_display:sample.latency_median_display, latency_max_display:sample.latency_max_display, ping_received:sample.ping_received, ping_sent:sample.ping_sent, online: Boolean(sample.online), packet_loss: sample.packet_loss}));
                    renderPingRecords(fresh);
                    drawPingChart();
                }
                renderAlertsTable(alerts);
            } catch (error) { setStatus(error.message); }
        }

        async function loadBuildingName() {
            try {
                const data = await requestJson('/api/settings/building-name');
                document.querySelector('#building-name').textContent = data.building_name;
                document.querySelector('#building-name-input').value = data.building_name;
            } catch (error) {
                document.querySelector('#building-name').textContent = 'Location unavailable';
            }
        }

        function modelReadinessText(status, model, dependencyNames) {
            const trained = status.models?.[model]?.state === 'trained';
            if (trained) return 'Trained';
            if (dependencyNames.some((name) => !status.dependencies[name])) return 'Dependency needed';
            return status[model]?.ready ? 'Ready to train' : 'Collecting data';
        }

        function updateModelReadiness(status) {
            const classCounts = status.label_counts || {};
            const classText = Object.entries(classCounts).map(([label, count]) => `${label}: ${count}`).join(', ') || 'no rule labels';
            const featureList = (status.pipeline?.features || status.feature_columns || ['online', 'latency_ms', 'packet_loss', 'receive_ratio']).join(', ');
            document.querySelector('#ml-status-line').textContent = `System 1 Baseline (${featureList}) — ${status.telemetry_samples} ping samples; ${status.labeled_samples} labeled samples (${classText}).`;
            const trainedModels = Object.values(status.models || {}).filter((model) => model.state === 'trained').length;
            document.querySelector('#dashboard-valid-samples').textContent = status.telemetry_samples;
            document.querySelector('#dashboard-labeled-samples').textContent = status.labeled_samples;
            document.querySelector('#dashboard-ml-version').textContent = `${trainedModels}/3 trained`;

            const entries = [
                ['if', 'isolation_forest', ['scikit-learn'], `${status.isolation_forest.normal_samples}/${status.isolation_forest.required_normal_samples} Normal samples`],
                ['gru', 'gru', ['scikit-learn', 'torch'], `${status.gru.sequence_windows}/${status.gru.required_sequence_windows} sequence windows; window length ${status.gru.sequence_length}`],
                ['xgb', 'xgboost', ['scikit-learn', 'xgboost'], `Needs at least ${status.xgboost.required_samples_per_class} samples in two classes`],
            ];
            entries.forEach(([shortName, key, required, detail]) => {
                const model = status.models?.[key];
                const state = modelReadinessText(status, key, required);
                document.querySelector(`#${shortName}-model-state`).textContent = state;
                document.querySelector(`#${shortName}-model-detail`).textContent = model?.state === 'trained'
                    ? Object.entries(model).filter(([name]) => !['state', 'classifier_comparison', 'confusion_matrix', 'per_class'].includes(name)).map(([name, value]) => `${name.replaceAll('_', ' ')}: ${typeof value === 'object' ? JSON.stringify(value) : value}`).join(' | ')
                    : detail;
            });
            renderPerConditionReadiness(status);
            renderEffectivenessTables(status);
            renderClassifierComparison(status);
            renderTrainingLogs(status.training_logs || []);
            const trainBtn = document.querySelector('#train-models-button');
            if (trainBtn) trainBtn.disabled = false;
        }

        function renderPerConditionReadiness(status) {
            const container = document.querySelector('#ml-condition-readiness-badges');
            if (!container) return;
            const readiness = status.per_condition_readiness || {};
            const labels = ['Normal', 'High Latency', 'Packet Loss', 'Unreachable'];
            container.innerHTML = labels.map((label) => {
                const item = readiness[label] || {count: status.label_counts?.[label] || 0, required: 5, ready: (status.label_counts?.[label] || 0) >= 5};
                const bg = item.ready ? 'rgba(46, 125, 50, 0.14)' : 'rgba(237, 108, 2, 0.14)';
                const border = item.ready ? '#2e7d32' : '#ed6c02';
                const icon = item.ready ? '✓ Ready' : `Needs ${Math.max(0, item.required - item.count)} more`;
                return `<span style="padding:4px 10px;border-radius:999px;border:1px solid ${border};background:${bg};font-size:0.85rem;"><strong>${escapeHtml(label)}:</strong> ${item.count}/${item.required} (${icon})</span>`;
            }).join('');
        }

        function renderTrainingLogs(logs) {
            const body = document.querySelector('#ml-training-logs-rows');
            if (!body) return;
            if (!logs || !logs.length) {
                body.innerHTML = '<tr><td colspan="5">No training runs logged yet. Train a model above to record a permanent crash-safe log entry.</td></tr>';
                return;
            }
            const formatPct = (val) => val == null ? '-' : `${(Number(val) * 100).toFixed(1)}%`;
            body.innerHTML = logs.map((entry) => {
                const models = entry.models || {};
                const parts = [];
                if (models.isolation_forest?.state === 'trained') {
                    const m = models.isolation_forest;
                    parts.push(`<strong>IF (Table 1):</strong> P=${formatPct(m.precision)}, R=${formatPct(m.recall)}, F1=${formatPct(m.f1_score)}, FPR=${formatPct(m.false_positive_rate)}`);
                }
                if (models.gru?.state === 'trained') {
                    const m = models.gru;
                    parts.push(`<strong>GRU (Table 2):</strong> Lat MAE=${m.latency_mae_ms}ms, RMSE=${m.latency_rmse_ms}ms, Loss MAE=${m.packet_loss_mae_percent}%, Acc=${formatPct(m.reachability_accuracy)}`);
                }
                if (models.xgboost?.state === 'trained') {
                    const m = models.xgboost;
                    parts.push(`<strong>XGB (Table 3):</strong> Macro-F1=${formatPct(m.temporal_test_macro_f1)}, Bal Acc=${formatPct(m.balanced_accuracy)}`);
                }
                if (!parts.length) {
                    Object.entries(models).forEach(([k, v]) => parts.push(`${escapeHtml(k)}: ${escapeHtml(v.state || 'unknown')} ${escapeHtml(v.reason || '')}`));
                }
                const classSummary = Object.entries(entry.label_counts || {}).map(([k, v]) => `${escapeHtml(k)}: ${v}`).join(', ');
                return `<tr><td>${escapeHtml(entry.trained_at || '')}</td><td>${escapeHtml(entry.building_name || 'Active')}</td><td><strong>${escapeHtml((entry.trigger || 'all').replaceAll('_', ' ').toUpperCase())}</strong></td><td>${entry.telemetry_samples ?? 0} samples<br><small>${classSummary}</small></td><td>${parts.join('<br>')}</td></tr>`;
            }).join('');
        }

        function renderEffectivenessTables(status) {
            const formatPercent = (value) => value == null ? 'N/A' : `${(Number(value) * 100).toFixed(1)}%`;
            const ifModel = status.models?.isolation_forest;
            const ifBody = document.querySelector('#table1-if-rows');
            if (ifBody) {
                if (ifModel?.state === 'trained' && ifModel.precision != null) {
                    const cm = ifModel.confusion_matrix || {};
                    ifBody.innerHTML = `<tr><td><strong>${formatPercent(ifModel.precision)}</strong></td><td><strong>${formatPercent(ifModel.recall)}</strong></td><td><strong>${formatPercent(ifModel.f1_score)}</strong></td><td><strong>${formatPercent(ifModel.false_positive_rate)}</strong></td><td>TP: ${cm.tp ?? 0}, FP: ${cm.fp ?? 0}, TN: ${cm.tn ?? 0}, FN: ${cm.fn ?? 0} (n=${ifModel.evaluation_samples ?? ifModel.evaluated_samples ?? 0})</td></tr>`;
                } else {
                    ifBody.innerHTML = `<tr><td colspan="5">${escapeHtml(ifModel?.reason || 'Train Isolation Forest to populate Table 1 effectiveness metrics.')}</td></tr>`;
                }
            }

            const gruModel = status.models?.gru;
            const gruBody = document.querySelector('#table2-gru-rows');
            if (gruBody) {
                if (gruModel?.state === 'trained' && gruModel.latency_mae_ms != null) {
                    gruBody.innerHTML = `<tr><td><strong>${gruModel.latency_mae_ms} ms</strong></td><td><strong>${gruModel.latency_rmse_ms ?? 'N/A'} ms</strong></td><td><strong>${gruModel.packet_loss_mae_percent}%</strong></td><td><strong>${gruModel.packet_loss_rmse_percent ?? 'N/A'}%</strong></td><td><strong>${formatPercent(gruModel.reachability_accuracy)}</strong></td></tr>`;
                } else {
                    gruBody.innerHTML = `<tr><td colspan="5">${escapeHtml(gruModel?.reason || 'Train GRU to populate Table 2 effectiveness metrics.')}</td></tr>`;
                }
            }
        }

        function renderClassifierComparison(status) {
            const summary = document.querySelector('#classifier-comparison-summary');
            const body = document.querySelector('#classifier-comparison-rows');
            if (!summary || !body) return;
            const comparison = status.models?.xgboost?.classifier_comparison;
            if (!comparison) {
                const xgboostStatus = status.models?.xgboost;
                summary.textContent = xgboostStatus?.reason
                    ? `Not evaluated: ${xgboostStatus.reason}`
                    : 'No comparison yet. Review labels, then train to compare XGBoost with Logistic Regression and Random Forest on the same chronological holdout. XGBoost remains the live classifier.';
                body.innerHTML = '<tr><td colspan="4">Not evaluated. Every reviewed condition must appear in both the training and test periods.</td></tr>';
                return;
            }

            summary.textContent = `${comparison.protocol}: ${comparison.train_samples} training samples and ${comparison.test_samples} later test samples from ${comparison.test_start}. This is exploratory; validate on additional future periods before selecting a model.`;
            const modelNames = {
                xgboost: 'XGBoost',
                logistic_regression: 'Logistic Regression',
                random_forest: 'Random Forest',
            };
            const formatPercent = (value) => `${(Number(value) * 100).toFixed(1)}%`;
            body.innerHTML = Object.entries(comparison.models || {}).map(([name, metrics]) => {
                const classRecall = Object.entries(metrics.per_class || {}).map(([label, values]) =>
                    `${escapeHtml(label)}: ${formatPercent(values.recall)} (n=${values.support})`
                ).join('; ');
                return `<tr><td>${modelNames[name] || escapeHtml(name)}</td><td>${formatPercent(metrics.macro_f1)}</td><td>${formatPercent(metrics.balanced_accuracy)}</td><td>${classRecall}</td></tr>`;
            }).join('') || '<tr><td colspan="4">No comparison results are available.</td></tr>';
        }

        function modelOutputText(result, modelName) {
            if (!result || result.state === 'not_trained') return 'Not trained';
            if (result.state === 'not_enough_history') return `Needs ${result.required_samples} samples`;
            if (result.state === 'retrain_required') return 'Retrain model';
            if (result.state !== 'ready') return result.reason || result.state;
            if (modelName === 'isolation_forest') return `${result.result} (score ${result.anomaly_score})`;
            if (modelName === 'gru') {
                const recon = result.reconstruction_mse != null ? ` | Recon MSE: ${result.reconstruction_mse} (${result.reconstruction_anomaly ? '⚠️ Seq Anomaly' : 'Normal'}) [${result.inference_ms ?? 13}ms]` : '';
                return `${result.next_latency_ms} ms; ${result.next_packet_loss_percent}% loss; reachability ${Math.round(result.next_reachability_probability * 100)}%${recon}`;
            }
            return `${result.condition} (${Math.round(result.confidence * 100)}%)`;
        }

        function riskOutputText(result) {
            if (!result || result.state !== 'ready') return modelOutputText(result, 'gru');
            const risks = result.risk_indicators || {};
            return `Bottleneck: ${risks.bottleneck || 'N/A'}; congestion: ${risks.congestion || 'N/A'}; failure: ${risks.failure || 'N/A'}`;
        }

        function renderMlInsights(devices) {
            renderMlInsightsWithPagination(devices);
        }

        function renderNetworkReferences(data) {
            const setting = document.querySelector('#external-reference-ip');
            if (setting && document.activeElement !== setting) setting.value = data.external_reference_target || '';
            const refBody = document.querySelector('#reference-rows');
            const devBody = document.querySelector('#reference-device-rows');
            if (!refBody || !devBody) return;
            const referenceRows = [
                data.gateway || {name: 'Local gateway', target: 'Not detected', sample_count: 0, online: null},
                data.external || {name: 'External reference', target: data.external_reference_target, sample_count: 0, online: null},
            ];
            refBody.innerHTML = referenceRows.map((reference) => `<tr><td>${escapeHtml(reference.name)}</td><td>${escapeHtml(reference.target)}</td><td>${reference.sample_count ? reference.online ? 'Responding' : 'No ping reply' : 'Not checked'}</td><td>${reference.packet_loss_percent == null ? '-' : `${reference.packet_loss_percent}% (${reference.sample_count} samples)`}</td><td>${reference.latency_median_ms == null ? '-' : `${reference.latency_median_ms} ms`}</td><td>${reference.latency_variation_ms == null ? '-' : `${reference.latency_variation_ms} ms`}</td></tr>`).join('');
            devBody.innerHTML = data.devices.map((device) => `<tr><td>${escapeHtml(device.target)}</td><td>${device.packet_loss_percent == null ? '-' : `${device.packet_loss_percent}% (${device.sample_count} samples)`}</td><td>${device.latency_median_ms == null ? '-' : `${device.latency_median_ms} ms`}</td><td>${device.latency_variation_ms == null ? '-' : `${device.latency_variation_ms} ms`}</td><td>${escapeHtml(device.comparison)}</td></tr>`).join('') || '<tr><td colspan="5">No monitored PC samples yet.</td></tr>';
        }

        async function pollNetworkReferences(button) {
            button.disabled = true;
            document.querySelector('#ml-action-status').textContent = 'Pinging gateway and external reference...';
            try {
                const data = await requestJson('/api/network-references/poll', {method: 'POST'});
                renderNetworkReferences(data);
                document.querySelector('#ml-action-status').textContent = 'Reference samples updated.';
            } catch (error) { document.querySelector('#ml-action-status').textContent = error.message; }
            finally { button.disabled = false; }
        }

        async function saveExternalReference() {
            const input = document.querySelector('#external-reference-ip');
            const status = document.querySelector('#reference-setting-status');
            try {
                const result = await requestJson('/api/settings/external-reference', {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({target: input.value})});
                input.value = result.target;
                status.textContent = 'External reference saved.';
                await refreshMlPanel();
            } catch (error) { status.textContent = error.message; }
        }

        async function loadDatabaseSelector() {
            const selector = document.querySelector('#database-selector');
            const status = document.querySelector('#reference-setting-status');
            try {
                const data = await requestJson('/api/settings/databases');
                document.querySelector('#building-name-input').value = data.current_building || '';
                const bldgBadge = document.querySelector('#building-name');
                if (bldgBadge) bldgBadge.textContent = data.current_building || 'Unknown location';
                selector.innerHTML = data.databases.map((db) => `<option value="${escapeAttribute(db.name)}" ${db.name === data.current_building ? 'selected' : ''}>${escapeHtml(db.name)}</option>`).join('') || '<option value="">No databases found</option>';
            } catch (error) { status.textContent = error.message; }
        }

        async function switchDatabase() {
            const selector = document.querySelector('#database-selector');
            const status = document.querySelector('#reference-setting-status');
            const building_name = selector.value;
            if (!building_name) {
                status.textContent = 'Select a database first.';
                return;
            }
            try {
                const result = await requestJson('/api/settings/databases/select', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ building_name })
                });
                status.textContent = result.message || 'Database switched successfully!';
                document.querySelector('#building-name-input').value = result.building_name;
                const bldgBadge = document.querySelector('#building-name');
                if (bldgBadge) bldgBadge.textContent = result.building_name;
                await loadDatabaseSelector();
                await refreshStatus();
                setTimeout(() => { status.textContent = ''; }, 5000);
            } catch (error) { status.textContent = error.message; }
        }

        async function restartMonitoring() {
            const status = document.querySelector('#reference-setting-status');
            try {
                const result = await requestJson('/api/control/restart-monitoring', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                status.textContent = result.message || 'Monitoring service restarted successfully!';
            } catch (error) { status.textContent = error.message; }
        }

        async function loadExternalReferenceSetting() {
            try {
                const data = await requestJson('/api/network-references');
                renderNetworkReferences(data);
            } catch (error) { document.querySelector('#reference-setting-status').textContent = error.message; }
        }

        function renderRecommendationFeedback(feedback) {
            const outcomes = [['resolved', 'Resolved'], ['not_resolved', 'Not resolved'], ['unknown', 'Unknown']];
            const findings = ['', 'Shared path degradation', 'Device-specific issue', 'ICMP blocked', 'No issue found', 'Other / unknown'];
            const body = document.querySelector('#ml-feedback-rows');
            body.innerHTML = feedback.map((item) => `<tr><td>${escapeHtml(item.selected_at)}</td><td>${escapeHtml(item.device_name)}<br><small>${escapeHtml(item.target)}</small></td><td>${escapeHtml(item.model_sources.join(', '))}<br><small>${escapeHtml(item.evidence.join(' '))}</small></td><td>${escapeHtml(item.suggested_action)}</td><td><select class="ml-feedback-control" aria-label="Outcome for selected action ${item.id}"><option value="">Record outcome</option>${outcomes.map(([value, label]) => `<option value="${value}" ${item.outcome === value ? 'selected' : ''}>${label}</option>`).join('')}</select></td><td><select class="ml-feedback-control" aria-label="Verified finding for selected action ${item.id}">${findings.map((value) => `<option value="${escapeAttribute(value)}" ${item.verified_finding === value ? 'selected' : ''}>${escapeHtml(value || 'Not verified')}</option>`).join('')}</select></td><td><input class="ml-feedback-control ml-feedback-notes" type="text" maxlength="1000" value="${escapeAttribute(item.notes)}" aria-label="Notes for selected action ${item.id}"></td><td><button class="range-button" type="button" onclick="saveMlRecommendationOutcome(${item.id}, this)">Save</button></td></tr>`).join('') || '<tr><td colspan="8">No selected suggestions yet.</td></tr>';
        }

        async function refreshMlPanel() {
            try {
                const [status, insights] = await Promise.all([
                    requestJson('/api/ml/status'),
                    requestJson('/api/ml/insights'),
                ]);
                updateModelReadiness(status);
                renderMlRecommendations(insights.devices || []);
            } catch (error) {
                document.querySelector('#ml-action-status').textContent = error.message;
            }
        }

        async function saveMlLabel(telemetryId, button) {
            const label = button.closest('tr').querySelector('select').value;
            if (!label) { document.querySelector('#ml-action-status').textContent = 'Choose a condition label first.'; return; }
            try {
                await requestJson(`/api/ml/labels/${telemetryId}`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({label})});
                document.querySelector('#ml-action-status').textContent = 'Reviewed label saved.';
                await refreshMlPanel();
            } catch (error) { document.querySelector('#ml-action-status').textContent = error.message; }
        }

        async function selectMlRecommendation(telemetryId, suggestionId, button) {
            button.disabled = true;
            try {
                await requestJson(`/api/ml/recommendation-feedback/${telemetryId}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({suggestion_id: suggestionId})});
                document.querySelector('#ml-action-status').textContent = 'Selection recorded. Perform the check, then record its outcome below.';
                await refreshMlPanel();
            } catch (error) { document.querySelector('#ml-action-status').textContent = error.message; }
            finally { button.disabled = false; }
        }

        async function saveMlRecommendationOutcome(feedbackId, button) {
            const row = button.closest('tr');
            const controls = row.querySelectorAll('select');
            const outcome = controls[0].value;
            if (!outcome) { document.querySelector('#ml-action-status').textContent = 'Choose an outcome before saving.'; return; }
            try {
                await requestJson(`/api/ml/recommendation-feedback/${feedbackId}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({outcome, verified_finding: controls[1].value, notes: row.querySelector('.ml-feedback-notes').value})});
                document.querySelector('#ml-action-status').textContent = 'Action outcome saved for later review.';
                await refreshMlPanel();
            } catch (error) { document.querySelector('#ml-action-status').textContent = error.message; }
        }

        async function applyAutoRuleLabels(button) {
            if (button) button.disabled = true;
            document.querySelector('#ml-action-status').textContent = 'Applying System 1 rigid >150ms rule labels to all ping samples...';
            try {
                const result = await requestJson('/api/ml/auto-label', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({overwrite: true})});
                await refreshMlPanel();
                document.querySelector('#ml-action-status').textContent = `Rule-based auto-labeling complete (${result.updated} samples labeled with >150ms threshold).`;
            } catch (error) { document.querySelector('#ml-action-status').textContent = error.message; }
            finally { if (button) button.disabled = false; }
        }

        async function trainSingleMlModel(modelName, button) {
            if (button) button.disabled = true;
            const labelMap = {
                isolation_forest: 'Isolation Forest (Unsupervised)',
                gru: 'GRU (Time-Series Forecast)',
                xgboost: 'XGBoost (Supervised Condition Classifier)',
            };
            document.querySelector('#ml-action-status').textContent = `Training ${labelMap[modelName] || modelName} and saving crash-safe checkpoint...`;
            try {
                const response = await requestJson(`/api/ml/train/${modelName}`, {method: 'POST'});
                const modelState = response.result?.state || 'unknown';
                const detail = response.result?.reason ? ` (${response.result.reason})` : '';
                const summary = `${labelMap[modelName] || modelName}: ${modelState}${detail} — saved to disk & training history log.`;
                await refreshMlPanel();
                document.querySelector('#ml-action-status').textContent = summary;
            } catch (error) {
                document.querySelector('#ml-action-status').textContent = error.message;
            } finally {
                if (button) button.disabled = false;
            }
        }

        async function trainMlModels(button) {
            button.disabled = true;
            document.querySelector('#ml-action-status').textContent = 'Training models that meet their data requirements...';
            try {
                const result = await requestJson('/api/ml/train', {method: 'POST'});
                const summary = Object.entries(result.models).map(([name, value]) => `${name.replaceAll('_', ' ')}: ${value.state}`).join('; ');
                document.querySelector('#ml-action-status').textContent = summary;
                await refreshMlPanel();
                document.querySelector('#ml-action-status').textContent = summary;
            } catch (error) { document.querySelector('#ml-action-status').textContent = error.message; }
            finally { button.disabled = false; }
        }

        async function pollNow(button) {
            button.disabled = true;
            try { await requestJson('/api/monitor-now', {method: 'POST'}); await refreshStatus(); }
            catch (error) { setStatus(error.message); }
            finally { button.disabled = false; }
        }

        function drawPingChart() {
            const canvas = document.querySelector('#ping-chart');
            if (!canvas || document.querySelector('[data-panel="monitor"][hidden]')) return;
            const width = canvas.clientWidth || 600;
            const height = 220;
            const ratio = window.devicePixelRatio || 1;
            canvas.width = width * ratio;
            canvas.height = height * ratio;
            const context = canvas.getContext('2d');
            context.scale(ratio, ratio);
            context.clearRect(0, 0, width, height);
            const target = document.querySelector('#chart-device').value;
            const points = monitorHistory.filter((sample) => sample.device === target && sample.latency != null).slice(-100);
            const padding = {top: 18, right: 18, bottom: 28, left: 42};
            const maximum = Math.max(10, ...points.map((point) => point.latency));
            const x = (index) => padding.left + index / Math.max(points.length - 1, 1) * (width - padding.left - padding.right);
            const y = (value) => height - padding.bottom - value / maximum * (height - padding.top - padding.bottom);
            context.strokeStyle = getComputedStyle(document.body).getPropertyValue('--chart-grid') || '#dce6ee';
            for (let index = 0; index < 4; index += 1) { const lineY = padding.top + index * (height - padding.top - padding.bottom) / 3; context.beginPath(); context.moveTo(padding.left, lineY); context.lineTo(width - padding.right, lineY); context.stroke(); }
            if (points.length) {
                context.beginPath(); context.strokeStyle = '#1976c9'; context.lineWidth = 2.5;
                points.forEach((point, index) => index ? context.lineTo(x(index), y(point.latency)) : context.moveTo(x(index), y(point.latency)));
                context.stroke();
            }
            context.fillStyle = getComputedStyle(document.body).color;
            context.font = '12px Segoe UI';
            context.fillText(`${Math.round(maximum)} ms`, 4, padding.top + 4);
            context.fillText('0 ms', 4, height - padding.bottom + 4);
            if (!points.length) context.fillText('No ping samples yet', padding.left + 8, height / 2);
        }

        document.querySelectorAll('.range-button[data-hours]').forEach((button) => button.addEventListener('click', () => {
            const cutoff = Date.now() - Number(button.dataset.hours) * 3600000;
            document.querySelectorAll('.range-button[data-hours]').forEach((item) => item.classList.toggle('active', item === button));
            document.querySelectorAll('#reports-table tbody tr[data-recorded-at]').forEach((row) => { row.hidden = Date.parse(row.dataset.recordedAt) < cutoff; });
        }));

        const themeToggle = document.querySelector('#theme-toggle');
        function setTheme(isDark) {
            document.body.classList.toggle('dark-mode', isDark);
            themeToggle.checked = isDark;
            document.querySelector('#theme-label').textContent = isDark ? 'Dark mode' : 'Light mode';
            localStorage.setItem('network-monitor-theme', isDark ? 'dark' : 'light');
        }
        setTheme(localStorage.getItem('network-monitor-theme') === 'dark');
        themeToggle.addEventListener('change', () => { setTheme(themeToggle.checked); drawPingChart(); });

        const viewUrlMap = {
            'dashboard': '/dashboard',
            'monitor': '/ping',
            'alerts': '/alerts',
            'reports': '/records',
            'ml-insights': '/ml-insights',
            'settings': '/settings',
            'about': '/about'
        };

        const urlViewMap = {
            '': 'dashboard',
            '/': 'dashboard',
            '/dashboard': 'dashboard',
            '/ping': 'monitor',
            '/monitor': 'monitor',
            '/alerts': 'alerts',
            '/records': 'reports',
            '/reports': 'reports',
            '/ping-records': 'reports',
            '/ml-insights': 'ml-insights',
            '/settings': 'settings',
            '/about': 'about'
        };

        function switchView(viewName, pushHistory = true) {
            const navItems = document.querySelectorAll('.nav-item');
            const panels = document.querySelectorAll('[data-panel]');
            const targetItem = document.querySelector(`.nav-item[data-view="${viewName}"]`);
            if (!targetItem) return;

            navItems.forEach((navItem) => {
                const active = navItem === targetItem;
                navItem.classList.toggle('active', active);
                if (active) navItem.setAttribute('aria-current', 'page');
                else navItem.removeAttribute('aria-current');
            });

            panels.forEach((panel) => {
                const visible = panel.dataset.panel === viewName;
                panel.hidden = !visible;
                panel.classList.toggle('active', visible);
            });

            if (viewName === 'monitor') { drawPingChart(); refreshStatus(); }
            if (viewName === 'ml-insights') refreshMlPanel();
            if (viewName === 'settings') { loadExternalReferenceSetting(); loadDatabaseSelector(); }

            if (pushHistory) {
                const targetUrl = viewUrlMap[viewName] || `/${viewName}`;
                if (window.location.pathname.toLowerCase() !== targetUrl.toLowerCase()) {
                    history.pushState({ view: viewName }, '', targetUrl);
                }
            }
        }

        document.querySelectorAll('.nav-item').forEach((item) => {
            item.addEventListener('click', (event) => {
                if (event.ctrlKey || event.metaKey || event.shiftKey || event.which === 2) {
                    return;
                }
                event.preventDefault();
                const viewName = item.dataset.view;
                if (viewName) {
                    switchView(viewName, true);
                }
            });
        });

        window.addEventListener('popstate', (event) => {
            const currentPath = window.location.pathname.toLowerCase().replace(/\/$/, '') || '/';
            const targetView = (event.state && event.state.view) || urlViewMap[currentPath] || 'dashboard';
            switchView(targetView, false);
        });

        const mlOldRecRows = document.querySelector('#ml-recommendation-rows');
        if (mlOldRecRows) mlOldRecRows.addEventListener('click', (event) => {
            const button = event.target.closest('[data-select-suggestion]');
            if (button) selectMlRecommendation(Number(button.dataset.selectTelemetry), button.dataset.selectSuggestion, button);
        });

        window.addEventListener('resize', drawPingChart);
        requestJson('/api/devices').then((data) => { document.querySelector('#subnet-input').value = data.local_network.suggested_subnet; }).catch((error) => setStatus(error.message));
        loadBuildingName();
        refreshMlPanel();
        refreshStatus();
        window.setInterval(refreshStatus, 5000);
    </script>
</body>
</html>