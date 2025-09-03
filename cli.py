import argparse
from tabulate import tabulate
from app.budget import spend_by_category, generate_budgets, save_budgets, compare_to_budget
from app.db import init_db

def cmd_spend(args):
    s = spend_by_category(days=args.days)
    rows = [(k, round(v, 2)) for k, v in s.by_category.items()]
    print(tabulate(rows, headers=["Category", f"Spend ({args.days}d)"]))

def cmd_budget(args):
    budgets = generate_budgets(days=args.days, cushion=args.cushion)
    save_budgets(budgets)
    rows = [(k, v) for k, v in budgets.items()]
    print(tabulate(rows, headers=["Category", "Monthly Budget"]))

def cmd_status(args):
    cmp = compare_to_budget()
    rows = [(k, b, a, d) for k, (b, a, d) in cmp.items()]
    print(tabulate(rows, headers=["Category", "Budget", "Actual", "Δ (A-B)"]))

if __name__ == "__main__":
    init_db()
    p = argparse.ArgumentParser(prog="plaid-budget-agent")
    sub = p.add_subparsers(required=True)

    sp = sub.add_parser("spend"); sp.set_defaults(func=cmd_spend)
    sp.add_argument("--days", type=int, default=90)

    bg = sub.add_parser("budget"); bg.set_defaults(func=cmd_budget)
    bg.add_argument("--days", type=int, default=90)
    bg.add_argument("--cushion", type=float, default=0.10)

    st = sub.add_parser("status"); st.set_defaults(func=cmd_status)

    args = p.parse_args()
    args.func(args)
