# Trial Data Quality: Multi-Site Comparative Monitoring Framework

A simulated multi-site clinical trial data quality monitoring framework. It
generates visit-level data for 9 simulated sites with deliberately **uneven**
data-quality issue rates, runs an automated validation engine against every
site independently, produces a per-site quality score and cross-site
ranking, generates real audit documentation and compliance reports per
site, and includes a substantive team training guide for site coordinators
grounded in the actual validation rules implemented.

All data is synthetic. No real patient data is used anywhere in this
project.

## Differentiation from the sibling `ClinicalData-QualityCompliance-Framework`

This project covers related but distinct ground from the sibling
`ClinicalData-QualityCompliance-Framework` project in this portfolio.
Read both READMEs if comparing them:

| | `ClinicalData-QualityCompliance-Framework` | `TrialDataQuality` (this project) |
|---|---|---|
| Core question | "Is this *pooled* database clean enough to lock?" | "*Which sites* are the data-quality problem, and what do we do about each one?" |
| Scale | 12,500+ records, 1,700 subjects, 18 sites, single pooled accuracy metric (99.7%) | ~1,400 records, 9 sites, scored and ranked **per site** |
| Issue distribution | Low, roughly uniform injection rate across the whole dataset | Deliberately **uneven** injection rate per site (2% - 22%) so some sites are clearly worse than others, mirroring real-world site variability |
| Primary deliverable | A single statistical-compliance / FDA-submission-style QC accuracy report | 9 per-site audit reports + 1 cross-site compliance rollup + a site-coordinator training guide |
| Framing | SAS-substitution QC engine for a database-lock milestone | Multi-site comparative monitoring program + team mentoring/training materials |

In short: the sibling project proves "can you build an accurate QC engine
at scale," while this project proves "can you run a multi-site monitoring
program that identifies which sites need help and can you train the people
at those sites" -- the data management and team-mentoring side of the same
job description line, not a duplicate of the SAS-substitute QC engine.

## What this project does

1. **`simulate_site_data.py`** -- simulates visit-level clinical trial data
   (vitals + labs) for 9 simulated sites (263 subjects, 1,433 visit
   records in the reference run below), with a deliberately uneven
   per-site issue injection rate (2% at the cleanest site up to 22% at the
   worst) across four categories: out-of-range values, missing required
   fields, inconsistent dates, and duplicate records. Ground truth is
   logged to `data/raw/injected_issues_log.csv`.

2. **`validate_site_data.py`** -- a real validation engine that runs four
   categories of automated checks against every record, independently
   per site:
   - **Completeness** -- required fields present and non-blank
   - **Range checks** -- vitals/labs within plausible physiological bounds
   - **Cross-field consistency** -- visit date on/after enrollment date,
     not in the future
   - **Duplicate detection** -- same subject/visit/date recorded more
     than once

   It computes a per-site quality score (`1 - flagged/total`), ranks all
   9 sites against each other, and writes:
   - `output/flagged_records.csv` -- every flagged record + reason
   - `output/site_quality_scores.csv` / `output/validation_summary.csv` --
     per-site score, rank, and per-category counts
   - `output/reports/<SITE_ID>_audit_report.md` -- one real audit report
     per site with findings and a recommended action tier
   - `output/reports/compliance_report.md` -- cross-site rollup, ranking,
     and escalation list

3. **`docs/team_training_guide.md`** -- a substantive data-quality training
   guide for site coordinators, built directly from the four validation
   categories actually implemented (not generic QA boilerplate), including
   why each check exists, plausible-range tables, and what to do when a
   site's report shows a finding.

4. **`tests/test_pipeline.py`** -- pytest suite verifying the multi-site
   structure, that all four validation categories produce findings, that
   per-site scores and ranks are internally consistent, that the
   deliberately worst-configured site (highest injected issue rate) is
   correctly identified as the worst-ranked site by the validation engine,
   and a standalone sanity check that a corrupted record is caught.

## Results (real, from the run used to write this README)

```
Total records validated: 1,433
Total unique flagged records: 233
Study-wide data quality score: 83.7404%

Per-site ranking (best to worst):
  1. S07 - Cascade Medical Research:            92.86% (12/168 flagged)
  2. S01 - Stony Brook Univ. Medical Center:     92.79% (15/208 flagged)
  3. S02 - Lakeshore Clinical Research:          90.34% (17/176 flagged)
  4. S04 - Riverside Family Health:              85.15% (30/202 flagged)
  5. S05 - Granite State Research Partners:      82.26% (22/124 flagged)
  6. S08 - Heartland Trial Network:              81.16% (26/138 flagged)
  7. S09 - Pine Ridge Clinical Site:             78.15% (26/119 flagged)
  8. S03 - Desert Valley Trials Center:          74.15% (38/147 flagged)
  9. S06 - Bayou Clinical Associates:            68.87% (47/151 flagged)
```

Injected ground truth (`data/raw/injected_issues_log.csv`): 106 issues
(27 out_of_range, 30 missing_required, 25 inconsistent_date,
24 duplicate_record) distributed unevenly across sites per their
configured `issue_rate` (0.02 - 0.22). Site S06 was configured with the
highest injection rate (0.22) and is, as expected, validated as the
lowest-scoring site (68.87%) -- this is enforced as a regression check in
`tests/test_pipeline.py::test_worst_configured_site_is_ranked_worst`.

**Test suite: 8/8 passed** (`pytest tests/ -v`).

Exact counts vary slightly run-to-run only if the random seed changes; the
fixed random seed (`RNG_SEED = 42`) in `simulate_site_data.py` makes this
specific run reproducible.

## Running it

```bash
pip install -r requirements.txt
python run_all.py          # simulate multi-site data, then run validation
pytest tests/ -v            # run the test suite
```

## Repository layout

```
simulate_site_data.py        # multi-site data simulation + uneven issue injection
validate_site_data.py        # per-site validation engine, scoring, ranking, report generation
run_all.py                   # end-to-end pipeline runner
tests/test_pipeline.py       # pytest suite
docs/team_training_guide.md  # site coordinator data-quality training guide
data/raw/                    # simulated input data + injected-issue ground truth (generated)
output/                      # validation outputs + per-site/cross-site reports (generated)
```

## Conventions

This repo follows the same lightweight, reproducible-pipeline structure as
the sibling `CharacterizationPipeline` and `ClinicalData-QualityCompliance-Framework`
projects in this portfolio: a simulate-then-analyze script pair, a
`run_all.py` orchestrator, a small pytest suite, and generated data/output
committed for reviewability.
