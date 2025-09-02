from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.model.products import Products
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions

from .plaid_client import get_plaid_client
from .db import SessionLocal, init_db
from .models import Item, Transaction


def seed_sandbox_item(institution_id: str = "ins_109508"):
    """Create a Sandbox Item and store its access_token in DB."""
    init_db()
    client = get_plaid_client()

    req = SandboxPublicTokenCreateRequest(
        institution_id=institution_id,
        initial_products=[Products("transactions")],
        options={"transactions": {"days_requested": 90}},
    )
    resp = client.sandbox_public_token_create(req)
    public_token = resp.public_token

    exchange_req = ItemPublicTokenExchangeRequest(public_token=public_token)
    exchange_resp = client.item_public_token_exchange(exchange_req)
    access_token = exchange_resp.access_token

    with SessionLocal() as s:
        item = Item(access_token=access_token, institution_name="First Platypus Bank")
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


def _top_and_sub_category(t) -> Tuple[str, Optional[str]]:
    """
    Prefer Plaid Personal Finance Category (PFC). `t` is a Plaid model, not a dict.
    """
    pfc = getattr(t, "personal_finance_category", None)
    if pfc:
        primary = getattr(pfc, "primary", None)
        detailed = getattr(pfc, "detailed", None)
        if primary:
            top = primary.split("_")[0].title()
            sub = detailed.replace("_", " ").title() if detailed else None
            return top, sub

    cats = getattr(t, "category", None) or []
    top = cats[0] if cats else "Other"
    sub = cats[1] if len(cats) > 1 else None
    return top, sub


def sync_transactions(access_token: Optional[str] = None, days: int = 90) -> int:
    """Pull transactions for the last N days and upsert into DB. Returns count inserted."""
    init_db()
    with SessionLocal() as s:
        if not access_token:
            item = s.execute(select(Item)).scalar_one_or_none()
            if not item:
                raise RuntimeError("No Item in DB. Run seed_sandbox_item() first.")
            access_token = item.access_token

        client = get_plaid_client()
        start_date = (datetime.utcnow() - timedelta(days=days)).date()
        end_date   = datetime.utcnow().date()

        req = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            options=TransactionsGetRequestOptions(count=500, offset=0),
        )

        inserted = 0
        while True:
            resp = client.transactions_get(req)
            transactions: List = resp.transactions  
            for t in transactions:
                top, sub = _top_and_sub_category(t)
                model = Transaction(
                    plaid_txn_id=t.transaction_id,
                    account_id=t.account_id,
                    name=t.name,
                    merchant_name=t.merchant_name,
                    amount=float(t.amount or 0.0),
                    date=t.date, 
                    category=top,
                    subcategory=sub,
                    iso_currency=t.iso_currency_code or "USD",
                    pending=bool(t.pending or False),
                )
                try:
                    s.add(model)
                    s.commit()
                    inserted += 1
                except IntegrityError:
                    s.rollback()  

            total = resp.total_transactions
            if req.options.offset + req.options.count >= total:
                break
            req.options.offset += req.options.count

        return inserted
