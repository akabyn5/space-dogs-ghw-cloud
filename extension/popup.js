// =============================================================================
// ELEMENT REFERENCES
// =============================================================================
const output           = document.getElementById("output");
const connectionStatus = document.getElementById("connection-status");
const timestampDisplay = document.getElementById("timestamp-display");


// =============================================================================
// APP STATE
// =============================================================================
const state = {
  status:  "idle",   // "idle" | "loading" | "success" | "error"
  records: [],       // last successful array of up to 5 records
  error:   null,
};


// =============================================================================
// STATUS CLASSIFIERS  (pure functions — input in, descriptor out)
// Thresholds live here and nowhere else; change one place, update everywhere.
// =============================================================================

function classifyTemperature(temp) {
  if (temp > 80) return { cls: "critical", icon: "🔴", label: "CRIT" };
  if (temp > 60) return { cls: "warning",  icon: "🟡", label: "WARN" };
  return           { cls: "nominal",  icon: "🟢", label: "NOM"  };
}

function classifyBattery(level) {
  if (level < 20) return { cls: "critical", icon: "🔴", label: "CRIT" };
  if (level < 50) return { cls: "warning",  icon: "🟡", label: "WARN" };
  return           { cls: "nominal",  icon: "🟢", label: "OK"   };
}

function classifySignal(strength) {
  if (strength < 30) return { cls: "critical", icon: "🔴", label: "WEAK"   };
  if (strength < 70) return { cls: "warning",  icon: "🟡", label: "FAIR"   };
  return              { cls: "nominal",  icon: "🟢", label: "STRONG" };
}

function classifySystem(status) {
  if (status === "critical") return { cls: "critical", icon: "🔴" };
  if (status === "warning")  return { cls: "warning",  icon: "🟡" };
  return                      { cls: "nominal",  icon: "🟢" };
}

// Converts a severity class to its CSS hex colour string.
function severityColor(cls) {
  const map = { critical: "ff3333", warning: "ffcc00", nominal: "00ff88" };
  return `#${map[cls] ?? "8899aa"}`;
}


// =============================================================================
// RENDERING HELPERS
// =============================================================================

