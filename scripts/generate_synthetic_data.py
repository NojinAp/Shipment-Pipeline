"""
Synthetic data generator for the FADR / SLA-breach project.

"""

import json
import random
import uuid
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta

random.seed(42)

# Config
END_DATE = date.today()
START_DATE = END_DATE - relativedelta(years=15)
TOTAL_DAYS = (END_DATE - START_DATE).days

BASE_DAILY_VOLUME = 130
ANNUAL_GROWTH_RATE = 0.06
HOLIDAY_MULTIPLIER = 1.3
SUNDAY_MULTIPLIER = 0.35

REGIONS_WEIGHTED = {
    "GTA": 0.40,
    "Montreal": 0.20,
    "Vancouver": 0.15,
    "Calgary-Edmonton": 0.15,
    "Atlantic": 0.10,
}

HUBS_BY_REGION = {
    "GTA": ["GTA-HUB-01", "GTA-HUB-02", "GTA-HUB-03"],
    "Montreal": ["MTL-HUB-01", "MTL-HUB-02"],
    "Vancouver": ["VAN-HUB-01", "VAN-HUB-02"],
    "Calgary-Edmonton": ["CAL-HUB-01", "EDM-HUB-01"],
    "Atlantic": ["ATL-HUB-01"],
}

SERVICE_TIERS = {
    "GROUND": {"weight": 0.70, "offset_days": 3},
    "EXPRESS": {"weight": 0.22, "offset_days": 2},
    "SAME_DAY": {"weight": 0.08, "offset_days": 0},
}

SAME_DAY_CUTOFF_HOUR = 15  # 3pm

CUSTOMER_TYPES = {"RESIDENTIAL": 0.65, "COMMERCIAL": 0.35}
BASE_FDA_SUCCESS = {"RESIDENTIAL": 0.78, "COMMERCIAL": 0.90}
DOW_PENALTY = {0: 0.06, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.05, 5: 0.02, 6: 0.03}  # Mon=0

FAIL_REASONS_RESIDENTIAL = ["FAILED_NO_ONE_HOME", "FAILED_NO_ACCESS", "FAILED_REFUSED"]
FAIL_REASONS_RESIDENTIAL_W = [0.75, 0.15, 0.10]
FAIL_REASONS_COMMERCIAL = ["FAILED_NO_ACCESS", "FAILED_NO_ONE_HOME", "FAILED_REFUSED"]
FAIL_REASONS_COMMERCIAL_W = [0.60, 0.30, 0.10]

PCT_STILL_IN_TRANSIT_RECENT = 0.15
PCT_ORPHAN_SCAN_EVENTS = 0.005
PCT_DUPLICATE_SUCCESS = 0.003

GUARANTEE_BASE_RATE = {"RESIDENTIAL": 0.12, "COMMERCIAL": 0.30}
GUARANTEE_TIER_MULTIPLIER = {"GROUND": 1.0, "EXPRESS": 1.4, "SAME_DAY": 1.8}

PCT_EXTERNAL_DELAY = 0.03
EXTERNAL_DELAY_HOURS = (24, 72)

WEIGHT_KG_RANGE_BY_TIER = {
    "GROUND": (1.0, 25.0),
    "EXPRESS": (0.5, 12.0),
    "SAME_DAY": (0.2, 5.0),
}

# Billing (separate finance-system extract)
BASE_RATE_PER_KG_START = {"GROUND": 1.20, "EXPRESS": 2.50, "SAME_DAY": 5.00}
RATE_ESCALATION_PER_YEAR = 0.03  # ~3%/year freight rate-card increase
MIN_BASE_RATE_START = {"GROUND": 8.00, "EXPRESS": 15.00, "SAME_DAY": 25.00}
GUARANTEE_FEE_FLAT = {"GROUND": 5.00, "EXPRESS": 8.00, "SAME_DAY": 12.00}
INVOICE_DELAY_HOURS = (6, 30)

# Fuel surcharge: modeled as a monthly random-walk index, not a constant.
# Real carrier surcharges are published monthly, indexed to fuel prices.
FUEL_SURCHARGE_START = 0.145
FUEL_SURCHARGE_MIN = 0.08
FUEL_SURCHARGE_MAX = 0.22
FUEL_SURCHARGE_MONTHLY_STEP = 0.01  # max monthly drift


def weighted_choice(weighted_dict):
    return random.choices(list(weighted_dict.keys()), weights=list(weighted_dict.values()), k=1)[0]


def is_holiday_period(d: date) -> bool:
    return (d.month == 11 and d.day >= 15) or (d.month == 12 and d.day <= 24)


def daily_volume_for(d: date) -> int:
    years_elapsed = (d - START_DATE).days / 365.0
    growth_factor = (1 + ANNUAL_GROWTH_RATE) ** years_elapsed
    vol = BASE_DAILY_VOLUME * growth_factor
    if is_holiday_period(d):
        vol *= HOLIDAY_MULTIPLIER
    if d.weekday() == 6:
        vol *= SUNDAY_MULTIPLIER
    vol *= random.uniform(0.9, 1.1)
    return max(1, int(round(vol)))


