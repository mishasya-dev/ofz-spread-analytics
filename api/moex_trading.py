"""
Проверка статуса торгов на Мосбирже
"""
import requests
from datetime import datetime, time, date
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class TradingStatus(Enum):
    """Статус торгов"""
    OPEN = "open"                    # Основная сессия открыта
    CLOSED = "closed"                # Биржа закрыта
    PREMARKET = "premarket"          # Предторговый период
    POSTMARKET = "postmarket"        # Послеторговый период
    HOLIDAY = "holiday"              # Праздничный день
    WEEKEND = "weekend"              # Выходной день
    MAINTENANCE = "maintenance"      # Технический перерыв


@dataclass
class ExchangeInfo:
    """Информация о статусе биржи"""
    status: TradingStatus
    is_trading: bool
    message: str
    current_time: datetime
    session_start: Optional[datetime] = None
    session_end: Optional[datetime] = None
    next_session: Optional[datetime] = None


class TradingChecker:
    """Проверка статуса торгов на Мосбирже"""
    
    MOEX_BASE_URL = "https://iss.moex.com/iss"
    
    # Часы торговли для рынка облигаций
    PREMARKET_START = time(6, 50)
    MAIN_SESSION_START = time(7, 0)
    MAIN_SESSION_END = time(15, 40)
    POSTMARKET_START = time(15, 45)
    POSTMARKET_END = time(16, 0)
    
    # Российские праздники 2024-2025 (примеры)
    HOLIDAYS_2024 = [
        "2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04",
        "2024-01-05", "2024-01-06", "2024-01-07", "2024-01-08",
        "2024-02-23", "2024-03-08", "2024-04-29", "2024-04-30",
        "2024-05-01", "2024-05-09", "2024-05-10", "2024-06-12",
        "2024-11-04", "2024-12-30", "2024-12-31",
    ]
    
    HOLIDAYS_2025 = [
        "2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06",
        "2025-01-07", "2025-01-08", "2025-02-23", "2025-02-24",
        "2025-03-08", "2025-03-10", "2025-05-01", "2025-05-02",
        "2025-05-09", "2025-06-12", "2025-06-13", "2025-11-03",
        "2025-11-04", "2025-12-31",
    ]
    
    def __init__(self, timeout: int = 10):
        """
        Инициализация
        
        Args:
            timeout: Таймаут запроса в секундах
        """
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "OFZ-Analytics/1.0"
        })
    
    def check_by_api(self, board: str = "TQOB") -> Dict[str, Any]:
        """
        Проверка статуса торгов через API Мосбиржи
        
        Args:
            board: Торговая площадка (TQOB - облигации)
            
        Returns:
            Словарь с информацией о статусе торгов
        """
        try:
            # Проверяем есть ли данные по облигациям
            url = f"{self.MOEX_BASE_URL}/engines/stock/markets/bonds/boards/{board}/securities.json"
            params = {
                "securities.columns": "SECID,YIELD,LAST",
                "iss.only": "marketdata",
                "iss.meta": "off"
            }
            
            response = self._session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            marketdata = data.get("marketdata", {})
            columns = marketdata.get("columns", [])
            rows = marketdata.get("data", [])
            
            # Проверяем есть ли активные данные
            active_count = 0
            for row in rows:
                if len(row) >= 3:
                    # Проверяем YIELD или LAST
                    if row[1] is not None or row[2] is not None:
                        active_count += 1
            
            return {
                "has_trading_data": active_count > 0,
                "active_instruments": active_count,
                "total_instruments": len(rows),
                "board": board,
                "checked_at": datetime.now().isoformat()
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при проверке API: {e}")
            return {
                "has_trading_data": False,
                "active_instruments": 0,
                "total_instruments": 0,
                "board": board,
                "error": str(e),
                "checked_at": datetime.now().isoformat()
            }
    
    def check_by_schedule(self, check_time: Optional[datetime] = None) -> ExchangeInfo:
        """
        Проверка статуса торгов по расписанию
        
        Args:
            check_time: Время для проверки (по умолчанию текущее)
            
        Returns:
            ExchangeInfo с информацией о статусе
        """
        if check_time is None:
            check_time = datetime.now()
        
        current_date = check_time.date()
        current_time = check_time.time()
        
        # Проверяем выходные
        if check_time.weekday() >= 5:  # Суббота = 5, Воскресенье = 6
            return ExchangeInfo(
                status=TradingStatus.WEEKEND,
                is_trading=False,
                message=f"Выходной день ({['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][check_time.weekday()]})",
                current_time=check_time
            )
        
        # Проверяем праздники
        date_str = current_date.isoformat()
        all_holidays = self.HOLIDAYS_2024 + self.HOLIDAYS_2025
        if date_str in all_holidays:
            return ExchangeInfo(
                status=TradingStatus.HOLIDAY,
                is_trading=False,
                message="Праздничный день",
                current_time=check_time
            )
        
        # Проверяем время торговой сессии
        if current_time < self.PREMARKET_START:
            return ExchangeInfo(
                status=TradingStatus.CLOSED,
                is_trading=False,
                message="Биржа закрыта (до начала предторгового периода)",
                current_time=check_time,
                session_start=datetime.combine(current_date, self.MAIN_SESSION_START)
            )
        
        if self.PREMARKET_START <= current_time < self.MAIN_SESSION_START:
            return ExchangeInfo(
                status=TradingStatus.PREMARKET,
                is_trading=False,
                message="Предторговый период (аукцион открытия)",
                current_time=check_time,
                session_start=datetime.combine(current_date, self.MAIN_SESSION_START)
            )
        
        if self.MAIN_SESSION_START <= current_time < self.MAIN_SESSION_END:
            return ExchangeInfo(
                status=TradingStatus.OPEN,
                is_trading=True,
                message="Основная торговая сессия открыта",
                current_time=check_time,
                session_start=datetime.combine(current_date, self.MAIN_SESSION_START),
                session_end=datetime.combine(current_date, self.MAIN_SESSION_END)
            )
        
        if self.POSTMARKET_START <= current_time < self.POSTMARKET_END:
            return ExchangeInfo(
                status=TradingStatus.POSTMARKET,
                is_trading=False,
                message="Послеторговый период (аукцион закрытия)",
                current_time=check_time
            )
        
        # После закрытия
        return ExchangeInfo(
            status=TradingStatus.CLOSED,
            is_trading=False,
            message="Биржа закрыта (после окончания торгов)",
            current_time=check_time,
            next_session=self._get_next_session_date(check_time)
        )
    
    def check_comprehensive(self, board: str = "TQOB") -> ExchangeInfo:
        """
        Комплексная проверка статуса торгов (API + расписание)
        
        Сначала проверяет расписание, затем подтверждает через API.
        
        Args:
            board: Торговая площадка
            
        Returns:
            ExchangeInfo с полной информацией
        """
        # Проверяем по расписанию
        schedule_info = self.check_by_schedule()
        
        # Если по расписанию биржа должна быть открыта, проверяем через API
        if schedule_info.is_trading:
            api_result = self.check_by_api(board)
            
            if api_result.get("error"):
                # Ошибка API - доверяем расписанию
                logger.warning(f"API недоступен, используем расписание: {api_result.get('error')}")
                return schedule_info
            
            if not api_result.get("has_trading_data"):
                # API показывает нет данных - возможно техперерыв
                return ExchangeInfo(
                    status=TradingStatus.MAINTENANCE,
                    is_trading=False,
                    message="Торги приостановлены или технический перерыв",
                    current_time=datetime.now(),
                    session_start=schedule_info.session_start,
                    session_end=schedule_info.session_end
                )
        
        return schedule_info
    
    def is_trading_now(self, board: str = "TQOB") -> bool:
        """
        Быстрая проверка: открыты ли торги сейчас
        
        Args:
            board: Торговая площадка
            
        Returns:
            True если торги открыты
        """
        info = self.check_comprehensive(board)
        return info.is_trading
    
    def get_trading_schedule(self, date: Optional[date] = None) -> Dict[str, Any]:
        """
        Получить расписание торгов на указанную дату
        
        Args:
            date: Дата для проверки (по умолчанию сегодня)
            
        Returns:
            Словарь с расписанием
        """
        if date is None:
            date = datetime.now().date()
        
        return {
            "date": date.isoformat(),
            "premarket_start": self.PREMARKET_START.isoformat(),
            "main_session_start": self.MAIN_SESSION_START.isoformat(),
            "main_session_end": self.MAIN_SESSION_END.isoformat(),
            "postmarket_start": self.POSTMARKET_START.isoformat(),
            "postmarket_end": self.POSTMARKET_END.isoformat(),
            "is_weekend": date.weekday() >= 5,
            "is_holiday": date.isoformat() in (self.HOLIDAYS_2024 + self.HOLIDAYS_2025)
        }
    
    def _get_next_session_date(self, current: datetime) -> datetime:
        """
        Получить дату следующей торговой сессии
        
        Args:
            current: Текущее время
            
        Returns:
            datetime следующей сессии
        """
        next_date = current.date()
        
        # Ищем следующий рабочий день
        for _ in range(7):  # Максимум 7 дней
            next_date = date(next_date.year, next_date.month, next_date.day + 1)
            
            # Пропускаем выходные
            if next_date.weekday() >= 5:
                continue
            
            # Пропускаем праздники
            if next_date.isoformat() in (self.HOLIDAYS_2024 + self.HOLIDAYS_2025):
                continue
            
            break
        
        return datetime.combine(next_date, self.MAIN_SESSION_START)
    
    def close(self):
        """Закрыть сессию"""
        self._session.close()


# Удобная функция для быстрого использования
def is_market_open(board: str = "TQOB") -> bool:
    """
    Быстрая проверка: открыта ли биржа
    
    Args:
        board: Торговая площадка
        
    Returns:
        True если биржа открыта
    """
    checker = TradingChecker()
    return checker.is_trading_now(board)
