# Session Context - 14.03.2026 (Updated)

## Project State

### Git Information
- **Repository**: https://github.com/mishasya-dev/ofz-spread-analytics
- **Branch**: `feature/g-spread-yearyields-method`
- **Last Commits**: 
  - `d94fa7a` - fix: use session_state.bonds instead of undefined favorites
  - `104266a` - fix: use dicts instead of BondConfig for session_state.bonds
  - `7bab190` - fix: remove unsupported duration args from BondConfig
  - `5580b41` - fix: prevent favorites conflicts between tabs
  - `6e75ce9` - fix: prevent sync_from_url from overwriting widget values

### Database Status
- **Location**: `data/ofz_data.db`
- **Tables**: bonds, daily_ytm, intraday_ytm, spreads, ns_params, g_spreads, zcyc_cache, zcyc_empty_dates, cointegration_cache
- **Bonds Tracked**: 32+ (все ОФЗ с ZCYC данными)

## Recent Changes: State Persistence Fixes (14.03.2026)

### Проблемы решённые в этой сессии

#### 1. Слайдеры/radio не меняли значения
**Причина**: `sync_from_url()` загружал значения из URL и перезаписывал session_state при каждом rerun, затирая только что установленное значение.

**Решение**: Добавлена проверка `key not in st.session_state`:
```python
def sync_from_url():
    for key, type_conv in QUERY_KEYS.items():
        # Загружаем из URL ТОЛЬКО если нет в session_state
        if key in params and key not in st.session_state:
            st.session_state[key] = type_conv(value)
```

#### 2. Конфликты избранного между вкладками
**Причина**: Список избранного загружался из БД при каждом rerun, поэтому изменения в одной вкладке сразу влияли на другие.

**Решение**: Загрузка только один раз при старте сессии:
```python
if 'bonds' not in st.session_state or 'favorites_loaded' not in st.session_state:
    favorites = db.get_favorite_bonds_as_config()
    st.session_state.bonds = favorites
    st.session_state.favorites_loaded = True
```

Добавлена кнопка 🔄 для ручной синхронизации с БД.

### URL Query Parameters

Настройки сохраняются в URL через `st.query_params`:
- `period`, `spread_window`, `z_threshold`
- `g_spread_period`, `g_spread_window`, `g_spread_z_threshold`
- `candle_interval`, `candle_days`
- `b1`, `b2` (ISIN облигаций)

**Преимущества**:
- Синхронный API (нет async/callback проблем)
- Ссылки можно шарить
- Переживает F5

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    app.py (UI Layer)                         │
│  - Streamlit компоненты                                      │
│  - @st.cache_data декораторы                                 │
│  - session_state для настроек                                │
│  - query_params для URL                                      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                 services/ (Business Logic)                   │
│  - data_loader.py → загрузка данных с MOEX                   │
│  - state_manager.py → sync URL ↔ session_state               │
│  - g_spread_calculator.py → статистика G-spread              │
│  - spread_calculator.py → статистика spread                  │
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

## Key Files Reference

### Core Files
```
app.py                                   - UI + session_state + query_params
services/state_manager.py                - URL sync (sync_from_url, sync_to_url)
services/data_loader.py                  - Загрузка данных
api/moex_zcyc.py                         - ZCYC API (G-spread напрямую из MOEX)
components/bond_manager.py               - Управление избранным + refresh_favorites_from_db()
```

### State Management Flow
```
1. При старте (init_session_state):
   ├─ sync_from_url() → загружает URL params в session_state (только если ключа нет)
   ├─ load favorites from DB → session_state.bonds (только если favorites_loaded=False)
   └─ load_last_pair() → восстановление пары облигаций

2. При изменении виджета:
   ├─ Streamlit обновляет session_state[key]
   ├─ on_change callback логирует изменение
   └─ st.rerun()

3. После рендера (конец main()):
   └─ sync_to_url() → сохраняет session_state в URL
```

## Database Tables

| Table | Purpose | Records |
|-------|---------|---------|
| `bonds` | Облигации (is_favorite) | 32+ |
| `daily_ytm` | Дневные YTM | ~16000 |
| `intraday_ytm` | Внутридневные YTM | ~50000 |
| `zcyc_cache` | Кэш ZCYC (G-spread) | ~16000 |
| `zcyc_history_raw` | Raw ZCYC данные | ~16000 |
| `cointegration_cache` | Кэш коинтеграции | ~100 |

## Tests Status

**Passing**: 57 tests
- test_bonds.py ✅
- test_cointegration.py ✅
- test_database.py ✅
- и др.

**Removed** (устарели):
- test_state_manager.py (для browser-storage API)
- test_state_integration.py (для browser-storage API)

## Notes for Next Session

- Working directory: `/home/z/my-project/ofz-spread-analytics/`
- Run tests: `pytest tests/ -q`
- Start app: `streamlit run app.py`
- Database: `data/ofz_data.db`

### Completed Tasks
- [x] Fix sliders/radio not changing values
- [x] Fix favorites conflicts between tabs
- [x] Add refresh button for favorites sync
- [x] Remove browser-storage dependency
- [x] Implement URL-based state persistence

### Potential Future Tasks
- [ ] Add new tests for state_manager (URL-based)
- [ ] Add daily snapshot job for ZCYC data
- [ ] Merge feature branch to master

---
*Session saved: 2026-03-14 UTC*