def is_guaranteed_for(customer_type, service_tier):
    rate = GUARANTEE_BASE_RATE[customer_type] * GUARANTEE_TIER_MULTIPLIER[service_tier]
    rate = min(0.95, rate)
    return random.random() < rate


def build_fuel_surcharge_index():
    """One surcharge % per (year, month) across the window, via a bounded
    random walk -- reflects real monthly-indexed fuel surcharge revisions."""
    index = {}
    current_rate = FUEL_SURCHARGE_START
    y, m = START_DATE.year, START_DATE.month
    end_y, end_m = END_DATE.year, END_DATE.month
    while (y, m) <= (end_y, end_m):
        step = random.uniform(-FUEL_SURCHARGE_MONTHLY_STEP, FUEL_SURCHARGE_MONTHLY_STEP)
        current_rate = min(FUEL_SURCHARGE_MAX, max(FUEL_SURCHARGE_MIN, current_rate + step))
        index[(y, m)] = round(current_rate, 4)
        m += 1
        if m > 12:
            m = 1
            y += 1
    return index


def rate_escalation_multiplier(d: date) -> float:
    years_elapsed = (d - START_DATE).days / 365.0
    return (1 + RATE_ESCALATION_PER_YEAR) ** years_elapsed


def gen_billing_record(shipment_id, service_tier, weight_kg, is_guaranteed, booking_ts, fuel_index):
    escalation = rate_escalation_multiplier(booking_ts.date())
    per_kg = BASE_RATE_PER_KG_START[service_tier] * escalation
    min_rate = MIN_BASE_RATE_START[service_tier] * escalation

    base_rate = round(max(min_rate, weight_kg * per_kg), 2)

    invoice_date = (booking_ts + timedelta(hours=random.uniform(*INVOICE_DELAY_HOURS))).date()
    fuel_surcharge_pct = fuel_index[(invoice_date.year, invoice_date.month)]
    fuel_surcharge = round(base_rate * fuel_surcharge_pct, 2)

    guarantee_fee = GUARANTEE_FEE_FLAT[service_tier] if is_guaranteed else 0.0
    total_billed = round(base_rate + fuel_surcharge + guarantee_fee, 2)

    return {
        "shipment_id": shipment_id,
        "invoice_date": invoice_date.isoformat(),
        "base_rate": base_rate,
        "fuel_surcharge_pct": fuel_surcharge_pct,
        "fuel_surcharge_amount": fuel_surcharge,
        "guarantee_fee": guarantee_fee,
        "total_billed": total_billed,
    }


def gen_shipment_master_and_events(fuel_index):
    master_rows = []
    billing_rows = []
    events = []
    shipment_counter = 0

    current = START_DATE
    while current <= END_DATE:
        n_today = daily_volume_for(current)
        days_from_end = (END_DATE - current).days

        for _ in range(n_today):
            shipment_id = f"SHP-{shipment_counter:08d}"
            shipment_counter += 1

            region = weighted_choice(REGIONS_WEIGHTED)
            customer_type = weighted_choice(CUSTOMER_TYPES)
            service_tier = weighted_choice({k: v["weight"] for k, v in SERVICE_TIERS.items()})
            hub = random.choice(HUBS_BY_REGION[region])
            guaranteed = is_guaranteed_for(customer_type, service_tier)
            weight_kg = round(random.uniform(*WEIGHT_KG_RANGE_BY_TIER[service_tier]), 2)

            booking_ts = datetime.combine(current, datetime.min.time()) + timedelta(
                hours=random.uniform(6, 20)
            )
            offset_days = SERVICE_TIERS[service_tier]["offset_days"]

            if service_tier == "SAME_DAY" and booking_ts.hour >= SAME_DAY_CUTOFF_HOUR:
                promised_delivery_date = (booking_ts + timedelta(days=1)).date()
            else:
                promised_delivery_date = (booking_ts + timedelta(days=offset_days)).date()

            master_rows.append({
                "shipment_id": shipment_id,
                "booking_timestamp": booking_ts.isoformat(),
                "promised_delivery_date": promised_delivery_date.isoformat(),
                "region": region,
                "customer_type": customer_type,
                "service_tier": service_tier,
                "is_guaranteed": guaranteed,
                "weight_kg": weight_kg,
            })

            billing_rows.append(
                gen_billing_record(shipment_id, service_tier, weight_kg, guaranteed, booking_ts, fuel_index)
            )

            can_be_in_transit = days_from_end <= 4
            in_transit = can_be_in_transit and random.random() < PCT_STILL_IN_TRANSIT_RECENT

            events.extend(
                _gen_events_for_shipment(shipment_id, region, customer_type, service_tier,
                                          hub, booking_ts, in_transit)
            )

        current += timedelta(days=1)

    return master_rows, billing_rows, events


