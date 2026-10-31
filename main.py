from src.validation.run_all_validations import main as run_validations
from src.anomaly_detection.detect_anomalies import main as run_anomaly_detection


def main():
    print("\n====================================")
    print(" ORDER-TO-CASH MONITORING SYSTEM")
    print("====================================")

    print("\nRunning data and financial validations...")
    run_validations()

    print("\nRunning anomaly detection...")
    run_anomaly_detection()

    print("\nProject execution completed successfully.")


if __name__ == "__main__":
    main()
    