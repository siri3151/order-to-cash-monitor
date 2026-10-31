
# Order-to-Cash Monitoring System
## Data Dictionary

**Project:** YottaFlex AI Candidate Project  
**Database:** SQLite  
**Currency:** INR  
**Date format:** ISO 8601 (`YYYY-MM-DD`)  
**Timestamp format:** ISO 8601 with timezone  
**Monetary convention:** INR (to be stored as integer paise in the final schema)

## Monetary Data Convention

All monetary values are stored as integer paise to avoid floating-point precision errors.

Example:
- ₹100.50 is stored as 10050.
- ₹250.75 is stored as 25075.

All monetary columns use the SQLite INTEGER data type.

---

## 1. Account

Purpose: Stores customer and business account information.

| Field | Type | Required | Unique | Validation / Allowed Values |
|---|---|---|---|---|
| account_id | TEXT | Yes | PK | ACC-2026-000001 format |
| account_name | TEXT | Yes | No | Non-empty |
| email | TEXT | No | Yes | Valid email format |
| industry | TEXT | No | No | Business industry |
| country | TEXT | Yes | No | Non-empty country |
| created_at | TEXT | Yes | No | Valid ISO date |
| account_status | TEXT | Yes | No | ACTIVE, INACTIVE |

## 2. Quote

Purpose: Stores sales quotations created for customer accounts.

| Field | Type | Required | Unique | Validation / Allowed Values |
|---|---|---|---|---|
| quote_id | TEXT | Yes | PK | QTE-2026-000001 format |
| account_id | TEXT | Yes | FK | Must reference Account |
| quote_date | TEXT | Yes | No | Valid ISO date |
| expiry_date | TEXT | Yes | No | Must be >= quote_date |
| status | TEXT | Yes | No | DRAFT, SENT, ACCEPTED, REJECTED, EXPIRED |
| currency | TEXT | Yes | No | ISO currency code; default INR |
| total_amount | INTEGER | Yes | No | >= 0, INR |

## 3. QuoteLine

Purpose: Stores individual products or services included in a quote.

| Field | Type | Required | Unique | Validation / Allowed Values |
|---|---|---|---|---|
| quote_line_id | TEXT | Yes | PK | Unique line ID |
| quote_id | TEXT | Yes | FK | Must reference Quote |
| product_name | TEXT | Yes | No | Non-empty |
| quantity | INTEGER | Yes | No | > 0, units |
| unit_price | INTEGER | Yes | No | >= 0, INR |
| line_total | INTEGER | Yes | No | quantity × unit_price |

## 4. SalesOrder

Purpose: Stores confirmed customer orders converted from accepted quotes.

| Field | Type | Required | Unique | Validation / Allowed Values |
|---|---|---|---|---|
| order_id | TEXT | Yes | PK | SO-2026-000001 format |
| quote_id | TEXT | Yes | FK, UNIQUE | Must reference an accepted Quote |
| account_id | TEXT | Yes | FK | Must reference Account |
| order_date | TEXT | Yes | No | Must be >= quote_date |
| status | TEXT | Yes | No | OPEN, CONFIRMED, PARTIALLY_FULFILLED, FULFILLED, CLOSED, CANCELLED |
| total_amount | INTEGER | Yes | No | >= 0, INR |

## 5. OrderLine

Purpose: Stores products and quantities belonging to sales orders.

| Field | Type | Required | Unique | Validation / Allowed Values |
|---|---|---|---|---|
| order_line_id | TEXT | Yes | PK | Unique line ID |
| order_id | TEXT | Yes | FK | Must reference SalesOrder |
| quote_line_id | TEXT | Yes | FK, UNIQUE | Must reference QuoteLine |
| product_name | TEXT | Yes | No | Non-empty |
| ordered_quantity | INTEGER | Yes | No | > 0, units |
| unit_price | INTEGER | Yes | No | >= 0, INR |
| line_total | INTEGER | Yes | No | ordered_quantity × unit_price |

## 6. Shipment

Purpose: Records shipment and fulfillment activity for sales orders.

| Field | Type | Required | Unique | Validation / Allowed Values |
|---|---|---|---|---|
| shipment_id | TEXT | Yes | PK | SHP-2026-000001 format |
| order_id | TEXT | Yes | FK | Must reference SalesOrder |
| shipment_date | TEXT | Yes | No | Valid ISO date |
| delivery_date | TEXT | No | No | >= shipment_date |
| status | TEXT | Yes | No | CREATED, DISPATCHED, IN_TRANSIT, DELIVERED, FAILED, CANCELLED |

## 7. ShipmentLine (Additional bridge/detail table)

Purpose: Connects shipments to order lines and tracks partial fulfillment.

| Field | Type | Required | Unique | Validation / Allowed Values |
|---|---|---|---|---|
| shipment_line_id | TEXT | Yes | PK | Unique line ID |
| shipment_id | TEXT | Yes | FK | Must reference Shipment |
| order_line_id | TEXT | Yes | FK | Must reference OrderLine |
| shipped_quantity | INTEGER | Yes | No | > 0, units |

Business rule: Cumulative delivered quantities must not exceed ordered quantities, except in explicitly labelled anomaly cases.

## 8. Invoice

Purpose: Records invoices issued for fulfilled goods or services.

| Field | Type | Required | Unique | Validation / Allowed Values |
|---|---|---|---|---|
| invoice_id | TEXT | Yes | PK | INV-2026-000001 format |
| account_id | TEXT | Yes | FK | Must reference Account |
| order_id | TEXT | Yes | FK | Must reference SalesOrder |
| invoice_date | TEXT | Yes | No | Valid ISO date |
| due_date | TEXT | Yes | No | >= invoice_date |
| status | TEXT | Yes | No | DRAFT, ISSUED, PARTIALLY_PAID, PAID, OVERDUE, VOID |
| currency | TEXT | Yes | No | ISO currency code; default INR |
| total_amount | INTEGER | Yes | No | >= 0, INR |

