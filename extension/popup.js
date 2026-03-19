// =============================================================================
// popup.js — Space Dogs Telemetry Extension
//
// Architecture (each section has one job — see the refactor session for detail):
//
//   CONFIG      — all tunable constants in one place
//   Errors      — typed exceptions so the controller can act on *what* failed
//   Classifiers — pure functions: value in → severity descriptor out
//   Formatters  — pure functions: value in → display string out
//   Cache       — localStorage wrapper; gives instant paint on popup open
//   API         — all network calls; supports AbortController for cancellation
//   Chart       — pure SVG builder; data in → SVG string out
//   Renderer    — pure HTML builders; never touches the DOM directly
//   UI          — the ONLY layer that reads/writes the DOM
//   Controller  — thin orchestrator: API → state → UI, owns all timing logic
// =============================================================================


// ─────────────────────────────────────────────────────────────────────────────
// CONFIG
//
// Two intervals instead of one is the key architectural shift:
//   POLL_INTERVAL_MS     — how often we *read* (check for new data)
//   GENERATE_INTERVAL_MS — how often we *write* (create a new reading)
//
// Reading every 5s but only writing every 30s cuts server write load by 6×
// with no perceptible loss of freshness — a 5-second-old reading still feels
// real-time. The intervals are independent so you can tune them separately.
// ─────────────────────────────────────────────────────────────────────────────

const CONFIG = Object.freeze({
  API_BASE:             "http://127.0.0.1:5000",
  HISTORY_LIMIT:        5,

  // Read cadence — how often the popup checks for updated data.
  POLL_INTERVAL_MS:     5_000,

  // Write cadence — how often the popup asks the server to generate a reading.
  // Deliberately slower than the poll rate so most polls are read-only GETs.
  GENERATE_INTERVAL_MS: 30_000,

  // Error backoff — after consecutive failures, wait progressively longer.
  // Formula: min(MAX_BACKOFF_MS, POLL_INTERVAL_MS × 2^(errorCount − 1))
  // Result:  5s → 10s → 20s → 40s → 60s (capped), then stays at 60s.
  MAX_BACKOFF_MS:       60_000,

  // Session cache — how long localStorage data is considered fresh enough
  // to paint immediately on popup open before a real fetch completes.
  CACHE_MAX_AGE_MS:     60_000,
  CACHE_KEY:            "sd_telemetry_cache",
});


// ─────────────────────────────────────────────────────────────────────────────
// ERRORS
// ─────────────────────────────────────────────────────────────────────────────

/** Thrown when the server is unreachable or returns a non-OK HTTP status. */
class NetworkError extends Error {
  constructor(message) { super(message); this.name = "NetworkError"; }
}

/** Thrown when the server responds but the payload shape is wrong or empty. */
class DataError extends Error {
  constructor(message) { super(message); this.name = "DataError"; }
}


// ─────────────────────────────────────────────────────────────────────────────
// CLASSIFIERS  (pure: value in → severity descriptor out)
// ─────────────────────────────────────────────────────────────────────────────

const Classifiers = Object.freeze({
  temperature(temp) {
    if (temp > 80) return { cls: "critical", icon: "🔴", label: "CRIT" };
    if (temp > 60) return { cls: "warning",  icon: "🟡", label: "WARN" };
    return           { cls: "nominal",  icon: "🟢", label: "NOM"  };
  },
  battery(level) {
    if (level < 20) return { cls: "critical", icon: "🔴", label: "CRIT" };
    if (level < 50) return { cls: "warning",  icon: "🟡", label: "WARN" };
    return           { cls: "nominal",  icon: "🟢", label: "OK"   };
  },
  signal(strength) {
    if (strength < 30) return { cls: "critical", icon: "🔴", label: "WEAK"  };
    if (strength < 70) return { cls: "warning",  icon: "🟡", label: "FAIR"  };
    return              { cls: "nominal",  icon: "🟢", label: "STRONG" };
  },
  system(status) {
    if (status === "critical") return { cls: "critical", icon: "🔴" };
    if (status === "warning")  return { cls: "warning",  icon: "🟡" };
    return                      { cls: "nominal",  icon: "🟢" };
  },
  severityColor(cls) {
    const p = { critical: "ff3333", warning: "ffcc00", nominal: "00ffcc" };
    return `#${p[cls] ?? "8899aa"}`;
  },
});


