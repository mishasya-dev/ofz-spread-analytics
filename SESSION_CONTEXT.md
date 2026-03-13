# Session Context - 13.03.2026

## Project State

### Git Information
- **Repository**: https://github.com/mishasya-dev/ofz-spread-analytics
- **Branch**: `feature/g-spread-yearyields-method`
- **Last Commit**: `5921830` - perf: optimize ZCYC loading - load all bonds at once

### Database Status
- **Location**: `data/ofz_data.db`
- **Tables**: bonds, daily_ytm, intraday_ytm, spreads, ns_params, g_spreads, zcyc_cache, zcyc_empty_dates
- **Bonds Tracked**: 32+ (все ОФЗ с ZCYC данными)

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
Returns: securities data with trdyield, clcyield, crtduration (32 облигации!)
```

### Key Functions
```python
from api.moex_zcyc import get_zcyc_history_parallel
from core.db import get_g_spread_repo

repo = get_g_spread_repo()

# Загрузка ВСЕХ облигаций за период (оптимизировано!)
df = get_zcyc_history_parallel(
    start_date=start_date,
    end_date=end_date,
    isin=None,  # None = все облигации!
    use_cache=True,
    save_callback=repo.save_zcyc,
    max_workers=5
)

# Фильтрация по конкретному ISIN (из кэша, мгновенно)
df_filtered = get_zcyc_history_parallel(
    start_date=start_date,
    end_date=end_date,
    isin="SU26224RMFS4",  # Конкретная облигация
    use_cache=True
)
```

## 🚀 Optimizations (13.03.2026)

### ZCYC Loading Optimization
**Проблема:** ZCYC загружался отдельно для каждой облигации = N × D запросов

**Решение:** MOEX API возвращает ВСЕ 32 облигации за один запрос!
```
Было:  N облигаций × D дней запросов
Стало: D дней запросов (все облигации вместе)
```

**Изменения в `api/moex_zcyc.py`:**
1. Проверяем кэш БЕЗ фильтрации по ISIN (получаем все даты)
2. Загружаем ВСЕ облигации с MOEX (не фильтруем при загрузке)
3. Сохраняем ВСЕ облигации в БД (`zcyc_cache`)
4. Фильтруем по ISIN только при возврате результата

**Результат:**
| Метрика | До | После |
|---------|-----|-------|
| Запросов для 5 облигаций, 250 дней | 1250 | 250 |
| Сокращение | - | **5x** |

## Weekend/Holiday Handling

```
┌─────────────────────────────────────────────────────────────┐
│  Генерация trading_days                                      │
├─────────────────────────────────────────────────────────────┤
│  - Только пн-пт (сб/вс исключаются)                         │
│  - Праздничные будние дни включаются                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Загрузка с MOEX                                             │
├─────────────────────────────────────────────────────────────┤
│  - Рабочий день → данные в zcyc_cache                        │
│  - Праздник → пустой ответ → дата в zcyc_empty_dates        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Повторная загрузка                                          │
├─────────────────────────────────────────────────────────────┤
│  - Проверяем zcyc_empty_dates → исключаем праздники         │
│  - Берём данные из zcyc_cache                               │
└─────────────────────────────────────────────────────────────┘
```

## Caching Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Первый запрос периода                                      │
├─────────────────────────────────────────────────────────────┤
│  1. Проверка zcyc_empty_dates → исключаем праздники         │
│  2. Проверка zcyc_cache (все даты, без ISIN фильтра)        │
│  3. Дозагрузка только недостающих дней с MOEX               │
│  4. Сохранение ВСЕХ облигаций в zcyc_cache                  │
│  5. Сохранение праздников в zcyc_empty_dates                │
│  6. Кэширование результата в Streamlit                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Повторный запрос (другой ISIN, те же даты)                 │
├─────────────────────────────────────────────────────────────┤
│  1. Проверка zcyc_cache → ВСЕ даты уже есть!                │
│  2. Фильтрация по ISIN локально                              │
│  3. Мгновенный возврат (0.00 сек)                           │
└─────────────────────────────────────────────────────────────┘
```

## Database Tables

| Table | Purpose |
|-------|---------|
| `zcyc_cache` | Кэш ZCYC данных (G-spread для ВСЕХ облигаций) |
| `zcyc_empty_dates` | Праздники (нет торгов) |
| `g_spreads` | Рассчитанные G-spread (deprecated, используем zcyc_cache) |
| `ns_params` | Параметры Nelson-Siegel (deprecated) |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer                                 │
│  api/moex_zcyc.py → ZCYC данные (ВСЕ облигации сразу)       │
│  api/moex_client.py → Единый клиент с rate limiting         │
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
api/moex_zcyc.py                         - ZCYC API (оптимизировано: все облигации)
api/moex_client.py                       - Единый MOEX клиент с rate limiting
core/db/g_spread_repo.py                 - ZCYC cache + empty dates
services/g_spread_calculator.py          - G-spread stats & signals
components/charts.py                     - Chart builders
app.py                                   - Main Streamlit application
```

### Tests
```
tests/test_zcyc_optimization.py          - Тесты оптимизации ZCYC
test_zcyc.py                             - 7 tests for ZCYC functionality
tests/                                   - 400+ tests total
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

- Working directory: `/home/z/my-project/`
- Run tests: `python tests/test_zcyc_optimization.py`
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
- [x] **Optimize ZCYC loading - load ALL bonds at once (5x speedup)**
- [x] **Fix duplicate element ID for G-spread charts**
- [x] **Add warning when same bond selected in both dropdowns**

### Potential Future Tasks
- [ ] Add daily snapshot job for ZCYC data
- [ ] Implement G-spread alerts/notifications
- [ ] Add more bond pairs for analysis
- [ ] Create API documentation with OpenAPI
- [ ] Merge feature branch to master

---
*Session saved: 2026-03-13 UTC*
