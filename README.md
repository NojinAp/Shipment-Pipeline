# Shipment Pipeline

An end to end data pipeline that flags SLA/FDA (first delivery attempt) breaches and calculates credit liability for guaranteed shipments that were delivered late. Built as a portfolio project to mirror the real production patterns I learned during a data engineering co-op, using real AWS infrastructure and synthetic data at a realistic scale (1M+ shipment records spanning 2011 to 2026).

Repo: github.com/NojinAp/Shipment-Pipeline

## What it does

The pipeline ingests shipment bookings, billing records, and package scan events from three separate sources, cleans and joins them, and produces a final table showing whether each guaranteed shipment breached its delivery promise and how much credit liability that breach creates. On top of that, a Gold layer forecasts future credit liability by service tier, comparing a few different modeling approaches.

## Tech stack

AWS Glue (PySpark), Step Functions, Redshift Serverless, RDS (Postgres), Kinesis Data Streams and Firehose, Lambda, EventBridge, CloudWatch, SNS, S3, SageMaker, Terraform, Python (boto3, psycopg2, redshift_connector), pytest.

## Architecture

Two ingestion paths feed into one S3 raw zone.

**Batch path:** an hourly EventBridge schedule triggers a Lambda that inserts new shipment bookings into RDS Postgres (the operational source of truth, since it has real enforced primary and foreign keys). A sync script truncates and reloads Redshift from RDS, then unloads that data to S3.

**Streaming path:** a producer script pushes scan events (package pickup, delivery attempts, etc.) onto a Kinesis stream, which Firehose delivers into S3, hour partitioned. Scan events never touch RDS or Redshift, since that's a more realistic shape for high volume event data than a relational table.

From there, Step Functions orchestrates three sequential Glue jobs.

- **Extract:** reads the raw CSV/JSON from both paths and writes typed Parquet.
- **Transform:** runs six data quality checks (orphaned and duplicate billing, orphaned and duplicate scan events, duplicate and bad date shipments), quarantining anything that fails, and derives each shipment's first delivery attempt and actual delivery date from the scan events.
- **Load:** joins everything into a final shipment level table and calculates `is_breached` and `credit_liability`.

## Key design decisions

**RDS as the real operational source.** Redshift only documents its constraints, it doesn't enforce them, so RDS is where duplicate/orphan prevention actually happens. Historical data was loaded into RDS using Postgres's native `aws_s3` extension rather than a local file import.

**Backfill and ongoing activity are kept separate.** Bookings have both a one time historical backfill script and a genuinely-running hourly Lambda for ongoing activity. I deliberately didn't fake continuous history, since AWS's own timestamps would contradict it.

**Redshift is fully truncated and reloaded on every sync**, not incremental. Simpler, and still a legitimate strategy at this data size.

**Testable logic is pulled out of the Glue scripts.** Both `transform.py` and `load.py` import their core business logic (duplicate/orphan detection, breach and liability calculation) from separate modules (`transform_logic.py`, `load_logic.py`) so it can be unit tested with pytest without needing to run an actual Glue job.

## Monitoring and alerting

Two independent layers feed the same SNS topic, which emails on failure.

- **Glue job level:** an EventBridge rule watches for Glue job state change events (FAILED, TIMEOUT, STOPPED) on each individual job and publishes to SNS the moment one happens.
- **Pipeline level:** a CloudWatch Alarm watches the Step Functions state machine's `ExecutionsFailed` metric, catching failures that might not come from a Glue job specifically (a bad IAM permission on the state machine itself, for example), as a redundant backup to the EventBridge layer.

## Testing and CI/CD

`tests/test_transform_logic.py` and `tests/test_load_logic.py` cover the core data quality and business logic functions with pytest, including edge cases like unresolved delivery status staying null instead of defaulting to a value, and non-guaranteed shipments never being charged regardless of breach status.

