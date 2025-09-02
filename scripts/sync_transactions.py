import argparse
from app.ingest import sync_transactions

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90, help="Lookback days")
    args = parser.parse_args()

    count = sync_transactions(days=args.days)
    print(f"Inserted {count} new transactions.")
