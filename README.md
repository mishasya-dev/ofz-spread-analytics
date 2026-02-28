# OFZ Spread Analytics

Аналитика спредов доходности облигаций ОФЗ

## Описание

OFZ Spread Analytics — приложение для анализа of yield spreads between Russian government bonds (OFZ). It helps identify trading opportunities by tracking the spread between different maturity bonds.

## Features

### Unified 4-Chart Layout (v0.3.0)

The application displays 4 synchronized charts:

| Chart | Data | Description |
|-------|------|-------------|
| 1 | YTM Daily | YIELDCLOSE from MOEX | Yield history + statistics |
| 2 | Spread Daily | Calculated from YTM | Percentiles P10, P25, P75, P90 |
| 3 | YTM Combined | History + Candles | Combined chart |
| 4 | Spread Intraday | Candle data + reference | Daily percentiles as reference |

### Key Features

- **Real-time MOEX Data**: Direct connection to Moscow Exchange API
- **YTM Calculation**: Accurate yield-to-maturity calculation from candle prices
- **Spread Analysis**: Automatic spread calculation between any two bonds
- **Trading Signals**: BUY/SELL signals based on percentile analysis
- **Linked Zoom**: Synchronized zoom between paired charts
- **Database Storage**: SQLite for historical data
- **Bond Management**: Dynamic addition/removal of tracked bonds

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

Bonds are configured in `config.py`:

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

1. Select two bonds from the sidebar
2. Adjust analysis period (30 days - 2 years)
3. Select candle interval (1min/10min/1hour)
4. Charts will update automatically

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
│   └── signals.py          # Trading signal generation
├── components/
│   ├── charts.py           # Plotly chart builders
│   ├── sidebar.py          # Sidebar components
│   └── bond_manager.py     # Bond selection modal
├── models/
│   └── bond.py              # Bond dataclass model
└── tests/                  # Test suite (287 tests)
```

## Testing

```bash
# Run all tests
cd streamlit-app
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_ytm_calculation.py -v
```

### Test Coverage

| File | Tests | Description |
|------|-------|-------------|
| test_ytm_calculation.py | 6 | YTM calculation accuracy |
| test_app_integration.py | 30 | App integration tests |
| test_edge_cases.py | 25 | Edge cases (empty data, NaN) |
| test_linked_zoom.py | 22 | Linked zoom functionality |
| test_sidebar_v030.py | 36 | Sidebar components |
| test_charts_v030.py | 28 | Chart creation |
| test_models_bond.py | 26 | Bond dataclass |
| test_database.py | ~100 | Database operations |

## API Reference

### MOEX API Endpoints

- **Securities List**: `https://iss.moex.com/iss/engines/stock/markets/bonds/securities.json`
- **Historical YTM**: `https://iss.moex.com/iss/engines/stock/markets/bonds/boards/TQOB/securities/{ISIN}/candles.json`
- **Candles**: `https://iss.moex.com/iss/engines/stock/markets/bonds/boards/TQOB/securities/{ISIN}/candles.json`

### YTM Calculation

The application calculates YTM using Newton-Raphson method:

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

Developed for analysis of Russian government bond market.

## Links

- [MOEX ISS API Documentation](https://www.moex.com/a2193)
- [Streamlit Documentation](https://docs.streamlit.io)
