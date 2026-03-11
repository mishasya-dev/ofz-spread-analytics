#!/usr/bin/env python3
"""Тест ZCYC caching"""

from datetime import date
from core.db import get_g_spread_repo
from api.moex_zcyc import get_zcyc_history

repo = get_g_spread_repo()
isin = "SU26247RMFS5"
start = date(2026, 3, 1)
end = date(2026, 3, 5)

print("Test 1: Load with use_cache=False...")
df = get_zcyc_history(start, end, isin=isin, use_cache=False)
print(f"  Loaded: {len(df)} records")

print("Test 2: save manually...")
saved = repo.save_zcyc(df)
print(f"  Saved: {saved} records")

print("Test 3: verify DB...")
count = repo.count_zcyc(isin)
print(f"  DB records for {count}")
print("=== Test complete ===")