## 9. InvoiceLine

Purpose: Tracks quantities and amounts billed against order lines.

| Field | Type | Required | Unique | Validation / Allowed Values |
|---|---|---|---|---|
| invoice_line_id | TEXT | Yes | PK | Unique line ID |
| invoice_id | TEXT | Yes | FK | Must reference Invoice |
| order_line_id | TEXT | Yes | FK | Must reference OrderLine |
| invoiced_quantity | INTEGER | Yes | No | > 0, units |
| unit_price | INTEGER | Yes | No | >= 0, INR |
| line_total | INTEGER | Yes | No | invoiced_quantity × unit_price |

Business rule: Total invoiced quantity should not exceed fulfilled quantity in normal records.

## 10. Payment

Purpose: Records customer payments received against outstanding invoices.

| Field | Type | Required | Unique | Validation / Allowed Values |
|---|---|---|---|---|
| payment_id | TEXT | Yes | PK | PAY-2026-000001 format |
| account_id | TEXT | Yes | FK | Must reference Account |
| payment_date | TEXT | Yes | No | Valid ISO date |
| amount | INTEGER | Yes | No | > 0, INR |
| currency | TEXT | Yes | No | ISO currency code; default INR |
| payment_method | TEXT | Yes | No | BANK_TRANSFER, CARD, UPI, CHEQUE |
| status | TEXT | Yes | No | RECEIVED, PARTIALLY_ALLOCATED, ALLOCATED, REFUNDED |

## 11. PaymentAllocation (Additional bridge table)

Purpose: Connects payments with invoices and records how much money is allocated to each invoice.

| Field | Type | Required | Unique | Validation / Allowed Values |
|---|---|---|---|---|
| allocation_id | TEXT | Yes | PK | Unique allocation ID |
| payment_id | TEXT | Yes | FK | Must reference Payment |
| invoice_id | TEXT | Yes | FK | Must reference Invoice |
| allocated_amount | INTEGER | Yes | No | > 0, INR |
| allocation_date | TEXT | Yes | No | Valid ISO date |

Business rules:
- Total allocations must not exceed the payment amount.
- Total allocated payments must be reconciled against invoice balances.
- Duplicate allocations must be identified and flagged.

## 12. Dispute

Purpose: Records customer disputes related to invoices.

| Field | Type | Required | Unique | Validation / Allowed Values |
|---|---|---|---|---|
| dispute_id | TEXT | Yes | PK | DSP-2026-000001 format |
| invoice_id | TEXT | Yes | FK | Must reference Invoice |
| opened_date | TEXT | Yes | No | Valid ISO date |
| resolved_date | TEXT | No | No | >= opened_date |
| reason | TEXT | Yes | No | DAMAGED_GOODS, WRONG_AMOUNT, MISSING_ITEMS, DUPLICATE_INVOICE, OTHER |
| status | TEXT | Yes | No | OPEN, UNDER_REVIEW, RESOLVED, REJECTED |
| disputed_amount | INTEGER | Yes | No | > 0, INR |

Business rule: Open disputes must be reflected in receivables calculations according to the documented dispute policy.

## 13. StatusEvent

Purpose: Maintains historical state changes for accounts, quotes, orders, shipments, invoices, payments and disputes.

| Field | Type | Required | Unique | Validation / Allowed Values |
|---|---|---|---|---|
| event_id | TEXT | Yes | PK | Unique event ID |
| entity_type | TEXT | Yes | No | ACCOUNT, QUOTE, SALES_ORDER, SHIPMENT, INVOICE, PAYMENT, DISPUTE |
| account_id | TEXT | Conditional | FK | References Account |
| quote_id | TEXT | Conditional | FK | References Quote |
| order_id | TEXT | Conditional | FK | References SalesOrder |
| shipment_id | TEXT | Conditional | FK | References Shipment |
| invoice_id | TEXT | Conditional | FK | References Invoice |
| payment_id | TEXT | Conditional | FK | References Payment |
| dispute_id | TEXT | Conditional | FK | References Dispute |
| old_status | TEXT | No | No | Previous state; NULL for initial event |
| new_status | TEXT | Yes | No | New state |
| event_timestamp | TEXT | Yes | No | ISO 8601 timestamp |
| actor | TEXT | Yes | No | SYSTEM, SALES, SUPPORT, ADMIN |
| reason | TEXT | No | No | Explanation for state change |

Business rule: Every state transition must be stored as a new event. Existing event records must never be overwritten.

---

# Global Data Validation Rules

1. All primary keys must be unique and immutable.
2. All foreign keys must reference existing parent records.
3. Dates must follow chronological business order.
4. Monetary calculations must reconcile.
5. Quantities must be positive.
6. Accepted quotes can be converted into orders.
7. Only fulfilled quantities can normally be invoiced.
8. Payment allocations cannot exceed payment amounts.
9. Open disputes must be accounted for in receivables.
10. Every state change must have a corresponding StatusEvent.
11. Anomalies must have explicit issue_type and ground_truth labels.
12. Ground-truth labels must never be used as input features for anomaly detection.

# Reproducibility

- Random seed: 20261022
- Target quotes: 10,000
- Target orders: 7,000
- Target invoices: 8,000
- Target payments/events: 15,000
- IDs: Deterministic and zero-padded.
- Generator: Parameterized to support starter and full dataset sizes.
- Validation: Row counts, primary keys, foreign keys, business rules and output checksums.

