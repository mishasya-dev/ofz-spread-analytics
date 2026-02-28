"""
Тесты для CandleService

Модуль тестирует:
- Инициализацию сервиса
- Маппинг интервалов
- Расчёт лимитов дней
- Объединение DataFrame
- Извлечение дат
"""
import pytest
import pandas as pd
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Мок streamlit до импорта
import sys
sys.modules['streamlit'] = MagicMock()

from services.candle_service import CandleService
from api.moex_candles import CandleInterval
from models.bond import Bond


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def mock_fetcher():
    """Мок CandleFetcher"""
    fetcher = Mock()
    fetcher.fetch_candles = Mock(return_value=pd.DataFrame())
    fetcher.close = Mock()
    return fetcher


@pytest.fixture
def mock_ytm_repo():
    """Мок YTMRepository"""
    repo = Mock()
    repo.load_intraday_ytm = Mock(return_value=pd.DataFrame())
    repo.save_intraday_ytm = Mock()
    return repo


@pytest.fixture
def sample_bond():
    """Тестовая облигация"""
    return Bond(
        isin="RU000A1038V6",
        name="ОФЗ 26240",
        maturity_date="2046-05-15",
        coupon_rate=7.10,
        face_value=1000.0,
        coupon_frequency=2
    )


@pytest.fixture
def sample_candles_df():
    """DataFrame с тестовыми свечами"""
    dates = pd.date_range(
        start="2026-02-20 10:00:00",
        periods=10,
        freq="h"
    )
    return pd.DataFrame({
        "close": [95.0 + i * 0.1 for i in range(10)],
        "ytm_close": [14.5 + i * 0.01 for i in range(10)],
        "accrued_interest": [25.0] * 10
    }, index=dates)


@pytest.fixture
def service(mock_fetcher, mock_ytm_repo):
    """CandleService с моками"""
    return CandleService(fetcher=mock_fetcher, ytm_repo=mock_ytm_repo)


# ============================================
# TestCandleServiceInit
# ============================================

class TestCandleServiceInit:
    """Тесты инициализации"""
    
    def test_init_with_fetcher_and_repo(self, mock_fetcher, mock_ytm_repo):
        """Инициализация с fetcher и repo"""
        service = CandleService(fetcher=mock_fetcher, ytm_repo=mock_ytm_repo)
        
        assert service._fetcher is mock_fetcher
        assert service._ytm_repo is mock_ytm_repo
    
    def test_init_without_fetcher(self, mock_ytm_repo):
        """Инициализация без fetcher (ленивая загрузка)"""
        service = CandleService(ytm_repo=mock_ytm_repo)
        
        assert service._fetcher is None
        # fetcher создаётся при обращении
        assert service.fetcher is not None
    
    def test_init_without_repo(self, mock_fetcher):
        """Инициализация без repo (создаётся по умолчанию)"""
        with patch('services.candle_service.YTMRepository') as MockRepo:
            MockRepo.return_value = Mock()
            service = CandleService(fetcher=mock_fetcher)
            
            assert service._ytm_repo is not None


# ============================================
# TestIntervalMapping
# ============================================

class TestIntervalMapping:
    """Тесты маппинга интервалов"""
    
    def test_interval_1_minute(self, service):
        """Интервал '1' -> MIN_1"""
        result = service.get_interval_enum("1")
        assert result == CandleInterval.MIN_1
    
    def test_interval_10_minutes(self, service):
        """Интервал '10' -> MIN_10"""
        result = service.get_interval_enum("10")
        assert result == CandleInterval.MIN_10
    
    def test_interval_60_minutes(self, service):
        """Интервал '60' -> MIN_60"""
        result = service.get_interval_enum("60")
        assert result == CandleInterval.MIN_60
    
    def test_interval_unknown_defaults_to_60(self, service):
        """Неизвестный интервал -> MIN_60"""
        result = service.get_interval_enum("unknown")
        assert result == CandleInterval.MIN_60
    
    def test_interval_empty_defaults_to_60(self, service):
        """Пустой интервал -> MIN_60"""
        result = service.get_interval_enum("")
        assert result == CandleInterval.MIN_60


