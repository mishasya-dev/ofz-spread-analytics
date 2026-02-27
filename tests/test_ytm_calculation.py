"""
TDD Test: YTM calculation bug - settlement_date not passed

Bug: When calculating YTM for historical candles, settlement_date is not passed.
     This causes YTM to be calculated with today's date instead of candle date.

Case: OFZ 26207 (SU26207RMFS9) on 2025-02-27
- Price close: 86.579%
- MOEX YTM: 17.22%
- Calculated (WRONG): 26.6% (uses today's date)
- Calculated (CORRECT): 17.2% (uses candle date)

Run:
    python -m pytest tests/test_ytm_calculation.py -v
"""
import pytest
from datetime import date
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ytm_calculator import YTMCalculator, BondParams


class TestYTMSettlementDate:
    """Тесты для проверки правильной даты расчёта YTM"""

    @pytest.fixture
    def ofz_26207_params(self):
        """Параметры ОФЗ 26207"""
        return BondParams(
            isin="SU26207RMFS9",
            name="ОФЗ-ПД 26207",
            face_value=1000.0,
            coupon_rate=8.15,
            coupon_frequency=2,
            maturity_date=date(2027, 2, 3),
        )

    def test_ytm_with_correct_settlement_date(self, ofz_26207_params):
        """
        YTM с правильной датой расчёта должен совпадать с MOEX

        Дата: 2025-02-27
        Цена: 86.579%
        Ожидаемый YTM: ~17.22% (от MOEX)
        """
        calc = YTMCalculator()
        price = 86.579
        settlement = date(2025, 2, 27)
        expected_ytm = 17.22

        ytm = calc.calculate_ytm(price, ofz_26207_params, settlement_date=settlement)

        assert ytm is not None, "YTM should not be None"
        # Допустимая погрешность 0.5 п.п.
        assert abs(ytm - expected_ytm) < 0.5, f"YTM {ytm}% differs from expected {expected_ytm}%"

    def test_ytm_with_wrong_settlement_date(self, ofz_26207_params):
        """
        YTM с неправильной датой расчёта (сегодня) сильно отличается от MOEX

        Это демонстрирует баг: если не передать settlement_date,
        используется date.today() вместо даты свечи.
        """
        calc = YTMCalculator()
        price = 86.579
        expected_ytm = 17.22

        # Расчёт без settlement_date (использует сегодня)
        ytm_today = calc.calculate_ytm(price, ofz_26207_params)

        # YTM должен сильно отличаться от ожидаемого
        assert ytm_today is not None
        assert abs(ytm_today - expected_ytm) > 5, \
            f"YTM with today's date should differ significantly from {expected_ytm}%"

    def test_ytm_settlement_date_impact(self, ofz_26207_params):
        """
        Разные даты расчёта дают разный YTM

        При приближении к дате погашения YTM должен расти (если цена < номинала).
        """
        calc = YTMCalculator()
        price = 86.579

        ytm_2025 = calc.calculate_ytm(price, ofz_26207_params, settlement_date=date(2025, 2, 27))
        ytm_2026 = calc.calculate_ytm(price, ofz_26207_params, settlement_date=date(2026, 2, 27))

        assert ytm_2025 < ytm_2026, \
            f"YTM should increase as settlement approaches maturity: {ytm_2025}% vs {ytm_2026}%"


class TestYTMHistoricalCandles:
    """Тесты для проверки расчёта YTM исторических свечей"""

    @pytest.fixture
    def ofz_26207_params(self):
        return BondParams(
            isin="SU26207RMFS9",
            name="ОФЗ-ПД 26207",
            face_value=1000.0,
            coupon_rate=8.15,
            coupon_frequency=2,
            maturity_date=date(2027, 2, 3),
        )

    def test_candle_ytm_uses_candle_date(self, ofz_26207_params):
        """
        YTM для свечи должен рассчитываться на дату свечи, а не на сегодня

        После исправления _safe_calculate_ytm принимает settlement_date.
        """
        from api.moex_candles import CandleFetcher

        fetcher = CandleFetcher()

        # Получаем НКД
        accrued = fetcher._get_accrued_interest("SU26207RMFS9")

        # Цена на 2025-02-27
        price = 86.579
        candle_date = date(2025, 2, 27)
        expected_ytm = 17.22

        # Теперь _safe_calculate_ytm принимает settlement_date
        ytm_with_date = fetcher._safe_calculate_ytm(
            price, ofz_26207_params, accrued, settlement_date=candle_date
        )

        fetcher.close()

        # Результат должен быть близок к MOEX
        assert ytm_with_date is not None
        assert abs(ytm_with_date - expected_ytm) < 1.0, \
            f"YTM {ytm_with_date}% should be close to MOEX {expected_ytm}%"


def test_ytm_calculation_accuracy():
    """
    Независимый тест точности расчёта YTM

    Проверяем, что калькулятор даёт результат близкий к MOEX
    при правильных входных данных.
    """
    calc = YTMCalculator()

    bond = BondParams(
        isin="SU26207RMFS9",
        name="ОФЗ-ПД 26207",
        face_value=1000.0,
        coupon_rate=8.15,
        coupon_frequency=2,
        maturity_date=date(2027, 2, 3),
    )

    # Тест на несколько дат с известными YTM от MOEX
    test_cases = [
        # (дата, цена, ожидаемый YTM от MOEX)
        (date(2025, 2, 27), 86.579, 17.22),
        (date(2025, 2, 26), 85.988, 17.65),
        (date(2025, 2, 28), 86.799, 17.09),
    ]

    for settlement, price, expected_ytm in test_cases:
        ytm = calc.calculate_ytm(price, bond, settlement_date=settlement)
        assert ytm is not None, f"YTM is None for {settlement}"
        # Допустимая погрешность 1 п.п.
        assert abs(ytm - expected_ytm) < 1.0, \
            f"YTM on {settlement}: {ytm}% vs expected {expected_ytm}%"


def test_fetch_candles_ytm_accuracy():
    """
    Интеграционный тест: fetch_candles должен возвращать правильный YTM

    Проверяем весь пайплайн: свечи → расчёт YTM → сравнение с MOEX.
    """
    from api.moex_candles import CandleFetcher, CandleInterval
    from config import BondConfig

    bond_config = BondConfig(
        isin="SU26207RMFS9",
        name="ОФЗ-ПД 26207",
        coupon_rate=8.15,
        maturity_date="2027-02-03",
        issue_date="2012-02-22",
        face_value=1000,
        coupon_frequency=2,
        day_count_convention="ACT/ACT"
    )

    fetcher = CandleFetcher()

    # Получаем дневные свечи
    df = fetcher.fetch_candles(
        bond_config.isin,
        bond_config,
        CandleInterval.DAY,
        start_date=date(2025, 2, 25),
        end_date=date(2025, 2, 28)
    )

    fetcher.close()

    assert not df.empty, "DataFrame should not be empty"

    # Проверяем YTM на конкретную дату
    expected_ytm = {
        date(2025, 2, 25): 17.45,
        date(2025, 2, 26): 17.65,
        date(2025, 2, 27): 17.22,
        date(2025, 2, 28): 17.09,
    }

    for test_date, expected in expected_ytm.items():
        # Находим строку с этой датой
        mask = df.index.date == test_date
        if mask.any():
            row = df[mask].iloc[0]
            ytm = row.get('ytm_close')
            assert ytm is not None, f"YTM is None for {test_date}"
            assert abs(ytm - expected) < 1.5, \
                f"YTM on {test_date}: {ytm}% vs expected {expected}% (diff: {abs(ytm - expected):.2f}pp)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
