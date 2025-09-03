# app/agent_loop.py
from __future__ import annotations
from typing import List
from .budget import compare_to_budget

def propose_actions() -> List[str]:
    """
    Simple rule-based 'agent' that reads this month's (budget, actual, delta)
    and proposes actions. Positive delta = over budget.
    """
    cmp = compare_to_budget()
    actions: List[str] = []

    for cat, (budget, actual, delta) in sorted(cmp.items(), key=lambda kv: kv[1][2], reverse=True):
        if budget <= 0 and actual <= 0:
            continue

        if delta > 0: 
            pct = (delta / budget * 100) if budget > 0 else 0.0
            move_amt = round(min(delta, max(0.0, 0.5 * budget)), 2) if budget > 0 else round(delta, 2)
            actions.append(
                f"Alert: {cat} is over budget by ${delta:.2f} (~{pct:.0f}%). "
                f"Suggest pausing discretionary spend and moving ${move_amt:.2f} from lower-utilized categories."
            )
        elif budget > 0 and actual < 0.7 * budget:  
            reallocate = round(0.2 * budget, 2)
            actions.append(
                f"Opportunity: {cat} spend is well below budget (actual ${actual:.2f} vs ${budget:.2f}). "
                f"Consider reallocating ${reallocate:.2f} to Savings or Debt Repayment."
            )

    if not actions:
        actions.append("All categories within thresholds. Maintain course and add 5% to Savings next month.")
    return actions
