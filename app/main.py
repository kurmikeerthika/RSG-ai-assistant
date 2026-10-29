from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sqlite3, os, json, re, csv
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent
DB = BASE / 'sales.db'
CSV = BASE / 'data' / 'sales_data.csv'
STATIC = BASE / 'app' / 'static'

app = FastAPI(title='Mini AI Business Intelligence Assistant', version='1.1.0')
app.mount('/static', StaticFiles(directory=STATIC), name='static')


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = conn()
    c.execute('''CREATE TABLE IF NOT EXISTS sales (
        transaction_id TEXT PRIMARY KEY, order_date TEXT NOT NULL, product TEXT NOT NULL,
        category TEXT NOT NULL, region TEXT NOT NULL, sales_channel TEXT NOT NULL,
        quantity INTEGER NOT NULL, unit_price REAL, discount_amount REAL NOT NULL,
        status TEXT NOT NULL
    )''')
    count = c.execute('SELECT COUNT(*) FROM sales').fetchone()[0]
    if count == 0:
        with open(CSV, newline='', encoding='utf-8') as f:
            rows = []
            for r in csv.DictReader(f):
                price = float(r['Unit_price']) if r['Unit_price'].strip() else None
                rows.append((
                    r['Transaction_Id'],
                    datetime.strptime(r['Order_date'], '%d-%m-%Y').strftime('%Y-%m-%d'),
                    r['Product'].strip(), r['Category'].strip(), r['Region'].strip(),
                    r['Sales_channel'].strip(), int(r['Quantity']), price,
                    float(r['Discount_amount']), r['Status'].strip()
                ))
        c.executemany('INSERT INTO sales VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
    c.commit(); c.close()


init_db()


class Question(BaseModel):
    question: str


ALLOWED_INTENTS = {
    'total_revenue', 'top_product', 'monthly_trend', 'top_region', 'month_change',
    'sales_by_category', 'sales_by_channel', 'sales_by_product', 'sales_by_region',
    'total_units', 'top_quantity_product', 'average_order_value', 'transaction_count',
    'total_discount', 'return_summary', 'product_revenue', 'category_revenue',
    'region_revenue', 'channel_revenue', 'month_revenue', 'unsupported'
}


def allowed_base():
    return "status = 'Completed' AND quantity > 0 AND unit_price IS NOT NULL"


def revenue_expr():
    return '(quantity * unit_price - discount_amount)'


def query(sql, params=()):
    c = conn()
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    c.close()
    return rows


def result(intent, sql, params=(), answer=''):
    return {'intent': intent, 'answer': answer, 'rows': query(sql, params), 'sql': sql}


def clean_name(text):
    return re.sub(r'[^a-z0-9\- ]', '', text.lower()).strip()


def find_value(s, values):
    for v in sorted(values, key=len, reverse=True):
        if v.lower() in s:
            return v
    return None


def interpret(q):
    s = q.lower().strip()
    if not s:
        return {'intent': 'unsupported'}

    products = [r['product'] for r in query('SELECT DISTINCT product FROM sales')]
    categories = [r['category'] for r in query('SELECT DISTINCT category FROM sales')]
    regions = [r['region'] for r in query('SELECT DISTINCT region FROM sales')]
    channels = [r['sales_channel'] for r in query('SELECT DISTINCT sales_channel FROM sales')]

    product = find_value(s, products)
    category = find_value(s, categories)
    region = find_value(s, regions)
    channel = find_value(s, channels)

    # Explicit comparison: "between January and March", "January vs March", etc.
    month_names = {'jan':'01','january':'01','feb':'02','february':'02','mar':'03','march':'03',
                   'apr':'04','april':'04','may':'05','jun':'06','june':'06'}
    month_pattern = r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?)'
    m = re.search(rf'\b{month_pattern}\b.*?\b(?:and|to|vs|versus)\b.*?\b{month_pattern}\b', s)
    if m or ('compare' in s and 'month' in s) or ('change' in s and 'month' in s):
        return {'intent': 'month_change', 'month1': m.group(1) if m else None, 'month2': m.group(2) if m else None}

    # Specific month revenue.
    month_match = re.search(rf'\b{month_pattern}\b', s)
    if month_match and ('revenue' in s or 'sales' in s) and ('monthly' not in s and 'trend' not in s):
        return {'intent': 'month_revenue', 'month': month_match.group(1)}

    # Generic breakdowns come before single-entity matching so questions like
    # "compare online vs retail" are treated as a channel comparison.
    if ('channel' in s or 'online vs retail' in s or ('online' in s and 'retail' in s)) and any(w in s for w in ['breakdown','compare','by channel','each channel','sales by','vs']):
        return {'intent': 'sales_by_channel'}

    # Specific entity revenue.
    if product and ('revenue' in s or 'sales' in s) and not ('highest' in s or 'top' in s or 'best' in s):
        return {'intent': 'product_revenue', 'product': product}
    if category and ('revenue' in s or 'sales' in s) and not ('highest' in s or 'top' in s):
        return {'intent': 'category_revenue', 'category': category}
    if region and ('revenue' in s or 'sales' in s) and not ('highest' in s or 'top' in s):
        return {'intent': 'region_revenue', 'region': region}
    if channel and ('revenue' in s or 'sales' in s) and not ('highest' in s or 'top' in s):
        return {'intent': 'channel_revenue', 'channel': channel}

    # Generic breakdowns.
    if 'category' in s and any(w in s for w in ['breakdown','break up','by category','each category','per category','sales by']):
        return {'intent': 'sales_by_category'}
    if ('channel' in s or 'online vs retail' in s or ('online' in s and 'retail' in s)) and any(w in s for w in ['breakdown','compare','by channel','each channel','sales by','vs']):
        return {'intent': 'sales_by_channel'}
    if 'product' in s and any(w in s for w in ['breakdown','by product','each product','per product','sales by']):
        return {'intent': 'sales_by_product'}
    if 'region' in s and any(w in s for w in ['breakdown','by region','each region','per region','sales by']):
        return {'intent': 'sales_by_region'}

    # Ranking / KPIs.
    if ('highest' in s or 'top' in s or 'best' in s or 'most' in s) and any(x in s for x in ['quantity','units']) and ('product' in s or 'sold' in s):
        return {'intent': 'top_quantity_product'}
    if ('highest' in s or 'top' in s) and 'product' in s and ('revenue' in s or 'sales' in s):
        return {'intent': 'top_product'}
    if ('highest' in s or 'top' in s) and 'region' in s:
        return {'intent': 'top_region'}
    if 'monthly' in s or ('month' in s and 'trend' in s):
        return {'intent': 'monthly_trend'}
    if ('average' in s or 'avg' in s or 'mean' in s) and any(x in s for x in ['order value','transaction value','sale value']):
        return {'intent': 'average_order_value'}
    if 'return' in s and any(x in s for x in ['how many','count','summary','returned']):
        return {'intent': 'return_summary'}
    if ('how many' in s or 'number of' in s or 'count' in s) and 'transaction' in s:
        return {'intent': 'transaction_count'}
    if ('how many' in s or 'total' in s or 'sum' in s) and any(x in s for x in ['units','quantity','items']):
        return {'intent': 'total_units'}
    if 'discount' in s and any(x in s for x in ['total','sum','how much']):
        return {'intent': 'total_discount'}
    if 'total' in s and ('revenue' in s or 'sales' in s):
        return {'intent': 'total_revenue'}
    if 'revenue' in s and ('how much' in s or 'total' in s):
        return {'intent': 'total_revenue'}

    return {'intent': 'unsupported'}


