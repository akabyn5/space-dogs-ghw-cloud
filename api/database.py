"""
database.py — Space Dogs Telemetry Dashboard  (v3)
====================================================
All database logic lives here. app.py should never import sqlite3 directly.

New in v3:
  - Schema migrations: the database can evolve safely without losing data.
  - ValidationError + validate_record(): bad data is rejected *before* SQL.
  - bulk_save_telemetry(): insert many records in one fast transaction.
  - search_telemetry(): dynamic filtering by status, battery, temp, date range.
"""

import sqlite3
import os
import logging
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.environ.get(
    "TELEMETRY_DB_PATH",
    os.path.join(BASE_DIR, "telemetry.db"),
)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DatabaseError(Exception):
    """
    Raised when a SQLite operation fails unexpectedly.
    Wrapping sqlite3's own exceptions in this one type means callers only
    need to know about DatabaseError — they never need to import sqlite3.
    """
    pass


class ValidationError(Exception):
    """
    Raised when incoming data fails business-rule checks *before* any SQL
    is attempted.

    Why have a separate exception just for validation?
    Because it maps to a different HTTP status code. A DatabaseError means
    something broke on the server → HTTP 503. A ValidationError means the
    *caller* sent bad data → HTTP 400 Bad Request. Keeping them separate
    lets app.py give the right status code without inspecting error messages.
    """
    pass


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

# The set of allowed subsystem status values. Storing it here (in the data
# layer) keeps the business rule in one place. app.py and tests can import
# this constant instead of hard-coding strings in multiple files.
VALID_STATUSES = frozenset({"nominal", "warning", "critical"})


@dataclass
class TelemetryRecord:
    """
    Typed representation of one row in the telemetry table.

    Using a dataclass gives us __init__, __repr__, and __eq__ for free.
    'id' is Optional[int] because a new record has no ID until SQLite assigns
    one on INSERT.
    """
    temperature:      float
    battery_level:    int
    signal_strength:  int
    timestamp:        str
    subsystem_status: str
    id:               Optional[int] = None

    def to_dict(self) -> dict:
        """Plain dict for jsonify(), with 'id' placed first for readability."""
        d = asdict(self)
        return {"id": d.pop("id"), **d}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_record(record: TelemetryRecord) -> None:
    """
    Checks that a TelemetryRecord obeys all business rules.
    Raises ValidationError with a human-readable message on the *first*
    problem found — fast feedback for the caller.

    Why validate in Python when SQLite CHECK constraints already exist?
    Two reasons:
      1. Python validation runs *before* a connection is opened, saving
         a round-trip to the database file entirely.
      2. Python can produce friendlier error messages ("temperature must
         be between -100 and 150") than SQLite's generic constraint errors.
    Think of Python validation as the first gate and SQL constraints as the
    last-resort safety net behind it.

    Raises:
        ValidationError: describing exactly which field is wrong and why.
    """
    if not (-100.0 <= record.temperature <= 150.0):
        raise ValidationError(
            f"temperature={record.temperature} is outside the realistic range "
            f"[-100.0, 150.0] °C."
        )

    if not (0 <= record.battery_level <= 100):
        raise ValidationError(
            f"battery_level={record.battery_level} must be between 0 and 100."
        )

    if not (0 <= record.signal_strength <= 100):
        raise ValidationError(
            f"signal_strength={record.signal_strength} must be between 0 and 100."
        )

    if not record.timestamp:
        raise ValidationError("timestamp cannot be empty.")

    if record.subsystem_status not in VALID_STATUSES:
        raise ValidationError(
            f"subsystem_status='{record.subsystem_status}' is not valid. "
            f"Allowed values: {sorted(VALID_STATUSES)}."
        )


# ---------------------------------------------------------------------------
# Schema migrations
# ---------------------------------------------------------------------------

