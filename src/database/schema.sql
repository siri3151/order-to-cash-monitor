
PRAGMA foreign_keys = ON;

-- 1. ACCOUNT
CREATE TABLE IF NOT EXISTS Account (
    account_id TEXT PRIMARY KEY,
    account_name TEXT NOT NULL,
    email TEXT UNIQUE,
    industry TEXT,
    country TEXT NOT NULL,
    created_at TEXT NOT NULL,
    account_status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (account_status IN ('ACTIVE', 'INACTIVE'))
);

-- 2. QUOTE
CREATE TABLE IF NOT EXISTS Quote (
    quote_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    quote_date TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN (
            'DRAFT', 'SENT', 'ACCEPTED', 'REJECTED', 'EXPIRED'
        )),
    currency TEXT NOT NULL DEFAULT 'INR',
    total_amount INTEGER NOT NULL CHECK (total_amount >= 0),
    FOREIGN KEY (account_id) REFERENCES Account(account_id),
    CHECK (expiry_date >= quote_date)
);

-- 3. QUOTE LINE
CREATE TABLE IF NOT EXISTS QuoteLine (
    quote_line_id TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price INTEGER NOT NULL CHECK (unit_price >= 0),
    line_total INTEGER NOT NULL CHECK (line_total >= 0),
    FOREIGN KEY (quote_id) REFERENCES Quote(quote_id)
);

-- 4. SALES ORDER
CREATE TABLE IF NOT EXISTS SalesOrder (
    order_id TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL UNIQUE,
    account_id TEXT NOT NULL,
    order_date TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN (
            'OPEN', 'CONFIRMED', 'PARTIALLY_FULFILLED',
            'FULFILLED', 'CLOSED', 'CANCELLED'
        )),
    total_amount INTEGER NOT NULL CHECK (total_amount >= 0),
    FOREIGN KEY (quote_id) REFERENCES Quote(quote_id),
    FOREIGN KEY (account_id) REFERENCES Account(account_id)
);

-- 5. ORDER LINE
CREATE TABLE IF NOT EXISTS OrderLine (
    order_line_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    quote_line_id TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    ordered_quantity INTEGER NOT NULL CHECK (ordered_quantity > 0),
    unit_price INTEGER NOT NULL CHECK (unit_price >= 0),
    line_total INTEGER NOT NULL CHECK (line_total >= 0),
    FOREIGN KEY (order_id) REFERENCES SalesOrder(order_id),
    FOREIGN KEY (quote_line_id) REFERENCES QuoteLine(quote_line_id)
);

-- 6. SHIPMENT
CREATE TABLE IF NOT EXISTS Shipment (
    shipment_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    shipment_date TEXT NOT NULL,
    delivery_date TEXT,
    status TEXT NOT NULL
        CHECK (status IN (
            'CREATED', 'DISPATCHED', 'IN_TRANSIT',
            'DELIVERED', 'FAILED', 'CANCELLED'
        )),
    FOREIGN KEY (order_id) REFERENCES SalesOrder(order_id),
    CHECK (
        delivery_date IS NULL OR delivery_date >= shipment_date
    )
);

-- Additional table: SHIPMENT LINE
CREATE TABLE IF NOT EXISTS ShipmentLine (
    shipment_line_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL,
    order_line_id TEXT NOT NULL,
    shipped_quantity INTEGER NOT NULL CHECK (shipped_quantity > 0),
    FOREIGN KEY (shipment_id) REFERENCES Shipment(shipment_id),
    FOREIGN KEY (order_line_id) REFERENCES OrderLine(order_line_id)
);

-- 7. INVOICE
CREATE TABLE IF NOT EXISTS Invoice (
    invoice_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN (
            'DRAFT', 'ISSUED', 'PARTIALLY_PAID',
            'PAID', 'OVERDUE', 'VOID'
        )),
    currency TEXT NOT NULL DEFAULT 'INR',
    total_amount INTEGER NOT NULL CHECK (total_amount >= 0),
    FOREIGN KEY (account_id) REFERENCES Account(account_id),
    FOREIGN KEY (order_id) REFERENCES SalesOrder(order_id),
    CHECK (due_date >= invoice_date)
);

-- 8. INVOICE LINE
CREATE TABLE IF NOT EXISTS InvoiceLine (
    invoice_line_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    order_line_id TEXT NOT NULL,
    invoiced_quantity INTEGER NOT NULL CHECK (invoiced_quantity > 0),
    unit_price INTEGER NOT NULL CHECK (unit_price >= 0),
    line_total INTEGER NOT NULL CHECK (line_total >= 0),
    FOREIGN KEY (invoice_id) REFERENCES Invoice(invoice_id),
    FOREIGN KEY (order_line_id) REFERENCES OrderLine(order_line_id)
);

-- 9. PAYMENT
CREATE TABLE IF NOT EXISTS Payment (
    payment_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    payment_date TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    payment_method TEXT NOT NULL
        CHECK (payment_method IN (
            'BANK_TRANSFER', 'CARD', 'UPI', 'CHEQUE'
        )),
    status TEXT NOT NULL
        CHECK (status IN (
            'RECEIVED', 'PARTIALLY_ALLOCATED',
            'ALLOCATED', 'REFUNDED'
        )),
    FOREIGN KEY (account_id) REFERENCES Account(account_id)
);

