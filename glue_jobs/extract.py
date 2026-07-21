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
from pyspark.sql.types import StructType, StructField, StringType, IntegerType
from pyspark.sql.functions import when, col
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
shipment_df = shipment_df.withColumn(
    "is_guaranteed",
    when(col("is_guaranteed") == "t", True).otherwise(False)
)
billing_df = spark.read.csv(
    "s3://{}/extract/raw/billing_extract/".format(args["BUCKET_NAME"]),
    header=True,
    inferSchema=True,
)
scan_event_schema = StructType([
    StructField("event_id", StringType(), True),
    StructField("shipment_id", StringType(), True),
    StructField("event_type", StringType(), True),
    StructField("event_timestamp", StringType(), True),
    StructField("carrier_hub", StringType(), True),
    StructField("ingestion_date", StringType(), True),
    StructField("attempt_number", IntegerType(), True),
    StructField("attempt_result", StringType(), True),
])
scan_event_df = spark.read.option("recursiveFileLookup", "true").schema(scan_event_schema).json(
    's3://{}/extract/raw/scan_events/'.format(args["BUCKET_NAME"])
)

shipment_df.write.mode("overwrite").parquet(
    "s3://{}/extract/preprocessed/shipment_master/".format(args["BUCKET_NAME"])
)
scan_event_df.write.mode("overwrite").parquet(
    "s3://{}/extract/preprocessed/scan_events/".format(args["BUCKET_NAME"])
)
billing_df.write.mode("overwrite").parquet(
    "s3://{}/extract/preprocessed/billing/".format(args["BUCKET_NAME"])
)

job.commit()
