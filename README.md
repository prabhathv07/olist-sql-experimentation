# Olist SQL + Experimentation

An end-to-end analytics project on the real Olist dataset (Brazilian
e-commerce, 99,441 orders / 96,096 customers, Sep 2016 to Oct 2018). It does
the SQL piece (window functions and a cohort retention matrix in DuckDB), the
experimentation piece (power analysis and a two-proportion z-test in
statsmodels), and a 1-page PM-facing recommendation at the end.

I built this because I wanted a portfolio project that ended in a decision a
stakeholder could act on, not just a "here's a chart" notebook.

## TL;DR of what I found

The popular hypothesis going in was: *credit-card buyers retain better than
boleto buyers*. In this data, that's false. The 90-day repeat rates are
**2.07% (credit card) vs 2.10% (boleto)**, p = 0.76, 95% CI on the difference
[-0.27, +0.19] pp. And it's a well-powered null: the test could detect a gap
as small as 0.34pp.

The real story isn't payment method, it's that **only 3.1% of customers ever
order a second time**, so retention work should be aimed at the
first-to-second purchase, not at payment rails. The full pitch is in
[`RECOMMENDATION.md`](RECOMMENDATION.md).

I think reporting an honest null and pivoting the recommendation is more
useful than forcing a "we found a significant effect" finding.

## Data

Real Olist data, taken from the Kaggle "E-commerce dataset by Olist as an
SQLite database" (`olist.sqlite`). The four tables I use (`customers`,
`orders`, `order_items`, `order_payments`) are exported to `data_real/*.csv`
with Python's built-in `sqlite3` and read by DuckDB from there.

`01_generate_data.py` builds an Olist-style synthetic set in `data/`. I kept
it as a fallback so the pipeline still runs if you don't have the SQLite
file handy, but everything in this README is computed against `data_real/`.

## Files

| File | What it does |
|---|---|
| `02_analysis.sql` | 6 analytical queries (window functions) + cohort retention |
| `02_run_sql.py` | Loads `data_real/` into DuckDB, runs the SQL, writes `results/*.csv` |
| `03_experiment.py` | Hypotheses, power analysis, z-test / chi-square, writes `results/experiment_output.txt` |
| `04_figures.py` | `results/summary_figure.png` (retention curve + repeat rate by payment) |
| `RECOMMENDATION.md` | The 1-page "what I'd tell the PM and why" |
| `01_generate_data.py` | Fallback synthetic Olist-style generator |
| `results/` | Query outputs, cohort matrix, experiment log, figure |

## How to run it

```bash
pip install duckdb statsmodels scipy pandas matplotlib

# data_real/ is populated from olist.sqlite. To rebuild it from the SQLite dump:
python3 -c "import sqlite3, pandas as pd; con = sqlite3.connect('data/olist.sqlite'); \
[pd.read_sql(f'SELECT * FROM \"{t}\"', con).to_csv(f'data_real/{t}.csv', index=False) \
 for t in ['customers', 'orders', 'order_items', 'order_payments']]"

python3 02_run_sql.py
python3 03_experiment.py
python3 04_figures.py
```

If neither `data_real/` nor `data/olist.sqlite` is present, run
`python3 01_generate_data.py` first to populate `data/` with the synthetic
set. The same SQL works in both cases.

## SQL techniques used (`02_analysis.sql`)

- **Q1** monthly revenue with `SUM() OVER` running total + `LAG()` MoM growth
- **Q2** days between 1st -> 2nd -> 3rd order using `LAG()` over each customer's timeline
- **Q3** state revenue leaderboard with `RANK()` and share of total via `SUM() OVER ()`
- **Q4** 7-day moving average with a windowed frame (`ROWS BETWEEN 6 PRECEDING ...`)
- **Q5** cohort retention matrix: monthly acquisition cohort x months since first order
- **Q6** 90-day repeat rate by first-order payment type (this feeds the experiment)

The "order spine" view uses `ROW_NUMBER`, `MIN` and `FIRST_VALUE` window
functions to attach each person's order sequence, cohort month, and
first-order payment type to every order row. Split payments (real Olist
allows several payment rows per order) are collapsed to one row per order
with `arg_min(payment_type, payment_sequential)`.

## Experimentation (`03_experiment.py`)

1. **Question and hypotheses** (two-sided, alpha = 0.05): does first-order
   payment type change the 90-day repeat rate?
2. **Power analysis** with `NormalIndPower`: the minimum detectable effect
   for the sample we have (0.34pp), and the required N for a prospective
   balanced A/B test of the observed effect.
3. **Significance test**: two-proportion z-test, Newcombe CI on the
   absolute difference, chi-square as a cross-check.

Result: fail to reject H0, with a tight CI -> a confident null rather than
an underpowered one.

## Headline numbers (real data)

- 99,441 orders / 96,096 customers, of whom only **2,997 (3.1%) repeat**
- Overall 90-day repeat rate: **2.09%**; month-1 cohort retention ~0.5%
- Median gap to a 2nd order: ~28 days (mean ~81, long right tail)
- Payment-type effect on retention: none (p = 0.76)
