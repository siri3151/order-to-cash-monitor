
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

def detect_overbilling(connection):
    query = """
        WITH delivered AS (
            SELECT
                sl.order_line_id,
                SUM(sl.shipped_quantity) AS fulfilled_quantity
            FROM ShipmentLine sl
            JOIN Shipment s
                ON sl.shipment_id = s.shipment_id
            WHERE s.status = 'DELIVERED'
            GROUP BY sl.order_line_id
        ),
        invoiced AS (
            SELECT
                il.order_line_id,
                SUM(il.invoiced_quantity) AS invoiced_quantity
            FROM InvoiceLine il
            JOIN Invoice i
                ON il.invoice_id = i.invoice_id
            WHERE i.status NOT IN ('DRAFT', 'VOID')
            GROUP BY il.order_line_id
        )
        SELECT
            i.order_line_id,
            ol.order_id,
            d.fulfilled_quantity,
            i.invoiced_quantity,
            i.invoiced_quantity - d.fulfilled_quantity
                AS excess_quantity
        FROM invoiced i
        JOIN delivered d
            ON i.order_line_id = d.order_line_id
        JOIN OrderLine ol
            ON i.order_line_id = ol.order_line_id
        WHERE i.invoiced_quantity > d.fulfilled_quantity
    """

    return connection.execute(query).fetchall()

def detect_duplicate_payment_allocations(connection):
    query = """
        SELECT
            payment_id,
            invoice_id,
            allocated_amount,
            allocation_date,
            COUNT(*) AS occurrence_count
        FROM PaymentAllocation
        GROUP BY
            payment_id,
            invoice_id,
            allocated_amount,
            allocation_date
        HAVING COUNT(*) > 1
    """

    return connection.execute(query).fetchall()

def detect_closed_orders_with_unpaid_invoices(connection):
    query = """
        SELECT
            so.order_id,
            i.invoice_id,
            i.total_amount,
            COALESCE(SUM(pa.allocated_amount), 0) AS total_paid,
            i.total_amount - COALESCE(SUM(pa.allocated_amount), 0)
                AS outstanding_amount
        FROM SalesOrder so
        JOIN Invoice i
            ON so.order_id = i.order_id
        LEFT JOIN PaymentAllocation pa
            ON i.invoice_id = pa.invoice_id
        WHERE so.status = 'CLOSED'
          AND i.status NOT IN ('DRAFT', 'VOID')
        GROUP BY so.order_id, i.invoice_id
        HAVING outstanding_amount > 0
    """

    return connection.execute(query).fetchall()

def detect_invalid_status_transitions(connection):
    query = """
        SELECT
            event_id,
            entity_type,
            order_id,
            old_status,
            new_status,
            event_timestamp
        FROM StatusEvent
        WHERE entity_type = 'SALES_ORDER'
          AND old_status = 'CONFIRMED'
          AND new_status = 'FULFILLED'
    """

    return connection.execute(query).fetchall()

def detect_unadjusted_disputes(connection):
    query = """
        SELECT
            d.dispute_id,
            d.invoice_id,
            d.disputed_amount,
            COALESCE(da.posted_amount, 0) AS posted_amount
        FROM Dispute d
        LEFT JOIN (
            SELECT
                dispute_id,
                SUM(adjusted_amount) AS posted_amount
            FROM DisputeAdjustment
            WHERE status = 'POSTED'
            GROUP BY dispute_id
        ) da
            ON d.dispute_id = da.dispute_id
        WHERE d.status IN ('OPEN', 'UNDER_REVIEW')
    """

    results = connection.execute(query).fetchall()

    unadjusted = []

    for row in results:
        dispute_id, invoice_id, disputed_amount, posted_amount = row

        if posted_amount == 0:
            unadjusted.append({
                "dispute_id": dispute_id,
                "invoice_id": invoice_id,
                "disputed_amount_paise": disputed_amount,
                "posted_adjustment_paise": posted_amount
            })

    return unadjusted 

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
                # 4. Detect the five required anomalies

        overbilling = detect_overbilling(connection)

        duplicate_allocations = (
            detect_duplicate_payment_allocations(connection)
        )

        closed_unpaid = (
            detect_closed_orders_with_unpaid_invoices(connection)
        )

        invalid_transitions = (
            detect_invalid_status_transitions(connection)
        )

        unadjusted_disputes = detect_unadjusted_disputes(connection)

        print("\n4. REQUIRED ANOMALY DETECTION")
        print("Invoice overbilling:", len(overbilling))
        print("Duplicate payment allocations:", len(duplicate_allocations))
        print("Closed orders with unpaid invoices:", len(closed_unpaid))
        print("Invalid status transitions:", len(invalid_transitions))
        print("Disputes missing adjustments:", len(unadjusted_disputes))
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
                "under_review_disputes": review_count,
                "overbilling_cases": len(overbilling),
                "duplicate_payment_allocations": len(duplicate_allocations),
                "closed_orders_with_unpaid_invoices": len(closed_unpaid),
                "invalid_status_transitions": len(invalid_transitions),
                "disputes_missing_adjustments": len(unadjusted_disputes)
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
            ],
             "overbilling_details":
            [
                {
                   "order_line_id": row[0],
                   "order_id": row[1],
                   "fulfilled_quantity": row[2],
                   "invoiced_quantity": row[3],
                   "excess_quantity": row[4]
                }
                for row in overbilling
            ],
             "duplicate_payment_details": [
                {
                   "payment_id": row[0],
                   "invoice_id": row[1],
                   "allocated_amount_inr": round(row[2] / 100, 2),
                   "allocation_date": row[3],
                   "occurrences": row[4]
                }
                for row in duplicate_allocations
            ],

             "closed_unpaid_invoice_details": [
                {
                    "order_id": row[0],
                    "invoice_id": row[1],
                    "invoice_amount_inr": round(row[2] / 100, 2),
                    "paid_amount_inr": round(row[3] / 100, 2),
                    "outstanding_amount_inr": round(row[4] / 100, 2)
                }
                for row in closed_unpaid
            ],

             "invalid_transition_details": [
               {
                   "event_id": row[0],
                   "entity_type": row[1],
                   "order_id": row[2],
                   "old_status": row[3],
                   "new_status": row[4],
                   "event_timestamp": row[5]
               }
               for row in invalid_transitions
            ],

             "unadjusted_dispute_details": [
              {
                **row,
                "disputed_amount_inr": round(
                row["disputed_amount_paise"] / 100, 2
                ),
                "posted_adjustment_inr": round(
                row["posted_adjustment_paise"] / 100, 2
                )
              }
               for row in unadjusted_disputes
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


