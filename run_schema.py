import os
from dotenv import load_dotenv
import redshift_connector

load_dotenv()

conn = redshift_connector.connect(
    host=os.environ["REDSHIFT_HOST"],
    port=int(os.environ["REDSHIFT_PORT"]),
    database=os.environ["REDSHIFT_DB"],
    user=os.environ["REDSHIFT_USER"],
    password=os.environ["REDSHIFT_PASSWORD"],
)

with open("redshift/schema.sql") as f:
    sql = f.read()

statements = [s.strip() for s in sql.split(";") if s.strip()]

cursor = conn.cursor()
for statement in statements:
    cursor.execute(statement)

conn.commit()
conn.close()

print("Schema applied successfully.")