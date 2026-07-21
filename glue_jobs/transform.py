"""
Reads the preprocessed parquet files (shipments, scan events, billing) and applies
data quality checks: quarantines orphaned and duplicate billing records, orphaned and
duplicate scan events, and duplicate or bad-date shipments. Also derives the first
delivery attempt (FDA) and actual delivery date per shipment. Writes the cleaned
dataframes and the quarantine tables under transform/.

Job params: JOB_NAME, BUCKET_NAME
"""

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import Window
from pyspark.sql.functions import col, to_date, lit, row_number, when
from transform_logic import find_duplicates, find_orphans

args = getResolvedOptions(sys.argv, ["JOB_NAME", "BUCKET_NAME"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

shipment_df = spark.read.parquet(
    "s3://{}/extract/preprocessed/shipment_master/".format(args["BUCKET_NAME"])
)
scan_event_df = spark.read.parquet(
    "s3://{}/extract/preprocessed/scan_events/".format(args["BUCKET_NAME"])
)
billing_df = spark.read.parquet(
    "s3://{}/extract/preprocessed/billing/".format(args["BUCKET_NAME"])
)

# duplicate billing records
duplicate_billing_df = find_duplicates(billing_df, "shipment_id")
# orphaned billing records
orphaned_billing_df = find_orphans(billing_df, shipment_df, 'shipment_id')

# duplicate events
duplicate_event_df = find_duplicates(scan_event_df, "event_id")
# orphaned events
orphaned_event_df = find_orphans(scan_event_df, shipment_df, 'shipment_id')

# duplicate shipments
duplicate_shipment_df = find_duplicates(shipment_df, "shipment_id")
# bad-date shipments
bad_date_shipment_df = shipment_df.filter(
    col("promised_delivery_date") < to_date(col("booking_timestamp"))
)

# billing quarantine dataframe
orphaned_billing_df = orphaned_billing_df.withColumn(
    "quarantine_reason", lit("orphaned")
)
duplicate_billing_df = duplicate_billing_df.withColumn(
    "quarantine_reason", lit("duplicate")
)

billing_quarantine_df = orphaned_billing_df.unionByName(
    duplicate_billing_df, allowMissingColumns=True
)

billing_quarantine_df.write.mode("overwrite").parquet(
    "s3://{}/transform/quarantine/quarantined_billing/".format(args["BUCKET_NAME"])
)

billing_df = billing_df.join(
    shipment_df.select("shipment_id"), on="shipment_id", how="left_semi"
).join(duplicate_billing_df.select("shipment_id"), on="shipment_id", how="left_anti")

# events quarantine dataframe
orphaned_event_df = orphaned_event_df.withColumn("quarantine_reason", lit("orphaned"))
duplicate_event_df = duplicate_event_df.withColumn(
    "quarantine_reason", lit("duplicate")
)

event_quarantine_df = orphaned_event_df.unionByName(
    duplicate_event_df, allowMissingColumns=True
)

event_quarantine_df.write.mode("overwrite").parquet(
    "s3://{}/transform/quarantine/quarantined_event/".format(args["BUCKET_NAME"])
)

scan_event_df = scan_event_df.join(
    shipment_df.select("shipment_id"), on="shipment_id", how="left_semi"
).join(duplicate_event_df.select("event_id"), on="event_id", how="left_anti")

# shipments quarantine dataframe
duplicate_shipment_df = duplicate_shipment_df.withColumn(
    "quarantine_reason", lit("duplicate")
)
bad_date_shipment_df = bad_date_shipment_df.withColumn(
    "quarantine_reason", lit("incorrect delivery date")
)

shipment_quarantine_df = duplicate_shipment_df.unionByName(
    bad_date_shipment_df, allowMissingColumns=True
)

shipment_quarantine_df.write.mode("overwrite").parquet(
    "s3://{}/transform/quarantine/quarantined_shipment/".format(args["BUCKET_NAME"])
)

shipment_df = shipment_df.join(
    duplicate_shipment_df.select("shipment_id"), on="shipment_id", how="left_anti"
).join(bad_date_shipment_df.select("shipment_id"), on="shipment_id", how="left_anti")


delivery_attempts_df = scan_event_df.filter(col("event_type") == "DELIVERY_ATTEMPT")

dup_window_4 = Window.partitionBy("shipment_id").orderBy("event_timestamp")
delivery_attempts_df = delivery_attempts_df.withColumn(
    "attempt_seq", row_number().over(dup_window_4)
)

first_attempts_df = delivery_attempts_df.filter(col("attempt_seq") == 1)

# first delivery attempts that were successful
# an unknown or invalid attempt_result gets a null fda instead of a 0. A bad reading should not
# look the same as a real failed delivery attempt.
first_attempts_df = (
    first_attempts_df.withColumn(
        "fda_data_quality_flag",
        when(
            col("attempt_result").isin(
                "SUCCESS", "FAILED_NO_ONE_HOME", "FAILED_NO_ACCESS", "FAILED_REFUSED"
            ),
            False,
        ).otherwise(True),
    )
    .withColumn(
        "fda",
        when(col("fda_data_quality_flag") == True, None)
        .when(col("attempt_result") == "SUCCESS", 1)
        .otherwise(0),
    )
    .withColumn("first_attempt_date", to_date(col("event_timestamp")))
)

actual_delivery_df = (
    delivery_attempts_df.filter(col("attempt_result") == "SUCCESS")
    .select("shipment_id", "event_timestamp")
    .withColumnRenamed("event_timestamp", "actual_delivery_date")
)

shipment_df.write.mode("overwrite").parquet(
    "s3://{}/transform/shipments/".format(args["BUCKET_NAME"])
)
billing_df.write.mode("overwrite").parquet(
    "s3://{}/transform/billing/".format(args["BUCKET_NAME"])
)
first_attempts_df.write.mode("overwrite").parquet(
    "s3://{}/transform/first_attempts/".format(args["BUCKET_NAME"])
)
actual_delivery_df.write.mode("overwrite").parquet(
    "s3://{}/transform/actual_delivery/".format(args["BUCKET_NAME"])
)

job.commit()