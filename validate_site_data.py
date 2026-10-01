"""
validate_site_data.py

Automated multi-site data quality validation engine for clinical trial
data. Runs the same four edit-check categories against EVERY site's data
independently, then rolls results up into a per-site quality score and
a cross-site ranking -- the core deliverable of a multi-site comparative
quality monitoring program (as distinct from a single-pool QC accuracy
metric).

Validation categories:
    1. Completeness   -- required fields present and non-blank
    2. Range checks   -- vitals/labs within plausible physiological bounds
    3. Cross-field consistency -- visit_date >= enrollment_date, not in future
    4. Duplicate detection -- records that are exact or near-exact dupes of
       another record for the same subject/visit

Outputs:
    output/flagged_records.csv       -- every flagged record, reason, site
    output/site_quality_scores.csv   -- per-site score + rank
    output/validation_summary.csv    -- per-site x per-category counts
    output/reports/<SITE_ID>_audit_report.md -- one audit report per site
    output/reports/compliance_report.md      -- cross-site compliance rollup
"""

import csv
import os
from collections import defaultdict
from datetime import date, datetime

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
OUT_DIR = os.path.join(BASE_DIR, "output")
REPORTS_DIR = os.path.join(OUT_DIR, "reports")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

REQUIRED_FIELDS = ["age", "visit_date", "enrollment_date", "weight_kg", "adverse_event"]

RANGE_BOUNDS = {
    "age": (18, 90),
    "weight_kg": (30.0, 250.0),
    "height_cm": (120.0, 215.0),
    "systolic_bp": (70, 220),
    "diastolic_bp": (40, 130),
    "heart_rate": (30, 200),
    "temp_c": (34.0, 41.5),
    "alt_u_l": (0, 200),
    "creatinine_mg_dl": (0.1, 10.0),
}

TODAY = date(2026, 10, 1)


def load_records():
    path = os.path.join(DATA_DIR, "site_data.csv")
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_sites():
    path = os.path.join(DATA_DIR, "site_roster.csv")
    with open(path, newline="") as f:
        return {row["site_id"]: row for row in csv.DictReader(f)}


def to_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def check_completeness(rec):
    missing = [f for f in REQUIRED_FIELDS if rec.get(f, "") in ("", None)]
    return missing


def check_range(rec):
    violations = []
    for field, (lo, hi) in RANGE_BOUNDS.items():
        raw = rec.get(field, "")
        if raw in ("", None):
            continue  # completeness check already covers blanks
        val = to_float(raw)
        if val is None:
            continue
        if val < lo or val > hi:
            violations.append((field, val, lo, hi))
    return violations


def check_dates(rec):
    issues = []
    visit_raw = rec.get("visit_date", "")
    enroll_raw = rec.get("enrollment_date", "")
    if visit_raw and enroll_raw:
        try:
            visit_d = date.fromisoformat(visit_raw)
            enroll_d = date.fromisoformat(enroll_raw)
            if visit_d < enroll_d:
                issues.append(f"visit_date {visit_raw} precedes enrollment_date {enroll_raw}")
            if visit_d > TODAY:
                issues.append(f"visit_date {visit_raw} is in the future (after {TODAY.isoformat()})")
        except ValueError:
            issues.append(f"unparseable date(s): visit_date={visit_raw!r}, enrollment_date={enroll_raw!r}")
    return issues


def check_duplicates(records):
    """Flags records sharing (site_id, subject_id, visit_name, visit_date) --
    same subject, same visit, same date recorded more than once."""
    seen = defaultdict(list)
    for rec in records:
        key = (rec["site_id"], rec["subject_id"], rec["visit_name"], rec.get("visit_date", ""))
        seen[key].append(rec["record_id"])
    dup_record_ids = set()
    for key, ids in seen.items():
        if len(ids) > 1:
            dup_record_ids.update(ids)
    return dup_record_ids


