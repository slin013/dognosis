// Minimal charts/UI script for environments where the server isn't configured
// to expose `/static-1/`.
//
// Expects the same DOM ids as `templates/index.html`:
// - hrChart
// - hrCardValue, hrCardStatus
// - activityCardValue, activityCardStatus
// - tempCardValue, tempCardStatus
// - flagsList

const LIVE_DATA_TIMEOUT_MS = 5000;
const SAMPLE_STALE_AFTER_SEC = 12;

let updateChartInFlight = false;

async function fetchJson(url, timeoutMs = LIVE_DATA_TIMEOUT_MS) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
        const response = await fetch(url, { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
        return await response.json();
    } finally {
        window.clearTimeout(timeoutId);
    }
}

let hrChart = null;
let stepsChart = null;
let tempChart = null;
let currentTimeWindowSeconds = 1800; // default 30 min

// Activity: rolling window for steps/min (placeholder thresholds — tune later)
const ACTIVITY_ROLLING_WINDOW_SEC = 90; // ~1.5 min (try 60–120)
const ACTIVITY_LOW_STEPS_PER_MIN = 8;
const ACTIVITY_HIGH_STEPS_PER_MIN = 35;

// Temperature (°F) — matches logger display
const TEMP_F_LOW_MAX = 65;
const TEMP_F_HIGH_MIN = 104;

// Dog profile → predicted HR (must match templates/index.html dog profile script)
const DOG_PROFILE_STORAGE_KEY = "dogProfile";
const HR_PRED_MEAN = 114;
const HR_PRED_MEAN_WEIGHT_KG = 19.3;
const HR_PRED_WEIGHT_SLOPE = -0.21;
const HR_PRED_AGE_PER_DAY = 0.002;
/** Typical daily band vs predicted baseline (same as profile “ideal typical daily” placeholders) */
const HR_STATUS_LOW_BELOW_PRED = 15;
const HR_STATUS_HIGH_ABOVE_PRED = 35;

const HR_PRED_BREED_COEFFS = {
    border_collie: -7.777,
    ckcs: 13.822,
    golden_retriever: -6.152,
    labrador_retriever: -5.356,
    springer_spaniel: -6.735,
    staffordshire_bull_terrier: 5.556,
    west_highland_white_terrier: -6.0,
    yorkshire_terrier: 14.178,
};

function parseDobAsLocalMidnightDog(dobStr) {
    if (!dobStr) return null;
    const parts = String(dobStr).split("-");
    if (parts.length !== 3) return null;
    const year = Number(parts[0]);
    const month = Number(parts[1]);
    const day = Number(parts[2]);
    if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) return null;
    const d = new Date(year, month - 1, day);
    if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) return null;
    return d;
}

function ageDaysFromDobStrDog(dobStr) {
    const dobDate = parseDobAsLocalMidnightDog(dobStr);
    if (!dobDate) return null;
    const today = new Date();
    const todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    if (dobDate > todayMidnight) return null;
    return Math.floor((todayMidnight - dobDate) / 86400000);
}

function migrateLegacyDogProfile(profile) {
    if (!profile || typeof profile !== "object") return profile;
    if (!profile.dogBreedSelect && profile.dogBreed) {
        profile.dogBreedSelect = "other";
        profile.dogBreedOther = String(profile.dogBreed || "").trim();
        delete profile.dogBreed;
    }
    return profile;
}

function getDogProfileForHr() {
    try {
        const raw = localStorage.getItem(DOG_PROFILE_STORAGE_KEY);
        if (!raw) return null;
        return migrateLegacyDogProfile(JSON.parse(raw));
    } catch (e) {
        return null;
    }
}

function computePredictedHrFromProfile(profile) {
    if (!profile) return null;
    const w = profile.dogWeightKg;
    if (w == null || !Number.isFinite(Number(w)) || Number(w) <= 0) return null;

    let hr = HR_PRED_MEAN + HR_PRED_WEIGHT_SLOPE * (Number(w) - HR_PRED_MEAN_WEIGHT_KG);

    const ageDays = ageDaysFromDobStrDog(profile.dogDateOfBirth);
    if (ageDays != null && ageDays >= 0) {
        hr += HR_PRED_AGE_PER_DAY * ageDays;
    }

    const sel = profile.dogBreedSelect;
    if (sel && sel !== "other" && Object.prototype.hasOwnProperty.call(HR_PRED_BREED_COEFFS, sel)) {
        hr += HR_PRED_BREED_COEFFS[sel];
    }

    hr = Math.max(45, Math.min(220, hr));
    return Math.round(hr * 10) / 10;
}
// Flags & Insights state for the fallback UI
const dashboardState = {
    deviceFlags: [],
    userFlags: [],
    selectedFlag: null,
    // `selectedFlagTypes === null` means "show all flag types".
    availableFlagTypes: [],
    selectedFlagTypes: null,
    _flagTypeFilterTypesKey: "",
    _flagTypeFilterHandlerAttached: false,
    // Tracks which flag currently has incident data loaded in the table.
    incidentDataLoadedForFlagId: null,
};
let incidentDataRequestToken = 0;

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

