from pathlib import Path
import shutil
from datetime import datetime
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cb_monitor import load_market_data

DATA = ROOT / "data"
DAILY = DATA / "daily"
DAILY.mkdir(parents=True, exist_ok=True)

df = load_market_data()

today = datetime.now().strftime("%Y-%m-%d")
latest = DATA / "latest.csv"
previous = DATA / "previous_market.csv"
daily = DAILY / f"{today}.csv"

if latest.exists():
    shutil.copy2(latest, previous)

df.to_csv(latest, index=False, encoding="utf-8-sig")
df.to_csv(daily, index=False, encoding="utf-8-sig")

print(f"Saved {latest}")
print(f"Archived {daily}")
