"""
Make a chart: adverse-event reports per MONTH for a drug.
Run AFTER collect.py (reads signal_<drug>.csv). Usage: python visualise.py OZEMPIC
"""
import sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

drug = sys.argv[1].lower() if len(sys.argv) > 1 else "ozempic"
df = pd.read_csv(f"signal_{drug}.csv")
df["month"] = pd.to_datetime(df["month"])

fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df["month"], df["n_reports"], linewidth=2.5, color="#c0392b", marker="o", markersize=3)
ax.fill_between(df["month"], df["n_reports"], alpha=0.12, color="#c0392b")
ax.set_title(f"Monthly FDA adverse-event reports mentioning {drug.upper()}\n"
             "Source: openFDA / FAERS", fontsize=12)
ax.set_xlabel("Month")
ax.set_ylabel("Number of reports")
ax.grid(True, alpha=0.3, axis="y")
fig.autofmt_xdate(rotation=45)
fig.tight_layout()
fig.savefig(f"signal_{drug}.png", dpi=150)

print(f"Saved -> signal_{drug}.png (monthly data)")
print(f"Total data points: {len(df)} months")
print(f"Date range: {df['month'].min().strftime('%Y-%m')} to {df['month'].max().strftime('%Y-%m')}")
print(f"Total reports: {df['n_reports'].sum():,}")
