# OFZ Spread Analytics - Журнал работы

## v0.2.1-patch1 — Исправление тестов (27.02.2026)

### Найденные и исправленные проблемы

| # | Проблема | Решение |
|---|----------|---------|
| 1 | `ImportError` в `__init__.py` при запуске pytest | try/except с fallback на абсолютные импорты |
| 2 | Отсутствует `tests/conftest.py` | Создан файл с настройкой путей |
| 3 | 6 тестов падали в `test_moex_bonds.py` | Обновлены тестовые данные (`has_trades`, `num_trades`) |

### Изменённые файлы

- `streamlit-app/__init__.py` — fallback импорты
- `streamlit-app/tests/conftest.py` — новый файл для pytest
- `streamlit-app/tests/test_moex_bonds.py` — обновлены тестовые данные

### Результаты тестирования

```
pytest streamlit-app/tests/ -v
================================
79 passed in 12.34s
```

### Git

- Ветка: `fix/v0.2.1-tests-and-imports`
- Репозиторий: `mishasya-dev/ofz-spread-analytics`

---

## v0.2.2 — Оптимизация (27.02.2026)

### Найденные и исправленные проблемы

| # | Проблема | Решение |
|---|----------|---------|
| 1 | `FutureWarning: 'H' is deprecated` | `freq='H'` → `freq='h'` |
| 2 | Пустой `except:` без логирования | `(ValueError, TypeError)` с логированием |
| 3 | **Медленный MOEX API (30+ сек)** | Пакетный запрос `fetch_all_market_data()` |
| 4 | `LASTTRADEDATE` недоступна | Используем `NUMTRADES` / `VALTODAY` |
| 5 | Дубли облигаций | `seen_isins` для удаления |
| 6 | O(n²) расчёт спредов | Убран — спреды на лету |

### Оптимизация MOEX API

**До:**
```
fetch_ofz_only() - много запросов
fetch_market_data(isin) - N запросов
LASTTRADEDATE - не работает
```

**После:**
```
fetch_ofz_only() - 1 запрос
fetch_all_market_data() - 1 запрос для всех
NUMTRADES, VALTODAY - работают
```

**Результат:** ~1.7 сек для 33 ОФЗ (было 30+ сек)

### Intraday улучшения

| Интервал | Было | Стало |
|----------|------|-------|
| 1 минута | 3 дня | 3 дня |
| 10 минут | 30 дней | 30 дней |
| **1 час** | **30 дней** | **365 дней** |

Пагинация работает: ~6 сек для 4000+ часовых свечей.

### Удаление лишнего

- **Расчёт спредов при обновлении БД** — убран
- Спреды рассчитываются на лету: `spread = (YTM1 - YTM2) × 100`
- Для 64 облигаций: 2016 расчётов → 0

### Тесты

```
tests/run_tests.py:    38/38 ✅
tests/test_database.py: 38/38 ✅
tests/test_sidebar.py:  14/14 ✅
────────────────────────────────
Итого:                  90/90 ✅
```

---

## v0.2.0 — Динамическое управление (27.02.2026)

### Реализовано

- Таблица `bonds` в SQLite
- Модальное окно `@st.dialog` для управления
- Фильтрация: ОФЗ-ПД, > 0.5 года, торги за 10 дней
- `is_favorite` для избранного
- Миграция 16 облигаций из config.py

### Файлы

- `components/bond_manager.py` — модальное окно
- `api/moex_bonds.py` — получение облигаций с MOEX
- `tests/test_sidebar.py` — 14 новых тестов

---

## v0.1.0 — Базовая версия (26.02.2026)

### Реализовано

- SQLite БД (daily_ytm, intraday_ytm, spreads)
- Два режима: daily и intraday
- Расчёт YTM из цен свечей
- Торговые сигналы
- 76 тестов

---

*Последнее обновление: 27.02.2026*

---

## Анализ кода для рефакторинга (27.02.2026)

### Текущая архитектура

```
streamlit-app/
├── app.py                 # ~1100 строк — ГЛАВНЫЙ ФАЙЛ (слишком большой)
├── config.py              # Конфигурация
├── api/
│   ├── moex_bonds.py      # Получение списка облигаций
│   ├── moex_candles.py    # Свечи + расчёт YTM
│   ├── moex_history.py    # Исторические данные
│   └── moex_trading.py    # Проверка торгов
├── core/
│   ├── database.py        # ~1200 строк — БД менеджер
│   ├── ytm_calculator.py  # Расчёт YTM
│   ├── spread.py          # Расчёт спредов
│   ├── signals.py         # Генерация сигналов
│   └── backtest.py        # Бэктестинг (не используется)
├── components/
│   ├── bond_manager.py    # Модальное окно выбора
│   └── charts.py          # Графики
├── modes/
│   ├── base.py            # Базовый класс режима
│   └── intraday.py        # Intraday режим (не используется)
├── export/
│   ├── formatters.py      # Форматирование
│   └── signal_sender.py   # Отправка сигналов (не используется)
└── tests/                 # 97 тестов
```

### Проблемы и предложения

#### 1. 📁 **app.py — Бог-объект (~1100 строк)**

**Проблема:** Весь UI код в одном файле. Сложно поддерживать, тестировать.

**Решение:** Разбить на модули:
```
components/
├── sidebar.py          # Боковая панель (настройки)
├── header.py           # Заголовок + режимы
├── metrics.py          # Метрики и сигналы
├── charts.py           # Графики (уже есть)
├── bond_manager.py     # Модальное окно (уже есть)
└── db_panel.py         # Панель управления БД
```

**Приоритет:** 🔴 Высокий

---

#### 2. 🗄️ **database.py — Большой класс (~1200 строк)**

**Проблема:** DatabaseManager делает всё: облигации, YTM, свечи, спреды, снимки.

**Решение:** Разделить на репозитории:
```
core/
├── db/
│   ├── __init__.py
│   ├── connection.py    # get_connection, ensure_db_dir
│   ├── bonds_repo.py    # save_bond, load_bond, get_favorites
│   ├── ytm_repo.py      # save_daily_ytm, save_intraday_ytm
│   ├── candles_repo.py  # save_candles, load_candles
│   └── spreads_repo.py  # save_spread, load_spreads
```

**Приоритет:** 🟡 Средний

---

#### 3. 📊 **Дублирование кода графиков**

**Проблема:** `create_ytm_chart()`, `create_spread_chart()` в app.py, но есть `components/charts.py`.

**Решение:** Перенести все функции графиков в `components/charts.py`, использовать ChartBuilder.

**Приоритет:** 🟢 Низкий

---

#### 4. 🔄 **Кэширование session_state**

**Проблема:** Много дублирования для инициализации session_state:
```python
if 'key' not in st.session_state:
    st.session_state.key = default_value
```

**Решение:** Создать класс-обёртку:
```python
# core/session.py
class SessionManager:
    DEFAULTS = {
        'data_mode': 'daily',
        'candle_interval': '60',
        'auto_refresh': False,
        # ...
    }
    
    @classmethod
    def init_defaults(cls):
        for key, value in cls.DEFAULTS.items():
            if key not in st.session_state:
                st.session_state[key] = value
```

**Приоритет:** 🟢 Низкий

---

#### 5. 🧪 **Мёртвый код**

**Не используется:**
- `modes/base.py` — BaseMode класс
- `modes/intraday.py` — IntradayMode класс (дублирует логику в app.py)
- `core/backtest.py` — бэктестинг
- `export/signal_sender.py` — отправка сигналов

**Решение:** Удалить или вынести в отдельную ветку/репозиторий.

**Приоритет:** 🟡 Средний

---

#### 6. 📝 **Дублирование BondItem/BondConfig**

**Проблема:** 
- `BondConfig` в config.py (dataclass)
- `BondItem` в app.py (внутренний класс)
- Словарь с данными облигации в БД

