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

with open("redshift/rds_schema.sql") as f:
    sql = f.read()

statements = [s.strip() for s in sql.split(";") if s.strip()]

cursor = conn.cursor()
for statement in statements:
    cursor.execute(statement)

conn.commit()
conn.close()

print("RDS schema applied successfully.")