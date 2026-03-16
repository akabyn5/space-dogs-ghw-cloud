import sqlite3


def init_db():
    """
    Initializes the telemetry database and creates the telemetry table
    if it does not already exist.
    """

    # Create connection to database file
    conn = sqlite3.connect("telemetry.db")

    # Create a cursor to execute SQL commands
    cursor = conn.cursor()

    # Create telemetry table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        temperature REAL,
        battery_level INTEGER,
        signal_strength INTEGER,
        timestamp TEXT,
        subsystem_status TEXT
    )
    """)

    # Save changes
    conn.commit()

    # Close connection
    conn.close()