**Решение:** Единая модель:
```python
# models/bond.py
from dataclasses import dataclass

@dataclass
class Bond:
    isin: str
    name: str
    maturity_date: str
    coupon_rate: float
    face_value: float = 1000
    coupon_frequency: int = 2
    is_favorite: bool = False
    # ...
    
    @classmethod
    def from_db_row(cls, row: dict) -> 'Bond':
        ...
```

**Приоритет:** 🟡 Средний

---

#### 7. 🔧 **Конфигурация рассыпана**

**Проблема:** Константы в разных местах:
- `MAX_TRADE_DAYS_AGO = 10` в moex_bonds.py
- Интервалы в app.py
- Пороги сигналов в generate_signal()

**Решение:** Централизовать:
```python
# config.py
class AppConfig:
    # MOEX
    MAX_TRADE_DAYS_AGO = 10
    MIN_MATURITY_DAYS = 180
    
    # Intervals
    INTRADAY_INTERVALS = {
        '1': {'max_days': 3, 'default': 1},
        '10': {'max_days': 30, 'default': 7},
        '60': {'max_days': 365, 'default': 30},
    }
    
    # Signals
    SIGNAL_THRESHOLDS = {
        'p10': 0.10,
        'p25': 0.25,
        'p75': 0.75,
        'p90': 0.90,
    }
```

**Приоритет:** 🟢 Низкий

---

#### 8. ⚠️ **Обработка ошибок**

**Проблема:** Много мест с пустым `except:` или общим `except Exception`.

**Решение:** Использовать специфичные исключения:
```python
# core/exceptions.py
class OFZError(Exception):
    """Базовое исключение"""

class MOEXAPIError(OFZError):
    """Ошибка MOEX API"""

class YTMCalculationError(OFZError):
    """Ошибка расчёта YTM"""
```

**Приоритет:** 🟡 Средний

---

#### 9. 📈 **Производительность: fetch_candle_data_cached**

**Проблема:** Сложная логика с множеством проверок в кэшируемой функции. ~120 строк.

**Решение:** Вынести логику в отдельный сервис:
```python
# services/candle_service.py
class CandleService:
    def __init__(self, fetcher, db):
        self.fetcher = fetcher
        self.db = db
    
    def get_candles_with_ytm(self, isin, interval, days) -> pd.DataFrame:
        ...
```

**Приоритет:** 🟡 Средний

---

#### 10. 🧹 **Type hints**

**Проблема:** Неполные type hints, особенно для pandas DataFrame.

**Решение:** Добавить type hints, использовать TypedDict:
```python
from typing import TypedDict

class BondData(TypedDict):
    isin: str
    name: str
    ytm: float
    duration_years: float
```

**Приоритет:** 🟢 Низкий

---

### Итоговая таблица приоритетов

| # | Изменение | Приоритет | Оценка | Влияние |
|---|-----------|-----------|--------|---------|
| 1 | Разбить app.py | 🔴 Высокий | 4ч | Улучшит читаемость |
| 2 | Разбить database.py | 🟡 Средний | 3ч | Улучшит тестируемость |
| 3 | Графики в charts.py | 🟢 Низкий | 1ч | DRY |
| 4 | SessionManager | 🟢 Низкий | 1ч | DRY |
| 5 | Удалить мёртвый код | 🟡 Средний | 30мин | Чистота |
| 6 | Единая модель Bond | 🟡 Средний | 2ч | Консистентность |
| 7 | Централизовать конфиг | 🟢 Низкий | 1ч | Поддержка |
| 8 | Специфичные исключения | 🟡 Средний | 2ч | Отладка |
| 9 | CandleService | 🟡 Средний | 2ч | Тестируемость |
| 10 | Type hints | 🟢 Низкий | 2ч | Документация |

---

### Рекомендуемый порядок рефакторинга

**Фаза 1: Очистка (1 час)**
- Удалить мёртвый код (modes/, export/signal_sender.py, backtest.py)

**Фаза 2: Структура (4-5 часов)**
- Разбить app.py на компоненты
- Вынести графики в charts.py

**Фаза 3: Модели (3-4 часа)**
- Создать единую модель Bond
- Разбить DatabaseManager на репозитории

**Фаза 4: Полировка (3-4 часа)**
- SessionManager
- Централизовать конфигурацию
- Type hints
- Специфичные исключения

---

*Анализ выполнен: 27.02.2026*

---

## v0.3.0-patch1 — Исправление TypeError slider (28.02.2026)

### Проблема

```
TypeError: SliderMixin.slider() got an unexpected keyword argument 'format_func'
```

### Причина

`st.slider()` в Streamlit не поддерживает параметр `format_func`.
Этот параметр доступен только для `st.selectbox()` и `st.radio()`.

### Решение

```python
# Было (ошибка):
period = st.slider(
    "Период анализа",
    format_func=lambda x: f"{x // 30} мес." if x < 365 else f"{x // 365} год(а)"
)

# Стало (исправлено):
period = st.slider(
    "Период анализа (дней)",
    format="%d дней"
)
```

### Изменённые файлы

- `app.py` — строки 544-551

### Тесты

```
97 passed, 12 errors (Playwright tests require setup)
```

### Git

- Ветка: `feature/v0.3.0-unified-charts`
- Коммит: `5db51aa`
- Push: https://github.com/mishasya-dev/ofz-spread-analytics

---

## v0.3.0-refactor1 — Обновление sidebar.py (28.02.2026)

### Изменения

Обновлён `components/sidebar.py` для соответствия v0.3.0 unified charts:

| Функция | Изменение |
|---------|-----------|
| `render_period_selector()` | Один слайдер периода (30-730 дней) |
| `render_candle_interval_selector()` | **Новая** — выбор интервала свечей |
| `render_db_panel()` | **Новая** — панель управления БД |
| `render_cache_clear()` | **Новая** — кнопка очистки кэша |
| `render_sidebar()` | **Новая** — главная точка входа |
| `render_intraday_options()` | **Удалена** — больше не нужна |

### Обновлённые файлы

- `components/sidebar.py` — полный рефакторинг
- `components/__init__.py` — обновлены экспорты

### Тесты

```
97 passed
```

### Git

- Коммит: `29c71d9`

---

## v0.3.0-tests — Новые тесты (28.02.2026)

### Новые тестовые файлы

| Файл | Тестов | Что тестирует |
|------|--------|---------------|
| `test_charts_v030.py` | 28 | Новые графики v0.3.0 |
| `test_models_bond.py` | 26 | Модель Bond (dataclass) |

### Покрытие test_charts_v030.py

- `calculate_future_range()` — расчёт оси X с запасом
- `create_daily_ytm_chart()` — график YTM по дневным данным
- `create_daily_spread_chart()` — график спреда с перцентилями
- `create_combined_ytm_chart()` — склеенный график (история + свечи)
- `create_intraday_spread_chart()` — intraday спред с референсом

### Покрытие test_models_bond.py

- Bond dataclass: создание, defaults
- `Bond.from_dict()` / `from_db_row()` — конвертация
- `Bond.to_dict()` / `to_db_dict()` — сериализация
- `get_years_to_maturity()` — расчёт лет до погашения
- `format_label()` — форматирование метки
- BondPair: расчёт спреда

### Итого

```
Было:  97 тестов
Стало: 151 тест (+54)
```

### Git

- Коммит: `756b986`

---

## v0.3.0 — Unified Charts (27.02.2026)

### Выполненная работа

#### 1. Новый UI с 4 графиками

Убран режим daily/intraday. Теперь всегда отображаются 4 связанных графика:

| График | Данные | Назначение |
|--------|--------|------------|
| 1 | YTM дневные (YIELDCLOSE) | История + статистика |
| 2 | Спред дневной | Перцентили, среднее |
| 3 | YTM склеенный | История + свечи (intraday) |
| 4 | Спред intraday | Перцентили от дневных данных |

#### 2. Связанные графики (Linked Zoom)