/** Formats a JS Date as HH:MM:SS. */
function formatTime(date) {
  return date.toLocaleTimeString([], {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

/**
 * Renders a single value cell for the history table.
 * The text colour is driven by the severity class so the table is
 * "heatmap-like" — you can scan it visually without reading every number.
 */
function renderCell(value, unit, cls) {
  return `
    <span class="history-cell" style="color: ${severityColor(cls)};">
      ${value}<span class="history-unit">${unit}</span>
    </span>
  `;
}

/**
 * Renders one history row from a telemetry record object.
 * @param {object} record  — the telemetry payload from the API
 * @param {number} index   — 0 = most recent; used to apply the "latest" badge
 */
function renderHistoryRow(record, index) {
  const time    = formatTime(new Date(record.timestamp));
  const sys     = classifySystem(record.subsystem_status);
  const tempS   = classifyTemperature(record.temperature);
  const batS    = classifyBattery(record.battery_level);
  const sigS    = classifySignal(record.signal_strength);
  const isFirst = index === 0;

  return `
    <div class="history-row ${isFirst ? "history-row--latest" : ""}">

      <!-- Sequence badge: "LATEST" for the newest, or a dim record number -->
      <div class="history-seq">
        ${isFirst
          ? `<span class="latest-badge">NEW</span>`
          : `<span class="seq-num">#${index + 1}</span>`}
      </div>

      <!-- Timestamp -->
      <div class="history-time">${time}</div>

      <!-- Sensor readings, each coloured by severity -->
      <div class="history-metrics">
        ${renderCell(record.temperature,     "°", tempS.cls)}
        ${renderCell(record.battery_level,   "%", batS.cls)}
        ${renderCell(record.signal_strength, "%", sigS.cls)}
      </div>

      <!-- System status icon -->
      <div class="history-status" title="${record.subsystem_status.toUpperCase()}">
        <span class="sys-icon">${sys.icon}</span>
        <span class="sys-label ${sys.cls}">${record.subsystem_status.toUpperCase()}</span>
      </div>

    </div>
  `;
}

/**
 * Renders the full history list: a sticky column-header row + N data rows.
 * The header uses short labels so everything fits in 320 px.
 */
function renderHistory(records) {
  const latestTime = formatTime(new Date(records[0].timestamp));

  output.innerHTML = `

    <!-- Column header row -->
    <div class="history-header">
      <div class="history-seq"></div>
      <div class="history-time">TIME</div>
      <div class="history-metrics">
        <span>TEMP</span>
        <span>BAT</span>
        <span>SIG</span>
      </div>
      <div class="history-status">STATUS</div>
    </div>

    <!-- Data rows (newest at top, index 0 = most recent) -->
    ${records.map((r, i) => renderHistoryRow(r, i)).join("")}

    <!-- Record count caption -->
    <div class="history-caption">
      Showing ${records.length} most recent readings
    </div>
  `;

  // Restore the connection status indicator.
  connectionStatus.textContent = "●";
  connectionStatus.classList.remove("offline");
  connectionStatus.style.animation = "none";
  timestampDisplay.textContent = latestTime;
}


// =============================================================================
// LOADING STATE
// =============================================================================
function renderLoading() {
  output.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <div class="loading-text">Fetching telemetry history…</div>
    </div>
    <style>
      .spinner {
        width: 32px; height: 32px;
        border: 3px solid rgba(0,255,204,0.15);
        border-top-color: #00ffcc;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
        margin: 0 auto 12px;
      }
      @keyframes spin { to { transform: rotate(360deg); } }
    </style>
  `;
  connectionStatus.style.animation = "pulse 1.2s ease-in-out infinite";
}


// =============================================================================
// ERROR STATE
// =============================================================================
function renderError(message, isOffline = false) {
  const heading = isOffline ? "API Connection Lost" : "No Data Available";
  const hint    = isOffline
    ? "Make sure the local server is running on port 5000."
    : "The server responded but returned no valid telemetry.";

  output.innerHTML = `
    <div class="error-state">
      <div class="error-icon">${isOffline ? "✕" : "⚠"}</div>
      <div class="error-heading">${heading}</div>
      <div class="error-hint">${hint}</div>
      ${message ? `<div class="error-detail">${message}</div>` : ""}
      <button class="retry-btn" onclick="loadTelemetry()">↻ Retry</button>
    </div>
  `;

  connectionStatus.textContent = "●";
  connectionStatus.classList.add("offline");
  connectionStatus.style.animation = "none";
}


// =============================================================================
// DATA LAYER
// Calls /telemetry/history?limit=5 and hands the result to renderHistory.
// We also POST a fresh reading first so there's always something new to see.
// =============================================================================
async function loadTelemetry() {
  // Only show the spinner on the very first load — subsequent auto-refreshes
  // update silently so the list doesn't flash on every poll.
  if (state.status !== "success") {
    renderLoading();
  }

  try {
    // Step 1: generate a new telemetry record so each refresh adds fresh data.
    const generateRes = await fetch("http://127.0.0.1:5000/telemetry", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({}),
    });

    if (!generateRes.ok) {
      throw new Error(`Server error ${generateRes.status} on POST /telemetry`);
    }

    // Step 2: fetch the five most recent records from the history endpoint.
    // ?limit=5&page=1 returns the newest records first (server sorts DESC).
    const historyRes = await fetch(
      "http://127.0.0.1:5000/telemetry/history?limit=5&page=1"
    );

    if (!historyRes.ok) {
      throw new Error(`Server error ${historyRes.status} on GET /telemetry/history`);
    }

    const result = await historyRes.json();

    // Step 3: validate the response shape before touching the DOM.
    if (!result.success || !Array.isArray(result.data) || result.data.length === 0) {
      state.status = "error";
      state.error  = "Response contained no telemetry records.";
      renderError(state.error, false);
      return;
    }

    // Step 4: update state and render.
    state.status  = "success";
    state.records = result.data;
    state.error   = null;
    renderHistory(state.records);

  } catch (err) {
    state.status = "error";
    state.error  = err.message;

    // fetch() throws TypeError on network-level failures (server unreachable).
    // Other errors (e.g. bad JSON) are regular Error instances.
    const isOffline = err instanceof TypeError;
    renderError(state.error, isOffline);
    console.error("[Telemetry] Load failed:", err);
  }
}


// =============================================================================
// INIT — load immediately, then poll every 5 seconds.
// =============================================================================
loadTelemetry();
setInterval(loadTelemetry, 5_000);