function setLastUpdated(latestSampleTsSeconds = null, latestSampleAgeSec = null) {
    const el = document.getElementById("lastUpdatedText");
    if (!el) return;
    const now = new Date();
    if (latestSampleTsSeconds == null || !Number.isFinite(Number(latestSampleTsSeconds))) {
        el.textContent = `Updated at ${now.toLocaleTimeString()}`;
        return;
    }

    const latestStr = new Date(Number(latestSampleTsSeconds) * 1000).toLocaleTimeString();
    const ageStr =
        latestSampleAgeSec == null || !Number.isFinite(Number(latestSampleAgeSec))
            ? ""
            : ` (${Math.floor(Number(latestSampleAgeSec))}s ago)`;
    el.textContent = `Updated at ${now.toLocaleTimeString()} • Latest sample: ${latestStr}${ageStr}`;
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

    const profile = getDogProfileForHr();
    const predicted = computePredictedHrFromProfile(profile);

    let statusText = "Normal";
    let badgeClass = "badge bg-success";

    if (predicted != null) {
        const lowBelow = predicted - HR_STATUS_LOW_BELOW_PRED;
        const highAbove = predicted + HR_STATUS_HIGH_ABOVE_PRED;
        if (rounded < lowBelow) {
            statusText = "Low";
            badgeClass = "badge bg-warning text-dark";
        } else if (rounded > highAbove) {
            statusText = "High";
            badgeClass = "badge bg-danger";
        } else {
            statusText = "Normal";
            badgeClass = "badge bg-success";
        }
    } else {
        if (rounded < 50) {
            statusText = "Low";
            badgeClass = "badge bg-warning text-dark";
        } else if (rounded > 140) {
            statusText = "High";
            badgeClass = "badge bg-danger";
        }
    }

    statusEl.textContent = statusText;
    statusEl.className = badgeClass;
}

function computeStepsPerMinute(samples, windowSec) {
    if (!Array.isArray(samples) || samples.length === 0) return null;
    const nowSec = Math.floor(Date.now() / 1000);
    const cutoff = nowSec - windowSec;
    const pts = samples
        .map((s) => ({
            ts: s.timestamp ?? s[0],
            steps: s.step_count ?? s.steps ?? s[4],
        }))
        .filter(
            (p) =>
                p.ts != null &&
                p.steps != null &&
                Number.isFinite(Number(p.steps)) &&
                p.ts >= cutoff
        )
        .sort((a, b) => a.ts - b.ts);
    if (pts.length < 2) return null;
    const first = pts[0];
    const last = pts[pts.length - 1];
    const delta = Number(last.steps) - Number(first.steps);
    const dur = last.ts - first.ts;
    if (dur <= 0) return null;
    return Math.max(0, (Math.max(0, delta) / dur) * 60);
}

