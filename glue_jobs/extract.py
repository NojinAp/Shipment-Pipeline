"""
Reads raw shipment, scan event, and billing files from s3 (csv/jsonl) and writes them
back out as parquet under extract/preprocessed/. Straight format conversion, no
filtering or business logic in this job.

Job params: JOB_NAME, BUCKET_NAME
"""

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

args = getResolvedOptions(sys.argv, ["JOB_NAME", "BUCKET_NAME"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

shipment_df = spark.read.csv(
    "s3://{}/extract/raw/shipment_master/".format(args["BUCKET_NAME"]),
    header=True,
    inferSchema=True,
)
billing_df = spark.read.csv(
    "s3://{}/extract/raw/billing_extract/".format(args["BUCKET_NAME"]),
    header=True,
    inferSchema=True,
)
scan_events_df = spark.read.json(
    "s3://{}/extract/raw/raw_scan_events.jsonl".format(args["BUCKET_NAME"])
)

shipment_df.write.mode("overwrite").parquet(
    "s3://{}/extract/preprocessed/shipment_master/".format(args["BUCKET_NAME"])
)
scan_events_df.write.mode("overwrite").parquet(
    "s3://{}/extract/preprocessed/scan_events/".format(args["BUCKET_NAME"])
)
billing_df.write.mode("overwrite").parquet(
    "s3://{}/extract/preprocessed/billing/".format(args["BUCKET_NAME"])
)

job.commit()
