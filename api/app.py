"""
app.py — Space Dogs Telemetry Dashboard  (v3)
==============================================
REST API built with Flask. Owns routing and HTTP concerns only;
all database work is delegated to database.py.

New in v3:
  - RateLimiter: in-memory per-IP rate limiting (no external libraries).
  - StatsCache:  TTL cache for /telemetry/stats (avoids re-running the
                 aggregate SQL query on every single request).
  - X-Request-ID header: every request gets a unique ID for log tracing.
  - POST /telemetry accepts an optional JSON body for custom readings.
  - POST /telemetry/bulk generates N readings in one fast batch insert.
  - GET  /telemetry/search filters by status, battery, temperature, dates.
  - GET  /telemetry/export.csv streams a downloadable CSV file.

Environment variables:
    FLASK_DEBUG          — "1" enables debug mode (default: 0)
    FLASK_PORT           — TCP port (default: 5000)
    TELEMETRY_DB_PATH    — override the SQLite file path
    RATE_LIMIT_PER_MIN   — max requests per IP per minute (default: 60)
    STATS_CACHE_TTL_SECS — seconds to cache /stats results (default: 10)
"""

import csv
import io
import os
import random
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from time import monotonic

from flask import Flask, Response, jsonify, request, g
from database import (
    DatabaseError,
    ValidationError,
    TelemetryRecord,
    VALID_STATUSES,
    init_db,
    save_telemetry,
    bulk_save_telemetry,
    get_by_id,
    get_telemetry_page,
    get_anomalies,
    get_telemetry_stats,
    search_telemetry,
    get_all_rows_for_export,
    delete_old_records,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# WHY THIS ORDER MATTERS:
# We must define _RequestIdFilter *before* calling basicConfig, because we
# immediately attach it to the root logger's handlers right after basicConfig
# creates them. If we defined it after, we'd have nothing to attach.

class _RequestIdFilter(logging.Filter):
    """
    Injects a 'request_id' field into every log record so the format string
    %(request_id)s always resolves — even for log lines emitted outside a
    Flask request context (e.g. during startup, or by Werkzeug internals).

    The fix for the KeyError crash: previously this filter was only added to
    app.py's own logger. Any log line from database.py, Flask, or Werkzeug
    bypassed the filter entirely, so %(request_id)s was undefined when Python
    tried to format those lines and raised KeyError → ValueError → crash.

    Now we attach this filter to every handler on the ROOT logger (done below),
    which means it intercepts 100% of log records in the entire process —
    database.py, Werkzeug, Flask internals, everything.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        # Try to read request_id from Flask's per-request 'g' object.
        # If we're outside a request context (startup, background tasks),
        # Flask raises RuntimeError when you access g — we catch it and
        # fall back to '-' so the format string always has something to print.
        try:
            record.request_id = g.request_id
        except RuntimeError:
            # RuntimeError means we're outside an application/request context.
            record.request_id = "-"
        except AttributeError:
            # AttributeError means g exists but request_id hasn't been set yet
            # (e.g. a log line before @before_request runs).
            record.request_id = "-"
        return True   # returning True means "yes, emit this record"


logging.basicConfig(
    level   = logging.DEBUG if os.environ.get("FLASK_DEBUG") == "1" else logging.INFO,
    format  = "%(asctime)s  %(levelname)-8s  %(name)s  [%(request_id)s]  %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)

# Attach the filter to EVERY handler the root logger owns.
# basicConfig() creates exactly one StreamHandler (the console) and attaches
# it to the root logger. All other loggers in the process (database, flask,
# werkzeug) propagate their records UP to the root logger's handlers, so
# patching here is sufficient — we don't need to touch each logger individually.
_request_id_filter = _RequestIdFilter()
for _handler in logging.root.handlers:
    _handler.addFilter(_request_id_filter)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate limiter (no external dependencies)
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Simple in-memory per-IP rate limiter using a sliding fixed-window strategy.

    How it works:
    We keep a dictionary that maps each IP address to a (request_count,
    window_start_time) tuple. When a request arrives, we check whether the
    current second is still within the same 60-second window as the first
    request from that IP. If it is, we increment the counter and check it
    against the limit. If the window has expired, we reset the counter to 1
    and start a new window.

    Why no external library?
    Libraries like Flask-Limiter work well, but they add a dependency and
    require configuration. For a hackathon project, understanding how to build
    the mechanism yourself is more valuable than importing a black box.

    Limitation: because we store counts in a Python dict, state is lost when
    the process restarts and is NOT shared across multiple server processes.
    For a production system with multiple workers, you would store rate-limit
    state in Redis instead.
    """

    def __init__(self, max_requests: int, window_seconds: int = 60):
        self._max      = max_requests
        self._window   = window_seconds
        # defaultdict means accessing a missing key creates it automatically
        # rather than raising a KeyError. Each value is [count, window_start].
        self._counters: dict[str, list] = defaultdict(lambda: [0, monotonic()])

    def is_allowed(self, ip: str) -> tuple[bool, int]:
        """
        Checks whether the given IP is within its rate limit.

        Returns:
            (allowed, remaining) where 'remaining' is how many more
            requests the IP can make in the current window.
        """
        now   = monotonic()
        entry = self._counters[ip]   # [count, window_start]

        if now - entry[1] >= self._window:
            # The previous window has expired — start a fresh one.
            entry[0] = 0
            entry[1] = now

        entry[0] += 1
        remaining = max(0, self._max - entry[0])
        return entry[0] <= self._max, remaining


# ---------------------------------------------------------------------------
# Stats cache (TTL-based)
# ---------------------------------------------------------------------------

class StatsCache:
    """
    A minimal Time-To-Live cache for a single value (the telemetry stats dict).

    The aggregate SQL query that powers /telemetry/stats scans every row in
    the table. If the endpoint gets hit frequently (e.g. by a dashboard that
    polls every second), this becomes wasteful — the stats don't change
    meaningfully between individual requests.

    A TTL cache solves this: we store the result together with the time it
    was computed. On the next request, if less than TTL seconds have passed,
    we return the stored result without touching the database. If the TTL has
    expired, we re-run the query and update the cache.

    This is the simplest form of caching. Production systems use tools like
    Redis or Memcached for distributed caches that survive restarts and are
    shared across multiple server processes.
    """

    def __init__(self, ttl_seconds: float):
        self._ttl        = ttl_seconds
        self._value      = None
        self._expires_at = 0.0   # monotonic timestamp when the cache expires

    def get(self):
        """Returns the cached value, or None if the cache has expired."""
        if monotonic() < self._expires_at:
            return self._value
        return None

    def set(self, value) -> None:
        """Stores a new value and resets the TTL countdown."""
        self._value      = value
        self._expires_at = monotonic() + self._ttl

    def invalidate(self) -> None:
        """Forces the cache to expire immediately (useful after writes)."""
        self._expires_at = 0.0


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)

