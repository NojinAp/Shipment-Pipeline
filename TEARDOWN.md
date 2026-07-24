# Teardown and Cost Plan

This project runs on real, billable AWS infrastructure, not a simulation. This document lists what actually costs money, roughly how much, and how to tear it down cleanly when the project is no longer being actively worked on.

## What bills continuously, regardless of use

These run 24/7 once created, whether or not the pipeline is actively being triggered.

**RDS instance (`shipment-pipeline-source-db`, db.t3.micro)**
This is the single largest ongoing cost. A `db.t3.micro` runs on the order of $15 to $20 USD per month if left running continuously, plus a small amount for the 20 GB of allocated storage. This is the first thing to stop between work sessions.

- To pause temporarily: RDS console, select the instance, Actions, Stop. Note that AWS automatically restarts a stopped RDS instance after 7 days, so this isn't a permanent off switch, only a way to avoid paying while not actively working on the project for a few days.
- To remove entirely: `terraform destroy -target=aws_db_instance.shipment_source`, or delete manually in the console (skip final snapshot, since `skip_final_snapshot = true` is already set).

**Kinesis Data Stream**
A provisioned stream (1 shard) bills a small fixed hourly rate regardless of whether data is flowing through it, on the order of a few dollars a month. Not urgent to tear down given how small this is, but it's not free just because it's idle.

## What bills per use, not continuously

These only cost money when they actually run, so they're not a concern to leave in place between sessions.

- **Glue jobs** (extract, transform, load): billed per DPU-hour of actual job runtime. At this data scale, each run costs a small fraction of a cent to a few cents.
- **Step Functions**: billed per state transition, negligible at this scale.
- **Lambda** (hourly shipment producer): billed per invocation and execution time, negligible.
- **Firehose**: billed per GB ingested, negligible at this data volume.
- **S3 storage**: a few cents a month at the current data size (a few hundred MB across all layers).
- **SNS, CloudWatch Alarms, EventBridge rules**: free or effectively free at this volume.
- **SageMaker training jobs**: billed per instance-hour of actual training time. The DeepAR training jobs run for a few minutes each on `ml.c5.xlarge`, so each run cost well under a dollar. Deliberately did not stand up a persistent SageMaker inference endpoint (which does bill continuously like RDS) since the notebook evaluates the model directly against its own test set rather than deploying it for live predictions.

## What to actually tear down for a full stop

If the project is done being actively developed and the goal is to stop all billing:

1. **RDS instance.** The biggest recurring cost, tear this down first.
2. **SageMaker Studio domain.** If a Studio app is left running, it bills per instance-hour like RDS does. Stop any running Studio app (Studio, user profile, Spaces/Apps, Stop), and if the whole project is done, delete the domain entirely.
3. **Kinesis stream and Firehose delivery stream.** Small ongoing cost, worth removing for a truly clean teardown.
4. Everything else (Glue jobs, Step Functions, Lambda, S3, SNS, CloudWatch, EventBridge) can either be destroyed via Terraform along with the above, or left in place indefinitely, since they cost nothing while idle.

The cleanest way to tear down everything Terraform manages at once:
```
terraform destroy
```
This removes every resource in `main.tf` in one pass. Since state is stored remotely in S3, running this from any machine with the right AWS credentials will correctly tear down the real infrastructure, not just the local view of it.

## Rough total cost estimate

For the several days this project was actively built and tested, with the RDS instance running continuously and everything else billed per use, total spend was on the order of a few dollars, most of it from RDS. AWS's own Cost Anomaly Detection flagged one anomaly during development (a $0.23 spike from repeated Glue job runs while debugging), which is normal and expected during active iteration, not a sign of a leak.

If this project were left running indefinitely without ever tearing down RDS, the ongoing cost would land around $15 to $20 USD per month, almost entirely from the database sitting idle.