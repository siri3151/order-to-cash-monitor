import sqlite3
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

DB_PATH = BASE_DIR / "data" / "order_to_cash.db"

GROUND_TRUTH_PATH = (
    BASE_DIR / "data" / "ground_truth" / "ground_truth.json"
)


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def save_ground_truth(issues):
    GROUND_TRUTH_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(GROUND_TRUTH_PATH, "w", encoding="utf-8") as file:
        json.dump(issues, file, indent=4)

    print("Ground truth saved:", GROUND_TRUTH_PATH)

def inject_overbilling_anomaly(connection):
    cursor = connection.cursor()

    result = cursor.execute("""
        SELECT
            il.invoice_line_id,
            il.invoice_id,
            il.order_line_id,
            il.invoiced_quantity,
            il.unit_price,
            COALESCE((
                SELECT SUM(sl.shipped_quantity)
                FROM ShipmentLine sl
                JOIN Shipment s
                    ON sl.shipment_id = s.shipment_id
                WHERE sl.order_line_id = il.order_line_id
                  AND s.status = 'DELIVERED'
            ), 0) AS fulfilled_quantity
        FROM InvoiceLine il
        ORDER BY il.invoice_line_id
        LIMIT 1
    """).fetchone()

    if result is None or result[5] <= 0:
        raise ValueError("No suitable invoice line found for overbilling.")

    invoice_line_id, invoice_id, order_line_id, old_quantity, unit_price, fulfilled_quantity = result

    new_quantity = fulfilled_quantity + 1
    new_line_total = new_quantity * unit_price
    additional_amount = new_line_total - (old_quantity * unit_price)

    cursor.execute("""
        UPDATE InvoiceLine
        SET invoiced_quantity = ?,
            line_total = ?
        WHERE invoice_line_id = ?
    """, (new_quantity, new_line_total, invoice_line_id))

    cursor.execute("""
        UPDATE Invoice
        SET total_amount = total_amount + ?
        WHERE invoice_id = ?
    """, (additional_amount, invoice_id))

    print("Injected overbilling anomaly:", invoice_id)

    return {
        "anomaly_id": "ANOM-001",
        "issue_type": "INVOICE_EXCEEDS_FULFILLED_QUANTITY",
        "affected_record_id": invoice_id,
        "order_line_id": order_line_id,
        "expected_fulfilled_quantity": fulfilled_quantity,
        "actual_invoiced_quantity": new_quantity,
        "description": "Invoice quantity exceeds delivered quantity."
    }