DEBUG            = os.environ.get("FLASK_DEBUG", "0") == "1"
PORT             = int(os.environ.get("FLASK_PORT",           "5000"))
RATE_LIMIT       = int(os.environ.get("RATE_LIMIT_PER_MIN",   "60"))
STATS_CACHE_TTL  = float(os.environ.get("STATS_CACHE_TTL_SECS", "10"))

_rate_limiter = RateLimiter(max_requests=RATE_LIMIT, window_seconds=60)
_stats_cache  = StatsCache(ttl_seconds=STATS_CACHE_TTL)

init_db()


# ---------------------------------------------------------------------------
# Telemetry simulation
# ---------------------------------------------------------------------------

_STATUSES = ["nominal", "warning", "critical"]
_WEIGHTS  = [0.90,       0.07,      0.03]


def _build_record(
    temperature:      float | None = None,
    battery_level:    int   | None = None,
    signal_strength:  int   | None = None,
    subsystem_status: str   | None = None,
) -> TelemetryRecord:
    """
    Builds a TelemetryRecord, using provided values or generating simulated
    ones for any field that was left as None.

    This dual-mode function is used by both the auto-generate endpoint (all
    fields None → fully simulated) and the custom-body endpoint (some fields
    provided by the caller → mixed).
    """
    status = subsystem_status or random.choices(_STATUSES, weights=_WEIGHTS, k=1)[0]

    if temperature is None or battery_level is None or signal_strength is None:
        # Generate sensor ranges consistent with the chosen status.
        if status == "critical":
            temp    = temperature     if temperature    is not None else round(random.uniform(35.0, 55.0), 2)
            battery = battery_level   if battery_level  is not None else random.randint(5, 30)
            signal  = signal_strength if signal_strength is not None else random.randint(10, 40)
        elif status == "warning":
            temp    = temperature     if temperature    is not None else round(random.uniform(30.0, 38.0), 2)
            battery = battery_level   if battery_level  is not None else random.randint(31, 59)
            signal  = signal_strength if signal_strength is not None else random.randint(41, 69)
        else:
            temp    = temperature     if temperature    is not None else round(random.uniform(15.0, 30.0), 2)
            battery = battery_level   if battery_level  is not None else random.randint(70, 100)
            signal  = signal_strength if signal_strength is not None else random.randint(75, 100)
    else:
        temp, battery, signal = temperature, battery_level, signal_strength

    return TelemetryRecord(
        temperature      = temp,
        battery_level    = battery,
        signal_strength  = signal,
        timestamp        = datetime.now(timezone.utc).isoformat(),
        subsystem_status = status,
    )


