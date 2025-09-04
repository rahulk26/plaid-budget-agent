from __future__ import annotations
from flask import Flask, jsonify, render_template, request, redirect, url_for
from datetime import date, timedelta
from sqlalchemy import select, text
from .config import settings
from .db import init_db, SessionLocal
from .models import Item, Transaction
from .plaid_client import get_plaid_client

from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

from app.budget import compare_to_budget, generate_budgets, save_budgets
from app.agent_loop import propose_actions


app = Flask(__name__, template_folder="../templates", static_folder="../static")
init_db()

def _get_first_item(session):
    return session.execute(select(Item)).scalar_one_or_none()

@app.get("/")
def home():
    with SessionLocal() as s:
        item = _get_first_item(s)
        is_connected = item is not None
    return render_template("index.html", is_connected=is_connected)

@app.get("/api/link_token")
def api_link_token():
    """Create a short-lived link_token for Plaid Link initialization."""
    client = get_plaid_client()
    req = LinkTokenCreateRequest(
        products=[Products("transactions")],
        client_name="Plaid Budget Agent",
        country_codes=[CountryCode(settings.plaid_country)],
        language="en",
        user=LinkTokenCreateRequestUser(client_user_id="demo-user-123"),
    )
    resp = client.link_token_create(req)
    return jsonify({"link_token": resp.link_token})

@app.post("/api/exchange_public_token")
def api_exchange_public_token():
    """Exchange public_token for access_token and store Item."""
    public_token = request.json.get("public_token")
    if not public_token:
        return jsonify({"error": "missing public_token"}), 400

    client = get_plaid_client()
    exchange_req = ItemPublicTokenExchangeRequest(public_token=public_token)
    exchange_resp = client.item_public_token_exchange(exchange_req)
    access_token = exchange_resp.access_token

    with SessionLocal() as s:
        existing = _get_first_item(s)
        if existing:
            existing.access_token = access_token
        else:
            s.add(Item(access_token=access_token, institution_name="(via Link)"))
        s.commit()

    return jsonify({"ok": True})

@app.get("/transactions")
def transactions_page():
    """Transactions page with filters: days (30/60/90) + category."""
    # app/web.py (inside transactions_page)
    days = int(request.args.get("days", "90"))
    categories_selected = request.args.getlist("category")  # <-- multi-select
    if not categories_selected or "All" in categories_selected:
        categories_selected = ["All"]

    q = """
        SELECT id, date, name, merchant_name, category, subcategory, amount, iso_currency
        FROM transactions
        WHERE pending = 0
        AND date >= DATE('now', :days)
        AND amount > 0
    """
    params = {"days": f"-{days} day"}

    if "All" not in categories_selected:
        placeholders = ",".join([f":cat{i}" for i in range(len(categories_selected))])
        q += f" AND COALESCE(category,'Other') IN ({placeholders})"
        for i, c in enumerate(categories_selected):
            params[f"cat{i}"] = c

    q += " ORDER BY date DESC"

    with SessionLocal() as s:
        rows = s.execute(text(q), params).all()
        cats = s.execute(text("SELECT DISTINCT COALESCE(category,'Other') FROM transactions")).scalars().all()
        categories = sorted({"All", *[c or "Other" for c in cats]})

    return render_template(
        "transactions.html",
        rows=rows, days=days,
        categories=categories,
        categories_selected=categories_selected
    )
