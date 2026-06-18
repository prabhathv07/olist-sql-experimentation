# Recommendation: don't chase payment method as a retention lever, fix the first-to-second-order gap instead

**To:** Product Manager, Growth
**From:** Data Science
**Date:** 2026-06-18
**Data:** Real Olist dataset (99,441 orders, 96,096 customers, Sep 2016 to Oct 2018)

**One line.** I tested the common hypothesis that credit-card buyers retain
better than boleto buyers. They don't. The difference is **0.03pp
(p = 0.76)**, and the test was strong enough to catch a gap as small as
0.34pp. Payment method is not a retention lever. The real problem is that
**97% of customers never place a second order**, and that's where I'd point
the effort.

---

## What I found

**1. Olist is effectively a one-purchase marketplace.** Of 96,096
customers, only **2,997 (3.1%)** ever order again. The cohort retention
curve is brutal: across cohorts of 500+ customers, only ~0.5% are active
one month after their first order, decaying to ~0.25% by month six. This
single fact is bigger than any segment effect we can find.

**2. The first-to-second order gap is wide, and that's where the
opportunity sits.** Among the few who do return, the median time to a
second order is ~28 days, but the mean is ~81 days, so there's a long
right tail. People decide quickly or drift away. The 2-8 week window after
the first delivery is the natural place for a retention intervention.

**3. First-order payment type does NOT predict whether customers come
back.**

| First payment | Customers | 90-day repeat rate |
|---|---:|---:|
| Voucher | 1,448 | 2.83% |
| Boleto | 19,101 | 2.10% |
| Credit card | 73,533 | 2.07% |
| Debit card | 1,477 | 1.90% |

Credit card vs boleto, the comparison the growth team usually cares about,
is **2.07% vs 2.10%**. No meaningful difference.

## Why I trust the null

A null result is only useful if the test could have found an effect. It
could have:

- **Two-proportion z-test:** z = -0.30, **p = 0.76**. Chi-square agrees.
- **95% CI on the difference: [-0.27, +0.19] pp.** The true gap is pinned
  tightly around zero — not "unknown", but "confidently tiny."
- **Power:** with 73,533 vs 19,101 customers, the test could reliably
  detect a gap as small as **0.34pp** at 80% power. Our observed 0.03pp is
  far below that floor.

So this is not an "underpowered, we didn't see anything" result. It's
strong evidence that the effect, if there is one, is too small to be worth
acting on commercially.

Voucher looks highest at 2.83%, but it sits on 1,448 customers with a wide
CI that overlaps the others. I wouldn't build a strategy on it.

## What I'd tell the PM to do

1. **Don't invest in pushing card checkout to lift retention.** The data
   says it won't move the needle, and we'd risk losing boleto-reliant
   buyers (boleto is ~21% of first orders) for no retention gain. If
   there's a cost or fraud reason to favour cards, fine, but that's a
   different business case.
2. **Reframe the goal around the real bottleneck: first to second
   purchase.** With a ~2% repeat rate, even a 1pp absolute lift would be
   ~50% relative improvement in repeat customers. The lever is lifecycle
   and CRM, not payment rails: post-delivery follow-up, category-based
   reorder prompts, and a first-repeat incentive timed to the 2-8 week
   window where repeats actually happen.
3. **Run a real randomised experiment on that lever.** Randomly assign
   first-time buyers to a post-purchase re-engagement flow vs control.
   Primary metric: 90-day repeat rate. Guardrail: margin (don't buy back
   unprofitable orders with discounts). To detect a 1pp lift on a 2% base
   at 80% power / 95% confidence needs about **6,400 customers per arm**,
   well within a month of Olist's volume.
4. **Set the decision rule in advance:** ship only if the treatment lifts
   90-day repeat by >= 1pp with p < 0.05 and margin holds. Pre-committing
   stops us from peeking and over-claiming.

**Bottom line:** the "card users are more loyal" story is not true in
this data. The useful finding is that retention is uniformly low across
payment methods, so the money should go to a first-to-second-order
re-engagement test, not to payment-method engineering.

---

*Methods: DuckDB for the cohort and window-function SQL over the real Olist
SQLite database; statsmodels for the power analysis and two-proportion
z-test. See `results/summary_figure.png`, `results/experiment_output.txt`,
and the rest of `results/`.*
