from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_total_revenue():
    r = client.post('/ask', json={'question':'What is the total revenue?'})
    assert r.status_code == 200
    assert r.json()['rows'][0]['total_revenue'] == 1439200.0

def test_top_product():
    d = client.post('/ask', json={'question':'Which product generated the highest revenue?'}).json()
    assert d['rows'][0]['product'] == 'Monitor'

def test_monthly_trend():
    d = client.post('/ask', json={'question':'What is the monthly revenue trend?'}).json()
    assert len(d['rows']) == 6

def test_top_region():
    d = client.post('/ask', json={'question':'Which region generated the highest sales?'}).json()
    assert d['rows'][0]['region'] == 'South'

def test_new_analytics():
    assert client.post('/ask', json={'question':'Which product sold the most units?'}).json()['rows'][0]['product'] == 'Wireless Mouse'
    assert client.post('/ask', json={'question':'Show sales by category'}).json()['intent'] == 'sales_by_category'
    assert client.post('/ask', json={'question':'How many returned transactions?'}).json()['rows'][0]['status'] == 'Returned'
    assert client.post('/ask', json={'question':'What is the average order value?'}).json()['intent'] == 'average_order_value'

def test_invalid_question():
    d = client.post('/ask', json={'question':'What is the weather today?'}).json()
    assert d['intent'] == 'unsupported'

def test_empty_question():
    d = client.post('/ask', json={'question':''}).json()
    assert d['intent'] == 'unsupported'