# ============================================
# TestIntervalLimits
# ============================================

class TestIntervalLimits:
    """Тесты лимитов интервалов"""
    
    def test_max_days_interval_1(self, service):
        """Макс дней для интервала '1' = 3"""
        assert service.get_max_days("1") == 3
    
    def test_max_days_interval_10(self, service):
        """Макс дней для интервала '10' = 30"""
        assert service.get_max_days("10") == 30
    
    def test_max_days_interval_60(self, service):
        """Макс дней для интервала '60' = 365"""
        assert service.get_max_days("60") == 365
    
    def test_max_days_unknown_defaults_to_30(self, service):
        """Макс дней для неизвестного = 30"""
        assert service.get_max_days("unknown") == 30
    
    def test_default_days_interval_1(self, service):
        """Дней по умолчанию для '1' = 1"""
        assert service.get_default_days("1") == 1
    
    def test_default_days_interval_10(self, service):
        """Дней по умолчанию для '10' = 7"""
        assert service.get_default_days("10") == 7
    
    def test_default_days_interval_60(self, service):
        """Дней по умолчанию для '60' = 30"""
        assert service.get_default_days("60") == 30
    
    def test_default_days_unknown_defaults_to_7(self, service):
        """Дней по умолчанию для неизвестного = 7"""
        assert service.get_default_days("unknown") == 7


# ============================================
# TestMergeDataframes
# ============================================

class TestMergeDataframes:
    """Тесты объединения DataFrame"""
    
    def test_merge_both_empty(self, service):
        """Оба DataFrame пустые"""
        result = service._merge_dataframes(
            pd.DataFrame(),
            pd.DataFrame()
        )
        
        assert result.empty
    
    def test_merge_history_only(self, service, sample_candles_df):
        """Только исторические данные"""
        result = service._merge_dataframes(
            sample_candles_df,
            pd.DataFrame()
        )
        
        assert len(result) == len(sample_candles_df)
    
    def test_merge_today_only(self, service, sample_candles_df):
        """Только текущие данные"""
        result = service._merge_dataframes(
            pd.DataFrame(),
            sample_candles_df
        )
        
        assert len(result) == len(sample_candles_df)
    
    def test_merge_both(self, service):
        """Исторические + текущие данные"""
        # Исторические (вчера)
        history_dates = pd.date_range(
            start="2026-02-19 10:00:00",
            periods=5,
            freq="h"
        )
        history_df = pd.DataFrame({
            "close": [95.0] * 5,
            "ytm_close": [14.5] * 5
        }, index=history_dates)
        
        # Текущие (сегодня)
        today_dates = pd.date_range(
            start="2026-02-20 10:00:00",
            periods=5,
            freq="h"
        )
        today_df = pd.DataFrame({
            "close": [96.0] * 5,
            "ytm_close": [14.6] * 5
        }, index=today_dates)
        
        result = service._merge_dataframes(history_df, today_df)
        
        assert len(result) == 10
    
    def test_merge_removes_duplicates(self, service):
        """Удаление дубликатов при объединении"""
        # Пересекающиеся даты
        dates = pd.date_range(
            start="2026-02-20 10:00:00",
            periods=5,
            freq="h"
        )
        
        history_df = pd.DataFrame({
            "close": [95.0] * 5,
            "ytm_close": [14.5] * 5
        }, index=dates)
        
        # Те же даты, но другие значения (перезапись)
        today_df = pd.DataFrame({
            "close": [96.0] * 5,
            "ytm_close": [14.6] * 5
        }, index=dates)
        
        result = service._merge_dataframes(history_df, today_df)
        
        # Дубликаты удалены, остаются последние значения
        assert len(result) == 5
        assert result["close"].iloc[0] == 96.0
    
    def test_merge_sorted_by_index(self, service):
        """Результат отсортирован по времени"""
        # Неупорядоченные данные
        dates1 = pd.date_range("2026-02-20 14:00:00", periods=2, freq="h")
        dates2 = pd.date_range("2026-02-20 10:00:00", periods=2, freq="h")
        
        df1 = pd.DataFrame({"close": [95.0] * 2}, index=dates1)
        df2 = pd.DataFrame({"close": [96.0] * 2}, index=dates2)
        
        result = service._merge_dataframes(df1, df2)
        
        # Проверяем сортировку
        assert result.index.is_monotonic_increasing


