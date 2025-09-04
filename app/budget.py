# app/budget.py
from __future__ import annotations
from typing import Dict, Tuple
from sqlalchemy import text
from datetime import datetime

from .db import SessionLocal
from .models import Budget

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def _current_month() -> str:
    """Return current month as YYYY-MM string."""
    return datetime.now().strftime("%Y-%m")


# ------------------------------------------------------------------------------
# Generate and save budgets
# ------------------------------------------------------------------------------

def generate_budgets(days: int = 90, cushion: float = 0.10) -> Dict[str, float]:
    """
    Look at the last N days of spend, average per month, and add cushion.
    Returns {category: monthly_budget}.
    """
    sql = text("""
      SELECT COALESCE(category,'Other') as cat, SUM(amount) as spend
      FROM transactions
      WHERE pending = 0
        AND date >= DATE('now', :days)
        AND amount > 0
      GROUP BY cat
    """)
    with SessionLocal() as s:
        rows = s.execute(sql, {"days": f"-{days} day"}).all()

    budgets: Dict[str, float] = {}
    scale = max(1.0, days / 30.0)  # convert window to months
    for cat, spend in rows:
        monthly_avg = (spend or 0.0) / scale
        budgets[cat] = round(monthly_avg * (1.0 + cushion), 2)
    return budgets


def save_budgets(budgets: Dict[str, float]) -> None:
    """Save generated budgets into DB for current month."""
    month = _current_month()
    with SessionLocal() as s:
        # Delete existing budgets for this month
        s.query(Budget).filter(Budget.month == month).delete()
        # Insert new
        for cat, amt in budgets.items():
            s.add(Budget(month=month, category=cat, amount=amt))
        s.commit()


# ------------------------------------------------------------------------------
# Month-to-date comparison
# ------------------------------------------------------------------------------

def compare_to_budget(month: str | None = None) -> Dict[str, Tuple[float, float, float]]:
    """
    Compare actual spend (month-to-date) vs saved budgets for given month.
    Returns {category: (budget, actual, delta)}.
    """
    if month is None:
        month = _current_month()

    sql = text("""
      SELECT COALESCE(category,'Other') as cat, SUM(amount) as spend
      FROM transactions
      WHERE pending = 0
        AND strftime('%Y-%m', date) = :month
        AND amount > 0
      GROUP BY cat
    """)
    with SessionLocal() as s:
        actuals = dict(s.execute(sql, {"month": month}).all())
        budgets = {b.category or "Other": float(b.amount)
                   for b in s.query(Budget).filter(Budget.month == month).all()}

    out: Dict[str, Tuple[float, float, float]] = {}
    for cat in set(budgets) | set(actuals):
        b = budgets.get(cat, 0.0)
        a = float(actuals.get(cat, 0.0) or 0.0)
        d = a - b
        out[cat] = (b, a, d)
    return out


# ------------------------------------------------------------------------------
# Timeframe-window comparison (scaled budgets)
# ------------------------------------------------------------------------------

def spend_by_category_window(days: int = 90) -> Dict[str, float]:
    """Aggregate spend by category over the last N days."""
    sql = text("""
      SELECT COALESCE(category,'Other') as cat, SUM(amount) as spend
      FROM transactions
      WHERE pending = 0
        AND date >= DATE('now', :days)
        AND amount > 0
      GROUP BY cat
    """)
    with SessionLocal() as s:
        rows = s.execute(sql, {"days": f"-{days} day"}).all()
        return {cat: float(spend or 0.0) for cat, spend in rows}


def compare_to_budget_window(days: int = 90) -> Dict[str, Tuple[float, float, float, float]]:
    """
    Compare actual spending in last N days against monthly budgets, scaled to window.
    Returns {category: (monthly_budget, actual_window, delta, pct)}.
    """
    actuals = spend_by_category_window(days)
    with SessionLocal() as s:
        budgets = {b.category or "Other": float(b.amount)
                   for b in s.query(Budget).filter(Budget.month == _current_month()).all()}

    scale = max(1.0, days / 30.0)
    out: Dict[str, Tuple[float, float, float, float]] = {}
    for cat in set(budgets) | set(actuals):
        monthly_budget = budgets.get(cat, 0.0)
        window_budget = monthly_budget * scale
        actual = actuals.get(cat, 0.0)
        delta = actual - window_budget
        pct = 0.0 if window_budget <= 0 else min(100.0, round((actual / window_budget) * 100.0, 1))
        out[cat] = (round(monthly_budget, 2), round(actual, 2), round(delta, 2), pct)
    return out