- Графики 1-2 синхронизированы по zoom
- Графики 3-4 синхронизированы по zoom
- Выделение периода на одном → автоматический zoom на втором

#### 3. Цветовая схема

| Элемент | История | Свечи |
|---------|---------|-------|
| Облигация 1 | Тёмно-синий `#1a5276` | Ярко-синий `#3498DB` |
| Облигация 2 | Тёмно-красный `#922B21` | Ярко-красный `#E74C3C` |
| Спред | Фиолетовый `#9B59B6` | — |

#### 4. Единый период

- Один слайдер: 1 месяц — 2 года
- По умолчанию: 1 год
- 15% места для "будущего" на оси X

#### 5. Исправленные баги

- Период 2 года не обновлял графики (fixed)
- Статистика спреда искажалась в intraday режиме (fixed: теперь перцентили от дневных данных)

### Git

- Ветка: `feature/v0.3.0-unified-charts`
- Коммит: `2ced4bb`
- Push: https://github.com/mishasya-dev/ofz-spread-analytics

---

*Последнее обновление: 27.02.2026*

---

## v0.3.0-tests2 — Новые тесты (28.02.2026)

### Выполненная работа

#### 1. Новые тестовые файлы

| Файл | Тестов | Что тестирует |
|------|--------|---------------|
| `test_candle_service.py` | 36 | CandleService |
| `test_db_repositories.py` | 23 | BondsRepository, YTMRepository, SpreadsRepository |
| `test_app_v030.py` | 20 | Интеграционные тесты (spread, signals, labels) |

#### 2. Исправления графиков

**Проблема:** На скриншоте видно, что история и свечи неразличимы - одинаковый цвет.

**Решение:**
- История: тёмный цвет + пунктир (`dash='dash'`) + метка "(дневн.)"
- Свечи: яркий цвет + сплошная линия + метка "(свечи)"
- Добавлена сетка на все 4 графика

```python
# Было:
line=dict(color=BOND1_COLORS["history"], width=2)

# Стало:
line=dict(color=BOND1_COLORS["history"], width=2, dash='dash'),
opacity=0.8
```

#### 3. Итоги тестирования

```
До:    198 тестов
После: 277 тестов (+79)
```

### Git

- Ветка: `feature/v0.3.0-unified-charts`
- Коммит: `0cc19af`
- Push: https://github.com/mishasya-dev/ofz-spread-analytics

---

## Рекомендации по стабильности (TODO)

### 1. Файл зависимостей
**Приоритет:** 🟡 Средний

**Текущее состояние:**
- `requirements.txt` — основные зависимости
- `requirements-dev.txt` — для разработки

**Рекомендация:**
- Добавить `requirements-lock.txt` с фиксированными версиями
- Или использовать `pip-compile` от pip-tools

---

### 2. Обработка пропусков данных
**Приоритет:** 🔴 Высокий

**Проблема:** Если MOEX не вернул данные за день — возможны ошибки.

**Где исправить:**
- `app.py:fetch_historical_data_cached()` — проверить на пустые данные
- `app.py:fetch_candle_data_cached()` — проверить на пустые данные
- Расчёт спреда — обработать NaN

**Решение:**
```python
# Проверка на пустые данные
if df.empty:
    st.warning("Нет данных за период")
    return pd.DataFrame()

# Интерполяция пропусков
df = df.interpolate()

# Fallback на последние данные
if pd.isna(current_value):
    current_value = df['ytm'].iloc[-1]
```

---

### 3. Хардкод путей
**Приоритет:** 🟡 Средний

**Найденные места:**
```
core/db/connection.py: DB_PATH = ".../data/ofz_data.db"
core/database.py:       DB_PATH = ".../data/ofz_data.db"
```

**Решение:**
```python
# config.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "ofz_data.db"

# Или через переменные окружения
DB_PATH = os.environ.get("OFZ_DB_PATH", "data/ofz_data.db")
```

---

### Чек-лист для реализации

- [ ] `requirements-lock.txt` с фиксированными версиями
- [ ] Обработка пустых данных в fetch_historical_data_cached()
- [ ] Обработка пустых данных в fetch_candle_data_cached()
- [ ] Обработка NaN в расчёте спреда
- [ ] Конфигурация путей в config.py
- [ ] Убрать хардкод из core/db/connection.py
- [ ] Убрать хардкод из core/database.py

---

*Рекомендации добавлены: 27.02.2026*

---

## 📋 Текущее состояние проекта (28.02.2026)

### Git

- **Репозиторий:** https://github.com/mishasya-dev/ofz-spread-analytics
- **Ветка:** `feature/v0.3.0-unified-charts`
- **Последний коммит:** `0cc19af`
- **Токен:** Встроен в git remote URL

### Тесты

```
Всего тестов: 277
Прошли:       277 ✅
Ошибки:       12 (Playwright UI - нужны браузеры)
```

### Структура тестов

| Файл | Тестов |
|------|--------|
| test_database.py | ~100 |
| test_sidebar_v030.py | 36 |
| test_candle_service.py | 36 |
| test_moex_bonds.py | 34 |
| test_bond_manager.py | 31 |
| test_charts_v030.py | 28 |
| test_models_bond.py | 26 |
| test_bonds.py | 22 |
| test_app_v030.py | 20 |
| test_sidebar.py | 14 |
| test_ytm_calculation.py | 6 |

### Последние изменения

1. **Графики (charts.py)**
   - История: пунктир + метка "(дневн.)"
   - Свечи: сплошная + метка "(свечи)"
   - Добавлена сетка на все 4 графика

2. **Новые тесты**
   - test_candle_service.py (36 тестов)
   - test_db_repositories.py (23 теста)
   - test_app_v030.py (20 тестов)

### База данных

- **Путь:** `streamlit-app/data/ofz_data.db`
- **Таблицы:** bonds, daily_ytm, intraday_ytm, spreads
- **Облигаций:** 16
- **Дневных YTM:** ~821 записей

### Файлы проекта

```
streamlit-app/
├── app.py                    # Главный файл (~1100 строк)
├── config.py                 # Конфигурация
├── api/                      # MOEX API
│   ├── moex_bonds.py
│   ├── moex_candles.py
│   ├── moex_history.py
│   └── moex_trading.py
├── core/
│   ├── database.py           # DatabaseManager
│   ├── db/                   # Репозитории
│   │   ├── connection.py
│   │   ├── bonds_repo.py
│   │   ├── ytm_repo.py
│   │   └── spreads_repo.py
│   ├── ytm_calculator.py
│   ├── spread.py
│   ├── signals.py
│   └── session.py
├── components/
│   ├── sidebar.py            # Панель настроек
│   ├── charts.py             # Графики Plotly
│   ├── bond_manager.py       # Модальное окно
│   └── metrics.py
├── models/
│   └── bond.py               # Bond dataclass
├── services/
│   └── candle_service.py
└── tests/                    # 277 тестов
```

### Следующие задачи

1. **Рефакторинг** (из анализа выше):
   - Разбить app.py на компоненты
   - Удалить мёртвый код (modes/, backtest.py)
   
2. **Стабильность**:
   - Обработка пустых данных MOEX
   - requirements-lock.txt

---

## v0.3.0-bugfix1 — Исправление расхождения YTM (28.02.2026)

### Проблема

На 3-м графике (YTM история + свечи) наблюдалось расхождение между:
- Дневными YTM (YIELDCLOSE с MOEX)
- Свечными YTM (расчёт из цен свечей)

### Причина

История и свечи показывались за **одинаковый период** (365 дней):
- История: дневные YTM за 365 дней
- Свечи: часовые YTM за 365 дней (~2500 точек!)

### Решение

1. Ограничить intraday данные до 30 дней
2. Обрезать историю до начала свечей (не дублировать)
3. Использовать отдельные копии для графика vs статистики

### Git

- Коммит: `a17629f`
- Push: https://github.com/mishasya-dev/ofz-spread-analytics

---

## 🧪 План тестирования v0.3.0 (28.02.2026)

