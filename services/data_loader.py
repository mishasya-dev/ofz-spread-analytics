"""
Сервис загрузки данных для OFZ Spread Analytics

Содержит функции для загрузки данных с MOEX API и кэширования.
Использует MOEXClient для запросов.
"""
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, Optional
import logging
import inspect

from api.moex_client import MOEXClient
from api.moex_history import fetch_ytm_history, get_trading_data
from api.moex_candles import fetch_candles, CandleInterval
from services.trading_calendar import TradingCalendar

logger = logging.getLogger(__name__)


def _get_caller_info(skip_frames: int = 2) -> str:
    """Получить информацию о вызывающей функции"""
    try:
        frame = inspect.currentframe()
        for _ in range(skip_frames):
            if frame is None:
                return "unknown"
            frame = frame.f_back
        if frame is None:
            return "unknown"
        caller_name = frame.f_code.co_name
        return caller_name
    except Exception:
        return "unknown"


def fetch_trading_data(secid: str) -> Dict:
    """
    Получить торговые данные (live) с MOEX.

    Args:
        secid: ISIN облигации

    Returns:
        Dict с торговыми данными или {'has_data': False}
    """
    with MOEXClient() as client:
        return get_trading_data(secid, client=client)


def fetch_trading_data_batch(isins: list) -> Dict[str, Dict]:
    """
    Получить торговые данные для нескольких облигаций (batch).

    Использует параллельные запросы через один MOEXClient.
    Гораздо эффективнее чем вызывать fetch_trading_data для каждой облигации.

    Args:
        isins: Список ISIN облигаций

    Returns:
        Dict {ISIN: Dict с торговыми данными}
    """
    from api.moex_history import get_trading_data_batch as _get_batch
    return _get_batch(isins)


def fetch_historical_data(
    secid: str,
    days: int,
    db=None,
    use_cache: bool = True
) -> pd.DataFrame:
    """
    Получить исторические данные YTM с MOEX.

    Загружает из БД если есть, иначе с MOEX API.
    Поддерживает инкрементальное обновление.

    Args:
        secid: ISIN облигации
        days: Количество дней для загрузки
        db: Экземпляр DatabaseManager
        use_cache: Использовать кэширование Streamlit

    Returns:
        DataFrame с колонками: ytm, price, duration_days
    """
    caller = _get_caller_info()
    calendar = TradingCalendar()
    today = date.today()
    start_date = today - timedelta(days=days)

    if db is None:
        from core.db import get_db_facade
        db = get_db_facade()

    # Проверяем наличие данных в БД
    db_df = db.load_daily_ytm(secid, start_date=start_date)
    last_db_date = db.get_last_daily_ytm_date(secid)

    # Логируем состояние БД
    if db_df.empty:
        logger.info(f"[DATA] fetch_historical_data: secid={secid} days={days} caller={caller} → БД пуста, нужна полная загрузка")
    else:
        db_min_date = db_df.index.min().date() if hasattr(db_df.index.min(), 'date') else db_df.index.min()
        db_max_date = db_df.index.max().date() if hasattr(db_df.index.max(), 'date') else db_df.index.max()
        logger.info(f"[DATA] fetch_historical_data: secid={secid} days={days} caller={caller} → БД: {len(db_df)} записей, даты: {db_min_date}..{db_max_date}")

    # Проверяем покрытие периода с учётом торгового календаря
    need_reload = False
    reload_reason = None
    if not db_df.empty:
        db_min_date = db_df.index.min().date() if hasattr(db_df.index.min(), 'date') else db_df.index.min()
        
        # Находим первый торговый день от start_date
        first_trading_day = calendar.get_first_trading_day_from(start_date)
        
        if db_min_date > first_trading_day:
            # Данные в БД начинаются позже первого торгового дня
            days_diff = (db_min_date - first_trading_day).days
            if days_diff > 5:
                need_reload = True
                reload_reason = f"пропуск {days_diff} дней данных"
                logger.info(f"[DATA] fetch_historical_data: secid={secid} → ПЕРЕЗАГРУЗКА: БД с {db_min_date}, первый торговый день {first_trading_day}, {reload_reason}")
            else:
                logger.info(f"[DATA] fetch_historical_data: secid={secid} → OK: данные с {db_min_date}, первый торговый день от {start_date} = {first_trading_day}")

    if not db_df.empty and last_db_date and not need_reload:
        # Проверяем актуальность данных
        # Используем последний ЗАВЕРШЁННЫЙ торговый день (с доступными историческими данными)
        last_completed_trading_day = calendar.get_last_completed_trading_day()
        
        if last_db_date >= last_completed_trading_day:
            logger.info(f"[DATA] fetch_historical_data: secid={secid} → возврат из БД (последний завершённый торговый день {last_completed_trading_day} уже в БД)")
            return db_df
        
        # Инкрементальное обновление — начинаем с первого торгового дня после последней записи
        next_trading_day = calendar.get_first_trading_day_from(last_db_date + timedelta(days=1))
        
        # Ограничиваем инкремент до последнего завершённого торгового дня
        if next_trading_day > last_completed_trading_day:
            logger.info(f"[DATA] fetch_historical_data: secid={secid} → БД актуальна (следующий торговый день {next_trading_day} > последнего завершённого {last_completed_trading_day})")
            return db_df
        
        new_start = next_trading_day
        logger.info(f"[DATA] fetch_historical_data: secid={secid} → ИНКРЕМЕНТ: обновление с {new_start} по {last_completed_trading_day} (последняя дата в БД: {last_db_date})")

        with MOEXClient() as client:
            new_df = fetch_ytm_history(secid, start_date=new_start, client=client, reason="инкремент")

        if not new_df.empty:
            db.save_daily_ytm(secid, new_df)
            db_df = pd.concat([db_df, new_df])
            db_df = db_df[~db_df.index.duplicated(keep='last')]
            logger.info(f"[DATA] fetch_historical_data: secid={secid} → инкремент: добавлено {len(new_df)} записей")
    else:
        # Полная загрузка
        reason_str = reload_reason or "БД пуста"
        logger.info(f"[DATA] fetch_historical_data: secid={secid} → ПОЛНАЯ ЗАГРУЗКА: {reason_str}")

        with MOEXClient() as client:
            db_df = fetch_ytm_history(secid, start_date=start_date, client=client, reason="полная загрузка")

        if not db_df.empty:
            db.save_daily_ytm(secid, db_df)
            logger.info(f"[DATA] fetch_historical_data: secid={secid} → сохранено {len(db_df)} записей в БД")

    return db_df


