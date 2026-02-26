"""
Получение внутридневных свечей с Мосбиржи
"""
import requests
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging
import time as time_module

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


class CandleFetcher:
    """Получение внутридневных свечей"""
    
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
    
    def fetch_candles(
        self,
        isin: str,
        interval: CandleInterval = CandleInterval.MIN_60,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        board: str = "TQOB"
    ) -> pd.DataFrame:
        """
        Получить свечи по облигации
        
        Args:
            isin: ISIN код облигации
            interval: Интервал свечей
            start_date: Начальная дата
            end_date: Конечная дата
            board: Торговая площадка
            
        Returns:
            DataFrame со свечами
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=7)
        if end_date is None:
            end_date = date.today()
        
        # Сначала нужно найти SECID для свечей
        secid = self._find_secid_for_candles(isin, board)
        
        if not secid:
            logger.warning(f"Не удалось найти SECID для свечей {isin}")
            return pd.DataFrame()
        
        all_data = []
        start = 0
        batch_size = 500
        
        while True:
            url = f"{self.MOEX_BASE_URL}/engines/stock/markets/bonds/boards/{board}/securities/{secid}/candles.json"
            params = {
                "from": start_date.isoformat(),
                "till": end_date.isoformat(),
                "interval": interval.value,
                "iss.meta": "off",
                "iss.only": "candles",
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
        
        return df
    
    def fetch_hourly_ytm(
        self,
        isin: str,
        trading_date: Optional[date] = None,
        board: str = "TQOB"
    ) -> pd.DataFrame:
        """
        Получить почасовые данные YTM за торговый день
        
        Args:
            isin: ISIN код облигации
            trading_date: Дата торгов
            board: Торговая площадка
            
        Returns:
            DataFrame с почасовыми данными
        """
        if trading_date is None:
            trading_date = date.today()
        
        # Получаем часовые свечи по цене
        candles_df = self.fetch_candles(
            isin,
            interval=CandleInterval.MIN_60,
            start_date=trading_date,
            end_date=trading_date,
            board=board
        )
        
        if candles_df.empty:
            return pd.DataFrame()
        
        # Получаем информацию об облигации для расчёта YTM
        bond_info = self._get_bond_params(isin, board)
        
        if not bond_info:
            return candles_df
        
        # Рассчитываем YTM из цены (упрощённо)
        candles_df["ytm"] = candles_df["close"].apply(
            lambda price: self._estimate_ytm_from_price(price, bond_info)
        )
        
        return candles_df
    
    def fetch_multi_bonds_candles(
        self,
        isins: List[str],
        interval: CandleInterval = CandleInterval.MIN_60,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        board: str = "TQOB",
        delay: float = 0.3
    ) -> Dict[str, pd.DataFrame]:
        """
        Получить свечи для нескольких облигаций
        
        Args:
            isins: Список ISIN кодов
            interval: Интервал свечей
            start_date: Начальная дата
            end_date: Конечная дата
            board: Торговая площадка
            delay: Задержка между запросами
            
        Returns:
            Словарь {ISIN: DataFrame}
        """
        results = {}
        
        for isin in isins:
            logger.info(f"Загрузка свечей для {isin}...")
            df = self.fetch_candles(isin, interval, start_date, end_date, board)
            
            if not df.empty:
                results[isin] = df
            else:
                logger.warning(f"Нет свечей для {isin}")
            
            time_module.sleep(delay)
        
        return results
    
    def get_today_hourly(
        self,
        isins: List[str],
        board: str = "TQOB"
    ) -> Dict[str, pd.DataFrame]:
        """
        Получить почасовые данные за сегодня
        
        Args:
            isins: Список ISIN кодов
            board: Торговая площадка
            
        Returns:
            Словарь {ISIN: DataFrame}
        """
        return self.fetch_multi_bonds_candles(
            isins,
            interval=CandleInterval.MIN_60,
            start_date=date.today(),
            end_date=date.today(),
            board=board
        )
    
    def _find_secid_for_candles(self, isin: str, board: str) -> Optional[str]:
        """
        Найти SECID для получения свечей
        
        Для свечей может требоваться короткий идентификатор.
        
        Args:
            isin: ISIN код облигации
            board: Торговая площадка
            
        Returns:
            SECID или ISIN
        """
        url = f"{self.MOEX_BASE_URL}/securities/{isin}.json"
        params = {
            "iss.meta": "off",
            "iss.only": "boards"
        }
        
        try:
            response = self._make_request(url, params)
            data = response.json()
            
            boards = data.get("boards", {})
            rows = boards.get("data", [])
            columns = boards.get("columns", [])
            
            for row in rows:
                row_dict = dict(zip(columns, row))
                if row_dict.get("boardid") == board:
                    return row_dict.get("secid", isin)
            
            return isin
            
        except Exception as e:
            logger.debug(f"Ошибка при поиске SECID: {e}")
            return isin
    
    def _get_bond_params(self, isin: str, board: str) -> Optional[Dict[str, Any]]:
        """
        Получить параметры облигации для расчёта YTM
        
        Args:
            isin: ISIN код
            board: Торговая площадка
            
        Returns:
            Словарь с параметрами
        """
        url = f"{self.MOEX_BASE_URL}/securities/{isin}.json"
        params = {
            "iss.meta": "off",
            "iss.only": "description"
        }
        
        try:
            response = self._make_request(url, params)
            data = response.json()
            
            description = data.get("description", {})
            rows = description.get("data", [])
            
            params_dict = {}
            for row in rows:
                if row[0] == "COUPONPERCENT":
                    params_dict["coupon_rate"] = float(row[2]) if row[2] else None
                elif row[0] == "MATDATE":
                    params_dict["maturity_date"] = row[2]
                elif row[0] == "FACEVALUE":
                    params_dict["face_value"] = float(row[2]) if row[2] else 1000
                elif row[0] == "DURATION":
                    params_dict["duration"] = float(row[2]) if row[2] else None
            
            return params_dict if params_dict else None
            
        except Exception as e:
            logger.debug(f"Ошибка при получении параметров: {e}")
            return None
    
    def _estimate_ytm_from_price(self, price: float, params: Dict[str, Any]) -> Optional[float]:
        """
        Оценка YTM из цены (упрощённый расчёт)
        
        Args:
            price: Цена облигации
            params: Параметры облигации
            
        Returns:
            Оценка YTM в процентах
        """
        if not price or price <= 0:
            return None
        
        coupon_rate = params.get("coupon_rate")
        face_value = params.get("face_value", 1000)
        
        if not coupon_rate:
            return None
        
        # Упрощённая формула: YTM ≈ (Купон/Цена - 1) × 100
        # Более точный расчёт требует сложного алгоритма
        try:
            price_ratio = price / face_value
            # Номинальная доходность + коррекция на цену
            estimated_ytm = (coupon_rate / price_ratio) * (1 - (price_ratio - 1) * 0.5)
            return round(estimated_ytm, 2)
        except Exception:
            return None
    
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
def get_hourly_candles(isin: str, days: int = 1) -> pd.DataFrame:
    """
    Получить часовые свечи за указанный период
    
    Args:
        isin: ISIN код облигации
        days: Количество дней
        
    Returns:
        DataFrame со свечами
    """
    fetcher = CandleFetcher()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    return fetcher.fetch_candles(
        isin,
        interval=CandleInterval.MIN_60,
        start_date=start_date,
        end_date=end_date
    )