# A migration is a tuple of (version_number, sql_statement_to_run).
# To add a new column in the future you simply append a new tuple here —
# the migration runner below will detect that the database is behind and
# apply only the missing steps, in order.
#
# CRITICAL RULE: never edit an existing migration. If you change migration
# number 1's SQL after it has already run on a production database, that
# database won't know it needs to re-run anything. Always ADD a new entry.
_MIGRATIONS: list[tuple[int, str]] = [
    (1, """
        CREATE TABLE IF NOT EXISTS telemetry (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            temperature      REAL    NOT NULL,
            battery_level    INTEGER NOT NULL
                                     CHECK (battery_level  BETWEEN 0 AND 100),
            signal_strength  INTEGER NOT NULL
                                     CHECK (signal_strength BETWEEN 0 AND 100),
            timestamp        TEXT    NOT NULL,
            subsystem_status TEXT    NOT NULL DEFAULT 'nominal'
        )
    """),
    (2, "CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry (timestamp DESC)"),
    (3, "CREATE INDEX IF NOT EXISTS idx_telemetry_status    ON telemetry (subsystem_status)"),
    # Future example — safe to add later without touching existing entries:
    # (4, "ALTER TABLE telemetry ADD COLUMN altitude_km REAL DEFAULT NULL"),
]


def _get_schema_version(conn: sqlite3.Connection) -> int:
    """
    Returns the current migration version stored in the database.
    Returns 0 if the version table doesn't exist yet (fresh database).
    This is a private helper used only by _run_migrations().
    """
    try:
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        return row[0] if row[0] is not None else 0
    except sqlite3.OperationalError:
        # The schema_version table doesn't exist yet — this is a brand-new DB.
        return 0


def _run_migrations(conn: sqlite3.Connection) -> None:
    """
    Applies any migrations that haven't been run yet, in version order.

    The schema_version table acts as a ledger: each time a migration runs
    successfully, we record its version number. On the next startup, we
    read the highest recorded version and skip everything up to that point.

    This is the standard pattern used by professional migration tools like
    Flyway, Alembic, and Django's manage.py migrate — we're implementing
    the same idea from scratch to understand how it works.
    """
    # Ensure the ledger table exists before we try to read from it.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version    INTEGER PRIMARY KEY,
            applied_at TEXT    NOT NULL
        )
    """)
    conn.commit()

    current = _get_schema_version(conn)

    for version, sql in _MIGRATIONS:
        if version <= current:
            continue   # already applied — skip it

        logger.info("Applying database migration v%s …", version)
        conn.executescript(sql)   # executescript auto-commits after each statement
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
            (version,),
        )
        conn.commit()
        logger.info("Migration v%s applied successfully.", version)


# ---------------------------------------------------------------------------
# Connection helper (private)
# ---------------------------------------------------------------------------

@contextmanager
def _get_connection():
    """
    Opens a SQLite connection, configures it, yields it, then always closes it.
    Commits on success, rolls back on any exception.
    Re-raises sqlite3 errors as DatabaseError so callers have one type to handle.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        # WAL mode: lets multiple readers run alongside a writer simultaneously.
        conn.execute("PRAGMA journal_mode=WAL")
        # foreign_keys=ON enforces any REFERENCES constraints we add in the future.
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
        conn.commit()

    except sqlite3.Error as exc:
        if conn:
            conn.rollback()
        raise DatabaseError(f"Database operation failed: {exc}") from exc

    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Runs all pending schema migrations and brings the database up to date.
    Safe to call every startup — migrations that already ran are skipped.
    """
    # We open a raw connection here (not via the context manager) because
    # _run_migrations() manages its own commits for each migration step.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        _run_migrations(conn)
    finally:
        conn.close()

    logger.info("Database ready at: %s", DB_PATH)


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def save_telemetry(record: TelemetryRecord) -> int:
    """
    Validates then inserts one TelemetryRecord. Returns the new row's ID.

    Raises:
        ValidationError: if the record's values break business rules.
        DatabaseError:   if the INSERT fails.
    """
    validate_record(record)   # ← always validate BEFORE opening a connection

    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO telemetry
                (temperature, battery_level, signal_strength,
                 timestamp,   subsystem_status)
            VALUES
                (:temperature, :battery_level, :signal_strength,
                 :timestamp,   :subsystem_status)
            """,
            asdict(record),
        )
        new_id = cursor.lastrowid

    logger.debug("Saved record id=%s  status=%s", new_id, record.subsystem_status)
    return new_id