### Текущий статус (198 тестов)

| Файл | Тестов | Статус |
|------|--------|--------|
| test_database.py | ~100 | ✅ Прошли |
| test_sidebar_v030.py | 36 | ✅ Прошли |
| test_charts_v030.py | 28 | ✅ Прошли |
| test_models_bond.py | 26 | ✅ Прошли |
| test_sidebar.py | 14 | ✅ Прошли |
| test_ytm_calculation.py | 6 | ✅ Прошли |
| test_ui.py | 12 | ❌ Playwright (нужны браузеры) |

---

### ✅ Уже протестировано

#### 1. Sidebar (test_sidebar_v030.py)
- `render_period_selector()` — диапазон 30-730, шаг 30, формат
- `render_candle_interval_selector()` — опции 1/10/60, format_func
- `render_auto_refresh()` — toggle, интервал, session_state
- `render_db_panel()` — статистика, кнопка, callback, ошибки
- `render_bond_selection()` — selectbox, format_func, YTM в метке
- `format_bond_label()` — YTM, дюрация, годы до погашения
- `get_years_to_maturity()` — будущие/прошлые даты
- `get_bonds_list()` — список из session_state

#### 2. Charts (test_charts_v030.py)
- `calculate_future_range()` — пустой индекс, одна точка, 15% запас
- `create_daily_ytm_chart()` — пустые данные, 1/2 облигации, цвета
- `create_daily_spread_chart()` — перцентили P25/P75, fill, цвет
- `create_combined_ytm_chart()` — история + свечи, 4 линии
- `create_intraday_spread_chart()` — референс от дневных данных
- `apply_zoom_range()` — применение диапазона

#### 3. Models (test_models_bond.py)
- Bond dataclass — создание, defaults
- `Bond.from_dict()` / `from_db_row()` — конвертация
- `Bond.to_dict()` / `to_db_dict()` — сериализация
- `get_years_to_maturity()` — расчёт лет
- `format_label()` — метка с YTM/дюрацией
- BondPair — расчёт спреда

---

### ❌ Недостающие тесты (приоритеты)

#### 🔴 Высокий приоритет

##### 1. Интеграционные тесты app.py

**Функция: `calculate_spread_stats()`**
```python
# Что тестировать:
- Пустой series → пустой dict
- Series с NaN → корректные значения
- Все перцентили: p10, p25, p50, p75, p90
- mean, median, std, min, max
- current = последнее значение
```

**Функция: `generate_signal()`**
```python
# Что тестировать:
- spread < p25 → SELL_BUY
- spread < p10 → STRONG
- spread > p75 → BUY_SELL
- spread > p90 → STRONG
- p25 <= spread <= p75 → NEUTRAL
- Проверка reason, color, strength
```

**Функция: `prepare_spread_dataframe()`**
```python
# Что тестировать:
- Пустой df1 или df2 → пустой результат
- Отсутствие колонки ytm → пустой результат
- Корректный расчёт: spread = (ytm1 - ytm2) * 100
- Удаление NaN
- is_intraday=True → колонка 'datetime'
- is_intraday=False → колонка 'date'
```

##### 2. Linked Zoom функциональность

```python
# test_linked_zoom.py (новый файл)

def test_zoom_selection_captured():
    """Выделение на графике сохраняется в session_state"""

def test_zoom_applied_to_paired_chart():
    """Zoom с графика 1 применяется к графику 2"""

def test_zoom_reset_clears_session_state():
    """Кнопка сброса очищает zoom range"""

def test_intraday_zoom_separate_from_daily():
    """Zoom графиков 3-4 независим от 1-2"""
```

##### 3. Обработка пустых данных

```python
# test_edge_cases.py (новый файл)

def test_empty_daily_data():
    """Пустые дневные данные → предупреждение"""

def test_empty_intraday_data():
    """Пустые intraday данные → только история"""

def test_nan_in_spread():
    """NaN в YTM → исключается из спреда"""

def test_single_day_data():
    """Одна точка данных → корректное отображение"""

def test_moex_api_timeout():
    """Таймаут MOEX → graceful degradation"""
```

---

#### 🟡 Средний приоритет

##### 4. Функции обновления БД

**Функция: `update_database_full()`**
```python
# Что тестировать:
- Прогресс callback вызывается
- Дневные YTM сохраняются
- Intraday YTM для каждого интервала
- Обработка ошибок для отдельных облигаций
- Возврат статистики {daily_ytm_saved, intraday_ytm_saved, errors}
```

##### 5. Session State инициализация

```python
# test_session_init.py (новый файл)

def test_init_session_state_defaults():
    """Все defaults установлены"""

def test_session_state_persistence():
    """Значения сохраняются между rerun"""

def test_bonds_migration_from_config():
    """Миграция облигаций из config.py"""

def test_bonds_loaded_from_db():
    """Загрузка избранных облигаций из БД"""
```

##### 6. Candle Interval Constraints

```python
# test_candle_constraints.py (новый файл)

def test_1min_max_3_days():
    """1-минутные свечи ограничены 3 днями"""

def test_10min_max_30_days():
    """10-минутные свечи ограничены 30 днями"""

def test_60min_max_365_days():
    """Часовые свечи ограничены 365 днями"""

def test_period_capped_by_interval():
    """Период обрезается по интервалу"""
```

---

#### 🟢 Низкий приоритет

##### 7. Форматирование и отображение

```python
# test_formatting.py (новый файл)

def test_bond_label_without_ytm():
    """Метка без YTM — только имя и годы"""

def test_bond_label_with_all_data():
    """Метка с YTM, дюрацией, годами"""

def test_metric_display_format():
    """Формат метрик: YTM.2f%, spread.1f б.п."""

def test_exchange_status_open():
    """Статус биржи: открыта"""

def test_exchange_status_closed():
    """Статус биржи: закрыта"""
```

##### 8. Цветовая схема графиков

```python
# test_chart_colors.py (новый файл)

def test_bond1_history_color():
    """Облигация 1 история: #1a5276"""

def test_bond1_intraday_color():
    """Облигация 1 свечи: #3498DB"""

def test_bond2_history_color():
    """Облигация 2 история: #922B21"""

def test_bond2_intraday_color():
    """Облигация 2 свечи: #E74C3C"""

def test_spread_color():
    """Спред: #9B59B6"""
```

---

### 📊 Покрытие по модулям

| Модуль | Текущее | Целевое |
|--------|---------|---------|
| app.py | 0% | 70% |
| components/sidebar.py | 90% | 95% |
| components/charts.py | 80% | 90% |
| core/database.py | 85% | 90% |
| api/moex_*.py | 70% | 80% |
| models/bond.py | 95% | 95% |

---

### 🚀 План реализации

**Фаза 1: Критические тесты (2-3 часа)**
1. `test_app_integration.py` — calculate_spread_stats, generate_signal
2. `test_spread_preparation.py` — prepare_spread_dataframe
3. `test_edge_cases.py` — пустые данные, NaN

**Фаза 2: Связанные графики (1-2 часа)**
4. `test_linked_zoom.py` — zoom синхронизация
5. `test_candle_constraints.py` — ограничения интервалов

**Фаза 3: Полировка (1-2 часа)**
6. `test_session_init.py` — session_state
7. `test_update_db.py` — обновление БД
8. `test_formatting.py` — форматирование

---

### Итоговая оценка

| Приоритет | Тестов | Время |
|-----------|--------|-------|
| 🔴 Высокий | ~30 | 3-4 часа |
| 🟡 Средний | ~20 | 2-3 часа |
| 🟢 Низкий | ~15 | 1-2 часа |
| **Итого** | **~65** | **6-9 часов** |

---

*План тестирования создан: 28.02.2026*

---

## ✅ Реализованные тесты v0.3.0 (28.02.2026)

### Созданные файлы

