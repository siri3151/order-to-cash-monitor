
import sqlite3
import unittest
from pathlib import Path

from src.anomaly_detection.detect_anomalies import (
    detect_overbilling,
    detect_duplicate_payment_allocations,
    detect_closed_orders_with_unpaid_invoices,
    detect_invalid_status_transitions,
    detect_unadjusted_disputes,
)

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "order_to_cash.db"


class TestInjectedAnomalies(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.connection = sqlite3.connect(DB_PATH)
        cls.connection.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def test_overbilling_is_detected(self):
        results = detect_overbilling(self.connection)
        self.assertGreater(len(results), 0)

    def test_duplicate_payment_is_detected(self):
        results = detect_duplicate_payment_allocations(self.connection)
        self.assertGreater(len(results), 0)

    def test_closed_order_with_unpaid_invoice_is_detected(self):
        results = detect_closed_orders_with_unpaid_invoices(
            self.connection
        )
        self.assertGreater(len(results), 0)

    def test_invalid_status_transition_is_detected(self):
        results = detect_invalid_status_transitions(self.connection)
        self.assertGreater(len(results), 0)

    def test_missing_dispute_adjustment_is_detected(self):
        results = detect_unadjusted_disputes(self.connection)
        self.assertGreater(len(results), 0)


if __name__ == "__main__":
    unittest.main()
