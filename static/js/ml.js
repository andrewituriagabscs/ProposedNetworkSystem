/**
 * Machine learning panel, models, training, labeling, and recommendation handlers.
 */

let mlInsightsCurrentPage = 1;
let mlLabelsCurrentPage = 1;
let mlRecommendationsCurrentPage = 1;
let allMlRecords = [];
let allMlLabels = [];
let allMlRecommendations = [];
const mlItemsPerPage = 10;

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
    const statusLine = document.querySelector('#ml-status-line');
    if (statusLine) {
        statusLine.textContent = `SYSTEM 2: Proposed / Enhanced Approach (12 Temporal Features: ${featureList}) — ${status.telemetry_samples} 5-probe burst samples; ${status.labeled_samples} Admin-Reviewed condition labels (${classText}).`;
    }
    const trainedModels = Object.values(status.models || {}).filter((model) => model.state === 'trained').length;
    const valSamples = document.querySelector('#dashboard-valid-samples');
    if (valSamples) valSamples.textContent = status.telemetry_samples;
    const labSamples = document.querySelector('#dashboard-labeled-samples');
    if (labSamples) labSamples.textContent = status.labeled_samples;
    const mlVer = document.querySelector('#dashboard-ml-version');
    if (mlVer) mlVer.textContent = `${trainedModels}/3 trained`;

    const entries = [
        ['if', 'isolation_forest', ['scikit-learn'], `${status.isolation_forest.normal_samples}/${status.isolation_forest.required_normal_samples} Normal samples`],
        ['gru', 'gru', ['scikit-learn', 'torch'], `${status.gru.sequence_windows}/${status.gru.required_sequence_windows} sequence windows; window length ${status.gru.sequence_length}`],
        ['xgb', 'xgboost', ['scikit-learn', 'xgboost'], `Needs at least ${status.xgboost.required_samples_per_class} samples in two classes`],
    ];
    entries.forEach(([shortName, key, required, detail]) => {
        const model = status.models?.[key];
        const state = modelReadinessText(status, key, required);
        const stateEl = document.querySelector(`#${shortName}-model-state`);
        if (stateEl) stateEl.textContent = state;
        const detailEl = document.querySelector(`#${shortName}-model-detail`);
        if (detailEl) {
            detailEl.textContent = model?.state === 'trained'
                ? Object.entries(model).filter(([name]) => !['state', 'classifier_comparison', 'confusion_matrix', 'per_class'].includes(name)).map(([name, value]) => `${name.replaceAll('_', ' ')}: ${typeof value === 'object' ? JSON.stringify(value) : value}`).join(' | ')
                : detail;
        }
    });
    renderPerConditionReadiness(status);
    renderEffectivenessTables(status);
    renderClassifierComparison(status);
    renderTrainingLogs(status.training_logs || []);
}