GitHub Actions runs the full pytest suite on every push and pull request to main. A second job runs `terraform plan` in CI as well, using a remote S3 backend for Terraform state (shared between my local machine and GitHub Actions) so infrastructure changes are visible before they're applied. `terraform apply` itself is still run manually, which is a deliberate choice: auto-applying infrastructure changes on every push is a real risk without more safeguards than a project this size has, and most real teams gate the actual apply behind manual approval even when the plan itself is automated.

## Forecasting

The Gold layer forecasts quarterly credit liability by service tier, comparing four approaches head to head using MAPE (mean absolute percentage error) on a time based holdout:

| Model | MAPE (quarterly) |
|---|---|
| Naive baseline (same quarter last year) | 13.06% |
| Trend-only regression | 7.37% |
| Trend + seasonality regression | 7.93% |
| Random Forest | 12.16% |

Trend-only regression won at every grain tested. Random Forest underperformed both regressions since tree based models can't extrapolate a trend past the range they were trained on, and this dataset has a clear ongoing upward trend.

I also trained AWS SageMaker DeepAR, a neural forecasting model that learns patterns across multiple related time series at once, as a fourth candidate. Two versions were tested, one using only the raw series and one adding a categorical feature to distinguish the three service tiers.

| Model | Metric | Value |
|---|---|---|
| DeepAR (no categorical feature) | mean weighted quantile loss | 0.0892 |
| DeepAR (with categorical feature) | mean weighted quantile loss | 0.0948 |

Adding the categorical feature made DeepAR slightly worse rather than better, most likely because there are only three series here with a fairly short history each, not enough examples per category for the extra model capacity to pay off. DeepAR's best result (roughly 8.9% by this metric) didn't beat trend-only regression's 7.37% MAPE either, though the two metrics aren't computed identically so this isn't a perfectly apples to apples comparison. Trend-only regression remains the production recommendation: simpler to deploy, and at least as accurate on this dataset. DeepAR would likely be more competitive with more related series to learn across, or messier data without such a clean trend.

## Known issues and lessons learned

A few real bugs came up while building this, worth documenting since they're genuinely instructive.

**Missing deploy step for a refactored module.** When I split `transform.py`'s duplicate and orphan detection logic into a separate `transform_logic.py` file so it could be pytest tested, I never actually wired it into the Glue job's deployment. Tests passed locally, but the actual Glue job failed in production with `ModuleNotFoundError`, since Glue only sees files explicitly listed in its `--extra-py-files` argument. Passing tests and a correct deploy config are two separate things that can silently diverge. Fixed by adding the missing Terraform resource and argument, and the same care was taken when `load_logic.py` was added later.

**Historical data completeness gap in scan events.** Bookings and billing had a proper one time historical backfill into RDS, but scan events only ever had the ongoing streaming producer, with no equivalent backfill. This meant `is_breached` resolved to null for one hundred percent of the 1M+ historical rows, since no shipment outside the producer's brief live run window had any scan events to derive a delivery outcome from. Fixed with a one time historical scan events file uploaded directly to S3 and a full pipeline re-run.

**SageMaker Python SDK v3.** AWS shipped a major breaking change to the SageMaker SDK partway through this project, restructuring it into several submodules and leaving the top level `sagemaker` package as an empty meta-package. This broke standard DeepAR training code that every existing tutorial uses. Fixed by pinning to the SDK's v2 branch.

**A bug in the SageMaker Estimator class itself.** Even on the correct SDK version, the high level `Estimator` class kept injecting an `Environment` field into the training request that SageMaker's built-in algorithms reject outright, regardless of which Debugger or telemetry settings were disabled. Fixed by dropping to a direct boto3 `create_training_job` call instead of going through the high level SDK wrapper at all.

## Cost and Teardown

This project runs on real, billable AWS infrastructure. See [TEARDOWN.md](./TEARDOWN.md) for what actually costs money, roughly how much, and how to tear it down cleanly.

## In progress
- Glue Data Catalog, a Crawler, and Athena, to allow SQL querying over the S3 data directly.