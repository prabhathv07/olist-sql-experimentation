# Loads the Olist CSVs into DuckDB, runs every query in 02_analysis.sql, prints
# each result, and writes the rows to results/<name>.csv so the other scripts
# can pick them up.

import os
import re
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).resolve().parent

# Prefer real Olist data if it's there, otherwise fall back to the synthetic CSVs
# that 01_generate_data.py produces.
if (HERE / "data_real").is_dir():
    DATA = HERE / "data_real"
else:
    DATA = HERE / "data"

RES = HERE / "results"
RES.mkdir(exist_ok=True)

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 30)

# in-memory db so reruns don't trip on leftover .wal files
con = duckdb.connect()

# If you happen to have the Kaggle "Olist as SQLite database" file at
# data/olist.sqlite, this branch loads it directly via DuckDB's sqlite extension
# and the rest of the script is identical.
sqlite_path = DATA / "olist.sqlite"
if sqlite_path.exists():
    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute(f"ATTACH '{sqlite_path}' AS olist (TYPE sqlite);")
    for t in ["customers", "orders", "order_items", "order_payments"]:
        con.execute(f"CREATE OR REPLACE VIEW {t} AS SELECT * FROM olist.{t}")
    print(f"[source] real Olist SQLite db: {sqlite_path}")
else:
    for t in ["customers", "orders", "order_items", "order_payments"]:
        con.execute(
            f"CREATE OR REPLACE VIEW {t} AS "
            f"SELECT * FROM read_csv_auto('{DATA / (t + '.csv')}')"
        )
    label = "real Olist (data_real/)" if DATA.name == "data_real" else "synthetic CSVs"
    print(f"[source] {label} from {DATA}")

# Read the SQL file. Everything before the first `-- @export` is the spine view;
# after that we have alternating "-- @export <name>" markers and the query body.
sql_text = (HERE / "02_analysis.sql").read_text()

spine_block = sql_text.split("-- @export", 1)[0]
con.execute(spine_block)

# split into (name, body) pairs
chunks = re.split(r"-- @export\s+(\w+)", sql_text)[1:]
pairs = list(zip(chunks[0::2], chunks[1::2]))

for name, body in pairs:
    # body may have trailing comments / the start of the next section's header,
    # so keep only up to the last semicolon (end of this query).
    stmt = body[: body.rfind(";") + 1]
    df = con.execute(stmt).df()
    df.to_csv(RES / f"{name}.csv", index=False)

    print("\n" + "=" * 78)
    print(f"{name}  ({len(df)} rows)")
    print("=" * 78)

    if name == "q5_cohort_retention":
        # pivot to the classic triangular retention matrix
        pivoted = df.pivot(
            index=["cohort_month", "cohort_size"],
            columns="month_offset",
            values="retention_pct",
        )
        print(pivoted.to_string())
        pivoted.to_csv(RES / "q5_cohort_matrix.csv")
    else:
        print(df.to_string(index=False))

con.close()
print(f"\nAll results written to {RES}")
