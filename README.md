# Order-to-Cash Revenue Leakage and Process Monitoring System

## Project Overview

The Order-to-Cash Revenue Leakage and Process Monitoring System is a Python-based project designed to identify potential revenue leakage and process issues across the order-to-cash cycle.

The system uses a synthetic business dataset stored in SQLite to monitor orders, shipments, invoices, payments, and disputes. It performs data validation, financial validation, and anomaly detection to highlight records that may require further investigation.

## Problem Statement

Businesses can experience revenue leakage and operational delays when:

- Delivered products or services are not fully invoiced.
- Invoices remain unpaid after their due dates.
- Customer disputes remain unresolved for long periods.
- Payment allocations or transaction quantities contain inconsistencies.

This project demonstrates how Python and SQL can be used to identify these issues through automated checks and reports.

## Key Features

### 1. Data Validation
- Checks whether shipped quantities exceed ordered quantities.
- Identifies invoiced quantities exceeding delivered quantities.
- Checks whether payment allocations exceed payment amounts.
- Verifies database foreign key relationships.

### 2. Financial Validation
- Calculates outstanding invoice balances.
- Identifies invoice overpayments.
- Calculates dispute-adjusted receivables.
- Summarizes outstanding and adjusted receivable amounts.

### 3. Anomaly Detection
- Detects overdue invoices with outstanding balances.
- Identifies potentially uninvoiced delivered quantities.
- Estimates the potential billing gap.
- Detects disputes that have remained open or under review for more than 30 days.

### 4. Automated Reporting
- Generates a consolidated validation report.
- Generates a detailed anomaly detection report.
- Saves both reports in JSON format for further analysis.

## Technology Stack

- **Programming Language:** Python
- **Database:** SQLite
- **Data Generation:** Faker
- **SQL:** Data retrieval, joins, aggregations, and financial calculations
- **Reporting:** JSON

## Project Structure

```text
order-to-cash-monitor/
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── ground_truth/
│   └── order_to_cash.db
│
├── src/
│   ├── generators/
│   ├── database/
│   │   ├── schema.sql
│   │   └── init_db.py
│   │
│   ├── business_logic/
│   ├── anomaly_detection/
│   │   └── detect_anomalies.py
│   │
│   └── validation/
│       ├── validate_data.py
│       ├── financial_validation.py
│       └── run_all_validations.py
│
├── tests/
├── docs/
├── outputs/
│   ├── validation_summary.json
│   └── anomaly_report.json
│
├── config.py
├── main.py
└── requirements.txt
```

## Dataset

The project uses synthetic data stored in an SQLite database.

| Entity | Records |
|---|---:|
| Accounts | 2,000 |
| Quotes | 10,000 |
| Quote Lines | 24,869 |
| Sales Orders | 7,000 |
| Order Lines | 17,262 |
| Shipments | 7,914 |
| Shipment Lines | 18,890 |
| Invoices | 8,000 |
| Invoice Lines | 8,000 |
| Payments | 15,000 |
| Payment Allocations | 15,000 |
| Disputes | 400 |
| Status Events | 15,000 |

## Setup and Execution

### Prerequisites

- Python 3.12 or compatible Python 3 version
- Git
- VS Code or another Python editor

### 1. Clone the repository

```bash
git clone <your-github-repository-url>
cd order-to-cash-monitor
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run data validation

```bash
python -m src.validation.run_all_validations
```

This generates:

```text
outputs/validation_summary.json
```

### 5. Run anomaly detection

```bash
python -m src.anomaly_detection.detect_anomalies
```

This generates:

```text
outputs/anomaly_report.json
```

The repository includes the generated SQLite database and reports, so the validation and anomaly detection modules can be executed against the included dataset.

## Results

### Data and Financial Validation

| Validation | Violations | Result |
|---|---:|---|
| Shipped Quantity | 0 | PASSED |
| Invoiced Quantity | 0 | PASSED |
| Payment Allocations | 0 | PASSED |
| Foreign Keys | 0 | PASSED |
| Invoice Overpayments | 0 | PASSED |

Financial results:

- Total outstanding receivables: INR 533,956,251.64
- Dispute-adjusted receivables: INR 521,983,959.04

### Anomaly Detection

| Finding | Count / Value |
|---|---:|
| Overdue invoices | 8,000 |
| Potentially uninvoiced order lines | 1,305 |
| Potentially uninvoiced units | 7,514 |
| Estimated potential billing gap | INR 385,371,706.00 |
| Long-unresolved disputes | 197 |
| Open disputes | 102 |
| Disputes under review | 95 |

## Important Assumptions and Limitations

- The dataset is synthetic and does not represent real customer or business transactions.
- The billing gap is an estimated potential value based on delivered and invoiced quantities. It should not be treated as confirmed lost revenue.
- Quantity comparisons are performed at the order-line level.
- The overdue invoice count is influenced by the dates and outstanding balances in the generated dataset.
- The project is a prototype for monitoring and analysis, not a production financial reconciliation platform.

## Future Improvements

- Add a dashboard to visualize revenue leakage and operational metrics.
- Implement scheduled monitoring and automated alerts.
- Add more advanced anomaly detection techniques.
- Improve invoice-to-shipment reconciliation.
- Add automated unit and integration tests.
- Support larger datasets and additional database systems.

## Author

**Sirisha Geddada**

B.Tech – Computer Science and Engineering

GitHub: https://github.com/siri3151

LinkedIn: https://linkedin.com/in/sirisha-geddada-334191271/