def run_intent(p):
    intent = p['intent']
    base = allowed_base()
    rev = revenue_expr()

    if intent == 'total_revenue':
        sql = f"SELECT ROUND(SUM({rev}),2) AS total_revenue, COUNT(*) AS included_transactions FROM sales WHERE {base}"
        r = result(intent, sql)
        v = r['rows'][0]
        r['answer'] = f"Total revenue is ₹{v['total_revenue']:,.2f} across {v['included_transactions']} valid completed transactions."
        return r

    if intent == 'top_product':
        sql = f"SELECT product, ROUND(SUM({rev}),2) AS revenue FROM sales WHERE {base} GROUP BY product ORDER BY revenue DESC LIMIT 10"
        r = result(intent, sql); v = r['rows'][0]
        r['answer'] = f"{v['product']} generated the highest revenue at ₹{v['revenue']:,.2f}."
        return r

    if intent == 'top_region':
        sql = f"SELECT region, ROUND(SUM({rev}),2) AS revenue FROM sales WHERE {base} GROUP BY region ORDER BY revenue DESC"
        r = result(intent, sql); v = r['rows'][0]
        r['answer'] = f"{v['region']} generated the highest sales at ₹{v['revenue']:,.2f}."
        return r

    if intent == 'monthly_trend':
        sql = f"SELECT strftime('%Y-%m', order_date) AS month, ROUND(SUM({rev}),2) AS revenue FROM sales WHERE {base} GROUP BY month ORDER BY month"
        return result(intent, sql, answer='Monthly revenue trend for completed, valid transactions.')

    if intent == 'month_change':
        rows = query(f"SELECT strftime('%Y-%m', order_date) AS month, ROUND(SUM({rev}),2) AS revenue FROM sales WHERE {base} GROUP BY month ORDER BY month")
        r = {'intent': intent, 'rows': rows, 'sql': f"SELECT strftime('%Y-%m', order_date) AS month, ROUND(SUM({rev}),2) AS revenue FROM sales WHERE {base} GROUP BY month ORDER BY month", 'answer': ''}
        if p.get('month1') and p.get('month2'):
            names = {'jan':'01','january':'01','feb':'02','february':'02','mar':'03','march':'03','apr':'04','april':'04','may':'05','jun':'06','june':'06'}
            a, b = names[p['month1']], names[p['month2']]
            ra = next((x['revenue'] for x in rows if x['month'].endswith('-'+a)), None)
            rb = next((x['revenue'] for x in rows if x['month'].endswith('-'+b)), None)
            if ra is not None and rb is not None:
                diff = rb - ra
                pct = (diff / ra * 100) if ra else 0
                direction = 'increased' if diff >= 0 else 'decreased'
                r['answer'] = f"Revenue {direction} by ₹{abs(diff):,.2f} ({abs(pct):.2f}%) from {p['month1'].title()} to {p['month2'].title()}."
                return r
        r['answer'] = 'Monthly revenue figures are shown below. For two named months, change is later month minus earlier month.'
        return r

    if intent in {'sales_by_category','sales_by_channel','sales_by_product','sales_by_region'}:
        mapping = {
            'sales_by_category': ('category','Category'), 'sales_by_channel': ('sales_channel','Sales channel'),
            'sales_by_product': ('product','Product'), 'sales_by_region': ('region','Region')
        }
        col, label = mapping[intent]
        sql = f"SELECT {col}, ROUND(SUM({rev}),2) AS revenue, SUM(quantity) AS units, COUNT(*) AS transactions FROM sales WHERE {base} GROUP BY {col} ORDER BY revenue DESC"
        return result(intent, sql, answer=f"Revenue breakdown by {label.lower()}.")

    if intent == 'total_units':
        sql = f"SELECT SUM(quantity) AS total_units, COUNT(*) AS transactions FROM sales WHERE {base}"
        r = result(intent, sql); v=r['rows'][0]
        r['answer'] = f"Total units sold are {v['total_units']:,} across {v['transactions']} valid transactions."
        return r

    if intent == 'top_quantity_product':
        sql = f"SELECT product, SUM(quantity) AS units, ROUND(SUM({rev}),2) AS revenue FROM sales WHERE {base} GROUP BY product ORDER BY units DESC LIMIT 10"
        r = result(intent, sql); v=r['rows'][0]
        r['answer'] = f"{v['product']} sold the most units: {v['units']:,}."
        return r

    if intent == 'average_order_value':
        sql = f"SELECT ROUND(AVG(order_revenue),2) AS average_order_value, COUNT(*) AS transactions FROM (SELECT transaction_id, {rev} AS order_revenue FROM sales WHERE {base})"
        r=result(intent,sql); v=r['rows'][0]
        r['answer']=f"Average transaction value is ₹{v['average_order_value']:,.2f}."
        return r

    if intent == 'transaction_count':
        sql = f"SELECT COUNT(*) AS transactions FROM sales WHERE {base}"
        r=result(intent,sql); r['answer']=f"There are {r['rows'][0]['transactions']} valid completed transactions."
        return r

    if intent == 'total_discount':
        sql = f"SELECT ROUND(SUM(discount_amount),2) AS total_discount FROM sales WHERE {base}"
        r=result(intent,sql); r['answer']=f"Total discount applied to valid completed sales is ₹{r['rows'][0]['total_discount']:,.2f}."
        return r

    if intent == 'return_summary':
        sql = "SELECT status, COUNT(*) AS transactions, COALESCE(SUM(quantity),0) AS units FROM sales WHERE status='Returned' GROUP BY status"
        r=result(intent,sql); returned=r['rows'][0] if r['rows'] else None
        r['answer']=f"There are {returned['transactions'] if returned else 0} returned transaction(s)."
        return r

    if intent in {'product_revenue','category_revenue','region_revenue','channel_revenue'}:
        mapping = {'product_revenue':('product','product'),'category_revenue':('category','category'),'region_revenue':('region','region'),'channel_revenue':('sales_channel','sales channel')}
        col,label=mapping[intent]; value=p[intent.split('_')[0] if intent != 'channel_revenue' else 'channel']
        sql=f"SELECT {col} AS {col}, ROUND(SUM({rev}),2) AS revenue, SUM(quantity) AS units, COUNT(*) AS transactions FROM sales WHERE {base} AND LOWER({col}) = LOWER(?) GROUP BY {col}"
        r=result(intent,sql,(value,))
        if r['rows']:
            v=r['rows'][0]; r['answer']=f"{v[col]} generated ₹{v['revenue']:,.2f} from {v['transactions']} valid transaction(s)."
        else: r['answer']=f"No valid completed sales were found for {value}."
        return r

    if intent == 'month_revenue':
        names={'jan':'01','january':'01','feb':'02','february':'02','mar':'03','march':'03','apr':'04','april':'04','may':'05','jun':'06','june':'06'}
        mm=names[p['month']]
        sql=f"SELECT strftime('%Y-%m', order_date) AS month, ROUND(SUM({rev}),2) AS revenue, SUM(quantity) AS units, COUNT(*) AS transactions FROM sales WHERE {base} AND strftime('%m', order_date)=? GROUP BY month"
        r=result(intent,sql,(mm,)); r['answer']=f"Revenue for {p['month'].title()} is ₹{r['rows'][0]['revenue']:,.2f}." if r['rows'] else f"No valid sales found for {p['month'].title()}."
        return r

    return {'intent':'unsupported','answer': 'I can calculate revenue, units, transaction counts, averages, discounts, returns, monthly trends, month comparisons, and breakdowns by product, category, region, or sales channel.','rows':[],'sql':None}


