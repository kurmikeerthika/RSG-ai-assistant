# RSG GET – Mini AI Business Intelligence Assistant

A FastAPI + SQLite mini BI assistant for the RSG Graduate Engineer Trainee AI-assisted development challenge.

## What it can answer

The assistant supports deterministic database-backed analytics for:

- Total revenue
- Highest-revenue product
- Highest-sales region
- Monthly revenue trend
- Revenue change between two months
- Revenue for a specific month
- Revenue for a specific product/category/region/channel
- Sales breakdown by product
- Sales breakdown by category
- Sales breakdown by region
- Online vs Retail / sales-channel comparison
- Total units sold
- Product with the highest unit volume
- Average transaction/order value
- Valid transaction count
- Total discounts
- Returned transaction summary

The UI also displays supporting figures and the validated SQL used for the answer.

## Data rules

Revenue is calculated as:

`quantity * unit_price - discount_amount`

Only rows with `status = Completed`, positive quantity, and a known unit price are included in revenue calculations. Returned, zero-quantity, and missing-price rows are retained in the database but excluded from revenue KPIs.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## Tests

```powershell
$env:PYTHONPATH='.'
pytest -q
```

Expected: **7 passed**.

## AI safety design

The optional LLM is used only for intent classification. It never generates or executes SQL. The backend maps the approved intent to a fixed SQL template, which prevents destructive SQL and keeps calculations deterministic.

Without an API key, the application uses a local rule-based intent interpreter, so the demo works without an external AI service.
