# Site Coordinator Training Guide: Data Quality Standards

**Audience:** site coordinators and study staff entering or reviewing subject
visit data across all participating sites.
**Purpose:** explain, in plain language, exactly what the automated
validation engine (`validate_site_data.py`) checks on every record, why
each check exists, and what to do when your site's audit report shows a
finding in that category. This guide is grounded directly in the four
validation categories actually implemented in the pipeline -- nothing here
is aspirational or generic.

This guide accompanies the per-site audit reports generated to
`output/reports/<SITE_ID>_audit_report.md` and the study-wide
`output/reports/compliance_report.md`. Read your site's report alongside
this guide.

---

## 1. Why multi-site comparison matters

Each site in this study enters data independently, but every record flows
into the same validation engine and the same scoring formula:

```
site quality score = 1 - (unique flagged records at your site / total records at your site)
```

Because every site is scored with the identical formula and the identical
rule set, the resulting ranking is a fair, apples-to-apples comparison --
not a judgment based on volume (a site with fewer subjects is not
penalized or favored just for being smaller). Use your rank and score to
understand how your site compares, not just whether your site is "good or
bad" in isolation.

## 2. The four things that get checked on every record

### 2.1 Completeness

**What it checks:** whether these required fields are present and non-blank
on every visit record: `age`, `visit_date`, `enrollment_date`, `weight_kg`,
`adverse_event`.

**Why it matters:** a blank required field cannot be imputed reliably after
the fact, and in a real trial it blocks statistical analysis and can trigger
a formal query to the site months after the visit, when the coordinator may
no longer remember the visit clearly. Catching it at entry time is far
cheaper than catching it at database lock.

**What to do if your report flags this:** check the source
document/worksheet for that visit. If the value was collected but not
transcribed, correct it immediately. If the value was genuinely not
collected, document why (e.g., subject declined, procedure not applicable)
rather than leaving the field silently blank.

### 2.2 Range checks

**What it checks:** that vitals and lab values fall within plausible
physiological bounds, for example:

| Field | Plausible range |
|---|---|
| Age | 18 - 90 years |
| Weight | 30 - 250 kg |
| Systolic BP | 70 - 220 mmHg |
| Diastolic BP | 40 - 130 mmHg |
| Heart rate | 30 - 200 bpm |
| Temperature | 34.0 - 41.5 C |
| ALT (liver enzyme) | 0 - 200 U/L |
| Creatinine | 0.1 - 10.0 mg/dL |

**Why it matters:** a value outside these bounds is almost always a
transcription or unit error (e.g., entering weight in pounds instead of
kilograms, or a decimal-point slip turning 98.6 F logic into 986). Left
uncorrected, these are exactly the kind of values that distort a trial's
safety summary statistics.

**What to do if your report flags this:** re-check the source document
first. Most range flags are a single-digit or unit transcription error and
can be corrected in minutes. If the value is confirmed correct as entered
(a genuinely extreme but real measurement), document the confirmation --
do not just leave it flagged with no resolution note.

### 2.3 Cross-field (date) consistency

**What it checks:** that every visit's `visit_date` is on or after that
subject's `enrollment_date`, and that no visit date is in the future
relative to the current date.

**Why it matters:** a visit recorded before enrollment, or a date years in
the future, usually indicates a data-entry date-field slip (day/month
transposition is the most common cause) rather than a real scheduling
event. These errors silently break visit-window and time-to-event
calculations downstream.

**What to do if your report flags this:** verify the actual calendar date
of the visit against the source document and correct the entry. If your
site uses a day/month date format different from the EDC system's expected
format, flag this to the data management team -- it is usually a systemic,
fixable issue rather than a one-off typo, and it is often concentrated at
one or two sites.

### 2.4 Duplicate detection

**What it checks:** whether more than one record exists for the same
subject, same visit name, and same visit date.

**Why it matters:** duplicate records double-count a subject's data in
summary statistics and can indicate either a double data-entry error or,
less commonly, a genuine double-visit that needs to be reconciled with the
protocol-defined visit schedule.

**What to do if your report flags this:** determine which of the duplicate
records is correct (compare against the source document) and submit a
deletion/correction request for the other through your site's standard data
correction process. Do not delete records directly in the EDC without a
documented correction request -- this preserves the audit trail.

## 3. How your site's score and action tier are determined

| Quality score | Tier | Action |
|---|---|---|
| >= 97% | Excellent | No action required; routine monitoring continues. |
| 90% - 96.9% | Good | Written query sent for flagged records; SOP reminder in next site newsletter. |
| 80% - 89.9% | Needs improvement | Remote retraining call scheduled with the coordinator; re-audit within 30 days. |
| < 80% | Escalation | In-person/video monitoring visit, formal CAPA request, and 100% source-data-verification hold until re-audit shows sustained improvement. |

These same thresholds are applied identically to every site in
`validate_site_data.py` -- they are not adjusted site-by-site.

## 4. Practical habits that prevent most findings

1. **Enter data the same day as the visit**, while the source document and
   your memory of the visit are both fresh. Most completeness and
   range-check findings come from batch entry done days or weeks later.
2. **Double-check unit fields** (kg vs lb, C vs F) every time you enter a
   new vital sign, especially after switching between source documents
   that use different units.
3. **Enter dates in the format the EDC expects**, and re-read the date back
   once entered rather than trusting the field as typed.
4. **Never re-enter a visit "just to be safe"** if you are unsure whether it
   was already entered -- check first, since this is the most common cause
   of duplicate-record findings.
5. **Read your site's audit report when it arrives.** A pattern of repeated
   findings in the same category is the single best early signal that a
   specific training refresher (not a one-off correction) is needed.

## 5. Questions

Direct questions about a specific finding in your site's audit report to
the data management team. Direct questions about this guide or about the
validation rules themselves to the study's data quality lead.
