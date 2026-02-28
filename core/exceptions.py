"""
Иерархия исключений для OFZ Spread Analytics

Все исключения наследуются от OFZError для удобной обработки.
"""


class OFZError(Exception):
    """
    Базовое исключение для всех ошибок OFZ Spread Analytics
    
    Все специфичные исключения наследуются от этого класса.
    """
    pass


# ==========================================
# MOEX API Ошибки
# ==========================================

class MOEXError(OFZError):
    """Базовое исключение для ошибок MOEX API"""
    pass


class MOEXConnectionError(MOEXError):
    """Ошибка соединения с MOEX API"""
    pass


class MOEXAPIError(MOEXError):
    """Ошибка MOEX API (неверный запрос, нет данных и т.д.)"""
    
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class MOEXTimeoutError(MOEXError):
    """Таймаут при запросе к MOEX API"""
    pass


class MOEXDataError(MOEXError):
    """Некорректные данные от MOEX API"""
    pass


# ==========================================
# Ошибки расчёта YTM
# ==========================================

class YTMError(OFZError):
    """Базовое исключение для ошибок расчёта YTM"""
    pass


class YTMCalculationError(YTMError):
    """Ошибка при расчёте YTM из цены"""
    
    def __init__(self, message: str, isin: str = None, price: float = None):
        super().__init__(message)
        self.isin = isin
        self.price = price


class YTMConvergenceError(YTMCalculationError):
    """YTM не сошёлся (метод Ньютона-Рафсона)"""
    pass


class YTMMissingDataError(YTMError):
    """Недостаточно данных для расчёта YTM"""
    
    def __init__(self, message: str, missing_fields: list = None):
        super().__init__(message)
        self.missing_fields = missing_fields or []


class InvalidBondDataError(YTMError):
    """Некорректные данные облигации для расчёта YTM"""
    pass


# ==========================================
# Ошибки БД
# ==========================================

class DatabaseError(OFZError):
    """Базовое исключение для ошибок БД"""
    pass


class DatabaseConnectionError(DatabaseError):
    """Ошибка соединения с БД"""
    pass


class DatabaseQueryError(DatabaseError):
    """Ошибка выполнения запроса к БД"""
    
    def __init__(self, message: str, query: str = None):
        super().__init__(message)
        self.query = query


class RecordNotFoundError(DatabaseError):
    """Запись не найдена в БД"""
    
    def __init__(self, table: str, identifier: str):
        super().__init__(f"Record not found: {table}/{identifier}")
        self.table = table
        self.identifier = identifier


# ==========================================
# Ошибки облигаций
# ==========================================

class BondError(OFZError):
    """Базовое исключение для ошибок связанных с облигациями"""
    pass


class BondNotFoundError(BondError):
    """Облигация не найдена"""
    
    def __init__(self, isin: str):
        super().__init__(f"Bond not found: {isin}")
        self.isin = isin


class InvalidISINError(BondError):
    """Некорректный ISIN"""
    
    def __init__(self, isin: str):
        super().__init__(f"Invalid ISIN: {isin}")
        self.isin = isin


class BondMaturedError(BondError):
    """Облигация уже погашена"""
    
    def __init__(self, isin: str, maturity_date: str):
        super().__init__(f"Bond {isin} already matured on {maturity_date}")
        self.isin = isin
        self.maturity_date = maturity_date


# ==========================================
# Ошибки свечей
# ==========================================

class CandleError(OFZError):
    """Базовое исключение для ошибок связанных со свечами"""
    pass


class NoCandlesError(CandleError):
    """Нет свечей для указанного периода"""
    
    def __init__(self, isin: str, interval: str, start_date: str):
        super().__init__(f"No candles for {isin} ({interval}) from {start_date}")
        self.isin = isin
        self.interval = interval
        self.start_date = start_date


class CandleFetchError(CandleError):
    """Ошибка при получении свечей"""
    
    def __init__(self, message: str, isin: str = None, interval: str = None):
        super().__init__(message)
        self.isin = isin
        self.interval = interval


# ==========================================
# Ошибки конфигурации
# ==========================================

class ConfigError(OFZError):
    """Базовое исключение для ошибок конфигурации"""
    pass


class ConfigFileError(ConfigError):
    """Ошибка чтения файла конфигурации"""
    pass


class InvalidConfigError(ConfigError):
    """Некорректная конфигурация"""
    
    def __init__(self, message: str, field: str = None):
        super().__init__(message)
        self.field = field


# ==========================================
# Утилиты для обработки исключений
# ==========================================

def is_retriable_error(error: Exception) -> bool:
    """
    Проверить, является ли ошибка повторяемой
    
    Args:
        error: Исключение
    
    Returns:
        True если запрос можно повторить
    """
    return isinstance(error, (
        MOEXConnectionError,
        MOEXTimeoutError,
        DatabaseConnectionError,
    ))


def get_error_category(error: Exception) -> str:
    """
    Получить категорию ошибки для логирования
    
    Args:
        error: Исключение
    
    Returns:
        Категория ошибки (moex, ytm, db, bond, candle, config, unknown)
    """
    if isinstance(error, MOEXError):
        return 'moex'
    elif isinstance(error, YTMError):
        return 'ytm'
    elif isinstance(error, DatabaseError):
        return 'db'
    elif isinstance(error, BondError):
        return 'bond'
    elif isinstance(error, CandleError):
        return 'candle'
    elif isinstance(error, ConfigError):
        return 'config'
    else:
        return 'unknown'
