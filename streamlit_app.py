# streamlit_app.py
import streamlit as st
import pandas as pd

from app.db import init_db, SessionLocal
from app.models import Transaction, Budget
from app.budget import spend_by_category, generate_budgets, save_budgets, compare_to_budget
from app.agent_loop import propose_actions

st.set_page_config(page_title="Plaid Budget Agent", layout="wide")
st.title("💸 Plaid Budget Agent (Sandbox)")

init_db()

st.subheader("Spend by Category (last 90 days → monthly estimate)")
summary = spend_by_category(days=90)
monthly_scaled = {k: round(v * (30/90), 2) for k, v in summary.by_category.items()}
spend_df = pd.DataFrame(
    [{"Category": k, "Monthly Spend (est.)": v} for k, v in monthly_scaled.items()]
).sort_values("Monthly Spend (est.)", ascending=False)
st.dataframe(spend_df, use_container_width=True, hide_index=True)

st.subheader("Budgets (current month)")
left, right = st.columns([1, 1])

with left:
    if st.button("Generate & Save Budgets (from 90d history)"):
        budgets = generate_budgets(days=90, cushion=0.10)
        save_budgets(budgets)
        st.success("Budgets generated & saved for this month.")

with right:
    cmp = compare_to_budget()
    budget_rows = [
        {"Category": c, "Budget": b, "Actual": a, "Δ (Actual - Budget)": d}
        for c, (b, a, d) in sorted(cmp.items())
    ]
    budget_df = pd.DataFrame(budget_rows)
    st.dataframe(budget_df, use_container_width=True, hide_index=True)

st.subheader("Agent Proposals")
actions = propose_actions()
for i, a in enumerate(actions, 1):
    st.write(f"{i}. {a}")

st.caption("Tip: Re-run your sync script periodically to refresh data: `python -m scripts.sync_transactions --days 90`.")