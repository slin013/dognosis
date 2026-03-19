// Parse server-provided JSON for initial chart state
let rows = [];
let latest = null;

const sensorScript = document.getElementById("sensor-data");
if (sensorScript && sensorScript.textContent) {
    try {
        rows = JSON.parse(sensorScript.textContent) || [];
    } catch (e) {
        console.error("Failed to parse sensor-data JSON", e);
    }
}

const latestScript = document.getElementById("latest-data");
if (latestScript && latestScript.textContent) {
    try {
        latest = JSON.parse(latestScript.textContent) || null;
    } catch (e) {
        console.error("Failed to parse latest-data JSON", e);
    }
}

// Simple dashboard state for flags tab
const dashboardState = {
    flags: [],
    selectedFlag: null
};

let ctx = document.getElementById("hrChart").getContext("2d");

let hrChart = new Chart(ctx, {
    type: "line",
    data: {
        labels: [],
        datasets: [{
            label: "Heart Rate",
            data: [],
            borderWidth: 2,
            borderColor: "rgba(220, 53, 69, 1)",
            backgroundColor: "rgba(220, 53, 69, 0.08)",
            tension: 0.25,
            pointRadius: 0
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true
            },
            tooltip: {
                mode: "index",
                intersect: false
            }
        },
        scales: {
            x: {
                ticks: {
                    autoSkip: true,
                    maxTicksLimit: 8
                }
            },
            y: {
                beginAtZero: false
            }
        }
    }
});

let currentTimeWindowSeconds = 1800; // default 30 minutes

function setConnectionStatus(isOnline) {
    const badge = document.getElementById("connectionStatus");
    if (!badge) return;

    if (isOnline) {
        badge.textContent = "Live";
        badge.className = "badge bg-success";
    } else {
        badge.textContent = "Offline";
        badge.className = "badge bg-danger";
    }
}

function setLastUpdated() {
    const el = document.getElementById("lastUpdatedText");
    if (!el) return;
    const now = new Date();
    el.textContent = `Updated at ${now.toLocaleTimeString()}`;
}

function updateHeartRateCard(latestSample) {
    const valueEl = document.getElementById("hrCardValue");
    const statusEl = document.getElementById("hrCardStatus");
    if (!latestSample || !valueEl || !statusEl) return;

    const bpm =
        latestSample.bpm ??
        latestSample.heart_rate ??
        latestSample.hr ??
        latestSample[1];
    if (bpm == null) {
        valueEl.textContent = "-- bpm";
        statusEl.textContent = "No data";
        statusEl.className = "badge bg-secondary";
        return;
    }

    const rounded = Math.round(bpm);
    valueEl.textContent = `${rounded} bpm`;

    // Simple, placeholder thresholds – adjust based on vet guidance
    let statusText = "Normal";
    let badgeClass = "badge bg-success";
    if (rounded < 50) {
        statusText = "Low";
        badgeClass = "badge bg-warning text-dark";
    } else if (rounded > 140) {
        statusText = "High";
        badgeClass = "badge bg-danger";
    }

    statusEl.textContent = statusText;
    statusEl.className = badgeClass;
}

function updateActivityTempCards(sample) {
    const actEl = document.getElementById("activityCardValue");
    const actStatus = document.getElementById("activityCardStatus");
    const tempEl = document.getElementById("tempCardValue");
    const tempStatus = document.getElementById("tempCardStatus");
    if (!sample) {
        if (actEl) actEl.textContent = "--";
        if (tempEl) tempEl.textContent = "--";
        return;
    }
    const steps = sample.step_count ?? sample[4];
    if (actEl) actEl.textContent = steps != null ? String(steps) : "--";
    if (actStatus) actStatus.textContent = "Total steps";

    const t = sample.temperature ?? sample[2];
    if (tempEl) {
        if (t != null && !Number.isNaN(Number(t))) {
            const n = Number(t);
            tempEl.textContent = `${n.toFixed(1)}°`;
            if (tempStatus) {
                tempStatus.textContent = n > 45 ? "°F (approx.)" : "°C (approx.)";
            }
        } else {
            tempEl.textContent = "--";
        }
    }
}

// async function updateChart() {
//     try {
//         const response = await fetch("/live-data");
//         if (!response.ok) {
//             throw new Error(`HTTP ${response.status}`);
//         }
//         const data = await response.json();

