
import json
from pathlib import Path

from .validate_data import (
    get_connection,
    check_shipped_quantity,
    check_invoiced_quantity,
    check_payment_allocations,
    check_foreign_keys,
)

from .financial_validation import (
    calculate_outstanding_balances,
    check_invoice_overpayments,
    calculate_dispute_adjusted_receivables,
)


BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "outputs"
REPORT_PATH = OUTPUT_DIR / "validation_summary.json"


def run_validations(connection):

    # 1. Data quality checks
    checks = {
        "shipped_quantity": check_shipped_quantity(connection),
        "invoiced_quantity": check_invoiced_quantity(connection),
        "payment_allocations": check_payment_allocations(connection),
        "foreign_keys": check_foreign_keys(connection),
    }

    data_quality = {}

    for name, errors in checks.items():
        data_quality[name] = {
            "violations": len(errors),
            "status": "PASSED" if len(errors) == 0 else "FAILED",
            "examples": [list(row) for row in errors[:5]]
        }

    # 2. Financial checks
    balances = calculate_outstanding_balances(connection)

    total_outstanding = sum(float(row[3]) for row in balances)

    unpaid_invoices = sum(
        1 for row in balances if row[3] > 0
    )

    overpayments = check_invoice_overpayments(connection)

    dispute_results = calculate_dispute_adjusted_receivables(connection)

    total_disputed = sum(
        float(row[4]) for row in dispute_results
    )

    total_adjusted = sum(
        float(row[5]) for row in dispute_results
    )

    total_applied_dispute = sum(
        max(0, float(row[3]) - float(row[5]))
        for row in dispute_results
    )

    # 3. Build financial summary
    financial_summary = {
        "invoices_considered": len(balances),
        "invoices_with_outstanding_balance": unpaid_invoices,
        "overpaid_invoices": len(overpayments),

        "total_outstanding_paise": round(total_outstanding, 2),
        "total_outstanding_inr": round(total_outstanding / 100, 2),

        "active_disputed_amount_paise": round(total_disputed, 2),
        "active_disputed_amount_inr": round(total_disputed / 100, 2),

        "dispute_amount_applied_paise": round(total_applied_dispute, 2),
        "dispute_amount_applied_inr": round(total_applied_dispute / 100, 2),

        "adjusted_receivables_paise": round(total_adjusted, 2),
        "adjusted_receivables_inr": round(total_adjusted / 100, 2),
    }

    financial_summary["status"] = (
        "PASSED" if len(overpayments) == 0 else "FAILED"
    )

    # 4. Overall validation result
    all_data_checks_passed = all(
        result["status"] == "PASSED"
        for result in data_quality.values()
    )

    overall_status = (
        "PASSED"
        if all_data_checks_passed
        and financial_summary["status"] == "PASSED"
        else "FAILED"
    )

    # 5. Final report
    report = {
        "project": "Order-to-Cash Revenue Leakage Monitoring",
        "overall_status": overall_status,
        "data_quality_checks": data_quality,
        "financial_summary": financial_summary,
    }

    return report


def main():

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    connection = get_connection()

    try:
        report = run_validations(connection)

        with open(REPORT_PATH, "w", encoding="utf-8") as file:
            json.dump(report, file, indent=4)

        print("\nCONSOLIDATED VALIDATION REPORT")
        print("=" * 45)

        for name, result in report["data_quality_checks"].items():
            print(
                name,
                "| Violations:", result["violations"],
                "| Status:", result["status"]
            )

        print("\nFinancial validation:")
        print("Outstanding: ₹", report["financial_summary"]["total_outstanding_inr"])
        print("Overpaid invoices:", report["financial_summary"]["overpaid_invoices"])
        print("Adjusted receivables: ₹", report["financial_summary"]["adjusted_receivables_inr"])

        print("\nOverall status:", report["overall_status"])
        print("Report saved to:", REPORT_PATH)

    finally:
        connection.close()


if __name__ == "__main__":
    main()