def bulk_save_telemetry(records: list[TelemetryRecord]) -> int:
    """
    Validates and inserts many TelemetryRecords in a single transaction.

    Why is this much faster than calling save_telemetry() in a loop?
    Every call to save_telemetry() opens a connection, sends SQL to SQLite,
    commits (which flushes data to disk), and closes the connection. Disk
    flushes are expensive — typically 5–20 ms each. With 100 records that's
    up to 2 seconds just in flush overhead.

    executemany() sends all rows in one batch and flushes to disk exactly
    once at the end. For 100 records it's often 10-50× faster.

    Args:
        records: List of TelemetryRecord instances (each id should be None).

    Returns:
        The number of rows successfully inserted.

    Raises:
        ValidationError: if *any* record fails validation (checked before
                         any SQL is attempted, so nothing is partially inserted).
        DatabaseError:   if the batch INSERT fails.
    """
    if not records:
        return 0

    # Validate ALL records first. If even one is invalid we raise immediately
    # and no database connection is opened. This is called "fail fast" — it's
    # better to reject the whole batch early than to insert 99 rows and then
    # fail on row 100, leaving the database in an inconsistent state.
    for i, record in enumerate(records):
        try:
            validate_record(record)
        except ValidationError as exc:
            raise ValidationError(f"Record at index {i} is invalid: {exc}") from exc

    rows_as_dicts = [asdict(r) for r in records]

    with _get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO telemetry
                (temperature, battery_level, signal_strength,
                 timestamp,   subsystem_status)
            VALUES
                (:temperature, :battery_level, :signal_strength,
                 :timestamp,   :subsystem_status)
            """,
            rows_as_dicts,
        )

    logger.info("Bulk-inserted %d telemetry records.", len(records))
    return len(records)


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def get_by_id(record_id: int) -> Optional[TelemetryRecord]:
    """
    Returns the record with the given primary key, or None if not found.
    app.py uses the None return to generate a 404 response cleanly.
    """
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM telemetry WHERE id = ?", (record_id,)
        ).fetchone()
    return TelemetryRecord(**dict(row)) if row else None


def get_telemetry_page(
    limit: int  = 50,
    offset: int = 0,
) -> tuple[list[TelemetryRecord], int]:
    """
    Returns one page of records (newest first) plus the total row count.
    The total count lets the caller calculate 'Page 2 of 47' without a
    second query.
    """
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM telemetry ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]

    return [TelemetryRecord(**dict(r)) for r in rows], total


def search_telemetry(
    status:      Optional[str]   = None,
    min_battery: Optional[int]   = None,
    max_battery: Optional[int]   = None,
    min_temp:    Optional[float] = None,
    max_temp:    Optional[float] = None,
    from_ts:     Optional[str]   = None,   # ISO 8601 string, e.g. "2026-03-15T00:00:00"
    to_ts:       Optional[str]   = None,
    limit:       int             = 50,
    offset:      int             = 0,
) -> tuple[list[TelemetryRecord], int]:
    """
    Returns filtered telemetry records matching all provided criteria,
    plus the total count of matching rows (for pagination).

    How does dynamic query building work?
    We start with a base query and then *conditionally* append WHERE clauses
    only for the filters that were actually provided. This is safer than
    building SQL strings with f-strings (which risks SQL injection) because
    we always use '?' placeholders and pass values separately as a list.

    Example calls:
        search_telemetry(status="warning")
        search_telemetry(min_battery=20, max_battery=50, min_temp=35.0)
        search_telemetry(from_ts="2026-03-15T00:00:00", to_ts="2026-03-15T23:59:59")

    Raises:
        ValidationError: if status is provided but not a valid value.
        DatabaseError:   on SQLite errors.
    """
    if status is not None and status not in VALID_STATUSES:
        raise ValidationError(
            f"Invalid status filter '{status}'. "
            f"Allowed: {sorted(VALID_STATUSES)}."
        )

    # We build the WHERE clause as a list of condition strings, then JOIN
    # them with AND. This is cleaner than nesting if/else chains and easier
    # to extend when new filters are added in the future.
    conditions: list[str] = []
    params:     list      = []

    if status is not None:
        conditions.append("subsystem_status = ?")
        params.append(status)

    if min_battery is not None:
        conditions.append("battery_level >= ?")
        params.append(min_battery)

    if max_battery is not None:
        conditions.append("battery_level <= ?")
        params.append(max_battery)

    if min_temp is not None:
        conditions.append("temperature >= ?")
        params.append(min_temp)

    if max_temp is not None:
        conditions.append("temperature <= ?")
        params.append(max_temp)

    if from_ts is not None:
        conditions.append("timestamp >= ?")
        params.append(from_ts)

    if to_ts is not None:
        conditions.append("timestamp <= ?")
        params.append(to_ts)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with _get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM telemetry
            {where_clause}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()

        total = conn.execute(
            f"SELECT COUNT(*) FROM telemetry {where_clause}",
            params,
        ).fetchone()[0]

    return [TelemetryRecord(**dict(r)) for r in rows], total


def get_anomalies(limit: int = 50) -> list[TelemetryRecord]:
    """Returns the most recent non-nominal records (warning + critical)."""
    records, _ = search_telemetry(limit=limit)   # reuse search with no filter first...
    # Actually query specifically — we want any non-nominal status:
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM telemetry
            WHERE  subsystem_status != 'nominal'
            ORDER  BY id DESC
            LIMIT  ?
            """,
            (limit,),
        ).fetchall()
    return [TelemetryRecord(**dict(r)) for r in rows]


