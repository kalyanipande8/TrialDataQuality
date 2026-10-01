"""
Pytest suite for the multi-site trial data quality pipeline.

Runs simulate -> validate end to end (using the fixed RNG_SEED, so the
run is reproducible) and checks:
  - multi-site structure is present (9 sites, expected record volume)
  - all four validation categories produce output
  - per-site scoring and ranking is internally consistent
  - a deliberately corrupted record (sanity check) is caught
  - the site whose issue_rate was configured highest ends up ranked worst
    (the core "does validation correctly identify the worst-quality site"
    check requested for this project)
"""

import csv
import os
import subprocess
import sys

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
OUT_DIR = os.path.join(BASE_DIR, "output")


@pytest.fixture(scope="module", autouse=True)
def run_pipeline():
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "simulate_site_data.py")], check=True)
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "validate_site_data.py")], check=True)
    yield


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_multi_site_structure_present():
    sites = read_csv(os.path.join(DATA_DIR, "site_roster.csv"))
    assert len(sites) == 9
    records = read_csv(os.path.join(DATA_DIR, "site_data.csv"))
    site_ids_in_data = {r["site_id"] for r in records}
    site_ids_in_roster = {s["site_id"] for s in sites}
    assert site_ids_in_data == site_ids_in_roster
    assert len(records) > 1000


def test_injected_issues_log_has_all_categories():
    issues = read_csv(os.path.join(DATA_DIR, "injected_issues_log.csv"))
    categories = {i["category"] for i in issues}
    assert categories == {"out_of_range", "missing_required", "inconsistent_date", "duplicate_record"}
    assert len(issues) > 0


def test_flagged_records_cover_all_categories():
    flags = read_csv(os.path.join(OUT_DIR, "flagged_records.csv"))
    categories = {f["category"] for f in flags}
    assert categories == {"out_of_range", "missing_required", "inconsistent_date", "duplicate_record"}


def test_site_quality_scores_rank_consistently():
    scores = read_csv(os.path.join(OUT_DIR, "site_quality_scores.csv"))
    assert len(scores) == 9
    ranks = sorted(int(r["rank"]) for r in scores)
    assert ranks == list(range(1, 10))
    # Ranking must be sorted descending by quality score
    pct_in_rank_order = [float(r["quality_score_pct"]) for r in sorted(scores, key=lambda r: int(r["rank"]))]
    assert pct_in_rank_order == sorted(pct_in_rank_order, reverse=True)


def test_worst_configured_site_is_ranked_worst():
    """Sanity check: S06 is configured with the highest injected issue_rate
    (0.22) in simulate_site_data.py. Validation must correctly identify it
    as the lowest (or tied-lowest) scoring site."""
    sites = read_csv(os.path.join(DATA_DIR, "site_roster.csv"))
    worst_configured = max(sites, key=lambda s: float(s["issue_rate"]))
    scores = read_csv(os.path.join(OUT_DIR, "site_quality_scores.csv"))
    worst_scored = min(scores, key=lambda r: float(r["quality_score_pct"]))
    assert worst_configured["site_id"] == "S06"
    assert worst_scored["site_id"] == worst_configured["site_id"], (
        f"Expected worst-quality site {worst_configured['site_id']} to rank last, "
        f"but {worst_scored['site_id']} scored lowest instead."
    )


def test_per_site_audit_reports_generated():
    sites = read_csv(os.path.join(DATA_DIR, "site_roster.csv"))
    for site in sites:
        path = os.path.join(OUT_DIR, "reports", f"{site['site_id']}_audit_report.md")
        assert os.path.exists(path), f"missing audit report for {site['site_id']}"
        with open(path) as f:
            content = f.read()
        assert "Data quality score" in content


def test_compliance_report_generated():
    path = os.path.join(OUT_DIR, "reports", "compliance_report.md")
    assert os.path.exists(path)
    with open(path) as f:
        content = f.read()
    assert "Study-wide data quality score" in content
    assert "Site Ranking" in content


def test_deliberately_corrupted_record_is_caught():
    """Standalone sanity check independent of the simulation: feed the
    validation engine a record with an obviously corrupted value and
    confirm it is flagged as out_of_range."""
    sys.path.insert(0, BASE_DIR)
    import validate_site_data as vsd

    bad_record = {
        "record_id": "TEST-BAD-001",
        "site_id": "S99",
        "subject_id": "SUBJTEST",
        "visit_name": "Baseline",
        "visit_date": "2024-06-01",
        "enrollment_date": "2024-05-01",
        "age": "45",
        "weight_kg": "75.0",
        "height_cm": "170.0",
        "systolic_bp": "999",  # deliberately impossible
        "diastolic_bp": "80",
        "heart_rate": "70",
        "temp_c": "36.8",
        "alt_u_l": "20",
        "creatinine_mg_dl": "0.9",
        "adverse_event": "None",
    }
    flags = vsd.run_validation([bad_record])
    categories = {f["category"] for f in flags}
    assert "out_of_range" in categories
