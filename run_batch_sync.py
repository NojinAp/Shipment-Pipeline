import os
import csv
import io
import boto3
import psycopg2
import redshift_connector
from dotenv import load_dotenv

load_dotenv()

rds_conn = psycopg2.connect(
    host=os.environ["RDS_HOST"],
    port=int(os.environ["RDS_PORT"]),
    dbname=os.environ["RDS_DB"],
    user=os.environ["RDS_USER"],
    password=os.environ["RDS_PASSWORD"],
)
rds_cursor = rds_conn.cursor()
s3 = boto3.client("s3", region_name="ca-central-1")
BUCKET = os.environ["REDSHIFT_S3_BUCKET"]

def export_table_to_s3(query, columns, key):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    rds_cursor.execute(query)
    writer.writerows(rds_cursor.fetchall())
    s3.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())
    print(f"Uploaded {key}")

export_table_to_s3(
    "SELECT shipment_id, booking_timestamp, promised_delivery_date, region, customer_type, service_tier, is_guaranteed, weight_kg FROM shipments",
    ["shipment_id", "booking_timestamp", "promised_delivery_date", "region", "customer_type", "service_tier", "is_guaranteed", "weight_kg"],
    "redshift/staging/shipment_master.csv",
)
export_table_to_s3(
    "SELECT shipment_id, invoice_date, base_rate, fuel_surcharge_pct, fuel_surcharge_amount, guarantee_fee, total_billed FROM billing",
    ["shipment_id", "invoice_date", "base_rate", "fuel_surcharge_pct", "fuel_surcharge_amount", "guarantee_fee", "total_billed"],
    "redshift/staging/billing_extract.csv",
)
rds_conn.close()

redshift_conn = redshift_connector.connect(
    host=os.environ["REDSHIFT_HOST"],
    port=int(os.environ["REDSHIFT_PORT"]),
    database=os.environ["REDSHIFT_DB"],
    user=os.environ["REDSHIFT_USER"],
    password=os.environ["REDSHIFT_PASSWORD"],
)

with open("redshift/sync.sql") as f:
    sql = f.read()
sql = sql.replace("{{BUCKET_NAME}}", BUCKET).replace("{{IAM_ROLE_ARN}}", os.environ["REDSHIFT_IAM_ROLE_ARN"])
statements = [s.strip() for s in sql.split(";") if s.strip()]

redshift_cursor = redshift_conn.cursor()
for statement in statements:
    redshift_cursor.execute(statement)
redshift_conn.commit()
redshift_conn.close()

print("Batch sync completed: RDS -> Redshift.")