def get_telemetry_stats() -> dict:
    """Aggregate statistics in one SQL query (far cheaper than pulling all rows)."""
    with _get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*)                           AS total_records,
                ROUND(AVG(temperature),      2)    AS avg_temperature,
                ROUND(MIN(temperature),      2)    AS min_temperature,
                ROUND(MAX(temperature),      2)    AS max_temperature,
                ROUND(AVG(battery_level),    1)    AS avg_battery,
                MIN(battery_level)                 AS min_battery,
                ROUND(AVG(signal_strength),  1)    AS avg_signal,
                MIN(signal_strength)               AS min_signal,
                MIN(timestamp)                     AS first_reading,
                MAX(timestamp)                     AS last_reading,
                SUM(subsystem_status != 'nominal') AS anomaly_count
            FROM telemetry
            """
        ).fetchone()
    return dict(row) if row else {}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def get_all_rows_for_export() -> tuple[list[str], list[tuple]]:
    """
    Returns (column_names, list_of_raw_tuples) for CSV export.

    We return raw tuples (not TelemetryRecord objects) because the csv
    module works directly with sequences, avoiding an extra conversion step.
    Returning column names separately means the CSV header is always
    consistent with the actual query columns, even if we add columns later.
    """
    columns = [
        "id", "timestamp", "temperature", "battery_level",
        "signal_strength", "subsystem_status",
    ]
    with _get_connection() as conn:
        # Turn off Row factory temporarily to get plain tuples
        conn.row_factory = None
        rows = conn.execute(
            f"SELECT {', '.join(columns)} FROM telemetry ORDER BY id ASC"
        ).fetchall()
    return columns, rows


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

def delete_old_records(keep_last_n: int = 1000) -> int:
    """
    Deletes all but the most recent `keep_last_n` records.
    Returns the number of rows deleted (0 if nothing needed pruning).
    """
    with _get_connection() as conn:
        result = conn.execute(
            """
            DELETE FROM telemetry
            WHERE id NOT IN (
                SELECT id FROM telemetry
                ORDER  BY id DESC
                LIMIT  ?
            )
            """,
            (keep_last_n,),
        )
        deleted = result.rowcount

    if deleted:
        logger.info("Pruned %d old records (kept last %d).", deleted, keep_last_n)
    return deleted