def run_validation(records):
    """Runs all checks. Returns list of flags: dict(record_id, site_id, category, detail)."""
    flags = []
    dup_ids = check_duplicates(records)

    for rec in records:
        rid = rec["record_id"]
        sid = rec["site_id"]

        missing = check_completeness(rec)
        for field in missing:
            flags.append({"record_id": rid, "site_id": sid, "category": "missing_required",
                          "detail": f"required field '{field}' is blank"})

        for field, val, lo, hi in check_range(rec):
            flags.append({"record_id": rid, "site_id": sid, "category": "out_of_range",
                          "detail": f"{field}={val} outside plausible range [{lo}, {hi}]"})

        for detail in check_dates(rec):
            flags.append({"record_id": rid, "site_id": sid, "category": "inconsistent_date",
                          "detail": detail})

        if rid in dup_ids:
            flags.append({"record_id": rid, "site_id": sid, "category": "duplicate_record",
                          "detail": "duplicate subject/visit/date combination detected"})

    return flags


def compute_site_scores(records, flags, sites):
    """Per-site quality score = 1 - (unique flagged records / total records for that site)."""
    total_by_site = defaultdict(int)
    for rec in records:
        total_by_site[rec["site_id"]] += 1

    flagged_ids_by_site = defaultdict(set)
    cat_counts_by_site = defaultdict(lambda: defaultdict(int))
    for flag in flags:
        flagged_ids_by_site[flag["site_id"]].add(flag["record_id"])
        cat_counts_by_site[flag["site_id"]][flag["category"]] += 1

    scores = []
    for site_id, total in total_by_site.items():
        n_flagged = len(flagged_ids_by_site[site_id])
        score = 1 - (n_flagged / total) if total else 0.0
        scores.append({
            "site_id": site_id,
            "site_name": sites.get(site_id, {}).get("site_name", ""),
            "coordinator": sites.get(site_id, {}).get("coordinator", ""),
            "total_records": total,
            "flagged_records": n_flagged,
            "quality_score_pct": round(score * 100, 2),
            "out_of_range": cat_counts_by_site[site_id].get("out_of_range", 0),
            "missing_required": cat_counts_by_site[site_id].get("missing_required", 0),
            "inconsistent_date": cat_counts_by_site[site_id].get("inconsistent_date", 0),
            "duplicate_record": cat_counts_by_site[site_id].get("duplicate_record", 0),
        })

    scores.sort(key=lambda r: r["quality_score_pct"], reverse=True)
    for i, row in enumerate(scores, start=1):
        row["rank"] = i

    return scores


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_site_audit_report(site_row, flags_for_site, path):
    sid = site_row["site_id"]
    lines = []
    lines.append(f"# Site Audit Report -- {sid}: {site_row['site_name']}")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Site Summary")
    lines.append("")
    lines.append(f"- Coordinator: {site_row['coordinator']}")
    lines.append(f"- Total records reviewed: {site_row['total_records']}")
    lines.append(f"- Records flagged: {site_row['flagged_records']}")
    lines.append(f"- Data quality score: {site_row['quality_score_pct']}%")
    lines.append(f"- Cross-site rank: {site_row['rank']} of 9")
    lines.append("")
    lines.append("## Findings by Category")
    lines.append("")
    lines.append("| Category | Count |")
    lines.append("|---|---|")
    lines.append(f"| Out-of-range values | {site_row['out_of_range']} |")
    lines.append(f"| Missing required fields | {site_row['missing_required']} |")
    lines.append(f"| Inconsistent dates | {site_row['inconsistent_date']} |")
    lines.append(f"| Duplicate records | {site_row['duplicate_record']} |")
    lines.append("")
    lines.append("## Detailed Findings")
    lines.append("")
    if flags_for_site:
        lines.append("| Record ID | Category | Detail |")
        lines.append("|---|---|---|")
        for f in sorted(flags_for_site, key=lambda x: (x["category"], x["record_id"])):
            lines.append(f"| {f['record_id']} | {f['category']} | {f['detail']} |")
    else:
        lines.append("No findings -- all records passed all validation checks.")
    lines.append("")
    lines.append("## Recommended Action")
    lines.append("")
    score = site_row["quality_score_pct"]
    if score >= 97:
        action = ("No action required. Continue routine monitoring at the standard "
                  "interval.")
    elif score >= 90:
        action = ("Minor action: send a written query for the flagged records above and "
                  "include a reminder of the relevant SOP in the next site newsletter.")
    elif score >= 80:
        action = ("Moderate action: schedule a remote retraining call with the site "
                  "coordinator covering the categories above before the next enrollment "
                  "wave; re-audit within 30 days.")
    else:
        action = ("Escalate: schedule an in-person or video monitoring visit, issue a "
                  "formal corrective and preventive action (CAPA) request, and place the "
                  "site on a 100% source-data-verification hold until re-audit shows "
                  "sustained improvement.")
    lines.append(action)
    lines.append("")

    with open(path, "w") as f:
        f.write("\n".join(lines))