//         if (!Array.isArray(data) || data.length === 0) {
//             hrChart.data.labels = [];
//             hrChart.data.datasets[0].data = [];
//             hrChart.update();
//             setConnectionStatus(true);
//             setLastUpdated();
//             updateHeartRateCard(null);
//             return;
//         }

//         // Assume each row has a Unix timestamp in seconds; support both object and array shapes.
//         const nowSec = Math.floor(Date.now() / 1000);
//         const filtered = data.filter(sample => {
//             const ts = sample.timestamp ?? sample[0];
//             if (!ts) return false;
//             return ts >= nowSec - currentTimeWindowSeconds;
//         });

//         const timestamps = filtered.map(sample => {
//             const ts = sample.timestamp ?? sample[0];
//             return new Date(ts * 1000).toLocaleTimeString();
//         });

//         const heartRates = filtered.map(sample => (
//             sample.bpm ??
//             sample.heart_rate ??
//             sample.hr ??
//             sample[1]
//         ));

//         hrChart.data.labels = timestamps.reverse();
//         hrChart.data.datasets[0].data = heartRates.reverse();
//         hrChart.update();

//         const latestSample = filtered[filtered.length - 1] || data[data.length - 1];
//         updateHeartRateCard(latestSample);

//         setConnectionStatus(true);
//         setLastUpdated();
//     } catch (err) {
//         console.error("Error updating chart", err);
//         setConnectionStatus(false);
//     }
// }

async function updateChart() {
    try {
        const response = await fetch("/live-data");
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();

        if (!Array.isArray(data) || data.length === 0) {
            hrChart.data.labels = [];
            hrChart.data.datasets[0].data = [];
            hrChart.update();
            setConnectionStatus(true);
            setLastUpdated();
            updateHeartRateCard(null);
            updateActivityTempCards(null);
            return;
        }

        const nowSec = Math.floor(Date.now() / 1000);
        const filtered = data.filter((sample) => {
            const ts = sample.timestamp ?? sample[0];
            if (ts == null) return false;
            return ts >= nowSec - currentTimeWindowSeconds;
        });

        const use = filtered.length ? filtered : data;
        const chronological = [...use].reverse();

        const timestamps = chronological.map((sample) => {
            const ts = sample.timestamp ?? sample[0];
            return new Date(ts * 1000).toLocaleTimeString();
        });
        const heartRates = chronological.map(
            (sample) =>
                sample.bpm ?? sample.heart_rate ?? sample.hr ?? sample[1]
        );

        hrChart.data.labels = timestamps;
        hrChart.data.datasets[0].data = heartRates;
        hrChart.update();

        const latestSample = data[0];
        updateHeartRateCard(latestSample);
        updateActivityTempCards(latestSample);

        setConnectionStatus(true);
        setLastUpdated();
    } catch (err) {
        console.error("Error updating chart", err);
        setConnectionStatus(false);
    }
}

async function updateFlags() {
    const listEl = document.getElementById("flagsList");
    if (!listEl) return;

    try {
        const response = await fetch("/flags");
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();

        if (!Array.isArray(data) || data.length === 0) {
            listEl.innerHTML = '<li class="list-group-item text-muted">No flags recorded yet</li>';
            return;
        }

        listEl.innerHTML = "";

        data.forEach(row => {
            // Support both tuple-like rows and object rows
            const id = row.id ?? row[0];
            const ts = row.timestamp ?? row[1];
            const label =
                row.flag_type ?? row.label ?? row.type ?? row[2] ?? "Flag";
            const severity = (row.severity ?? row[3] ?? "").toString().toLowerCase();

            let severityBadgeClass = "bg-secondary";
            if (severity.includes("high") || severity.includes("critical")) {
                severityBadgeClass = "bg-danger";
            } else if (severity.includes("medium") || severity.includes("moderate")) {
                severityBadgeClass = "bg-warning text-dark";
            } else if (severity.includes("low")) {
                severityBadgeClass = "bg-info text-dark";
            }

            const li = document.createElement("li");
            li.className = "list-group-item d-flex justify-content-between align-items-center";
            li.style.cursor = "pointer";

            const left = document.createElement("div");
            const title = document.createElement("div");
            title.className = "fw-semibold";
            title.textContent = label;

            const subtitle = document.createElement("small");
            subtitle.className = "text-muted";
            if (ts) {
                const date = new Date(ts * 1000);
                subtitle.textContent = date.toLocaleString();
            } else {
                subtitle.textContent = "Timestamp unavailable";
            }

            left.appendChild(title);
            left.appendChild(subtitle);

            const badge = document.createElement("span");
            badge.className = `badge ${severityBadgeClass}`;
            badge.textContent = severity || "Flag";

            li.appendChild(left);
            li.appendChild(badge);

            if (id != null) {
                li.addEventListener("click", () => {
                    const flagsTab = document.getElementById("flags-tab");
                    if (flagsTab && typeof bootstrap !== "undefined") {
                        bootstrap.Tab.getOrCreateInstance(flagsTab).show();
                    }
                });
            }

            listEl.appendChild(li);
        });
    } catch (err) {
        console.error("Error loading flags", err);
        listEl.innerHTML = '<li class="list-group-item text-danger">Failed to load flags</li>';
    }
}

