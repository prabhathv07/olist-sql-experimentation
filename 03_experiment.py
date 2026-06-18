# Experimentation step.
#
# Business question:
#   Do customers whose FIRST order is paid by credit card retain better
#   (place a 2nd order within 90 days) than customers whose first order
#   is paid by boleto?
#
# This is OBSERVATIONAL (not a randomised A/B test), and I try to be clear
# about that. The workflow follows what I'd do around a real experiment:
#   1. State hypotheses.
#   2. Power analysis: what could this sample size reliably detect (MDE)?
#                      how big would a prospective A/B test need to be?
#   3. Significance test: two-proportion z-test + chi-square cross-check,
#                         plus a confidence interval on the difference.

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import (
    confint_proportions_2indep,
    proportion_effectsize,
    proportions_ztest,
)

HERE = Path(__file__).resolve().parent
RES = HERE / "results"

q6 = pd.read_csv(RES / "q6_repeat_by_payment.csv")
cc = q6[q6.first_payment_type == "credit_card"].iloc[0]
bo = q6[q6.first_payment_type == "boleto"].iloc[0]

n_cc, x_cc = int(cc.customers), int(cc.repeaters_90d)
n_bo, x_bo = int(bo.customers), int(bo.repeaters_90d)
p_cc = x_cc / n_cc
p_bo = x_bo / n_bo

# tiny helper: print + buffer so the same lines end up on disk
log_lines = []
def out(line=""):
    print(line)
    log_lines.append(line)


out("=" * 70)
out("BUSINESS QUESTION")
out("=" * 70)
out("Do credit-card-first customers retain (90-day repeat) better than")
out("boleto-first customers? Payment-method-at-acquisition is a lever the")
out("growth team can nudge (e.g. promoting card checkout), so a real,")
out("reliable gap would be worth acting on.")
out("")
out("HYPOTHESES (two-sided, alpha = 0.05)")
out("  H0: repeat_rate(credit_card) = repeat_rate(boleto)")
out("  H1: repeat_rate(credit_card) != repeat_rate(boleto)")
out("")
out("OBSERVED")
out(f"  credit_card: {x_cc:>5}/{n_cc:<6} = {p_cc*100:5.2f}% repeat")
out(f"  boleto     : {x_bo:>5}/{n_bo:<6} = {p_bo*100:5.2f}% repeat")
out(f"  absolute difference: {(p_cc - p_bo) * 100:+.2f} pp")
out(f"  relative lift      : {(p_cc / p_bo - 1) * 100:+.1f}%")


# ---------- 1) power analysis -------------------------------------------------
out("\n" + "=" * 70)
out("POWER ANALYSIS  (statsmodels NormalIndPower)")
out("=" * 70)

analysis = NormalIndPower()
alpha = 0.05
power_target = 0.80

# (a) Minimum detectable effect for the sample we actually have.
# ratio = n_bo / n_cc means the smaller arm is respected.
ratio = n_bo / n_cc
es_detectable = analysis.solve_power(
    effect_size=None,
    nobs1=n_cc,
    alpha=alpha,
    power=power_target,
    ratio=ratio,
    alternative="two-sided",
)
# convert Cohen's h back to an approximate absolute pp gap at this base rate
p2_mde = np.sin(np.arcsin(np.sqrt(p_bo)) + es_detectable / 2) ** 2
mde_pp = (p2_mde - p_bo) * 100

out(f"With n_cc={n_cc:,} and n_bo={n_bo:,}, at alpha=0.05 / power=0.80:")
out(f"  smallest detectable effect (Cohen's h): {es_detectable:.4f}")
out(f"  ~ absolute gap detectable vs {p_bo*100:.2f}% base: ~{mde_pp:.2f} pp")
out("  -> compare our observed gap to this floor below.")

# (b) If we were designing a fresh balanced experiment to catch the observed
# effect, how many per arm would we need?
es_obs = proportion_effectsize(p_cc, p_bo)
n_needed = analysis.solve_power(
    effect_size=es_obs,
    nobs1=None,
    alpha=alpha,
    power=power_target,
    ratio=1.0,
    alternative="two-sided",
)
out("")
out("If we were to design a fresh, balanced experiment to detect the")
out(f"observed effect (h={es_obs:.4f}) at 80% power:")
out(f"  required sample per arm: {int(np.ceil(n_needed)):,}")
out(f"  total:                   {int(np.ceil(n_needed)) * 2:,}")

# (c) Post-hoc power of the test we actually ran.
power_actual = analysis.solve_power(
    effect_size=es_obs,
    nobs1=n_cc,
    alpha=alpha,
    ratio=ratio,
    alternative="two-sided",
)
out("")
out(f"Post-hoc power of the comparison we actually ran: {power_actual:.3f}")


# ---------- 2) significance test ----------------------------------------------
out("\n" + "=" * 70)
out("SIGNIFICANCE TEST")
out("=" * 70)

count = np.array([x_cc, x_bo])
nobs = np.array([n_cc, n_bo])
z, pval = proportions_ztest(count, nobs, alternative="two-sided")
out(f"Two-proportion z-test:  z = {z:.3f},  p = {pval:.3e}")

# 95% CI on the difference using Newcombe's method
lo, hi = confint_proportions_2indep(
    x_cc, n_cc, x_bo, n_bo, method="newcomb", compare="diff"
)
out(f"95% CI on absolute difference: [{lo*100:+.2f}, {hi*100:+.2f}] pp")
out(f"Relative lift point estimate: {(p_cc / p_bo - 1) * 100:+.1f}%")

# chi-square cross-check
table = np.array([[x_cc, n_cc - x_cc], [x_bo, n_bo - x_bo]])
chi2, p_chi, dof, _ = chi2_contingency(table, correction=False)
out(f"Chi-square cross-check: chi2 = {chi2:.3f}, p = {p_chi:.3e}")

verdict = "REJECT H0" if pval < alpha else "fail to reject H0"
out("")
out(f"VERDICT: {verdict} at alpha=0.05.")

(RES / "experiment_output.txt").write_text("\n".join(log_lines))
print(f"\nSaved -> {RES / 'experiment_output.txt'}")
