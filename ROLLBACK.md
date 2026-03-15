# Rollback Guide - Cleanup Duplicate Code

## Step 1: core/exceptions.py (DELETED)

**File:** `core/exceptions.py` (150 lines)
**Reason:** DEAD CODE - не импортируется нигде
**Dependencies:** None
**Status:** ✅ DELETED

**To rollback:**
```bash
git checkout HEAD~1 -- core/exceptions.py
```

---

## Step 2: export/ (PENDING)

**Files:**
- `export/formatters.py`
- `export/signal_sender.py`

---

## Step 3: modes/ (PENDING)

**Files:**
- `modes/base.py`
- `modes/intraday.py`

---

## Step 4: core/spread.py (PENDING)

**File:** `core/spread.py`
**Dependencies:** modes/, tests/run_tests.py
**Replacement:** `services/spread_calculator.py`

---

## Step 5: core/signals.py (PENDING)

**File:** `core/signals.py`
**Dependencies:** modes/, tests/run_tests.py
**Replacement:** `services/spread_calculator.py::generate_signal()`

---

## Step 6: core/backtest.py (PENDING)

**File:** `core/backtest.py`
**Dependencies:** core/__init__.py only

---

## Step 7: Update __init__.py files (PENDING)

---

## Step 8: Remove duplicate in components/signals.py (PENDING)
