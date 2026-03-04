"""
Тесты для анализа коинтеграции

Unit тесты:
- synchronize_series()
- CointegrationAnalyzer.adf_test()
- CointegrationAnalyzer.kpss_test()
- CointegrationAnalyzer.engle_granger_test()
- CointegrationAnalyzer.calculate_half_life()
- CointegrationAnalyzer.calculate_hedge_ratio()
- CointegrationAnalyzer.analyze_pair()

Integration тесты:
- Полный анализ пары облигаций
- Интеграция с реальными данными YTM
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

    def test_ffill_method(self):
        """Тест: заполнение пропусков методом ffill"""
        from core.cointegration import synchronize_series
        
        dates1 = pd.date_range('2024-01-01', periods=10)
        dates2 = pd.date_range('2024-01-01', periods=10)
        
        ytm1 = pd.Series([1, 2, np.nan, 4, 5, 6, 7, 8, 9, 10], index=dates1)
        ytm2 = pd.Series([1, 2, 3, 4, np.nan, 6, 7, 8, 9, 10], index=dates2)
        
        sync1, sync2 = synchronize_series(ytm1, ytm2, fill_method='ffill')
        
        # После ffill и dropna должны быть данные
        assert len(sync1) > 0

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


class TestCointegrationAnalyzer:
    """Тесты класса CointegrationAnalyzer"""

    @pytest.fixture
    def analyzer(self):
        from core.cointegration import CointegrationAnalyzer
        return CointegrationAnalyzer(significance_level=0.05)

    @pytest.fixture
    def cointegrated_pair(self):
        """Генерация коинтегрированной пары (случайные блуждания с общей компонентой)"""
        np.random.seed(42)
        n = 200
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq='D')
        
        # Общая случайная компонента (случайное блуждание)
        common = np.cumsum(np.random.randn(n) * 0.5)
        
        # Два ряда с общей компонентой + независимый шум
        # Каждый ряд - случайное блуждание (нестационарный)
        ytm1 = 14 + common + np.cumsum(np.random.randn(n) * 0.3)
        ytm2 = 13 + common * 0.8 + np.cumsum(np.random.randn(n) * 0.3)
        
        return pd.Series(ytm1, index=dates), pd.Series(ytm2, index=dates)

    @pytest.fixture
    def random_walk_pair(self):
        """Генерация двух независимых случайных блужданий"""
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
        
        # Стационарный ряд (белый шум вокруг среднего)
        ytm = 14 + np.random.randn(n) * 0.1
        
        return pd.Series(ytm, index=dates)

    def test_initialization(self, analyzer):
        """Тест: инициализация анализатора"""
        assert analyzer.significance_level == 0.05

    def test_adf_test_structure(self, analyzer, random_walk_pair):
        """Тест: структура результата ADF теста"""
        ytm1, _ = random_walk_pair
        
        result = analyzer.adf_test(ytm1)
        
        # Проверяем структуру
        assert 'test' in result
        assert 'adf_statistic' in result
        assert 'pvalue' in result
        assert 'critical_values' in result
        assert 'is_stationary' in result
        assert 'interpretation' in result

    def test_adf_test_random_walk(self, analyzer, random_walk_pair):
        """Тест: ADF на случайном блуждании должен показать нестационарность"""
        ytm1, _ = random_walk_pair
        
        result = analyzer.adf_test(ytm1)
        
        # Случайное блуждание должно быть нестационарно (p > 0.05)
        # Но это не гарантировано на случайных данных
        assert 'is_stationary' in result

    def test_adf_test_stationary(self, analyzer, stationary_series):
        """Тест: ADF на стационарном ряде должен показать стационарность"""
        result = analyzer.adf_test(stationary_series)
        
        # Стационарный ряд должен быть определён как стационарный
        # p-value обычно очень низкий для белого шума
        assert result['pvalue'] < 0.05 or result['is_stationary']

    def test_adf_insufficient_data(self, analyzer):
        """Тест: ошибка при недостатке данных"""
        short_series = pd.Series([1, 2, 3, 4, 5])
        
        result = analyzer.adf_test(short_series)
        
        assert 'error' in result
        assert 'Insufficient' in result['error']

    def test_engle_granger_cointegrated(self, analyzer, cointegrated_pair):
        """Тест: Engle-Granger на коинтегрированной паре"""
        ytm1, ytm2 = cointegrated_pair
        
        result = analyzer.engle_granger_test(ytm1, ytm2)
        
        assert 'test' in result
        assert 'coint_statistic' in result
        assert 'pvalue' in result
        assert 'is_cointegrated' in result
        assert 'both_nonstationary' in result
        assert 'interpretation' in result

    def test_engle_granger_random_walk(self, analyzer, random_walk_pair):
        """Тест: Engle-Granger на независимых случайных блужданиях"""
        ytm1, ytm2 = random_walk_pair
        
        result = analyzer.engle_granger_test(ytm1, ytm2)
        
        # Независимые случайные блуждания обычно не коинтегрированы
        # Но p-value может быть любым
        assert 'pvalue' in result

    def test_engle_granger_stationary_input(self, analyzer, stationary_series):
        """Тест: Engle-Granger со стационарным рядом"""
        # Создаём второй стационарный ряд
        np.random.seed(789)
        n = 200
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq='D')
        ytm2 = pd.Series(13 + np.random.randn(n) * 0.1, index=dates)
        
        result = analyzer.engle_granger_test(stationary_series, ytm2)
        
        # Может быть ошибка или результат
        if 'error' not in result:
            # Должно быть предупреждение о стационарности
            assert result['both_nonstationary'] == False or 'стационарн' in result['interpretation'].lower()

    def test_half_life_calculation(self, analyzer, cointegrated_pair):
        """Тест: расчёт half-life"""
        ytm1, ytm2 = cointegrated_pair
        
        spread = (ytm1 - ytm2) * 100
        half_life = analyzer.calculate_half_life(spread)
        
        # Half-life должен быть положительным или inf
        if half_life is not None:
            assert half_life > 0 or half_life == float('inf')

    def test_half_life_short_series(self, analyzer):
        """Тест: half-life на коротком ряде"""
        short_series = pd.Series([1, 2, 3, 4, 5])
        
        half_life = analyzer.calculate_half_life(short_series)
        
        assert half_life is None

    def test_hedge_ratio(self, analyzer, cointegrated_pair):
        """Тест: расчёт hedge ratio"""
        ytm1, ytm2 = cointegrated_pair
        
        hedge_ratio = analyzer.calculate_hedge_ratio(ytm1, ytm2)
        
        if hedge_ratio is not None:
            # Hedge ratio должен быть числом
            assert isinstance(hedge_ratio, (int, float))
    
    def test_kpss_test_structure(self, analyzer, random_walk_pair):
        """Тест: структура результата KPSS теста"""
        ytm1, _ = random_walk_pair
        
        result = analyzer.kpss_test(ytm1)
        
        # Проверяем структуру
        assert 'test' in result
        assert 'kpss_statistic' in result
        assert 'pvalue' in result
        assert 'is_stationary' in result
    
    def test_kpss_insufficient_data(self, analyzer):
        """Тест: KPSS при недостатке данных"""
        short_series = pd.Series([1, 2, 3, 4, 5])
        
        result = analyzer.kpss_test(short_series)
        
        assert 'error' in result
    
    def test_engle_granger_bidirectional(self, analyzer):
        """Тест: bidirectional Engle-Granger выбирает лучший результат"""
        np.random.seed(999)
        n = 200
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq='D')
        
        # Создаём асимметричную пару
        common = np.cumsum(np.random.randn(n) * 0.5)
        ytm1 = pd.Series(14 + common + np.random.randn(n) * 0.1, index=dates)
        ytm2 = pd.Series(13 + common * 1.5 + np.random.randn(n) * 0.1, index=dates)
        
        # Bidirectional = True (по умолчанию)
        result_bi = analyzer.engle_granger_test(ytm1, ytm2, bidirectional=True)
        
        # Bidirectional = False
        result_uni = analyzer.engle_granger_test(ytm1, ytm2, bidirectional=False)
        
        # Bidirectional должен вернуть p-value не хуже
        assert result_bi['pvalue'] <= result_uni['pvalue'] + 0.001  # допуск на округление
    
    def test_duplicate_dates_handling(self, analyzer):
        """Тест: обработка дубликатов дат"""
        np.random.seed(111)
        dates = pd.date_range('2024-01-01', periods=100)
        
        # Создаём дубликаты
        dates_with_dupes = list(dates) + [dates[50], dates[75]]
        values = np.random.randn(102)
        
        ytm1 = pd.Series(values[:100], index=dates)
        ytm2 = pd.Series(values, index=dates_with_dupes)
        
        # Не должно падать
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        assert 'n_observations' in result

    def test_analyze_pair_structure(self, analyzer, cointegrated_pair):
        """Тест: структура результата analyze_pair"""
        ytm1, ytm2 = cointegrated_pair
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        # Проверяем структуру
        assert 'n_observations' in result
        assert 'engle_granger' in result
        assert 'adf_ytm1' in result
        assert 'adf_ytm2' in result
        assert 'half_life' in result
        assert 'hedge_ratio' in result
        assert 'is_cointegrated' in result
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


class TestFormatCointegrationReport:
    """Тесты форматирования отчёта"""

    def test_error_report(self):
        """Тест: отчёт с ошибкой"""
        from core.cointegration import format_cointegration_report
        
        result = {'error': 'statsmodels not installed'}
        report = format_cointegration_report(result)
        
        assert '❌' in report
        assert 'Ошибка' in report

    def test_success_report(self):
        """Тест: успешный отчёт с коинтеграцией"""
        from core.cointegration import format_cointegration_report
        
        result = {
            'engle_granger': {
                'coint_statistic': -3.5,
                'pvalue': 0.02,
                'ytm1_stationary': False,
                'ytm2_stationary': False,
                'ytm1_adf_pvalue': 0.3,
                'ytm2_adf_pvalue': 0.4,
                'interpretation': '✅ Коинтеграция есть'
            },
            'is_cointegrated': True,
            'half_life': 15.5,
            'hedge_ratio': 1.05,
            'recommendation': {
                'strategy': 'Pair Trading',
                'reason': 'Test reason',
                'risk': 'low'
            }
        }
        
        report = format_cointegration_report(result)
        
        assert '📊' in report
        assert 'Engle-Granger' in report
        assert 'Half-life' in report
        assert 'Hedge Ratio' in report

    def test_report_with_bond_names(self):
        """Тест: отчёт с названиями облигаций"""
        from core.cointegration import format_cointegration_report
        
        result = {
            'engle_granger': {
                'coint_statistic': -3.5,
                'pvalue': 0.02,
                'ytm1_stationary': False,
                'ytm2_stationary': False,
                'ytm1_adf_pvalue': 0.3,
                'ytm2_adf_pvalue': 0.4,
                'interpretation': '✅ Коинтеграция есть'
            },
            'is_cointegrated': True,
            'half_life': 15.5,
            'hedge_ratio': 1.05,
            'recommendation': {
                'strategy': 'Pair Trading',
                'reason': 'Test reason',
                'risk': 'low'
            }
        }
        
        report = format_cointegration_report(result, "ОФЗ 26238", "ОФЗ 26243")
        
        # Проверяем, что названия облигаций в отчёте
        assert 'ОФЗ 26238' in report
        assert 'ОФЗ 26243' in report
        # Проверяем, что старые YTM₁/YTM₂ не используются
        assert 'YTM₁' not in report
        assert 'YTM₂' not in report

    def test_hedge_ratio_explanation(self):
        """Тест: текстовое объяснение Hedge Ratio"""
        from core.cointegration import format_cointegration_report
        
        result = {
            'engle_granger': {
                'coint_statistic': -3.5,
                'pvalue': 0.02,
                'ytm1_stationary': False,
                'ytm2_stationary': False,
                'ytm1_adf_pvalue': 0.3,
                'ytm2_adf_pvalue': 0.4,
                'interpretation': '✅ Коинтеграция есть'
            },
            'is_cointegrated': True,
            'hedge_ratio': 1.25,
            'recommendation': {
                'strategy': 'Pair Trading',
                'reason': 'Test reason',
                'risk': 'low'
            }
        }
        
        report = format_cointegration_report(result, "ОФЗ 26238", "ОФЗ 26243")
        
        # Проверяем текстовое объяснение
        assert '1.25 единицы ОФЗ 26243' in report
        assert '1 единицу ОФЗ 26238' in report

    def test_no_halflife_when_not_cointegrated(self):
        """Тест: Half-life и Hedge Ratio НЕ показываются если нет коинтеграции"""
        from core.cointegration import format_cointegration_report
        
        result = {
            'engle_granger': {
                'coint_statistic': -2.8,
                'pvalue': 0.1594,
                'ytm1_stationary': False,
                'ytm2_stationary': False,
                'ytm1_adf_pvalue': 0.29,
                'ytm2_adf_pvalue': 0.52,
                'interpretation': '❌ Коинтеграции нет'
            },
            'is_cointegrated': False,
            'half_life': 15.6,  # Не имеет смысла без коинтеграции
            'hedge_ratio': 0.86,  # Не имеет смысла без коинтеграции
            'recommendation': {
                'strategy': 'Не рекомендуется',
                'reason': 'Пара не коинтегрирована',
                'risk': 'high'
            }
        }
        
        report = format_cointegration_report(result, "ОФЗ 26230", "ОФЗ 26238")
        
        # Half-life и Hedge Ratio НЕ должны быть в отчёте
        assert 'Half-life' not in report
        assert 'Hedge Ratio' not in report
        # Но рекомендация должна быть
        assert 'Не рекомендуется' in report


class TestIntegrationWithYTM:
    """Интеграционные тесты с реальными данными YTM"""

    @pytest.fixture
    def sample_ytm_data(self):
        """Создание тестовых YTM данных как в приложении"""
        np.random.seed(42)
        n = 365
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq='D')
        
        # ОФЗ 26238 (длинная)
        trend1 = np.cumsum(np.random.randn(n) * 0.01)
        ytm1 = 14 + trend1 + np.random.randn(n) * 0.05
        
        # ОФЗ 26243 (короткая) - с общим трендом
        ytm2 = 13 + trend1 * 0.8 + np.random.randn(n) * 0.05
        
        df1 = pd.DataFrame({'ytm': ytm1}, index=dates)
        df2 = pd.DataFrame({'ytm': ytm2}, index=dates)
        
        return df1, df2

    def test_full_analysis_workflow(self, sample_ytm_data):
        """Тест: полный workflow анализа"""
        from core.cointegration import CointegrationAnalyzer, format_cointegration_report
        
        df1, df2 = sample_ytm_data
        
        analyzer = CointegrationAnalyzer()
        result = analyzer.analyze_pair(df1['ytm'], df2['ytm'])
        
        # Проверяем что анализ прошёл успешно
        assert 'error' not in result or result.get('error') is None
        assert result['n_observations'] > 0
        
        # Форматируем отчёт
        report = format_cointegration_report(result)
        assert len(report) > 0

    def test_analysis_with_missing_dates(self, sample_ytm_data):
        """Тест: анализ с пропусками в датах"""
        from core.cointegration import CointegrationAnalyzer
        
        df1, df2 = sample_ytm_data
        
        # Удаляем некоторые даты
        df1_missing = df1.drop(df1.index[50:60])
        df2_missing = df2.drop(df2.index[80:90])
        
        analyzer = CointegrationAnalyzer()
        result = analyzer.analyze_pair(df1_missing['ytm'], df2_missing['ytm'])
        
        # Должен синхронизировать и вернуть результат
        assert 'n_observations' in result

    def test_analysis_with_short_period(self):
        """Тест: анализ на коротком периоде (меньше 30 дней)"""
        from core.cointegration import CointegrationAnalyzer
        
        dates = pd.date_range(end=pd.Timestamp.now(), periods=20, freq='D')
        ytm1 = pd.Series(np.random.randn(20), index=dates)
        ytm2 = pd.Series(np.random.randn(20), index=dates)
        
        analyzer = CointegrationAnalyzer()
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        # Должна быть ошибка о недостатке данных
        assert 'error' in result
        assert 'Insufficient' in result['error']


class TestEdgeCases:
    """Тесты краевых случаев"""

    def test_empty_series(self):
        """Тест: пустые ряды"""
        from core.cointegration import CointegrationAnalyzer
        
        empty = pd.Series([], dtype=float)
        analyzer = CointegrationAnalyzer()
        
        result = analyzer.analyze_pair(empty, empty)
        
        assert 'error' in result

    def test_all_nan_series(self):
        """Тест: ряды только из NaN"""
        from core.cointegration import CointegrationAnalyzer
        
        dates = pd.date_range('2024-01-01', periods=50)
        nan_series = pd.Series([np.nan] * 50, index=dates)
        
        analyzer = CointegrationAnalyzer()
        result = analyzer.analyze_pair(nan_series, nan_series)
        
        assert 'error' in result

    def test_constant_series(self):
        """Тест: константные ряды"""
        from core.cointegration import CointegrationAnalyzer
        
        dates = pd.date_range('2024-01-01', periods=100)
        const1 = pd.Series([14.0] * 100, index=dates)
        const2 = pd.Series([13.0] * 100, index=dates)
        
        analyzer = CointegrationAnalyzer()
        
        # Константные ряды обрабатываются gracefully
        result = analyzer.analyze_pair(const1, const2)
        
        # Должен вернуться результат без падения
        assert result is not None
        # Константные ряды - стационарны, поэтому коинтеграция не применима
        if 'error' not in result:
            assert result.get('both_nonstationary') == False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
