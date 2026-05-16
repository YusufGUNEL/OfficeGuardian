// OfficeGuardian - Admin Dashboard WebSocket & Live Updates

let ws = null;
let warningTarget = null;

// --- Chart.js Canli Grafikler ---
const MAX_CHART_POINTS = 60; // Son 60 veri noktasi (~1dk)
let postureChart = null;
let workBreakChart = null;
let comparisonChart = null;
const chartData = {}; // {username: {scores: [], labels: [], working: 0, onBreak: 0}}

function getChartTextColor() {
    return getComputedStyle(document.body).getPropertyValue('--text-secondary').trim() || '#8b95a8';
}

function getChartGridColor() {
    return getComputedStyle(document.body).getPropertyValue('--border-subtle').trim() || 'rgba(255,255,255,0.06)';
}

const CHART_COLORS = [
    '#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa',
    '#fb923c', '#22d3ee', '#e879f9', '#84cc16', '#f43f5e',
];

function initCharts() {
    const textColor = getChartTextColor();
    const gridColor = getChartGridColor();

    // Postur Skoru Zaman Grafigi (Line)
    const postureCtx = document.getElementById('postureChart');
    if (postureCtx) {
        postureChart = new Chart(postureCtx, {
            type: 'line',
            data: { labels: [], datasets: [] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 300 },
                interaction: { intersect: false, mode: 'index' },
                scales: {
                    x: {
                        display: true,
                        ticks: { color: textColor, maxTicksLimit: 10, font: { size: 10 } },
                        grid: { color: gridColor },
                    },
                    y: {
                        min: 0, max: 100,
                        ticks: { color: textColor, font: { size: 10 } },
                        grid: { color: gridColor },
                    },
                },
                plugins: {
                    legend: { labels: { color: textColor, font: { size: 11 } } },
                },
            },
        });
    }

    // Calisma/Mola Pasta Grafigi (Doughnut)
    const workCtx = document.getElementById('workBreakChart');
    if (workCtx) {
        workBreakChart = new Chart(workCtx, {
            type: 'doughnut',
            data: {
                labels: ['Calisiyor', 'Mola'],
                datasets: [{
                    data: [0, 0],
                    backgroundColor: ['#34d399', '#fbbf24'],
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { labels: { color: textColor, font: { size: 11 } } },
                },
            },
        });
    }

    // Calisan Karsilastirma (Bar)
    const compCtx = document.getElementById('comparisonChart');
    if (compCtx) {
        comparisonChart = new Chart(compCtx, {
            type: 'bar',
            data: { labels: [], datasets: [
                { label: 'Postur Skoru', data: [], backgroundColor: '#60a5fa', borderRadius: 4 },
            ]},
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: textColor, font: { size: 11 } }, grid: { display: false } },
                    y: { min: 0, max: 100, ticks: { color: textColor, font: { size: 10 } }, grid: { color: gridColor } },
                },
                plugins: {
                    legend: { labels: { color: textColor, font: { size: 11 } } },
                },
            },
        });
    }
}

function updateCharts(username, data) {
    const posture = data.posture || {};
    const gaze = data.gaze || {};
    const score = posture.score || 0;
    const isWorking = gaze.is_working !== false;

    // Kullanici verisini baslat
    if (!chartData[username]) {
        chartData[username] = { scores: [], labels: [], working: 0, onBreak: 0 };
    }
    const ud = chartData[username];

    // Zaman etiketi
    const now = new Date();
    const timeLabel = now.getHours().toString().padStart(2,'0') + ':' +
                      now.getMinutes().toString().padStart(2,'0') + ':' +
                      now.getSeconds().toString().padStart(2,'0');

    ud.scores.push(score);
    ud.labels.push(timeLabel);
    if (ud.scores.length > MAX_CHART_POINTS) {
        ud.scores.shift();
        ud.labels.shift();
    }

    // Calisma/mola sayaci
    if (isWorking) ud.working++;
    else ud.onBreak++;

    // --- Postur Line Chart guncelle ---
    if (postureChart) {
        // Labels (en uzun dizi)
        let maxLen = 0;
        const usernames = Object.keys(chartData);
        usernames.forEach(u => { if (chartData[u].labels.length > maxLen) maxLen = chartData[u].labels.length; });
        const longestUser = usernames.find(u => chartData[u].labels.length === maxLen);
        postureChart.data.labels = longestUser ? chartData[longestUser].labels : [];

        // Dataset olustur
        postureChart.data.datasets = usernames.map((u, i) => ({
            label: u,
            data: chartData[u].scores,
            borderColor: CHART_COLORS[i % CHART_COLORS.length],
            backgroundColor: 'transparent',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
        }));
        postureChart.update('none');
    }

    // --- Pasta grafik guncelle (toplam) ---
    if (workBreakChart) {
        let totalWorking = 0, totalBreak = 0;
        Object.values(chartData).forEach(d => {
            totalWorking += d.working;
            totalBreak += d.onBreak;
        });
        workBreakChart.data.datasets[0].data = [totalWorking, totalBreak];
        workBreakChart.update('none');
    }

    // --- Bar chart guncelle ---
    if (comparisonChart) {
        const usernames = Object.keys(chartData);
        const lastScores = usernames.map(u => {
            const s = chartData[u].scores;
            return s.length > 0 ? s[s.length - 1] : 0;
        });
        comparisonChart.data.labels = usernames;
        comparisonChart.data.datasets[0].data = lastScores;
        comparisonChart.data.datasets[0].backgroundColor = usernames.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]);
        comparisonChart.update('none');
    }
}

