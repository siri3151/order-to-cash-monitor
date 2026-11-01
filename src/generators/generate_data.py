import random
import sqlite3
import os
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

# --------------------------------------------------
# Configuration
# --------------------------------------------------

SEED = 20261022
ACCOUNT_COUNT = 2000
QUOTE_COUNT = 10000

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "order_to_cash.db"

random.seed(SEED)
fake = Faker("en_IN")
Faker.seed(SEED)


# --------------------------------------------------
# Database connection
# --------------------------------------------------

def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# --------------------------------------------------
# Generate accounts
# --------------------------------------------------

def generate_accounts(connection):
    cursor = connection.cursor()

    industries = [
        "Technology",
        "Manufacturing",
        "Healthcare",
        "Retail",
        "Finance",
        "Education",
        "Logistics"
    ]

    accounts = []

    for i in range(1, ACCOUNT_COUNT + 1):
        account_id = f"ACC-2026-{i:06d}"

        accounts.append((
            account_id,
            f"{fake.company()} {i}",
            f"customer{i}@example.com",
            random.choice(industries),
            "India",
            fake.date_between(
                start_date=date(2024, 1, 1),
                end_date=date(2026, 10, 1)
            ).isoformat(),
            random.choices(
                ["ACTIVE", "INACTIVE"],
                weights=[90, 10]
            )[0]
        ))

    cursor.executemany("""
        INSERT INTO Account (
            account_id, account_name, email, industry,
            country, created_at, account_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, accounts)

    print(f"Generated {len(accounts)} accounts")


# --------------------------------------------------
# Generate quotes and quote lines
# --------------------------------------------------

def generate_quotes(connection):
    cursor = connection.cursor()

    accounts = [
        row[0] for row in cursor.execute(
            "SELECT account_id FROM Account"
        ).fetchall()
    ]

    products = [
        "Cloud Subscription",
        "Software License",
        "Technical Support",
        "Data Analytics Service",
        "Security Package",
        "Consulting Service",
        "API Subscription",
        "Maintenance Package"
    ]

    # Exactly 7,000 accepted quotes so we can
    # convert them into 7,000 sales orders later.
    statuses = (
        ["ACCEPTED"] * 7000
        + ["SENT"] * 1000
        + ["REJECTED"] * 800
        + ["EXPIRED"] * 700
        + ["DRAFT"] * 500
    )

    random.shuffle(statuses)

    for i in range(1, QUOTE_COUNT + 1):
        quote_id = f"QTE-2026-{i:06d}"
        account_id = random.choice(accounts)

        quote_date = fake.date_between(
            start_date=date(2026, 8, 1),
            end_date=date(2026, 10, 20)

        )

        expiry_date = quote_date + timedelta(days=30)

        status = statuses[i - 1]

        line_count = random.randint(1, 4)
        quote_lines = []
        total_amount = 0

        for line_number in range(1, line_count + 1):
            quantity = random.randint(1, 20)

            # Price stored in paise.
            unit_price = random.randint(500, 100000) * 100

            line_total = quantity * unit_price
            total_amount += line_total

            quote_lines.append((
                f"QL-{i:06d}-{line_number:02d}",
                quote_id,
                random.choice(products),
                quantity,
                unit_price,
                line_total
            ))

        cursor.execute("""
            INSERT INTO Quote (
                quote_id, account_id, quote_date,
                expiry_date, status, currency, total_amount
            )
            VALUES (?, ?, ?, ?, ?, 'INR', ?)
        """, (
            quote_id,
            account_id,
            quote_date.isoformat(),
            expiry_date.isoformat(),
            status,
            total_amount
        ))

        cursor.executemany("""
            INSERT INTO QuoteLine (
                quote_line_id, quote_id, product_name,
                quantity, unit_price, line_total
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, quote_lines)

    print(f"Generated {QUOTE_COUNT} quotes and their quote lines")



def generate_sales_orders(connection):
    cursor = connection.cursor()

    accepted_quotes = cursor.execute("""
        SELECT quote_id, account_id, quote_date, total_amount
        FROM Quote
        WHERE status = 'ACCEPTED'
        ORDER BY quote_id
    """).fetchall()

    for i, quote in enumerate(accepted_quotes, start=1):
        quote_id, account_id, quote_date, total_amount = quote

        order_id = f"SO-2026-{i:06d}"

        order_date = (
            date.fromisoformat(quote_date)
            + timedelta(days=random.randint(1, 10))
        )

        cursor.execute("""
            INSERT INTO SalesOrder (
                order_id, quote_id, account_id,
                order_date, status, total_amount
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            order_id,
            quote_id,
            account_id,
            order_date.isoformat(),
            "CONFIRMED",
            total_amount
        ))

        quote_lines = cursor.execute("""
            SELECT quote_line_id, product_name,
                   quantity, unit_price, line_total
            FROM QuoteLine
            WHERE quote_id = ?
            ORDER BY quote_line_id
        """, (quote_id,)).fetchall()

        order_lines = []

        for line_number, line in enumerate(quote_lines, start=1):
            quote_line_id, product, quantity, price, line_total = line

            order_lines.append((
                f"OL-{i:06d}-{line_number:02d}",
                order_id,
                quote_line_id,
                product,
                quantity,
                price,
                line_total
            ))

        cursor.executemany("""
            INSERT INTO OrderLine (
                order_line_id, order_id, quote_line_id,
                product_name, ordered_quantity,
                unit_price, line_total
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, order_lines)

    print(f"Generated {len(accepted_quotes)} sales orders")


def generate_shipments(connection):
    cursor = connection.cursor()

    orders = cursor.execute("""
        SELECT order_id, order_date
        FROM SalesOrder
        ORDER BY order_id
    """).fetchall()

    shipment_count = 0
    shipment_line_count = 0

    for order_id, order_date in orders:

        # Some orders may not have shipped yet.
        if random.random() < 0.10:
            continue

        order_lines = cursor.execute("""
            SELECT order_line_id, ordered_quantity
            FROM OrderLine
            WHERE order_id = ?
        """, (order_id,)).fetchall()

        shipment_date = (
            date.fromisoformat(order_date)
            + timedelta(days=random.randint(1, 15))
        )

        # Split an order into one or two shipments.
        number_of_shipments = random.choices(
            [1, 2], weights=[75, 25]
        )[0]

        shipment_id_list = []

        for _ in range(number_of_shipments):
            shipment_count += 1
            shipment_id = f"SHP-2026-{shipment_count:06d}"
            shipment_id_list.append(shipment_id)

            status = random.choice([
                "DELIVERED",
                "DELIVERED",
                "IN_TRANSIT",
                "DISPATCHED"
            ])

            delivery_date = None

            if status == "DELIVERED":
                delivery_date = (
                    shipment_date
                    + timedelta(days=random.randint(1, 7))
                ).isoformat()

            cursor.execute("""
                INSERT INTO Shipment (
                    shipment_id, order_id, shipment_date,
                    delivery_date, status
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                shipment_id,
                order_id,
                shipment_date.isoformat(),
                delivery_date,
                status
            ))

        # Distribute ordered quantities across shipments.
        for order_line_id, ordered_quantity in order_lines:

            remaining = ordered_quantity

            for shipment_id in shipment_id_list:
                if remaining <= 0:
                    break

                shipped_quantity = random.randint(1, remaining)

                shipment_line_count += 1

                cursor.execute("""
                    INSERT INTO ShipmentLine (
                        shipment_line_id, shipment_id,
                        order_line_id, shipped_quantity
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    f"SL-{shipment_line_count:07d}",
                    shipment_id,
                    order_line_id,
                    shipped_quantity
                ))

                remaining -= shipped_quantity

    print(f"Generated {shipment_count} shipments")
    print(f"Generated {shipment_line_count} shipment lines")


def generate_invoices(connection):
    cursor = connection.cursor()

    delivered_lines = cursor.execute("""
        SELECT
            sl.shipment_line_id,
            sl.shipped_quantity,
            sh.delivery_date,
            ol.order_line_id,
            ol.unit_price,
            so.order_id,
            so.account_id
        FROM ShipmentLine sl
        JOIN Shipment sh
            ON sl.shipment_id = sh.shipment_id
        JOIN OrderLine ol
            ON sl.order_line_id = ol.order_line_id
        JOIN SalesOrder so
            ON ol.order_id = so.order_id
        WHERE sh.status = 'DELIVERED'
        ORDER BY sh.delivery_date, sl.shipment_line_id
    """).fetchall()
    random.shuffle(delivered_lines)
    delivered_lines = delivered_lines[:8000]
    for i, row in enumerate(delivered_lines, start=1):
        (
            shipment_line_id,
            quantity,
            delivery_date,
            order_line_id,
            unit_price,
            order_id,
            account_id
        ) = row

        invoice_id = f"INV-2026-{i:06d}"
        invoice_line_id = f"IL-{i:06d}"

        invoice_date = date.fromisoformat(delivery_date)
        due_date = invoice_date + timedelta(days=30)

        line_total = quantity * unit_price

        cursor.execute("""
            INSERT INTO Invoice (
                invoice_id, account_id, order_id,
                invoice_date, due_date, status,
                currency, total_amount
            )
            VALUES (?, ?, ?, ?, ?, ?, 'INR', ?)
        """, (
            invoice_id,
            account_id,
            order_id,
            invoice_date.isoformat(),
            due_date.isoformat(),
            "ISSUED",
            line_total
        ))

        cursor.execute("""
            INSERT INTO InvoiceLine (
                invoice_line_id, invoice_id,
                order_line_id, invoiced_quantity,
                unit_price, line_total
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            invoice_line_id,
            invoice_id,
            order_line_id,
            quantity,
            unit_price,
            line_total
        ))

    print(f"Generated {len(delivered_lines)} invoices")


def generate_payments(connection):
    cursor = connection.cursor()

    invoices = cursor.execute("""
        SELECT invoice_id, account_id, invoice_date, total_amount
        FROM Invoice
        ORDER BY invoice_id
    """).fetchall()

    payment_methods = [
        "BANK_TRANSFER", "CARD", "UPI", "CHEQUE"
    ]

    payment_number = 1
    allocation_number = 1

    for invoice_index, invoice in enumerate(invoices):
        invoice_id, account_id, invoice_date, total_amount = invoice

        # Exactly 15,000 payments across 8,000 invoices:
        # First 7,000 invoices get 2 payments each.
        # Remaining 1,000 invoices get 1 payment each.
        number_of_payments = 2 if invoice_index < 7000 else 1

        # Generate a paid amount between 50% and 100% of invoice value.
        total_amount = int(round(total_amount))
        paid_amount = random.randint(
            total_amount // 2,
            total_amount
        )

        if number_of_payments == 2:
            first_amount = random.randint(1, paid_amount - 1)
            payment_amounts = [
                first_amount,
                paid_amount - first_amount
            ]
        else:
            payment_amounts = [paid_amount]

        for amount in payment_amounts:
            payment_id = f"PAY-2026-{payment_number:06d}"
            allocation_id = f"PA-{allocation_number:06d}"

            payment_date = (
                date.fromisoformat(invoice_date)
                + timedelta(days=random.randint(1, 45))
            ).isoformat()

            payment_method = random.choice(payment_methods)

            cursor.execute("""
                INSERT INTO Payment (
                    payment_id, account_id, payment_date,
                    amount, currency, payment_method, status
                )
                VALUES (?, ?, ?, ?, 'INR', ?, 'ALLOCATED')
            """, (
                payment_id,
                account_id,
                payment_date,
                amount,
                payment_method
            ))

            cursor.execute("""
                INSERT INTO PaymentAllocation (
                    allocation_id, payment_id, invoice_id,
                    allocated_amount, allocation_date
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                allocation_id,
                payment_id,
                invoice_id,
                amount,
                payment_date
            ))

            payment_number += 1
            allocation_number += 1

    connection.commit()

    print("Payment generation completed.")
    print("Payments:", payment_number - 1)
    print("Payment Allocations:", allocation_number - 1)


def generate_disputes(connection):
    cursor = connection.cursor()

    invoices = cursor.execute("""
        SELECT invoice_id, invoice_date, total_amount
        FROM Invoice
        ORDER BY invoice_id
    """).fetchall()

    selected_invoices = random.sample(invoices, 400)

    reasons = [
        "DAMAGED_GOODS",
        "WRONG_AMOUNT",
        "MISSING_ITEMS",
        "DUPLICATE_INVOICE",
        "OTHER"
    ]

    statuses = [
        "OPEN",
        "UNDER_REVIEW",
        "RESOLVED",
        "REJECTED"
    ]

    for i, (invoice_id, invoice_date, total_amount) in enumerate(
        selected_invoices, start=1
    ):
        total_amount = int(total_amount)
        dispute_id = f"DSP-2026-{i:06d}"

        opened_date = (
            date.fromisoformat(invoice_date)
            + timedelta(days=random.randint(1, 20))
        )

        status = random.choice(statuses)

        resolved_date = None
        if status in ("RESOLVED", "REJECTED"):
            resolved_date = (
                opened_date + timedelta(days=random.randint(1, 15))
            ).isoformat()

        disputed_amount = random.randint(1, total_amount)

        cursor.execute("""
            INSERT INTO Dispute (
                dispute_id, invoice_id, opened_date,
                resolved_date, reason, status, disputed_amount
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            dispute_id,
            invoice_id,
            opened_date.isoformat(),
            resolved_date,
            random.choice(reasons),
            status,
            disputed_amount
        ))

        if status in ("OPEN", "UNDER_REVIEW"):
            total_paid = cursor.execute("""
                SELECT COALESCE(SUM(allocated_amount), 0)
                FROM PaymentAllocation
                WHERE invoice_id = ?
            """, (invoice_id,)).fetchone()[0]

            outstanding = max(0, total_amount - total_paid)
            adjustment_amount = min(disputed_amount, outstanding)

            if adjustment_amount > 0:
                cursor.execute("""
                    INSERT INTO DisputeAdjustment (
                        adjustment_id,
                        dispute_id,
                        adjusted_amount,
                        adjustment_date,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    f"DPA-2026-{i:06d}",
                    dispute_id,
                    adjustment_amount,
                    opened_date.isoformat(),
                    "POSTED"
                ))

    connection.commit()
    print("Disputes generated:", len(selected_invoices))

    adjustment_count = cursor.execute("""
        SELECT COUNT(*) FROM DisputeAdjustment
    """).fetchone()[0]

    print("Dispute adjustments generated:", adjustment_count)

def generate_status_events(connection):
    cursor = connection.cursor()

    entity_queries = [
        ("ACCOUNT", "Account", "account_id", "account_status"),
        ("QUOTE", "Quote", "quote_id", "status"),
        ("SALES_ORDER", "SalesOrder", "order_id", "status"),
        ("SHIPMENT", "Shipment", "shipment_id", "status"),
        ("INVOICE", "Invoice", "invoice_id", "status"),
        ("PAYMENT", "Payment", "payment_id", "status"),
        ("DISPUTE", "Dispute", "dispute_id", "status")
    ]

    candidates = []

    for entity_type, table, id_column, status_column in entity_queries:
        rows = cursor.execute(
            f"SELECT {id_column}, {status_column} FROM {table}"
        ).fetchall()

        for entity_id, status in rows:
            candidates.append((entity_type, entity_id, status))

    if len(candidates) < 15000:
        raise ValueError("Not enough records to generate 15,000 events.")

    selected_events = random.sample(candidates, 15000)

    column_mapping = {
        "ACCOUNT": "account_id",
        "QUOTE": "quote_id",
        "SALES_ORDER": "order_id",
        "SHIPMENT": "shipment_id",
        "INVOICE": "invoice_id",
        "PAYMENT": "payment_id",
        "DISPUTE": "dispute_id"
    }

    for i, (entity_type, entity_id, status) in enumerate(
        selected_events, start=1
    ):
        event_date = (
            date(2025, 1, 1)
            + timedelta(days=random.randint(0, 667))
        )

        entity_column = column_mapping[entity_type]

        values = {
            "account_id": None,
            "quote_id": None,
            "order_id": None,
            "shipment_id": None,
            "invoice_id": None,
            "payment_id": None,
            "dispute_id": None
        }

        values[entity_column] = entity_id

        cursor.execute("""
            INSERT INTO StatusEvent (
                event_id, entity_type,
                account_id, quote_id, order_id,
                shipment_id, invoice_id, payment_id, dispute_id,
                old_status, new_status, event_timestamp,
                actor, reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"EVT-2026-{i:06d}",
            entity_type,
            values["account_id"],
            values["quote_id"],
            values["order_id"],
            values["shipment_id"],
            values["invoice_id"],
            values["payment_id"],
            values["dispute_id"],
            None,
            status,
            f"{event_date.isoformat()}T12:00:00",
            random.choice(["SYSTEM", "SALES_OPS", "FINANCE", "SUPPORT"]),
            "Initial status snapshot"
        ))

    connection.commit()
    print("Status events generated:", len(selected_events))


# --------------------------------------------------
# Main execution
# --------------------------------------------------
def main():
    from src.database.init_db import reset_and_initialize_database

    reset_and_initialize_database()

    connection = get_connection()

    try:
        generate_accounts(connection)
        generate_quotes(connection)
        generate_sales_orders(connection)
        generate_shipments(connection)
        generate_invoices(connection)
        generate_payments(connection)
        generate_disputes(connection)
        generate_status_events(connection)

        print("\nBaseline data generation completed successfully!")

    except Exception as error:
        connection.rollback()
        print("Data generation failed:", error)
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()