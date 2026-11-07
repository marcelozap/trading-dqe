from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "output"
DB_PATH = ROOT / "trading_dqe.duckdb"


def sql_string(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def connect() -> duckdb.DuckDBPyConnection:
    OUT.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(f"""
        create or replace table raw_orders as
        select * from read_csv_auto('{sql_string(DATA / "raw_orders.csv")}', all_varchar=true);
    """)
    con.execute(f"""
        create or replace table raw_order_details as
        select * from read_csv_auto('{sql_string(DATA / "raw_order_details.csv")}', all_varchar=true);
    """)
    con.execute(f"""
        create or replace table transform_orders as
        select * from read_csv_auto('{sql_string(DATA / "transform_orders.csv")}', all_varchar=true);
    """)
    con.execute(f"""
        create or replace table transform_order_details as
        select * from read_csv_auto('{sql_string(DATA / "transform_order_details.csv")}', all_varchar=true);
    """)
    return con


def build_quarantine(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        create or replace table quarantine_results as
        with checks as (
            select 'raw_orders' as table_name, 'missing_order_id' as rule_name,
                coalesce(order_id, '<blank>') as business_key,
                'order_id is required' as reason
            from raw_orders
            where order_id is null or trim(order_id) = ''

            union all
            select 'raw_orders', 'duplicate_order_id', order_id,
                'order_id appears more than once'
            from raw_orders
            where order_id is not null and trim(order_id) <> ''
            qualify count(*) over (partition by order_id) > 1

            union all
            select 'raw_orders', 'invalid_status', coalesce(order_id, '<blank>'),
                'status is not in allowed list'
            from raw_orders
            where upper(coalesce(status, '')) not in ('OPEN', 'FILLED', 'CANCELLED', 'REJECTED')

            union all
            select 'raw_orders', 'invalid_order_datetime', coalesce(order_id, '<blank>'),
                'order_datetime is missing or not a timestamp'
            from raw_orders
            where try_cast(order_datetime as timestamp) is null

            union all
            select 'raw_order_details', 'detail_without_header', d.order_detail_id,
                'detail order_id has no matching raw order header'
            from raw_order_details d
            left join raw_orders o on d.order_id = o.order_id
            where o.order_id is null

            union all
            select 'raw_order_details', 'bad_quantity', order_detail_id,
                'quantity must be numeric and greater than zero'
            from raw_order_details
            where try_cast(quantity as double) is null or try_cast(quantity as double) <= 0

            union all
            select 'raw_order_details', 'bad_price', order_detail_id,
                'price must be numeric and greater than zero'
            from raw_order_details
            where try_cast(price as double) is null or try_cast(price as double) <= 0

            union all
            select 'transform_orders', 'raw_order_missing_in_transform', r.order_id,
                'raw order did not land in transform orders'
            from raw_orders r
            left join transform_orders t on r.order_id = t.order_key
            where r.order_id is not null and trim(r.order_id) <> ''
              and t.order_key is null

            union all
            select 'transform_orders', 'transform_order_missing_in_raw', t.order_key,
                'transform order has no matching raw order'
            from transform_orders t
            left join raw_orders r on t.order_key = r.order_id
            where r.order_id is null

            union all
            select 'transform_order_details', 'raw_detail_missing_in_transform', r.order_detail_id,
                'raw detail did not land in transform details'
            from raw_order_details r
            left join transform_order_details t on r.order_detail_id = t.order_line_key
            where t.order_line_key is null

            union all
            select 'transform_order_details', 'transform_detail_missing_in_raw', t.order_line_key,
                'transform detail has no matching raw detail'
            from transform_order_details t
            left join raw_order_details r on t.order_line_key = r.order_detail_id
            where r.order_detail_id is null
        )
        select current_timestamp as checked_at, * from checks;
    """)


def export_outputs(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"""
        copy quarantine_results
        to '{sql_string(OUT / "quarantine_results.csv")}'
        with (header, delimiter ',');
    """)
    con.execute("""
        create or replace table dqe_summary as
        select table_name, rule_name, count(*) as failed_rows
        from quarantine_results
        group by table_name, rule_name
        order by table_name, rule_name;
    """)
    con.execute(f"""
        copy dqe_summary
        to '{sql_string(OUT / "dqe_summary.csv")}'
        with (header, delimiter ',');
    """)


def main() -> None:
    con = connect()
    build_quarantine(con)
    export_outputs(con)
    failures = con.execute("select count(*) from quarantine_results").fetchone()[0]
    print(f"DQE check complete. Failures found: {failures}")
    print(f"Quarantine: {OUT / 'quarantine_results.csv'}")
    print(f"Summary: {OUT / 'dqe_summary.csv'}")


if __name__ == "__main__":
    main()