function renderPerConditionReadiness(status) {
    const container = document.querySelector('#ml-condition-readiness-badges');
    if (!container) return;
    const readiness = status.per_condition_readiness || {};
    const labels = ['Normal', 'High Latency', 'Packet Loss', 'Unreachable'];
    container.innerHTML = labels.map((label) => {
        const item = readiness[label] || { count: status.label_counts?.[label] || 0, required: 5, ready: (status.label_counts?.[label] || 0) >= 5 };
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
    if (modelName === 'gru') return `${result.next_latency_ms} ms; ${result.next_packet_loss_percent}% loss; reachability ${Math.round(result.next_reachability_probability * 100)}%`;
    return `${result.condition} (${Math.round(result.confidence * 100)}%)`;
}

function riskOutputText(result) {
    if (!result || result.state !== 'ready') return modelOutputText(result, 'gru');
    const risks = result.risk_indicators || {};
    return `Bottleneck: ${risks.bottleneck || 'N/A'}; congestion: ${risks.congestion || 'N/A'}; failure: ${risks.failure || 'N/A'}`;
}

function renderMlLabels(labelData) {
    allMlLabels = labelData.samples || [];
    const startIndex = (mlLabelsCurrentPage - 1) * mlItemsPerPage;
    const endIndex = startIndex + mlItemsPerPage;
    const pageLabels = allMlLabels.slice(startIndex, endIndex);

    const labels = labelData.labels || [];
    const body = document.querySelector('#ml-label-rows');
    if (body) {
        body.innerHTML = pageLabels.map((sample) => `
            <tr>
                <td>${escapeHtml(sample.recorded_at)}</td>
                <td>${escapeHtml(sample.device_name)}<br><small>${escapeHtml(sample.target)}</small></td>
                <td>${sample.online ? `${sample.latency_median_ms ?? sample.latency_ms ?? '-'} ms` : 'Unreachable'}</td>
                <td>${sample.packet_loss}%</td>
                <td>
                    <select class="ml-label-select" aria-label="Condition label for sample ${sample.id}">
                        <option value="">Choose label</option>
                        ${labels.map((label) => `<option value="${escapeHtml(label)}" ${sample.condition_label === label ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('')}
                    </select>
                </td>
                <td><button class="range-button" type="button" onclick="saveMlLabel(${sample.id}, this)">Save</button></td>
            </tr>
        `).join('') || '<tr><td colspan="6">No valid ping samples available to label.</td></tr>';
    }
    renderPaginationForTable('#ml-labels-pagination', mlLabelsCurrentPage, allMlLabels.length, goToMlLabelsPage);
}

function goToMlLabelsPage(pageNum) {
    mlLabelsCurrentPage = pageNum;
    renderMlLabels({ samples: allMlLabels, labels: ['Normal', 'High Latency', 'Packet Loss', 'Unreachable'] });
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
        };
        return {
            device_name: device.device_name,
            target: device.target,
            current: device.current || {},
            isolation_forest: device.isolation_forest || {},
            gru: device.gru || {},
            ...rec,
        };
    });
    mlRecommendationsCurrentPage = 1;
    renderMlRecommendationsPage();
}

function renderMlRecommendationsPage() {
    const body = document.querySelector('#ml-recommendation-rows');
    if (!body) return;
    const showNormal = document.querySelector('#show-normal-recommendations')?.checked || false;
    const filtered = showNormal
        ? allMlRecommendations
        : allMlRecommendations.filter((row) => row.condition !== 'Normal');

    if (!allMlRecommendations.length) {
        body.innerHTML = '<tr><td colspan="7">No monitored device ping samples yet.</td></tr>';
        renderPaginationForTable('#ml-recommendations-pagination', 1, 0, goToMlRecommendationsPage);
        return;
    }

    if (!filtered.length) {
        body.innerHTML = '<tr><td colspan="7" style="color:#2e7d32;font-weight:600;">✓ All monitored devices are currently Normal (5-probe burst healthy, 0% loss) — no actions required.</td></tr>';
        renderPaginationForTable('#ml-recommendations-pagination', 1, 0, goToMlRecommendationsPage);
        return;
    }

    const startIndex = (mlRecommendationsCurrentPage - 1) * mlItemsPerPage;
    const endIndex = startIndex + mlItemsPerPage;
    const pageRecs = filtered.slice(startIndex, endIndex);

    const badgeStyle = (severity) => {
        if (severity === 'critical') return 'background:rgba(211,47,47,0.14);color:#c62828;border:1px solid #c62828;';
        if (severity === 'warning') return 'background:rgba(237,108,2,0.14);color:#ef6c00;border:1px solid #ef6c00;';
        return 'background:rgba(46,125,50,0.14);color:#2e7d32;border:1px solid #2e7d32;';
    };

    body.innerHTML = pageRecs.map((row) => {
        const pingText = row.current.online
            ? `${row.current.latency_min_ms ?? '-'}/${row.current.latency_median_ms ?? '-'}/${row.current.latency_max_ms ?? '-'} ms (jitter ${row.current.latency_jitter_ms ?? 0} ms)`
            : 'No reply (Offline)';
        const lossText = `${row.current.packet_loss ?? 0}% loss`;
        const confidenceText = row.confidence != null
            ? `${Math.round(Number(row.confidence) * 100)}% confidence`
            : 'Rule preview (Train XGBoost)';
        return `<tr>
            <td><strong>${escapeHtml(row.device_name)}</strong><br><small>${escapeHtml(row.target)}</small></td>
            <td>${escapeHtml(pingText)}<br><small>${escapeHtml(lossText)}</small></td>
            <td>${escapeHtml(modelOutputText(row.isolation_forest, 'isolation_forest'))}</td>
            <td>${escapeHtml(modelOutputText(row.gru, 'gru'))}<br><small>${escapeHtml(riskOutputText(row.gru))}</small></td>
            <td><span style="display:inline-block;padding:3px 10px;border-radius:999px;font-weight:600;font-size:0.85rem;${badgeStyle(row.severity)}">${escapeHtml(row.condition)}</span><br><small>${escapeHtml(confidenceText)}</small></td>
            <td><strong>${escapeHtml(row.possible_cause)}</strong></td>
            <td>${escapeHtml(row.recommended_action)}</td>
        </tr>`;
    }).join('');

    renderPaginationForTable('#ml-recommendations-pagination', mlRecommendationsCurrentPage, filtered.length, goToMlRecommendationsPage);
}

function goToMlRecommendationsPage(pageNum) {
    mlRecommendationsCurrentPage = pageNum;
    renderMlRecommendationsPage();
}

function renderNetworkReferences(data) {
    const setting = document.querySelector('#external-reference-ip');
    if (setting && document.activeElement !== setting) setting.value = data.external_reference_target || '';
    const refBody = document.querySelector('#reference-rows');
    const devBody = document.querySelector('#reference-device-rows');
    if (!refBody || !devBody) return;
    const referenceRows = [
        data.gateway || { name: 'Local gateway', target: 'Not detected', sample_count: 0, online: null },
        data.external || { name: 'External reference', target: data.external_reference_target, sample_count: 0, online: null },
    ];
    refBody.innerHTML = referenceRows.map((reference) => `
        <tr>
            <td>${escapeHtml(reference.name)}</td>
            <td>${escapeHtml(reference.target)}</td>
            <td>${reference.sample_count ? (reference.online ? 'Responding' : 'No ping reply') : 'Not checked'}</td>
            <td>${reference.packet_loss_percent == null ? '-' : `${reference.packet_loss_percent}% (${reference.sample_count} samples)`}</td>
            <td>${reference.latency_median_ms == null ? '-' : `${reference.latency_median_ms} ms`}</td>
            <td>${reference.latency_variation_ms == null ? '-' : `${reference.latency_variation_ms} ms`}</td>
        </tr>
    `).join('');
    devBody.innerHTML = data.devices.map((device) => `
        <tr>
            <td>${escapeHtml(device.target)}</td>
            <td>${device.packet_loss_percent == null ? '-' : `${device.packet_loss_percent}% (${device.sample_count} samples)`}</td>
            <td>${device.latency_median_ms == null ? '-' : `${device.latency_median_ms} ms`}</td>
            <td>${device.latency_variation_ms == null ? '-' : `${device.latency_variation_ms} ms`}</td>
            <td>${escapeHtml(device.comparison)}</td>
        </tr>
    `).join('') || '<tr><td colspan="5">No monitored PC samples yet.</td></tr>';
}

async function pollNetworkReferences(button) {
    if (button) button.disabled = true;
    const actionStatus = document.querySelector('#ml-action-status');
    if (actionStatus) actionStatus.textContent = 'Pinging gateway and external reference...';
    try {
        const data = await requestJson('/api/network-references/poll', { method: 'POST' });
        renderNetworkReferences(data);
        if (actionStatus) actionStatus.textContent = 'Reference samples updated.';
    } catch (error) {
        if (actionStatus) actionStatus.textContent = error.message;
    } finally {
        if (button) button.disabled = false;
    }
}

async function refreshMlPanel() {
    try {
        const [status, insights, refData, labelData] = await Promise.all([
            requestJson('/api/ml/status'),
            requestJson('/api/ml/insights'),
            requestJson('/api/network-references').catch(() => null),
            requestJson('/api/ml/labels').catch(() => null),
        ]);
        if (refData) renderNetworkReferences(refData);
        if (labelData) renderMlLabels(labelData);
        updateModelReadiness(status);
        renderMlRecommendations(insights.devices || []);
    } catch (error) {
        const statusEl = document.querySelector('#ml-action-status');
        if (statusEl) statusEl.textContent = error.message;
    }
}

async function saveMlLabel(telemetryId, button) {
    const label = button.closest('tr')?.querySelector('select')?.value;
    const actionStatus = document.querySelector('#ml-action-status');
    if (!label) {
        if (actionStatus) actionStatus.textContent = 'Choose a condition label first.';
        return;
    }
    try {
        await requestJson(`/api/ml/labels/${telemetryId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ label }),
        });
        if (actionStatus) actionStatus.textContent = 'Reviewed label saved.';
        await refreshMlPanel();
    } catch (error) {
        if (actionStatus) actionStatus.textContent = error.message;
    }
}

