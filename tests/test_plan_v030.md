# План тестов для v0.3.0

## Обзор

Новые компоненты и функции требуют дополнительных тестов:

| Компонент | Новые функции | Приоритет |
|-----------|---------------|-----------|
| `components/sidebar.py` | 5 новых функций | Высокий |
| `components/charts.py` | 4 новых графика | Высокий |
| `models/bond.py` | Bond, BondPair dataclasses | Средний |
| `services/candle_service.py` | CandleService | Средний |
| `core/db/` | 3 репозитория | Низкий (уже есть test_bonds.py) |

---

## 1. test_charts_v030.py — Новые графики

### TestCalculateFutureRange
```python
def test_future_range_empty_index():
    """Пустой индекс возвращает (None, None)"""
    
def test_future_range_single_point():
    """Одна точка — future_percent от 0"""
    
def test_future_range_normal():
    """Нормальный диапазон с 15% запасом"""
    # 100 дней → 115 дней на оси X
    
def test_future_range_custom_percent():
    """Кастомный процент будущего"""
    # future_percent=0.2 → 20% запас
```

### TestDailyYtmChart
```python
def test_chart_with_empty_dataframes():
    """Пустые DataFrame возвращают пустой Figure"""
    
def test_chart_with_single_bond():
    """График с одной облигацией"""
    
def test_chart_with_two_bonds():
    """График с двумя облигациями"""
    
def test_chart_colors_bond1_dark_blue():
    """Облигация 1 — тёмно-синий цвет"""
    
def test_chart_colors_bond2_dark_red():
    """Облигация 2 — тёмно-красный цвет"""
    
def test_chart_has_legend():
    """График имеет легенду"""
    
def test_chart_hovermode_unified():
    """Hovermode = 'x unified'"""
```

### TestDailySpreadChart
```python
def test_spread_chart_empty_dataframe():
    """Пустой DataFrame"""
    
def test_spread_chart_with_stats():
    """График с перцентилями P25, P75, среднее"""
    
def test_spread_chart_stats_none():
    """График без статистики"""
    
def test_spread_chart_fill_to_zero():
    """Заполнение до нуля (fill='tozeroy')"""
```

### TestCombinedYtmChart
```python
def test_combined_with_history_only():
    """Только исторические данные"""
    
def test_combined_with_intraday_only():
    """Только свечи"""
    
def test_combined_with_both():
    """История + свечи (склеенный график)"""
    
def test_combined_colors_intraday_brighter():
    """Intraday цвета ярче исторических"""
    # BOND1_COLORS["intraday"] ярче BOND1_COLORS["history"]
```

### TestIntradaySpreadChart
```python
def test_intraday_with_daily_stats():
    """Перцентили от дневных данных (референс)"""
    
def test_intraday_empty_dataframe():
    """Пустой DataFrame"""
    
def test_intraday_percentile_lines():
    """Линии P10, P25, P75, P90, среднее"""
```

---

## 2. test_sidebar_v030.py — Обновлённый sidebar

### TestRenderPeriodSelector
```python
def test_period_default_value():
    """Значение по умолчанию из session_state.period"""
    
def test_period_returns_int():
    """Возвращает целое число дней"""
    
def test_period_range_30_to_730():
    """Диапазон 30-730 дней"""
    
def test_period_updates_session_state():
    """Обновляет st.session_state.period"""
```

### TestRenderCandleIntervalSelector
```python
def test_interval_options():
    """Опции: '1', '10', '60'"""
    
def test_interval_format_func():
    """Форматирование: '1 минута', '10 минут', '1 час'"""
    
def test_interval_shows_max_period():
    """Показывает макс. период для интервала"""
    # 1 мин → 3 дня, 10 мин → 30 дней, 60 мин → 365 дней
    
def test_interval_updates_session_state():
    """Обновляет st.session_state.candle_interval"""
```

### TestRenderAutoRefresh
```python
def test_toggle_off_by_default():
    """По умолчанию выключен"""
    
def test_toggle_shows_slider_when_on():
    """При включении показывает слайдер интервала"""
    
def test_slider_range_30_to_300():
    """Диапазон слайдера 30-300 сек"""
    
def test_shows_last_update_time():
    """Показывает время последнего обновления"""
```