// ─────────────────────────────────────────────────────────────────────────────
// FORMATTERS  (pure: value in → display string out)
// ─────────────────────────────────────────────────────────────────────────────

const Formatters = Object.freeze({
  // hour12: false forces 24-hour output ("13:05:22") in every locale.
  // Without it, toLocaleTimeString appends "a.m." / "p.m." which adds
  // ~5 extra characters and overflows the fixed-width time column.
  time(date) {
    return date.toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    });
  },
  // Short form used on the chart X-axis where vertical space is tight.
  timeShort(date) {
    return date.toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit", hour12: false,
    });
  },
});


// ─────────────────────────────────────────────────────────────────────────────
// CACHE
//
// The problem this solves: every time a user opens the popup, they see a blank
// spinner while waiting for the first network round-trip (~300ms best case).
// That perceived latency is jarring for something that should feel instant.
//
// The solution: on a successful fetch, persist the records to localStorage
// (which survives popup close/open within the same browser session). On the
// next popup open, paint the cached data immediately while a fresh fetch runs
// silently in the background. If the fresh fetch returns the same data, nothing
// changes visually; if it returns new data, the UI updates seamlessly.
//
// Why localStorage and not chrome.storage.session?
//   chrome.storage.session requires the "storage" permission in manifest.json,
//   which means a user-visible permission prompt. localStorage is available to
//   all extension pages with no extra permission, and the popup's localStorage
//   is scoped to the extension's origin, so it can't leak to web pages.
//
// The CACHE_MAX_AGE_MS guard prevents showing data that's so old it might be
// actively misleading (e.g. after the laptop wakes from sleep).
// ─────────────────────────────────────────────────────────────────────────────

const Cache = Object.freeze({

  /** Saves records to localStorage with a write timestamp. */
  save(records) {
    try {
      localStorage.setItem(CONFIG.CACHE_KEY, JSON.stringify({
        records,
        savedAt: Date.now(),
      }));
    } catch {
      // localStorage can throw in private browsing with storage blocked.
      // Failing silently is fine — the cache is a performance optimisation,
      // not a correctness requirement.
    }
  },

  /**
   * Returns cached records if they exist and are younger than CACHE_MAX_AGE_MS.
   * Returns null if the cache is empty, unreadable, or too stale.
   */
  load() {
    try {
      const raw = localStorage.getItem(CONFIG.CACHE_KEY);
      if (!raw) return null;

      const { records, savedAt } = JSON.parse(raw);
      const age = Date.now() - savedAt;

      if (age > CONFIG.CACHE_MAX_AGE_MS) return null;
      if (!Array.isArray(records) || records.length === 0) return null;

      return records;
    } catch {
      return null;
    }
  },

  /** Clears the cache — called when the server returns an unrecoverable error. */
  clear() {
    try { localStorage.removeItem(CONFIG.CACHE_KEY); } catch { /* silent */ }
  },

});


// ─────────────────────────────────────────────────────────────────────────────
// API
//
// Key changes from the previous version:
//
//   generateReading(signal) — now accepts an AbortSignal so the Controller
//     can cancel it if a new poll fires before this one completes.
//
//   fetchHistory(limit, signal) — same AbortSignal pattern.
//
// Both methods still throw typed errors (NetworkError / DataError) so the
// Controller can reason about *what* went wrong without inspecting raw types.
// ─────────────────────────────────────────────────────────────────────────────

const API = Object.freeze({

  /**
   * Asks the server to generate and persist one new telemetry reading.
   * @param {AbortSignal} signal — cancels the request if the caller aborts
   * @throws {NetworkError}
   */
  async generateReading(signal) {
    let res;
    try {
      res = await fetch(`${CONFIG.API_BASE}/telemetry`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({}),
        signal,  // honours AbortController.abort()
      });
    } catch (err) {
      // AbortError means *we* cancelled the request — not a network failure.
      // Re-throw it as-is so the controller can distinguish the two cases.
      if (err.name === "AbortError") throw err;
      throw new NetworkError("Cannot reach the telemetry server.");
    }
    if (!res.ok) {
      throw new NetworkError(`POST /telemetry failed — HTTP ${res.status}.`);
    }
  },

  /**
   * Fetches the N most recent records from /telemetry/history.
   * @param {number}      limit
   * @param {AbortSignal} signal
   * @returns {object[]} records array, newest first
   * @throws {NetworkError | DataError}
   */
  async fetchHistory(limit = CONFIG.HISTORY_LIMIT, signal) {
    let res;
    try {
      res = await fetch(
        `${CONFIG.API_BASE}/telemetry/history?limit=${limit}&page=1`,
        { signal }
      );
    } catch (err) {
      if (err.name === "AbortError") throw err;
      throw new NetworkError("Cannot reach the telemetry server.");
    }
    if (!res.ok) {
      throw new NetworkError(`GET /telemetry/history failed — HTTP ${res.status}.`);
    }
    const body = await res.json();
    if (!body.success || !Array.isArray(body.data) || body.data.length === 0) {
      throw new DataError("Server responded but returned no telemetry records.");
    }
    return body.data;
  },

});