def fetch_candle_data(
    isin: str,
    bond_config_dict: Dict,
    interval: str,
    days: int,
    db=None
) -> pd.DataFrame:
    """
    Получить данные свечей с рассчитанным YTM.

    Загружает из БД если есть, иначе рассчитывает из цен свечей.
    Поддерживает инкрементальное обновление.

    Args:
        isin: ISIN облигации
        bond_config_dict: Словарь с параметрами облигации
        interval: Интервал свечей ('1', '10', '60')
        days: Количество дней для загрузки
        db: Экземпляр DatabaseManager

    Returns:
        DataFrame с колонками: close, ytm_close, accrued_interest, volume, value
    """
    from config import BondConfig
    from services.candle_processor_ytm_for_bonds import BondYTMProcessor

    ytm_processor = BondYTMProcessor()

    if db is None:
        from core.db import get_db_facade
        db = get_db_facade()

    bond_config = BondConfig(**bond_config_dict)

    interval_map = {
        "1": CandleInterval.MIN_1,
        "10": CandleInterval.MIN_10,
        "60": CandleInterval.MIN_60,
    }

    candle_interval = interval_map.get(interval, CandleInterval.MIN_60)
    start_date = date.today() - timedelta(days=days)

    # Загружаем из БД (история)
    db_ytm_df = db.load_intraday_ytm(isin, interval, start_date=start_date, end_date=date.today() - timedelta(days=1))

    with MOEXClient() as client:
        # Запрашиваем текущий день - сырые свечи
        raw_today_df = fetch_candles(
            isin,
            interval=candle_interval,
            start_date=date.today(),
            end_date=date.today(),
            client=client
        )
        
        # Рассчитываем YTM для текущего дня
        today_df = pd.DataFrame()
        if not raw_today_df.empty:
            today_df = ytm_processor.add_ytm_to_candles(raw_today_df, bond_config)

        # Проверяем нужно ли обновить историю
        need_history = False
        history_start = start_date
        history_end = None

        if days > 1:
            if db_ytm_df.empty:
                need_history = True
            else:
                # Проверяем покрытие периода
                db_min_date = db_ytm_df.index.min().date() if hasattr(db_ytm_df.index.min(), 'date') else db_ytm_df.index.min()
                if db_min_date > start_date:
                    need_history = True
                    # ОПТИМИЗАЦИЯ: загружаем только недостающий период
                    history_start = start_date
                    history_end = db_min_date - timedelta(days=1)
                    logger.info(f"Данные в БД с {db_min_date}, нужно с {start_date} - дозагружаем")

        if need_history:
            if not db_ytm_df.empty and history_end:
                # Дозагрузка недостающего периода - сырые свечи
                raw_history_df = fetch_candles(
                    isin,
                    interval=candle_interval,
                    start_date=history_start,
                    end_date=history_end,
                    client=client
                )
                
                # Рассчитываем YTM
                history_df = pd.DataFrame()
                if not raw_history_df.empty:
                    history_df = ytm_processor.add_ytm_to_candles(raw_history_df, bond_config)

                if not history_df.empty and 'ytm_close' in history_df.columns:
                    db.save_intraday_ytm(isin, interval, history_df)
                    db_ytm_df = pd.concat([history_df, db_ytm_df])
                    db_ytm_df = db_ytm_df[~db_ytm_df.index.duplicated(keep='last')]
                    logger.info(f"Дозагружены intraday YTM для {isin}: {len(history_df)} записей")
            else:
                # Полная загрузка истории - сырые свечи
                raw_history_df = fetch_candles(
                    isin,
                    interval=candle_interval,
                    start_date=start_date,
                    end_date=date.today() - timedelta(days=1),
                    client=client
                )
                
                # Рассчитываем YTM
                history_df = pd.DataFrame()
                if not raw_history_df.empty:
                    history_df = ytm_processor.add_ytm_to_candles(raw_history_df, bond_config)

                if not history_df.empty and 'ytm_close' in history_df.columns:
                    db.save_intraday_ytm(isin, interval, history_df)
                    db_ytm_df = history_df
                    logger.info(f"Сохранены intraday YTM в БД для {isin}: {len(history_df)} записей")

    # Сохраняем текущие данные
    if not today_df.empty and 'ytm_close' in today_df.columns:
        db.save_intraday_ytm(isin, interval, today_df)

    # Объединяем
    if not db_ytm_df.empty and not today_df.empty:
        result_df = pd.concat([db_ytm_df, today_df])
        result_df = result_df[~result_df.index.duplicated(keep='last')]
    elif not today_df.empty:
        result_df = today_df
    elif not db_ytm_df.empty:
        result_df = db_ytm_df
    else:
        result_df = pd.DataFrame()

    if not result_df.empty:
        result_df = result_df.sort_index()

    return result_df


