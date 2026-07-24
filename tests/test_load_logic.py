import pytest
from pyspark.sql import SparkSession
from datetime import date
from pyspark.sql.types import StructType, StructField, StringType, BooleanType, DateType, DoubleType
from load_logic import calculate_is_breached, calculate_credit_liability


@pytest.fixture(scope="module")
def spark():
    return SparkSession.builder.master("local[1]").appName("test").getOrCreate()


def test_guaranteed_and_breached_charges_half(spark):
    df = spark.createDataFrame(
        [("SHP1", True, date(2024, 1, 5), date(2024, 1, 1), 100.0)],
        ["shipment_id", "is_guaranteed", "actual_delivery_date", "promised_delivery_date", "total_billed"],
    )
    result = calculate_credit_liability(calculate_is_breached(df)).collect()[0]

    assert result["is_breached"] is True
    assert result["credit_liability"] == 50.0


def test_not_guaranteed_stays_zero_regardless_of_breach(spark):
    df = spark.createDataFrame(
        [("SHP2", False, date(2024, 1, 5), date(2024, 1, 1), 100.0)],
        ["shipment_id", "is_guaranteed", "actual_delivery_date", "promised_delivery_date", "total_billed"],
    )
    result = calculate_credit_liability(calculate_is_breached(df)).collect()[0]

    assert result["is_breached"] is True  # breach still correctly detected
    assert result["credit_liability"] == 0.0  # but not charged, since not guaranteed


def test_unresolved_delivery_stays_null_but_liability_treats_as_not_breached(spark):
    schema = StructType([
        StructField("shipment_id", StringType()),
        StructField("is_guaranteed", BooleanType()),
        StructField("actual_delivery_date", DateType()),
        StructField("promised_delivery_date", DateType()),
        StructField("total_billed", DoubleType()),
    ])
    df = spark.createDataFrame(
        [("SHP3", True, None, date(2024, 1, 1), 100.0)],
        schema=schema,
    )
    result = calculate_credit_liability(calculate_is_breached(df)).collect()[0]

    assert result["is_breached"] is None
    assert result["credit_liability"] == 0.0

def test_not_breached_stays_zero(spark):
    df = spark.createDataFrame(
        [("SHP4", True, date(2024, 1, 1), date(2024, 1, 5), 100.0)],  # delivered early/on-time
        ["shipment_id", "is_guaranteed", "actual_delivery_date", "promised_delivery_date", "total_billed"],
    )
    result = calculate_credit_liability(calculate_is_breached(df)).collect()[0]

    assert result["is_breached"] is False
    assert result["credit_liability"] == 0.0