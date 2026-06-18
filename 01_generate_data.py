# Fallback synthetic data generator (only used if the real Olist CSVs are missing).
# I built this while waiting for the Kaggle download to go through so I could keep
# working on the SQL queries. It mimics Olist's schema and the part of its behaviour
# that matters for this project: per-order customer_id with a stable
# customer_unique_id, a low repeat-purchase rate, growing monthly cohorts, and a
# credit-card-dominant payment mix. There's also a small baked-in repeat-rate gap
# between payment types so the experimentation script has something to detect when
# you run it on the synthetic set.
#
# Tables produced (same column names as the real Olist dump):
#   customers.csv       customer_id, customer_unique_id, customer_state
#   orders.csv          order_id, customer_id, order_status, order_purchase_timestamp
#   order_items.csv     order_id, order_item_id, product_id, price, freight_value
#   order_payments.csv  order_id, payment_type, payment_installments, payment_value

import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)

HERE = Path(__file__).resolve().parent
OUT = HERE / "data"
OUT.mkdir(exist_ok=True)

N_CUSTOMERS = 30_000
START = datetime(2023, 1, 1)
MONTHS = 24   # Jan 2023 through Dec 2024

# Brazilian states with roughly Olist's weighting (SP is by far the biggest)
STATES = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "GO", "ES", "PE", "CE"]
state_w = np.array([42, 13, 12, 6, 5, 4, 4, 3, 3, 2, 3, 3], dtype=float)
state_w = state_w / state_w.sum()

# Payment mix, also close to what the real data shows
PAY_TYPES = ["credit_card", "boleto", "voucher", "debit_card"]
pay_w = np.array([0.74, 0.19, 0.05, 0.02])

# Baked-in effect: 90-day repeat probability depends on the FIRST order's payment
# type. This is the lever the experiment script will try to detect.
REPEAT_P = {
    "credit_card": 0.066,
    "boleto":      0.045,
    "voucher":     0.050,
    "debit_card":  0.052,
}


def random_ts(month_idx):
    """Pick a random timestamp inside a given month offset from START."""
    base = START + timedelta(days=30.4 * month_idx)
    day = int(rng.integers(0, 28))
    hour = int(rng.integers(0, 24))
    minute = int(rng.integers(0, 60))
    return base + timedelta(days=day, hours=hour, minutes=minute)


def make_id(prefix, i):
    return f"{prefix}_{i:08x}"


# Cohort sizes grow over time so it looks like a real ramping business
growth = np.linspace(1.0, 2.2, MONTHS)
growth = growth / growth.sum()
cohort_counts = rng.multinomial(N_CUSTOMERS, growth)

customers, orders, items, payments = [], [], [], []
order_seq = 0

for month_idx, n_in_cohort in enumerate(cohort_counts):
    for _ in range(int(n_in_cohort)):
        # the person (stable across their orders)
        cu_id = make_id("cust", len(customers))
        state = rng.choice(STATES, p=state_w)
        first_pay = rng.choice(PAY_TYPES, p=pay_w)

        # build this person's order timeline (1, 2, or rarely 3 orders)
        ts_list = [random_ts(month_idx)]
        if rng.random() < REPEAT_P[first_pay]:
            gap_days = int(rng.integers(15, 95))
            ts_list.append(ts_list[0] + timedelta(days=gap_days))
            if rng.random() < 0.25:
                gap2 = int(rng.integers(20, 160))
                ts_list.append(ts_list[1] + timedelta(days=gap2))

        for order_idx, ts in enumerate(ts_list):
            order_seq += 1
            order_id = make_id("order", order_seq)
            # Olist quirk: each order gets a fresh customer_id, the person is
            # identified by customer_unique_id
            customer_id = make_id("cid", order_seq)
            customers.append((customer_id, cu_id, state))

            if rng.random() < 0.97:
                status = "delivered"
            else:
                status = rng.choice(["shipped", "canceled", "invoiced"])
            orders.append((order_id, customer_id, status, ts))

            # 1-3 items per order, log-normal prices (median around R$55)
            n_items = 1 + int(rng.binomial(2, 0.25))
            order_total = 0.0
            for i in range(n_items):
                price = round(float(np.exp(rng.normal(4.0, 0.7))), 2)
                freight = round(price * float(rng.uniform(0.08, 0.22)), 2)
                product_id = make_id("prod", int(rng.integers(0, 4000)))
                items.append((order_id, i + 1, product_id, price, freight))
                order_total += price + freight

            # first order uses first_pay; later orders mostly reuse it
            if order_idx == 0 or rng.random() < 0.8:
                pay_type = first_pay
            else:
                pay_type = rng.choice(PAY_TYPES, p=pay_w)

            installments = 1
            if pay_type == "credit_card":
                installments = int(rng.choice(
                    [1, 2, 3, 4, 6, 10],
                    p=[.35, .2, .15, .12, .1, .08]
                ))
            # payment_sequential = 1 because the synthetic generator doesn't
            # produce split payments (real Olist sometimes does).
            payments.append(
                (order_id, 1, pay_type, installments, round(order_total, 2))
            )


pd.DataFrame(
    customers,
    columns=["customer_id", "customer_unique_id", "customer_state"],
).to_csv(OUT / "customers.csv", index=False)

pd.DataFrame(
    orders,
    columns=["order_id", "customer_id", "order_status", "order_purchase_timestamp"],
).to_csv(OUT / "orders.csv", index=False)

pd.DataFrame(
    items,
    columns=["order_id", "order_item_id", "product_id", "price", "freight_value"],
).to_csv(OUT / "order_items.csv", index=False)

pd.DataFrame(
    payments,
    columns=[
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    ],
).to_csv(OUT / "order_payments.csv", index=False)

print(f"customers (order-level rows): {len(customers):,}")
print(f"unique people:               {N_CUSTOMERS:,}")
print(f"orders:                      {len(orders):,}")
print(f"order_items:                 {len(items):,}")
print(f"payments:                    {len(payments):,}")
print(f"repeat orders:               {len(orders) - N_CUSTOMERS:,}")
print(f"saved to {OUT}")
