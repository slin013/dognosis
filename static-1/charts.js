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

    const bpm = latestSample.heart_rate ?? latestSample.hr ?? latestSample[1];
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
            return;
        }

        // Assume each row has a Unix timestamp in seconds; support both object and array shapes.
        const nowSec = Math.floor(Date.now() / 1000);
        const filtered = data.filter(sample => {
            const ts = sample.timestamp ?? sample[0];
            if (!ts) return false;
            return ts >= nowSec - currentTimeWindowSeconds;
        });

        const timestamps = filtered.map(sample => {
            const ts = sample.timestamp ?? sample[0];
            return new Date(ts * 1000).toLocaleTimeString();
        });

        const heartRates = filtered.map(sample => {
            return sample.heart_rate ?? sample.hr ?? sample[1];
        });

        hrChart.data.labels = timestamps.reverse();
        hrChart.data.datasets[0].data = heartRates.reverse();
        hrChart.update();

        const latestSample = filtered[filtered.length - 1] || data[data.length - 1];
        updateHeartRateCard(latestSample);

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
            const label = row.label ?? row.type ?? row[2] ?? "Flag";
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
                    // For now, navigate to the JSON view; can be upgraded to a modal with charts.
                    window.location.href = `/flag/${id}`;
                });
            }

            listEl.appendChild(li);
        });
    } catch (err) {
        console.error("Error loading flags", err);
        listEl.innerHTML = '<li class="list-group-item text-danger">Failed to load flags</li>';
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

setInterval(updateChart, 3000);
setInterval(updateFlags, 10000);