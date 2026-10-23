/**
 * Ping latency canvas chart rendering.
 */

function drawPingChart() {
    const canvas = document.querySelector('#ping-chart');
    if (!canvas) return;

    // Don't draw if the ping panel is currently hidden
    const pingPanel = document.querySelector('[data-panel="ping"]') || document.querySelector('[data-panel="monitor"]');
    if (pingPanel && pingPanel.hidden) return;

    const width = canvas.clientWidth || 600;
    const height = 220;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    const context = canvas.getContext('2d');
    context.scale(ratio, ratio);
    context.clearRect(0, 0, width, height);

    const targetSelect = document.querySelector('#chart-device');
    const target = targetSelect ? targetSelect.value : '';
    const points = (window.monitorHistory || [])
        .filter((sample) => sample.device === target && sample.latency != null)
        .slice(-100);

    const padding = { top: 18, right: 18, bottom: 28, left: 42 };
    const maximum = Math.max(10, ...points.map((point) => point.latency));
    const x = (index) => padding.left + (index / Math.max(points.length - 1, 1)) * (width - padding.left - padding.right);
    const y = (value) => height - padding.bottom - (value / maximum) * (height - padding.top - padding.bottom);

    context.strokeStyle = getComputedStyle(document.body).getPropertyValue('--chart-grid') || '#dce6ee';
    for (let index = 0; index < 4; index += 1) {
        const lineY = padding.top + (index * (height - padding.top - padding.bottom)) / 3;
        context.beginPath();
        context.moveTo(padding.left, lineY);
        context.lineTo(width - padding.right, lineY);
        context.stroke();
    }

    if (points.length) {
        context.beginPath();
        context.strokeStyle = '#1976c9';
        context.lineWidth = 2.5;
        points.forEach((point, index) => {
            if (index) {
                context.lineTo(x(index), y(point.latency));
            } else {
                context.moveTo(x(index), y(point.latency));
            }
        });
        context.stroke();
    }

    context.fillStyle = getComputedStyle(document.body).color;
    context.font = '12px Segoe UI';
    context.fillText(`${Math.round(maximum)} ms`, 4, padding.top + 4);
    context.fillText('0 ms', 4, height - padding.bottom + 4);
    if (!points.length) {
        context.fillText('No ping samples yet', padding.left + 8, height / 2);
    }
}

window.addEventListener('resize', drawPingChart);
