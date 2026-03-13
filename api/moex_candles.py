"""
Получение внутридневных свечей с Мосбиржи

Только сырые данные OHLCV, без расчёта YTM.
Для расчёта YTM используйте services.candle_processor_ytm_for_bonds.BondYTMProcessor
"""
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

from api.moex_client import MOEXClient

logger = logging.getLogger(__name__)


class CandleInterval(Enum):
    """Интервалы свечей MOEX"""
    MIN_1 = "1"      # 1 минута
    MIN_10 = "10"    # 10 минут
    MIN_60 = "60"    # 1 час
    MIN_240 = "240"  # 4 часа
    DAY = "24"       # 1 день
    WEEK = "7"       # 1 неделя
    MONTH = "31"     # 1 месяц


@dataclass
class Candle:
    """Данные свечи (сырые, без YTM)"""
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    value: Optional[float] = None


# ==========================================
# ФУНКЦИИ API
# ==========================================

def fetch_candles(
    isin: str,
    interval: CandleInterval = CandleInterval.MIN_60,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    board: str = "TQOB",
    client: MOEXClient = None
) -> pd.DataFrame:
    """
    Получить свечи по инструменту (сырые, без YTM)

    Args:
        isin: ISIN код инструмента
        interval: Интервал свечей
        start_date: Начальная дата
        end_date: Конечная дата
        board: Торговая площадка (TQOB для облигаций)
        client: MOEXClient

    Returns:
        DataFrame с колонками: open, high, low, close, volume, value
    """
    if start_date is None:
        start_date = date.today() - timedelta(days=7)
    if end_date is None:
        end_date = date.today()

    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        all_data = []
        start = 0
        batch_size = 500

        while True:
            data = client.get_json(
                f"/engines/stock/markets/bonds/boards/{board}/securities/{isin}/candles.json",
                {
                    "from": start_date.isoformat(),
                    "till": end_date.isoformat(),
                    "interval": interval.value,
                    "iss.meta": "off",
                    "start": start,
                    "limit": batch_size
                }
            )

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

        if not all_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_data)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")
        df = df.sort_index()

        return df

    except Exception as e:
        logger.error(f"Ошибка при получении свечей для {isin}: {e}")
        return pd.DataFrame()

    finally:
        if use_context:
            client.__exit__(None, None, None)


def fetch_candles_with_ytm(
    isin: str,
    bond_config: Any,
    interval: CandleInterval = CandleInterval.MIN_60,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    board: str = "TQOB",
    client: MOEXClient = None
) -> pd.DataFrame:
    """
    Получить свечи с рассчитанным YTM (deprecated wrapper)

    DEPRECATED: Используйте fetch_candles() + BondYTMProcessor
    """
    from services.candle_processor_ytm_for_bonds import BondYTMProcessor

    # Получаем сырые свечи
    df = fetch_candles(isin, interval, start_date, end_date, board, client)

    if df.empty:
        return df

    # Рассчитываем YTM через процессор
    processor = BondYTMProcessor()
    return processor.add_ytm_to_candles(df, bond_config)


# ==========================================
# УДОБНЫЕ ФУНКЦИИ
# ==========================================

def get_raw_candles(
    isin: str,
    interval: CandleInterval = CandleInterval.MIN_60,
    days: int = 7
) -> pd.DataFrame:
    """
    Получить сырые свечи за указанный период

    Args:
        isin: ISIN код инструмента
        interval: Интервал свечей
        days: Количество дней

    Returns:
        DataFrame с OHLCV данными
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    return fetch_candles(isin, interval, start_date, end_date)


# Deprecated: используйте get_raw_candles + BondYTMProcessor
def get_hourly_candles_with_ytm(
    isin: str,
    bond_config: Any,
    days: int = 1
) -> pd.DataFrame:
    """
    DEPRECATED: Используйте get_raw_candles() + BondYTMProcessor
    """
    return fetch_candles_with_ytm(
        isin,
        bond_config=bond_config,
        interval=CandleInterval.MIN_60,
        start_date=date.today() - timedelta(days=days),
        end_date=date.today()
    )


def get_today_hourly_ytm(
    isin: str,
    bond_config: Any
) -> pd.DataFrame:
    """
    DEPRECATED: Используйте get_raw_candles() + BondYTMProcessor
    """
    return fetch_candles_with_ytm(
        isin,
        bond_config=bond_config,
        interval=CandleInterval.MIN_60,
        start_date=date.today(),
        end_date=date.today()
    )
