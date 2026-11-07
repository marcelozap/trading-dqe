# Trading DQE

Local-first practice project for raw-to-transform data quality checks.

This uses fake trading/order data so no work files, screenshots, or company data are needed.

## Run

```powershell
python -m pip install -r requirements.txt
python scripts/run_checks.py
streamlit run app.py
```

## What It Teaches

- raw table to transform table comparison
- required field checks
- duplicate business key checks
- status validation
- date validation
- detail-without-header checks
- quarantine output with reasons

## Shape

```text
source -> raw -> DQ checks -> transform -> quarantine/report
```