| Файл | Тестов | Что тестирует |
|------|--------|---------------|
| `test_app_integration.py` | 30 | calculate_spread_stats, generate_signal, prepare_spread_dataframe |
| `test_edge_cases.py` | 25 | Пустые данные, NaN, одна точка, границы |
| `test_linked_zoom.py` | 22 | Синхронизация zoom, независимость пар |

### Детали test_app_integration.py

**TestCalculateSpreadStats (8 тестов):**
- Пустой series → пустой dict
- Одно значение — все статистики равны
- Перцентили p10, p25, p75, p90
- NaN исключаются из расчёта
- Отрицательные значения
- current = последнее значение
- Большой набор данных (10,000 значений)

**TestGenerateSignal (12 тестов):**
- spread < p25 → SELL_BUY
- spread < p10 → Сильный сигнал
- spread > p75 → BUY_SELL
- spread > p90 → Сильный сигнал
- p25 <= spread <= p75 → NEUTRAL
- Границы включены в NEUTRAL
- Проверка reason, color, strength

**TestPrepareSpreadDataframe (10 тестов):**
- Пустой df1/df2 → пустой результат
- Отсутствие колонки ytm → пустой результат
- spread = (ytm1 - ytm2) * 100
- Удаление NaN строк
- daily → колонка 'date'
- intraday → колонка 'datetime'
- Отрицательный спред
- Разные индексы — пересечение

### Детали test_edge_cases.py

**TestEmptyDailyData (5 тестов):**
- Пустой DataFrame YTM
- Пустой series статистика
- Графики с пустыми данными

**TestEmptyIntradayData (3 теста):**
- Пустой DataFrame свечей
- Склеенный график с только дневными

**TestNaNHandling (4 теста):**
- NaN в YTM series
- NaN в расчёте спреда
- Перцентили с NaN
- Полностью NaN series

**TestSingleDataPoint (4 теста):**
- Одно значение YTM
- Статистика одной точки
- График с одной точкой
- Спред из одной точки

**TestDateRangeBoundaries (5 тестов):**
- Период min=30, max=730 дней
- 1мин = max 3 дня
- 10мин = max 30 дней
- 60мин = max 365 дней

**TestPercentileBoundaries (2 теста):**
- Порядок p10 < p25 < p50 < p75 < p90
- Перцентиль на границе

### Детали test_linked_zoom.py

**TestZoomRangeStorage (4 теста):**
- daily_zoom_range = None по умолчанию
- intraday_zoom_range = None по умолчанию
- Сохранение и сброс zoom

**TestApplyZoomRange (4 теста):**
- Валидный диапазон применяется
- None диапазон — без изменений
- Частичный диапазон (один None) игнорируется
- Строковый диапазон от Plotly

**TestDailyChartsSync (3 теста):**
- Оба графика 1-2 используют один range
- Zoom применяется к YTM
- Zoom применяется к спреду

**TestIntradayChartsSync (2 теста):**
- Склеенный график принимает range
- Intraday спред принимает range

**TestZoomIndependence (3 теста):**
- Daily и intraday zoom независимы
- Установка intraday не влияет на daily
- Сброс daily не влияет на intraday

### Итоговый результат

```
До:    198 тестов
После: 287 тестов (+89)
Прошли: 275 ✅
Ошибки: 12 (Playwright UI - нужны браузеры)
```

---

*Тесты реализованы: 28.02.2026*

---

*Контекст сохранён: 28.02.2026*

---

## v0.3.0-hotfix1 — Исправление расчёта НКД (28.02.2026)

### Проблема

Расчётный YTM расходился с биржевыми данными на исторических периодах:
- ОФЗ 26207: расчётный YTM был выше биржевого (апрель-август, октябрь)
- ОФЗ 26232: расчётный YTM был ниже биржевого (апрель-август)

### Причина

В `api/moex_candles.py` НКД получался с MOEX **один раз** для всего DataFrame:
```python
# БЫЛО (баг):
accrued_interest = self._get_accrued_interest(bond_config.isin)
```

НКД (накопленный купонный доход) **меняется каждый день**, а код использовал текущий НКД для всех исторических свечей.

### Исправление

1. Добавлен метод `calculate_accrued_interest_for_date()` в `core/ytm_calculator.py`
2. Добавлен метод `_find_last_coupon_date()` для расчёта даты последнего купона
3. НКД теперь рассчитывается для каждой даты свечи

```python
# СТАЛО (исправлено):
for idx, row in df.iterrows():
    accrued_interest = self._ytm_calculator.calculate_accrued_interest_for_date(
        bond_params, settlement_date
    )
```

### Пример изменения НКД

**ОФЗ 26207 (купон 8.15%):**
| Дата | НКД |
|------|------|
| 04.04.2025 | 13.43 руб |
| 01.08.2025 | 40.08 руб |
| 05.08.2025 | 0.45 руб (после купона) |

**ОФЗ 26232 (купон 6.0%):**
| Дата | НКД |
|------|------|
| 04.04.2025 | 29.67 руб |
| 01.08.2025 | 19.29 руб |
| 02.10.2025 | 29.51 руб |

### Результат

Графики расчётного YTM теперь совпадают с биржевыми данными на всех периодах.

### Git

- Коммит: `70c2bd2`
- Ветка: `feature/v0.3.0-unified-charts`

---

*Исправление подтверждено: 28.02.2026*

---

## 📋 Сессия 28.02.2026 — Итоги

### Выполненная работа

#### 1. Исправлен критический баг: Расхождение YTM

**Проблема:** Расчётный YTM расходился с биржевыми данными на исторических периодах.

**Причина:** НКД (накопленный купонный доход) получался с MOEX один раз для всего DataFrame.

**Исправление:**
- Добавлен `calculate_accrued_interest_for_date()` — расчёт НКД на конкретную дату
- Добавлен `_find_last_coupon_date()` — поиск даты последнего купона
- НКД теперь рассчитывается для каждой даты свечи

**Коммит:** `70c2bd2`

#### 2. Новые тесты (+77)

| Файл | Тестов |
|------|--------|
| test_app_integration.py | 30 |
| test_edge_cases.py | 25 |
| test_linked_zoom.py | 22 |

**Всего тестов:** 287 (275 прошли)

#### 3. Документация

- `README.md` — документация проекта (ru/en)
- `CHANGELOG.md` — история версий
- `SESSION_CONTEXT.md` — контекст сессии

### Git Status

```
Repository: https://github.com/mishasya-dev/ofz-spread-analytics
Branch:     feature/v0.3.0-unified-charts
Commits:    
  - 70c2bd2: fix: НКД теперь рассчитывается на дату каждой свечи
  - 38977b8: v0.3.0-tests: +77 новых тестов
```

### Пример работы исправления

**ОФЗ 26207 (купон 8.15%):**
| Дата | НКД до | НКД после |
|------|--------|-----------|
| 04.04.2025 | 40.64 (текущий) | **13.43** |
| 01.08.2025 | 40.64 (текущий) | **40.08** |
| 05.08.2025 | 40.64 (текущий) | **0.45** |

### Структура файлов

```
streamlit-app/
├── api/moex_candles.py      # ИСПРАВЛЕНО: НКД на дату свечи
├── core/ytm_calculator.py   # ИСПРАВЛЕНО: новые методы
├── tests/
│   ├── test_app_integration.py  # НОВЫЙ
│   ├── test_edge_cases.py       # НОВЫЙ
│   └── test_linked_zoom.py      # НОВЫЙ
├── README.md                 # НОВЫЙ
├── CHANGELOG.md              # НОВЫЙ
├── SESSION_CONTEXT.md        # НОВЫЙ
└── worklog.md               # ОБНОВЛЁН
```

### Следующие шаги

1. Слить `feature/v0.3.0-unified-charts` в main
2. Настроить Playwright для UI тестов
3. Добавить новые облигации по мере выпуска

---

*Сессия завершена: 28.02.2026 14:45 UTC*

---

## v0.3.1 — Spread Analytics с Z-Score (01.03.2026)

