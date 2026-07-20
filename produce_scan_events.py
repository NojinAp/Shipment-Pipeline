import os
import json
import time
import boto3
from dotenv import load_dotenv

load_dotenv()

client = boto3.client("kinesis", region_name="ca-central-1")
STREAM_NAME = "shipment-pipeline-scan-events"

with open("sample_data/raw/raw_scan_events.jsonl", "r") as f:
    for i, line in enumerate(f):
        event = json.loads(line)

        client.put_record(
            StreamName=STREAM_NAME,
            Data=json.dumps(event).encode("utf-8"),
            PartitionKey=event["shipment_id"],
        )

        if i % 100 == 0:
            print(f"Sent {i} events...")

        if i >= 2000:
            break

        time.sleep(0.05)

print("Done sending events.")