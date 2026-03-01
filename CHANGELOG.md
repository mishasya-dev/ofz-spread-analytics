# Changelog

All notable changes to this project will be documented in this file.

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
