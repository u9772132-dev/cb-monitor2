from pathlib import Path
import sys
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cb_monitor import TPEX_CB_DAILY_API, TPEX_CB_ISSUE_API, _get_json, _api_rows

for name, url in [("CB每日行情", TPEX_CB_DAILY_API), ("CB發行/條件", TPEX_CB_ISSUE_API)]:
    print(f"\n[{name}] {url}")
    payload = _get_json(url)
    rows = _api_rows(payload)
    print(f"rows={len(rows)}")
    if rows:
        print("fields=", list(rows[0].keys()))
        print("sample=", json.dumps(rows[0], ensure_ascii=False, default=str)[:1200])