// ─────────────────────────────────────────────────────────────────────────────
// CHART  (pure SVG builder — see previous session for detailed math notes)
// ─────────────────────────────────────────────────────────────────────────────

const Chart = Object.freeze({
  buildTempSvg(records) {
    const pts   = [...records].reverse();
    const n     = pts.length;
    const temps = pts.map(r => r.temperature);
    const times = pts.map(r => Formatters.timeShort(new Date(r.timestamp)));
    const dims  = this._dimensions();
    const range = this._yRange(temps);
    const xAt   = this._xMapper(n, dims);
    const yAt   = this._yMapper(range, dims);
    const color = Classifiers.severityColor(Classifiers.temperature(temps[n - 1]).cls);
    return this._assembleSvg({ temps, times, n, dims, xAt, yAt, color, range });
  },
  _dimensions() {
    const W = 276, H = 78;
    const PAD = { top: 10, right: 8, bottom: 18, left: 28 };
    return { W, H, PAD, plotW: W - PAD.left - PAD.right, plotH: H - PAD.top - PAD.bottom };
  },
  _yRange(temps) {
    const rawMin = Math.min(...temps), rawMax = Math.max(...temps);
    const spread = Math.max(rawMax - rawMin, 15);
    return { min: Math.max(0, rawMin - spread * 0.25), max: Math.min(150, rawMax + spread * 0.25) };
  },
  _xMapper(n, { PAD, plotW }) {
    return i => PAD.left + (n > 1 ? (i / (n - 1)) * plotW : plotW / 2);
  },
  _yMapper({ min, max }, { PAD, plotH }) {
    return v => PAD.top + plotH - ((v - min) / (max - min)) * plotH;
  },
  _fillPath(temps, n, xAt, yAt, baseline) {
    return [
      `M ${xAt(0).toFixed(1)},${yAt(temps[0]).toFixed(1)}`,
      ...temps.slice(1).map((t, i) => `L ${xAt(i+1).toFixed(1)},${yAt(t).toFixed(1)}`),
      `L ${xAt(n-1).toFixed(1)},${baseline}`,
      `L ${xAt(0).toFixed(1)},${baseline}`, "Z",
    ].join(" ");
  },
  _gridLines(yTicks, { PAD, plotW }, yAt) {
    return yTicks.map(v => `<line x1="${PAD.left}" y1="${yAt(v).toFixed(1)}"
      x2="${PAD.left + plotW}" y2="${yAt(v).toFixed(1)}"
      stroke="rgba(0,217,179,0.09)" stroke-width="0.5" stroke-dasharray="3,3"/>`).join("");
  },
  _dots(temps, n, xAt, yAt) {
    return temps.map((t, i) => {
      const fill = Classifiers.severityColor(Classifiers.temperature(t).cls);
      const r    = i === n - 1 ? 3 : 2;
      const glow = i === n - 1 ? 'filter="url(#glow)"' : "";
      return `<circle cx="${xAt(i).toFixed(1)}" cy="${yAt(t).toFixed(1)}" r="${r}" fill="${fill}" ${glow}/>`;
    }).join("");
  },
  _yLabels(yTicks, { PAD }, yAt) {
    return yTicks.map(v => `<text x="${PAD.left - 3}" y="${(yAt(v)+3).toFixed(1)}"
      text-anchor="end" font-size="7" font-family="Courier New, monospace"
      fill="#445566">${Math.round(v)}°</text>`).join("");
  },
  _xLabels(times, n, xAt, H) {
    return `
      <text x="${xAt(0).toFixed(1)}" y="${H-2}" text-anchor="start"
            font-size="7" font-family="Courier New, monospace" fill="#445566">${times[0]}</text>
      <text x="${xAt(n-1).toFixed(1)}" y="${H-2}" text-anchor="end"
            font-size="7" font-family="Courier New, monospace" fill="#445566">${times[n-1]}</text>`;
  },
  _assembleSvg({ temps, times, n, dims, xAt, yAt, color, range }) {
    const { W, H, PAD, plotW, plotH } = dims;
    const baseline   = (PAD.top + plotH).toFixed(1);
    const yTicks     = [range.min, (range.min + range.max) / 2, range.max];
    const linePoints = temps.map((t, i) => `${xAt(i).toFixed(1)},${yAt(t).toFixed(1)}`).join(" ");
    return `
      <svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg"
           style="width:100%;height:auto;display:block;overflow:visible;">
        <defs>
          <linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stop-color="${color}" stop-opacity="0.25"/>
            <stop offset="100%" stop-color="${color}" stop-opacity="0.0"/>
          </linearGradient>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.5" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>
        <rect x="${PAD.left}" y="${PAD.top}" width="${plotW}" height="${plotH}"
              fill="none" stroke="rgba(0,217,179,0.12)" stroke-width="0.8" rx="2"/>
        ${this._gridLines(yTicks, dims, yAt)}
        <path d="${this._fillPath(temps, n, xAt, yAt, baseline)}" fill="url(#tg)"/>
        <polyline points="${linePoints}" fill="none" stroke="${color}"
                  stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"
                  filter="url(#glow)"/>
        ${this._dots(temps, n, xAt, yAt)}
        ${this._yLabels(yTicks, dims, yAt)}
        ${this._xLabels(times, n, xAt, H)}
      </svg>`;
  },
});