def update_database_full(
    bonds_list: list = None,
    progress_callback=None
) -> Dict:
    """
    Полное обновление базы данных.

    Args:
        bonds_list: Список облигаций (объекты с isin, name, и т.д.)
        progress_callback: Функция для отчёта о прогрессе (progress, message)

    Returns:
        Dict со статистикой: daily_ytm_saved, intraday_ytm_saved, errors
    """
    from core.db import get_db_facade
    from services.candle_processor_ytm_for_bonds import BondYTMProcessor

    ytm_processor = BondYTMProcessor()
    db = get_db_facade()

    if not bonds_list:
        return {'daily_ytm_saved': 0, 'intraday_ytm_saved': 0, 'errors': ['Нет облигаций']}

    stats = {
        'daily_ytm_saved': 0,
        'intraday_ytm_saved': 0,
        'errors': []
    }

    total_steps = len(bonds_list) * 4
    current_step = 0

    # Используем один MOEXClient для всех запросов
    with MOEXClient() as client:
        # Дневные YTM
        for bond in bonds_list:
            try:
                if progress_callback:
                    progress_callback(current_step / total_steps, f"Загрузка дневных YTM: {bond.name}")

                df = fetch_ytm_history(bond.isin, start_date=date.today() - timedelta(days=730), client=client)
                if not df.empty:
                    saved = db.save_daily_ytm(bond.isin, df)
                    stats['daily_ytm_saved'] += saved
            except Exception as e:
                stats['errors'].append(f"Daily YTM {bond.name}: {str(e)}")

            current_step += 1

        # Intraday YTM
        intervals = [
            ("60", CandleInterval.MIN_60, 30),
            ("10", CandleInterval.MIN_10, 7),
            ("1", CandleInterval.MIN_1, 3),
        ]

        for bond in bonds_list:
            for interval_str, interval_enum, days in intervals:
                try:
                    if progress_callback:
                        progress_callback(current_step / total_steps, f"Загрузка {interval_str}мин свечей: {bond.name}")

                    # Получаем сырые свечи через новый API
                    raw_df = fetch_candles(
                        bond.isin,
                        interval=interval_enum,
                        start_date=date.today() - timedelta(days=days),
                        end_date=date.today(),
                        client=client
                    )
                    
                    # Рассчитываем YTM
                    df = pd.DataFrame()
                    if not raw_df.empty:
                        df = ytm_processor.add_ytm_to_candles(raw_df, bond)

                    if not df.empty and 'ytm_close' in df.columns:
                        saved = db.save_intraday_ytm(bond.isin, interval_str, df)
                        stats['intraday_ytm_saved'] += saved
                except Exception as e:
                    stats['errors'].append(f"Intraday YTM {bond.name} {interval_str}min: {str(e)}")

                current_step += 1

    if progress_callback:
        progress_callback(1.0, "Готово!")

    return stats
