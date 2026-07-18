import pandas as pd
import json
import os

os.makedirs("sample_data/preview", exist_ok=True)

# CSV sources — first 2000 rows is plenty to show structure
for name in ["shipment_master", "billing_extract"]:
    df = pd.read_csv(f"sample_data/raw/{name}.csv", nrows=2000)
    df.to_csv(f"sample_data/preview/{name}_sample.csv", index=False)
    print(f"{name}: wrote {len(df)} rows")

# JSONL — read line-by-line so we never load the full 773MB into memory at once
with open("sample_data/raw/raw_scan_events.jsonl", "r") as infile, \
     open("sample_data/preview/raw_scan_events_sample.jsonl", "w") as outfile:
    for i, line in enumerate(infile):
        if i >= 2000:
            break
        outfile.write(line)
print("raw_scan_events: wrote 2000 lines")

# Final output — same row-limit approach
df = pd.read_csv("sample_data/output/final_shipments.csv", nrows=2000)
df.to_csv("sample_data/preview/final_shipments_sample.csv", index=False)
print(f"final_shipments: wrote {len(df)} rows")