// ─────────────────────────────────────────────────────────────────────────────
// RENDERER  (pure HTML builders — no DOM access)
// ─────────────────────────────────────────────────────────────────────────────

const Renderer = Object.freeze({
  loading() {
    return `<div class="loading-state">
              <div class="spinner"></div>
              <div class="loading-text">Fetching telemetry history…</div>
            </div>`;
  },
  error(message, isOffline = false) {
    const heading = isOffline ? "API Connection Lost"   : "No Data Available";
    const hint    = isOffline
      ? "Make sure the local server is running on port 5000."
      : "The server responded but returned no valid telemetry.";
    return `
      <div class="error-state">
        <div class="error-icon">${isOffline ? "✕" : "⚠"}</div>
        <div class="error-heading">${heading}</div>
        <div class="error-hint">${hint}</div>
        ${message ? `<div class="error-detail">${message}</div>` : ""}
        <button class="retry-btn">↻ Retry</button>
      </div>`;
  },
  metricCell(value, unit, cls) {
    return `<span class="history-cell" style="color:${Classifiers.severityColor(cls)};">
              ${value}<span class="history-unit">${unit}</span>
            </span>`;
  },
  historyRow(record, index) {
    const time   = Formatters.time(new Date(record.timestamp));
    const sys    = Classifiers.system(record.subsystem_status);
    const tempS  = Classifiers.temperature(record.temperature);
    const batS   = Classifiers.battery(record.battery_level);
    const sigS   = Classifiers.signal(record.signal_strength);
    const latest = index === 0;
    return `
      <div class="history-row ${latest ? "history-row--latest" : ""}">
        <div class="history-seq">
          ${latest ? `<span class="latest-badge">NEW</span>` : `<span class="seq-num">#${index+1}</span>`}
        </div>
        <div class="history-time">${time}</div>
        <div class="history-metrics">
          ${this.metricCell(record.temperature,     "°", tempS.cls)}
          ${this.metricCell(record.battery_level,   "%", batS.cls)}
          ${this.metricCell(record.signal_strength, "%", sigS.cls)}
        </div>
        <div class="history-status" title="${record.subsystem_status.toUpperCase()}">
          <span class="sys-icon">${sys.icon}</span>
          <span class="sys-label ${sys.cls}">${record.subsystem_status.toUpperCase()}</span>
        </div>
      </div>`;
  },
  dashboard(records) {
    return `
      <div class="history-header">
        <div class="history-seq"></div>
        <div class="history-time">TIME</div>
        <div class="history-metrics"><span>TEMP</span><span>BAT</span><span>SIG</span></div>
        <div class="history-status">STATUS</div>
      </div>
      ${records.map((r, i) => this.historyRow(r, i)).join("")}
      <div class="history-caption">Showing ${records.length} most recent readings</div>
      <div class="chart-card">
        <div class="chart-title">🌡 TEMPERATURE TREND</div>
        <div class="chart-body">${Chart.buildTempSvg(records)}</div>
      </div>`;
  },
});


// ─────────────────────────────────────────────────────────────────────────────
// UI  (the ONLY layer allowed to touch the DOM)
// ─────────────────────────────────────────────────────────────────────────────

const UI = Object.freeze({
  _output:    document.getElementById("output"),
  _connDot:   document.getElementById("connection-status"),
  _timestamp: document.getElementById("timestamp-display"),

  showLoading() {
    this._output.innerHTML = Renderer.loading();
    this._setConnector("connecting");
  },
  showError(message, isOffline = false) {
    this._output.innerHTML = Renderer.error(message, isOffline);
    this._setConnector("offline");
  },
  showDashboard(records) {
    this._output.innerHTML      = Renderer.dashboard(records);
    this._timestamp.textContent = Formatters.time(new Date(records[0].timestamp));
    this._setConnector("online");
  },
  _setConnector(mode) {
    const el = this._connDot;
    el.textContent = "●";
    el.classList.toggle("offline", mode === "offline");
    el.style.animation = mode === "connecting" ? "pulse 1.2s ease-in-out infinite" : "none";
  },
});


// ─────────────────────────────────────────────────────────────────────────────
// CONTROLLER
//
// This is where all four optimisations are implemented and coordinated:
//
//   1. POST THROTTLING
//      lastGenerateTime tracks when we last POSTed. We only generate a new
//      reading when GENERATE_INTERVAL_MS has elapsed. All other polls are
//      read-only GETs — much cheaper for the server.
//
//   2. SESSION CACHING
//      On the very first call, load() checks localStorage for recent data.
//      If found, it renders immediately (zero perceived latency) and then
//      fetches in the background to check for fresher data.
//
//   3. ID-BASED RENDER DIFFING
//      lastSeenId stores the `id` field of the newest record currently
//      displayed. After a successful fetch, we compare the incoming newest
//      ID to lastSeenId. If they match, the data hasn't changed and we skip
//      the DOM re-render entirely — saving layout work on every idle poll.
//
//   4. EXPONENTIAL BACKOFF
//      consecutiveErrors tracks how many polls in a row have failed.
//      nextPollMs() uses that count to compute a progressively longer wait,
//      capped at MAX_BACKOFF_MS. On the first success, the count resets.
//
//   5. ABORTCONTROLLER (bonus)
//      A new AbortController is created before each fetch cycle. If a poll
//      fires while the previous one is still in flight, the old request is
//      aborted before the new one starts. This prevents a slow response from
//      racing with a fast one and painting stale data over fresh data.
// ─────────────────────────────────────────────────────────────────────────────

const Controller = (() => {

  // ── Private state ────────────────────────────────────────────────────────

  const state = {
    status:            "idle",
    records:           [],
    error:             null,

    // The `id` of the newest record currently painted on screen.
    // null means nothing has been rendered yet.
    lastSeenId:        null,

    // Timestamp of the last POST to /telemetry.
    // Initialised to 0 so the very first poll always generates a reading.
    lastGenerateTime:  0,

    // How many polls in a row have ended in error (for backoff calculation).
    consecutiveErrors: 0,

    // The AbortController for the currently in-flight fetch cycle.
    // Stored here so we can cancel it before starting the next one.
    activeAbort:       null,
  };

  // ── Helpers ───────────────────────────────────────────────────────────────

  /**
   * Computes how long to wait before the next poll.
   * On success this is always POLL_INTERVAL_MS.
   * On repeated errors it doubles each time, capped at MAX_BACKOFF_MS.
   *
   * Why exponential and not linear? Linear backoff (5s, 10s, 15s…) still
   * hammers a dead server fairly hard over time. Exponential backoff
   * (5s, 10s, 20s, 40s, 60s…) approaches a safe steady state much faster.
   */
  function nextPollMs() {
    if (state.consecutiveErrors === 0) return CONFIG.POLL_INTERVAL_MS;
    const backoff = CONFIG.POLL_INTERVAL_MS * (2 ** (state.consecutiveErrors - 1));
    return Math.min(backoff, CONFIG.MAX_BACKOFF_MS);
  }

  /**
   * Decides whether the current poll should generate a new reading.
   * True only if GENERATE_INTERVAL_MS has passed since the last POST.
   */
  function shouldGenerate() {
    return Date.now() - state.lastGenerateTime >= CONFIG.GENERATE_INTERVAL_MS;
  }

  // ── Core refresh cycle ────────────────────────────────────────────────────

  async function refresh() {
    // Cancel any in-flight request from the previous cycle before we start.
    // This prevents stale responses from overwriting a newer render.
    if (state.activeAbort) state.activeAbort.abort();
    const abort = new AbortController();
    state.activeAbort = abort;

    // On the very first load: show the spinner only if we have no cached data.
    // If cache.load() returns something, we'll paint that data immediately
    // below and the user never sees a blank state.
    if (state.status === "idle") {
      const cached = Cache.load();
      if (cached) {
        // Paint stale-but-recent data right away so the popup feels instant.
        // The fresh fetch below will silently update if anything changed.
        UI.showDashboard(cached);
        state.lastSeenId = cached[0]?.id ?? null;
      } else {
        UI.showLoading();
      }
      state.status = "loading";
    }

    try {
      // ── Step 1: Conditionally generate a new reading ──────────────────
      // Only POST if the generate interval has elapsed. This decouples the
      // write cadence from the read cadence and is the largest single
      // reduction in server load.
      if (shouldGenerate()) {
        await API.generateReading(abort.signal);
        state.lastGenerateTime = Date.now();
      }

      // ── Step 2: Fetch the current history ─────────────────────────────
      const records = await API.fetchHistory(CONFIG.HISTORY_LIMIT, abort.signal);

      // ── Step 3: ID diffing — skip render if nothing has changed ───────
      // The server sorts history newest-first, so records[0] is always the
      // most recent. If its `id` matches what we already have on screen,
      // the underlying data is identical and re-rendering would be pure waste.
      const incomingId = records[0]?.id ?? null;

      if (incomingId !== null && incomingId === state.lastSeenId) {
        // Data is unchanged — update only the footer timestamp to show the
        // poll ran successfully, but leave the main content alone.
        document.getElementById("timestamp-display").textContent =
          Formatters.time(new Date());
        // Still schedule the next poll — don't return early from that logic.
        state.consecutiveErrors = 0;
      } else {
        // New data arrived — do a full render and update the cache.
        state.records          = records;
        state.lastSeenId       = incomingId;
        state.consecutiveErrors = 0;
        state.status           = "success";

        UI.showDashboard(records);
        Cache.save(records); // persist for next popup open
      }

    } catch (err) {
      // AbortError means we cancelled this request ourselves (a newer poll
      // started). This is not a real failure — ignore it silently and let
      // the newer cycle handle the result.
      if (err.name === "AbortError") return;

      state.status = "error";
      state.error  = err.message;
      state.consecutiveErrors++;
      Cache.clear(); // stale cache after repeated errors is misleading

      const isOffline = err instanceof NetworkError;
      UI.showError(err.message, isOffline);
      console.error(
        `[Telemetry] ${err.name}: ${err.message}`,
        `(error #${state.consecutiveErrors},`,
        `next poll in ${nextPollMs() / 1000}s)`
      );
    } finally {
      // Schedule the next poll using the backoff-adjusted interval.
      // setTimeout instead of setInterval gives us precise control: each
      // poll waits for the previous one to finish (or fail) before the
      // next delay begins, preventing overlapping cycles on a slow server.
      setTimeout(refresh, nextPollMs());
    }
  }

  // ── Public init ───────────────────────────────────────────────────────────

  function init() {
    // Event delegation for the retry button — see refactor session for rationale.
    UI._output.addEventListener("click", e => {
      if (e.target.matches(".retry-btn")) {
        // Reset error state so the next refresh shows the spinner again
        // instead of immediately re-showing the error panel.
        state.status           = "idle";
        state.consecutiveErrors = 0;
        refresh();
      }
    });

    refresh(); // kick off the first cycle immediately
    // Note: no setInterval here — the next call is scheduled inside refresh()
    // via setTimeout, which gives us backoff-aware spacing between polls.
  }

  return { init };

})();


// ─────────────────────────────────────────────────────────────────────────────
// ENTRY POINT
// ─────────────────────────────────────────────────────────────────────────────

Controller.init();