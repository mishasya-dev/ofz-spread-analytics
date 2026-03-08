# Session Context - 08.03.2026

## Project State

### Git Information
- **Repository**: https://github.com/mishasya-dev/ofz-spread-analytics
- **Branch**: `experiments`
- **Last Commit**: `0487eac` - docs: add NS implementation for G-spread

### Database Status
- **Location**: `streamlit-app/data/ofz_data.db`
- **Tables**: bonds, daily_ytm, intraday_ytm, spreads
- **Bonds Tracked**: 16+

## Research Summary: G-spread Calculation

### Problem
Historical G-spread is NOT available directly from MOEX:
- ZSPREAD in history/yields = always None
- clcyield (YTM by KBD) = only current data
- yearyields (KBD points) = only current data

### Solution: Nelson-Siegel Model

```
G-spread = YTM_bond - YTM_KBD(duration)

YTM_KBD(t) = β₀ + β₁·f₁(t) + β₂·f₂(t)

where:
  f₁(t) = (1 - e^(-t/τ)) / (t/τ)
  f₂(t) = f₁(t) - e^(-t/τ)
```

### Data Sources

| Data | Endpoint | History |
|------|----------|---------|
| NS params (B1,B2,B3,T1) | `/history/engines/stock/zcyc` | ✅ 16528 records |
| Bond YTM, Duration | `/history/.../securities/{ISIN}` | ✅ 2+ years |
| yearyields (KBD points) | `/engines/stock/zcyc` | ❌ Current only |
| clcyield | `/engines/stock/zcyc/securities` | ❌ Current only |

### Algorithm

```python
# Step 1: Get historical NS params
ns_params = fetch_history_zcyc(date_from, date_to)
# Returns: {date: {B1, B2, B3, T1}}

# Step 2: Get bond data
bond_data = fetch_history_securities(isin, date_from, date_to)
# Returns: {date: {YIELDCLOSE, DURATION}}

# Step 3: Calibrate NS to current yearyields
beta0, beta1, beta2, tau = fit_ns_to_yearyields(yearyields, B1_hint)

# Step 4: Calculate G-spread
for date in dates:
    duration_years = bond_data[date]['DURATION'] / 365.25
    ytm_kbd = nelson_siegel(duration_years, beta0, beta1, beta2, tau)
    g_spread = bond_data[date]['YIELDCLOSE'] - ytm_kbd
```

### Accuracy

| Method | Error (bps) |
|--------|-------------|
| API clcyield (current) | 0 (exact) |
| NS calibrated to current yearyields | 2-20 |
| NS with daily yearyields snapshots | 0-2 |

### Recommendation for Mean-Reversion Strategy

1. **Current signals**: Use `clcyield` or `zspread` from API (exact)
2. **Historical analysis**: Use NS calibration (acceptable error)
3. **Production**: Save yearyields daily to DB for future accuracy

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    API Layer                                    │
│  api/moex_candles.py → только сырые свечи (OHLCV)              │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                 Business Logic                                  │
│  services/candle_processor_ytm_for_bonds.py                    │
│  → BondYTMProcessor: расчёт YTM из цен                         │
│  → GSpreadCalculator: расчёт G-spread через NS (NEW)           │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                  Service Layer                                  │
│  services/candle_service.py, data_loader.py                    │
│  → Кэширование, дозагрузка данных                              │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Database                                     │
│  core/db/ytm_repo.py → SQLite storage                          │
│  → NEW TABLE: yearyields_snapshots (для истории КБД)           │
└─────────────────────────────────────────────────────────────────┘
```

## Key Files Reference

### Core Files
```
api/moex_candles.py                      - Raw candle data only
services/candle_processor_ytm_for_bonds.py - BondYTMProcessor
components/charts.py                     - 4 functions (~650 lines)
app.py                                   - Main Streamlit application
```

### Active Tests
```
tests/test_bond_ytm_processor.py         - 14 tests for BondYTMProcessor
tests/test_spread_analytics_chart.py     - 15 tests for Z-Score chart
tests/test_hover_label.py                - 8 tests for hover labels
tests/test_cointegration.py              - 12 tests for cointegration
tests/test_sidebar_v030.py               - 36 tests for sidebar
tests/test_database.py                   - ~100 tests for DB
tests/test_candle_service.py             - 33 tests for candle service

Total: 398 tests
```

## Notes for Next Session

- Working directory: `/home/z/my-project/streamlit-app/`
- Run tests: `python -m pytest tests/ -v --ignore=tests/test_ui.py`
- Start app: `streamlit run app.py`
- Database: `data/ofz_data.db`

### TODO for G-spread Implementation

- [ ] Create `services/g_spread_calculator.py`
- [ ] Add `yearyields_snapshots` table to DB
- [ ] Create daily snapshot job for yearyields
- [ ] Add G-spread chart to UI
- [ ] Test historical G-spread accuracy

---
*Session saved: 2026-03-08 UTC*
