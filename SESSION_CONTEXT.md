# Session Context - 06.03.2026

## Project State

### Git Information
- **Repository**: https://github.com/mishasya-dev/ofz-spread-analytics
- **Branch**: `experiments`
- **Last Commit**: `3e7c610` - docs: update CHANGELOG for v0.7.0

### Database Status
- **Location**: `streamlit-app/data/ofz_data.db`
- **Tables**: bonds, daily_ytm, intraday_ytm, spreads
- **Bonds Tracked**: 16+

## Recent Changes (v0.7.0)

### Architecture Refactor
**YTM Calculation Separation**:
- `api/moex_candles.py` → только сырые свечи (OHLCV)
- `services/candle_processor_ytm_for_bonds.py` → новый `BondYTMProcessor`
- Single Responsibility Principle: API fetches, service calculates

### Cache Optimization
**Decoupled from period slider**:
- `_fetch_all_historical_data(isin)` → кэш по ISIN (730 дней)
- `fetch_historical_data_cached(isin, days)` → фильтрация без cache miss
- Аналогично для свечей: кэш по (ISIN, interval)

### BondYTMProcessor Service
```python
# Add YTM to candles DataFrame
df_with_ytm = processor.add_ytm_to_candles(raw_candles_df, bond_config)

# Calculate YTM for single price
ytm = processor.calculate_ytm_for_price(
    price=95.5,
    bond_config=bond_config,
    trade_date=date(2025, 3, 6)
)
```

## Current Chart Layout (3 Charts)

```
📊 Chart 1: Spread Analytics (Z-Score)
  - Panel 1: YTM both bonds (daily)
  - Panel 2: Spread + Rolling Mean + ±Zσ

📊 Chart 2: Combined YTM (history + candles)
  - Bond 1 & 2 yields with volume bars

📊 Chart 3: Intraday Spread
  - Intraday spread with daily percentiles
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer                            │
│  api/moex_candles.py → только сырые свечи (OHLCV)      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                 Business Logic                          │
│  services/candle_processor_ytm_for_bonds.py            │
│  → BondYTMProcessor: расчёт YTM из цен                 │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  Service Layer                          │
│  services/candle_service.py, data_loader.py            │
│  → Кэширование, дозагрузка данных                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    Database                             │
│  core/db/ytm_repo.py → SQLite storage                  │
└─────────────────────────────────────────────────────────┘
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

## Technical Details

### Z-Score Calculation
```
Z-Score = (spread - rolling_mean) / rolling_std

Signals:
- Z > +threshold → SELL (spread too high)
- Z < -threshold → BUY (spread too low)
- Otherwise → NEUTRAL
```

### Chart Configuration (Sidebar)
| Parameter | Range | Default |
|-----------|-------|---------|
| Rolling Window | 5-90 days | 30 |
| Z-Score Threshold | 1.0-3.0σ | 2.0 |

### Caching Behavior
| Scenario | Before | After |
|----------|--------|-------|
| Period 365 → 180 days | Cache miss, DB query | Filter from cache |
| Period 180 → 365 days | Cache miss, DB query | Filter from cache |
| Change bond pair | Load new ISIN | Load new ISIN |

## Notes for Next Session

- Working directory: `/home/z/my-project/streamlit-app/`
- Run tests: `python -m pytest tests/ -v --ignore=tests/test_ui.py`
- Start app: `streamlit run app.py`
- Database: `data/ofz_data.db`

---
*Session saved: 2026-03-06 UTC*
