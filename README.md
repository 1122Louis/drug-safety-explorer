# Drug Safety Explorer

Detecting post-market drug-safety signals from FDA adverse-event reports.

A tool for exploring post-market drug-safety signals in public FDA data. It collects
real-world adverse-event reports from the official
[openFDA Drug Adverse Event API](https://open.fda.gov/apis/drug/event/) (the FDA's
FAERS system) and turns them into an interactive tool anyone can use to explore
drug-safety signals — no coding required.

## What's in here

**`drug_safety_explorer.html`** — the app. A single self-contained web
page (no install, no server). Just open it in a browser and search. It fetches live
data from the FDA in your browser and answers real research questions:

- **How much?** Total reports, timeline of reports per month, busiest period.
- **Compared to how much it's prescribed?** Reports per 100,000 Medicare Part D
  prescriptions — a fairer comparison than raw counts.
- **Is it a disproportionate signal?** The Proportional Reporting Ratio (PRR), the
  method regulators use to flag side effects reported unusually often for a drug.
- **Who is affected, and how serious?** Age, sex, and outcomes (serious,
  hospitalizations, deaths).
- **Which drugs cause a given symptom?** A reverse search from a side effect to the
  drugs most associated with it.
- **What's emerging over time?** Side effects whose *share* of reports is rising.
- **What else do these patients take?** Commonly co-reported drugs.
- **Who reports it, from where, and how is it used?** Reporter type, country, and
  off-label use.

You can compare two drugs side by side, download any table as CSV, share a link to a
specific view, and save the whole thing as a PDF.

**Python data pipeline** — the scripts that collect and chart the data:

- `collect.py` — collects adverse-event reports for a drug and saves them as CSV.
  Run: `python collect.py OZEMPIC`
- `visualise.py` — charts reports over time.

## How to use the tool

Open `drug_safety_explorer.html` in a modern browser (an internet connection is
needed, since it pulls live data from the FDA). Type a drug name — brand or generic,
any capitalization — or switch to "Search by side effect" to go the other way.

## Data sources

- **openFDA Drug Adverse Event API** — adverse-event reports (FAERS).
- **CMS Medicare Part D Spending by Drug** — prescription volumes, used as the
  denominator for the rate feature (baked in for a set of drugs).

## Important caveats

These are **reports, not proof**. A report does not mean a drug caused an event, and
report counts are shaped by how much a drug is used, media attention, and lawsuits.
There is no true denominator for most drugs, so counts can't give a real risk rate.
A high signal is a reason to investigate — never a conclusion. Every part of the tool
states its own limitations.