def llm_interpret(q):
    """Optional AI interpretation. The SQL is never generated by the model."""
    key=os.getenv('OPENAI_API_KEY')
    if not key: return None
    try:
        from openai import OpenAI
        client=OpenAI(api_key=key)
        intents=', '.join(sorted(ALLOWED_INTENTS))
        resp=client.chat.completions.create(
            model=os.getenv('OPENAI_MODEL','gpt-4o-mini'), temperature=0,
            response_format={'type':'json_object'},
            messages=[
                {'role':'system','content':f'Classify a sales BI question. Return JSON {{"intent": one of [{intents}]}}. Never generate SQL.'},
                {'role':'user','content':q}
            ])
        data=json.loads(resp.choices[0].message.content)
        if data.get('intent') in ALLOWED_INTENTS: return data
    except Exception:
        return None
    return None


@app.get('/')
def home(): return FileResponse(STATIC/'index.html')

@app.get('/health')
def health(): return {'status':'ok'}

@app.post('/ask')
def ask(item: Question):
    if len(item.question)>500: raise HTTPException(400,'Question is too long.')
    # Prefer the deterministic interpreter because it extracts required parameters
    # (product/category/region/months) as well as the intent. Use the optional LLM
    # only when the local interpreter cannot understand the question.
    parsed=interpret(item.question)
    if parsed.get('intent') == 'unsupported':
        ai=llm_interpret(item.question)
        if ai:
            parsed=ai
    return run_intent(parsed)

@app.get('/data-quality')
def quality():
    c=conn()
    total=c.execute('SELECT COUNT(*) n FROM sales').fetchone()['n']
    missing=c.execute('SELECT COUNT(*) n FROM sales WHERE unit_price IS NULL').fetchone()['n']
    zero=c.execute('SELECT COUNT(*) n FROM sales WHERE quantity <= 0').fetchone()['n']
    returned=c.execute("SELECT COUNT(*) n FROM sales WHERE status='Returned'").fetchone()['n']
    c.close()
    return {'total_rows':total,'missing_unit_price':missing,'zero_or_negative_quantity':zero,'returned_rows':returned,
            'revenue_policy':'Completed + quantity > 0 + known unit price; returned/invalid rows are excluded.'}