async function selectMlRecommendation(telemetryId, suggestionId, button) {
    if (button) button.disabled = true;
    const actionStatus = document.querySelector('#ml-action-status');
    try {
        await requestJson(`/api/ml/recommendation-feedback/${telemetryId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ suggestion_id: suggestionId }),
        });
        if (actionStatus) actionStatus.textContent = 'Selection recorded. Perform the check, then record its outcome below.';
        await refreshMlPanel();
    } catch (error) {
        if (actionStatus) actionStatus.textContent = error.message;
    } finally {
        if (button) button.disabled = false;
    }
}

async function saveMlRecommendationOutcome(feedbackId, button) {
    const row = button.closest('tr');
    const controls = row.querySelectorAll('select');
    const outcome = controls[0]?.value;
    const actionStatus = document.querySelector('#ml-action-status');
    if (!outcome) {
        if (actionStatus) actionStatus.textContent = 'Choose an outcome before saving.';
        return;
    }
    try {
        await requestJson(`/api/ml/recommendation-feedback/${feedbackId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                outcome,
                verified_finding: controls[1]?.value,
                notes: row.querySelector('.ml-feedback-notes')?.value || '',
            }),
        });
        if (actionStatus) actionStatus.textContent = 'Action outcome saved for later review.';
        await refreshMlPanel();
    } catch (error) {
        if (actionStatus) actionStatus.textContent = error.message;
    }
}