def inject_duplicate_payment_allocation(connection):
    cursor = connection.cursor()

    result = cursor.execute("""
        SELECT
            payment_id,
            invoice_id,
            allocated_amount,
            allocation_date
        FROM PaymentAllocation
        ORDER BY allocation_id
        LIMIT 1
    """).fetchone()

    if result is None:
        raise ValueError("No payment allocation available.")

    payment_id, invoice_id, amount, allocation_date = result

    cursor.execute("""
        INSERT INTO PaymentAllocation (
            allocation_id,
            payment_id,
            invoice_id,
            allocated_amount,
            allocation_date
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        "ANOM-PA-001",
        payment_id,
        invoice_id,
        amount,
        allocation_date
    ))

    print("Injected duplicate payment allocation:", payment_id)

    return {
        "anomaly_id": "ANOM-002",
        "issue_type": "PAYMENT_ALLOCATED_TWICE",
        "affected_record_id": payment_id,
        "invoice_id": invoice_id,
        "duplicated_amount_paise": amount,
        "description": "The same payment allocation was recorded twice."
    }

def inject_closed_order_unpaid_anomaly(connection):
    cursor = connection.cursor()

    result = cursor.execute("""
        SELECT
            i.invoice_id,
            i.order_id,
            i.total_amount,
            COALESCE(SUM(pa.allocated_amount), 0) AS total_paid
        FROM Invoice i
        LEFT JOIN PaymentAllocation pa
            ON i.invoice_id = pa.invoice_id
        JOIN SalesOrder so
            ON i.order_id = so.order_id
        WHERE i.status NOT IN ('DRAFT', 'VOID')
          AND so.status != 'CLOSED'
        GROUP BY i.invoice_id
        HAVING total_paid < i.total_amount
        ORDER BY i.invoice_id
        LIMIT 1
    """).fetchone()

    if result is None:
        raise ValueError("No unpaid invoice available for anomaly.")

    invoice_id, order_id, total_amount, total_paid = result

    cursor.execute("""
        UPDATE SalesOrder
        SET status = 'CLOSED'
        WHERE order_id = ?
    """, (order_id,))

    print("Injected closed order with unpaid invoice:", order_id)

    return {
        "anomaly_id": "ANOM-003",
        "issue_type": "CLOSED_ORDER_WITH_UNPAID_INVOICE",
        "affected_record_id": order_id,
        "invoice_id": invoice_id,
        "invoice_amount_paise": total_amount,
        "paid_amount_paise": total_paid,
        "outstanding_amount_paise": total_amount - total_paid,
        "description": "Order closed while its invoice has an unpaid balance."
    }

def inject_invalid_status_transition(connection):

    order = connection.execute("""
        SELECT order_id
        FROM SalesOrder
        WHERE status = 'CONFIRMED'
        LIMIT 1
    """).fetchone()

    if not order:
        raise ValueError("No confirmed order found")

    order_id = order[0]

    connection.execute("""
        INSERT INTO StatusEvent (
            event_id,
            entity_type,
            order_id,
            old_status,
            new_status,
            event_timestamp,
            actor,
            reason
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "ANOM-EVT-001",
        "SALES_ORDER",
        order_id,
        "CONFIRMED",
        "FULFILLED",
        "2026-10-31T12:00:00",
        "SYSTEM",
        "Deliberately skipped intermediate fulfillment state"
    ))

    return {
        "anomaly_id": "ANOM-004",
        "issue_type": "INVALID_STATUS_TRANSITION",
        "sales_order_id": order_id,
        "description": "Order moved directly from CONFIRMED to FULFILLED, skipping the intermediate fulfillment state."
    }

def inject_missing_dispute_adjustment(connection):
    cursor = connection.cursor()

    result = cursor.execute("""
        SELECT
            d.dispute_id,
            d.invoice_id,
            d.disputed_amount,
            da.adjustment_id
        FROM Dispute d
        JOIN DisputeAdjustment da
            ON d.dispute_id = da.dispute_id
        WHERE d.status IN ('OPEN', 'UNDER_REVIEW')
          AND da.status = 'POSTED'
        ORDER BY d.dispute_id
        LIMIT 1
    """).fetchone()

    if result is None:
        raise ValueError("No posted active dispute adjustment available.")

    dispute_id, invoice_id, disputed_amount, adjustment_id = result

    cursor.execute("""
        DELETE FROM DisputeAdjustment
        WHERE adjustment_id = ?
    """, (adjustment_id,))

    print("Injected missing dispute adjustment:", dispute_id)

    return {
        "anomaly_id": "ANOM-005",
        "issue_type": "DISPUTE_NOT_REFLECTED_IN_RECEIVABLES",
        "affected_record_id": dispute_id,
        "invoice_id": invoice_id,
        "disputed_amount_paise": disputed_amount,
        "description": "An active dispute has no posted receivables adjustment."
    }

def main():
    connection = get_connection()

    try:
        issues = []

        print("\nINJECTING FIVE DELIBERATE ANOMALIES")

        issues.append(inject_overbilling_anomaly(connection))
        issues.append(inject_duplicate_payment_allocation(connection))
        issues.append(inject_closed_order_unpaid_anomaly(connection))
        issues.append(inject_invalid_status_transition(connection))
        issues.append(inject_missing_dispute_adjustment(connection))

        connection.commit()

        save_ground_truth(issues)

        print("\nAnomaly injection completed!")
        print("Total anomalies injected:", len(issues))

    except Exception as error:
        connection.rollback()
        print("Anomaly injection failed:", error)
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()