function updateActivityTempCards(latestSample, allSamples) {
    const actEl = document.getElementById("activityCardValue");
    const actStatus = document.getElementById("activityCardStatus");
    const tempEl = document.getElementById("tempCardValue");
    const tempStatus = document.getElementById("tempCardStatus");

    if (!latestSample) {
        if (actEl) actEl.textContent = "--";
        if (actStatus) {
            actStatus.textContent = "No data";
            actStatus.className = "badge bg-secondary mb-3";
        }
        if (tempEl) tempEl.textContent = "-- °F";
        if (tempStatus) {
            tempStatus.textContent = "No data";
            tempStatus.className = "badge bg-secondary mb-3";
        }
        return;
    }

    const steps = latestSample.step_count ?? latestSample[4];
    // steps/min used only for badge classification (UI shows total steps only)
    const stepsPerMin = computeStepsPerMinute(allSamples, ACTIVITY_ROLLING_WINDOW_SEC);

    if (actEl) {
        actEl.textContent = steps != null ? String(steps) : "--";
    }
    if (actStatus) {
        if (stepsPerMin == null) {
            actStatus.textContent = "Collecting";
            actStatus.className = "badge bg-secondary mb-3";
        } else if (stepsPerMin < ACTIVITY_LOW_STEPS_PER_MIN) {
            actStatus.textContent = "Resting";
            actStatus.className = "badge bg-warning text-dark mb-3";
        } else if (stepsPerMin > ACTIVITY_HIGH_STEPS_PER_MIN) {
            actStatus.textContent = "High activity";
            actStatus.className = "badge bg-danger mb-3";
        } else {
            actStatus.textContent = "Moderate activity";
            actStatus.className = "badge bg-success mb-3";
        }
    }

    const t = latestSample.temperature ?? latestSample[2];
    if (tempEl) {
        if (t != null && !Number.isNaN(Number(t))) {
            const n = Number(t);
            tempEl.textContent = `${n.toFixed(1)} °F`;
        } else {
            tempEl.textContent = "-- °F";
        }
    }
    if (tempStatus) {
        if (t == null || Number.isNaN(Number(t))) {
            tempStatus.textContent = "No data";
            tempStatus.className = "badge bg-secondary mb-3";
        } else {
            const n = Number(t);
            if (n < TEMP_F_LOW_MAX) {
                tempStatus.textContent = "Low";
                tempStatus.className = "badge bg-warning text-dark mb-3";
            } else if (n > TEMP_F_HIGH_MIN) {
                tempStatus.textContent = "High";
                tempStatus.className = "badge bg-danger mb-3";
            } else {
                tempStatus.textContent = "Normal";
                tempStatus.className = "badge bg-success mb-3";
            }
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

    // Steps chart (optional canvas)
    const stepsCanvas = document.getElementById("stepsChart");
    if (stepsCanvas) {
        stepsChart = new Chart(stepsCanvas.getContext("2d"), {
            type: "line",
            data: {
                labels: [],
                datasets: [
                    {
                        label: "Steps",
                        data: [],
                        borderWidth: 2,
                        borderColor: "rgba(25, 135, 84, 1)",
                        backgroundColor: "rgba(25, 135, 84, 0.08)",
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
                    x: { ticks: { autoSkip: true, maxTicksLimit: 8 } },
                    y: { beginAtZero: false },
                },
            },
        });
    }

    // Temperature chart (optional canvas)
    const tempCanvas = document.getElementById("tempChart");
    if (tempCanvas) {
        tempChart = new Chart(tempCanvas.getContext("2d"), {
            type: "line",
            data: {
                labels: [],
                datasets: [
                    {
                        label: "Temperature",
                        data: [],
                        borderWidth: 2,
                        borderColor: "rgba(255, 193, 7, 1)",
                        backgroundColor: "rgba(255, 193, 7, 0.10)",
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
                    x: { ticks: { autoSkip: true, maxTicksLimit: 8 } },
                    y: { beginAtZero: false },
                },
            },
        });
    }
}

function mapFlagTypeToLabel(flagType) {
    if (!flagType) return "Flag";
    if (flagType === "Emotional Distress") return "Emotional distress";
    return String(flagType).replace(/_/g, " ");
}

function formatMaybeNumber(value, digits = 1) {
    if (value == null) return "--";
    const n = Number(value);
    if (!Number.isFinite(n)) return "--";
    return n.toFixed(digits);
}

function formatIncidentTimestamp(ts, fallbackDatetime) {
    if (ts != null) {
        return new Date(Number(ts) * 1000).toLocaleString();
    }
    if (fallbackDatetime) return String(fallbackDatetime);
    return "--";
}

function renderIncidentDataRows(samples) {
    const tbody = document.getElementById("flagIncidentDataBody");
    const emptyEl = document.getElementById("flagIncidentDataEmpty");
    const loadingEl = document.getElementById("flagIncidentDataLoading");
    if (!tbody || !emptyEl || !loadingEl) return;

    loadingEl.classList.add("d-none");
    tbody.innerHTML = "";

    if (!Array.isArray(samples) || samples.length === 0) {
        emptyEl.classList.remove("d-none");
        tbody.innerHTML =
            '<tr><td colspan="6" class="text-muted">No samples in this window</td></tr>';
        return;
    }

    emptyEl.classList.add("d-none");
    samples.forEach((sample) => {
        const tr = document.createElement("tr");

        const timeCell = document.createElement("td");
        timeCell.textContent = formatIncidentTimestamp(sample.timestamp, sample.datetime);

        const bpmCell = document.createElement("td");
        bpmCell.textContent = formatMaybeNumber(sample.bpm, 0);

        const tempCell = document.createElement("td");
        tempCell.textContent = formatMaybeNumber(sample.temperature, 1);

        const stepsCell = document.createElement("td");
        stepsCell.textContent = sample.step_count != null ? String(sample.step_count) : "--";

        const limpCell = document.createElement("td");
        limpCell.textContent = sample.limp === 1 ? "Yes" : "No";

        const asymCell = document.createElement("td");
        asymCell.textContent = formatMaybeNumber(sample.asymmetry, 2);

        tr.appendChild(timeCell);
        tr.appendChild(bpmCell);
        tr.appendChild(tempCell);
        tr.appendChild(stepsCell);
        tr.appendChild(limpCell);
        tr.appendChild(asymCell);
        tbody.appendChild(tr);
    });
}

async function loadIncidentDataForFlag(flag) {
    const tbody = document.getElementById("flagIncidentDataBody");
    const emptyEl = document.getElementById("flagIncidentDataEmpty");
    const loadingEl = document.getElementById("flagIncidentDataLoading");
    if (!tbody || !emptyEl || !loadingEl) return;

    if (!flag || flag.id == null) {
        loadingEl.classList.add("d-none");
        emptyEl.classList.add("d-none");
        tbody.innerHTML = '<tr><td colspan="6" class="text-muted">Select an incident</td></tr>';
        return;
    }

    const thisRequestToken = ++incidentDataRequestToken;
    loadingEl.classList.remove("d-none");
    emptyEl.classList.add("d-none");
    tbody.innerHTML = '<tr><td colspan="6" class="text-muted">Loading...</td></tr>';

    try {
        const payload = await fetchJson(`/incident-context/${flag.id}?window_minutes=15`);
        if (thisRequestToken !== incidentDataRequestToken) return;
        renderIncidentDataRows(payload.samples || []);
        dashboardState.incidentDataLoadedForFlagId =
            flag && flag.id != null ? Number(flag.id) : null;
    } catch (err) {
        if (thisRequestToken !== incidentDataRequestToken) return;
        loadingEl.classList.add("d-none");
        emptyEl.classList.add("d-none");
        tbody.innerHTML =
            '<tr><td colspan="6" class="text-danger">Failed to load incident data</td></tr>';
    }
}

function resetIncidentDataTableForSelection() {
    const tbody = document.getElementById("flagIncidentDataBody");
    const emptyEl = document.getElementById("flagIncidentDataEmpty");
    const loadingEl = document.getElementById("flagIncidentDataLoading");
    if (!tbody || !emptyEl || !loadingEl) return;

    loadingEl.classList.add("d-none");
    emptyEl.classList.add("d-none");
    dashboardState.incidentDataLoadedForFlagId = null;
    tbody.innerHTML =
        '<tr><td colspan="6" class="text-muted">Click “Load / refresh incident data” to fetch samples for this incident.</td></tr>';
}

function renderFlagDetail() {
    const emptyEl = document.getElementById("flagDetailEmpty");
    const contentEl = document.getElementById("flagDetailContent");
    if (!emptyEl || !contentEl) return; // element not present in some layouts

    const flag = dashboardState.selectedFlag;
    if (!flag) {
        emptyEl.classList.remove("d-none");
        contentEl.classList.add("d-none");
        dashboardState.incidentDataLoadedForFlagId = null;
        return;
    }

    emptyEl.classList.add("d-none");
    contentEl.classList.remove("d-none");

    const timeEl = document.getElementById("flagDetailTime");
    const typeEl = document.getElementById("flagDetailType");
    const metricsEl = document.getElementById("flagDetailMetrics");
    const descEl = document.getElementById("flagDetailDescription");

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
        if (flag.temperature != null) {
            const n = Number(flag.temperature);
            if (Number.isFinite(n)) parts.push(`${n.toFixed(1)} °F`);
        }
        if (flag.step_count != null) parts.push(`${flag.step_count} steps`);
        if (flag.limp === 1) parts.push("limp");
        if (flag.asymmetry != null) parts.push(`asym ${Number(flag.asymmetry).toFixed(2)}`);
        metricsEl.textContent = parts.join(" • ") || "No sensor context available";
    }

    if (descEl) {
        descEl.textContent = flag.description || "No additional description.";
    }

    // Do not auto-load incident context; wait for explicit user action.
    // Also, avoid clearing the table on background refreshes if we already
    // loaded data for this flag.
    const currentLoadedId =
        dashboardState.incidentDataLoadedForFlagId != null
            ? Number(dashboardState.incidentDataLoadedForFlagId)
            : null;
    const thisFlagId = flag && flag.id != null ? Number(flag.id) : null;
    if (currentLoadedId !== thisFlagId) {
        resetIncidentDataTableForSelection();
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
        if (flag.temperature != null) {
            const n = Number(flag.temperature);
            if (Number.isFinite(n)) parts.push(`${n.toFixed(1)} °F`);
        }
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

function initIncidentDataLoadButton() {
    const btn = document.getElementById("loadIncidentDataButton");
    if (!btn) return;
    btn.addEventListener("click", () => {
        const flag = dashboardState.selectedFlag;
        loadIncidentDataForFlag(flag);
    });
}

function ensureFlagTypeFilterUI(deviceFlags) {
    const container = document.getElementById("flagTypeCheckboxes");
    const statusEl = document.getElementById("flagTypeFilterStatus");
    if (!container) return;

    const types = [
        ...new Set(
            (deviceFlags || [])
                .map((f) => (f && f.flag_type != null ? String(f.flag_type) : null))
                .filter((t) => t && t.trim() !== "")
        ),
    ];

    // Sort by display label for a stable, human-friendly order.
    types.sort((a, b) => mapFlagTypeToLabel(a).localeCompare(mapFlagTypeToLabel(b)));
    const typesKey = types.join("|");
    dashboardState.availableFlagTypes = types;

    if (dashboardState._flagTypeFilterTypesKey !== typesKey) {
        container.innerHTML = "";

        if (types.length === 0) {
            container.innerHTML =
                '<div class="text-muted small">No device flags available for filtering.</div>';
        } else {
        types.forEach((flagType, idx) => {
            const checkboxId = `flagTypeCheckbox_${idx}`;
            const wrapper = document.createElement("div");
            wrapper.className = "form-check";

            const input = document.createElement("input");
            input.type = "checkbox";
            input.className = "form-check-input";
            input.id = checkboxId;
            input.dataset.flagType = flagType;
            input.checked = dashboardState.selectedFlagTypes == null || dashboardState.selectedFlagTypes.has(flagType);

            const label = document.createElement("label");
            label.className = "form-check-label";
            label.htmlFor = checkboxId;
            label.textContent = mapFlagTypeToLabel(flagType);

            wrapper.appendChild(input);
            wrapper.appendChild(label);
            container.appendChild(wrapper);
        });
        }

        dashboardState._flagTypeFilterTypesKey = typesKey;
    }

    // Attach event handler once (event delegation via `change` bubbling).
    if (!dashboardState._flagTypeFilterHandlerAttached) {
        container.addEventListener("change", (ev) => {
            const target = ev.target;
            if (!(target instanceof HTMLInputElement)) return;
            if (!target.matches('input[data-flag-type]')) return;

            const inputs = container.querySelectorAll('input[type="checkbox"][data-flag-type]');
            const checkedTypes = [];
            inputs.forEach((inp) => {
                if (inp.checked) checkedTypes.push(String(inp.dataset.flagType || ""));
            });

            // If everything is checked, switch back to "show all".
            if (dashboardState.availableFlagTypes.length > 0 && checkedTypes.length === dashboardState.availableFlagTypes.length) {
                dashboardState.selectedFlagTypes = null;
            } else {
                dashboardState.selectedFlagTypes = new Set(checkedTypes);
            }

            applyFlagTypeFilterAndRender();
        });
        dashboardState._flagTypeFilterHandlerAttached = true;
    }

    if (statusEl) {
        if (dashboardState.selectedFlagTypes == null) {
            statusEl.textContent = dashboardState.availableFlagTypes.length
                ? `All (${dashboardState.availableFlagTypes.length})`
                : "No device flag types";
        } else {
            statusEl.textContent = `Selected (${dashboardState.selectedFlagTypes.size})`;
        }
    }
}

function applyFlagTypeFilterAndRender() {
    const deviceTbody = document.getElementById("deviceFlagsTableBody");
    const userTbody = document.getElementById("userFlagsTableBody");
    if (!deviceTbody || !userTbody) return;

    const selectedTypes = dashboardState.selectedFlagTypes;
    const filterFn = (f) => {
        if (!f) return false;
        if (selectedTypes == null) return true;
        const t = f.flag_type != null ? String(f.flag_type) : "";
        return selectedTypes.has(t);
    };

    const deviceFiltered = (dashboardState.deviceFlags || []).filter(filterFn);
    // Per requirement: checkbox filter should ONLY apply to device incidents.
    const userFiltered = dashboardState.userFlags || [];

    // Preserve the server-provided timestamp order by filtering only (no re-sorting).
    renderFlagsTable("deviceFlagsTableBody", deviceFiltered);
    renderFlagsTable("userFlagsTableBody", userFiltered);

    // Ensure the selected incident is still visible after filtering.
    const selectedId =
        dashboardState.selectedFlag && dashboardState.selectedFlag.id != null
            ? String(dashboardState.selectedFlag.id)
            : null;

    let nextSelected =
        selectedId != null
            ? [...deviceFiltered, ...userFiltered].find((f) => String(f.id) === selectedId)
            : null;

    if (!nextSelected) {
        nextSelected = deviceFiltered[0] || userFiltered[0] || null;
    }

    dashboardState.selectedFlag = nextSelected;
    highlightSelectedFlag();
    renderFlagDetail();
}

async function loadFlagsSummary() {
    try {
        const data = await fetchJson("/flags-summary");
        if (!Array.isArray(data)) throw new Error("Unexpected flags-summary payload");

        const deviceFlags = data.filter((f) => Number(f.is_user_generated) === 0);
        const userFlags = data.filter((f) => Number(f.is_user_generated) === 1);

        dashboardState.deviceFlags = deviceFlags;
        dashboardState.userFlags = userFlags;

        // If we have a selected flag, try to resolve it to the latest full object from the DB.
        const selectedId =
            dashboardState.selectedFlag && dashboardState.selectedFlag.id != null
                ? String(dashboardState.selectedFlag.id)
                : null;
        if (selectedId) {
            const match = [...deviceFlags, ...userFlags].find((f) => String(f.id) === selectedId);
            dashboardState.selectedFlag = match || null;
        }

        ensureFlagTypeFilterUI(deviceFlags);
        applyFlagTypeFilterAndRender();
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
    if (updateChartInFlight) return;
    updateChartInFlight = true;
    try {
        const data = await fetchJson("/live-data");

        if (!Array.isArray(data) || data.length === 0) {
            if (hrChart) {
                hrChart.data.labels = [];
                hrChart.data.datasets[0].data = [];
                hrChart.update();
            }
            if (stepsChart) {
                stepsChart.data.labels = [];
                stepsChart.data.datasets[0].data = [];
                stepsChart.update();
            }
            if (tempChart) {
                tempChart.data.labels = [];
                tempChart.data.datasets[0].data = [];
                tempChart.update();
            }
            setConnectionStatus(false);
            setLastUpdated();
            updateHeartRateCard(null);
            updateActivityTempCards(null, null);
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

        if (stepsChart) {
            const steps = chronological.map((s) => s.step_count ?? s.steps ?? s[4]);
            stepsChart.data.labels = timestamps;
            stepsChart.data.datasets[0].data = steps;
            stepsChart.update();
        }

        if (tempChart) {
            const temps = chronological.map((s) => s.temperature ?? s.temp ?? s[2]);
            tempChart.data.labels = timestamps;
            tempChart.data.datasets[0].data = temps;
            tempChart.update();
        }

        const latestSample = data[0];
        updateHeartRateCard(latestSample);
        updateActivityTempCards(latestSample, data);

        const latestTs = latestSample?.timestamp ?? latestSample?.[0];
        const latestAgeSec =
            latestTs != null && Number.isFinite(Number(latestTs)) ? nowSec - Math.floor(Number(latestTs)) : null;

        const isFresh = latestAgeSec == null ? true : latestAgeSec <= SAMPLE_STALE_AFTER_SEC;
        setConnectionStatus(isFresh);
        setLastUpdated(latestTs, latestAgeSec);
    } catch (err) {
        console.error("Error updating chart", err);
        setConnectionStatus(false);
        setLastUpdated();
    } finally {
        updateChartInFlight = false;
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
    initIncidentDataLoadButton();
    updateChart();
    updateFlags();
    loadFlagsSummary();
    setInterval(updateChart, 3000);
    setInterval(updateFlags, 10000);
    setInterval(loadFlagsSummary, 10000);
}

start();

