# Session Context - 28.02.2026

## Project State

### Git Information
- **Repository**: https://github.com/mishasya-dev/ofz-spread-analytics
- **Branch**: `feature/v0.3.0-unified-charts`
- **Last Commit**: `70c2bd2` - fix: НКД теперь рассчитывается на дату каждой свечи
- **Previous Commit**: `38977b8` - v0.3.0-tests: +77 новых тестов

### Test Results
```
Total: 287 tests
Passed: 275
Errors: 12 (Playwright UI - require browser setup)
```

### Database Status
- **Location**: `streamlit-app/data/ofz_data.db`
- **Tables**: bonds, daily_ytm, intraday_ytm, spreads
- **Bonds Tracked**: 16
- **Daily YTM Records**: ~821

## Work Completed This Session

### 1. Bug Fix: NKD Calculation

**Problem**: YTM calculated from candle prices diverged from MOEX historical data.

**Root Cause**: NKD (accrued interest) was fetched once from MOEX and used for all historical candles.

**Fix**:
- Added `calculate_accrued_interest_for_date()` method
- Added `_find_last_coupon_date()` helper
- NKD now calculated for each candle's date

**Files Modified**:
- `api/moex_candles.py`
- `core/ytm_calculator.py`

### 2. New Tests (+77)

Created 3 new test files:

| File | Tests | Coverage |
|------|-------|----------|
| `test_app_integration.py` | 30 | calculate_spread_stats, generate_signal, prepare_spread_dataframe |
| `test_edge_cases.py` | 25 | Empty data, NaN handling, single data point |
| `test_linked_zoom.py` | 22 | Zoom synchronization, independence |

### 3. Documentation

Created:
- `README.md` - Project documentation
- `CHANGELOG.md` - Version history

## Key Files Reference

### Modified Files
```
api/moex_candles.py     - NKD calculation per candle date
core/ytm_calculator.py  - New methods: calculate_accrued_interest_for_date(), _find_last_coupon_date()
```

### New Test Files
```
tests/test_app_integration.py
tests/test_edge_cases.py
tests/test_linked_zoom.py
```

### Documentation Files
```
README.md
CHANGELOG.md
worklog.md (updated)
SESSION_CONTEXT.md (this file)
```

## Technical Details

### NKD Calculation Formula
```
NKD = (Face Value × Coupon Rate / Frequency) × Days Since Last Coupon / Days Between Coupons
```

### Example NKD Values (OFZ 26207, coupon 8.15%)
| Date | NKD (rubles) |
|------|--------------|
| 2025-04-04 | 13.43 |
| 2025-08-01 | 40.08 |
| 2025-08-05 | 0.45 (after coupon payment) |

### Chart Color Scheme
| Element | History | Intraday |
|---------|---------|----------|
| Bond 1 | #1a5276 (dark blue) | #3498DB (bright blue) |
| Bond 2 | #922B21 (dark red) | #E74C3C (bright red) |
| Spread | #9B59B6 (purple) | - |

## Next Steps

### Recommended
1. Merge `feature/v0.3.0-unified-charts` into main
2. Add more bonds to tracking (currently 16)
3. Set up Playwright for UI tests

### Future Features (documented in FUTURE_FEATURES.md)
- Price alerts
- Export to Excel
- Backtesting module
- Telegram notifications

## Notes for Next Session

- Working directory: `/home/z/my-project/streamlit-app/`
- Run tests: `python -m pytest tests/ -v`
- Start app: `streamlit run app.py`
- Database: `data/ofz_data.db`

---
*Session saved: 2026-02-28 14:40 UTC*
