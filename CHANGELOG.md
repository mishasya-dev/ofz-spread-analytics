# Changelog

All notable changes to this project will be documented in this file.

## [v0.8.1] - 2026-03-17

### Added
- **Intraday Quotes Storage**: Automatic saving of current bond quotes during auto-refresh
  - New table `intraday_quotes` in SQLite database
  - Stores: trdyield, clcyield, g_spread_bp, bid/ask prices, duration
  - Uses `created_at` timestamp for uniqueness (MOEX updatetime doesn't change frequently)
- **Intraday Points on G-Spread Charts**: Real-time points displayed on G-Spread dashboard
  - Colored by Z-Score: RED (sell), GREEN (buy), YELLOW (neutral)
  - Z-Score calculated using historical rolling_mean/std
  - Works for both `create_g_spread_dashboard()` and `create_g_spread_chart_single()`

### Changed
- **Auto-refresh Flow**: Now saves intraday quotes to database before reloading
- **load_intraday_quotes()**: Uses `most_recent=True` by default (loads max tradedate)
  - Fixes issue where data saved at night couldn't be loaded next morning

### Fixed
- **Missing `updatetime` Column**: Added migration for intraday_quotes table
- **Date Mismatch Bug**: intraday data now loaded by MAX(tradedate) instead of date.today()

### Database
- **New Table**: `intraday_quotes` for storing current bond quotes
- **New Columns**: `updatetime`, `created_at` for proper timestamping

## [v0.8.0] - 2026-03-10

### Architecture
- **YTM Calculation Separation**: Split YTM calculation from MOEX API layer
  - `api/moex_candles.py` → only raw OHLCV data (no YTM calculation)
  - `services/candle_processor_ytm_for_bonds.py` → new `BondYTMProcessor` class
  - Single Responsibility Principle: API fetches, service calculates

### Changed
- **CandleFetcher.fetch_candles()**: Returns only raw candles (open, high, low, close, volume)
- **BondYTMProcessor**: New service for YTM calculation from candle prices
  - `add_ytm_to_candles(df, bond_config)` - add YTM column to DataFrame
  - `calculate_ytm_for_price(price, bond_config, trade_date)` - single price YTM
  - T+1 settlement date handling for OFZ bonds

### Improved
- **Cache Optimization**: Decoupled cache from period slider
  - `_fetch_all_historical_data(isin)` - caches by ISIN only (730 days)
  - `fetch_historical_data_cached(isin, days)` - filters by period (no cache miss)
  - Same pattern for candle data: cache by (ISIN, interval)
  - No unnecessary MOEX requests when changing period slider

### Tests
- **+14 New Tests**: `test_bond_ytm_processor.py` for BondYTMProcessor
- All 398 tests passing

## [v0.6.0] - 2026-03-04

### Changed
- **Code Cleanup**: Removed unused code from charts.py
  - Deleted `ChartBuilder` class and its methods
  - Deleted unused functions: `create_ytm_chart`, `create_spread_chart`, `create_signal_chart`, `create_backtest_chart`, `create_daily_ytm_chart`, `create_daily_spread_chart`, `calculate_future_range`
  - File reduced from 1512 to ~650 lines (-57%)
- **Tests Cleanup**: Removed obsolete test files
  - Deleted `tests/test_charts_v030.py` (functions removed)
  - Deleted `tests/test_edge_cases.py` (functions removed)
  - Deleted `tests/test_linked_zoom.py` (linked zoom removed earlier)

### Kept Functions (used in app.py)
- `create_combined_ytm_chart` - Combined YTM (history + candles)
- `create_intraday_spread_chart` - Intraday spread chart
- `create_spread_analytics_chart` - Z-Score analysis panel
- `apply_zoom_range` - Zoom utility

## [v0.5.6] - 2026-03-03

### Added
- **Data Period Info**: Display actual data period for each bond under Spread Analytics chart
  - Shows individual date ranges for both bonds
  - Shows combined period after inner join (determined by later-issued bond)

### Info
- Spread Analytics uses **inner join** on dates → only days with BOTH bonds' data are shown
- If one bond was issued later, the chart starts from that date regardless of requested period

## [v0.5.5] - 2026-03-03

### Fixed
- **Chart Not Updating**: Fixed Spread Analytics chart not redrawing when period slider changes
  - Added `key` parameter to `st.plotly_chart()` for forced redraw
  - Key includes period, bond ISINs, and data length for unique identification
- **Logging**: Added logging of data counts before chart creation for debugging

### Note
- MOEX returns 0 records for periods before bond issue date (expected behavior)
- For example, SU26254RMFS1 was issued 2025-10-22, so no data exists before that date

## [v0.5.4] - 2026-03-01

### Fixed
- **Period Slider Chart Update**: Fixed Spread Analytics chart not updating when increasing analysis period
  - Added explicit filtering by requested period before returning data
  - Added detailed logging for debugging data loading process
  - Fixed typo: `secin` → `secid` in save_daily_ytm call
- **Data Filtering**: Ensured returned DataFrame is always filtered by the requested `start_date`

### Changed
- Enhanced `fetch_historical_data_cached()` with comprehensive logging for troubleshooting

## [v0.5.3] - 2026-03-01

### Added
- **Test Suite**: New tests for period slider functionality
  - `tests/test_period_slider.py`: 9 tests for incremental loading logic
  - Tests for `fetch_historical_data_cached()` behavior
  - Tests for slider range validation (candle period slider)
  - Tests for edge case: hourly interval with 30-day period (min == max)

## [v0.5.2] - 2026-03-01

### Fixed
- **Period Slider Bug**: Fixed chart not updating when increasing analysis period
  - When period increased (e.g., 365 → 730 days), only missing historical data is now loaded incrementally
  - Data is properly merged with existing database records instead of being overwritten
- **Incremental Loading**: Added proper handling for `need_reload` case in `fetch_historical_data_cached()`

## [v0.5.1] - 2026-03-01

### Fixed
- **Slider Crash**: Fixed `StreamlitAPIException: Slider min_value must be less than the max_value` when candle period slider had equal min/max values (occurred with 1-hour interval and 30-day analysis period)
- **UI Improvement**: When slider range is degenerate (min >= max), show info message instead of crashing

## [v0.5.0] - 2026-03-01

### Added
- **Modular Architecture**: Refactored code into focused modules
  - `services/data_loader.py`: MOEX data fetching with caching
  - `services/spread_calculator.py`: Spread statistics and signal generation
  - `utils/bond_utils.py`: BondItem class and bond utilities
  - `core/db/facade.py`: DatabaseFacade using repository pattern
- **BondItem Class**: Unified bond representation for UI
- **Spread DataFrame Preparation**: `prepare_spread_dataframe()` function

### Changed
- **Code Organization**: Better separation of concerns
  - Services handle business logic and external APIs
  - Utils contain pure utility functions
  - Facade pattern for database access
- **Repository Pattern**: `DatabaseFacade` delegates to specialized repositories

### Technical
- All 364 tests passing
- No breaking changes to existing functionality
- Backward compatible with existing code

## [v0.4.8] - 2026-03-01

### Fixed
- **Test Fix**: Added `volume` and `value` columns to test fixtures for `intraday_ytm` table
- **Database Migration**: Ensured migration runs for new columns

### Changed
- **Test Count**: 364 tests passing (12 Playwright UI tests skipped)

## [v0.4.7] - 2026-03-01

### Performance
- **Chart Optimizations**: Removed white outline from volume bars, simplified hover templates

## [v0.4.6] - 2026-03-01

### Changed
- **Incremental Data Loading**: Only load missing period instead of full reload when increasing period slider
- **Optimization**: Use `pd.concat([new, old])` instead of delete + reload

## [v0.4.5] - 2026-03-01

### Fixed
- **Slider Bounce**: All sliders use `key` parameter for automatic session_state sync

## [v0.4.4] - 2026-03-01

### Fixed
- **Slider Sync**: Fixed slider bounce-back bug using `key` parameter pattern

## [v0.4.3] - 2026-03-01

### Fixed
- **Period Coverage**: Check if DB data covers requested period before returning cached data

## [v0.4.2] - 2026-03-01

### Fixed
- **Modal Bugs**: Fixed "Clear" button not working and shrinking bond list issues
- **Dynamic Key**: Added version counter for `st.data_editor` to force widget recreation
- **Favorite Toggle**: Use `set_favorite(isin, False)` instead of `delete_bond()`

## [v0.4.1] - 2026-03-01

### Added
- **Volume Bars**: Trading volume (value in rubles) displayed on YTM charts
- **Two Volume Traces**: Light blue for bond 1, light pink for bond 2

## [v0.4.0] - 2026-03-01

### Added
- **Volume Data**: Added `value` column to database for trading volume in rubles
- **MOEX API**: Fetch both `volume` (pieces) and `value` (rubles) from API

## [v0.3.1] - 2026-03-01

### Added
- **Spread Analytics Chart**: Professional two-panel chart with Z-Score analysis
  - Panel 1: YTM of both bonds (daily data)
  - Panel 2: Spread with Rolling Mean and ±Zσ boundaries
  - Configurable rolling window (5-90 days, default 30)
  - Configurable Z-Score threshold (1.0-3.0σ, default 2.0)
  - Color-coded signals: GREEN (BUY), RED (SELL), GRAY (Neutral)
  - Current point marker with Z-Score label
- **+11 New Tests**: Comprehensive tests for `create_spread_analytics_chart()`

### Changed
- **UI Simplified**: Removed redundant charts 1-2 (daily YTM and spread)
- **Chart Renumbering**: Intraday charts now numbered 2-3
- **Grid Style**: Changed to dotted grid on Spread Analytics chart

### Fixed
- **Slider Error**: Fixed `min_value == max_value` (30 == 30) crash
- **Duplicate Indices**: Fixed `cannot reindex on an axis with duplicate labels` error

## [v0.3.0] - 2026-02-28

### Added
- **Unified 4-Chart Layout**: Replaced daily/intraday mode with always-visible 4 synchronized charts
- **Linked Zoom**: Zoom on chart 1 automatically applies to chart 2,- **Single Period Slider**: One slider controls all charts (30-730 days)
- **Candle Interval Selector**: Choose 1min/10min/1hour for charts 3+4
- **NKD Calculation Fix**: NKD (accrued interest) now calculated for each candle date,- **+77 New Tests**: Added comprehensive test suite for v0.3.0

### Changed
- **Chart Colors**: History uses dashed lines, candles use solid lines
- **Future Range**: 15% extra space on X-axis for future dates
- **Spread Percentiles**: Intraday charts use daily percentiles as reference

### Fixed
- **YTM Divergence Bug**: Fixed NKD calculation that was using current NKD for all historical candles
- **Slider TypeError**: Fixed `format_func` parameter (not supported by `st.slider`)

## [v0.2.2] - 2026-02-27

### Added
- **Bond Management Modal**: Dynamic addition/removal of tracked bonds
- **Database Migration**: Automatic migration from config.py to SQLite

### Changed
- **MOEX API Optimization**: Batch requests instead of per-bond queries
- **Intraday Limits**: 1-hour candles now support 365 days (was 30)

## [v0.2.1] - 2026-02-27

### Fixed
- Import errors in `__init__.py`
- Test failures in `test_moex_bonds.py`

## [v0.2.0] - 2026-02-27

### Added
- **SQLite Database**: Persistent storage for bonds, YTM, and spreads
- **Bond Favorites**: Mark bonds as favorites in database
- **Dynamic Bond Selection**: Add/remove bonds from UI

### Changed
- **Refactored Architecture**: Separated concerns into api/, core/, components/

## [v0.1.0] - 2026-02-26

### Added
- **Initial Release**: Basic YTM tracking and spread analysis
- **MOEX Integration**: Real-time data from Moscow Exchange
- **Daily/Intraday Modes**: Two separate analysis modes
- **Trading Signals**: BUY/SELL signals based on spread percentiles
