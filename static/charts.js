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
// Flags & Insights state for the fallback UI
const dashboardState = {
    deviceFlags: [],
    userFlags: [],
    selectedFlag: null,
};

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

function mapFlagTypeToLabel(flagType) {
    if (!flagType) return "Flag";
    return String(flagType).replace(/_/g, " ");
}

function renderFlagDetail() {
    const emptyEl = document.getElementById("flagDetailEmpty");
    const contentEl = document.getElementById("flagDetailContent");
    if (!emptyEl || !contentEl) return; // element not present in some layouts

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
            timeEl.textContent = new Date(flag.timestamp * 1000).toLocaleString();
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
        if (flag.temperature != null) parts.push(`${Number(flag.temperature).toFixed(1)} °C`);
        if (flag.step_count != null) parts.push(`${flag.step_count} steps`);
        if (flag.limp === 1) parts.push("limp");
        if (flag.asymmetry != null) parts.push(`asym ${Number(flag.asymmetry).toFixed(2)}`);
        metricsEl.textContent = parts.join(" • ") || "No sensor context available";
    }

    if (descEl) {
        descEl.textContent = flag.description || "No additional description.";
    }

    // Keep insights simple in this fallback script.
    if (insightsEl) {
        insightsEl.innerHTML = "";
        const li = document.createElement("li");
        li.textContent = "Insights are limited in the fallback UI. (Check the main UI assets if you want full insights.)";
        insightsEl.appendChild(li);
    }
}

function renderFlagsTable(tbodyId, flags) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;

    if (!Array.isArray(flags) || flags.length === 0) {
        tbody.innerHTML =
            '<tr><td colspan="3" class="text-muted">No incidents recorded yet</td></tr>';
        return;
    }

    tbody.innerHTML = "";

    flags.forEach((flag) => {
        const tr = document.createElement("tr");
        if (flag && flag.id != null) tr.dataset.flagId = String(flag.id);
        tr.style.cursor = "pointer";

        const tsCell = document.createElement("td");
        tsCell.textContent = flag.timestamp
            ? new Date(flag.timestamp * 1000).toLocaleString()
            : "Unknown time";

        const typeCell = document.createElement("td");
        typeCell.textContent = mapFlagTypeToLabel(flag.flag_type);

        const detailCell = document.createElement("td");
        const parts = [];
        if (flag.bpm != null) parts.push(`${Math.round(flag.bpm)} bpm`);
        if (flag.temperature != null) parts.push(`${Number(flag.temperature).toFixed(1)} °C`);
        if (flag.step_count != null) parts.push(`${flag.step_count} steps`);
        if (flag.limp === 1) parts.push("limp");
        if (flag.asymmetry != null) parts.push(`asym ${Number(flag.asymmetry).toFixed(2)}`);
        detailCell.textContent = parts.join(" • ") || flag.description || "";

        tr.appendChild(tsCell);
        tr.appendChild(typeCell);
        tr.appendChild(detailCell);

        tr.addEventListener("click", () => {
            dashboardState.selectedFlag = flag;
            highlightSelectedFlag();
            renderFlagDetail();
        });

        // Allow editing/deleting only for user-flagged incidents.
        if (tbodyId === "userFlagsTableBody") {
            tr.addEventListener("dblclick", () => {
                dashboardState.selectedFlag = flag;
                highlightSelectedFlag();
                renderFlagDetail();
                openEditFlagModal(flag);
            });
        }

        tbody.appendChild(tr);
    });
}

function highlightSelectedFlag() {
    const selectedId =
        dashboardState.selectedFlag && dashboardState.selectedFlag.id != null
            ? String(dashboardState.selectedFlag.id)
            : null;

    ["deviceFlagsTableBody", "userFlagsTableBody"].forEach((tbodyId) => {
        const tbody = document.getElementById(tbodyId);
        if (!tbody) return;

        const trs = tbody.querySelectorAll("tr[data-flag-id]");
        trs.forEach((tr) => {
            const isSelected = selectedId != null && tr.dataset.flagId === selectedId;
            tr.classList.toggle("table-info", isSelected);
        });
    });
}

async function loadFlagsSummary() {
    try {
        const data = await fetchJson("/flags-summary");
        if (!Array.isArray(data)) throw new Error("Unexpected flags-summary payload");

        const deviceFlags = data.filter((f) => Number(f.is_user_generated) === 0);
        const userFlags = data.filter((f) => Number(f.is_user_generated) === 1);

        dashboardState.deviceFlags = deviceFlags;
        dashboardState.userFlags = userFlags;

        renderFlagsTable("deviceFlagsTableBody", deviceFlags);
        renderFlagsTable("userFlagsTableBody", userFlags);

        const selectedId =
            dashboardState.selectedFlag && dashboardState.selectedFlag.id != null
                ? String(dashboardState.selectedFlag.id)
                : null;

        if (selectedId) {
            const match = [...deviceFlags, ...userFlags].find((f) => String(f.id) === selectedId);
            if (match) dashboardState.selectedFlag = match;
        }

        if (!dashboardState.selectedFlag) {
            dashboardState.selectedFlag = deviceFlags[0] || userFlags[0] || null;
        }

        highlightSelectedFlag();
        renderFlagDetail();
    } catch (err) {
        console.error("Error loading flags summary", err);
        const dTbody = document.getElementById("deviceFlagsTableBody");
        const uTbody = document.getElementById("userFlagsTableBody");
        if (dTbody) dTbody.innerHTML = '<tr><td colspan="3" class="text-danger">Failed to load incidents</td></tr>';
        if (uTbody) uTbody.innerHTML = '<tr><td colspan="3" class="text-danger">Failed to load incidents</td></tr>';
    }
}

