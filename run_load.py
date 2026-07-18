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

with open("redshift/load.sql") as f:
    sql = f.read()

sql = sql.replace("{{BUCKET_NAME}}", os.environ["REDSHIFT_S3_BUCKET"])
sql = sql.replace("{{IAM_ROLE_ARN}}", os.environ["REDSHIFT_IAM_ROLE_ARN"])

statements = [s.strip() for s in sql.split(";") if s.strip()]

cursor = conn.cursor()
for statement in statements:
    cursor.execute(statement)

conn.commit()
conn.close()

print("Data loaded successfully.")