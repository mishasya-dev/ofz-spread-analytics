# Session Context - 14.03.2026

## Project State

### Git Information
- **Repository**: https://github.com/mishasya-dev/ofz-spread-analytics
- **Branch**: `feature/g-spread-yearyields-method`
- **Last Commits**: 
  - `977d78b` - refactor: use data_loader.fetch_candle_data in cached wrapper
  - `e464c09` - refactor: use data_loader.fetch_historical_data in cached wrapper
  - `6253954` - refactor: use data_loader.fetch_trading_data in cached wrapper
  - `6bf3160` - refactor: remove duplicate update_database_full from app.py

### Database Status
- **Location**: `data/ofz_data.db`
- **Tables**: bonds, daily_ytm, intraday_ytm, spreads, ns_params, g_spreads, zcyc_cache, zcyc_empty_dates
- **Bonds Tracked**: 32+ (все ОФЗ с ZCYC данными)

## Recent Changes: Рефакторинг app.py (14.03.2026)

### Проблема
`app.py` содержал ~1595 строк с дублирующимся кодом, уже реализованным в `services/data_loader.py`.

### Решение
Удалены дубликаты, функции заменены на импорты из сервисов:

```python
# app.py - до рефакторинга
def update_database_full(bonds_list=None, progress_callback=None):
    # 78 строк кода...

# app.py - после рефакторинга  
from services.data_loader import update_database_full
```

### Результат

| Метрика | До | После |
|---------|-----|-------|
| Строк в app.py | 1595 | 1314 |
| Удалено дубликатов | - | ~280 строк (18%) |

### Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    app.py (UI Layer)                         │
│  - Streamlit компоненты                                      │
│  - @st.cache_data декораторы                                 │
│  - Обёртки над сервисами                                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                 services/ (Business Logic)                   │
│  - data_loader.py → загрузка данных с MOEX                   │
│  - g_spread_calculator.py → статистика G-spread              │
│  - spread_calculator.py → статистика spread                  │
│  - candle_service.py → работа со свечами                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    api/ (External APIs)                      │
│  - moex_client.py → единый клиент с rate limiting            │
│  - moex_zcyc.py → ZCYC данные (G-spread)                     │
│  - moex_history.py → исторические YTM                        │
│  - moex_candles.py → свечи                                   │
└─────────────────────────────────────────────────────────────┘
```

## Key Change: G-Spread Methodology (v0.4.0)

### G-spread из MOEX ZCYC API
**G-spread теперь берётся НАПРЯМУЮ из MOEX:**
- `trdyield` — рыночная YTM облигации
- `clcyield` — теоретическая КБД от MOEX
- `G-spread = trdyield - clcyield` (уже рассчитан MOEX!)
- **Ошибка: 0 bp** ✅

### Оптимизация загрузки ZCYC
```
Было:  N облигаций × D дней запросов
Стало: D дней запросов (все облигации вместе)
Сокращение: 5x
```

## Caching Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Streamlit Cache (@st.cache_data)                           │
│  - TTL: 60 сек (свечи), 300 сек (история), 3600 сек (NS)    │
│  - Инвалидация: вручную или при обновлении БД               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  SQLite Cache (zcyc_cache)                                  │
│  - Все облигации за все даты                                │
│  - Инкрементальное обновление                               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  MOEX API                                                    │
│  - Только недостающие данные                                │
│  - Параллельная загрузка (5 workers)                        │
└─────────────────────────────────────────────────────────────┘
```

## Database Tables

| Table | Purpose | Records |
|-------|---------|---------|
| `bonds` | Облигации (is_favorite) | 32+ |
| `daily_ytm` | Дневные YTM | ~16000 |
| `intraday_ytm` | Внутридневные YTM | ~50000 |
| `zcyc_cache` | Кэш ZCYC (G-spread) | ~16000 |
| `zcyc_empty_dates` | Праздники | ~50 |
| `ns_params` | Nelson-Siegel (deprecated) | ~500 |
| `g_spreads` | G-spread (deprecated) | — |

## Key Files Reference

### Core Files (после рефакторинга)
```
app.py                                   - 1314 строк (UI + кэширование)
services/data_loader.py                  - Загрузка данных (330 строк)
services/g_spread_calculator.py          - G-spread статистика
services/spread_calculator.py            - Spread статистика
api/moex_zcyc.py                         - ZCYC API (850 строк)
api/moex_client.py                       - MOEX клиент
core/db/g_spread_repo.py                 - ZCYC cache repo
components/charts.py                     - Chart builders
```

### Tests
```
tests/                                   - 446+ tests total
test_zcyc_optimization.py                - Тесты оптимизации ZCYC
test_app_integration.py                  - Интеграционные тесты
```

## Deprecated Code (DO NOT USE)

```python
# DEPRECATED - даёт ~90-100 bp ошибку:
from services.g_spread_calculator import nelson_siegel

# DEPRECATED - используйте services/data_loader.py:
# - _fetch_all_historical_data()
# - _fetch_all_candle_data()
```

## Notes for Next Session

- Working directory: `/home/z/my-project/ofz-spread-analytics/`
- Run tests: `pytest tests/ -q`
- Start app: `streamlit run app.py`
- Database: `data/ofz_data.db`

### Completed Tasks
- [x] Implement G-spread from MOEX ZCYC API (0 bp error)
- [x] Optimize ZCYC loading - load ALL bonds at once (5x speedup)
- [x] Add zcyc_cache table for caching ZCYC data
- [x] Add zcyc_empty_dates table for holidays
- [x] Fix duplicate element ID for G-spread charts
- [x] Add warning when same bond selected in both dropdowns
- [x] **Refactor app.py - remove ~280 lines of duplicate code**
- [x] **Use services/data_loader.py for data loading**

### Potential Future Tasks
- [ ] Add daily snapshot job for ZCYC data
- [ ] Implement G-spread alerts/notifications
- [ ] Merge feature branch to master
- [ ] Further split sidebar into components/sidebar.py

---
*Session saved: 2026-03-14 UTC*
