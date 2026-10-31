
import sqlite3
from pathlib import Path
import json
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "order_to_cash.db"
OUTPUT_DIR = BASE_DIR / "outputs"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def detect_overdue_invoices(connection):
    query = """
        SELECT
            i.invoice_id,
            i.account_id,
            i.due_date,
            i.total_amount,
            COALESCE(SUM(pa.allocated_amount), 0) AS total_paid,
            i.total_amount - COALESCE(SUM(pa.allocated_amount), 0)
                AS outstanding,
            CAST(
                julianday(date('now')) - julianday(i.due_date)
                AS INTEGER
            ) AS days_overdue
        FROM Invoice i
        LEFT JOIN PaymentAllocation pa
            ON i.invoice_id = pa.invoice_id
        WHERE i.status NOT IN ('DRAFT', 'VOID')
          AND date(i.due_date) < date('now')
        GROUP BY i.invoice_id
        HAVING outstanding > 0
        ORDER BY days_overdue DESC
    """

    return connection.execute(query).fetchall()




def detect_uninvoiced_deliveries(connection):
    query = """
        WITH delivered AS (
            SELECT
                sl.order_line_id,
                SUM(sl.shipped_quantity) AS quantity
            FROM ShipmentLine sl
            JOIN Shipment s
                ON sl.shipment_id = s.shipment_id
            WHERE s.status = 'DELIVERED'
            GROUP BY sl.order_line_id
        ),
        invoiced AS (
            SELECT
                il.order_line_id,
                SUM(il.invoiced_quantity) AS quantity
            FROM InvoiceLine il
            JOIN Invoice i
                ON il.invoice_id = i.invoice_id
            WHERE i.status NOT IN ('DRAFT', 'VOID')
            GROUP BY il.order_line_id
        )
        SELECT
            ol.order_line_id,
            ol.order_id,
            ol.product_name,
            d.quantity AS delivered_quantity,
            COALESCE(i.quantity, 0) AS invoiced_quantity,
            d.quantity - COALESCE(i.quantity, 0)
                AS uninvoiced_quantity,
            (d.quantity - COALESCE(i.quantity, 0))
                * ol.unit_price AS estimated_value_paise
        FROM delivered d
        JOIN OrderLine ol
            ON d.order_line_id = ol.order_line_id
        LEFT JOIN invoiced i
            ON d.order_line_id = i.order_line_id
        WHERE d.quantity > COALESCE(i.quantity, 0)
        ORDER BY estimated_value_paise DESC
    """
    return connection.execute(query).fetchall()


def detect_old_disputes(connection):
    query = """
        SELECT
            dispute_id,
            invoice_id,
            reason,
            status,
            opened_date,
            CAST(
                julianday(date('now')) -
                julianday(opened_date)
                AS INTEGER
            ) AS days_open
        FROM Dispute
        WHERE status IN ('OPEN', 'UNDER_REVIEW')
          AND date(opened_date) <= date('now', '-30 days')
        ORDER BY days_open DESC
    """

    return connection.execute(query).fetchall()


def main():
    connection = get_connection()

    try:
        # 1. Detect overdue invoices
        overdue = detect_overdue_invoices(connection)

        print("\n========== ANOMALY DETECTION REPORT ==========")

        print("\n1. OVERDUE INVOICES")
        print("Overdue invoices found:", len(overdue))

        for row in overdue[:10]:
            invoice_id, account_id, due_date, total_amount, total_paid, outstanding, days_overdue = row

            print(
                f"{invoice_id} | "
                f"Outstanding: INR {outstanding / 100:,.2f} | "
                f"Days overdue: {days_overdue}"
            )

        # 2. Detect potentially uninvoiced deliveries
        uninvoiced = detect_uninvoiced_deliveries(connection)

        total_quantity = sum(row[5] for row in uninvoiced)
        total_value_paise = sum(row[6] for row in uninvoiced)

        print("\n2. POTENTIALLY UNINVOICED DELIVERIES")
        print("Affected order lines:", len(uninvoiced))
        print("Potentially uninvoiced units:", total_quantity)
        print(
            f"Estimated potential billing gap: "
            f"INR {total_value_paise / 100:,.2f}"
        )

        print("\nTop 5 potential billing gaps:")

        for row in uninvoiced[:5]:
            print(
                f"Order: {row[1]} | "
                f"Product: {row[2]} | "
                f"Uninvoiced quantity: {row[5]} | "
                f"Estimated value: INR {row[6] / 100:,.2f}"
            )
            # 3. Detect long-unresolved disputes
        old_disputes = detect_old_disputes(connection)
        open_count = sum(1 for row in old_disputes if row[3] == "OPEN")
        review_count = sum(1 for row in old_disputes if row[3] == "UNDER_REVIEW")
        print("Open disputes:", open_count)
        print("Disputes under review:", review_count)
        print("\n3. LONG-UNRESOLVED DISPUTES")
        print("Disputes open for more than 30 days:", len(old_disputes))

        for row in old_disputes[:10]:
            dispute_id, invoice_id, reason, status, opened_date, days_open = row

            print(
                f"{dispute_id} | "
                f"Invoice: {invoice_id} | "
                f"Reason: {reason} | "
                f"Status: {status} | "
                f"Days open: {days_open}"
            )
            # 4. Save anomaly results to JSON

        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "overdue_invoices": len(overdue),
                "potentially_uninvoiced_order_lines": len(uninvoiced),
                "potentially_uninvoiced_units": total_quantity,
                "estimated_billing_gap_inr": round(
                    total_value_paise / 100, 2
                ),
                "old_disputes": len(old_disputes),
                "open_disputes": open_count,
                "under_review_disputes": review_count
            },
            "overdue_invoice_details": [
                {
                    "invoice_id": row[0],
                    "account_id": row[1],
                    "due_date": row[2],
                    "outstanding_inr": round(row[5] / 100, 2),
                    "days_overdue": row[6]
                }
                for row in overdue
            ],
            "uninvoiced_delivery_details": [
                {
                    "order_line_id": row[0],
                    "order_id": row[1],
                    "product_name": row[2],
                    "delivered_quantity": row[3],
                    "invoiced_quantity": row[4],
                    "uninvoiced_quantity": row[5],
                    "estimated_value_inr": round(row[6] / 100, 2)
                }
                for row in uninvoiced
            ],
            "old_dispute_details": [
                {
                    "dispute_id": row[0],
                    "invoice_id": row[1],
                    "reason": row[2],
                    "status": row[3],
                    "opened_date": row[4],
                    "days_open": row[5]
                }
                for row in old_disputes
            ]
        }

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        report_path = OUTPUT_DIR / "anomaly_report.json"

        with open(report_path, "w", encoding="utf-8") as file:
            json.dump(report, file, indent=4)

        print("\nAnomaly report saved to:", report_path)
    finally:
        connection.close()


if __name__ == "__main__":
    main()