# ============================================
# TestExtractDate
# ============================================

class TestExtractDate:
    """Тесты извлечения даты"""
    
    def test_extract_from_datetime(self, service):
        """Извлечение из datetime"""
        dt = datetime(2026, 2, 20, 14, 30, 0)
        result = service._extract_date(dt)
        
        assert result == date(2026, 2, 20)
    
    def test_extract_from_timestamp(self, service):
        """Извлечение из pandas Timestamp"""
        ts = pd.Timestamp("2026-02-20 14:30:00")
        result = service._extract_date(ts)
        
        assert result == date(2026, 2, 20)
    
    def test_extract_from_date(self, service):
        """Извлечение из date (без изменений)"""
        d = date(2026, 2, 20)
        result = service._extract_date(d)
        
        assert result == date(2026, 2, 20)


# ============================================
# TestFetchTodayCandles
# ============================================

class TestFetchTodayCandles:
    """Тесты загрузки сегодняшних свечей"""
    
    def test_fetch_today_success(self, service, mock_fetcher, sample_bond, sample_candles_df):
        """Успешная загрузка сегодняшних свечей"""
        mock_fetcher.fetch_candles.return_value = sample_candles_df
        
        result = service._fetch_today_candles(sample_bond, "60")
        
        assert len(result) == 10
        mock_fetcher.fetch_candles.assert_called_once()
    
    def test_fetch_today_exception(self, service, mock_fetcher, sample_bond):
        """Обработка исключения при загрузке"""
        mock_fetcher.fetch_candles.side_effect = Exception("API Error")
        
        result = service._fetch_today_candles(sample_bond, "60")
        
        assert result.empty


# ============================================
# TestFetchHistoryCandles
# ============================================

class TestFetchHistoryCandles:
    """Тесты загрузки исторических свечей"""
    
    def test_fetch_history_success(self, service, mock_fetcher, sample_bond, sample_candles_df):
        """Успешная загрузка исторических свечей"""
        mock_fetcher.fetch_candles.return_value = sample_candles_df
        
        result = service._fetch_history_candles(
            sample_bond,
            "60",
            start_date=date.today() - timedelta(days=7)
        )
        
        assert len(result) == 10
    
    def test_fetch_history_exception(self, service, mock_fetcher, sample_bond):
        """Обработка исключения при загрузке истории"""
        mock_fetcher.fetch_candles.side_effect = Exception("API Error")
        
        result = service._fetch_history_candles(
            sample_bond,
            "60",
            start_date=date.today() - timedelta(days=7)
        )
        
        assert result.empty


# ============================================
# TestFillGaps
# ============================================

class TestFillGaps:
    """Тесты заполнения пропусков"""
    
    def test_fill_gaps_empty_df(self, service, sample_bond):
        """Пустой DataFrame возвращает как есть"""
        result = service._fill_gaps(
            pd.DataFrame(),
            sample_bond,
            "60",
            date.today() - timedelta(days=7)
        )
        
        assert result.empty
    
    def test_fill_gaps_no_gaps(self, service, sample_bond, sample_candles_df):
        """Нет пропусков - данные не меняются"""
        result = service._fill_gaps(
            sample_candles_df,
            sample_bond,
            "60",
            date.today() - timedelta(days=1)
        )
        
        assert len(result) == len(sample_candles_df)


# ============================================
# TestClose
# ============================================

class TestClose:
    """Тесты закрытия соединений"""
    
    def test_close_with_fetcher(self, service, mock_fetcher):
        """Закрытие с fetcher"""
        service.close()
        mock_fetcher.close.assert_called_once()
    
    def test_close_without_fetcher(self, mock_ytm_repo):
        """Закрытие без fetcher не вызывает ошибку"""
        service = CandleService(fetcher=None, ytm_repo=mock_ytm_repo)
        # Не должно вызывать ошибку
        service.close()
