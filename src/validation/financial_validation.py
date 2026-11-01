
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "order_to_cash.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def calculate_outstanding_balances(connection):

    query = """
        SELECT
            i.invoice_id,
            i.total_amount,
            COALESCE(SUM(pa.allocated_amount), 0) AS total_paid,
            i.total_amount -
                COALESCE(SUM(pa.allocated_amount), 0) AS outstanding
        FROM Invoice i
        LEFT JOIN PaymentAllocation pa
            ON i.invoice_id = pa.invoice_id
        WHERE i.status NOT IN ('DRAFT', 'VOID')
        GROUP BY i.invoice_id, i.total_amount
        ORDER BY outstanding DESC
    """

    return connection.execute(query).fetchall()


def check_invoice_overpayments(connection):

    query = """
        SELECT
            i.invoice_id,
            i.total_amount,
            SUM(pa.allocated_amount) AS total_paid,
            SUM(pa.allocated_amount) - i.total_amount AS overpayment
        FROM Invoice i
        JOIN PaymentAllocation pa
            ON i.invoice_id = pa.invoice_id
        WHERE i.status NOT IN ('DRAFT', 'VOID')
        GROUP BY i.invoice_id, i.total_amount
        HAVING SUM(pa.allocated_amount) > i.total_amount
    """

    return connection.execute(query).fetchall()


def calculate_dispute_adjusted_receivables(connection):

    query = """
        SELECT
            i.invoice_id,
            i.total_amount,
            COALESCE(payments.total_paid, 0) AS total_paid,
            i.total_amount - COALESCE(payments.total_paid, 0)
                AS outstanding,

            COALESCE(disputes.active_disputed_amount, 0)
                AS disputed_amount,

            MAX(
                0,
                i.total_amount
                - COALESCE(payments.total_paid, 0)
                - MIN(
                    COALESCE(disputes.active_disputed_amount, 0),
                    MAX(
                        0,
                        i.total_amount - COALESCE(payments.total_paid, 0)
                    )
                )
            ) AS adjusted_receivable

        FROM Invoice i

        LEFT JOIN (
            SELECT
                invoice_id,
                SUM(allocated_amount) AS total_paid
            FROM PaymentAllocation
            GROUP BY invoice_id
        ) payments
            ON i.invoice_id = payments.invoice_id

        LEFT JOIN (
            SELECT
               d.invoice_id,
               SUM(da.adjusted_amount) AS active_disputed_amount
            FROM Dispute d
            JOIN DisputeAdjustment da
                 ON d.dispute_id = da.dispute_id
            WHERE d.status IN ('OPEN', 'UNDER_REVIEW')
              AND da.status = 'POSTED'
            GROUP BY d.invoice_id
        ) disputes
            ON i.invoice_id = disputes.invoice_id

        WHERE i.status NOT IN ('DRAFT', 'VOID')
    """

    return connection.execute(query).fetchall()

def detect_unadjusted_disputes(connection):

    query = """
        SELECT
            d.dispute_id,
            d.invoice_id,
            d.disputed_amount,
            MAX(
                0,
                i.total_amount - COALESCE(p.total_paid, 0)
            ) AS outstanding,
            COALESCE(a.posted_amount, 0) AS posted_amount
        FROM Dispute d
        JOIN Invoice i
            ON d.invoice_id = i.invoice_id

        LEFT JOIN (
            SELECT
                invoice_id,
                SUM(allocated_amount) AS total_paid
            FROM PaymentAllocation
            GROUP BY invoice_id
        ) p ON i.invoice_id = p.invoice_id

        LEFT JOIN (
            SELECT
                dispute_id,
                SUM(adjusted_amount) AS posted_amount
            FROM DisputeAdjustment
            WHERE status = 'POSTED'
            GROUP BY dispute_id
        ) a ON d.dispute_id = a.dispute_id

        WHERE d.status IN ('OPEN', 'UNDER_REVIEW')
          AND i.status NOT IN ('DRAFT', 'VOID')
    """

    results = connection.execute(query).fetchall()
    unadjusted = []

    for row in results:
        dispute_id, invoice_id, disputed_amount, outstanding, posted_amount = row

        expected_adjustment = min(disputed_amount, outstanding)

        if posted_amount < expected_adjustment:
            unadjusted.append({
                "dispute_id": dispute_id,
                "invoice_id": invoice_id,
                "expected_adjustment_paise": expected_adjustment,
                "posted_adjustment_paise": posted_amount
            })

    return unadjusted

def main():
    connection = get_connection()

    balances = calculate_outstanding_balances(connection)

    total_outstanding = sum(row[3] for row in balances)
    unpaid_invoices = sum(1 for row in balances if row[3] > 0)

    print("\nFINANCIAL VALIDATION REPORT")
    print("=" * 40)

    print("Invoices considered:", len(balances))
    print("Invoices with outstanding balance:", unpaid_invoices)

    # Amounts are stored in paise; convert to rupees for display.
    print(
        "Total outstanding: ₹",
        round(total_outstanding / 100, 2)
    )

    print("\nTop 5 invoices with outstanding balances:")

    for row in balances[:5]:
        invoice_id, total, paid, outstanding = row

        print(
            invoice_id,
            "| Invoice: ₹", round(total / 100, 2),
            "| Paid: ₹", round(paid / 100, 2),
            "| Outstanding: ₹", round(outstanding / 100, 2)
        )

    overpayments = check_invoice_overpayments(connection)

    print("\nINVOICE OVERPAYMENT CHECK")
    print("=" * 40)
    print("Overpaid invoices:", len(overpayments))

    if overpayments:
        for row in overpayments[:5]:
            print(row)
    else:
        print("No invoice overpayments found.")

    dispute_results = calculate_dispute_adjusted_receivables(connection)

    total_adjusted = sum(row[5] for row in dispute_results)
    total_applied_dispute = sum(
        max(0, row[3] - row[5])
        for row in dispute_results
    )

    print(
        "Dispute amount applied: ₹",
        round(total_applied_dispute / 100, 2)
    )
    total_disputed = sum(row[4] for row in dispute_results)

    print("\nDISPUTE-ADJUSTED RECEIVABLES")
    print("=" * 40)
    print("Invoices considered:", len(dispute_results))
    print("Active disputed amount: ₹", round(total_disputed / 100, 2))
    print("Adjusted receivables: ₹", round(total_adjusted / 100, 2))

    connection.close()

if __name__ == "__main__":
    main()
