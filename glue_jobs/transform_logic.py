from pyspark.sql import Window
from pyspark.sql.functions import count, col

def find_duplicates(df, key_col):
    window = Window.partitionBy(key_col)
    return (
        df.withColumn("_count", count(key_col).over(window))
        .filter(col("_count") > 1)
        .drop("_count")
    )

def find_orphans(df, reference_df, key_col):
    return df.join(reference_df, on=key_col, how="left_anti")
