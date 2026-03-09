"""
Получение параметров Nelson-Siegel (КБД) с Мосбиржи

MOEX ISS API endpoints:
- /engines/stock/zcyc?date=YYYY-MM-DD — параметры NS за конкретную дату (ОДНА строка)
- /history/engines/stock/zcyc — тиковые данные за текущий день (НЕ исторические!)
- /engines/stock/zcyc/securities — текущие YTM по КБД для облигаций

ВАЖНО: MOEX API для zcyc:
- ИГНОРИРУЕТ параметры from/till (фильтрация по датам)
- ИГНОРИРУЕТ параметр start (пагинация)
- ПРИНИМАЕТ параметр date=YYYY-MM-DD для получения данных за конкретный день

Поэтому исторические данные загружаются ПО ДНЯМ через отдельные запросы.

Формула Nelson-Siegel:
Y(t) = b1 + b2 * f1(t) + b3 * f2(t)

где:
- t = duration (срок до погашения в годах)
- b1 (B1) = долгосрочный уровень ставки (base level) — в базисных пунктах!
- b2 (B2) = краткосрочный наклон (short-term slope)
- b3 (B3) = кривизна (curvature)
- tau (T1) = масштаб времени
- f1(t) = (1 - exp(-t/tau)) / (t/tau)
- f2(t) = f1(t) - exp(-t/tau)

ПРИМЕЧАНИЕ: B1 возвращается в базисных пунктах, нужно делить на 100 для расчетов!
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
    
    # По умолчанию загружаем 2 года истории
    DEFAULT_HISTORY_DAYS = 730  # ~500 торговых дней
    
    def __init__(self, timeout: int = 30, max_retries: int = 3, request_delay: float = 0.1):
        """
        Инициализация
        
        Args:
            timeout: Таймаут запроса в секундах
            max_retries: Максимальное количество повторных попыток
            request_delay: Задержка между запросами (для batch загрузки)
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.request_delay = request_delay
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "OFZ-Analytics/1.0"
        })
    
    def fetch_ns_params_by_date(self, target_date: date) -> Optional[NSParams]:
        """
        Получить параметры Nelson-Siegel за конкретную дату
        
        Endpoint: /engines/stock/zcyc?date=YYYY-MM-DD
        
        Возвращает ОДНУ строку с параметрами NS на конец дня.
        
        Args:
            target_date: Дата для получения параметров
            
        Returns:
            NSParams или None если нет данных
        """
        url = f"{self.MOEX_BASE_URL}/engines/stock/zcyc.json"
        params = {
            "iss.meta": "off",
            "date": target_date.strftime("%Y-%m-%d")
        }
        
        try:
            response = self._make_request(url, params)
            data = response.json()
            
            params_data = data.get("params", {})
            columns = params_data.get("columns", [])
            rows = params_data.get("data", [])
            
            if not rows:
                logger.debug(f"Нет данных NS за {target_date}")
                return None
            
            # Берем последнюю строку (конец дня)
            row = rows[-1]
            
            # Находим индексы колонок
            try:
                date_idx = columns.index('tradedate')
                b1_idx = columns.index('B1')  # Важно: B1 (заглавные!)
                b2_idx = columns.index('B2')
                b3_idx = columns.index('B3')
                t1_idx = columns.index('T1')
            except ValueError as e:
                # Пробуем строчные
                try:
                    b1_idx = columns.index('b1')
                    b2_idx = columns.index('b2')
                    b3_idx = columns.index('b3')
                    t1_idx = columns.index('t1')
                except ValueError:
                    logger.warning(f"Колонки NS не найдены. Available: {columns}")
                    return None
            
            if row[b1_idx] is None or row[t1_idx] is None:
                return None
            
            return NSParams(
                date=target_date,
                b1=row[b1_idx],
                b2=row[b2_idx],
                b3=row[b3_idx],
                t1=row[t1_idx]
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении NS за {target_date}: {e}")
            return None
    
    def fetch_ns_params_history(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        days: Optional[int] = None,
        save_callback=None,
        progress_callback=None,
        batch_size: int = 100
    ) -> pd.DataFrame:
        """
        Получить исторические параметры Nelson-Siegel
        
        Загружает данные ПО ДНЯМ через отдельные запросы к API.
        MOEX API для /history/engines/stock/zcyc ИГНОРИРУЕТ from/till.
        
        Сохраняет инкрементально батчами (по умолчанию каждые 100 дней).
        
        Args:
            start_date: Начальная дата (по умолчанию 2 года назад)
            end_date: Конечная дата (по умолчанию сегодня)
            days: Количество дней для загрузки (альтернатива start_date, по умолчанию 730)
            save_callback: Функция для сохранения (df -> int)
            progress_callback: Функция для прогресса (current, total, date)
            batch_size: Размер батча для инкрементального сохранения
            
        Returns:
            DataFrame с колонками: date, b1, b2, b3, t1
        """
        if end_date is None:
            end_date = date.today()
        
        if start_date is None:
            # Используем days или значение по умолчанию (2 года)
            history_days = days or self.DEFAULT_HISTORY_DAYS
            start_date = end_date - timedelta(days=history_days)
        
        logger.info(f"Период загрузки: {start_date} -- {end_date}")
        
        # Генерируем список торговых дней (без выходных)
        trading_days = []
        current = start_date
        while current <= end_date:
            # Пропускаем выходные
            if current.weekday() < 5:  # 0-4 = пн-пт
                trading_days.append(current)
            current += timedelta(days=1)
        
        logger.info(f"Загрузка NS параметров за {len(trading_days)} дней")
        
        all_params = []
        batch_params = []  # Буфер для батча
        total = len(trading_days)
        total_saved = 0
        
        for i, day in enumerate(trading_days):
            ns = self.fetch_ns_params_by_date(day)
            if ns:
                row = {
                    "date": ns.date,
                    "b1": ns.b1,
                    "b2": ns.b2,
                    "b3": ns.b3,
                    "t1": ns.t1
                }
                all_params.append(row)
                batch_params.append(row)
            
            # Инкрементальное сохранение батчами
            if save_callback and len(batch_params) >= batch_size:
                df_batch = pd.DataFrame(batch_params)
                df_batch["date"] = pd.to_datetime(df_batch["date"])
                df_batch = df_batch.set_index("date")
                saved = save_callback(df_batch)
                total_saved += saved
                logger.info(f"Сохранено батч: {saved} записей (всего: {total_saved})")
                batch_params = []  # Сбрасываем буфер
            
            # Прогресс (каждые 50 дней или в конце)
            if progress_callback and (i % 50 == 0 or i == total - 1):
                progress_callback(i + 1, total, day)
            
            # Задержка для не DDOS
            if i < total - 1:
                time_module.sleep(self.request_delay)
        
        # Сохраняем остаток
        if save_callback and batch_params:
            df_batch = pd.DataFrame(batch_params)
            df_batch["date"] = pd.to_datetime(df_batch["date"])
            df_batch = df_batch.set_index("date")
            saved = save_callback(df_batch)
            total_saved += saved
            logger.info(f"Сохранен последний батч: {saved} записей (всего: {total_saved})")
        
        if not all_params:
            logger.warning("Не удалось загрузить ни одного параметра NS")
            return pd.DataFrame()
        
        logger.info(f"Загружено {len(all_params)} параметров Nelson-Siegel, сохранено: {total_saved}")
        
        # Возвращаем полный DataFrame только если нет save_callback
        if save_callback:
            return pd.DataFrame()  # Уже сохранили
        
        df = pd.DataFrame(all_params)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df = df.sort_index()
        return df
    
    def fetch_ns_params_incremental(
        self,
        last_date: date,
        save_callback=None,
        progress_callback=None
    ) -> pd.DataFrame:
        """
        Получить параметры NS инкрементально (с last_date + 1 до сегодня)
        
        Используется для ежедневного обновления БД.
        
        Args:
            last_date: Последняя дата в БД
            save_callback: Функция для сохранения
            progress_callback: Функция для прогресса
            
        Returns:
            DataFrame с новыми параметрами NS
        """
        start_date = last_date + timedelta(days=1)
        end_date = date.today()
        
        if start_date > end_date:
            logger.info("Данные уже актуальны")
            return pd.DataFrame()
        
        return self.fetch_ns_params_history(
            start_date=start_date,
            end_date=end_date,
            save_callback=save_callback,
            progress_callback=progress_callback
        )
    
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
