-- Redshift does not enforce PRIMARY KEY or FOREIGN KEY constraints.
-- They're declared here for documentation and to help the query
-- optimizer, not to guarantee uniqueness or referential integrity.
-- (That's what the quarantine checks in transform.py are for.)

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id             VARCHAR(20)     NOT NULL,
    booking_timestamp       TIMESTAMP       NOT NULL,
    promised_delivery_date  DATE            NOT NULL,
    region                  VARCHAR(50),
    customer_type           VARCHAR(20),
    service_tier            VARCHAR(20),
    is_guaranteed            BOOLEAN,
    weight_kg               DECIMAL(10,2),
    PRIMARY KEY (shipment_id)
);

CREATE TABLE IF NOT EXISTS billing (
    shipment_id             VARCHAR(20)     NOT NULL,
    invoice_date            DATE            NOT NULL,
    base_rate               DECIMAL(10,2),
    fuel_surcharge_pct      DECIMAL(6,4),
    fuel_surcharge_amount   DECIMAL(10,2),
    guarantee_fee           DECIMAL(10,2),
    total_billed            DECIMAL(10,2),
    PRIMARY KEY (shipment_id),
    FOREIGN KEY (shipment_id) REFERENCES shipments (shipment_id)
);