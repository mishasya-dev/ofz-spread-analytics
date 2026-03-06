# API модуля cointegration.py

## Обзор

Модуль предоставляет анализ коинтеграции для пар облигаций ОФЗ.
Основной потребитель: `CointegrationService` → БД → UI

---

## Входные данные

### Источник данных
```
БД (daily_ytm таблица)
    ↓
DatabaseManager.load_daily_ytm(isin, start_date)
    ↓
pd.Series(index=dates, values=ytm)
```

### Формат входных данных
```python
ytm1: pd.Series  # YTM первой облигации
# index: DatetimeIndex (даты торгов)
# values: float (YTM в долях, напр. 0.1435 = 14.35%)

ytm2: pd.Series  # YTM второй облигации
# Аналогичная структура
```

### Параметры
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `significance_level` | float | 0.05 | Уровень значимости для тестов |
| `trend` | str | 'c' | Тип тренда для Engle-Granger |
| `bidirectional` | bool | True | Проверять оба направления |
| `fill_method` | str | 'drop' | Метод заполнения пропусков |

---

## Выходные данные

### Структура результата `analyze_pair()`

```python
{
    # Метаданные
    'n_observations': int,          # Количество наблюдений
    
    # Engle-Granger тест
    'engle_granger': {
        'test': 'Engle-Granger',
        'coint_statistic': float,   # Статистика теста
        'pvalue': float,            # P-value (ключевой показатель!)
        'critical_values': dict,    # Критические значения
        'is_cointegrated': bool,    # Коинтегрированы ли?
        'ytm1_adf_pvalue': float,   # P-value ADF для YTM1
        'ytm2_adf_pvalue': float,   # P-value ADF для YTM2
        'ytm1_stationary': bool,    # Стационарен ли YTM1?
        'ytm2_stationary': bool,    # Стационарен ли YTM2?
        'both_nonstationary': bool, # Оба нестационарны? (обязательно!)
        'direction': str,           # Направление теста
        'interpretation': str,      # Текстовая интерпретация
    },
    
    # ADF тесты отдельно
    'adf_ytm1': {...},
    'adf_ytm2': {...},
    'adf_spread': {...},
    
    # KPSS тест
    'kpss_spread': {...},
    
    # Метрики mean reversion
    'half_life': float | None,      # Дней до возврата к среднему
    'hedge_ratio': float | None,    # Коэффициент хеджирования
    
    # Агрегированные выводы
    'is_cointegrated': bool,        # Из engle_granger
    'both_nonstationary': bool,     # Из engle_granger
    
    # Рекомендация
    'recommendation': {
        'strategy': str,            # Название стратегии
        'reason': str,              # Причина
        'risk': 'low'|'medium'|'high',
        'half_life_days': float,    # Опционально
    }
}
```

### Потребители результата

```
analyze_pair() → Dict
    ↓
CointegrationService.analyze_pair()
    ↓
CointegrationResult.to_dict()
    ↓
DatabaseManager.save_cointegration_result()
    ↓
БД (cointegration_cache таблица)
    ↓
UI: get_cointegration_status_html()
UI: format_cointegration_details()
```

---

## Функции

### `synchronize_series(ytm1, ytm2, fill_method='drop')`

**Назначение:** Синхронизация двух рядов по датам

**Вход:**
- `ytm1: pd.Series` — первый ряд
- `ytm2: pd.Series` — второй ряд
- `fill_method: str` — 'drop' или 'ffill'

**Выход:**
- `Tuple[pd.Series, pd.Series]` — синхронизированные ряды

**Обработка:**
1. Удаление дубликатов дат
2. Объединение по индексу
3. Удаление/заполнение NaN

---

### `CointegrationAnalyzer`

#### `adf_test(series, max_lags=None)`

**Назначение:** Проверка стационарности ряда

**Вход:** `pd.Series`

**Выход:**
```python
{
    'test': 'ADF',
    'adf_statistic': float,
    'pvalue': float,
    'is_stationary': bool,      # p < 0.05
    'is_nonstationary': bool,   # p >= 0.05
    'interpretation': str,
}
# ИЛИ
{'error': str}
```

#### `kpss_test(series)`

**Назначение:** Дополнительный тест стационарности (обратные гипотезы)

**Вход:** `pd.Series`

**Выход:** Аналогично ADF

#### `engle_granger_test(ytm1, ytm2, trend='c', bidirectional=True)`

**Назначение:** Проверка коинтеграции между рядами

**Вход:**
- `ytm1, ytm2: pd.Series`
- `trend: str` — тип тренда
- `bidirectional: bool` — проверять оба направления

**Выход:**
```python
{
    'test': 'Engle-Granger',
    'coint_statistic': float,
    'pvalue': float,
    'is_cointegrated': bool,        # p < 0.05
    'both_nonstationary': bool,     # Оба ряда нестационарны
    'direction': str,               # 'ytm1_ytm2' или 'ytm2_ytm1'
    'interpretation': str,
}
```

#### `calculate_half_life(series)`

**Назначение:** Расчёт скорости mean reversion

**Вход:** `pd.Series` (обычно спред)

**Выход:** `float` (дней) или `None` или `float('inf')`

**Интерпретация:**
- `< 5 дней` — очень быстрая
- `5-15 дней` — быстрая
- `15-30 дней` — умеренная
- `> 30 дней` — медленная

#### `calculate_hedge_ratio(ytm1, ytm2)`

**Назначение:** Расчёт коэффициента для парного трейдинга

**Вход:** `ytm1, ytm2: pd.Series`

**Выход:** `float` или `None`

**Интерпретация:**
```
hedge_ratio = 1.05
→ На каждые 1.05 единицы bond2 нужно взять 1 единицу bond1
```

#### `analyze_pair(ytm1, ytm2)`

**Назначение:** Полный анализ пары (главный метод)

**Вход:** `ytm1, ytm2: pd.Series`

**Выход:** Полный `Dict` со всеми результатами

---

### `format_cointegration_report(result, bond1_name, bond2_name)`

**Назначение:** Форматирование Markdown отчёта (УСТАРЕЛО - дублирует app.py)

**Статус:** ⚠️ Кандидат на удаление

**Альтернатива:** `app.py:format_cointegration_details()`

---

## Зависимости

### Обязательные
- `pandas`
- `numpy`

### Опциональные
- `statsmodels` — без него возвращается `{'error': 'statsmodels not installed'}`

---

## Точки для упрощения

1. **Дублирование проверок**
   - `STATSMODELS_AVAILABLE` проверяется в каждом методе
   - `len(series) < 30` проверяется многократно
   - Константные ряды обрабатываются в ADF и KPSS

2. **`analyze_pair()` делает слишком много**
   - Вызывает 6 методов
   - Можно разделить на `analyze()` + `get_metrics()` + `get_recommendation()`

3. **`format_cointegration_report()` дублирует логику**
   - Удалить, использовать `app.py:format_cointegration_details()`

4. **Лишние тесты**
   - `kpss_test()` используется только внутри `analyze_pair()`
   - Можно сделать приватным методом

---

## Тестовое покрытие

```
tests/test_cointegration.py: 33 теста
- TestSynchronizeSeries: 5 тестов
- TestCointegrationAnalyzer: 18 тестов
- TestFormatCointegrationReport: 5 тестов
- TestIntegrationWithYTM: 3 теста
- TestEdgeCases: 3 теста
```

Все тесты проходят ✅
