"""
app.py — Space Dogs Telemetry Dashboard  (v3.2)
===============================================
REST API built with Flask. Owns routing and HTTP concerns only;
all database work is delegated to database.py.

New in v3.2 (Block 3 compliance pass):
  - POST /telemetry now explicitly rejects non-JSON requests with 415.
  - All endpoints now use a unified response contract:
        { "success": bool, "data": ..., ...optional fields... }
    Previously some endpoints used "records", "stats", or omitted "success".
  - /health now includes "success" for contract consistency.
  - DB error responses no longer expose raw exception messages, which
    could leak internal implementation details (table names, file paths).

New in v3.1:
  - _latest_cache: dedicated TTL cache for /telemetry/latest.
  - /telemetry/latest returns "status" + "cached" fields.
  - Eager cache invalidation on all write endpoints.

New in v3:
  - RateLimiter, StatsCache, X-Request-ID, bulk insert, search, CSV export.

Environment variables:
    FLASK_DEBUG          — "1" enables debug mode (default: 0)
    FLASK_PORT           — TCP port (default: 5000)
    TELEMETRY_DB_PATH    — override the SQLite file path
    RATE_LIMIT_PER_MIN   — max requests per IP per minute (default: 60)
    STATS_CACHE_TTL_SECS — seconds to cache /stats results (default: 10)
"""

import csv
import io
import random
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from time import monotonic