function initAdminDashboard(roomCode) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/admin/${roomCode}/`;

    ws = new WebSocket(wsUrl);

    ws.onopen = function() {
        console.log('[WS] Yönetici bağlantısı kuruldu');
        initCharts();
    };

    ws.onmessage = function(e) {
        const data = JSON.parse(e.data);

        switch(data.type) {
            case 'initial_state':
                console.log('[WS] Çevrimiçi:', data.online_users);
                break;

            case 'employee_status':
                updateEmployeeCard(data.username, data.data);
                break;

            case 'office_status':
                updateOfficeStatus(data.username, data.data);
                break;

            case 'employee_connected':
                addEmployeeCard(data.username);
                updateOnlineCount(1);
                if (typeof playAlertSound === 'function') playAlertSound('connect');
                break;

            case 'employee_disconnected':
                markEmployeeOffline(data.username);
                updateOnlineCount(-1);
                if (typeof playAlertSound === 'function') playAlertSound('disconnect');
                break;
        }
    };

    ws.onclose = function() {
        console.log('[WS] Bağlantı kapandı, 3sn sonra tekrar denenecek...');
        setTimeout(() => initAdminDashboard(roomCode), 3000);
    };

    ws.onerror = function(err) {
        console.error('[WS] Hata:', err);
    };
}

function updateEmployeeCard(username, data) {
    let card = document.getElementById(`card-${username}`);
    if (!card) {
        addEmployeeCard(username);
        card = document.getElementById(`card-${username}`);
    }
    if (!card) return;

    const posture = data.posture || {};
    const gaze = data.gaze || {};

    // Postür durumu
    const postureEl = document.getElementById(`posture-${username}`);
    if (postureEl) {
        if (posture.is_good) {
            postureEl.className = 'badge bg-success';
            postureEl.textContent = `Dik (${(posture.neck_angle || 0).toFixed(1)}°)`;
        } else {
            postureEl.className = 'badge bg-danger';
            postureEl.textContent = `Kambur (${(posture.neck_angle || 0).toFixed(1)}°)`;
        }
    }

    // Çalışma durumu
    const workEl = document.getElementById(`work-${username}`);
    if (workEl) {
        if (gaze.is_working) {
            workEl.className = 'badge bg-success';
            workEl.textContent = 'Çalışıyor';
        } else {
            workEl.className = 'badge bg-warning';
            workEl.textContent = 'Mola';
        }
    }

    // Skor
    const scoreEl = document.getElementById(`score-${username}`);
    if (scoreEl) {
        const score = posture.score || 0;
        let color = '#2ecc71';
        if (score < 50) color = '#e74c3c';
        else if (score < 75) color = '#f39c12';
        scoreEl.innerHTML = `<span style="color:${color}; font-weight:700">${score}</span>`;
    }

    // Grafikleri guncelle
    updateCharts(username, data);
}

function updateOfficeStatus(username, data) {
    const persons = data.persons || [];
    persons.forEach(person => {
        const label = `${username}_${person.label}`;
        updateEmployeeCard(label, {
            posture: person.posture,
            gaze: person.gaze,
        });
    });
}

function addEmployeeCard(username) {
    if (document.getElementById(`card-${username}`)) return;

    const grid = document.getElementById('employees-grid');
    if (!grid) return;

    const col = document.createElement('div');
    col.className = 'col-md-4 col-lg-3';
    col.id = `card-${username}`;
    col.innerHTML = `
        <div class="employee-card">
            <div class="card-header-custom">
                <span class="status-dot online"></span>
                <strong>${username}</strong>
            </div>
            <div class="card-body-custom">
                <div class="stat-row">
                    <span>Postür:</span>
                    <span id="posture-${username}" class="badge bg-secondary">Bekleniyor</span>
                </div>
                <div class="stat-row">
                    <span>Çalışma:</span>
                    <span id="work-${username}" class="badge bg-secondary">Bekleniyor</span>
                </div>
                <div class="stat-row">
                    <span>Skor:</span>
                    <span id="score-${username}">-</span>
                </div>
                <div class="mt-2 d-flex gap-1">
                    <button class="btn btn-warning btn-sm flex-grow-1"
                            onclick="openWarningModal('${username}')">
                        <i class="bi bi-exclamation-triangle"></i> Uyar
                    </button>
                    <a href="/employee/${username}/"
                       class="btn btn-info btn-sm">
                        <i class="bi bi-eye"></i>
                    </a>
                </div>
            </div>
        </div>
    `;
    grid.appendChild(col);
}

function markEmployeeOffline(username) {
    const card = document.getElementById(`card-${username}`);
    if (card) {
        const dot = card.querySelector('.status-dot');
        if (dot) {
            dot.classList.remove('online');
            dot.classList.add('offline');
        }
        card.style.opacity = '0.5';
    }
}

function updateOnlineCount(delta) {
    const countEl = document.getElementById('count-val');
    if (countEl) {
        const current = parseInt(countEl.textContent) || 0;
        countEl.textContent = Math.max(0, current + delta);
    }
}

function openWarningModal(username) {
    warningTarget = username;
    document.getElementById('warning-target').textContent = username;
    document.getElementById('warning-message').value = '';
    const modal = new bootstrap.Modal(document.getElementById('warningModal'));
    modal.show();
}

function sendWarning() {
    const message = document.getElementById('warning-message').value.trim();
    if (!message || !warningTarget || !ws) return;

    ws.send(JSON.stringify({
        type: 'send_warning',
        username: warningTarget,
        message: message,
    }));

    if (typeof playAlertSound === 'function') playAlertSound('warning');
    bootstrap.Modal.getInstance(document.getElementById('warningModal')).hide();
    warningTarget = null;
}

// Hızlı uyarı butonları
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.quick-warn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.getElementById('warning-message').value = this.dataset.msg;
        });
    });
});
