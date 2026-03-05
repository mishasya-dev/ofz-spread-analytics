# Session Context - 04.03.2026

## Project State

### Git Information
- **Repository**: https://github.com/mishasya-dev/ofz-spread-analytics
- **Branch**: `experiments`
- **Last Commit**: `026f2df` - refactor: remove unused code from charts.py

### Database Status
- **Location**: `streamlit-app/data/ofz_data.db`
- **Tables**: bonds, daily_ytm, intraday_ytm, spreads
- **Bonds Tracked**: 16

## Recent Changes (v0.6.0)

### Code Cleanup
Removed unused code from `components/charts.py`:
- Deleted `ChartBuilder` class and all its methods
- Deleted functions: `create_ytm_chart`, `create_spread_chart`, `create_signal_chart`, `create_backtest_chart`, `create_daily_ytm_chart`, `create_daily_spread_chart`, `calculate_future_range`
- File reduced from 1512 to ~650 lines (-57%)

### Kept Functions (used in app.py)
- `create_combined_ytm_chart` - Combined YTM (history + candles)
- `create_intraday_spread_chart` - Intraday spread chart
- `create_spread_analytics_chart` - Z-Score analysis panel
- `apply_zoom_range` - Zoom utility

### Tests Cleanup
Deleted obsolete test files:
- `tests/test_charts_v030.py`
- `tests/test_edge_cases.py`
- `tests/test_linked_zoom.py`

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

## Key Files Reference

### Core Files
```
components/charts.py    - 4 functions (~650 lines)
app.py                  - Main Streamlit application
components/sidebar.py   - Sidebar components
```

### Active Tests
```
tests/test_spread_analytics_chart.py  - 15 tests for Z-Score chart
tests/test_hover_label.py              - 8 tests for hover labels
tests/test_cointegration.py            - 12 tests for cointegration
tests/test_sidebar_v030.py             - 36 tests for sidebar
tests/test_database.py                 - ~100 tests for DB
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

## Notes for Next Session

- Working directory: `/home/z/my-project/streamlit-app/`
- Run tests: `python -m pytest tests/ -v`
- Start app: `streamlit run app.py`
- Database: `data/ofz_data.db`

---
*Session saved: 2026-03-04 UTC*
