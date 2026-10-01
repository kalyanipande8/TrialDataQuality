"""
simulate_site_data.py

Simulates multi-site clinical trial data (9 sites) for a comparative
data-quality monitoring exercise. Unlike a single-pool database-lock QC
run, the point here is SITE COMPARISON: data-quality issues are injected
at deliberately uneven rates across sites, so that some sites are clearly
worse than others -- mirroring the real job of a data manager who has to
triage which sites need a monitoring visit or retraining first.

All data is synthetic. No real patient data is used anywhere.

Output:
    data/raw/site_data.csv            -- all subject visit records, all sites
    data/raw/injected_issues_log.csv  -- ground truth of every injected issue
    data/raw/site_roster.csv          -- site metadata (coordinator, region, intended quality tier)
"""

import csv
import os
import random
from datetime import date, timedelta

RNG_SEED = 42
random.seed(RNG_SEED)

OUT_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")
os.makedirs(OUT_DIR, exist_ok=True)

ENROLLMENT_START = date(2024, 1, 15)
ENROLLMENT_END = date(2024, 11, 30)

VISITS = ["Screening", "Baseline", "Week 4", "Week 12", "Week 24", "End of Study"]

# 9 sites, with a deliberately uneven "true" quality tier that drives the
# injection rate below. Sites are not told their tier -- it emerges from
# the validation results.
SITES = [
    {"site_id": "S01", "site_name": "Stony Brook Univ. Medical Center", "coordinator": "J. Alvarez", "region": "Northeast", "n_subjects": 45, "issue_rate": 0.02},
    {"site_id": "S02", "site_name": "Lakeshore Clinical Research",      "coordinator": "M. Chen",     "region": "Midwest",   "n_subjects": 38, "issue_rate": 0.03},
    {"site_id": "S03", "site_name": "Desert Valley Trials Center",      "coordinator": "R. Osei",     "region": "Southwest", "n_subjects": 30, "issue_rate": 0.18},
    {"site_id": "S04", "site_name": "Riverside Family Health",         "coordinator": "T. Nguyen",   "region": "West",      "n_subjects": 42, "issue_rate": 0.04},
    {"site_id": "S05", "site_name": "Granite State Research Partners",  "coordinator": "K. O'Brien",  "region": "Northeast", "n_subjects": 28, "issue_rate": 0.07},
    {"site_id": "S06", "site_name": "Bayou Clinical Associates",       "coordinator": "D. Fontenot", "region": "South",     "n_subjects": 33, "issue_rate": 0.22},
    {"site_id": "S07", "site_name": "Cascade Medical Research",        "coordinator": "L. Park",     "region": "West",      "n_subjects": 36, "issue_rate": 0.03},
    {"site_id": "S08", "site_name": "Heartland Trial Network",         "coordinator": "S. Patel",    "region": "Midwest",   "n_subjects": 31, "issue_rate": 0.06},
    {"site_id": "S09", "site_name": "Pine Ridge Clinical Site",        "coordinator": "A. Whitfeather", "region": "South",  "n_subjects": 26, "issue_rate": 0.12},
]

ISSUE_CATEGORIES = [
    "out_of_range",
    "missing_required",
    "inconsistent_date",
    "duplicate_record",
]


def random_date(start, end):
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def make_clean_record(subject_id, site_id, visit_idx, enrollment_date):
    """Build a single clean, internally consistent visit record."""
    visit_name = VISITS[visit_idx]
    visit_date = enrollment_date + timedelta(days=visit_idx * 28 + random.randint(-2, 2))
    age = random.randint(21, 78)
    weight_kg = round(random.gauss(78, 14), 1)
    weight_kg = max(45.0, min(140.0, weight_kg))
    height_cm = round(random.gauss(170, 10), 1)
    sbp = random.randint(100, 139)
    dbp = random.randint(65, 89)
    heart_rate = random.randint(55, 95)
    temp_c = round(random.gauss(36.8, 0.3), 1)
    alt_u_l = random.randint(10, 40)      # liver enzyme, normal range
    creatinine_mg_dl = round(random.gauss(0.9, 0.15), 2)
    adverse_event = random.choices(["None", "Mild", "Moderate", "Severe"], weights=[75, 15, 8, 2])[0]
    return {
        "record_id": f"{site_id}-{subject_id}-{visit_idx:02d}",
        "site_id": site_id,
        "subject_id": subject_id,
        "visit_name": visit_name,
        "visit_date": visit_date.isoformat(),
        "enrollment_date": enrollment_date.isoformat(),
        "age": age,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "systolic_bp": sbp,
        "diastolic_bp": dbp,
        "heart_rate": heart_rate,
        "temp_c": temp_c,
        "alt_u_l": alt_u_l,
        "creatinine_mg_dl": creatinine_mg_dl,
        "adverse_event": adverse_event,
    }


