
import sqlite3
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).resolve().parents[2]
SCHEMA_PATH = BASE_DIR / "src" / "database" / "schema.sql"
DB_PATH = BASE_DIR / "data" / "order_to_cash.db"


def initialize_database():
    """Create the SQLite database and all required tables."""

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        connection.executescript(schema)

        print("Database created successfully!")

        cursor = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)

        print("\nCreated tables:")

        for row in cursor.fetchall():
            print("-", row[0])

    finally:
        connection.close()
def reset_database():
    if not DB_PATH.exists():
        print("Database does not exist. Nothing to reset.")
        return

    connection = sqlite3.connect(DB_PATH)

    try:
        connection.execute("PRAGMA foreign_keys = OFF")

        tables = connection.execute("""
            SELECT name FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
        """).fetchall()

        for (table_name,) in tables:
            connection.execute(f'DROP TABLE IF EXISTS "{table_name}"')

        connection.commit()
        print("Database tables reset successfully!")

    finally:
        connection.close()

def reset_and_initialize_database():
    reset_database()
    initialize_database()

def check_shipments():
    connection = sqlite3.connect(DB_PATH)

    print("Shipment statuses:")

    results = connection.execute(
        "SELECT status, COUNT(*) FROM Shipment GROUP BY status"
    ).fetchall()

    print(results)

    delivered = connection.execute("""
        SELECT COUNT(*)
        FROM ShipmentLine sl
        JOIN Shipment s
        ON sl.shipment_id = s.shipment_id
        WHERE s.status = 'DELIVERED'
    """).fetchone()[0]

    print("Delivered shipment lines:", delivered)

    connection.close()


if __name__ == "__main__":
    initialize_database()


    

