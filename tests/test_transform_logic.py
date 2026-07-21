import pytest
from pyspark.sql import SparkSession
from transform_logic import find_duplicates, find_orphans


@pytest.fixture(scope="session")
def spark():
    return (
        SparkSession.builder
        .appName("transform_logic_tests")
        .master("local[1]")
        .config("spark.sql.execution.arrow.pyspark.enabled", "false")
        .getOrCreate()
    )


def test_find_duplicates(spark):
    df = spark.createDataFrame(
        [("SHP-001",), ("SHP-001",), ("SHP-002",)], ["shipment_id"]
    )

    result = find_duplicates(df, "shipment_id")

    assert result.count() == 2


def test_find_orphans(spark):
    first_df = spark.createDataFrame(
        [("SHP-004",), ("SHP-005",), ("SHP-006",)], ["shipment_id"]
    )
    second_df = spark.createDataFrame(
        [("EV-001", "SHP-004"), ("EV-002", "SHP-005"), ("EV-003", None)],
        ["event_id", "shipment_id"],
    )
    result = find_orphans(first_df, second_df, "shipment_id")
    assert result.count() == 1