def inject_issue(record, category, issues_log):
    """Mutate `record` in place to inject one issue of the given category.
    Logs ground truth to issues_log. Returns the (possibly additional)
    record to append for duplicate injection, or None.
    """
    rid = record["record_id"]

    if category == "out_of_range":
        field = random.choice(["systolic_bp", "diastolic_bp", "heart_rate", "temp_c", "alt_u_l", "weight_kg"])
        bad_values = {
            "systolic_bp": random.choice([38, 260, -5]),
            "diastolic_bp": random.choice([10, 190]),
            "heart_rate": random.choice([2, 280]),
            "temp_c": random.choice([21.0, 44.5]),
            "alt_u_l": random.choice([-3, 850]),
            "weight_kg": random.choice([1.2, 410]),
        }
        old_val = record[field]
        record[field] = bad_values[field]
        issues_log.append({
            "record_id": rid, "site_id": record["site_id"], "category": category,
            "field": field, "original_value": old_val, "injected_value": record[field],
        })

    elif category == "missing_required":
        field = random.choice(["age", "visit_date", "weight_kg", "adverse_event", "enrollment_date"])
        old_val = record[field]
        record[field] = ""
        issues_log.append({
            "record_id": rid, "site_id": record["site_id"], "category": category,
            "field": field, "original_value": old_val, "injected_value": "",
        })

    elif category == "inconsistent_date":
        mode = random.choice(["before_enrollment", "future_date"])
        old_val = record["visit_date"]
        if mode == "before_enrollment":
            enroll = date.fromisoformat(record["enrollment_date"])
            bad_date = enroll - timedelta(days=random.randint(1, 60))
        else:
            bad_date = date(2027, random.randint(1, 12), random.randint(1, 28))
        record["visit_date"] = bad_date.isoformat()
        issues_log.append({
            "record_id": rid, "site_id": record["site_id"], "category": category,
            "field": "visit_date", "original_value": old_val, "injected_value": record["visit_date"],
        })

    elif category == "duplicate_record":
        dup = dict(record)
        dup["record_id"] = record["record_id"] + "-DUP"
        issues_log.append({
            "record_id": dup["record_id"], "site_id": record["site_id"], "category": category,
            "field": "record_id", "original_value": record["record_id"], "injected_value": dup["record_id"],
        })
        return dup

    return None


def simulate():
    all_records = []
    issues_log = []

    for site in SITES:
        site_id = site["site_id"]
        for s in range(site["n_subjects"]):
            subject_id = f"SUBJ{s+1:03d}"
            enrollment_date = random_date(ENROLLMENT_START, ENROLLMENT_END)
            n_visits = random.randint(3, len(VISITS))  # not everyone completes all visits
            subject_records = []
            for v in range(n_visits):
                rec = make_clean_record(subject_id, site_id, v, enrollment_date)
                subject_records.append(rec)

            # Decide, per record, whether to inject an issue, driven by the
            # site's issue_rate. This naturally produces uneven distribution.
            extra_records = []
            for rec in subject_records:
                if random.random() < site["issue_rate"]:
                    category = random.choice(ISSUE_CATEGORIES)
                    dup = inject_issue(rec, category, issues_log)
                    if dup is not None:
                        extra_records.append(dup)
            all_records.extend(subject_records)
            all_records.extend(extra_records)

    return all_records, issues_log


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    records, issues_log = simulate()

    record_fields = [
        "record_id", "site_id", "subject_id", "visit_name", "visit_date",
        "enrollment_date", "age", "weight_kg", "height_cm", "systolic_bp",
        "diastolic_bp", "heart_rate", "temp_c", "alt_u_l", "creatinine_mg_dl",
        "adverse_event",
    ]
    write_csv(os.path.join(OUT_DIR, "site_data.csv"), records, record_fields)

    issue_fields = ["record_id", "site_id", "category", "field", "original_value", "injected_value"]
    write_csv(os.path.join(OUT_DIR, "injected_issues_log.csv"), issues_log, issue_fields)

    site_fields = ["site_id", "site_name", "coordinator", "region", "n_subjects", "issue_rate"]
    write_csv(os.path.join(OUT_DIR, "site_roster.csv"), SITES, site_fields)

    print(f"Simulated {len(records)} records across {len(SITES)} sites.")
    print(f"Injected {len(issues_log)} ground-truth issues.")
    by_cat = {}
    for issue in issues_log:
        by_cat[issue["category"]] = by_cat.get(issue["category"], 0) + 1
    for cat, n in sorted(by_cat.items()):
        print(f"  {cat}: {n}")


if __name__ == "__main__":
    main()