def _gen_events_for_shipment(shipment_id, region, customer_type, service_tier, hub, booking_ts, in_transit):
    events = []

    external_delay = timedelta(0)
    if random.random() < PCT_EXTERNAL_DELAY:
        external_delay = timedelta(hours=random.uniform(*EXTERNAL_DELAY_HOURS))

    if service_tier == "SAME_DAY":
        t = booking_ts + timedelta(hours=random.uniform(0.5, 2)) + external_delay
        events.append(_event(shipment_id, "PICKUP", t, hub))
        attempt_time = t + timedelta(hours=random.uniform(2, 6))
    else:
        t = booking_ts + timedelta(hours=random.uniform(2, 8)) + external_delay
        events.append(_event(shipment_id, "PICKUP", t, hub))

        t = t + timedelta(hours=random.uniform(3, 10))
        events.append(_event(shipment_id, "HUB_SCAN", t, hub))

        attempt_time = t + timedelta(hours=random.uniform(10, 30))

    dow = attempt_time.weekday()
    base_rate = BASE_FDA_SUCCESS[customer_type]
    if customer_type == "RESIDENTIAL":
        base_rate -= DOW_PENALTY.get(dow, 0)
    base_rate = max(0.05, min(0.98, base_rate))

    max_attempts = 1 if in_transit else 3
    delivered = False

    for attempt_num in range(1, max_attempts + 1):
        if in_transit:
            success = False
        elif attempt_num == max_attempts:
            success = True
        else:
            rate = base_rate if attempt_num == 1 else min(0.95, base_rate + 0.15)
            success = random.random() < rate

        if success:
            events.append(_event(shipment_id, "DELIVERY_ATTEMPT", attempt_time, hub,
                                  attempt_number=attempt_num, attempt_result="SUCCESS"))
            delivered = True
            break
        else:
            reasons = FAIL_REASONS_RESIDENTIAL if customer_type == "RESIDENTIAL" else FAIL_REASONS_COMMERCIAL
            weights = FAIL_REASONS_RESIDENTIAL_W if customer_type == "RESIDENTIAL" else FAIL_REASONS_COMMERCIAL_W
            reason = random.choices(reasons, weights=weights, k=1)[0]
            events.append(_event(shipment_id, "DELIVERY_ATTEMPT", attempt_time, hub,
                                  attempt_number=attempt_num, attempt_result=reason))
            attempt_time += timedelta(days=random.uniform(1, 1.5))

    if delivered and random.random() < PCT_DUPLICATE_SUCCESS:
        dup_time = attempt_time + timedelta(hours=random.uniform(1, 5))
        events.append(_event(shipment_id, "DELIVERY_ATTEMPT", dup_time, hub,
                              attempt_number=max_attempts, attempt_result="SUCCESS"))

    return events


def _event(shipment_id, event_type, ts, hub, attempt_number=None, attempt_result=None):
    rec = {
        "event_id": str(uuid.uuid4()),
        "shipment_id": shipment_id,
        "event_type": event_type,
        "event_timestamp": ts.isoformat(),
        "carrier_hub": hub,
        "ingestion_date": ts.date().isoformat(),
    }
    if attempt_number is not None:
        rec["attempt_number"] = attempt_number
        rec["attempt_result"] = attempt_result
    return rec


def inject_orphan_events(events, num_master_shipments):
    num_orphans = int(num_master_shipments * PCT_ORPHAN_SCAN_EVENTS)
    all_hubs = [h for hubs in HUBS_BY_REGION.values() for h in hubs]
    for _ in range(num_orphans):
        fake_id = f"SHP-ORPHAN-{random.randint(0, 999999):06d}"
        hub = random.choice(all_hubs)
        random_offset = random.uniform(0, TOTAL_DAYS)
        ts = datetime.combine(START_DATE, datetime.min.time()) + timedelta(days=random_offset)
        events.append(_event(fake_id, "HUB_SCAN", ts, hub))
    return events


def write_csv(path, rows, fieldnames):
    import csv
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    import os
    REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    OUT_DIR = os.path.join(REPO_ROOT, "sample_data", "raw")
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Simulating {START_DATE} to {END_DATE} ({TOTAL_DAYS} days)...")
    fuel_index = build_fuel_surcharge_index()
    master_rows, billing_rows, events = gen_shipment_master_and_events(fuel_index)
    print(f"Generated {len(master_rows)} shipments, {len(billing_rows)} billing records, {len(events)} scan events")

    events = inject_orphan_events(events, len(master_rows))
    print(f"After injecting orphans: {len(events)} scan events")

    write_csv(
        os.path.join(OUT_DIR, "shipment_master.csv"),
        master_rows,
        ["shipment_id", "booking_timestamp", "promised_delivery_date",
         "region", "customer_type", "service_tier", "is_guaranteed", "weight_kg"],
    )
    write_csv(
        os.path.join(OUT_DIR, "billing_extract.csv"),
        billing_rows,
        ["shipment_id", "invoice_date", "base_rate", "fuel_surcharge_pct",
         "fuel_surcharge_amount", "guarantee_fee", "total_billed"],
    )
    write_jsonl(os.path.join(OUT_DIR, "raw_scan_events.jsonl"), events)
    print(f"Wrote shipment_master.csv, billing_extract.csv, and raw_scan_events.jsonl to {OUT_DIR}")