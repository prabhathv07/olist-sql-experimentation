# Two summary charts for the report:
#   1. Average cohort retention curve (months 1-6 after first order).
#   2. 90-day repeat rate by first-order payment type, with 95% Wilson CIs.

from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from statsmodels.stats.proportion import proportion_confint

HERE = Path(__file__).resolve().parent
RES = HERE / "results"

cohort = pd.read_csv(RES / "q5_cohort_matrix.csv")
payments = pd.read_csv(RES / "q6_repeat_by_payment.csv")

# drop blanks / "not_defined" — real Olist has a few of those
payments = payments[
    payments.first_payment_type.notna() & (payments.first_payment_type != "")
]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))

# ---- Panel 1: average cohort retention curve --------------------------------
# Only look at cohorts of 500+ so the tiny edge-month cohorts don't pull the
# average around.
offsets = [str(i) for i in range(1, 7)]
big_cohorts = cohort[cohort["cohort_size"] >= 500]
avg = big_cohorts[offsets].mean()

ax1.plot(range(1, 7), avg.values, "o-", color="#2b6cb0", lw=2)
ax1.set_title(
    "Repeat-purchase retention by months since first order\n"
    f"(avg across {len(big_cohorts)} cohorts with 500+ customers)"
)
ax1.set_xlabel("Months since first purchase")
ax1.set_ylabel("% of cohort active")
ax1.grid(alpha=0.3)
for x, y in zip(range(1, 7), avg.values):
    ax1.annotate(
        f"{y:.1f}%",
        (x, y),
        textcoords="offset points",
        xytext=(0, 7),
        ha="center",
        fontsize=8,
    )

# ---- Panel 2: 90-day repeat rate by first-order payment type ----------------
payments = payments.sort_values("customers", ascending=False)
rates, los, his = [], [], []
for _, row in payments.iterrows():
    p_hat = row.repeaters_90d / row.customers
    lo, hi = proportion_confint(row.repeaters_90d, row.customers, method="wilson")
    rates.append(p_hat * 100)
    los.append((p_hat - lo) * 100)
    his.append((hi - p_hat) * 100)

colors = [
    "#2f855a" if t == "credit_card"
    else "#c05621" if t == "boleto"
    else "#718096"
    for t in payments.first_payment_type
]
ax2.bar(payments.first_payment_type, rates, yerr=[los, his], capsize=5, color=colors)
ax2.set_title(
    "90-day repeat rate by first-order payment type\n"
    "(error bars = 95% Wilson CI)"
)
ax2.set_ylabel("Repeat rate (%)")
for i, (t, p, n) in enumerate(
    zip(payments.first_payment_type, rates, payments.customers)
):
    ax2.annotate(
        f"{p:.2f}%\nn={n:,}",
        (i, p),
        textcoords="offset points",
        xytext=(0, 12),
        ha="center",
        fontsize=8,
    )
ax2.set_ylim(0, max(rates) * 1.5)

plt.tight_layout()
out_path = RES / "summary_figure.png"
plt.savefig(out_path, dpi=130)
print(f"saved {out_path}")
