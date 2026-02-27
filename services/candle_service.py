"""
Сервис для работы со свечами и YTM

Инкапсулирует логику загрузки свечей с MOEX, расчёта YTM и кэширования.
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
from typing import Optional, Dict, Any
import logging

from api.moex_candles import CandleFetcher, CandleInterval
from core.db.ytm_repo import YTMRepository
from models.bond import Bond

logger = logging.getLogger(__name__)


class CandleService:
    """
    Сервис для работы со свечами и YTM
    
    Ответственности:
    - Загрузка свечей с MOEX API
    - Расчёт YTM из цен свечей
    - Кэширование в БД
    - Получение исторических и текущих данных
    """
    
    # Маппинг строковых интервалов к enum
    INTERVAL_MAP = {
        "1": CandleInterval.MIN_1,
        "10": CandleInterval.MIN_10,
        "60": CandleInterval.MIN_60,
    }
    
    # Лимиты по интервалам
    INTERVAL_LIMITS = {
        "1": {"max_days": 3, "default": 1},
        "10": {"max_days": 30, "default": 7},
        "60": {"max_days": 365, "default": 30},
    }
    
    def __init__(self, fetcher: CandleFetcher = None, ytm_repo: YTMRepository = None):
        """
        Инициализация сервиса
        
        Args:
            fetcher: CandleFetcher для работы с MOEX API
            ytm_repo: Репозиторий YTM для работы с БД
        """
        self._fetcher = fetcher
        self._ytm_repo = ytm_repo or YTMRepository()
    
    @property
    def fetcher(self) -> CandleFetcher:
        """Ленивая инициализация fetcher"""
        if self._fetcher is None:
            self._fetcher = CandleFetcher()
        return self._fetcher
    
    def get_interval_enum(self, interval: str) -> CandleInterval:
        """
        Получить CandleInterval enum из строки
        
        Args:
            interval: Строковый интервал ('1', '10', '60')
        
        Returns:
            CandleInterval enum
        """
        return self.INTERVAL_MAP.get(interval, CandleInterval.MIN_60)
    
    def get_max_days(self, interval: str) -> int:
        """Получить максимальное количество дней для интервала"""
        return self.INTERVAL_LIMITS.get(interval, {"max_days": 30})["max_days"]
    
    def get_default_days(self, interval: str) -> int:
        """Получить количество дней по умолчанию для интервала"""
        return self.INTERVAL_LIMITS.get(interval, {"default": 7})["default"]
    
    @st.cache_data(ttl=60)
    def get_candles_with_ytm(
        self,
        bond: Bond,
        interval: str,
        days: int,
        _bond_dict: Dict[str, Any] = None
    ) -> pd.DataFrame:
        """
        Получить данные свечей с YTM с кэшированием в SQLite
        
        Args:
            bond: Облигация (Bond model)
            interval: Интервал ('1', '10', '60')
            days: Количество дней истории
            _bond_dict: Словарь для хэширования (костыль для st.cache_data)
        
        Returns:
            DataFrame с колонками: close, ytm_close, accrued_interest
        """
        start_date = date.today() - timedelta(days=days)
        
        # 1. Загружаем рассчитанные YTM из БД
        db_ytm_df = self._ytm_repo.load_intraday_ytm(
            bond.isin,
            interval,
            start_date=start_date,
            end_date=date.today() - timedelta(days=1)
        )
        
        # 2. Всегда запрашиваем данные за текущий день с MOEX
        today_df = self._fetch_today_candles(bond, interval)
        
        # 3. Если в БД нет данных, загружаем все исторические
        if db_ytm_df.empty and days > 1:
            history_df = self._fetch_history_candles(bond, interval, start_date)
            
            if not history_df.empty and 'ytm_close' in history_df.columns:
                self._ytm_repo.save_intraday_ytm(bond.isin, interval, history_df)
                logger.info(f"Сохранены intraday YTM в БД для {bond.isin}: {len(history_df)} записей")
            
            db_ytm_df = history_df
        
        elif not db_ytm_df.empty:
            # Проверяем пропуски и заполняем
            db_ytm_df = self._fill_gaps(db_ytm_df, bond, interval, start_date)
        
        # 4. Сохраняем текущие данные
        if not today_df.empty and 'ytm_close' in today_df.columns:
            self._ytm_repo.save_intraday_ytm(bond.isin, interval, today_df)
        
        # 5. Объединяем исторические + текущие данные
        result_df = self._merge_dataframes(db_ytm_df, today_df)
        
        return result_df
    
    def _fetch_today_candles(self, bond: Bond, interval: str) -> pd.DataFrame:
        """Загрузить свечи за текущий день"""
        try:
            return self.fetcher.fetch_candles(
                bond.isin,
                bond_config=bond,
                interval=self.get_interval_enum(interval),
                start_date=date.today(),
                end_date=date.today()
            )
        except Exception as e:
            logger.warning(f"Ошибка загрузки сегодняшних свечей: {e}")
            return pd.DataFrame()
    
    def _fetch_history_candles(
        self,
        bond: Bond,
        interval: str,
        start_date: date
    ) -> pd.DataFrame:
        """Загрузить исторические свечи"""
        try:
            return self.fetcher.fetch_candles(
                bond.isin,
                bond_config=bond,
                interval=self.get_interval_enum(interval),
                start_date=start_date,
                end_date=date.today() - timedelta(days=1)
            )
        except Exception as e:
            logger.warning(f"Ошибка загрузки исторических свечей: {e}")
            return pd.DataFrame()
    
    def _fill_gaps(
        self,
        df: pd.DataFrame,
        bond: Bond,
        interval: str,
        start_date: date
    ) -> pd.DataFrame:
        """Заполнить пропуски в данных"""
        if df.empty:
            return df
        
        first_db_datetime = df.index[0] if not df.empty else None
        last_db_datetime = df.index[-1] if not df.empty else None
        needed_end = date.today() - timedelta(days=1)
        
        # Проверяем пропуски в начале
        if first_db_datetime is not None:
            first_db_date = self._extract_date(first_db_datetime)
            
            if first_db_date > start_date:
                logger.info(f"Загрузка недостающих данных: {start_date} -> {first_db_date - timedelta(days=1)}")
                fill_df = self._fetch_history_range(
                    bond, interval, start_date, first_db_date - timedelta(days=1)
                )
                if not fill_df.empty and 'ytm_close' in fill_df.columns:
                    self._ytm_repo.save_intraday_ytm(bond.isin, interval, fill_df)
                    df = pd.concat([fill_df, df])
        
        # Проверяем пропуски в конце
        if last_db_datetime is not None:
            last_db_date = self._extract_date(last_db_datetime)
            
            if (needed_end - last_db_date).days > 1:
                fill_start = last_db_date + timedelta(days=1)
                fill_df = self._fetch_history_range(bond, interval, fill_start, needed_end)
                if not fill_df.empty and 'ytm_close' in fill_df.columns:
                    self._ytm_repo.save_intraday_ytm(bond.isin, interval, fill_df)
                    df = pd.concat([df, fill_df])
        
        return df
    
    def _fetch_history_range(
        self,
        bond: Bond,
        interval: str,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """Загрузить свечи за диапазон дат"""
        try:
            return self.fetcher.fetch_candles(
                bond.isin,
                bond_config=bond,
                interval=self.get_interval_enum(interval),
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            logger.warning(f"Ошибка загрузки диапазона {start_date}-{end_date}: {e}")
            return pd.DataFrame()
    
    def _extract_date(self, dt_value) -> date:
        """Извлечь дату из datetime значения"""
        if hasattr(dt_value, 'date'):
            return dt_value.date()
        if isinstance(dt_value, datetime):
            return dt_value.date()
        return dt_value
    
    def _merge_dataframes(
        self,
        history_df: pd.DataFrame,
        today_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Объединить исторические и текущие данные"""
        if not history_df.empty and not today_df.empty:
            result_df = pd.concat([history_df, today_df])
            result_df = result_df[~result_df.index.duplicated(keep='last')]
        elif not today_df.empty:
            result_df = today_df
        elif not history_df.empty:
            result_df = history_df
        else:
            result_df = pd.DataFrame()
        
        # Сортируем по времени
        if not result_df.empty:
            result_df = result_df.sort_index()
        
        return result_df
    
    def close(self):
        """Закрыть соединения"""
        if self._fetcher:
            self._fetcher.close()


# Фабрика для удобства
@st.cache_resource
def get_candle_service() -> CandleService:
    """Получить CandleService (кэшируется)"""
    return CandleService()