async function applyAutoRuleLabels(button) {
    if (button) button.disabled = true;
    const actionStatus = document.querySelector('#ml-action-status');
    if (actionStatus) actionStatus.textContent = 'Confirming Human-in-the-Loop condition labels for 5-probe burst samples...';
    try {
        const result = await requestJson('/api/ml/auto-label', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ overwrite: true }),
        });
        await refreshMlPanel();
        if (actionStatus) actionStatus.textContent = `Human-in-the-Loop condition labeling updated (${result.updated} Admin-Reviewed labels saved).`;
    } catch (error) {
        if (actionStatus) actionStatus.textContent = error.message;
    } finally {
        if (button) button.disabled = false;
    }
}

async function trainSingleMlModel(modelName, button) {
    if (button) button.disabled = true;
    const labelMap = {
        isolation_forest: 'Isolation Forest (Unsupervised)',
        gru: 'GRU (Time-Series Forecast)',
        xgboost: 'XGBoost (Supervised Condition Classifier)',
    };
    const actionStatus = document.querySelector('#ml-action-status');
    if (actionStatus) actionStatus.textContent = `Training ${labelMap[modelName] || modelName} and saving crash-safe checkpoint...`;
    try {
        const response = await requestJson(`/api/ml/train/${modelName}`, { method: 'POST' });
        const modelState = response.result?.state || 'unknown';
        const detail = response.result?.reason ? ` (${response.result.reason})` : '';
        const summary = `${labelMap[modelName] || modelName}: ${modelState}${detail} — saved to disk & training history log.`;
        await refreshMlPanel();
        if (actionStatus) actionStatus.textContent = summary;
    } catch (error) {
        if (actionStatus) actionStatus.textContent = error.message;
    } finally {
        if (button) button.disabled = false;
    }
}

async function trainMlModels(button) {
    if (button) button.disabled = true;
    const actionStatus = document.querySelector('#ml-action-status');
    if (actionStatus) actionStatus.textContent = 'Training models that meet their data requirements...';
    try {
        const result = await requestJson('/api/ml/train', { method: 'POST' });
        const summary = Object.entries(result.models).map(([name, value]) => `${name.replaceAll('_', ' ')}: ${value.state}`).join('; ');
        if (actionStatus) actionStatus.textContent = summary;
        await refreshMlPanel();
    } catch (error) {
        if (actionStatus) actionStatus.textContent = error.message;
    } finally {
        if (button) button.disabled = false;
    }
}