// ---- Flags & Insights tab helpers ----

function mapFlagTypeToLabel(flagType) {
    if (!flagType) return "Flag";
    switch (flagType) {
        case "hr_high":
            return "High heart rate";
        case "hr_low":
            return "Low heart rate";
        case "hr_rapid_change":
            return "Rapid HR change";
        case "hr_unstable":
            return "Unstable heart rate";
        case "temp_high":
            return "Overheating";
        case "temp_low":
            return "Underheating";
        case "limp":
            return "Limp / gait issue";
        default:
            return flagType.replace(/_/g, " ");
    }
}

function buildInsightsForFlag(flag) {
    const insights = [];

    const bpm = flag.bpm;
    const temp = flag.temperature;
    const limp = flag.limp;
    const asym = flag.asymmetry;

    if (flag.flag_type === "temp_high" || (temp != null && temp > 39.2)) {
        insights.push("Temperature is elevated; overheating is possible. Consider rest, shade, and water.");
    }
    if (flag.flag_type === "temp_low" || (temp != null && temp < 36.5)) {
        insights.push("Temperature is low; underheating or exposure to cold may be an issue.");
    }
    if (flag.flag_type === "hr_high" || (bpm != null && bpm > 160)) {
        insights.push("Heart rate is high relative to baseline; may indicate stress, pain, or heavy exertion.");
    }
    if (flag.flag_type === "hr_low" || (bpm != null && bpm < 50)) {
        insights.push("Heart rate is low; if dog is not resting calmly, this may warrant attention.");
    }
    if (flag.flag_type === "hr_rapid_change") {
        insights.push("Heart rate changed rapidly; check for sudden activity, anxiety, or pain triggers.");
    }
    if (flag.flag_type === "hr_unstable") {
        insights.push("Heart rate pattern is unstable; irregular rhythm may need veterinary review.");
    }
    if (flag.flag_type === "limp" || limp === 1 || (asym != null && asym > 0.2)) {
        insights.push("Gait asymmetry or limp detected; inspect paws, joints, and recent activity.");
    }

    if (insights.length === 0) {
        insights.push("No specific rule-based insight available; review context and trends around this time.");
    }

    return insights;
}

function renderFlagsTable() {
    const tbody = document.getElementById("flagsTableBody");
    if (!tbody) return;

    const flags = dashboardState.flags;
    if (!Array.isArray(flags) || flags.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-muted">No incidents recorded yet</td></tr>';
        return;
    }

    tbody.innerHTML = "";

    flags.forEach(flag => {
        const tr = document.createElement("tr");
        if (flag && flag.id != null) {
            tr.dataset.flagId = String(flag.id);
        }
        tr.style.cursor = "pointer";

        const tsCell = document.createElement("td");
        if (flag.timestamp) {
            const date = new Date(flag.timestamp * 1000);
            tsCell.textContent = date.toLocaleString();
        } else {
            tsCell.textContent = "Unknown time";
        }

        const typeCell = document.createElement("td");
        typeCell.textContent = mapFlagTypeToLabel(flag.flag_type);

        const detailCell = document.createElement("td");
        const parts = [];
        if (flag.bpm != null) parts.push(`${Math.round(flag.bpm)} bpm`);
        if (flag.temperature != null) parts.push(`${flag.temperature.toFixed(1)} °C`);
        if (flag.limp === 1) parts.push("limp");
        if (flag.asymmetry != null) parts.push(`asym ${flag.asymmetry.toFixed(2)}`);
        detailCell.textContent = parts.join(" • ") || (flag.description || "");

        tr.appendChild(tsCell);
        tr.appendChild(typeCell);
        tr.appendChild(detailCell);

        tr.addEventListener("click", () => {
            selectFlag(flag);
        });

        tbody.appendChild(tr);
    });
}

