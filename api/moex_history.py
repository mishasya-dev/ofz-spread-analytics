"""
Получение исторических данных с Мосбиржи
"""
import requests
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging
import time as time_module

logger = logging.getLogger(__name__)


@dataclass
class BondData:
    """Данные облигации"""
    secid: str
    trade_date: date
    close_price: Optional[float]
    ytm: Optional[float]
    duration: Optional[float]
    duration_years: Optional[float]
    coupon_rate: Optional[float]
    maturity_date: Optional[date]


class HistoryFetcher:
    """Получение исторических данных по облигациям"""
    
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
    
    def fetch_ytm_history(
        self,
        isin: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        board: str = "TQOB"
    ) -> pd.DataFrame:
        """
        Получить историю YTM облигации
        
        Args:
            isin: ISIN код облигации
            start_date: Начальная дата
            end_date: Конечная дата
            board: Торговая площадка
            
        Returns:
            DataFrame с историей YTM
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=365)
        if end_date is None:
            end_date = date.today()
        
        all_data = []
        start = 0
        batch_size = 100
        
        while True:
            # ИСПРАВЛЕНО: URL без /boards/{board}/ - как в рабочей версии
            url = f"{self.MOEX_BASE_URL}/history/engines/stock/markets/bonds/securities/{isin}.json"
            params = {
                "from": start_date.isoformat(),
                "till": end_date.isoformat(),
                "iss.meta": "off",
                "start": start
            }
            
            try:
                response = self._make_request(url, params)
                data = response.json()
                
                # Данные приходят в ключе 'history'
                history = data.get("history", {})
                columns = history.get("columns", [])
                rows = history.get("data", [])
                
                if not rows:
                    break
                
                # ИСПРАВЛЕНО: Находим индексы нужных колонок (как в рабочей версии)
                try:
                    date_idx = columns.index('TRADEDATE')
                    # ИСПРАВЛЕНО: YIELDCLOSE вместо YIELDCOUPON
                    yield_idx = columns.index('YIELDCLOSE')
                    duration_idx = columns.index('DURATION') if 'DURATION' in columns else None
                except ValueError as e:
                    logger.warning(f"Required columns not found for {isin}: {e}")
                    break
                
                for row in rows:
                    if row[yield_idx] is not None:
                        all_data.append({
                            "date": row[date_idx],
                            "ytm": row[yield_idx],
                            "duration_days": row[duration_idx] if duration_idx is not None and row[duration_idx] else None,
                            "secid": isin
                        })
                
                if len(rows) < batch_size:
                    break
                    
                start += batch_size
                
            except Exception as e:
                logger.error(f"Ошибка при получении истории для {isin}: {e}")
                break
        
        if not all_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(all_data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df = df.sort_index()
        
        # Конвертируем дюрацию из дней в годы
        if "duration_days" in df.columns:
            df["duration_years"] = df["duration_days"] / 365.25
        
        return df
    
    def fetch_multi_bonds_history(
        self,
        isins: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        board: str = "TQOB",
        delay: float = 0.3
    ) -> Dict[str, pd.DataFrame]:
        """
        Получить историю YTM для нескольких облигаций
        
        Args:
            isins: Список ISIN кодов
            start_date: Начальная дата
            end_date: Конечная дата
            board: Торговая площадка
            delay: Задержка между запросами (секунды)
            
        Returns:
            Словарь {ISIN: DataFrame}
        """
        results = {}
        
        for isin in isins:
            logger.info(f"Загрузка истории для {isin}...")
            df = self.fetch_ytm_history(isin, start_date, end_date, board)
            
            if not df.empty:
                results[isin] = df
            else:
                logger.warning(f"Нет данных для {isin}")
            
            time_module.sleep(delay)
        
        return results
    
    def fetch_bond_info(self, isin: str) -> Dict[str, Any]:
        """
        Получить информацию об облигации
        
        Args:
            isin: ISIN код облигации
            
        Returns:
            Словарь с информацией об облигации
        """
        url = f"{self.MOEX_BASE_URL}/securities/{isin}.json"
        params = {
            "iss.meta": "off",
            "iss.only": "description,boards"
        }
        
        try:
            response = self._make_request(url, params)
            data = response.json()
            
            # Парсим описание
            description = data.get("description", {})
            desc_data = {row[0]: row[2] for row in description.get("data", [])}
            
            # Парсим торговые площадки
            boards = data.get("boards", {})
            board_data = boards.get("data", [])
            board_info = {}
            if board_data:
                columns = boards.get("columns", [])
                for row in board_data:
                    if "TQOB" in row:
                        board_info = dict(zip(columns, row))
                        break
            
            return {
                "isin": isin,
                "name": desc_data.get("NAME", ""),
                "short_name": desc_data.get("SHORTNAME", ""),
                "coupon_rate": self._parse_float(desc_data.get("COUPONPERCENT")),
                "maturity_date": desc_data.get("MATDATE"),
                "face_value": self._parse_float(desc_data.get("FACEVALUE")),
                "board": board_info.get("boardid", "TQOB"),
                "lot_size": board_info.get("lotsize", 1),
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации для {isin}: {e}")
            return {"isin": isin, "error": str(e)}
    
    def get_latest_ytm(self, isin: str, board: str = "TQOB") -> Optional[float]:
        """
        Получить последнее значение YTM
        
        Args:
            isin: ISIN код облигации
            board: Торговая площадка
            
        Returns:
            YTM или None
        """
        df = self.fetch_ytm_history(
            isin,
            start_date=date.today() - timedelta(days=7),
            board=board
        )
        
        if df.empty or "ytm" not in df.columns:
            return None
        
        return df["ytm"].iloc[-1]
    
    def get_trading_data(
        self,
        isin: str,
        board: str = "TQOB"
    ) -> Dict[str, Any]:
        """
        Получить текущие торговые данные
        
        Args:
            isin: ISIN код облигации
            board: Торговая площадка
            
        Returns:
            Словарь с торговыми данными
        """
        # ИСПРАВЛЕНО: URL как в рабочей версии
        url = f"{self.MOEX_BASE_URL}/engines/stock/markets/bonds/securities/{isin}.json"
        params = {
            "iss.meta": "off"
        }
        
        try:
            response = self._make_request(url, params)
            data = response.json()
            
            # ИСПРАВЛЕНО: Парсим marketdata как в рабочей версии
            marketdata = data.get("marketdata", {})
            md_columns = marketdata.get("columns", [])
            md_rows = marketdata.get("data", [])
            
            result = {"isin": isin, "has_data": False}
            
            # Ищем данные на основной площадке TQOB
            for row in md_rows:
                board_id_idx = md_columns.index('BOARDID')
                if row[board_id_idx] == 'TQOB':
                    yield_idx = md_columns.index('YIELD')
                    duration_idx = md_columns.index('DURATION')
                    price_idx = md_columns.index('MARKETPRICE')
                    
                    ytm = row[yield_idx]
                    duration = row[duration_idx]
                    price = row[price_idx]
                    
                    if ytm is not None:
                        result.update({
                            "has_data": True,
                            "yield": ytm,
                            "duration": duration,
                            "duration_years": duration / 365.25 if duration else None,
                            "price": price,
                            "last": price,
                            "updated_at": datetime.now().isoformat()
                        })
                        break
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении торговых данных для {isin}: {e}")
            return {"isin": isin, "error": str(e), "has_data": False}
    
    def _make_request(self, url: str, params: Dict) -> requests.Response:
        """
        Выполнить запрос с повторными попытками
        
        Args:
            url: URL для запроса
            params: Параметры запроса
            
        Returns:
            Response объект
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
    
    @staticmethod
    def _parse_float(value: Any) -> Optional[float]:
        """Парсинг числа с плавающей точкой"""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def close(self):
        """Закрыть сессию"""
        self._session.close()


# Удобные функции
def get_ytm_history(isin: str, days: int = 365) -> pd.DataFrame:
    """
    Получить историю YTM за указанный период
    
    Args:
        isin: ISIN код облигации
        days: Количество дней
        
    Returns:
        DataFrame с историей
    """
    fetcher = HistoryFetcher()
    start_date = date.today() - timedelta(days=days)
    return fetcher.fetch_ytm_history(isin, start_date=start_date)
