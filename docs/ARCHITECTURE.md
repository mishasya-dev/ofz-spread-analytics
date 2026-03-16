# OFZ Spread Analytics - Архитектура приложения

**Версия:** 2.0
**Дата обновления:** Январь 2025

---

## 📋 Содержание

1. [Обзор](#обзор)
2. [Структура проекта](#структура-проекта)
3. [Архитектурные слои](#архитектурные-слои)
4. [Ключевые компоненты](#ключевые-компоненты)
5. [Потоки данных](#потоки-данных)
6. [API модули](#api-модули)
7. [База данных](#база-данных)
8. [Кэширование](#кэширование)
9. [Расчёт YTM](#расчёт-ytm)
10. [Анализ коинтеграции](#анализ-коинтеграции)
11. [Генерация сигналов](#генерация-сигналов)
12. [UI компоненты](#ui-компоненты)
13. [Конфигурация](#конфигурация)
14. [Зависимости](#зависимости)

---

## Обзор

**OFZ Spread Analytics** — приложение для анализа спредов между облигациями ОФЗ с использованием данных Московской биржи (MOEX).

### Основные функции:
- Загрузка исторических и внутридневных данных YTM (Yield to Maturity)
- Расчёт спредов между парами облигаций
- Анализ коинтеграции (Engle-Granger test)
- Генерация торговых сигналов (mean reversion)
- Визуализация через интерактивные графики Plotly
- Экспорт сигналов (Telegram, Webhook, JSON)

### Технологический стек:
- **Backend:** Python 3.10+
- **Frontend:** Streamlit
- **Database:** SQLite
- **API:** MOEX ISS API
- **Visualisation:** Plotly
- **Analysis:** pandas, numpy, statsmodels

---

## Структура проекта

```
ofz-spread-analytics/
├── api/                    # Слой работы с внешними API
│   ├── __init__.py
│   ├── moex_client.py      # Единый HTTP-клиент с context manager
│   ├── moex_trading.py     # Проверка статуса торгов
│   ├── moex_bonds.py       # Загрузка списка облигаций
│   ├── moex_history.py     # Исторические YTM (YIELDCLOSE)
│   ├── moex_candles.py     # Свечи (OHLCV)
│   └── moex_zcyc.py        # Кривая бескупонной доходности (ZCYC)
│
├── core/                   # Бизнес-логика (без Streamlit)
│   ├── __init__.py
│   ├── ytm_calculator.py   # Расчёт YTM из цены
│   ├── spread.py           # Расчёт спредов
│   ├── signals.py          # Генерация торговых сигналов
│   ├── backtest.py         # Бэктестинг стратегий
│   ├── cointegration.py    # Анализ коинтеграции
│   ├── cointegration_service.py
│   ├── ofz_cache.py        # Кэш списка ОФЗ
│   ├── session.py          # Управление session_state
│   ├── types.py            # TypedDict и Protocol
│   └── exceptions.py       # Иерархия исключений
│
├── core/db/                # Слой работы с БД
│   ├── __init__.py
│   ├── connection.py       # Подключение, миграции
│   ├── facade.py           # DatabaseFacade
│   ├── bonds_repo.py       # Репозиторий облигаций
│   ├── ytm_repo.py         # Репозиторий YTM
│   ├── spreads_repo.py     # Репозиторий спредов
│   └── g_spread_repo.py    # Репозиторий G-spread
│
├── models/                 # Доменные модели
│   ├── __init__.py
│   └── bond.py             # Bond, BondPair dataclasses
│
├── services/               # Сервисы (бизнес-логика + API)
│   ├── __init__.py
│   ├── candle_service.py   # Загрузка свечей с YTM
│   ├── candle_processor_ytm_for_bonds.py  # Расчёт YTM из цен
│   ├── data_loader.py      # Загрузка исторических данных
│   ├── spread_calculator.py  # Расчёт статистики спредов
│   └── g_spread_calculator.py  # G-spread через КБД
│
├── components/             # UI компоненты Streamlit
│   ├── __init__.py
│   ├── sidebar.py          # Боковая панель
│   ├── charts.py           # Графики Plotly
│   ├── metrics.py          # Метрики
│   ├── signals.py          # Карточки сигналов
│   ├── header.py           # Заголовок
│   ├── bond_manager.py     # Выбор инструментов
│   ├── db_panel.py         # Панель БД
│   └── styles.py           # CSS стили
│
├── modes/                  # Режимы работы
│   ├── __init__.py
│   ├── base.py             # DailyMode
│   └── intraday.py         # IntradayMode
│
├── export/                 # Экспорт сигналов
│   ├── __init__.py
│   ├── signal_sender.py    # SignalSender
│   └── formatters.py       # JSON, Telegram, Webhook
│
├── utils/                  # Утилиты
│   ├── __init__.py
│   ├── bond_utils.py       # BondItem
│   └── action_logger.py    # Логирование действий
│
├── config.py               # Конфигурация приложения
├── app.py                  # Главная страница Streamlit
└── requirements.txt
```

---

## Архитектурные слои

```
┌──────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                       │
│  (Streamlit UI - app.py, components/)                        │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                       SERVICE LAYER                           │
│  (services/, modes/)                                         │
│  CandleService, DataLoader, SpreadCalculator                 │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                      BUSINESS LOGIC LAYER                     │
│  (core/ytm_calculator.py, core/spread.py, core/signals.py)    │
│  YTMCalculator, SpreadCalculator, SignalGenerator            │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                       DATA ACCESS LAYER                       │
│  (core/db/, models/)                                         │
│  DatabaseFacade, YTMRepository, BondsRepository              │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                      EXTERNAL API LAYER                       │
│  (api/)                                                      │
│  MOEXClient → MOEX ISS API                                   │
└──────────────────────────────────────────────────────────────┘
```

---

## Ключевые компоненты

### 1. MOEXClient (api/moex_client.py)

Единый HTTP-клиент для работы с MOEX ISS API.

```python
# Использование с context manager
with MOEXClient() as client:
    data = client.get_json("/engines/stock/markets/bonds.json")

# Параллельные запросы
with MOEXClient(max_workers=10) as client:
    futures = client.request_batch([
        ("/path1", {"param": "value"}),
        ("/path2", {"param": "value"}),
    ])
```

**Ключевые особенности:**
- Context manager для автоматического закрытия сессии
- Retry с exponential backoff
- Rate limiting (50 запросов/сек)
- Пул соединений
- Параллельные запросы через `request_batch()`

### 2. DatabaseFacade (core/db/facade.py)

Фасад для работы с базой данных, делегирует вызовы репозиториям.

```python
from core.db import get_db_facade

db = get_db_facade()
db.save_daily_ytm(isin, df)
ytm_df = db.load_daily_ytm(isin, start_date, end_date)
```

### 3. YTMCalculator (core/ytm_calculator.py)

Расчёт доходности к погашению методом Ньютона-Рафсона.

```python
calculator = YTMCalculator()
ytm = calculator.calculate_ytm(
    price_percent=75.5,  # 75.5% от номинала
    bond_params=bond_params,
    settlement_date=date.today(),
    accrued_interest=30.5
)
```

### 4. SignalGenerator (core/signals.py)

Генерация торговых сигналов на основе перцентилей спреда.

```python
generator = SignalGenerator()
signal = generator.generate_signal(
    spread_series,
    bond_long="RU000A1038V6",
    bond_short="RU000A1038W3"
)
# signal.signal_type: STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL
```

---

## Потоки данных

### 1. Загрузка исторических YTM

```
app.py → services/data_loader.py → api/moex_history.py → MOEXClient
                                    ↓
                     core/db/ytm_repo.py (кэш в SQLite)
```

### 2. Загрузка внутридневных свечей

```
app.py → services/candle_service.py → api/moex_candles.py → MOEXClient
                ↓
         services/candle_processor_ytm_for_bonds.py
                ↓
         core/ytm_calculator.py (расчёт YTM из цены)
                ↓
         core/db/ytm_repo.py (сохранение)
```

### 3. Расчёт спредов

```
app.py → core/spread.py → SpreadCalculator.calculate_spread_series()
           ↓
        services/spread_calculator.py → calculate_spread_stats()
           ↓
        components/charts.py → create_intraday_spread_chart()
```

---

## API модули

### moex_client.py

Базовый клиент для всех API запросов.

**Константы:**
- `MOEX_BASE_URL = "https://iss.moex.com/iss"`
- `MAX_RETRIES = 3`
- `RATE_LIMIT_REQUESTS = 50`
- `RATE_LIMIT_WINDOW = 1.0`

**Методы:**
- `get(url, params)` → Response
- `get_json(url, params)` → dict
- `request_batch(requests_list)` → List[Future]

### moex_bonds.py

Загрузка списка облигаций ОФЗ.

**Функции:**
- `fetch_all_bonds(client)` → List[Dict]
- `fetch_ofz_only(client)` → List[Dict]
- `filter_ofz_for_trading(bonds)` → List[Dict]
- `fetch_and_filter_ofz(client)` → List[Dict]

### moex_history.py

Исторические YTM (YIELDCLOSE).

**Функции:**
- `fetch_ytm_history(isin, start_date, client)` → DataFrame
- `fetch_multi_bonds_history(isins, start_date, client)` → Dict[str, DataFrame]
- `fetch_multi_bonds_history_parallel(isins, ...)` → Dict[str, DataFrame]
- `get_trading_data(secid, client)` → Dict

### moex_candles.py

Свечи (OHLCV).

**Функции:**
- `fetch_candles(isin, interval, start_date, end_date, client)` → DataFrame
- `fetch_candles_with_ytm(isin, bond, interval, days, client)` → DataFrame

### moex_zcyc.py

Кривая бескупонной доходности (ZCYC).

**Функции:**
- `fetch_ns_params_by_date(date, client)` → DataFrame
- `fetch_current_zcyc(client)` → Dict
- `get_zcyc_history_parallel(start_date, end_date, ...)` → DataFrame

---

## База данных

### Таблицы

| Таблица | Описание |
|---------|----------|
| `bonds` | Облигации (ISIN, параметры, избранное) |
| `daily_ytm` | Дневные YTM с MOEX (YIELDCLOSE) |
| `intraday_ytm` | Рассчитанные YTM из цен свечей |
| `candles` | Сырые свечи |
| `spreads` | Рассчитанные спреды |
| `cointegration_cache` | Кэш результатов коинтеграции |
| `ns_params` | Параметры Nelson-Siegel |
| `g_spreads` | G-spread к КБД |
| `zcyc_history_raw` | История ZCYC от MOEX |
| `cache_metadata` | Метаданные кэша |

### Репозитории

**BondsRepository:**
- `save(bond_data)` → bool
- `load(isin)` → Dict
- `get_all()` → List[Dict]
- `get_favorites()` → List[Dict]
- `set_favorite(isin, is_favorite)` → bool

**YTMRepository:**
- `save_daily_ytm(isin, df)` → int
- `load_daily_ytm(isin, start_date, end_date)` → DataFrame
- `save_intraday_ytm(isin, interval, df)` → int
- `load_intraday_ytm(isin, interval, ...)` → DataFrame
- `validate_ytm_accuracy(isin, interval, days)` → Dict

---

## Кэширование

### 1. Кэш БД (SQLite)

- Дневные YTM (`daily_ytm`)
- Внутридневные YTM (`intraday_ytm`)
- Параметры NS (`ns_params`)
- Результаты коинтеграции (`cointegration_cache`)
- История ZCYC (`zcyc_history_raw`)

### 2. Кэш Streamlit

```python
@st.cache_data(ttl=3600)
def fetch_historical_data(secid: str, days: int, ...):
    ...
```

### 3. Кэш списка ОФЗ (OFZCache)

```python
from core.ofz_cache import OFZCache

cache = OFZCache(ttl_seconds=86400)  # 24 часа
bonds = cache.get_ofz_list()  # Из БД или загрузка с MOEX
```

---

## Расчёт YTM

### Метод Ньютона-Рафсона

Решение уравнения:
```
Price = Sum(CF_i / (1 + YTM)^t_i)
```

**Класс YTMCalculator:**
- `calculate_ytm(price, bond_params, ...)` → YTM%
- `calculate_ytm_simple(price, ...)` → YTM% (упрощённая формула)
- `calculate_price_from_ytm(ytm, ...)` → цена%
- `calculate_duration(ytm, ...)` → дюрация (лет)

### T+1 Settlement

```python
def get_t1_settlement_date(trade_date: date) -> date:
    """
    Пятница → Понедельник (+3 дня)
    Остальные → +1 день
    """
```

---

## Анализ коинтеграции

### Engle-Granger Test

1. ADF тест на стационарность (оба ряда должны быть нестационарны)
2. Engle-Granger тест на коинтеграцию
3. Расчёт half-life mean reversion
4. Расчёт hedge ratio

```python
from core.cointegration import run_cointegration_analysis

result = run_cointegration_analysis(
    ytm1, ytm2,
    significance_level=0.05,
    bidirectional=True
)
# result.is_cointegrated, result.half_life, result.hedge_ratio
```

### Кэширование

```python
from core.cointegration_service import CointegrationService

service = CointegrationService(ttl_hours=24)
result = service.get_or_calculate(
    bond1_isin, bond2_isin, period_days,
    ytm1_series, ytm2_series
)
```

---

## Генерация сигналов

### Логика

```
Спред < P10 → STRONG_BUY (покупать спред)
Спред < P25 → BUY
P25 ≤ Спред ≤ P75 → NEUTRAL
Спред > P75 → SELL
Спред > P90 → STRONG_SELL
```

### SignalGenerator

```python
signal = generator.generate_signal(spread_series, isin_long, isin_short)
# signal.signal_type: STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL
# signal.direction: LONG_SHORT | SHORT_LONG | FLAT
# signal.confidence: 0.0-1.0
# signal.expected_return_bp: ожидаемый возврат к среднему
```

---

## UI компоненты

### sidebar.py

- `render_bond_selection()` — выбор пары облигаций
- `render_period_selector()` — период анализа
- `render_candle_interval_selector()` — интервал свечей
- `render_auto_refresh()` — автообновление

### charts.py

- `create_combined_ytm_chart()` — склеенный график YTM
- `create_intraday_spread_chart()` — график спреда
- `create_spread_analytics_chart()` — Z-Score анализ

### bond_manager.py

Модальное окно для выбора инструментов:
- Загрузка списка из кэша БД
- Галочки = избранное
- Сохранение в БД при "Готово"

---

## Конфигурация

### config.py

```python
@dataclass
class AppConfig:
    lookback_days: int = 500
    bonds: Dict[str, BondConfig] = field(default_factory=dict)
    spread_pairs: List[Tuple[str, str]] = field(default_factory=list)
    
    @dataclass
    class Signals:
        percentile_window: int = 252
        
    @dataclass  
    class Backtest:
        initial_capital: float = 1_000_000
        position_size_pct: float = 0.25
```

---

## Зависимости

```
# requirements.txt
streamlit>=1.30
pandas>=2.0
numpy>=1.24
plotly>=5.18
requests>=2.31
statsmodels>=0.14  # для коинтеграции
```

---

## Расширение приложения

### Добавление нового источника данных

1. Создать модуль в `api/new_source.py`
2. Использовать `MOEXClient` или создать свой клиент
3. Добавить функции загрузки данных
4. Интегрировать в `services/data_loader.py`

### Добавление нового режима

1. Создать класс режима в `modes/new_mode.py`
2. Реализовать методы `run()`, `refresh()`, `close()`
3. Добавить UI в `components/` или в `app.py`

### Добавление нового репозитория

1. Создать класс в `core/db/new_repo.py`
2. Добавить в `DatabaseFacade`
3. Экспортировать в `core/db/__init__.py`

---

## Метрики производительности

| Операция | Время | Примечание |
|----------|-------|------------|
| Загрузка дневных YTM (1 бонд, 365 дней) | ~0.5 сек | Из кэша: мгновенно |
| Параллельная загрузка 10 облигаций | ~2 сек | 10 parallel requests |
| Расчёт YTM для 100 свечей | ~0.1 сек | |
| Engle-Granger test | ~0.05 сек | |

---

## Безопасность

- Все HTTP запросы через `MOEXClient` с retry
- Параметризованные SQL запросы (защита от SQL injection)
- Валидация ISIN перед запросами
- Rate limiting для MOEX API

---

## Мониторинг и логирование

```python
import logging
logger = logging.getLogger(__name__)

# Уровни:
# DEBUG - детали загрузки, расчёты
# INFO - ключевые операции
# WARNING - отсутствующие данные, fallback
# ERROR - ошибки API, БД
```

Логи записываются в `logs/ofz_analytics.log`.

---

**Документ подготовлен на основе анализа исходного кода.**
**Для вопросов и предложений обращайтесь к разработчику.**
