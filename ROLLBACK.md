# Rollback Guide - Cleanup Duplicate Code

## Step 1: core/exceptions.py ✅ DELETED

**File:** `core/exceptions.py` (150 lines)
**Reason:** DEAD CODE - не импортируется нигде
**Status:** ✅ DELETED

**To rollback:**
```bash
git checkout f2c4303 -- core/exceptions.py
```

---

## Step 2: export/ ✅ DELETED

**Files:**
- `export/formatters.py`
- `export/signal_sender.py`
- `export/__init__.py` (emptied)

**Reason:** DEAD CODE - не используется в app.py
**Status:** ✅ DELETED

**To rollback:**
```bash
git checkout 0db0902 -- export/
```

---

## Step 3: modes/ ✅ DELETED

**Files:**
- `modes/base.py` (DailyMode)
- `modes/intraday.py` (IntradayMode)
- `modes/__init__.py` (emptied)

**Reason:** DEAD CODE - functionality moved to app.py
**Status:** ✅ DELETED

**To rollback:**
```bash
git checkout 7ad4893 -- modes/base.py modes/intraday.py modes/__init__.py
```

---

## Step 4: core/spread.py ✅ DELETED

**File:** `core/spread.py` (380 lines)
**Also deleted:** `tests/run_tests.py` (legacy test runner)
**Replacement:** `services/spread_calculator.py`
**Status:** ✅ DELETED

**To rollback:**
```bash
git checkout 3db8045 -- core/spread.py tests/run_tests.py core/__init__.py
```

---

## Step 5: core/signals.py ✅ DELETED

**File:** `core/signals.py` (389 lines)
**Replacement:** `services/spread_calculator.py::generate_signal()`
**Status:** ✅ DELETED

**To rollback:**
```bash
git checkout 5dd4d01 -- core/signals.py
```

---

## Step 6: core/backtest.py ✅ DELETED

**File:** `core/backtest.py` (576 lines)
**Reason:** Not used in app.py
**Status:** ✅ DELETED

**To rollback:**
```bash
git checkout 3553ccf -- core/backtest.py
```

---

## Step 7: components/signals.py (duplicate) ✅ FIXED

**Change:** Removed `calculate_spread_stats()` function
**Reason:** Duplicate of `components/metrics.py::calculate_spread_stats()`
**Status:** ✅ FIXED

**To rollback:**
```bash
git checkout 3553ccf -- components/signals.py tests/test_metrics_signals.py
```

---

## Summary

| Step | File | Lines Removed | Status |
|------|------|---------------|--------|
| 1 | core/exceptions.py | 150 | ✅ DELETED |
| 2 | export/formatters.py, signal_sender.py | 1100+ | ✅ DELETED |
| 3 | modes/base.py, intraday.py | 875 | ✅ DELETED |
| 4 | core/spread.py, tests/run_tests.py | 1138 | ✅ DELETED |
| 5 | core/signals.py | 388 | ✅ DELETED |
| 6 | core/backtest.py | 576 | ✅ DELETED |
| 7 | components/signals.py (dup) | 14 | ✅ FIXED |

**Total removed:** ~4200+ lines of DEAD CODE

---

## Updated core/__init__.py

After all deletions, `core/__init__.py` only exports:
```python
from .ytm_calculator import YTMCalculator

__all__ = ["YTMCalculator"]
```

---

*Last updated: 2026-03-15*
