# app/web.py
from __future__ import annotations

from flask import Flask, jsonify, render_template, request, redirect, url_for
from urllib.parse import urlparse, urlencode, urlunparse, parse_qsl

from sqlalchemy import select, text

from .config import settings
from .db import init_db, SessionLocal
from .models import Item, Transaction
from .plaid_client import get_plaid_client

# Plaid models
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

# App logic
from .ingest import sync_transactions
from app.budget import compare_to_budget_window, generate_budgets, save_budgets
from app.agent_loop import propose_actions

# ------------------------------------------------------------------------------
# Flask app
# ------------------------------------------------------------------------------
app = Flask(__name__, template_folder="../templates", static_folder="../static")
init_db()


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def _get_first_item(session) -> Item | None:
    return session.execute(select(Item)).scalar_one_or_none()


# ------------------------------------------------------------------------------
# Home + Plaid Link
# ------------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    with SessionLocal() as s:
        item = _get_first_item(s)
        is_connected = item is not None
    return render_template("index.html", is_connected=is_connected)


@app.route("/api/link_token", methods=["GET"])
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


@app.route("/api/exchange_public_token", methods=["POST"])
def api_exchange_public_token():
    """Exchange public_token for access_token and store Item. Auto-sync 90d."""
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

    # Auto-sync so the UI has data immediately
    try:
        sync_transactions(access_token=access_token, days=90)
    except Exception:
        # Keep UI happy even if sync hiccups
        pass

    return jsonify({"ok": True})


# ------------------------------------------------------------------------------
# Transactions (with timeframe + multi-category filters)
# ------------------------------------------------------------------------------
@app.route("/transactions", methods=["GET"])
def transactions_page():
    days = int(request.args.get("days", "90"))
    categories_selected = request.args.getlist("category")
    if not categories_selected or "All" in categories_selected:
        categories_selected = ["All"]

    q = """
        SELECT id, date, name, merchant_name, category, subcategory, amount, iso_currency
        FROM transactions
        WHERE pending = 0
          AND amount > 0
          AND date >= DATE('now', :days)
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
        # Distinct categories for chips
        cats = s.execute(
            text("SELECT DISTINCT COALESCE(category,'Other') FROM transactions")
        ).scalars().all()
        categories = sorted({"All", *[c or "Other" for c in cats]})

    return render_template(
        "transactions.html",
        rows=rows,
        days=days,
        categories=categories,
        categories_selected=categories_selected,
    )


# ------------------------------------------------------------------------------
# Budgets (windowed actuals vs monthly budgets scaled to window)
# ------------------------------------------------------------------------------
@app.route("/budgets", methods=["GET", "POST"])
def budgets_page():
    # Rebuild budgets if POST
    if request.method == "POST":
        budgets = generate_budgets(days=90, cushion=0.10)
        save_budgets(budgets)

    days = int(request.args.get("days", "90"))
    cmp = compare_to_budget_window(days=days)

    rows = []
    for cat, (monthly_budget, actual, delta, pct) in sorted(cmp.items(), key=lambda kv: kv[0].lower()):
        status = "Under" if delta < 0 else ("Over" if delta > 0 else "On Track")
        rows.append({
            "category": cat,
            "budget": monthly_budget,
            "actual": actual,
            "delta": delta,
            "pct": pct,
            "status": status
        })

    suggestions = propose_actions()  # (still month-based for now)
    return render_template("budgets.html", rows=rows, suggestions=suggestions, days=days)

# ------------------------------------------------------------------------------
# Sync latest transactions (POST), then redirect back with ?synced=N
# ------------------------------------------------------------------------------
@app.route("/sync", methods=["POST"])
def sync_now():
    days = int(request.form.get("days", "90"))

    with SessionLocal() as s:
        item = _get_first_item(s)
        if not item:
            return redirect(url_for("home"))
        access_token = item.access_token

    inserted = 0
    try:
        inserted = sync_transactions(access_token=access_token, days=days)
    except Exception:
        inserted = 0

    ref = request.headers.get("Referer") or url_for("transactions_page")
    u = urlparse(ref)
    q = dict(parse_qsl(u.query))
    q["synced"] = str(inserted)
    target = urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))
    return redirect(target)