function toDatetimeLocalValue(date) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
        date.getHours()
    )}:${pad(date.getMinutes())}`;
}

function initAddFlagModal() {
    const addFlagButton = document.getElementById("addFlagButton");
    const modalEl = document.getElementById("addFlagModal");
    const saveButton = document.getElementById("saveFlagButton");

    if (!addFlagButton || !modalEl || !saveButton) return; // modal not present on this layout

    const modal = window.bootstrap ? window.bootstrap.Modal.getOrCreateInstance(modalEl) : null;

    const timeInput = document.getElementById("addFlagTime");
    const categorySelect = document.getElementById("addFlagCategory");
    const noteInput = document.getElementById("addFlagNote");

    if (!timeInput || !categorySelect || !noteInput) return;

    addFlagButton.addEventListener("click", () => {
        timeInput.value = toDatetimeLocalValue(new Date());
        noteInput.value = "";
        categorySelect.value = "hr_high";
        if (modal) modal.show();
    });

    saveButton.addEventListener("click", async () => {
        try {
            const dtStr = timeInput.value;
            const ts = Math.floor(new Date(dtStr).getTime() / 1000);
            const flag_type = categorySelect.value;
            const description = noteInput.value || "";

            if (!Number.isFinite(ts)) throw new Error("Invalid date/time");

            const res = await fetch("/flags-add", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ timestamp: ts, flag_type, description }),
            });

            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }

            const out = await res.json().catch(() => ({}));
            if (out && out.flag_id != null) {
                dashboardState.selectedFlag = { id: out.flag_id };
            }

            if (modal) modal.hide();
            await loadFlagsSummary();
        } catch (err) {
            console.error("Failed to add flag", err);
            alert("Failed to add flag. Check the console for details.");
        }
    });
}

function openEditFlagModal(flag) {
    const modalEl = document.getElementById("editFlagModal");
    const editFlagIdInput = document.getElementById("editFlagId");
    const editTimeInput = document.getElementById("editFlagTime");
    const editCategorySelect = document.getElementById("editFlagCategory");
    const editNoteInput = document.getElementById("editFlagNote");

    if (!modalEl || !editFlagIdInput || !editTimeInput || !editCategorySelect || !editNoteInput) {
        return;
    }

    if (!flag) return;

    editFlagIdInput.value = flag.id != null ? String(flag.id) : "";

    if (flag.timestamp != null) {
        const dt = new Date(Number(flag.timestamp) * 1000);
        editTimeInput.value = toDatetimeLocalValue(dt);
    }

    editCategorySelect.value = flag.flag_type || "hr_high";
    editNoteInput.value = flag.description || "";

    const modal = window.bootstrap ? window.bootstrap.Modal.getOrCreateInstance(modalEl) : null;
    if (modal) modal.show();
}

function initEditDeleteFlagModal() {
    const modalEl = document.getElementById("editFlagModal");
    const saveButton = document.getElementById("saveEditFlagButton");
    const deleteButton = document.getElementById("deleteFlagButton");

    if (!modalEl || !saveButton || !deleteButton) return;

    const editFlagIdInput = document.getElementById("editFlagId");
    const editTimeInput = document.getElementById("editFlagTime");
    const editCategorySelect = document.getElementById("editFlagCategory");
    const editNoteInput = document.getElementById("editFlagNote");

    if (!editFlagIdInput || !editTimeInput || !editCategorySelect || !editNoteInput) return;

    saveButton.addEventListener("click", async () => {
        try {
            const id = editFlagIdInput.value;
            const ts = Math.floor(new Date(editTimeInput.value).getTime() / 1000);
            const flag_type = editCategorySelect.value;
            const description = editNoteInput.value || "";

            if (!id) throw new Error("Missing flag id");
            if (!Number.isFinite(ts)) throw new Error("Invalid timestamp");

            const res = await fetch("/flags-update", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id, timestamp: ts, flag_type, description }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const out = await res.json().catch(() => ({}));
            const newId = out && out.flag_id != null ? out.flag_id : null;

            const modal = window.bootstrap
                ? window.bootstrap.Modal.getOrCreateInstance(modalEl)
                : null;
            if (modal) modal.hide();

            if (newId != null) dashboardState.selectedFlag = { id: newId };
            await loadFlagsSummary();
        } catch (err) {
            console.error("Failed to update flag", err);
            alert("Failed to update flag. Check console for details.");
        }
    });

    deleteButton.addEventListener("click", async () => {
        try {
            const id = editFlagIdInput.value;
            if (!id) throw new Error("Missing flag id");

            const ok = confirm("Delete this user-flag? This cannot be undone.");
            if (!ok) return;

            const res = await fetch("/flags-delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id }),
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const modal = window.bootstrap
                ? window.bootstrap.Modal.getOrCreateInstance(modalEl)
                : null;
            if (modal) modal.hide();

            dashboardState.selectedFlag = null;
            await loadFlagsSummary();
        } catch (err) {
            console.error("Failed to delete flag", err);
            alert("Failed to delete flag. Check console for details.");
        }
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
    initAddFlagModal();
    initEditDeleteFlagModal();
    updateChart();
    updateFlags();
    loadFlagsSummary();
    setInterval(updateChart, 3000);
    setInterval(updateFlags, 10000);
    setInterval(loadFlagsSummary, 10000);
}

start();