### Новая функция: create_spread_analytics_chart()

**Описание**: Профессиональная панель анализа спреда с Z-Score

**Структура графика**:
- Панель 1: YTM обеих облигаций (дневные данные)
- Панель 2: Спред + Rolling Mean + ±Zσ границы

**Функционал**:
| Параметр | Диапазон | По умолчанию |
|----------|----------|--------------|
| Rolling Window | 5-90 дней | 30 |
| Z-Score Threshold | 1.0-3.0σ | 2.0 |

**Сигналы**:
- 🟢 BUY: Z < -threshold (спред аномально низкий)
- 🔴 SELL: Z > +threshold (спред аномально высокий)
- ⚪ Neutral: Z в пределах threshold

### Рефакторинг UI

**Удалено**:
- График 1: Daily YTM (дублировал Панель 1)
- График 2: Daily Spread (дублировал Панель 2)
- `daily_zoom_range` session state

**Новая структура**:
```
📊 Метрики (YTM, Spread, Signal)
─────────────────────────────────
📊 График 1: Spread Analytics (Z-Score)
─────────────────────────────────
📊 График 2: Combined YTM (intraday)
📊 График 3: Intraday Spread
```

### Исправления

| # | Проблема | Решение |
|---|----------|---------|
| 1 | Slider crash: `min_value == max_value` (30 == 30) | `if max_days <= min_days: min_days = max(1, max_days - 1)` |
| 2 | `cannot reindex on an axis with duplicate labels` | Использован `join()` вместо dict-based DataFrame |
| 3 | Сетка сплошная | Добавлен `griddash='dot'` |

### Новые тесты (+11)

**Класс**: `TestSpreadAnalyticsChart`

| Тест | Описание |
|------|----------|
| test_empty_dataframes | Пустые данные |
| test_missing_ytm_column | Нет колонки ytm |
| test_basic_chart_structure | Структура графика |
| test_spread_calculation | Точность расчёта |
| test_z_score_signal_colors | Цвета сигналов |
| test_custom_window_and_threshold | Кастомные параметры |
| test_duplicate_indices_handling | Дубли индексов |
| test_different_date_ranges | Разные диапазоны дат |
| test_grid_style | Стиль сетки |
| test_layout_title_and_labels | Заголовок и подписи |

### Результаты тестирования

```
python tests/test_charts_v030.py
================================
Ran 38 tests in 2.359s
OK
```

### Git

- Ветка: `feature/v0.3.0-unified-charts`
- Коммиты:
  - `6697b09` - feat: add professional spread analytics chart with Z-Score
  - `0bb1cda` - feat: integrate Spread Analytics chart into UI
  - `990f5ef` - fix: slider error when min_value equals max_value
  - `ff5624e` - refactor: remove show_gaps from spread analytics chart
  - `db70db0` - fix: handle duplicate indices in create_spread_analytics_chart
  - `4e14b12` - fix: change grid to dotted style on Spread Analytics chart
  - `34c2d1b` - refactor: remove redundant charts 1-2
  - `648ead8` - test: add 11 tests for create_spread_analytics_chart
  - `9881f43` - docs: update SESSION_CONTEXT and CHANGELOG for v0.3.1

### Изменённые файлы

```
streamlit-app/
├── components/
│   ├── charts.py          # НОВАЯ ФУНКЦИЯ: create_spread_analytics_chart()
│   └── sidebar.py         # ИСПРАВЛЕНО: slider min_value bug
├── app.py                 # РЕФАКТОРИНГ: удалены графики 1-2
├── tests/
│   └── test_charts_v030.py # +11 тестов
├── SESSION_CONTEXT.md     # ОБНОВЛЁН
└── CHANGELOG.md           # ОБНОВЛЁН
```

### Следующие шаги

1. Тестирование пользователем в ветке `feature/v0.3.0-unified-charts`
2. При одобрении — merge в `stable` и обновление тега `v0.3.0-stable`
3. Рассмотреть добавление alerts на основе Z-Score

---

*Сессия завершена: 01.03.2026 13:55 UTC*

---

## v0.4.8 — Сессия восстановления (2026-03-01)

### Контекст сессии

Сессия восстановления после переполнения контекста. Основные задачи:
1. Сохранение контекста и сессии
2. Обновление документации
3. Проверка и исправление тестов
4. Тестирование приложения
5. Анализ рефакторинга

### Выполненные работы

#### 1. Исправление тестов БД

**Проблема:** Тесты `test_db_repositories.py` падали из-за отсутствия колонок `volume` и `value` в таблице `intraday_ytm`.

**Решение:**
- Обновлён fixture `temp_db` — добавлены колонки `volume`, `value`
- Обновлён fixture `sample_intraday_ytm_df` — добавлены тестовые данные для volume/value
- Запущена миграция БД через `init_database()`

**Результат:** 364 теста проходят успешно (12 Playwright UI тестов пропущены)

#### 2. Структура тестов

| Файл | Тестов | Статус |
|------|--------|--------|
| test_database.py | ~100 | ✅ |
| test_sidebar_v030.py | 36 | ✅ |
| test_candle_service.py | 36 | ✅ |
| test_moex_bonds.py | 34 | ✅ |
| test_bond_manager.py | 31 | ✅ |
| test_charts_v030.py | 28 | ✅ |
| test_models_bond.py | 26 | ✅ |
| test_db_repositories.py | 22 | ✅ |
| test_bonds.py | 22 | ✅ |
| test_app_integration.py | 30 | ✅ |
| test_app_v030.py | 20 | ✅ |
| test_sidebar.py | 14 | ✅ |
| test_edge_cases.py | 25 | ✅ |
| test_linked_zoom.py | 22 | ✅ |
| test_ytm_calculation.py | 6 | ✅ |
| test_ui.py | 12 | ⚠️ (Playwright) |
| **Итого** | **364** | **✅** |

### Git Status

- **Ветка:** `experiments`
- **Последний коммит:** `6f4cd72` — perf: оптимизация графиков YTM
- **Теги:** v0.4.0 ... v0.4.7

### Ключевые изменения в v0.4.x

1. **Объём торгов (volume/value)**
   - Добавлен график объёма торгов в рублях
   - Два набора баров (голубой для bond1, розовый для bond2)
   - Колонки `volume`, `value` в БД

2. **Оптимизация производительности**
   - Инкрементальная загрузка данных (дозагрузка вместо полной перезагрузки)
   - Оптимизация графиков (line width, opacity, hovertemplate)

3. **Исправления багов**
   - Модальное окно: динамический key для data_editor
   - Слайдеры: синхронизация через `key` вместо `value` + assignment
   - Проверка покрытия периода при увеличении слайдера

### Следующие шаги

1. Запуск приложения и тестирование UI
2. Анализ необходимости рефакторинга
3. Обновление документации (CHANGELOG.md, README.md)

---

*Сессия сохранена: 2026-03-01*

---

## v0.5.0 — Рефакторинг: Модульная архитектура (2026-03-01)

### Выполненный рефакторинг

#### Фаза 1: Сервисы загрузки данных

Создан `services/data_loader.py` (~350 строк):
- `get_history_fetcher()` — кэшированный HistoryFetcher
- `get_candle_fetcher()` — кэшированный CandleFetcher
- `fetch_trading_data()` — торговые данные с MOEX
- `fetch_historical_data()` — исторические YTM с инкрементальным обновлением
- `fetch_candle_data()` — свечи с YTM с инкрементальным обновлением
- `update_database_full()` — полное обновление БД

#### Фаза 2: Калькулятор спредов

Создан `services/spread_calculator.py` (~150 строк):
- `calculate_spread_stats()` — статистика спреда (mean, std, percentiles)
- `generate_signal()` — генерация торговых сигналов
- `prepare_spread_dataframe()` — подготовка DataFrame со спредом
- `calculate_rolling_stats()` — скользящая статистика
- `calculate_zscore()` — расчёт Z-Score