-- Additional table: PAYMENT ALLOCATION
CREATE TABLE IF NOT EXISTS PaymentAllocation (
    allocation_id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    allocated_amount INTEGER NOT NULL CHECK (allocated_amount > 0),
    allocation_date TEXT NOT NULL,
    FOREIGN KEY (payment_id) REFERENCES Payment(payment_id),
    FOREIGN KEY (invoice_id) REFERENCES Invoice(invoice_id)
);

-- 10. DISPUTE
CREATE TABLE IF NOT EXISTS Dispute (
    dispute_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    opened_date TEXT NOT NULL,
    resolved_date TEXT,
    reason TEXT NOT NULL
        CHECK (reason IN (
            'DAMAGED_GOODS', 'WRONG_AMOUNT',
            'MISSING_ITEMS', 'DUPLICATE_INVOICE', 'OTHER'
        )),
    status TEXT NOT NULL
        CHECK (status IN (
            'OPEN', 'UNDER_REVIEW', 'RESOLVED', 'REJECTED'
        )),
    disputed_amount INTEGER NOT NULL CHECK (disputed_amount > 0),
    FOREIGN KEY (invoice_id) REFERENCES Invoice(invoice_id),
    CHECK (
        resolved_date IS NULL OR resolved_date >= opened_date
    )
);

-- 11. STATUS EVENT
CREATE TABLE IF NOT EXISTS StatusEvent (
    event_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL
        CHECK (entity_type IN (
            'ACCOUNT', 'QUOTE', 'SALES_ORDER',
            'SHIPMENT', 'INVOICE', 'PAYMENT', 'DISPUTE'
        )),
    account_id TEXT REFERENCES Account(account_id),
    quote_id TEXT REFERENCES Quote(quote_id),
    order_id TEXT REFERENCES SalesOrder(order_id),
    shipment_id TEXT REFERENCES Shipment(shipment_id),
    invoice_id TEXT REFERENCES Invoice(invoice_id),
    payment_id TEXT REFERENCES Payment(payment_id),
    dispute_id TEXT REFERENCES Dispute(dispute_id),
    old_status TEXT,
    new_status TEXT NOT NULL,
    event_timestamp TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT,
    CHECK (
        (entity_type = 'ACCOUNT' AND account_id IS NOT NULL
            AND quote_id IS NULL AND order_id IS NULL
            AND shipment_id IS NULL AND invoice_id IS NULL
            AND payment_id IS NULL AND dispute_id IS NULL)
        OR
        (entity_type = 'QUOTE' AND quote_id IS NOT NULL
            AND account_id IS NULL AND order_id IS NULL
            AND shipment_id IS NULL AND invoice_id IS NULL
            AND payment_id IS NULL AND dispute_id IS NULL)
        OR
        (entity_type = 'SALES_ORDER' AND order_id IS NOT NULL
            AND account_id IS NULL AND quote_id IS NULL
            AND shipment_id IS NULL AND invoice_id IS NULL
            AND payment_id IS NULL AND dispute_id IS NULL)
        OR
        (entity_type = 'SHIPMENT' AND shipment_id IS NOT NULL
            AND account_id IS NULL AND quote_id IS NULL
            AND order_id IS NULL AND invoice_id IS NULL
            AND payment_id IS NULL AND dispute_id IS NULL)
        OR
        (entity_type = 'INVOICE' AND invoice_id IS NOT NULL
            AND account_id IS NULL AND quote_id IS NULL
            AND order_id IS NULL AND shipment_id IS NULL
            AND payment_id IS NULL AND dispute_id IS NULL)
        OR
        (entity_type = 'PAYMENT' AND payment_id IS NOT NULL
            AND account_id IS NULL AND quote_id IS NULL
            AND order_id IS NULL AND shipment_id IS NULL
            AND invoice_id IS NULL AND dispute_id IS NULL)
        OR
        (entity_type = 'DISPUTE' AND dispute_id IS NOT NULL
            AND account_id IS NULL AND quote_id IS NULL
            AND order_id IS NULL AND shipment_id IS NULL
            AND invoice_id IS NULL AND payment_id IS NULL)
    )
);

-- Useful indexes for analytics and joins
CREATE INDEX IF NOT EXISTS idx_quote_account
    ON Quote(account_id);

CREATE INDEX IF NOT EXISTS idx_order_account
    ON SalesOrder(account_id);

CREATE INDEX IF NOT EXISTS idx_shipment_order
    ON Shipment(order_id);

CREATE INDEX IF NOT EXISTS idx_invoice_account
    ON Invoice(account_id);

CREATE INDEX IF NOT EXISTS idx_invoice_due_date
    ON Invoice(due_date);

CREATE INDEX IF NOT EXISTS idx_payment_account
    ON Payment(account_id);

CREATE INDEX IF NOT EXISTS idx_allocation_invoice
    ON PaymentAllocation(invoice_id);

CREATE INDEX IF NOT EXISTS idx_event_timestamp
    ON StatusEvent(event_timestamp);
