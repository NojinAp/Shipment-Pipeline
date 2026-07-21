import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

conn = psycopg2.connect(
    host=os.environ["RDS_HOST"],
    port=int(os.environ["RDS_PORT"]),
    dbname=os.environ["RDS_DB"],
    user=os.environ["RDS_USER"],
    password=os.environ["RDS_PASSWORD"],
)

cursor = conn.cursor()

cursor.execute("CREATE EXTENSION IF NOT EXISTS aws_s3 CASCADE;")

cursor.execute("""
    SELECT aws_s3.table_import_from_s3(
        'shipments',
        '',
        '(format csv, header true)',
        %s, %s, %s
    );
""", (os.environ["RDS_S3_BUCKET"], "rds/staging/shipment_master.csv", "ca-central-1"))

cursor.execute("""
    SELECT aws_s3.table_import_from_s3(
        'billing',
        '',
        '(format csv, header true)',
        %s, %s, %s
    );
""", (os.environ["RDS_S3_BUCKET"], "rds/staging/billing_extract.csv", "ca-central-1"))

conn.commit()
conn.close()

print("RDS S3 import completed.")