function highlightSelectedFlag() {
    const tbody = document.getElementById("flagsTableBody");
    if (!tbody) return;

    const selectedId = dashboardState.selectedFlag && dashboardState.selectedFlag.id != null
        ? String(dashboardState.selectedFlag.id)
        : null;

    const trs = tbody.querySelectorAll("tr[data-flag-id]");
    trs.forEach(tr => {
        const isSelected = selectedId != null && tr.dataset.flagId === selectedId;
        tr.classList.toggle("table-info", isSelected);
    });
}

function selectFlag(flag) {
    dashboardState.selectedFlag = flag;
    highlightSelectedFlag();
    renderFlagDetail();
}

function renderFlagDetail() {
    const emptyEl = document.getElementById("flagDetailEmpty");
    const contentEl = document.getElementById("flagDetailContent");
    if (!emptyEl || !contentEl) return;

    const flag = dashboardState.selectedFlag;
    if (!flag) {
        emptyEl.classList.remove("d-none");
        contentEl.classList.add("d-none");
        return;
    }

    emptyEl.classList.add("d-none");
    contentEl.classList.remove("d-none");

    const timeEl = document.getElementById("flagDetailTime");
    const typeEl = document.getElementById("flagDetailType");
    const metricsEl = document.getElementById("flagDetailMetrics");
    const descEl = document.getElementById("flagDetailDescription");
    const insightsEl = document.getElementById("flagDetailInsights");

    if (timeEl) {
        if (flag.timestamp) {
            const d = new Date(flag.timestamp * 1000);
            timeEl.textContent = d.toLocaleString();
        } else {
            timeEl.textContent = "Unknown time";
        }
    }

    if (typeEl) {
        typeEl.textContent = mapFlagTypeToLabel(flag.flag_type);
    }

    if (metricsEl) {
        const parts = [];
        if (flag.bpm != null) parts.push(`${Math.round(flag.bpm)} bpm`);
        if (flag.temperature != null) parts.push(`${flag.temperature.toFixed(1)} °C`);
        if (flag.step_count != null) parts.push(`${flag.step_count} steps`);
        if (flag.limp === 1) parts.push("limp");
        if (flag.asymmetry != null) parts.push(`asymmetry ${flag.asymmetry.toFixed(2)}`);
        metricsEl.textContent = parts.join(" • ") || "No sensor context available";
    }

    if (descEl) {
        descEl.textContent = flag.description || "No additional description.";
    }

    if (insightsEl) {
        insightsEl.innerHTML = "";
        const insights = buildInsightsForFlag(flag);
        insights.forEach(text => {
            const li = document.createElement("li");
            li.textContent = text;
            insightsEl.appendChild(li);
        });
    }
}

async function loadFlagsSummary() {
    try {
        const res = await fetch("/flags-summary");
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        if (!Array.isArray(data)) {
            throw new Error("Unexpected flags-summary payload");
        }
        dashboardState.flags = data;
        renderFlagsTable();
        if (!dashboardState.selectedFlag && data.length > 0) {
            selectFlag(data[0]);
        }
    } catch (err) {
        console.error("Error loading flags summary", err);
        const tbody = document.getElementById("flagsTableBody");
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-danger">Failed to load incidents</td></tr>';
        }
    }
}

function initTimeWindowButtons() {
    const buttons = document.querySelectorAll('[data-window]');
    buttons.forEach(btn => {
        btn.addEventListener("click", () => {
            buttons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const value = parseInt(btn.getAttribute("data-window"), 10);
            if (!Number.isNaN(value)) {
                currentTimeWindowSeconds = value;
                updateChart();
            }
        });
    });
}

// Initialisation
initTimeWindowButtons();
updateChart();
updateFlags();
loadFlagsSummary();

setInterval(updateChart, 3000);
setInterval(updateFlags, 10000);
setInterval(loadFlagsSummary, 10000);