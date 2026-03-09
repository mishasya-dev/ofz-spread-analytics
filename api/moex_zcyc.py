"""
Получение параметров Nelson-Siegel (КБД) с Мосбиржи

MOEX ISS API endpoints:
- /history/engines/stock/zcyc — исторические параметры NS
- /engines/stock/zcyc — текущие параметры КБД
- /engines/stock/zcyc/securities — текущие YTM по КБД для облигаций

Формула Nelson-Siegel:
Y(t) = b1 + b2 * f1(t) + b3 * f2(t)

где:
- t = duration (срок до погашения в годах)
- b1 = долгосрочный уровень ставки (base level)
- b2 = краткосрочный наклон (short-term slope)
- b3 = кривизна (curvature)
- tau (t1) = масштаб времени
- f1(t) = (1 - exp(-t/tau)) / (t/tau)
- f2(t) = f1(t) - exp(-t/tau)
"""
import requests
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import logging
import time as time_module

logger = logging.getLogger(__name__)


@dataclass
class NSParams:
    """Параметры Nelson-Siegel на дату"""
    date: date
    b1: float  # Долгосрочный уровень
    b2: float  # Краткосрочный наклон
    b3: float  # Кривизна
    t1: float  # Масштаб времени (tau)


class ZCYCFetcher:
    """Получение параметров КБД (Zero-Coupon Yield Curve) с MOEX"""
    
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
    
    def fetch_ns_params_history(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        save_callback=None,
        batch_save_size: int = 1000
    ) -> pd.DataFrame:
        """
        Получить исторические параметры Nelson-Siegel
        
        Endpoint: /history/engines/stock/zcyc
        
        MOEX возвращает параметры NS во внутреннем формате:
        - B1, B2, B3 — параметры кривой (НЕ проценты!)
        - T1 — параметр масштаба времени (tau)
        
        Для расчёта YTM_КБД нужно интерполировать по yearyields
        или использовать clcyield из securities.
        
        Args:
            start_date: Начальная дата
            end_date: Конечная дата
            save_callback: Функция для инкрементального сохранения (df -> int)
            batch_save_size: Сохранять каждые N записей
            
        Returns:
            DataFrame с колонками: date, b1, b2, b3, t1
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=365)
        if end_date is None:
            end_date = date.today()
        
        all_data = []
        start = 0
        batch_size = 500
        total_saved = 0
        
        while True:
            url = f"{self.MOEX_BASE_URL}/history/engines/stock/zcyc.json"
            params = {
                "from": start_date.isoformat(),
                "till": end_date.isoformat(),
                "iss.meta": "off",
                "start": start
            }
            
            try:
                response = self._make_request(url, params)
                data = response.json()
                
                # Данные приходят в ключе 'params' (не 'zcyc'!)
                params_data = data.get("params", {})
                columns = params_data.get("columns", [])
                rows = params_data.get("data", [])
                
                if not rows:
                    break
                
                # Находим индексы нужных колонок
                # MOEX возвращает в нижнем регистре: b1, b2, b3, t1
                try:
                    date_idx = columns.index('tradedate')
                    b1_idx = columns.index('b1')
                    b2_idx = columns.index('b2')
                    b3_idx = columns.index('b3')
                    t1_idx = columns.index('t1')
                except ValueError as e:
                    logger.warning(f"Required columns not found in params: {e}")
                    logger.warning(f"Available columns: {columns}")
                    break
                
                # Преобразуем в нужный формат
                for row in rows:
                    # Пропускаем строки с None значениями
                    if row[b1_idx] is None or row[t1_idx] is None:
                        continue
                    
                    all_data.append({
                        "date": row[date_idx],
                        "b1": row[b1_idx],
                        "b2": row[b2_idx],
                        "b3": row[b3_idx],
                        "t1": row[t1_idx]
                    })
                
                # Инкрементальное сохранение
                if save_callback and len(all_data) >= batch_save_size:
                    df_batch = pd.DataFrame(all_data)
                    df_batch["date"] = pd.to_datetime(df_batch["date"])
                    df_batch = df_batch.set_index("date")
                    saved = save_callback(df_batch)
                    total_saved += saved
                    logger.info(f"Инкрементально сохранено {saved} записей (всего {total_saved})")
                    all_data = []  # Очищаем буфер
                
                if len(rows) < batch_size:
                    break
                    
                start += batch_size
                
            except Exception as e:
                logger.error(f"Ошибка при получении параметров NS: {e}")
                # Сохраняем то, что успели загрузить
                if save_callback and all_data:
                    df_batch = pd.DataFrame(all_data)
                    df_batch["date"] = pd.to_datetime(df_batch["date"])
                    df_batch = df_batch.set_index("date")
                    saved = save_callback(df_batch)
                    total_saved += saved
                    logger.info(f"При разрыве сохранено {saved} записей (всего {total_saved})")
                break
        
        # Сохраняем остаток
        if save_callback and all_data:
            df_batch = pd.DataFrame(all_data)
            df_batch["date"] = pd.to_datetime(df_batch["date"])
            df_batch = df_batch.set_index("date")
            saved = save_callback(df_batch)
            total_saved += saved
            logger.info(f"Финальное сохранение: {saved} записей (всего {total_saved})")
            return pd.DataFrame()  # Возвращаем пустой, т.к. уже сохранили
        
        if not all_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(all_data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df = df.sort_index()
        
        # Удаляем дубликаты дат (оставляем последнюю запись за день)
        duplicates = df.index.duplicated().sum()
        if duplicates > 0:
            logger.warning(f"Удалено {duplicates} дубликатов дат в параметрах NS")
            df = df[~df.index.duplicated(keep='last')]
        
        logger.info(f"Загружено {len(df)} записей параметров Nelson-Siegel")
        return df
    
    def fetch_current_zcyc(self) -> Dict[str, Any]:
        """
        Получить текущие параметры КБД (11 точек по срокам)
        
        Endpoint: /engines/stock/zcyc
        
        Returns:
            Словарь с текущими параметрами КБД
        """
        url = f"{self.MOEX_BASE_URL}/engines/stock/zcyc.json"
        params = {"iss.meta": "off"}
        
        try:
            response = self._make_request(url, params)
            data = response.json()
            
            result = {"has_data": False, "points": [], "params": {}}
            
            # Точки yearyields (11 сроков: 0.25, 0.5, 0.75, ..., 30 лет)
            yearyields = data.get("yearyields", {})
            if yearyields.get("data"):
                columns = yearyields.get("columns", [])
                for row in yearyields["data"]:
                    point = dict(zip(columns, row))
                    result["points"].append(point)
                result["has_data"] = True
            
            # Параметры NS (если есть)
            zcyc_params = data.get("params", {})
            if zcyc_params.get("data"):
                columns = zcyc_params.get("columns", [])
                for row in zcyc_params["data"]:
                    param = dict(zip(columns, row))
                    result["params"][param.get("name", "")] = param.get("value")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении текущих параметров КБД: {e}")
            return {"has_data": False, "error": str(e)}
    
    def fetch_current_clcyield(self, isin: str) -> Optional[float]:
        """
        Получить текущий YTM по КБД для конкретной облигации
        
        Endpoint: /engines/stock/zcyc/securities
        
        Args:
            isin: ISIN облигации
            
        Returns:
            YTM по КБД (%) или None
        """
        url = f"{self.MOEX_BASE_URL}/engines/stock/zcyc/securities.json"
        params = {
            "iss.meta": "off",
            "securities": isin
        }
        
        try:
            response = self._make_request(url, params)
            data = response.json()
            
            securities = data.get("securities", {})
            columns = securities.get("columns", [])
            rows = securities.get("data", [])
            
            if not rows:
                return None
            
            # Ищем колонку clcyield (calculated yield by curve)
            if "clcyield" in columns:
                clcyield_idx = columns.index("clcyield")
                for row in rows:
                    if row[clcyield_idx] is not None:
                        return row[clcyield_idx]
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении clcyield для {isin}: {e}")
            return None
    
    def fetch_all_clcyields(self, isins: List[str]) -> Dict[str, Optional[float]]:
        """
        Получить текущие YTM по КБД для списка облигаций
        
        Args:
            isins: Список ISIN
            
        Returns:
            Словарь {ISIN: clcyield}
        """
        url = f"{self.MOEX_BASE_URL}/engines/stock/zcyc/securities.json"
        params = {
            "iss.meta": "off",
            "securities": ",".join(isins)
        }
        
        try:
            response = self._make_request(url, params)
            data = response.json()
            
            securities = data.get("securities", {})
            columns = securities.get("columns", [])
            rows = securities.get("data", [])
            
            result = {isin: None for isin in isins}
            
            if not rows or "clcyield" not in columns:
                return result
            
            secid_idx = columns.index("secid")
            clcyield_idx = columns.index("clcyield")
            
            for row in rows:
                secid = row[secid_idx]
                clcyield = row[clcyield_idx]
                if secid in result:
                    result[secid] = clcyield
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении clcyields: {e}")
            return {isin: None for isin in isins}
    
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
    
    def close(self):
        """Закрыть сессию"""
        self._session.close()


# Удобные функции
def get_ns_params_history(days: int = 365) -> pd.DataFrame:
    """
    Получить историю параметров Nelson-Siegel
    
    Args:
        days: Количество дней
        
    Returns:
        DataFrame с параметрами NS
    """
    fetcher = ZCYCFetcher()
    start_date = date.today() - timedelta(days=days)
    return fetcher.fetch_ns_params_history(start_date=start_date)


def get_current_clcyield(isin: str) -> Optional[float]:
    """
    Получить текущий YTM по КБД для облигации
    
    Args:
        isin: ISIN облигации
        
    Returns:
        YTM по КБД (%)
    """
    fetcher = ZCYCFetcher()
    return fetcher.fetch_current_clcyield(isin)
