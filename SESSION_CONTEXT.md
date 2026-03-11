# Session Context - 11.03.2026

## Project State

### Git Information
- **Repository**: https://github.com/mishasya-dev/ofz-spread-analytics
- **Branch**: `feature/g-spread-yearyields-method`
- **Last Commit**: `f30c2e2` - docs: update README for v0.8.0, clean up tests

### Database Status
- **Location**: `streamlit-app/data/ofz_data.db`
- **Tables**: bonds, daily_ytm, intraday_ytm, spreads, ns_params, g_spreads, zcyc_cache, zcyc_empty_dates
- **Bonds Tracked**: 16+

## Key Change: G-Spread Methodology (v0.8.0)

### Problem
- Nelson-Siegel formula: ~90-100 bp ошибка
- Yearyields интерполяция: ~10-15 bp ошибка

### Solution: Direct MOEX ZCYC API
**G-spread теперь берётся НАПРЯМУЮ из MOEX ZCYC API:**
- `trdyield` — рыночная YTM облигации
- `clcyield` — теоретическая КБД от MOEX
- `G-spread = trdyield - clcyield` (уже рассчитан MOEX!)
- **Ошибка: 0 bp** ✅

### API Endpoints
```
GET /engines/stock/zcyc.json?date=YYYY-MM-DD
Returns: securities data with trdyield, clcyield, crtduration
```

### Key Functions
```python
from api.moex_zcyc import get_zcyc_data_for_date, get_zcyc_history_parallel

# G-spread за дату
df = get_zcyc_data_for_date(date(2026, 3, 10))

# История с кэшированием
df = get_zcyc_history_parallel(start_date, end_date, isin="SU26247RMFS5")
```

## Caching Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Первый запрос периода                                      │
├─────────────────────────────────────────────────────────────┤
│  1. Проверка Streamlit кэша → пусто                         │
│  2. Проверка БД → возврат имеющихся записей                 │
│  3. Дозагрузка только недостающих дней с MOEX               │
│  4. Сохранение праздников в zcyc_empty_dates                │
│  5. Кэширование результата в Streamlit                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Повторный запрос (смена слайдера, те же даты)              │
├─────────────────────────────────────────────────────────────┤
│  1. Проверка Streamlit кэша → есть!                         │
│  2. Мгновенный возврат (без БД и MOEX)                      │
└─────────────────────────────────────────────────────────────┘
```

## Database Tables

| Table | Purpose |
|-------|---------|
| `zcyc_cache` | Кэш ZCYC данных (G-spread) |
| `zcyc_empty_dates` | Праздники (нет торгов) - NEW! |
| `g_spreads` | Рассчитанные G-spread |
| `ns_params` | Параметры Nelson-Siegel (deprecated) |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer                                 │
│  api/moex_zcyc.py → ZCYC данные (G-spread от MOEX)          │
│  api/moex_candles.py → только сырые свечи (OHLCV)           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                 Business Logic                               │
│  services/g_spread_calculator.py → статистика и сигналы     │
│  services/candle_processor_ytm_for_bonds.py → YTM расчёт    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                  Database Layer                              │
│  core/db/g_spread_repo.py → ZCYC кэш + пустые даты          │
│  core/db/ytm_repo.py → YTM история                          │
└─────────────────────────────────────────────────────────────┘
```

## Key Files Reference

### Core Files
```
api/moex_zcyc.py                         - ZCYC API (G-spread from MOEX)
core/db/g_spread_repo.py                 - ZCYC cache + empty dates
services/g_spread_calculator.py          - G-spread stats & signals
components/charts.py                     - Chart builders
app.py                                   - Main Streamlit application
```

### Tests
```
test_zcyc.py                             - 7 tests for ZCYC functionality
tests/                                   - 398 tests total
```

## Deprecated Code (DO NOT USE)

```python
# DEPRECATED - даёт ~90-100 bp ошибку:
from services.g_spread_calculator import nelson_siegel

# DEPRECATED - заменено на get_zcyc_data_for_date():
from api.moex_zcyc import get_yearyields_for_date

# DEPRECATED - заменено на get_zcyc_history_parallel():
from services.g_spread_calculator import calculate_g_spread_history
```

## Notes for Next Session

- Working directory: `/home/z/my-project/streamlit-app/`
- Run tests: `python3 test_zcyc.py`
- Start app: `streamlit run app.py`
- Database: `data/ofz_data.db`

### Completed Tasks
- [x] Implement get_zcyc_data_for_date() - exact G-spread from MOEX
- [x] Implement get_zcyc_history_parallel() - parallel loading with 5 workers
- [x] Add zcyc_cache table for caching ZCYC data
- [x] Add zcyc_empty_dates table for holidays
- [x] Add Streamlit cache for ZCYC (no TTL - historical data immutable)
- [x] Update README with new architecture
- [x] Create comprehensive test_zcyc.py

### Potential Future Tasks
- [ ] Add daily snapshot job for ZCYC data
- [ ] Implement G-spread alerts/notifications
- [ ] Add more bond pairs for analysis
- [ ] Create API documentation with OpenAPI

---
*Session saved: 2026-03-11 UTC*
