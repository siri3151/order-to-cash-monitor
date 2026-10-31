
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "order_to_cash.db"


# Each query returns records that violate a business rule.
CHECKS = {
    "Quote total matches quote lines": """
        SELECT q.quote_id
        FROM Quote q
        LEFT JOIN QuoteLine ql ON q.quote_id = ql.quote_id
        GROUP BY q.quote_id
        HAVING ROUND(q.total_amount, 2) !=
               ROUND(COALESCE(SUM(ql.line_total), 0), 2)
    """,

    "Sales order total matches order lines": """
        SELECT so.order_id
        FROM SalesOrder so
        LEFT JOIN OrderLine ol ON so.order_id = ol.order_id
        GROUP BY so.order_id
        HAVING ROUND(so.total_amount, 2) !=
               ROUND(COALESCE(SUM(ol.line_total), 0), 2)
    """,

    "Order account matches quote account": """
        SELECT so.order_id
        FROM SalesOrder so
        JOIN Quote q ON so.quote_id = q.quote_id
        WHERE so.account_id != q.account_id
           OR q.status != 'ACCEPTED'
    """,

    "Order lines reference the correct quote": """
        SELECT ol.order_line_id
        FROM OrderLine ol
        JOIN SalesOrder so ON ol.order_id = so.order_id
        JOIN QuoteLine ql ON ol.quote_line_id = ql.quote_line_id
        WHERE so.quote_id != ql.quote_id
    """,

    "Shipment lines belong to the shipment order": """
        SELECT sl.shipment_line_id
        FROM ShipmentLine sl
        JOIN Shipment s ON sl.shipment_id = s.shipment_id
        JOIN OrderLine ol ON sl.order_line_id = ol.order_line_id
        WHERE s.order_id != ol.order_id
    """,

    "Delivered quantity does not exceed ordered quantity": """
        SELECT ol.order_line_id
        FROM OrderLine ol
        LEFT JOIN ShipmentLine sl
            ON ol.order_line_id = sl.order_line_id
        LEFT JOIN Shipment s
            ON sl.shipment_id = s.shipment_id
        GROUP BY ol.order_line_id, ol.ordered_quantity
        HAVING COALESCE(
            SUM(
                CASE WHEN s.status = 'DELIVERED'
                     THEN sl.shipped_quantity
                     ELSE 0 END
            ), 0
        ) > ol.ordered_quantity
    """,

    "Invoice account matches order account": """
        SELECT i.invoice_id
        FROM Invoice i
        JOIN SalesOrder so ON i.order_id = so.order_id
        WHERE i.account_id != so.account_id
    """,

    "Invoice lines belong to the invoice order": """
        SELECT il.invoice_line_id
        FROM InvoiceLine il
        JOIN Invoice i ON il.invoice_id = i.invoice_id
        JOIN OrderLine ol ON il.order_line_id = ol.order_line_id
        WHERE i.order_id != ol.order_id
    """,

    "Invoice quantity does not exceed delivered quantity": """
        SELECT il.invoice_line_id
        FROM InvoiceLine il
        JOIN Invoice i ON il.invoice_id = i.invoice_id
        JOIN OrderLine ol ON il.order_line_id = ol.order_line_id
        WHERE il.invoiced_quantity >
            COALESCE((
                SELECT SUM(sl.shipped_quantity)
                FROM ShipmentLine sl
                JOIN Shipment s
                    ON sl.shipment_id = s.shipment_id
                WHERE sl.order_line_id = il.order_line_id
                  AND s.order_id = i.order_id
                  AND s.status = 'DELIVERED'
            ), 0)
    """,

    "Payment allocations do not exceed payment amount": """
        SELECT p.payment_id
        FROM Payment p
        LEFT JOIN PaymentAllocation pa
            ON p.payment_id = pa.payment_id
        GROUP BY p.payment_id, p.amount
        HAVING COALESCE(SUM(pa.allocated_amount), 0) > p.amount
    """,

    "Payment and invoice accounts match": """
        SELECT pa.allocation_id
        FROM PaymentAllocation pa
        JOIN Payment p ON pa.payment_id = p.payment_id
        JOIN Invoice i ON pa.invoice_id = i.invoice_id
        WHERE p.account_id != i.account_id
    """,

    "Disputed amount does not exceed invoice amount": """
        SELECT d.dispute_id
        FROM Dispute d
        JOIN Invoice i ON d.invoice_id = i.invoice_id
        WHERE d.disputed_amount > i.total_amount
    """
}


def run_business_checks():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    passed = 0
    failed = 0

    print("\nBUSINESS RULE VALIDATION")
    print("=" * 55)

    try:
        for rule_name, query in CHECKS.items():
            violations = connection.execute(query).fetchall()

            if violations:
                failed += 1
                print(f"[FAILED] {rule_name}")
                print(f"          Violations found: {len(violations)}")
                print(f"          Sample records: {violations[:5]}")
            else:
                passed += 1
                print(f"[PASSED] {rule_name}")

    finally:
        connection.close()

    print("\n" + "=" * 55)
    print(f"Rules passed: {passed}")
    print(f"Rules failed: {failed}")
    print(f"Total rules: {len(CHECKS)}")

    return failed == 0


if __name__ == "__main__":
    success = run_business_checks()

    if not success:
        raise SystemExit("Business validation found violations.")

    print("\nBusiness validation completed.")
