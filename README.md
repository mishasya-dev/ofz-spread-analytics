# OFZ Spread Analytics

Аналитика спредов доходности облигаций ОФЗ

## Описание

OFZ Spread Analytics — приложение для анализа yield spreads между российскими государственными облигациями (ОФЗ). Помогает находить торговые возможности, отслеживая спреды между облигациями с разными сроками погашения.

## Features

### 3-Chart Layout (v0.6.0)

Приложение отображает 3 синхронизированных графика:

| Chart | Data | Description |
|-------|------|-------------|
| 1 | Spread Analytics | YTM обеих облигаций + Z-Score анализ спреда |
| 2 | YTM Combined | История (дневные) + свечи (intraday) |
| 3 | Spread Intraday | Intraday спред с перцентилями от дневных данных |

### Key Features

- **Real-time MOEX Data**: Прямое подключение к API Московской биржи
- **YTM Calculation**: Точный расчёт доходности к погашению из цен свечей
- **Spread Analysis**: Автоматический расчёт спреда между любыми двумя облигациями
- **Z-Score Signals**: BUY/SELL сигналы на основе Z-Score анализа
- **Database Storage**: SQLite для исторических данных
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

## Project Structure

```
streamlit-app/
├── app.py                 # Main Streamlit application
├── config.py              # Bond configuration
├── api/
│   ├── moex_bonds.py      # Bond list from MOEX
│   ├── moex_candles.py    # Candle data + YTM calculation
│   ├── moex_history.py    # Historical YTM data
│   └── moex_trading.py    # Trading status
├── core/
│   ├── database.py        # SQLite database manager
│   ├── ytm_calculator.py  # YTM calculation engine
│   ├── spread.py           # Spread calculations
│   ├── signals.py          # Trading signal generation
│   └── cointegration.py    # Cointegration analysis
├── components/
│   ├── charts.py           # Plotly chart builders (4 functions)
│   ├── sidebar.py          # Sidebar components
│   └── bond_manager.py     # Bond selection modal
├── models/
│   └── bond.py              # Bond dataclass model
└── tests/                  # Test suite
```

## Testing

```bash
# Run all tests
cd streamlit-app
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_spread_analytics_chart.py -v
```

### Test Coverage

| File | Tests | Description |
|------|-------|-------------|
| test_spread_analytics_chart.py | 15 | Spread Analytics chart |
| test_hover_label.py | 8 | Hover label structure |
| test_cointegration.py | 12 | Cointegration analysis |
| test_sidebar_v030.py | 36 | Sidebar components |
| test_database.py | ~100 | Database operations |
| test_ytm_calculation.py | 6 | YTM calculation accuracy |

## Charts API

### Available Functions (components/charts.py)

```python
# Spread Analytics with Z-Score
fig = create_spread_analytics_chart(
    df1, df2,                    # YTM DataFrames
    bond1_name, bond2_name,      # Bond names
    window=30,                    # Rolling window (days)
    z_threshold=2.0              # Z-Score threshold
)

# Combined YTM chart (history + candles)
fig = create_combined_ytm_chart(
    daily_df1, daily_df2,        # Daily YTM data
    intraday_df1, intraday_df2,  # Intraday candle data
    bond1_name, bond2_name,
    candle_days=30               # Candle period
)

# Intraday spread chart
fig = create_intraday_spread_chart(
    spread_df,                   # Spread DataFrame
    daily_stats                  # Daily percentiles
)

# Apply zoom range
fig = apply_zoom_range(fig, x_range)
```

## API Reference

### MOEX API Endpoints

- **Securities List**: `https://iss.moex.com/iss/engines/stock/markets/bonds/securities.json`
- **Historical YTM**: `https://iss.moex.com/iss/engines/stock/markets/bonds/boards/TQOB/securities/{ISIN}/candles.json`
- **Candles**: `https://iss.moex.com/iss/engines/stock/markets/bonds/boards/TQOB/securities/{ISIN}/candles.json`

### YTM Calculation

Приложение рассчитывает YTM методом Ньютона-Рафсона:

```python
from core.ytm_calculator import YTMCalculator

calculator = YTMCalculator()
ytm = calculator.calculate_ytm(
    price_percent=95.5,  # Price as % of face value
    bond_params=bond_params,
    settlement_date=date(2025, 2, 28),
    accrued_interest=13.43  # Current NKD
)
```

## License

MIT License

## Author

Разработано для анализа рынка российских государственных облигаций.

## Links

- [MOEX ISS API Documentation](https://www.moex.com/a2193)
- [Streamlit Documentation](https://docs.streamlit.io)