### TestRenderDbPanel
```python
def test_panel_shows_stats():
    """Показывает статистику БД в expander"""
    
def test_update_button_sets_session_state():
    """Кнопка обновления устанавливает updating_db=True"""
    
def test_progress_callback_called():
    """Callback прогресса вызывается"""
    
def test_success_message_on_complete():
    """Сообщение об успехе после завершения"""
    
def test_error_message_on_exception():
    """Сообщение об ошибке при исключении"""
```

### TestRenderCacheClear
```python
def test_clear_cache_button():
    """Кнопка очистки кэша"""
    
def test_clear_calls_cache_data_clear():
    """Вызывает st.cache_data.clear()"""
    
def test_clear_calls_rerun():
    """Вызывает st.rerun()"""
```

---

## 3. test_models_bond.py — Модель Bond

### TestBondDataclass
```python
def test_bond_required_isin():
    """ISIN — обязательное поле"""
    
def test_bond_defaults():
    """Значения по умолчанию"""
    # is_favorite=False, face_value=1000, coupon_frequency=2
    
def test_bond_from_dict():
    """Создание из словаря"""
    
def test_bond_from_db_row():
    """Создание из строки БД (sqlite3.Row)"""
    
def test_bond_from_config():
    """Создание из BondConfig (config.py)"""
    
def test_bond_to_dict():
    """Преобразование в словарь"""
    
def test_bond_to_db_dict():
    """Преобразование для сохранения в БД"""
    # day_count_convention → day_count
```

### TestBondMethods
```python
def test_get_display_name_with_name():
    """display_name = name"""
    
def test_get_display_name_fallback_to_isin():
    """display_name = isin если name пустой"""
    
def test_get_years_to_maturity_valid():
    """Расчёт лет до погашения"""
    
def test_get_years_to_maturity_invalid_date():
    """Некорректная дата возвращает 0"""
    
def test_get_years_to_maturity_empty():
    """Пустая дата возвращает 0"""
```

### TestBondFormatLabel
```python
def test_format_label_with_all_data():
    """Полная метка: Name | YTM: X.XX% | Дюр: X.Xг. | X.Xг. до погашения"""
    
def test_format_label_without_ytm():
    """Без YTM"""
    
def test_format_label_without_duration():
    """Без дюрации"""
    
def test_format_label_uses_instance_ytm():
    """Использует last_ytm если ytm=None"""
```

### TestBondPairDataclass
```python
def test_bond_pair_creation():
    """Создание пары облигаций"""
    
def test_get_spread_bp():
    """Расчёт спреда в базисных пунктах"""
    
def test_get_spread_bp_none_ytm():
    """None если YTM нет"""
    
def test_get_label():
    """Метка пары: Bond1 / Bond2"""
```

---

## 4. test_candle_service.py — CandleService

### TestCandleServiceInit
```python
def test_service_initialization():
    """Инициализация с fetcher и db"""
    
def test_service_default_interval():
    """Интервал по умолчанию = 60 мин"""
```

### TestCandleServiceGetCandles
```python
def test_get_candles_returns_dataframe():
    """Возвращает DataFrame"""
    
def test_get_candles_empty_isin():
    """Пустой ISIN возвращает пустой DataFrame"""
    
def test_get_candles_invalid_days():
    """Некорректное количество дней"""
    
def test_get_candles_with_ytm_calculation():
    """YTM рассчитывается для свечей"""
    
def test_get_candles_uses_cache():
    """Использует кэширование"""
```

### TestCandleServiceGetYtmFromCandles
```python
def test_calculate_ytm_from_price():
    """Расчёт YTM из цены свечи"""
    
def test_ytm_with_settlement_date():
    """YTM с датой расчёта (settlement_date)"""
    
def test_ytm_handles_missing_coupon_rate():
    """Обработка отсутствия купона"""
```

### TestCandleServiceDbIntegration
```python
def test_save_candles_to_db():
    """Сохранение свечей в БД"""
    
def test_load_candles_from_db():
    """Загрузка свечей из БД"""
    
def test_merge_candles_new_and_db():
    """Объединение новых свечей с БД"""
```

---

## 5. test_db_repositories.py — Репозитории БД