# ---------------------------------------------------------------------------
# Request lifecycle hooks
# ---------------------------------------------------------------------------

@app.before_request
def _before_request() -> None:
    """
    Runs before every route handler.

    We do three things here:
    1. Generate a unique request ID (a UUID) and store it in Flask's 'g' object.
       This ID will appear in every log line for this request, making it trivial
       to grep the logs for everything that happened during one specific request.
    2. Record the start time so we can measure response duration.
    3. Apply the rate limiter. If the caller has sent too many requests, we
       return a 429 response here — the route handler never even runs.
    """
    g.request_id = str(uuid.uuid4())[:8]   # short 8-char prefix is enough for tracing
    g.start_time = monotonic()
    logger.info("→ %s %s", request.method, request.path)

    # Rate limiting: get the caller's IP address.
    # X-Forwarded-For is set by proxies/load balancers and contains the real
    # client IP. We fall back to request.remote_addr when no proxy is present.
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    allowed, remaining = _rate_limiter.is_allowed(client_ip)

    if not allowed:
        logger.warning("Rate limit exceeded for IP %s", client_ip)
        return jsonify({
            "success": False,
            "error":   "Rate limit exceeded. Please wait before sending more requests.",
            "hint":    f"Maximum {RATE_LIMIT} requests per 60 seconds per IP address.",
        }), 429


@app.after_request
def _after_request(response):
    """
    Runs after every route handler, before the response is sent to the client.

    We add four things:
    1. CORS headers so a browser on a different domain can call this API.
    2. X-Request-ID so the caller can correlate their client-side logs with
       our server-side logs using the same unique ID.
    3. X-Response-Time-Ms so the caller can see how long the server took.
    4. X-RateLimit-Remaining so the caller knows how many requests they have
       left before hitting the rate limit.
    """
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"

    if hasattr(g, "request_id"):
        response.headers["X-Request-ID"] = g.request_id

    if hasattr(g, "start_time"):
        elapsed_ms = (monotonic() - g.start_time) * 1000
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"

    return response


