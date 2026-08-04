"""
Detecting post-market drug safety signals from FDA adverse-event reports.

Data source: openFDA Drug Adverse Event API  (https://api.fda.gov/drug/event.json)
The API exposes the FDA Adverse Event Reporting System (FAERS): voluntary reports of
suspected adverse reactions to marketed drugs. It is the backbone of pharmacovigilance
(post-market drug safety surveillance).

WHY THIS METHOD (calling a public API) IS THE RIGHT ONE
    - openFDA is the *official* programmatic interface to FAERS — sanctioned, documented,
      no Terms-of-Service violation, no scraping of a site that forbids it.
    - It returns structured JSON, so there is no fragile HTML parsing and no anti-bot risk.
    - The data is already de-identified at source (no names/addresses), which is the only
      ethically defensible way to work with individual health reports at scale.

PIPELINE STAGES
    1. signal_timeseries()   -> monthly report counts via the API's `count` endpoint
    2. fetch_reports()       -> paginated pull of individual reports (the raw collection)
    3. tidy_report()         -> map FDA codes to human labels; keep only what we need
    4. build_dataset()       -> assemble one tidy row per report -> CSV
    5. main()                -> run everything, save outputs, print a short summary

A NOTE ON PRIVACY
    Even though FAERS removes direct identifiers, each report still carries
    age + sex + country + date + reaction — *quasi-identifiers*. We therefore (a) collect
    only the fields the research question needs, and (b) never attempt re-identification.
"""

import os
import sys
import time
import datetime as dt

import requests
import pandas as pd

BASE = "https://api.fda.gov/drug/event.json"
HEADERS = {"User-Agent": "PracticalDataScience-research/1.0 (educational use)"}
REQUEST_DELAY = 0.3          # polite pause between requests (openFDA allows 240/min, 1000/day no key)
# CHALLENGE FOUND: without an API key openFDA rejects limit>=1000 with API_KEY_MISSING.
# Solution: page in 500s (works key-free), and *optionally* use a free key for bigger pulls.
PAGE_SIZE = 500
API_KEY = os.environ.get("OPENFDA_API_KEY")   # optional: export OPENFDA_API_KEY=... to raise limits

# --- FDA code -> human label lookups (documented in the openFDA data dictionary) ---
SEX = {"0": "Unknown", "1": "Male", "2": "Female"}
SERIOUS = {"1": "Serious", "2": "Non-serious"}
OUTCOME = {"1": "Recovered", "2": "Recovering", "3": "Not recovered",
           "4": "Recovered with sequelae", "5": "Fatal", "6": "Unknown"}
AGE_UNIT = {"800": "Decade", "801": "Year", "802": "Month",
            "803": "Week", "804": "Day", "805": "Hour"}


def _get(params: dict) -> dict:
    """Single GET with basic error surfacing. openFDA returns 404 when 0 results match."""
    if API_KEY:
        params = {**params, "api_key": API_KEY}
    time.sleep(REQUEST_DELAY)
    r = requests.get(BASE, params=params, headers=HEADERS, timeout=30)
    if r.status_code == 404:
        return {"results": [], "meta": {"results": {"total": 0}}}
    r.raise_for_status()
    return r.json()


def signal_timeseries(drug: str) -> pd.DataFrame:
    """Stage 1: monthly report counts for `drug` — the 'is there a signal?' view.

    Uses the API's server-side `count` aggregation (one request, no raw data downloaded)."""
    j = _get({"search": f'patient.drug.medicinalproduct:"{drug}"', "count": "receivedate"})
    rows = [{"date": pd.to_datetime(d["time"], format="%Y%m%d"), "n_reports": d["count"]}
            for d in j["results"]]
    ts = pd.DataFrame(rows)
    if ts.empty:
        return ts
    monthly = (ts.set_index("date").resample("ME")["n_reports"].sum()
               .rename("n_reports").reset_index())
    monthly["month"] = monthly["date"].dt.strftime("%Y-%m")
    print(f"[1] Signal view: {monthly['n_reports'].sum():,} total reports "
          f"over {len(monthly)} months ({monthly['month'].min()} to {monthly['month'].max()})")
    return monthly[["month", "n_reports"]]