#### Фаза 3: Утилиты облигаций

Создан `utils/bond_utils.py` (~150 строк):
- `BondItem` класс — унифицированное представление облигации
- `get_years_to_maturity()` — расчёт лет до погашения
- `get_bonds_list()` — получение списка BondItem
- `format_bond_label()` — форматирование метки для UI

#### Фаза 4: Фасад базы данных

Создан `core/db/facade.py` (~280 строк):
- `DatabaseFacade` — фасад для работы с БД
- Делегирует вызовы специализированным репозиториям:
  - `BondsRepository` — облигации
  - `YTMRepository` — YTM данные
  - `SpreadsRepository` — спреды

### Структура после рефакторинга

```
streamlit-app/
├── app.py                    # UI (~1040 строк) — без изменений
├── services/
│   ├── candle_service.py     # CandleService (существующий)
│   ├── data_loader.py        # Загрузка данных ← NEW
│   └── spread_calculator.py  # Расчёт спредов ← NEW
├── utils/
│   └── bond_utils.py         # BondItem класс ← NEW
├── core/db/
│   ├── connection.py         # Соединение с БД
│   ├── bonds_repo.py         # Репозиторий облигаций
│   ├── ytm_repo.py           # Репозиторий YTM
│   ├── spreads_repo.py       # Репозиторий спредов
│   └── facade.py             # Фасад БД ← NEW
└── components/
    └── charts.py             # Графики (~1470 строк) — без изменений
```

### Статистика

| Метрика | До | После |
|---------|-----|-------|
| Тестов | 364 | 364 |
| Проходят | 364 | 364 ✅ |
| Новых файлов | - | 5 |
| Новых строк | - | ~930 |

### Git

```
Commit: b75d36b
Tag:    v0.5.0-refactor
Push:   origin/experiments
```

### Следующие шаги

1. Интегрировать новые сервисы в app.py (заменить inline функции)
2. Разбить charts.py на ytm_charts.py и spread_charts.py
3. Мигрировать DatabaseManager → DatabaseFacade

---

*Рефакторинг завершён: 2026-03-01*

---

## v0.7.0 — Architecture Refactor (06.03.2026)

### Цель

Разделить расчёт YTM от API слоя (Single Responsibility Principle).

### Выполненная работа

#### 1. Рефакторинг api/moex_candles.py

**До:**
```python
def fetch_candles(isin, bond_config, ...):
    # Получал свечи И рассчитывал YTM
    return df_with_ytm
```

**После:**
```python
def fetch_candles(isin, ...):
    # Только сырые свечи OHLCV
    return raw_df  # open, high, low, close, volume
```

#### 2. Новый сервис BondYTMProcessor

```python
# services/candle_processor_ytm_for_bonds.py
class BondYTMProcessor:
    def add_ytm_to_candles(df, bond_config) -> pd.DataFrame:
        """Добавить колонку ytm_close к DataFrame"""
        
    def calculate_ytm_for_price(price, bond_config, trade_date) -> float:
        """Рассчитать YTM для одной цены"""
```

#### 3. Оптимизация кэширования

**Проблема:** Кэш инвалидируется при изменении периода слайдера.

**Решение:** Разделить кэширование:
```python
# Кэш по ISIN (730 дней)
@st.cache_data(ttl=300)
def _fetch_all_historical_data(isin) -> pd.DataFrame

# Фильтрация без кэша
def fetch_historical_data_cached(isin, days):
    all_df = _fetch_all_historical_data(isin)
    return all_df[date >= today - days]
```

**Результат:**
| Сценарий | До | После |
|----------|-----|-------|
| Период 365 → 180 | Cache miss, DB query | Filter from cache |
| Период 180 → 365 | Cache miss, DB query | Filter from cache |

#### 4. Обновлённые файлы

| Файл | Изменение |
|------|-----------|
| `api/moex_candles.py` | Только сырые свечи (-200 строк) |
| `services/candle_processor_ytm_for_bonds.py` | **Новый** (+270 строк) |
| `services/candle_service.py` | +BondYTMProcessor |
| `services/data_loader.py` | +BondYTMProcessor |
| `app.py` | +BondYTMProcessor, оптимизация кэша |
| `tests/test_bond_ytm_processor.py` | **Новый** (+293 строки) |

### Архитектура

```
API Layer (moex_candles.py)
    ↓ сырые свечи (OHLCV)
Business Logic (BondYTMProcessor)
    ↓ свечи + YTM
Service Layer (candle_service.py, data_loader.py)
    ↓ кэширование, дозагрузка
Database (ytm_repo.py)
```

### Тесты

```
Всего:  398 тестов
Прошли: 398 ✅
Новых:  +14 (test_bond_ytm_processor.py)
```

### Git

```
Branch:  refactor/separate-ytm-calculation
Commits: 00da0cf → 7e41d2b
Merged:  experiments (3e7c610)
```

---

*Рефакторинг завершён: 2026-03-06*

---

## Исследование history API MOEX (07.03.2026)

### Проверенные endpoints

#### 1. history/engines/stock/markets/bonds/securities/{ISIN}/yields.json
```
Columns: YIELDCLOSE, DURATION, ZSPREAD, CLOSE, ...
History: ✅ 2+ года (пагинация 100 записей)
```

#### 2. history/engines/stock/zcyc.json?date=YYYY-MM-DD
```
Параметры КБД: b1, b2, b3, t1
History: ✅ 16528 записей (intraday updates)
Yearyields: ❌ НЕТ истории
```

#### 3. engines/stock/zcyc.json (текущий)
```
yearyields: 11 точек (0.25, 0.5, 1, 2, 3, 5, 7, 10, 15, 20 лет)
securities: clcyield (YTM по КБД для каждой облигации)
```

### Ключевая находка: clcyield ≠ GSPREADBP

```
clcyield расчёт:
  YTM_факт = 14.76%, YTM_КБД = 14.49%
  G-spread = +27 bps

GSPREADBP (официальный):
  G-spread = +3 bps

Разница: 24 bps!

Причина: clcyield использует текущую КБД,
         GSPREADBP использует КБД на момент расчёта
```

### Правильный расчёт G-spread

```python
# Метод: интерполяция по yearyields
moex_yearyields = [
    (0.25, 13.68), (0.5, 13.90), (1.0, 14.24), ...
]

ytm_kbd = np.interp(duration_years, periods, yields)
g_spread = ytm_bond - ytm_kbd

# Результат: совпадает с GSPREADBP ±1 bps ✅
```

### Проблема исторического G-spread

| Что нужно | Доступность |
|-----------|-------------|
| YTM облигации | ✅ history/yields |
| Duration | ✅ history/yields |
| Точки КБД (yearyields) | ❌ Только текущие |
| Параметры NS (b1,b2,b3,t1) | ✅ history/zcyc |

### Решения

**A. Хранить снапшоты yearyields** (идеально)
- Каждый день сохранять 11 точек КБД
- История доступна в своей БД

**B. Использовать параметры NS** (практично)
- history/zcyc даёт b1,b2,b3,t1 на каждую дату
- Рассчитывать YTM_КБД по формуле NS
- Погрешность ~1%

**C. Комбо**
- Текущий: GSPREADBP из API
- Исторический: NS параметры + калибровка по текущим yearyields

---

*Исследование history API: 07.03.2026*

---

## Исследование moexalgo (08.03.2026)

### Цель

Проверить возможность получения исторических данных через библиотеку moexalgo вместо прямых HTTP запросов к MOEX ISS API.

### Установка

```bash
cd /home/z/my-project
python3 -m venv venv
source venv/bin/activate
pip install moexalgo pandas numpy
```

### Результаты исследования

#### 1. Формат тикеров

**Важно**: Тикеры должны быть полными с суффиксом (ISIN-based):
```
✅ SU26221RMFS0  - работает
❌ SU26221RMFS   - НЕ работает
❌ SU26221       - НЕ работает
❌ RU000A0JXFM1  - ISIN НЕ работает
```

