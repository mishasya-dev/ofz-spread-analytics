# Changelog

All notable changes to this project will be documented in this file.

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
