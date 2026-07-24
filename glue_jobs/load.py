"""
Reads the cleaned transform outputs (shipments, billing, first attempts, actual
delivery) and joins them into the final shipment-level table used for reporting:
adds is_breached and credit_liability. Writes the result under load/.

Job params: JOB_NAME, BUCKET_NAME
"""

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import col, lit, when, coalesce
from load_logic import calculate_is_breached, calculate_credit_liability

args = getResolvedOptions(sys.argv, ["JOB_NAME", "BUCKET_NAME"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

shipment_df = spark.read.parquet(
    "s3://{}/transform/shipments/".format(args["BUCKET_NAME"])
)
billing_df = spark.read.parquet(
    "s3://{}/transform/billing/".format(args["BUCKET_NAME"])
)
first_attempts_df = spark.read.parquet(
    "s3://{}/transform/first_attempts/".format(args["BUCKET_NAME"])
)
actual_delivery_df = spark.read.parquet(
    "s3://{}/transform/actual_delivery/".format(args["BUCKET_NAME"])
)

# complete dataframe showing whether shipments were breached, whether their FDA was successful, and the
# credit liability amount assigned to guaranteed shipments
final_df = (
    shipment_df.join(
        first_attempts_df.select(
            "shipment_id", "fda", "fda_data_quality_flag", "first_attempt_date"
        ),
        on="shipment_id",
        how="left",
    )
    .join(actual_delivery_df, on="shipment_id", how="left")
    .join(billing_df, on="shipment_id", how="left")
)
final_df = calculate_is_breached(final_df)
final_df = calculate_credit_liability(final_df)

final_df.write.mode("overwrite").parquet("s3://{}/load/".format(args["BUCKET_NAME"]))

job.commit()