def fetch_reports(drug: str, max_reports: int = 2000) -> list[dict]:
    """Stage 2: paginate through individual reports (the raw data collection step).

    openFDA caps `limit` at 1000 and `skip` at 25000; for a research sample we page
    with skip until we have `max_reports`."""
    out, skip = [], 0
    total = _get({"search": f'patient.drug.medicinalproduct:"{drug}"', "limit": 1}) \
        ["meta"]["results"]["total"]
    target = min(max_reports, total)
    print(f"[2] {total:,} reports exist for '{drug}'. Collecting a sample of {target:,}...")
    while len(out) < target and skip < 25000:
        j = _get({"search": f'patient.drug.medicinalproduct:"{drug}"',
                  "limit": min(PAGE_SIZE, target - len(out)), "skip": skip})
        batch = j["results"]
        if not batch:
            break
        out.extend(batch)
        skip += len(batch)
        print(f"      fetched {len(out):,}/{target:,}")
    return out


def tidy_report(ev: dict, target_drug: str) -> dict:
    """Stage 3: reduce one raw report to the fields the research question needs,
    translating FDA numeric codes into readable labels."""
    p = ev.get("patient", {})
    reactions = [rx.get("reactionmeddrapt") for rx in p.get("reaction", []) if rx.get("reactionmeddrapt")]
    outcomes = [OUTCOME.get(str(rx.get("reactionoutcome")), None)
                for rx in p.get("reaction", [])]
    age = p.get("patientonsetage")
    age_unit = AGE_UNIT.get(str(p.get("patientonsetageunit")), None)
    return {
        "report_id":   ev.get("safetyreportid"),
        "received":    _fmt_date(ev.get("receivedate")),
        "country":     ev.get("occurcountry"),
        # quasi-identifiers — collected because age/sex are core to a safety signal,
        # but deliberately nothing more granular than this:
        "age":         float(age) if age else None,
        "age_unit":    age_unit,
        "sex":         SEX.get(str(p.get("patientsex")), "Unknown"),
        "serious":     SERIOUS.get(str(ev.get("serious")), None),
        "hospitalised": bool(ev.get("seriousnesshospitalization")),
        "fatal":       "Fatal" in outcomes,
        "n_drugs_in_report": len(p.get("drug", [])),
        "top_reaction": reactions[0] if reactions else None,
        "all_reactions": "; ".join(reactions[:8]),
    }


def _fmt_date(yyyymmdd):
    if not yyyymmdd:
        return None
    try:
        return dt.datetime.strptime(yyyymmdd, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def build_dataset(drug: str, max_reports: int = 2000) -> pd.DataFrame:
    """Stages 2-4: collect raw reports and assemble the tidy per-report DataFrame."""
    raw = fetch_reports(drug, max_reports)
    df = pd.DataFrame(tidy_report(ev, drug) for ev in raw)
    print(f"[3] Tidied {len(df):,} reports into {df.shape[1]} columns")
    return df


def main():
    drug = sys.argv[1].upper() if len(sys.argv) > 1 else "OZEMPIC"
    print(f"=== openFDA adverse-event collection for: {drug} ===\n")

    monthly = signal_timeseries(drug)
    monthly.to_csv(f"signal_{drug.lower()}.csv", index=False)

    df = build_dataset(drug, max_reports=2000)
    df.to_csv(f"reports_{drug.lower()}.csv", index=False)
    print(f"\n[4] Saved -> signal_{drug.lower()}.csv  and  reports_{drug.lower()}.csv")

    # quick summary / sanity check
    print("\n--- Sample summary ---")
    print(f"Reports collected : {len(df):,}")
    print(f"Serious reports   : {(df['serious'] == 'Serious').mean()*100:.0f}%")
    print(f"Reported fatal    : {df['fatal'].mean()*100:.0f}%")
    print(f"Sex split         : {df['sex'].value_counts(normalize=True).mul(100).round(0).to_dict()}")
    print("Top 5 reported reactions:")
    for rx, n in df["top_reaction"].value_counts().head(5).items():
        print(f"   {n:4d}  {rx}")


if __name__ == "__main__":
    main()