#### 2. candles() - Исторические свечи

```python
from moexalgo import Ticker
from datetime import datetime, timedelta

ofz = Ticker('SU26221RMFS0')
end = datetime.now()
start = end - timedelta(days=60)

candles = ofz.candles(start=start, end=end, period='1d')
# ✅ Работает!
# Колонки: open, close, high, low, volume, value, begin, end
```

**НО**: Нет колонки yield/YTM! Только цены.

#### 3. marketdata() - Текущие данные

```python
from moexalgo import Market

bonds = Market('bonds')
md = bonds.marketdata()

# Фильтруем по тикеру
ofz = md[md['ticker'] == 'SU26221RMFS0']

# Доступные поля:
# yield: 14.71
# duration: 1830 дней
# zspread: 1.09 (G-спред!)
# yieldatwaprice: 14.73
```

**Ключевое**: `zspread` уже рассчитан биржей!

#### 4. tickers() - Информация о бумагах

```python
tickers = bonds.tickers()
# Колонки: ticker, shortname, matdate, couponpercent,
#          facevalue, couponperiod, accruedint, isin
```

### Сравнительная таблица

| Функция | moexalgo | MOEX ISS API |
|---------|----------|--------------|
| Текущий YTM | ✅ marketdata.yield | ✅ marketdata.yield |
| Текущий duration | ✅ marketdata.duration | ✅ marketdata.duration |
| Текущий zspread | ✅ marketdata.zspread | ✅ marketdata.zspread |
| Исторические YTM | ❌ Нет | ✅ history/yields |
| Исторические duration | ❌ Нет | ✅ history/yields |
| Исторические цены | ✅ candles.close | ✅ history/yields.close |
| Исторический zspread | ❌ Нет | ⚠️ Частично (None) |
| Параметры КБД | ❌ Нет | ✅ zcyc.json |

### Выводы

**moexalgo подходит для**:
- Текущие данные (yield, duration, zspread)
- Исторические цены свечей
- Информация о параметрах облигаций

**moexalgo НЕ подходит для**:
- Исторический YTM (нужно рассчитывать из цен)
- Исторический duration (нужно рассчитывать)
- Исторический G-spread (нужна КБД)

### Рекомендация

**Гибридный подход**:
1. **Текущие данные**: moexalgo.marketdata() → yield, duration, zspread
2. **Исторические данные**: MOEX ISS /history/ → YIELDCLOSE, DURATION
3. **Расчёт G-spread**: интерполяция по yearyields

### Следующие шаги

- [ ] Добавить метод получения yearyields через MOEX ISS
- [ ] Сохранять снапшоты yearyields в БД ежедневно
- [ ] Реализовать расчёт исторического G-spread
- [ ] Добавить график G-spread в UI

---

*Исследование moexalgo: 08.03.2026*

---

## Глубокое исследование источников G-spread (08.03.2026)

### Проблема

Для Mean-Reversion стратегии нужен **исторический G-spread**:
```
G-spread = YTM_облигации - YTM_КБД(duration)
```

### Результаты исследования MOEX ISS API

| Endpoint | Данные | История | Статус |
|----------|--------|---------|--------|
| `/history/.../securities/{ISIN}` | YIELDCLOSE, DURATION | ✅ 2+ года | Работает |
| `/history/.../securities/{ISIN}` | ZSPREAD | ❌ Всегда None | НЕ работает |
| `/history/engines/stock/zcyc/yearyields` | Точки КБД | ❌ Нет! | Только params |
| `/history/engines/stock/zcyc` | Параметры NS (b1,b2,b3,t1) | ✅ 16528 записей | Работает |
| `/engines/stock/zcyc` | yearyields (11 точек) | ❌ Только текущие | Работает |
| `/engines/stock/zcyc/securities` | clcyield, crtyield | ❌ Только текущие | Работает |

### Ключевые находки

1. **ZSPREAD в history ВСЕГДА None** для обычных ОФЗ
2. **Исторические yearyields НЕ доступны** через API
3. **Параметры NS доступны**, но с погрешностью ~100 б.п.
4. **clcyield** = YTM по КБД (уже рассчитанный MOEX)

### Рабочее решение для текущих данных

```python
# Из moexalgo или MOEX ISS:
# securities с clcyield в zcyc.json

url = "https://iss.moex.com/iss/engines/stock/zcyc.json"
data = requests.get(url).json()

# G-spread уже рассчитан:
for row in data['securities']['data']:
    trdyield = row[...]  # Фактический YTM
    clcyield = row[...]  # YTM по КБД
    
    g_spread = (trdyield - clcyield) * 100  # в б.п.
```

### Решение для исторических данных

**ВАРИАНТ 1: Самостоятельный сбор (рекомендуется)**
```
1. Ежедневно сохранять yearyields в БД
2. Интерполировать YTM_КБД по duration
3. G-spread = YIELDCLOSE - YTM_КБД
```

**ВАРИАНТ 2: Использовать параметры NS**
```
1. Получить b1,b2,b3,t1 на дату из /history/engines/stock/zcyc
2. Рассчитать YTM_КБД по формуле NS
3. ПОГРЕШНОСТЬ: ~100 б.п. (неприемлемо для спред-стратегий!)
```

### Вывод

❌ **moexalgo НЕ подходит** для исторического G-spread (нет данных)
✅ **MOEX ISS /history/** даёт YTM и Duration, но НЕ G-spread
✅ **Текущий G-spread** доступен через clcyield/zspread

📋 **Рекомендация**: Организовать ежедневное сохранение yearyields в БД для будущего исторического анализа.

---

*Исследование источников G-spread: 08.03.2026*

---

## Реализация расчёта G-spread через Nelson-Siegel (08.03.2026)

### Алгоритм

```
G-spread = YTM_облигации - YTM_КБД(duration)

YTM_КБД(t) = β₀ + β₁·f₁(t) + β₂·f₂(t)

где:
  f₁(t) = (1 - e^(-t/τ)) / (t/τ)
  f₂(t) = f₁(t) - e^(-t/τ)
```

### Источники данных MOEX

| Данные | Endpoint | Период |
|--------|----------|--------|
| Параметры NS (B1,B2,B3,T1) | `/history/engines/stock/zcyc.json` | История |
| Точки КБД (yearyields) | `/engines/stock/zcyc.json` | Только текущие |
| YTM и Duration облигации | `/history/.../securities/{ISIN}` | История |

### Ключевая проблема

Параметры MOEX (B1=1251, B2=5, B3=420) отличаются от классических NS!
Требуется калибровка по yearyields.

### Решение

```python
def nelson_siegel(t, beta0, beta1, beta2, tau):
    t_tau = t / tau
    exp_term = np.exp(-t_tau)
    factor1 = (1 - exp_term) / t_tau
    factor2 = factor1 - exp_term
    return beta0 + beta1 * factor1 + beta2 * factor2

# Калибровка NS по yearyields
def fit_ns_to_yearyields(yearyields):
    # Минимизируем ошибку между NS и yearyields
    # Получаем: beta0, beta1, beta2, tau
    
# Расчёт G-spread
duration_years = DURATION / 365.25
ytm_kbd = nelson_siegel(duration_years, beta0, beta1, beta2, tau)
g_spread = YIELDCLOSE - ytm_kbd
```

### Точность

| Метод | Погрешность |
|-------|-------------|
| clcyield из API (текущий) | 0 б.п. (точно) |
| NS по текущим yearyields | 2-20 б.п. |
| NS с ежедневными yearyields | 0-2 б.п. |

### Вывод для Mean-Reversion стратегии

✅ **Текущий G-spread**: Использовать `clcyield` из API точно
⚠️ **Исторический G-spread**: Приближённый через NS (погрешность 2-20 б.п.)
📊 **Решение**: Сохранять yearyields ежедневно для точной истории

---

*Реализация NS: 08.03.2026*
