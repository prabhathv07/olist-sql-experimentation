-- ============================================================================
-- 02_analysis.sql
--
-- DuckDB analytical queries against the Olist e-commerce dataset.
-- Run this via 02_run_sql.py, which loads the CSVs into views first.
--
-- The focus here is window functions and a monthly cohort retention analysis.
-- Each query is preceded by an export marker (see 02_run_sql.py) so the runner
-- knows where one query ends and the next begins, and what filename to save
-- the rows under.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- Base view: one row per ORDER, enriched with the person (customer_unique_id),
-- that person's order sequence number, their cohort month, and the payment type
-- they used on their FIRST order. Most of the other queries reach into this.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW order_spine AS
WITH pay AS (
    -- Real Olist allows split payments (multiple rows per order). Collapse to
    -- one row per order: total amount paid, plus the "primary" payment type
    -- (the row where payment_sequential = 1).
    SELECT
        order_id,
        SUM(payment_value)                          AS payment_value,
        arg_min(payment_type, payment_sequential)   AS payment_type
    FROM order_payments
    GROUP BY order_id
),
joined AS (
    SELECT
        o.order_id,
        c.customer_unique_id              AS person,
        c.customer_state                  AS state,
        o.order_status,
        CAST(o.order_purchase_timestamp AS TIMESTAMP) AS ts,
        p.payment_type,
        p.payment_value
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    LEFT JOIN pay  p ON o.order_id = p.order_id
    WHERE o.order_status <> 'canceled'
)
SELECT
    *,
    date_trunc('month', ts)                                    AS order_month,
    ROW_NUMBER() OVER (PARTITION BY person ORDER BY ts)        AS order_seq,
    MIN(ts)      OVER (PARTITION BY person)                    AS first_ts,
    date_trunc('month', MIN(ts) OVER (PARTITION BY person))    AS cohort_month,
    FIRST_VALUE(payment_type) OVER (
        PARTITION BY person ORDER BY ts
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    )                                                          AS first_payment_type
FROM joined;


-- ============================================================================
-- Q1. Monthly revenue with running total and month-over-month growth.
--     Windows used: SUM() OVER (running total), LAG() for MoM %.
-- ============================================================================
-- @export q1_monthly_revenue
WITH m AS (
    SELECT order_month,
           COUNT(*)            AS orders,
           SUM(payment_value)  AS revenue
    FROM order_spine
    GROUP BY order_month
)
SELECT
    order_month,
    orders,
    ROUND(revenue, 2)                                            AS revenue,
    ROUND(SUM(revenue) OVER (ORDER BY order_month), 2)           AS revenue_running_total,
    ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY order_month))
                 / LAG(revenue) OVER (ORDER BY order_month), 1)  AS mom_growth_pct
FROM m
ORDER BY order_month;


-- ============================================================================
-- Q2. Customer purchase journey: gap between 1st -> 2nd -> 3rd order per person.
--     Window: LAG() over each person's ordered timeline.
--     (Only repeat customers show up by construction, since prev_ts is NULL
--     for the very first order.)
-- ============================================================================
-- @export q2_repeat_gap
WITH seq AS (
    SELECT person, order_seq, ts,
           LAG(ts) OVER (PARTITION BY person ORDER BY ts) AS prev_ts
    FROM order_spine
)
SELECT
    order_seq,
    COUNT(*)                                                   AS n_orders,
    ROUND(AVG(date_diff('day', prev_ts, ts)), 1)              AS avg_days_since_prev,
    ROUND(MEDIAN(date_diff('day', prev_ts, ts)), 1)           AS median_days_since_prev
FROM seq
WHERE prev_ts IS NOT NULL          -- skip each person's first order
GROUP BY order_seq
ORDER BY order_seq;


-- ============================================================================
-- Q3. Top states by revenue with rank and share of total.
--     Windows: RANK() and SUM() OVER () for share-of-total.
-- ============================================================================
-- @export q3_state_leaderboard
WITH s AS (
    SELECT state,
           SUM(payment_value) AS revenue,
           COUNT(*)           AS orders
    FROM order_spine
    GROUP BY state
)
SELECT
    RANK() OVER (ORDER BY revenue DESC)                        AS rev_rank,
    state,
    orders,
    ROUND(revenue, 2)                                         AS revenue,
    ROUND(100.0 * revenue / SUM(revenue) OVER (), 1)         AS pct_of_total_rev,
    ROUND(100.0 * SUM(revenue) OVER (ORDER BY revenue DESC)
                 / SUM(revenue) OVER (), 1)                   AS cumulative_pct
FROM s
ORDER BY rev_rank;


-- ============================================================================
-- Q4. 7-day moving average of daily orders (windowed frame on a date axis).
--     Window: AVG() OVER (... ROWS BETWEEN 6 PRECEDING AND CURRENT ROW).
--     LIMIT 30 here just so the printed preview stays readable; remove the
--     LIMIT to get the full series.
-- ============================================================================
-- @export q4_daily_orders_ma
WITH d AS (
    SELECT CAST(ts AS DATE) AS day, COUNT(*) AS orders
    FROM order_spine
    GROUP BY 1
)
SELECT
    day,
    orders,
    ROUND(AVG(orders) OVER (ORDER BY day
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1)         AS orders_7d_ma
FROM d
ORDER BY day
LIMIT 30;


-- ============================================================================
-- Q5. Cohort retention matrix.
--     For each acquisition month, what share of that cohort places an order N
--     months after their first? This is a window-free aggregation on top of
--     the windowed spine view (cohort_month + first_ts come from the spine).
-- ============================================================================
-- @export q5_cohort_retention
WITH activity AS (
    SELECT DISTINCT
        person,
        cohort_month,
        date_diff('month', cohort_month, order_month) AS month_offset
    FROM order_spine
),
sizes AS (
    SELECT cohort_month, COUNT(DISTINCT person) AS cohort_size
    FROM activity
    WHERE month_offset = 0
    GROUP BY cohort_month
)
SELECT
    a.cohort_month,
    s.cohort_size,
    a.month_offset,
    COUNT(DISTINCT a.person)                                   AS active,
    ROUND(100.0 * COUNT(DISTINCT a.person) / s.cohort_size, 2) AS retention_pct
FROM activity a
JOIN sizes s USING (cohort_month)
WHERE a.month_offset BETWEEN 0 AND 6
GROUP BY a.cohort_month, s.cohort_size, a.month_offset
ORDER BY a.cohort_month, a.month_offset;


-- ============================================================================
-- Q6. Experiment input: 90-day repeat rate by FIRST-order payment type.
--     One row per PERSON. This is what 03_experiment.py reads in.
--     The spine view did the heavy lifting: order_seq, first_ts and
--     first_payment_type are all from its window functions.
-- ============================================================================
-- @export q6_repeat_by_payment
WITH per_person AS (
    SELECT
        person,
        first_payment_type,
        first_ts,
        MAX(CASE WHEN order_seq >= 2
                 AND date_diff('day', first_ts, ts) <= 90
                 THEN 1 ELSE 0 END)                            AS repeated_90d
    FROM order_spine
    GROUP BY person, first_payment_type, first_ts
)
SELECT
    first_payment_type,
    COUNT(*)                                                  AS customers,
    SUM(repeated_90d)                                         AS repeaters_90d,
    ROUND(100.0 * SUM(repeated_90d) / COUNT(*), 2)           AS repeat_rate_pct
FROM per_person
GROUP BY first_payment_type
ORDER BY customers DESC;