def write_compliance_report(scores, total_records, total_flagged, path):
    lines = []
    lines.append("# Cross-Site Compliance Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Study-Wide Summary")
    lines.append("")
    lines.append(f"- Sites monitored: {len(scores)}")
    lines.append(f"- Total records validated: {total_records}")
    lines.append(f"- Total unique flagged records: {total_flagged}")
    overall_score = round(100 * (1 - total_flagged / total_records), 2) if total_records else 0
    lines.append(f"- Study-wide data quality score: {overall_score}%")
    lines.append("")
    lines.append("## Site Ranking (best to worst)")
    lines.append("")
    lines.append("| Rank | Site | Coordinator | Records | Flagged | Quality Score |")
    lines.append("|---|---|---|---|---|---|")
    for row in scores:
        lines.append(
            f"| {row['rank']} | {row['site_id']} -- {row['site_name']} | {row['coordinator']} "
            f"| {row['total_records']} | {row['flagged_records']} | {row['quality_score_pct']}% |"
        )
    lines.append("")
    lines.append("## Sites Requiring Escalation (score < 80%)")
    lines.append("")
    escalate = [r for r in scores if r["quality_score_pct"] < 80]
    if escalate:
        for row in escalate:
            lines.append(f"- **{row['site_id']} ({row['site_name']})** -- {row['quality_score_pct']}%, "
                          f"flagged {row['flagged_records']}/{row['total_records']} records. "
                          "See per-site audit report for CAPA detail.")
    else:
        lines.append("None. All sites scored at or above the 80% escalation threshold.")
    lines.append("")
    lines.append("## Sites Requiring Monitoring/Retraining (80% <= score < 90%)")
    lines.append("")
    monitor = [r for r in scores if 80 <= r["quality_score_pct"] < 90]
    if monitor:
        for row in monitor:
            lines.append(f"- **{row['site_id']} ({row['site_name']})** -- {row['quality_score_pct']}%")
    else:
        lines.append("None.")
    lines.append("")

    with open(path, "w") as f:
        f.write("\n".join(lines))


def main():
    records = load_records()
    sites = load_sites()
    flags = run_validation(records)

    flag_fields = ["record_id", "site_id", "category", "detail"]
    write_csv(os.path.join(OUT_DIR, "flagged_records.csv"), flags, flag_fields)

    scores = compute_site_scores(records, flags, sites)
    score_fields = ["rank", "site_id", "site_name", "coordinator", "total_records",
                    "flagged_records", "quality_score_pct", "out_of_range",
                    "missing_required", "inconsistent_date", "duplicate_record"]
    write_csv(os.path.join(OUT_DIR, "site_quality_scores.csv"), scores, score_fields)

    # validation_summary.csv -- same content, kept as a distinct deliverable name
    write_csv(os.path.join(OUT_DIR, "validation_summary.csv"), scores, score_fields)

    flags_by_site = defaultdict(list)
    for f in flags:
        flags_by_site[f["site_id"]].append(f)

    for row in scores:
        report_path = os.path.join(REPORTS_DIR, f"{row['site_id']}_audit_report.md")
        write_site_audit_report(row, flags_by_site[row["site_id"]], report_path)

    total_records = len(records)
    unique_flagged = len({f["record_id"] for f in flags})
    write_compliance_report(scores, total_records, unique_flagged,
                             os.path.join(REPORTS_DIR, "compliance_report.md"))

    print(f"Total records validated: {total_records}")
    print(f"Total unique flagged records: {unique_flagged}")
    overall = round(100 * (1 - unique_flagged / total_records), 4) if total_records else 0
    print(f"Study-wide data quality score: {overall}%")
    print("")
    print("Per-site ranking:")
    for row in scores:
        print(f"  {row['rank']}. {row['site_id']} ({row['site_name']}): "
              f"{row['quality_score_pct']}% ({row['flagged_records']}/{row['total_records']} flagged)")


if __name__ == "__main__":
    main()