### TestBondsRepository
```python
def test_save_bond():
    """Сохранение облигации"""
    
def test_load_bond():
    """Загрузка облигации"""
    
def test_get_favorites():
    """Получение избранных"""
    
def test_set_favorite():
    """Установка is_favorite"""
    
def test_update_market_data():
    """Обновление рыночных данных"""
```

### TestYtmRepository
```python
def test_save_daily_ytm():
    """Сохранение дневных YTM"""
    
def test_load_daily_ytm():
    """Загрузка дневных YTM"""
    
def test_save_intraday_ytm():
    """Сохранение intraday YTM"""
    
def test_load_intraday_ytm():
    """Загрузка intraday YTM"""
    
def test_get_last_ytm_date():
    """Получение последней даты YTM"""
```

### TestSpreadsRepository
```python
def test_save_spread():
    """Сохранение спреда"""
    
def test_load_spreads():
    """Загрузка спредов"""
    
def test_get_spread_stats():
    """Получение статистики спреда"""
```

---

## 6. test_app_v030.py — Интеграционные тесты

### TestPrepareSpreadDataframe
```python
def test_prepare_daily_spread():
    """Подготовка DataFrame дневного спреда"""
    
def test_prepare_intraday_spread():
    """Подготовка DataFrame intraday спреда"""
    
def test_prepare_empty_dataframe():
    """Пустой результат при пустых входных данных"""
    
def test_spread_calculation_bp():
    """Спред в базисных пунктах: (ytm1 - ytm2) * 100"""
```

### TestCalculateSpreadStats
```python
def test_stats_with_data():
    """Статистика с данными: mean, median, std, p10, p25, p75, p90"""
    
def test_stats_empty_series():
    """Пустая статистика при пустом Series"""
    
def test_stats_current_value():
    """Текущее значение = последнее в Series"""
```

### TestUpdateDatabaseFull
```python
def test_update_with_progress_callback():
    """Обновление с callback прогресса"""
    
def test_update_saves_daily_ytm():
    """Сохраняет дневные YTM"""
    
def test_update_saves_intraday_ytm():
    """Сохраняет intraday YTM"""
    
def test_update_handles_errors():
    """Обработка ошибок при обновлении"""
    
def test_update_returns_stats():
    """Возвращает статистику: daily_ytm_saved, intraday_ytm_saved, errors"""
```

### TestFetchHistoricalDataCached
```python
def test_fetch_from_db_if_fresh():
    """Загрузка из БД если данные свежие (< 1 дня)"""
    
def test_fetch_from_moex_if_stale():
    """Загрузка с MOEX если данные устарели"""
    
def test_fetch_saves_to_db():
    """Сохранение в БД после загрузки"""
    
def test_fetch_returns_dataframe():
    """Возвращает DataFrame с индексом date"""
```

### TestFetchCandleDataCached
```python
def test_fetch_candles_from_db():
    """Загрузка свечей из БД"""
    
def test_fetch_candles_from_moex():
    """Загрузка свечей с MOEX"""
    
def test_fetch_calculates_ytm():
    """Расчёт YTM для свечей"""
    
def test_fetch_uses_bond_config():
    """Использование bond_config для расчёта YTM"""
```

---

## Порядок реализации

1. **Фаза 1 (высокий приоритет)**
   - `test_charts_v030.py` — новые графики
   - `test_sidebar_v030.py` — обновлённый sidebar

2. **Фаза 2 (средний приоритет)**
   - `test_models_bond.py` — модель Bond
   - `test_candle_service.py` — CandleService

3. **Фаза 3 (низкий приоритет)**
   - `test_db_repositories.py` — репозитории
   - `test_app_v030.py` — интеграционные

---

## Итого

| Файл тестов | Новых тестов | Приоритет |
|-------------|--------------|-----------|
| test_charts_v030.py | ~25 | Высокий |
| test_sidebar_v030.py | ~20 | Высокий |
| test_models_bond.py | ~20 | Средний |
| test_candle_service.py | ~15 | Средний |
| test_db_repositories.py | ~15 | Низкий |
| test_app_v030.py | ~20 | Низкий |
| **Всего** | **~115** | |

---

*План создан: 2026-02-28*
