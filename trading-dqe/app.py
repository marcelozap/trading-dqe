from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "trading_dqe.duckdb"

st.set_page_config(page_title="Trading DQE", layout="wide")
st.title("Trading DQE")
st.caption("Fake data. Local practice for raw -> transform comparison and quarantine logic.")

if not DB_PATH.exists():
    st.warning("Run `python scripts/run_checks.py` first.")
    st.stop()

con = duckdb.connect(str(DB_PATH), read_only=True)

summary = con.execute("select * from dqe_summary").df()
quarantine = con.execute("select * from quarantine_results order by checked_at desc, table_name, rule_name").df()

total_failures = int(quarantine.shape[0])
tables_impacted = int(quarantine["table_name"].nunique()) if total_failures else 0
rules_failed = int(quarantine["rule_name"].nunique()) if total_failures else 0
latest_check = quarantine["checked_at"].max() if total_failures else None

left, middle, right, fourth = st.columns(4)
left.metric("Failed Rows", total_failures)
middle.metric("Tables Impacted", tables_impacted)
right.metric("Rules Failed", rules_failed)
fourth.metric("Latest Check", latest_check.strftime("%Y-%m-%d %H:%M") if latest_check is not None else "No failures")

if total_failures == 0:
    st.success("No quarantine failures found in the latest DQE run.")
    st.stop()

st.subheader("Failure Summary")
st.dataframe(summary, use_container_width=True, hide_index=True)

st.subheader("Failures by Table")
failures_by_table = (
    quarantine.groupby("table_name", as_index=False)
    .size()
    .rename(columns={"size": "failed_rows"})
)
st.bar_chart(failures_by_table, x="table_name", y="failed_rows")

st.subheader("Quarantine Results")
filter_left, filter_right = st.columns(2)
table_filter = filter_left.multiselect("Table", sorted(quarantine["table_name"].unique()))
rule_filter = filter_right.multiselect("Rule", sorted(quarantine["rule_name"].unique()))

view = quarantine
if table_filter:
    view = view[view["table_name"].isin(table_filter)]
if rule_filter:
    view = view[view["rule_name"].isin(rule_filter)]

st.dataframe(view, use_container_width=True, hide_index=True)

st.subheader("Raw vs Transform Counts")
counts = pd.DataFrame(
    [
        {"table": "raw_orders", "rows": con.execute("select count(*) from raw_orders").fetchone()[0]},
        {"table": "transform_orders", "rows": con.execute("select count(*) from transform_orders").fetchone()[0]},
        {"table": "raw_order_details", "rows": con.execute("select count(*) from raw_order_details").fetchone()[0]},
        {"table": "transform_order_details", "rows": con.execute("select count(*) from transform_order_details").fetchone()[0]},
    ]
)
st.bar_chart(counts, x="table", y="rows")
