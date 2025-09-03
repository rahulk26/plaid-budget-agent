from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Dict
from sqlalchemy import text
from .db import SessionLocal, init_db

@dataclass
class SpendSummary:
    by_category: Dict[str, float]
    total_spend: float

def spend_by_category(days: int = 90) -> SpendSummary:
    """
    Aggregate transactions by category over the last N days.
    Only counts settled (pending=0) expenses (amount > 0).
    """
    init_db()
    sql = text(
        """
        SELECT COALESCE(category, 'Other') as cat, SUM(amount) as spend
        FROM transactions
        WHERE pending = 0
          AND date >= DATE('now', :days)
          AND amount > 0
        GROUP BY cat
        ORDER BY spend DESC
        """
    )
    by_cat: Dict[str, float] = {}
    with SessionLocal() as s:
        rows = s.execute(sql, {"days": f"-{days} day"}).all()
        for cat, spend in rows:
            by_cat[cat] = float(spend or 0.0)
    return SpendSummary(by_category=by_cat, total_spend=sum(by_cat.values()))

from typing import Tuple
from calendar import monthrange
from .db import SessionLocal, init_db
from .models import Budget

def _current_month() -> str:
    today = date.today()
    return f"{today.year}-{today.month:02d}"

def generate_budgets(days: int = 90, cushion: float = 0.10) -> Dict[str, float]:
    """
    Naive baseline: use last N days spend/category → scale to monthly → add cushion.
    Example: 90d spend of $900 → monthly ~ $300 → +10% = $330.
    """
    summary = spend_by_category(days=days)
    monthly_scale = 30.0 / days
    budgets = {cat: round(spend * monthly_scale * (1 + cushion), 2)
               for cat, spend in summary.by_category.items()}
    return budgets

def save_budgets(budgets: Dict[str, float], month: str | None = None) -> None:
    """
    Upsert monthly budgets for each category.
    """
    init_db()
    if not month:
        month = _current_month()
    with SessionLocal() as s:
        for cat, amt in budgets.items():
            s.merge(Budget(month=month, category=cat, amount=float(amt)))
        s.commit()

def month_spend(month: str | None = None) -> Dict[str, float]:
    """
    Actual spend for a given month (YYYY-MM).
    """
    if not month:
        month = _current_month()
    y, m = map(int, month.split("-"))
    start = f"{y}-{m:02d}-01"
    end_day = monthrange(y, m)[1]
    end = f"{y}-{m:02d}-{end_day:02d}"
    sql = text(
        """
        SELECT COALESCE(category, 'Other') as cat, SUM(amount) as spend
        FROM transactions
        WHERE pending = 0
          AND date BETWEEN :start AND :end
          AND amount > 0
        GROUP BY cat
        """
    )
    with SessionLocal() as s:
        rows = s.execute(sql, {"start": start, "end": end}).all()
        return {cat: float(spend or 0.0) for cat, spend in rows}

def compare_to_budget(month: str | None = None) -> Dict[str, Tuple[float, float, float]]:
    """
    Return {cat: (budget, actual, delta)} for the month.
    delta = actual - budget  (positive = over budget)
    """
    if not month:
        month = _current_month()
    with SessionLocal() as s:
        budgets = {b.category: b.amount for b in s.query(Budget).filter(Budget.month == month).all()}
    actual = month_spend(month)
    all_cats = set(budgets.keys()) | set(actual.keys())
    out = {}
    for cat in all_cats:
        b = float(budgets.get(cat, 0.0))
        a = float(actual.get(cat, 0.0))
        out[cat] = (b, a, round(a - b, 2))
    return out