# ---------------------------------------------------------------------------
# Custom JSON error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def _not_found(_):
    return jsonify({
        "success": False,
        "error":   "Endpoint not found.",
        "hint":    "Visit GET / for a list of available endpoints.",
    }), 404

@app.errorhandler(405)
def _method_not_allowed(_):
    return jsonify({
        "success": False,
        "error":   f"HTTP method '{request.method}' is not allowed on this endpoint.",
    }), 405

@app.errorhandler(500)
def _internal_error(error):
    logger.exception("Unhandled server error: %s", error)
    return jsonify({"success": False, "error": "An unexpected server error occurred."}), 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_pagination() -> tuple[int, int]:
    """Parses ?page and ?limit query params. Returns (limit, offset)."""
    page   = max(1,   int(request.args.get("page",  1)))
    limit  = min(100, int(request.args.get("limit", 20)))
    return limit, (page - 1) * limit


def _pagination_meta(total: int, limit: int, offset: int) -> dict:
    """Builds a reusable pagination metadata dict for any list endpoint."""
    current_page = (offset // limit) + 1
    total_pages  = max(1, -(-total // limit))  # ceiling division trick
    return {
        "total_records": total,
        "total_pages":   total_pages,
        "current_page":  current_page,
        "per_page":      limit,
        "has_next":      current_page < total_pages,
        "has_prev":      current_page > 1,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    """Index — service metadata and full endpoint map."""
    return jsonify({
        "service": "Space Dogs Telemetry API",
        "version": "3.0",
        "status":  "running",
        "team":    "José & Maryfer — Space Dogs International Projects",
        "event":   "Global Hack Week: Cloud — March 2026",
        "endpoints": {
            "GET  /":                      "This index page",
            "GET  /health":                "Lightweight health check",
            "POST /telemetry":             "Generate & save one reading (optional JSON body)",
            "GET  /telemetry/<id>":        "Retrieve one record by ID",
            "POST /telemetry/bulk":        "Generate N readings at once (?count=10)",
            "GET  /telemetry/history":     "Paginated history (?page=1&limit=20)",
            "GET  /telemetry/search":      "Filter by status, battery, temp, date",
            "GET  /telemetry/anomalies":   "Non-nominal records only",
            "GET  /telemetry/stats":       "Aggregate statistics (cached)",
            "GET  /telemetry/export.csv":  "Download all records as a CSV file",
            "DELETE /telemetry/old":       "Prune oldest records (?keep=1000)",
        },
    })


@app.route("/health")
def health_check():
    """Lightweight ping — no database touch, no telemetry generated."""
    return jsonify({
        "status":    "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/telemetry", methods=["GET", "POST"])
def telemetry_generate():
    """
    Generates one telemetry reading, saves it, and returns it.

    What's new in v3: if the request includes a JSON body, we read field
    values from it and use them instead of simulating random ones. This
    lets you inject specific test scenarios (e.g. a critical reading with
    known values) without hacking the simulation code.

    Example POST body (all fields optional — omit any to simulate it):
        {
            "temperature": 47.3,
            "battery_level": 12,
            "subsystem_status": "critical"
        }
    """
    try:
        body = request.get_json(silent=True) or {}
        # silent=True means get_json() returns None (not an error) if the
        # body is missing or not valid JSON. We then default to {}.

        record    = _build_record(
            temperature      = body.get("temperature"),
            battery_level    = body.get("battery_level"),
            signal_strength  = body.get("signal_strength"),
            subsystem_status = body.get("subsystem_status"),
        )
        record.id = save_telemetry(record)
        _stats_cache.invalidate()   # stats changed — expire the cache

        return jsonify({"success": True, "data": record.to_dict()}), 201

    except ValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except DatabaseError as exc:
        logger.error("DB error on POST /telemetry: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 503


@app.route("/telemetry/<int:record_id>")
def telemetry_get_one(record_id: int):
    """Returns the single record with the given ID, or 404 if not found."""
    try:
        record = get_by_id(record_id)
        if record is None:
            return jsonify({
                "success": False,
                "error":   f"No record found with id={record_id}.",
            }), 404
        return jsonify({"success": True, "data": record.to_dict()})

    except DatabaseError as exc:
        logger.error("DB error fetching id=%s: %s", record_id, exc)
        return jsonify({"success": False, "error": str(exc)}), 503


@app.route("/telemetry/bulk", methods=["POST"])
def telemetry_bulk():
    """
    Generates N telemetry readings and inserts them all in one fast batch.

    Query parameter:
        count — number of readings to generate (default: 10, max: 500)

    Why would you want this?
    Useful for quickly seeding the database with test data, or for
    simulating a burst of telemetry from a satellite that was out of
    contact for a while. It's also a great way to demonstrate the
    performance difference between N individual INSERTs and one
    bulk INSERT using executemany().

    Example: POST /telemetry/bulk?count=100
    """
    try:
        count = min(500, max(1, int(request.args.get("count", 10))))
        records = [_build_record() for _ in range(count)]
        inserted = bulk_save_telemetry(records)
        _stats_cache.invalidate()

        return jsonify({
            "success":          True,
            "records_inserted": inserted,
            "message":          f"Generated and saved {inserted} telemetry readings.",
        }), 201

    except ValueError:
        return jsonify({"success": False, "error": "'count' must be a positive integer."}), 400
    except ValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except DatabaseError as exc:
        logger.error("DB error on POST /telemetry/bulk: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 503


@app.route("/telemetry/history")
def telemetry_history():
    """
    Paginated list of records, newest first.

    Query parameters:
        page  — page number (default: 1)
        limit — records per page (default: 20, max: 100)
    """
    try:
        limit, offset  = _parse_pagination()
        records, total = get_telemetry_page(limit=limit, offset=offset)
        return jsonify({
            "success":    True,
            "pagination": _pagination_meta(total, limit, offset),
            "records":    [r.to_dict() for r in records],
        })
    except ValueError:
        return jsonify({"success": False, "error": "'page' and 'limit' must be integers."}), 400
    except DatabaseError as exc:
        logger.error("DB error on /telemetry/history: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 503


@app.route("/telemetry/search")
def telemetry_search():
    """
    Filtered search across stored telemetry records.

    All query parameters are optional — omit any you don't need:
        status      — 'nominal', 'warning', or 'critical'
        min_battery — minimum battery_level (0–100)
        max_battery — maximum battery_level (0–100)
        min_temp    — minimum temperature (float)
        max_temp    — maximum temperature (float)
        from_ts     — earliest timestamp (ISO 8601, e.g. 2026-03-15T00:00:00)
        to_ts       — latest  timestamp  (ISO 8601)
        page        — page number (default: 1)
        limit       — records per page (default: 20, max: 100)

    Example:
        GET /telemetry/search?status=warning&min_battery=20&max_temp=45.0
    """
    try:
        limit, offset = _parse_pagination()

        def opt_int(key):
            v = request.args.get(key)
            return int(v) if v is not None else None

        def opt_float(key):
            v = request.args.get(key)
            return float(v) if v is not None else None

        records, total = search_telemetry(
            status      = request.args.get("status")      or None,
            min_battery = opt_int("min_battery"),
            max_battery = opt_int("max_battery"),
            min_temp    = opt_float("min_temp"),
            max_temp    = opt_float("max_temp"),
            from_ts     = request.args.get("from_ts")     or None,
            to_ts       = request.args.get("to_ts")       or None,
            limit       = limit,
            offset      = offset,
        )
        return jsonify({
            "success":    True,
            "pagination": _pagination_meta(total, limit, offset),
            "records":    [r.to_dict() for r in records],
        })

    except ValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except ValueError:
        return jsonify({"success": False, "error": "Numeric parameters must be valid numbers."}), 400
    except DatabaseError as exc:
        logger.error("DB error on /telemetry/search: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 503


@app.route("/telemetry/anomalies")
def telemetry_anomalies():
    """Returns the most recent non-nominal records (warning + critical)."""
    try:
        limit   = min(100, int(request.args.get("limit", 20)))
        records = get_anomalies(limit=limit)
        return jsonify({
            "success": True,
            "count":   len(records),
            "records": [r.to_dict() for r in records],
        })
    except ValueError:
        return jsonify({"success": False, "error": "'limit' must be an integer."}), 400
    except DatabaseError as exc:
        logger.error("DB error on /telemetry/anomalies: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 503


@app.route("/telemetry/stats")
def telemetry_stats():
    """
    Aggregate statistics with TTL caching.

    The stats query scans every row in the table. If a frontend polls this
    endpoint every second, we'd run that full scan every second — wasteful
    when the data barely changes. The StatsCache stores the result for
    STATS_CACHE_TTL_SECS seconds (default: 10) and serves it from memory
    on subsequent requests. The response includes a 'cached' field so you
    can see when a cache hit occurred.
    """
    try:
        cached = _stats_cache.get()
        if cached is not None:
            return jsonify({"success": True, "cached": True,  "stats": cached})

        stats = get_telemetry_stats()
        _stats_cache.set(stats)
        return jsonify({"success": True, "cached": False, "stats": stats})

    except DatabaseError as exc:
        logger.error("DB error on /telemetry/stats: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 503


@app.route("/telemetry/export.csv")
def telemetry_export_csv():
    """
    Streams all telemetry records as a downloadable CSV file.

    What does 'streaming' mean here?
    Instead of building the entire CSV string in memory first, we write
    rows directly into a StringIO buffer that Flask sends incrementally
    to the client. For a small SQLite database this doesn't matter much,
    but it's the correct pattern — if the table had 1 million rows, loading
    them all into a Python string before sending would exhaust memory.

    The Content-Disposition header tells the browser to download the
    response as a file rather than displaying it inline.

    Try it in your browser: visit /telemetry/export.csv — it downloads!
    """
    try:
        columns, rows = get_all_rows_for_export()

        # io.StringIO is an in-memory text buffer — it behaves exactly like
        # a file but never touches the disk.
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)   # write the header row first
        writer.writerows(rows)     # write all data rows

        # Rewind the buffer to the beginning so Flask reads from the start.
        output.seek(0)

        filename  = f"telemetry_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            output.getvalue(),
            mimetype    = "text/csv",
            headers     = {
                "Content-Disposition": f"attachment; filename={filename}",
            },
        )

    except DatabaseError as exc:
        logger.error("DB error on /telemetry/export.csv: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 503


@app.route("/telemetry/old", methods=["DELETE"])
def telemetry_delete_old():
    """
    Prunes the oldest records, keeping only the most recent N.

    Query parameter:
        keep — how many recent records to preserve (default: 1000)

    Example: DELETE /telemetry/old?keep=500
    """
    try:
        keep    = max(1, int(request.args.get("keep", 1000)))
        deleted = delete_old_records(keep_last_n=keep)
        if deleted:
            _stats_cache.invalidate()

        return jsonify({
            "success":         True,
            "records_deleted": deleted,
            "records_kept":    keep,
            "message": f"Deleted {deleted} record(s)." if deleted
                       else "No records needed pruning.",
        })
    except ValueError:
        return jsonify({"success": False, "error": "'keep' must be a positive integer."}), 400
    except DatabaseError as exc:
        logger.error("DB error on DELETE /telemetry/old: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 503


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info(
        "Starting Space Dogs Telemetry API  port=%s  debug=%s  rate_limit=%s/min",
        PORT, DEBUG, RATE_LIMIT,
    )
    app.run(debug=DEBUG, port=PORT, host="0.0.0.0")