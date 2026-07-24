from pyspark.sql.functions import col, when, coalesce, lit


def calculate_is_breached(df):
    # is_breached stays null when there is no actual_delivery_date yet. Not delivered yet is not
    # the same as delivered on time, so we don't want to default it to False.
    return df.withColumn(
        "is_breached",
        when(col("actual_delivery_date").isNull(), None)
        .when(col("actual_delivery_date") > col("promised_delivery_date"), True)
        .otherwise(False),
    )


def calculate_credit_liability(df):
    return df.withColumn(
        "credit_liability",
        when(
            col("is_guaranteed") & coalesce(col("is_breached"), lit(False)),
            (col("total_billed") * 0.5),
        ).otherwise(0.00),
    )
