
import sqlite3
from pathlib import Path

# Project database location
BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "order_to_cash.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def check_shipped_quantity(connection):
    """Check whether shipped quantity exceeds ordered quantity."""

    query = """
        SELECT
            ol.order_line_id,
            ol.ordered_quantity,
            COALESCE(SUM(sl.shipped_quantity), 0) AS total_shipped
        FROM OrderLine ol
        LEFT JOIN ShipmentLine sl
            ON ol.order_line_id = sl.order_line_id
        GROUP BY ol.order_line_id, ol.ordered_quantity
        HAVING total_shipped > ol.ordered_quantity
    """

    return connection.execute(query).fetchall()


def check_invoiced_quantity(connection):
    """Check whether invoiced quantity exceeds delivered quantity."""

    query = """
        SELECT
            ol.order_line_id,
            COALESCE(delivered.total_delivered, 0) AS total_delivered,
            COALESCE(invoiced.total_invoiced, 0) AS total_invoiced
        FROM OrderLine ol

        LEFT JOIN (
            SELECT
                sl.order_line_id,
                SUM(sl.shipped_quantity) AS total_delivered
            FROM ShipmentLine sl
            JOIN Shipment s
                ON sl.shipment_id = s.shipment_id
            WHERE s.status = 'DELIVERED'
            GROUP BY sl.order_line_id
        ) delivered
            ON ol.order_line_id = delivered.order_line_id

        LEFT JOIN (
            SELECT
                il.order_line_id,
                SUM(il.invoiced_quantity) AS total_invoiced
            FROM InvoiceLine il
            JOIN Invoice i
                ON il.invoice_id = i.invoice_id
            WHERE i.status != 'VOID'
            GROUP BY il.order_line_id
        ) invoiced
            ON ol.order_line_id = invoiced.order_line_id

        WHERE total_invoiced > total_delivered
    """

    return connection.execute(query).fetchall()


def check_payment_allocations(connection):
    """Check whether allocations exceed the original payment amount."""

    query = """
        SELECT
            p.payment_id,
            p.amount,
            SUM(pa.allocated_amount) AS total_allocated
        FROM Payment p
        JOIN PaymentAllocation pa
            ON p.payment_id = pa.payment_id
        GROUP BY p.payment_id, p.amount
        HAVING total_allocated > p.amount
    """

    return connection.execute(query).fetchall()


def check_foreign_keys(connection):
    """Check database foreign-key integrity."""

    return connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()


def main():
    connection = get_connection()

    print("\\nDATA VALIDATION REPORT")
    print("=" * 40)

    checks = [
        ("Shipped quantity violations", check_shipped_quantity),
        ("Invoiced quantity violations", check_invoiced_quantity),
        ("Payment allocation violations", check_payment_allocations),
        ("Foreign key violations", check_foreign_keys),
    ]

    for title, check_function in checks:
        errors = check_function(connection)

        print(f"\\n{title}: {len(errors)}")

        if errors:
            print("Examples:")
            for error in errors[:5]:
                print(error)
        else:
            print("No violations found.")

    connection.close()


if __name__ == "__main__":
    main()
