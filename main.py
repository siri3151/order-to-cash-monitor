
from src.validation.run_all_validations import main as run_validations
from src.anomaly_detection.detect_anomalies import main as run_anomaly_detection


def main():
    print("\n====================================")
    print(" ORDER-TO-CASH MONITORING SYSTEM")
    print("====================================")

    try:
        print("\n[1/2] Running data and financial validations...")
        run_validations()

        print("\n[2/2] Running anomaly detection...")
        run_anomaly_detection()

        print("\n====================================")
        print(" MONITORING EXECUTION COMPLETED")
        print("====================================")
        print("Validation report: outputs/validation_summary.json")
        print("Anomaly report: outputs/anomaly_report.json")

    except Exception as error:
        print("\nProject execution failed:", error)
        raise


if __name__ == "__main__":
    main()
