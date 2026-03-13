"""
Тесты для анализа коинтеграции

Unit тесты:
- synchronize_series()
- clean_series()
- adf_test()
- run_cointegration_analysis()
- calculate_z_score()
- get_recommendation()

Legacy тесты (обратная совместимость):
- CointegrationAnalyzer class

Integration тесты:
- Полный анализ пары облигаций
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSynchronizeSeries:
    """Тесты функции синхронизации рядов"""

    def test_perfect_match(self):
        """Тест: идеальное совпадение дат"""
        from core.cointegration import synchronize_series
        
        dates = pd.date_range('2024-01-01', periods=100)
        ytm1 = pd.Series(np.random.randn(100), index=dates)
        ytm2 = pd.Series(np.random.randn(100), index=dates)
        
        sync1, sync2 = synchronize_series(ytm1, ytm2)
        
        assert len(sync1) == 100
        assert len(sync2) == 100
        assert (sync1.index == sync2.index).all()

    def test_partial_overlap(self):
        """Тест: частичное пересечение дат"""
        from core.cointegration import synchronize_series
        
        dates1 = pd.date_range('2024-01-01', periods=100)
        dates2 = pd.date_range('2024-01-20', periods=100)
        
        ytm1 = pd.Series(np.random.randn(100), index=dates1)
        ytm2 = pd.Series(np.random.randn(100), index=dates2)
        
        sync1, sync2 = synchronize_series(ytm1, ytm2)
        
        # Должны остаться только пересекающиеся даты
        assert len(sync1) < 100
        assert len(sync2) < 100
        assert len(sync1) == len(sync2)

    def test_no_overlap(self):
        """Тест: нет пересечения дат"""
        from core.cointegration import synchronize_series
        
        dates1 = pd.date_range('2024-01-01', periods=30)
        dates2 = pd.date_range('2024-03-01', periods=30)
        
        ytm1 = pd.Series(np.random.randn(30), index=dates1)
        ytm2 = pd.Series(np.random.randn(30), index=dates2)
        
        sync1, sync2 = synchronize_series(ytm1, ytm2)
        
        assert len(sync1) == 0
        assert len(sync2) == 0

    def test_nan_handling(self):
        """Тест: обработка NaN значений"""
        from core.cointegration import synchronize_series
        
        dates = pd.date_range('2024-01-01', periods=50)
        ytm1 = pd.Series(np.random.randn(50), index=dates)
        ytm2 = pd.Series(np.random.randn(50), index=dates)
        
        # Добавляем NaN
        ytm1.iloc[10:15] = np.nan
        ytm2.iloc[20:25] = np.nan
        
        sync1, sync2 = synchronize_series(ytm1, ytm2)
        
        # NaN должны быть удалены
        assert not sync1.isna().any()
        assert not sync2.isna().any()


class TestCointegrationResult:
    """Тесты dataclass CointegrationResult"""
    
    def test_result_creation(self):
        """Тест: создание результата"""
        from core.cointegration import CointegrationResult
        
        result = CointegrationResult(
            is_cointegrated=True,
            pvalue=0.0234,
            coint_statistic=-3.5,
            critical_values={'1%': -3.9, '5%': -3.3, '10%': -3.0},
            n_observations=456
        )
        
        assert result.is_cointegrated == True
        assert result.pvalue == 0.0234
        assert result.n_observations == 456
    
    def test_result_to_dict(self):
        """Тест: сериализация в словарь"""
        from core.cointegration import CointegrationResult
        
        result = CointegrationResult(
            is_cointegrated=True,
            pvalue=0.0234,
            coint_statistic=-3.5,
            n_observations=456,
            half_life=29.5,
            hedge_ratio=1.05
        )
        
        d = result.to_dict()
        
        assert d['is_cointegrated'] == True
        assert d['half_life'] == 29.5
        assert d['hedge_ratio'] == 1.05


class TestCleanSeries:
    """Тесты функции clean_series"""
    
    def test_sorting(self):
        """Тест: сортировка по дате"""
        from core.cointegration import clean_series
        
        dates = pd.date_range('2024-01-01', periods=10)
        values = np.arange(10)
        
        # Перемешиваем индекс
        s = pd.Series(values[::-1], index=dates[::-1])
        
        cleaned = clean_series(s)
        
        # Должен быть отсортирован
        assert cleaned.index.is_monotonic_increasing
    
    def test_duplicate_removal(self):
        """Тест: удаление дубликатов дат"""
        from core.cointegration import clean_series
        
        dates = list(pd.date_range('2024-01-01', periods=5)) + [pd.Timestamp('2024-01-03')]
        values = [1, 2, 3, 4, 5, 99]  # 99 - дубликат для 2024-01-03
        
        s = pd.Series(values, index=dates)
        cleaned = clean_series(s)
        
        # Дубликат удалён, осталось 5 значений
        assert len(cleaned) == 5
        # Последнее значение для 2024-01-03 должно быть 99
        assert cleaned.loc[pd.Timestamp('2024-01-03')] == 99


class TestADFTest:
    """Тесты функции adf_test"""
    
    def test_stationary_series(self):
        """Тест: стационарный ряд"""
        from core.cointegration import adf_test
        
        np.random.seed(456)
        dates = pd.date_range(end=pd.Timestamp.now(), periods=200, freq='D')
        series = pd.Series(14 + np.random.randn(200) * 0.1, index=dates)
        
        result = adf_test(series)
        
        assert 'pvalue' in result
        assert result['is_stationary'] == True
    
    def test_random_walk(self):
        """Тест: случайное блуждание (нестационарный)"""
        from core.cointegration import adf_test
        
        np.random.seed(123)
        dates = pd.date_range(end=pd.Timestamp.now(), periods=200, freq='D')
        series = pd.Series(14 + np.cumsum(np.random.randn(200) * 0.1), index=dates)
        
        result = adf_test(series)
        
        assert 'pvalue' in result
    
    def test_insufficient_data(self):
        """Тест: недостаточно данных"""
        from core.cointegration import adf_test
        
        dates = pd.date_range('2024-01-01', periods=10)
        series = pd.Series(np.random.randn(10), index=dates)
        
        result = adf_test(series)
        
        assert 'error' in result


class TestRunCointegrationAnalysis:
    """Тесты функции run_cointegration_analysis"""

    @pytest.fixture
    def cointegrated_pair(self):
        """Генерация коинтегрированной пары"""
        np.random.seed(42)
        n = 200
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq='D')
        
        common = np.cumsum(np.random.randn(n) * 0.5)
        ytm1 = 14 + common + np.cumsum(np.random.randn(n) * 0.3)
        ytm2 = 13 + common * 0.8 + np.cumsum(np.random.randn(n) * 0.3)
        
        return pd.Series(ytm1, index=dates), pd.Series(ytm2, index=dates)

    def test_result_structure(self, cointegrated_pair):
        """Тест: структура результата"""
        from core.cointegration import run_cointegration_analysis
        
        ytm1, ytm2 = cointegrated_pair
        result = run_cointegration_analysis(ytm1, ytm2)
        
        assert hasattr(result, 'is_cointegrated')
        assert hasattr(result, 'pvalue')
        assert hasattr(result, 'coint_statistic')
        assert hasattr(result, 'n_observations')
        assert hasattr(result, 'both_nonstationary')

    def test_bidirectional_better(self):
        """Тест: bidirectional выбирает лучший p-value"""
        from core.cointegration import run_cointegration_analysis
        
        np.random.seed(999)
        n = 200
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq='D')
        
        common = np.cumsum(np.random.randn(n) * 0.5)
        ytm1 = pd.Series(14 + common + np.random.randn(n) * 0.1, index=dates)
        ytm2 = pd.Series(13 + common * 1.5 + np.random.randn(n) * 0.1, index=dates)
        
        # Bidirectional
        result_bi = run_cointegration_analysis(ytm1, ytm2, bidirectional=True)
        # Unidirectional
        result_uni = run_cointegration_analysis(ytm1, ytm2, bidirectional=False)
        
        # Bidirectional должен быть не хуже
        assert result_bi.pvalue <= result_uni.pvalue + 0.001

    def test_insufficient_data(self):
        """Тест: недостаточно данных"""
        from core.cointegration import run_cointegration_analysis
        
        dates = pd.date_range('2024-01-01', periods=20)
        ytm1 = pd.Series(np.random.randn(20), index=dates)
        ytm2 = pd.Series(np.random.randn(20), index=dates)
        
        result = run_cointegration_analysis(ytm1, ytm2)
        
        assert result.error is not None
        assert 'Недостаточно' in result.error

    def test_half_life_calculated(self, cointegrated_pair):
        """Тест: half-life рассчитывается для коинтегрированной пары"""
        from core.cointegration import run_cointegration_analysis
        
        ytm1, ytm2 = cointegrated_pair
        result = run_cointegration_analysis(ytm1, ytm2)
        
        # Если коинтегрированы, half-life должен быть рассчитан
        if result.is_cointegrated:
            assert result.half_life is not None

    def test_hedge_ratio_calculated(self, cointegrated_pair):
        """Тест: hedge ratio рассчитывается для коинтегрированной пары"""
        from core.cointegration import run_cointegration_analysis
        
        ytm1, ytm2 = cointegrated_pair
        result = run_cointegration_analysis(ytm1, ytm2)
        
        if result.is_cointegrated:
            assert result.hedge_ratio is not None


class TestCalculateZScore:
    """Тесты функции calculate_z_score"""
    
    def test_z_score_values(self):
        """Тест: значения Z-score"""
        from core.cointegration import calculate_z_score
        
        np.random.seed(42)
        spread = pd.Series(np.random.randn(100) * 10, index=range(100))
        
        z = calculate_z_score(spread, window=20)
        
        # Z-score должен быть центрирован вокруг 0
        assert abs(z.dropna().mean()) < 0.5
    
    def test_z_score_with_trend(self):
        """Тест: Z-score с трендом показывает отклонения"""
        from core.cointegration import calculate_z_score
        
        # Спред с трендом - Z-score показывает направление
        spread = pd.Series(np.arange(100) + np.random.randn(100) * 2, index=range(100))
        
        z = calculate_z_score(spread, window=20)
        
        # Z-score должен показывать отклонения от среднего
        # С трендом вверх - Z-score положительный
        assert z.max() > 1.0
        assert z.dropna().mean() > 0


class TestGetRecommendation:
    """Тесты функции get_recommendation"""
    
    def test_not_cointegrated(self):
        """Тест: не коинтегрированы"""
        from core.cointegration import get_recommendation
        
        rec = get_recommendation(is_cointegrated=False, both_nonstationary=True, half_life=None)
        
        assert rec['risk'] == 'high'
        assert 'не коинтегрирована' in rec['reason'].lower()
    
    def test_stationary_input(self):
        """Тест: стационарные ряды"""
        from core.cointegration import get_recommendation
        
        rec = get_recommendation(is_cointegrated=True, both_nonstationary=False, half_life=10)
        
        assert rec['risk'] == 'high'
        assert 'стационарн' in rec['reason'].lower()
    
    def test_fast_mean_reversion(self):
        """Тест: быстрая mean reversion"""
        from core.cointegration import get_recommendation
        
        rec = get_recommendation(is_cointegrated=True, both_nonstationary=True, half_life=5)
        
        assert rec['risk'] == 'low'
        assert 'быстрая' in rec['reason'].lower()
    
    def test_slow_mean_reversion(self):
        """Тест: медленная mean reversion"""
        from core.cointegration import get_recommendation
        
        rec = get_recommendation(is_cointegrated=True, both_nonstationary=True, half_life=60)
        
        assert rec['risk'] == 'high'
        assert 'медленная' in rec['reason'].lower()


class TestCointegrationAnalyzer:
    """Тесты legacy класса CointegrationAnalyzer (обратная совместимость)"""

    @pytest.fixture
    def analyzer(self):
        from core.cointegration import CointegrationAnalyzer
        return CointegrationAnalyzer(significance_level=0.05)

    @pytest.fixture
    def cointegrated_pair(self):
        """Генерация коинтегрированной пары"""
        np.random.seed(42)
        n = 200
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq='D')
        
        common = np.cumsum(np.random.randn(n) * 0.5)
        ytm1 = 14 + common + np.cumsum(np.random.randn(n) * 0.3)
        ytm2 = 13 + common * 0.8 + np.cumsum(np.random.randn(n) * 0.3)
        
        return pd.Series(ytm1, index=dates), pd.Series(ytm2, index=dates)

    @pytest.fixture
    def random_walk_pair(self):
        """Генерация независимых случайных блужданий"""
        np.random.seed(123)
        n = 200
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq='D')
        
        ytm1 = 14 + np.cumsum(np.random.randn(n) * 0.1)
        ytm2 = 13 + np.cumsum(np.random.randn(n) * 0.1)
        
        return pd.Series(ytm1, index=dates), pd.Series(ytm2, index=dates)

    @pytest.fixture
    def stationary_series(self):
        """Генерация стационарного ряда"""
        np.random.seed(456)
        n = 200
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq='D')
        ytm = 14 + np.random.randn(n) * 0.1
        return pd.Series(ytm, index=dates)

    def test_initialization(self, analyzer):
        """Тест: инициализация"""
        assert analyzer.significance_level == 0.05

    def test_adf_test_structure(self, analyzer, random_walk_pair):
        """Тест: структура результата ADF теста"""
        ytm1, _ = random_walk_pair
        
        result = analyzer.adf_test(ytm1)
        
        assert 'test' in result
        assert 'pvalue' in result
        assert 'is_stationary' in result

    def test_engle_granger_cointegrated(self, analyzer, cointegrated_pair):
        """Тест: Engle-Granger на коинтегрированной паре"""
        ytm1, ytm2 = cointegrated_pair
        
        result = analyzer.engle_granger_test(ytm1, ytm2)
        
        assert 'test' in result
        assert 'pvalue' in result
        assert 'is_cointegrated' in result
        assert 'both_nonstationary' in result

    def test_half_life_calculation(self, analyzer, cointegrated_pair):
        """Тест: расчёт half-life"""
        ytm1, ytm2 = cointegrated_pair
        
        spread = (ytm1 - ytm2) * 100
        half_life = analyzer.calculate_half_life(spread)
        
        if half_life is not None:
            assert half_life > 0 or half_life == float('inf')

    def test_hedge_ratio(self, analyzer, cointegrated_pair):
        """Тест: расчёт hedge ratio"""
        ytm1, ytm2 = cointegrated_pair
        
        hedge_ratio = analyzer.calculate_hedge_ratio(ytm1, ytm2)
        
        if hedge_ratio is not None:
            assert isinstance(hedge_ratio, (int, float))

    def test_analyze_pair_structure(self, analyzer, cointegrated_pair):
        """Тест: структура результата analyze_pair"""
        ytm1, ytm2 = cointegrated_pair
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        assert 'n_observations' in result
        assert 'engle_granger' in result
        assert 'is_cointegrated' in result
        assert 'half_life' in result
        assert 'hedge_ratio' in result
        assert 'recommendation' in result

    def test_analyze_pair_recommendation(self, analyzer, cointegrated_pair):
        """Тест: рекомендация в результате анализа"""
        ytm1, ytm2 = cointegrated_pair
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        rec = result['recommendation']
        assert 'strategy' in rec
        assert 'reason' in rec
        assert 'risk' in rec
        assert rec['risk'] in ['low', 'medium', 'high']

    def test_duplicate_dates_handling(self, analyzer):
        """Тест: обработка дубликатов дат"""
        np.random.seed(111)
        dates = pd.date_range('2024-01-01', periods=100)
        
        dates_with_dupes = list(dates) + [dates[50], dates[75]]
        values = np.random.randn(102)
        
        ytm1 = pd.Series(values[:100], index=dates)
        ytm2 = pd.Series(values, index=dates_with_dupes)
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        assert 'n_observations' in result


class TestIntegrationWithYTM:
    """Интеграционные тесты с реальными данными YTM"""

    @pytest.fixture
    def sample_ytm_data(self):
        """Создание тестовых YTM данных"""
        np.random.seed(42)
        n = 365
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq='D')
        
        trend1 = np.cumsum(np.random.randn(n) * 0.01)
        ytm1 = 14 + trend1 + np.random.randn(n) * 0.05
        ytm2 = 13 + trend1 * 0.8 + np.random.randn(n) * 0.05
        
        df1 = pd.DataFrame({'ytm': ytm1}, index=dates)
        df2 = pd.DataFrame({'ytm': ytm2}, index=dates)
        
        return df1, df2

    def test_full_analysis_workflow(self, sample_ytm_data):
        """Тест: полный workflow анализа"""
        from core.cointegration import run_cointegration_analysis
        
        df1, df2 = sample_ytm_data
        
        result = run_cointegration_analysis(df1['ytm'], df2['ytm'])
        
        assert result.error is None
        assert result.n_observations > 0

    def test_analysis_with_missing_dates(self, sample_ytm_data):
        """Тест: анализ с пропусками в датах"""
        from core.cointegration import run_cointegration_analysis
        
        df1, df2 = sample_ytm_data
        
        # Удаляем некоторые даты
        df1_missing = df1.drop(df1.index[50:60])
        df2_missing = df2.drop(df2.index[80:90])
        
        result = run_cointegration_analysis(df1_missing['ytm'], df2_missing['ytm'])
        
        assert result.n_observations > 0

    def test_analysis_with_short_period(self):
        """Тест: анализ на коротком периоде"""
        from core.cointegration import run_cointegration_analysis
        
        dates = pd.date_range(end=pd.Timestamp.now(), periods=20, freq='D')
        ytm1 = pd.Series(np.random.randn(20), index=dates)
        ytm2 = pd.Series(np.random.randn(20), index=dates)
        
        result = run_cointegration_analysis(ytm1, ytm2)
        
        assert result.error is not None


class TestEdgeCases:
    """Тесты краевых случаев"""

    def test_empty_series(self):
        """Тест: пустые ряды"""
        from core.cointegration import run_cointegration_analysis
        
        empty = pd.Series([], dtype=float)
        
        result = run_cointegration_analysis(empty, empty)
        
        assert result.error is not None

    def test_all_nan_series(self):
        """Тест: ряды только из NaN"""
        from core.cointegration import run_cointegration_analysis
        
        dates = pd.date_range('2024-01-01', periods=50)
        nan_series = pd.Series([np.nan] * 50, index=dates)
        
        result = run_cointegration_analysis(nan_series, nan_series)
        
        assert result.error is not None

    def test_constant_series(self):
        """Тест: константные ряды"""
        from core.cointegration import run_cointegration_analysis
        
        dates = pd.date_range('2024-01-01', periods=100)
        const1 = pd.Series([14.0] * 100, index=dates)
        const2 = pd.Series([13.0] * 100, index=dates)
        
        result = run_cointegration_analysis(const1, const2)
        
        # Должен вернуться результат без падения
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
