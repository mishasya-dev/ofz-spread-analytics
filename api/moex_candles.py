"""
Получение внутридневных свечей с Мосбиржи и расчёт YTM
"""
import requests
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging
import time as time_module
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ytm_calculator import YTMCalculator, BondParams, calculate_ytm_from_price

logger = logging.getLogger(__name__)


class CandleInterval(Enum):
    """Интервалы свечей"""
    MIN_1 = "1"
    MIN_10 = "10"
    MIN_60 = "60"
    DAY = "24"
    WEEK = "7"
    MONTH = "31"


@dataclass
class Candle:
    """Данные свечи"""
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    ytm: Optional[float] = None
    ytm_open: Optional[float] = None
    ytm_high: Optional[float] = None
    ytm_low: Optional[float] = None


class CandleFetcher:
    """Получение внутридневных свечей с расчётом YTM"""
    
    MOEX_BASE_URL = "https://iss.moex.com/iss"
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        Инициализация
        
        Args:
            timeout: Таймаут запроса в секундах
            max_retries: Максимальное количество повторных попыток
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "OFZ-Analytics/1.0"
        })
        self._ytm_calculator = YTMCalculator()
        self._bond_params_cache: Dict[str, BondParams] = {}
        self._accrued_interest_cache: Dict[str, float] = {}
    
    def fetch_candles(
        self,
        isin: str,
        bond_config: Optional[Any] = None,
        interval: CandleInterval = CandleInterval.MIN_60,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        board: str = "TQOB"
    ) -> pd.DataFrame:
        """
        Получить свечи по облигации с рассчитанным YTM
        
        Args:
            isin: ISIN код облигации
            bond_config: Конфигурация облигации (BondConfig) для расчёта YTM
            interval: Интервал свечей
            start_date: Начальная дата
            end_date: Конечная дата
            board: Торговая площадка
            
        Returns:
            DataFrame со свечами и YTM
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=7)
        if end_date is None:
            end_date = date.today()
        
        all_data = []
        start = 0
        batch_size = 500
        
        while True:
            url = f"{self.MOEX_BASE_URL}/engines/stock/markets/bonds/boards/{board}/securities/{isin}/candles.json"
            params = {
                "from": start_date.isoformat(),
                "till": end_date.isoformat(),
                "interval": interval.value,
                "iss.meta": "off",
                "start": start,
                "limit": batch_size
            }
            
            try:
                response = self._make_request(url, params)
                data = response.json()
                
                candles = data.get("candles", {})
                columns = candles.get("columns", [])
                rows = candles.get("data", [])
                
                if not rows:
                    break
                
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    all_data.append({
                        "datetime": row_dict.get("begin"),
                        "open": row_dict.get("open"),
                        "high": row_dict.get("high"),
                        "low": row_dict.get("low"),
                        "close": row_dict.get("close"),
                        "volume": row_dict.get("volume"),
                        "value": row_dict.get("value"),
                    })
                
                if len(rows) < batch_size:
                    break
                    
                start += batch_size
                
            except Exception as e:
                logger.error(f"Ошибка при получении свечей для {isin}: {e}")
                break
        
        if not all_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(all_data)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")
        df = df.sort_index()
        
        # Рассчитываем YTM если есть параметры облигации
        if bond_config is not None:
            df = self._calculate_ytm_for_dataframe(df, bond_config)
        
        return df
    
    def fetch_hourly_ytm(
        self,
        isin: str,
        bond_config: Any,
        trading_date: Optional[date] = None,
        board: str = "TQOB"
    ) -> pd.DataFrame:
        """
        Получить почасовые данные YTM за торговый день
        
        Args:
            isin: ISIN код облигации
            bond_config: Конфигурация облигации (BondConfig)
            trading_date: Дата торгов
            board: Торговая площадка
            
        Returns:
            DataFrame с почасовыми данными и YTM
        """
        if trading_date is None:
            trading_date = date.today()
        
        return self.fetch_candles(
            isin,
            bond_config=bond_config,
            interval=CandleInterval.MIN_60,
            start_date=trading_date,
            end_date=trading_date,
            board=board
        )
    
    def fetch_multi_bonds_hourly(
        self,
        bonds_config: Dict[str, Any],
        trading_date: Optional[date] = None,
        board: str = "TQOB",
        delay: float = 0.3
    ) -> Dict[str, pd.DataFrame]:
        """
        Получить почасовые данные для нескольких облигаций
        
        Args:
            bonds_config: Словарь {ISIN: BondConfig}
            trading_date: Дата торгов
            board: Торговая площадка
            delay: Задержка между запросами
            
        Returns:
            Словарь {ISIN: DataFrame}
        """
        if trading_date is None:
            trading_date = date.today()
        
        results = {}
        
        for isin, bond_config in bonds_config.items():
            logger.info(f"Загрузка часовых данных для {isin}...")
            df = self.fetch_hourly_ytm(isin, bond_config, trading_date, board)
            
            if not df.empty:
                results[isin] = df
            else:
                logger.warning(f"Нет часовых данных для {isin}")
            
            time_module.sleep(delay)
        
        return results
    
    def get_intraday_spread(
        self,
        bond1_config: Any,
        bond2_config: Any,
        trading_date: Optional[date] = None,
        board: str = "TQOB"
    ) -> pd.DataFrame:
        """
        Получить внутридневной спред между двумя облигациями
        
        Args:
            bond1_config: Конфигурация облигации 1
            bond2_config: Конфигурация облигации 2
            trading_date: Дата торгов
            board: Торговая площадка
            
        Returns:
            DataFrame с внутридневными данными и спредом
        """
        if trading_date is None:
            trading_date = date.today()
        
        # Получаем данные для обеих облигаций
        df1 = self.fetch_hourly_ytm(bond1_config.isin, bond1_config, trading_date, board)
        df2 = self.fetch_hourly_ytm(bond2_config.isin, bond2_config, trading_date, board)
        
        if df1.empty or df2.empty:
            logger.warning("Нет данных для расчёта спреда")
            return pd.DataFrame()
        
        # Объединяем по времени
        merged = pd.merge(
            df1[['close', 'ytm_close']].rename(columns={'close': 'price_1', 'ytm_close': 'ytm_1'}),
            df2[['close', 'ytm_close']].rename(columns={'close': 'price_2', 'ytm_close': 'ytm_2'}),
            left_index=True,
            right_index=True,
            how='inner'
        )
        
        # Рассчитываем спред в базисных пунктах
        if 'ytm_1' in merged.columns and 'ytm_2' in merged.columns:
            merged['spread_bp'] = (merged['ytm_1'] - merged['ytm_2']) * 100
        
        return merged
    
    def _calculate_ytm_for_dataframe(
        self,
        df: pd.DataFrame,
        bond_config: Any
    ) -> pd.DataFrame:
        """
        Рассчитать YTM для всех свечей в DataFrame
        
        Args:
            df: DataFrame с ценами свечей
            bond_config: Конфигурация облигации
            
        Returns:
            DataFrame с добавленными колонками YTM
        """
        # Создаём BondParams
        bond_params = self._get_bond_params(bond_config)
        
        if bond_params is None:
            logger.warning(f"Не удалось создать параметры для {bond_config.isin}")
            return df
        
        # Получаем НКД с MOEX
        accrued_interest = self._get_accrued_interest(bond_config.isin)
        
        # Рассчитываем YTM для каждой цены
        df['ytm_open'] = df['open'].apply(
            lambda p: self._safe_calculate_ytm(p, bond_params, accrued_interest)
        )
        df['ytm_high'] = df['high'].apply(
            lambda p: self._safe_calculate_ytm(p, bond_params, accrued_interest)
        )
        df['ytm_low'] = df['low'].apply(
            lambda p: self._safe_calculate_ytm(p, bond_params, accrued_interest)
        )
        df['ytm_close'] = df['close'].apply(
            lambda p: self._safe_calculate_ytm(p, bond_params, accrued_interest)
        )
        
        # Основной YTM = YTM закрытия
        df['ytm'] = df['ytm_close']
        
        return df
    
    def _get_accrued_interest(self, isin: str) -> float:
        """
        Получить НКД (накопленный купонный доход) с MOEX
        
        Args:
            isin: ISIN код облигации
            
        Returns:
            НКД в рублях (0 если не удалось получить)
        """
        if isin in self._accrued_interest_cache:
            return self._accrued_interest_cache[isin]
        
        url = f"{self.MOEX_BASE_URL}/engines/stock/markets/bonds/securities/{isin}.json"
        params = {'iss.meta': 'off', 'iss.only': 'securities'}
        
        try:
            response = self._make_request(url, params)
            data = response.json()
            
            securities = data.get('securities', {})
            columns = securities.get('columns', [])
            rows = securities.get('data', [])
            
            # Ищем ACCRUEDINT (НКД)
            if 'ACCRUEDINT' in columns:
                accrued_idx = columns.index('ACCRUEDINT')
                for row in rows:
                    if row[accrued_idx] is not None:
                        accrued = float(row[accrued_idx])
                        self._accrued_interest_cache[isin] = accrued
                        logger.debug(f"НКД для {isin}: {accrued:.2f} руб.")
                        return accrued
            
            logger.warning(f"Не удалось получить НКД для {isin}")
            return 0.0
            
        except Exception as e:
            logger.warning(f"Ошибка получения НКД для {isin}: {e}")
            return 0.0
    
    def _get_bond_params(self, bond_config: Any) -> Optional[BondParams]:
        """
        Создать BondParams из BondConfig
        """
        isin = bond_config.isin
        
        if isin in self._bond_params_cache:
            return self._bond_params_cache[isin]
        
        try:
            maturity = datetime.strptime(bond_config.maturity_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            logger.warning(f"Неверная дата погашения для {isin}: {bond_config.maturity_date}")
            return None
        
        params = BondParams(
            isin=isin,
            name=bond_config.name,
            face_value=getattr(bond_config, 'face_value', 1000),
            coupon_rate=bond_config.coupon_rate,
            coupon_frequency=getattr(bond_config, 'coupon_frequency', 2),
            maturity_date=maturity,
            day_count_convention=getattr(bond_config, 'day_count_convention', 'ACT/ACT')
        )
        
        self._bond_params_cache[isin] = params
        return params
    
    def _safe_calculate_ytm(
        self, 
        price: float, 
        bond_params: BondParams, 
        accrued_interest: float = 0.0
    ) -> Optional[float]:
        """
        Безопасный расчёт YTM с обработкой ошибок
        
        Args:
            price: Цена в % от номинала
            bond_params: Параметры облигации
            accrued_interest: НКД в рублях
            
        Returns:
            YTM в % годовых
        """
        if price is None or price <= 0:
            return None
        
        try:
            return self._ytm_calculator.calculate_ytm(price, bond_params, accrued_interest=accrued_interest)
        except Exception as e:
            logger.debug(f"Ошибка расчёта YTM: {e}")
            # Возвращаем упрощённый расчёт
            return self._ytm_calculator.calculate_ytm_simple(price, bond_params)
    
    def _make_request(self, url: str, params: Dict) -> requests.Response:
        """
        Выполнить запрос с повторными попытками
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = self._session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"Попытка {attempt + 1} не удалась: {e}")
                time_module.sleep(1 * (attempt + 1))
        
        raise last_error
    
    def close(self):
        """Закрыть сессию"""
        self._session.close()


# Удобные функции
def get_hourly_candles_with_ytm(
    isin: str,
    bond_config: Any,
    days: int = 1
) -> pd.DataFrame:
    """
    Получить часовые свечи с YTM за указанный период
    
    Args:
        isin: ISIN код облигации
        bond_config: Конфигурация облигации (BondConfig)
        days: Количество дней
        
    Returns:
        DataFrame со свечами и YTM
    """
    fetcher = CandleFetcher()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    return fetcher.fetch_candles(
        isin,
        bond_config=bond_config,
        interval=CandleInterval.MIN_60,
        start_date=start_date,
        end_date=end_date
    )


def get_today_hourly_ytm(
    isin: str,
    bond_config: Any
) -> pd.DataFrame:
    """
    Получить часовые данные с YTM за сегодня
    
    Args:
        isin: ISIN код облигации
        bond_config: Конфигурация облигации
        
    Returns:
        DataFrame с часовыми данными
    """
    fetcher = CandleFetcher()
    return fetcher.fetch_hourly_ytm(isin, bond_config, date.today())
