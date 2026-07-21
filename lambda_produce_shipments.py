import os
import random
from datetime import datetime, timedelta
import psycopg2

REGIONS = ["GTA", "Montreal", "Calgary-Edmonton", "Atlantic", "Vancouver"]
CUSTOMER_TYPES = ["RESIDENTIAL", "COMMERCIAL"]
SERVICE_TIERS = ["SAME_DAY", "NEXT_DAY", "STANDARD"]
NEW_BOOKINGS_PER_RUN = 5

def lambda_handler(event, context):
    conn = psycopg2.connect(
        host=os.environ["RDS_HOST"],
        port=int(os.environ["RDS_PORT"]),
        dbname=os.environ["RDS_DB"],
        user=os.environ["RDS_USER"],
        password=os.environ["RDS_PASSWORD"],
    )
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM shipments")
    next_id_num = cursor.fetchone()[0] + 1

    for _ in range(NEW_BOOKINGS_PER_RUN):
        shipment_id = f"SHP-{next_id_num:08d}"
        next_id_num += 1

        booking_timestamp = datetime.now()
        service_tier = random.choice(SERVICE_TIERS)
        delivery_offset_days = {"SAME_DAY": 0, "NEXT_DAY": 1, "STANDARD": random.randint(2, 5)}[service_tier]
        promised_delivery_date = (booking_timestamp + timedelta(days=delivery_offset_days)).date()
        region = random.choice(REGIONS)
        customer_type = random.choice(CUSTOMER_TYPES)
        is_guaranteed = random.random() < 0.3
        weight_kg = round(random.uniform(0.5, 25.0), 2)

        cursor.execute("""
            INSERT INTO shipments
            (shipment_id, booking_timestamp, promised_delivery_date, region, customer_type, service_tier, is_guaranteed, weight_kg)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (shipment_id, booking_timestamp, promised_delivery_date, region, customer_type, service_tier, is_guaranteed, weight_kg))

        base_rate = round(random.uniform(15, 150), 2)
        fuel_surcharge_pct = round(random.uniform(0.08, 0.18), 4)
        fuel_surcharge_amount = round(base_rate * fuel_surcharge_pct, 2)
        guarantee_fee = round(random.uniform(10, 30), 2) if is_guaranteed else 0.0
        total_billed = round(base_rate + fuel_surcharge_amount + guarantee_fee, 2)

        cursor.execute("""
            INSERT INTO billing
            (shipment_id, invoice_date, base_rate, fuel_surcharge_pct, fuel_surcharge_amount, guarantee_fee, total_billed)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (shipment_id, booking_timestamp.date(), base_rate, fuel_surcharge_pct, fuel_surcharge_amount, guarantee_fee, total_billed))

    conn.commit()
    conn.close()

    return {"statusCode": 200, "body": f"{NEW_BOOKINGS_PER_RUN} new bookings created."}