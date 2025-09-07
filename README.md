# Budgie

💸 Budgie is your personal finance sidekick — a way to help you take control of your spending.

Connect a sandbox bank account securely through Plaid, instantly sync transactions, and explore them with smart filters by timeframe (30/60/90 days) and category.

📊 The app automatically builds personalized budgets from your past spending habits, compares them against your actual expenses, and visualizes your progress with clean animated charts.

🔁 With one click, you can refresh your data, rebuild budgets, and see suggestions to keep your finances on track — all in a sleek, modern interface that’s easy to use and fun to explore.

---

## ✨ Features
- 🔗 Secure Plaid Link sign-in (Sandbox)
- ⬇️ Transaction sync stored in **SQLite** with **SQLAlchemy**
- 🔎 Filterable Transactions page (30/60/90 days, multi-category chips)
- 📊 Budgets page with auto-generated budgets and progress bars
- 🔁 One-click **Sync Latest** and **Rebuild Budgets**

---

## 🚀 Quick Start

### 1. Clone & enter
```bash
git clone https://github.com/<your-username>/plaid-budget-agent.git
cd plaid-budget-agent
```
### 2. Enter virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux
```
### 3. Install necessary dependencies:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
### 4. Create a .env file in the project root:
```bash
PLAID_ENV=sandbox
PLAID_CLIENT_ID=your_client_id
PLAID_SECRET=your_sandbox_secret
PLAID_COUNTRY=US
```
### 5. Initialize database (in terminal):
```bash
python - <<'PY'
from app.db import init_db
init_db()
print("DB ready ✅")
PY
```
### 6. Run server!
```bash
export FLASK_APP=app.web        # macOS/Linux
python -m flask run
```