from flask import Flask, Response, jsonify, request, g
from config import DEBUG, PORT, RATE_LIMIT, STATS_CACHE_TTL
from database import (
    DatabaseError,
    ValidationError,
    TelemetryRecord,
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
    get_latest_telemetry,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class _RequestIdFilter(logging.Filter):
    """
    Injects a 'request_id' field into every log record so the format string
    %(request_id)s always resolves — even for log lines emitted outside a
    Flask request context (e.g. during startup, or by Werkzeug internals).
    """
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.request_id = g.request_id
        except RuntimeError:
            record.request_id = "-"
        except AttributeError:
            record.request_id = "-"
        return True


logging.basicConfig(
    level   = logging.DEBUG if DEBUG else logging.INFO,
    format  = "%(asctime)s  %(levelname)-8s  %(name)s  [%(request_id)s]  %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)

_request_id_filter = _RequestIdFilter()
for _handler in logging.root.handlers:
    _handler.addFilter(_request_id_filter)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Simple in-memory per-IP rate limiter using a fixed-window strategy.
    State is not shared across processes — use Redis for multi-worker setups.
    """

    def __init__(self, max_requests: int, window_seconds: int = 60):
        self._max      = max_requests
        self._window   = window_seconds
        self._counters: dict[str, list] = defaultdict(lambda: [0, monotonic()])

    def is_allowed(self, ip: str) -> tuple[bool, int]:
        now   = monotonic()
        entry = self._counters[ip]

        if now - entry[1] >= self._window:
            entry[0] = 0
            entry[1] = now

        entry[0] += 1
        remaining = max(0, self._max - entry[0])
        return entry[0] <= self._max, remaining


# ---------------------------------------------------------------------------
# TTL cache
# ---------------------------------------------------------------------------

class StatsCache:
    """
    Minimal TTL cache for a single value.

    Used for both _stats_cache (aggregate query results) and _latest_cache
    (most recent telemetry record) — the caching contract is identical for
    both, so one class handles both cases.
    """

    def __init__(self, ttl_seconds: float):
        self._ttl        = ttl_seconds
        self._value      = None
        self._expires_at = 0.0

    def get(self):
        """Returns the cached value, or None if the TTL has expired."""
        if monotonic() < self._expires_at:
            return self._value
        return None

    def set(self, value) -> None:
        """Stores a new value and resets the TTL countdown."""
        self._value      = value
        self._expires_at = monotonic() + self._ttl

    def invalidate(self) -> None:
        """Forces immediate expiry — call this after any write operation."""
        self._expires_at = 0.0


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)

_rate_limiter = RateLimiter(max_requests=RATE_LIMIT, window_seconds=60)
_stats_cache  = StatsCache(ttl_seconds=STATS_CACHE_TTL)

# Dedicated cache for the single latest record.
# Invalidated eagerly on every write so it never serves stale data.
_latest_cache = StatsCache(ttl_seconds=STATS_CACHE_TTL)

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
    Builds a TelemetryRecord using provided values, or simulating any field
    left as None. Sensor ranges are kept consistent with the chosen status.
    """
    status = subsystem_status or random.choices(_STATUSES, weights=_WEIGHTS, k=1)[0]

    if temperature is None or battery_level is None or signal_strength is None:
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
    """Assigns a unique request ID, records start time, enforces rate limits."""
    g.request_id = str(uuid.uuid4())[:8]
    g.start_time = monotonic()
    logger.info("-> %s %s", request.method, request.path)

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(",")[0].strip()
    client_ip = client_ip or "unknown"

    if client_ip in ("127.0.0.1", "::1"):
        g.rate_limit_remaining = "infinite"
    else:
        allowed, remaining = _rate_limiter.is_allowed(client_ip)
        g.rate_limit_remaining = remaining

        if not allowed:
            logger.warning("Rate limit exceeded for IP %s", client_ip)
            return jsonify({
                "success": False,
                "error":   "Rate limit exceeded. Please wait before sending more requests.",
                "hint":    f"Maximum {RATE_LIMIT} requests per 60 seconds per IP address.",
            }), 429


@app.after_request
def _after_request(response):
    """Adds CORS, X-Request-ID, X-Response-Time-Ms, and X-RateLimit-Remaining headers."""
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"

    if hasattr(g, "request_id"):
        response.headers["X-Request-ID"] = g.request_id

    if hasattr(g, "start_time"):
        elapsed_ms = (monotonic() - g.start_time) * 1000
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"

    if hasattr(g, "rate_limit_remaining"):
        response.headers["X-RateLimit-Remaining"] = str(g.rate_limit_remaining)

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
    page  = max(1,   int(request.args.get("page",  1)))
    limit = min(100, int(request.args.get("limit", 20)))
    return limit, (page - 1) * limit


def _pagination_meta(total: int, limit: int, offset: int) -> dict:
    """Builds a reusable pagination metadata dict for any list endpoint."""
    current_page = (offset // limit) + 1
    total_pages  = max(1, -(-total // limit))
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
        "success": True,   # v3.2: added for contract consistency
        "service": "Space Dogs Telemetry API",
        "version": "3.2",
        "status":  "running",
        "team":    "Jose & Maryfer - Space Dogs International Projects",
        "event":   "Global Hack Week: Cloud - March 2026",
        "endpoints": {
            "GET  /":                      "This index page",
            "GET  /health":                "Lightweight health check",
            "POST /telemetry":             "Generate & save one reading (optional JSON body)",
            "GET  /telemetry/latest":      "Retrieve the most recent record (cache-aware)",
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
    """
    Lightweight ping -- no database touch, no telemetry generated.

    v3.2: added "success" so this endpoint obeys the same contract as every
    other route. Previously it returned only "status" and "timestamp", making
    it the one outlier in the entire API.
    """
    return jsonify({
        "success":   True,          # v3.2: added for contract consistency
        "status":    "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/telemetry", methods=["GET", "POST"])
def telemetry_generate():
    """
    Generates one telemetry reading, saves it, and returns it.

    v3.2: the endpoint now explicitly rejects requests that are not sent with
    Content-Type: application/json (status 415 Unsupported Media Type).
    Previously, a plain-text or form body would silently become {} instead of
    raising an error, meaning bad input could appear to succeed.

    POST body (all fields optional -- omit any to simulate it):
        {
            "temperature": 47.3,
            "battery_level": 12,
            "subsystem_status": "critical"
        }
    """
    try:
        # v3.2: explicit Content-Type guard.
        # 415 Unsupported Media Type is the correct HTTP status here -- the
        # server understands the request but refuses the media format.
        if request.method == "POST" and not request.is_json:
            return jsonify({
                "success": False,
                "error":   "Request body must be JSON.",
                "hint":    "Set Content-Type: application/json and send a valid JSON body.",
            }), 415

        body = request.get_json(silent=True) or {}

        temp_raw   = body.get("temperature")
        bat_raw    = body.get("battery_level")
        sig_raw    = body.get("signal_strength")
        status_raw = body.get("subsystem_status")

        try:
            temperature = float(temp_raw)           if temp_raw   is not None else None
            battery     = int(bat_raw)              if bat_raw    is not None else None
            signal      = int(sig_raw)              if sig_raw    is not None else None
            status      = str(status_raw).strip()   if status_raw is not None else None
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error":   "Invalid input types.",
                "hint":    "temperature=float, battery_level=int, signal_strength=int, subsystem_status=str",
            }), 400

        if status is not None and status == "":
            return jsonify({
                "success": False,
                "error":   "subsystem_status must not be empty.",
            }), 400

        if temperature is not None and not (-100 <= temperature <= 150):
            return jsonify({
                "success": False,
                "error":   "temperature must be between -100 and 150 C.",
            }), 400

        if battery is not None and not (0 <= battery <= 100):
            return jsonify({
                "success": False,
                "error":   "battery_level must be between 0 and 100.",
            }), 400

        if signal is not None and not (0 <= signal <= 100):
            return jsonify({
                "success": False,
                "error":   "signal_strength must be between 0 and 100.",
            }), 400

        if status is not None and status not in _STATUSES:
            return jsonify({
                "success": False,
                "error":   f"subsystem_status must be one of: {', '.join(_STATUSES)}.",
            }), 400

        record    = _build_record(
            temperature      = temperature,
            battery_level    = battery,
            signal_strength  = signal,
            subsystem_status = status,
        )
        record.id = save_telemetry(record)
        _stats_cache.invalidate()
        _latest_cache.invalidate()   # a new record changes what "latest" means

        return jsonify({"success": True, "data": record.to_dict()}), 201

    except ValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except DatabaseError as exc:
        # v3.2: log the real exception internally but return a generic message
        # so we never leak table names, column names, or file paths to callers.
        logger.error("DB error on POST /telemetry: %s", exc)
        return jsonify({"success": False, "error": "Database unavailable. Please try again later."}), 503


@app.route("/telemetry/latest")
def telemetry_latest():
    """
    Returns the single most-recent telemetry record.

    Cache strategy (two-level, write-through invalidation):
      Level 1 -- _latest_cache: serve from memory with zero DB queries.
      Level 2 -- database: on a miss, query and populate the cache.

    The cache is invalidated eagerly on every write endpoint, so it never
    returns stale data after a POST or DELETE regardless of TTL time left.

    Response contract:
      200 + "status": "ok"    -- record found (from cache or DB)
      404 + "status": "empty" -- database has no records yet
    """
    try:
        cached = _latest_cache.get()
        if cached is not None:
            logger.info("Cache hit on /telemetry/latest")
            return jsonify({
                "success": True,
                "status":  "ok",
                "cached":  True,
                "data":    cached,
            }), 200

        logger.info("Cache miss on /telemetry/latest -- querying database")
        row = get_latest_telemetry()

        if row is None:
            logger.warning("No telemetry records found in database")
            return jsonify({
                "success": False,
                "status":  "empty",
                "data":    None,
                "message": "No telemetry data available. POST /telemetry to create the first reading.",
            }), 404

        record_dict = row.to_dict()
        _latest_cache.set(record_dict)

        return jsonify({
            "success": True,
            "status":  "ok",
            "cached":  False,
            "data":    record_dict,
        }), 200

    except DatabaseError as exc:
        logger.error("DB error on GET /telemetry/latest: %s", exc)
        return jsonify({"success": False, "error": "Database unavailable. Please try again later."}), 503


@app.route("/telemetry/<int:record_id>")
def telemetry_get_one(record_id: int):
    """Returns the single record with the given ID, or 404 if not found."""
    try:
        record = get_by_id(record_id)
        if record is None:
            return jsonify({
                "success": False,
                "data":    None,
                "error":   f"No record found with id={record_id}.",
            }), 404
        return jsonify({"success": True, "data": record.to_dict()})

    except DatabaseError as exc:
        logger.error("DB error fetching id=%s: %s", record_id, exc)
        return jsonify({"success": False, "error": "Database unavailable. Please try again later."}), 503


@app.route("/telemetry/bulk", methods=["POST"])
def telemetry_bulk():
    """
    Generates N telemetry readings and inserts them all in one fast batch.

    Query parameter:
        count -- number of readings to generate (default: 10, max: 500)

    Example: POST /telemetry/bulk?count=100
    """
    try:
        count    = min(500, max(1, int(request.args.get("count", 10))))
        records  = [_build_record() for _ in range(count)]
        inserted = bulk_save_telemetry(records)
        _stats_cache.invalidate()
        _latest_cache.invalidate()   # bulk insert changes what "latest" means

        return jsonify({
            "success": True,
            "data": {
                "records_inserted": inserted,
                "message": f"Generated and saved {inserted} telemetry readings.",
            },
        }), 201

    except ValueError:
        return jsonify({"success": False, "error": "'count' must be a positive integer."}), 400
    except ValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except DatabaseError as exc:
        logger.error("DB error on POST /telemetry/bulk: %s", exc)
        return jsonify({"success": False, "error": "Database unavailable. Please try again later."}), 503


@app.route("/telemetry/history")
def telemetry_history():
    """
    Paginated list of records, newest first.

    v3.2: payload moved under "data" key to match the unified response
    contract. Previously used "records" at the top level.

    Query parameters:
        page  -- page number (default: 1)
        limit -- records per page (default: 20, max: 100)
    """
    try:
        limit, offset  = _parse_pagination()
        records, total = get_telemetry_page(limit=limit, offset=offset)
        return jsonify({
            "success":    True,
            "pagination": _pagination_meta(total, limit, offset),
            "data":       [r.to_dict() for r in records],  # v3.2: was "records"
        })
    except ValueError:
        return jsonify({"success": False, "error": "'page' and 'limit' must be integers."}), 400
    except DatabaseError as exc:
        logger.error("DB error on /telemetry/history: %s", exc)
        return jsonify({"success": False, "error": "Database unavailable. Please try again later."}), 503


@app.route("/telemetry/search")
def telemetry_search():
    """
    Filtered search across stored telemetry records.

    All query parameters are optional:
        status, min_battery, max_battery, min_temp, max_temp,
        from_ts (ISO 8601), to_ts (ISO 8601), page, limit

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
            status      = request.args.get("status")  or None,
            min_battery = opt_int("min_battery"),
            max_battery = opt_int("max_battery"),
            min_temp    = opt_float("min_temp"),
            max_temp    = opt_float("max_temp"),
            from_ts     = request.args.get("from_ts") or None,
            to_ts       = request.args.get("to_ts")   or None,
            limit       = limit,
            offset      = offset,
        )
        return jsonify({
            "success":    True,
            "pagination": _pagination_meta(total, limit, offset),
            "data":       [r.to_dict() for r in records],  # v3.2: was "records"
        })

    except ValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except ValueError:
        return jsonify({"success": False, "error": "Numeric parameters must be valid numbers."}), 400
    except DatabaseError as exc:
        logger.error("DB error on /telemetry/search: %s", exc)
        return jsonify({"success": False, "error": "Database unavailable. Please try again later."}), 503


@app.route("/telemetry/anomalies")
def telemetry_anomalies():
    """
    Returns the most recent non-nominal records (warning + critical).

    v3.2: payload moved under "data" to match the unified response contract.
    Previously used "records" at the top level alongside a separate "count".
    The count is preserved as a convenience field.
    """
    try:
        limit   = min(100, int(request.args.get("limit", 20)))
        records = get_anomalies(limit=limit)
        return jsonify({
            "success": True,
            "count":   len(records),                       # convenience field
            "data":    [r.to_dict() for r in records],    # v3.2: was "records"
        })
    except ValueError:
        return jsonify({"success": False, "error": "'limit' must be an integer."}), 400
    except DatabaseError as exc:
        logger.error("DB error on /telemetry/anomalies: %s", exc)
        return jsonify({"success": False, "error": "Database unavailable. Please try again later."}), 503


@app.route("/telemetry/stats")
def telemetry_stats():
    """
    Aggregate statistics with TTL caching.

    v3.2: payload moved under "data" to match the unified response contract.
    Previously used "stats" at the top level.

    The "cached" field tells you whether the response came from memory or a
    fresh database scan -- useful for debugging and observability.
    """
    try:
        cached = _stats_cache.get()
        if cached is not None:
            return jsonify({"success": True, "cached": True,  "data": cached})  # v3.2: was "stats"

        stats = get_telemetry_stats()
        _stats_cache.set(stats)
        return jsonify({"success": True, "cached": False, "data": stats})       # v3.2: was "stats"

    except DatabaseError as exc:
        logger.error("DB error on /telemetry/stats: %s", exc)
        return jsonify({"success": False, "error": "Database unavailable. Please try again later."}), 503


@app.route("/telemetry/export.csv")
def telemetry_export_csv():
    """
    Returns all telemetry records as a downloadable CSV file.

    The Content-Disposition header tells the browser to download the
    response as a file rather than displaying it inline.

    Try it in your browser: visit /telemetry/export.csv -- it downloads!
    """
    try:
        columns, rows = get_all_rows_for_export()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        writer.writerows(rows)
        output.seek(0)

        filename = f"telemetry_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            output.getvalue(),
            mimetype = "text/csv",
            headers  = {"Content-Disposition": f"attachment; filename={filename}"},
        )

    except DatabaseError as exc:
        logger.error("DB error on /telemetry/export.csv: %s", exc)
        return jsonify({"success": False, "error": "Database unavailable. Please try again later."}), 503


@app.route("/telemetry/old", methods=["DELETE"])
def telemetry_delete_old():
    """
    Prunes the oldest records, keeping only the most recent N.

    Query parameter:
        keep -- how many recent records to preserve (default: 1000)

    Example: DELETE /telemetry/old?keep=500
    """
    try:
        keep    = max(1, int(request.args.get("keep", 1000)))
        deleted = delete_old_records(keep_last_n=keep)
        if deleted:
            _stats_cache.invalidate()
            _latest_cache.invalidate()   # deleting old records may change "latest"

        return jsonify({
            "success": True,
            "data": {
                "records_deleted": deleted,
                "records_kept":    keep,
                "message": f"Deleted {deleted} record(s)." if deleted
                           else "No records needed pruning.",
            },
        })
    except ValueError:
        return jsonify({"success": False, "error": "'keep' must be a positive integer."}), 400
    except DatabaseError as exc:
        logger.error("DB error on DELETE /telemetry/old: %s", exc)
        return jsonify({"success": False, "error": "Database unavailable. Please try again later."}), 503


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info(
        "Starting Space Dogs Telemetry API  port=%s  debug=%s  rate_limit=%s/min",
        PORT, DEBUG, RATE_LIMIT,
    )
    app.run(debug=DEBUG, port=PORT, host="0.0.0.0")