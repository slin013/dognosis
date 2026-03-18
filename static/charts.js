// Minimal charts/UI script for environments where the server isn't configured
// to expose `/static-1/`.
//
// Expects the same DOM ids as `templates/index.html`:
// - hrChart
// - hrCardValue, hrCardStatus
// - activityCardValue, activityCardStatus
// - tempCardValue, tempCardStatus
// - flagsList

async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
    return response.json();
}

let hrChart = null;
let currentTimeWindowSeconds = 1800; // default 30 min

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
    el.textContent = `Updated at ${new Date().toLocaleTimeString()}`;
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

function updateActivityTempCards(latestSample) {
    const actEl = document.getElementById("activityCardValue");
    const actStatus = document.getElementById("activityCardStatus");
    const tempEl = document.getElementById("tempCardValue");
    const tempStatus = document.getElementById("tempCardStatus");

    if (!latestSample) {
        if (actEl) actEl.textContent = "--";
        if (tempEl) tempEl.textContent = "--";
        return;
    }

    const steps = latestSample.step_count ?? latestSample[4];
    if (actEl) actEl.textContent = steps != null ? String(steps) : "--";
    if (actStatus) actStatus.textContent = "Total steps";

    const t = latestSample.temperature ?? latestSample[2];
    if (tempEl) {
        if (t != null && !Number.isNaN(Number(t))) {
            const n = Number(t);
            tempEl.textContent = `${n.toFixed(1)}°`;
            if (tempStatus) tempStatus.textContent = "Temp";
        } else {
            tempEl.textContent = "--";
        }
    }
}

function initChart() {
    const canvas = document.getElementById("hrChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    hrChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "Heart Rate",
                    data: [],
                    borderWidth: 2,
                    borderColor: "rgba(220, 53, 69, 1)",
                    backgroundColor: "rgba(220, 53, 69, 0.08)",
                    tension: 0.25,
                    pointRadius: 0,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true },
                tooltip: { mode: "index", intersect: false },
            },
            scales: {
                x: {
                    ticks: { autoSkip: true, maxTicksLimit: 8 },
                },
                y: { beginAtZero: false },
            },
        },
    });
}

async function updateChart() {
    try {
        const data = await fetchJson("/live-data");

        if (!Array.isArray(data) || data.length === 0) {
            if (hrChart) {
                hrChart.data.labels = [];
                hrChart.data.datasets[0].data = [];
                hrChart.update();
            }
            setConnectionStatus(true);
            setLastUpdated();
            updateHeartRateCard(null);
            updateActivityTempCards(null);
            return;
        }

        const nowSec = Math.floor(Date.now() / 1000);
        const filtered = data.filter((sample) => {
            const ts = sample.timestamp ?? sample[0];
            return ts != null && ts >= nowSec - currentTimeWindowSeconds;
        });

        const use = filtered.length ? filtered : data;
        const chronological = [...use].reverse(); // DB returns DESC

        const timestamps = chronological.map((s) => {
            const ts = s.timestamp ?? s[0];
            return new Date(ts * 1000).toLocaleTimeString();
        });
        const heartRates = chronological.map(
            (s) => s.bpm ?? s.heart_rate ?? s.hr ?? s[1]
        );

        if (hrChart) {
            hrChart.data.labels = timestamps;
            hrChart.data.datasets[0].data = heartRates;
            hrChart.update();
        }

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
        const data = await fetchJson("/flags");
        if (!Array.isArray(data) || data.length === 0) {
            listEl.innerHTML =
                '<li class="list-group-item text-muted">No flags recorded yet</li>';
            return;
        }

        listEl.innerHTML = "";
        data.forEach((row) => {
            const id = row.id ?? row[0];
            const ts = row.timestamp ?? row[1];
            const label = row.flag_type ?? row.label ?? row.type ?? "Flag";
            const li = document.createElement("li");
            li.className =
                "list-group-item d-flex justify-content-between align-items-center";
            li.style.cursor = "pointer";

            const left = document.createElement("div");
            const title = document.createElement("div");
            title.className = "fw-semibold";
            title.textContent = label;

            const subtitle = document.createElement("small");
            subtitle.className = "text-muted";
            if (ts) subtitle.textContent = new Date(ts * 1000).toLocaleString();
            else subtitle.textContent = "";

            left.appendChild(title);
            left.appendChild(subtitle);

            const badge = document.createElement("span");
            badge.className = "badge bg-secondary";
            badge.textContent = row.flag_type ? String(row.flag_type) : "Flag";

            li.appendChild(left);
            li.appendChild(badge);

            if (id != null) {
                li.addEventListener("click", () => {
                    window.location.href = `/flag/${id}`;
                });
            }
            listEl.appendChild(li);
        });
    } catch (err) {
        console.error("Error loading flags", err);
        listEl.innerHTML =
            '<li class="list-group-item text-danger">Failed to load flags</li>';
    }
}

function initTimeWindowButtons() {
    const buttons = document.querySelectorAll("[data-window]");
    buttons.forEach((btn) => {
        btn.addEventListener("click", () => {
            buttons.forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            const value = parseInt(btn.getAttribute("data-window"), 10);
            if (!Number.isNaN(value)) {
                currentTimeWindowSeconds = value;
                updateChart();
            }
        });
    });
}

function start() {
    initChart();
    initTimeWindowButtons();
    updateChart();
    updateFlags();
    setInterval(updateChart, 3000);
    setInterval(updateFlags, 10000);
}

start();

