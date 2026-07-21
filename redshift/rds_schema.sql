CREATE TABLE IF NOT EXISTS shipments (
    shipment_id             VARCHAR(20)     PRIMARY KEY,
    booking_timestamp       TIMESTAMP       NOT NULL,
    promised_delivery_date  DATE            NOT NULL,
    region                  VARCHAR(50),
    customer_type           VARCHAR(20),
    service_tier            VARCHAR(20),
    is_guaranteed           BOOLEAN,
    weight_kg               DECIMAL(10,2)
);

CREATE TABLE IF NOT EXISTS billing (
    shipment_id             VARCHAR(20)     PRIMARY KEY REFERENCES shipments(shipment_id),
    invoice_date            DATE            NOT NULL,
    base_rate               DECIMAL(10,2),
    fuel_surcharge_pct      DECIMAL(6,4),
    fuel_surcharge_amount   DECIMAL(10,2),
    guarantee_fee           DECIMAL(10,2),
    total_billed            DECIMAL(10,2)
);