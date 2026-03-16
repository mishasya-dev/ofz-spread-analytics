# OFZ Spread Analytics

Аналитика спредов доходности облигаций ОФЗ

## Описание

OFZ Spread Analytics — приложение для анализа yield spreads между российскими государственными облигациями (ОФЗ). Помогает находить торговые возможности, отслеживая спреды между облигациями с разными сроками погашения.

## Features

### Intraday Quotes (v0.8.1)

**Автоматическое сохранение текущих котировок:**
- При включённом автообновлении текущие котировки сохраняются в БД
- Точки отображаются на графиках G-Spread в реальном времени
- Z-Score рассчитывается на основе исторических rolling статистик
- Цветовая индикация: RED (SELL), GREEN (BUY), YELLOW (Neutral)

### G-Spread Analysis (v0.8.0)

**G-spread теперь берётся напрямую из MOEX ZCYC API:**
- `trdyield` — рыночная YTM облигации
- `clcyield` — теоретическая КБД от MOEX
- `G-spread = trdyield - clcyield` (уже рассчитан MOEX!)

Это обеспечивает **100% точность** по сравнению с самостоятельным расчётом:
- Nelson-Siegel: ~90-100 bp ошибка ❌
- Yearyields интерполяция: ~10-15 bp ошибка ❌  
- **MOEX ZCYC API: 0 bp ошибка** ✅

### 3-Chart Layout (v0.7.0)

Приложение отображает 3 синхронизированных графика:

| Chart | Data | Description |
|-------|------|-------------|
| 1 | Spread Analytics | YTM обеих облигаций + Z-Score анализ спреда |
| 2 | YTM Combined | История (дневные) + свечи (intraday) |
| 3 | G-Spread Dashboard | G-spread от MOEX с Z-score сигналами |

### Key Features

- **Real-time MOEX Data**: Прямое подключение к API Московской биржи
- **Exact G-Spread**: Точные значения G-spread из MOEX ZCYC API
- **YTM Calculation**: Точный расчёт доходности к погашению из цен свечей
- **Spread Analysis**: Автоматический расчёт спреда между любыми двумя облигациями
- **Z-Score Signals**: BUY/SELL сигналы на основе Z-Score анализа
- **Database Storage**: SQLite для исторических данных с умным кэшированием
- **Holiday Detection**: Автоматическое определение праздников (нет лишних API запросов)
- **Bond Management**: Динамическое добавление/удаление отслеживаемых облигаций

## Installation

```bash
# Clone repository
git clone https://github.com/mishasya-dev/ofz-spread-analytics.git
cd ofz-spread-analytics

# Install dependencies
pip install -r requirements.txt

# Run application
streamlit run streamlit-app/app.py
```

## Configuration

Облигации настраиваются через UI или в `config.py`:

### Adding a New Bond

```python
from config import BondConfig

# Add bond to config
bonds["SU26255RMFS1"] = BondConfig(
    isin="SU26255RMFS1",
    name="ОФЗ 26225",
    maturity_date="2034-05-10",
    coupon_rate=7.25,
    face_value=1000,
    coupon_frequency=2,
)
```

## Usage

1. Выберите две облигации из сайдбара
2. Настройте период анализа (30 дней - 2 года)
3. Выберите интервал свечей (1min/10min/1hour)
4. Графики обновятся автоматически

## Architecture (v0.8.0)

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

### Caching Strategy

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

## Project Structure

```
streamlit-app/
├── app.py                      # Main Streamlit application
├── config.py                   # Bond configuration
├── api/
│   ├── moex_zcyc.py            # ZCYC API (G-spread from MOEX)
│   ├── moex_bonds.py           # Bond list from MOEX
│   ├── moex_candles.py         # Raw candle data (OHLCV only)
│   ├── moex_history.py         # Historical YTM data
│   └── moex_trading.py         # Trading status
├── services/
│   ├── g_spread_calculator.py  # G-spread stats & signals
│   ├── candle_processor_ytm_for_bonds.py  # YTM calculation
│   ├── candle_service.py       # Candle data management
│   └── data_loader.py          # Data loading with caching
├── core/
│   ├── db/
│   │   ├── connection.py       # SQLite connection + tables
│   │   ├── g_spread_repo.py    # ZCYC cache + empty dates
│   │   ├── ytm_repo.py         # YTM storage
│   │   └── bonds_repo.py       # Bond metadata
│   ├── cointegration.py        # Cointegration analysis
│   └── cointegration_service.py
├── components/
│   ├── charts.py               # Plotly chart builders
│   ├── sidebar.py              # Sidebar components
│   └── bond_manager.py         # Bond selection modal
└── tests/                      # Test suite
```

## Testing

```bash
# Run all tests
cd streamlit-app
python -m pytest tests/ -v

# Run ZCYC tests
python test_zcyc.py
```

## API Reference

### MOEX ZCYC API

```python
from api.moex_zcyc import get_zcyc_data_for_date, get_zcyc_history_parallel
from datetime import date

# G-spread за конкретную дату
df = get_zcyc_data_for_date(date(2026, 3, 10))
# Returns: date, secid, trdyield, clcyield, duration_days, g_spread_bp

# История G-spread с кэшированием
df = get_zcyc_history_parallel(
    start_date=date(2025, 3, 1),
    end_date=date(2026, 3, 10),
    isin="SU26247RMFS5",
    use_cache=True,
    max_workers=5
)
```

### G-Spread Signals

```python
from services.g_spread_calculator import calculate_g_spread_stats, generate_g_spread_signal

# Статистика
stats = calculate_g_spread_stats(df['g_spread_bp'])
# Returns: mean, median, std, p10, p25, p75, p90, current

# Торговый сигнал
signal = generate_g_spread_signal(
    current_spread=stats['current'],
    p10=stats['p10'],
    p25=stats['p25'],
    p75=stats['p75'],
    p90=stats['p90']
)
# Returns: signal (BUY/SELL/HOLD), action, reason, color, strength
```

## Database Tables

| Table | Purpose |
|-------|---------|
| `zcyc_cache` | Кэш ZCYC данных (G-spread) |
| `zcyc_empty_dates` | Праздники (нет торгов) |
| `g_spreads` | Рассчитанные G-spread |
| `intraday_quotes` | Текущие котировки (auto-saved) |
| `daily_ytm` | Дневные YTM |
| `intraday_ytm` | Внутридневные YTM |
| `cointegration_cache` | Кэш коинтеграции |

## License

MIT License

## Author

Разработано для анализа рынка российских государственных облигаций.

## Links

- [MOEX ISS API Documentation](https://www.moex.com/a2193)
- [Streamlit Documentation](https://docs.streamlit.io)
