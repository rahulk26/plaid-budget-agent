from app.ingest import seed_sandbox_item
from app.db import init_db

if __name__ == "__main__":
    init_db()
    item = seed_sandbox_item()
    print(f"Seeded Sandbox Item. access_token endswith ...{item.access_token[-6:]}")
