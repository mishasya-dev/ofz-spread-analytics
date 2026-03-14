"""
Получение параметров Nelson-Siegel (КБД) с Мосбиржи

MOEX ISS API endpoints:
- /engines/stock/zcyc?date=YYYY-MM-DD — параметры NS за конкретную дату (ОДНА строка)
- /history/engines/stock/zcyc — тиковые данные за текущий день (НЕ исторические!)
- /engines/stock/zcyc/securities — текущие YTM по КБД для облигаций

Использует MOEXClient для запросов.
"""
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import logging

from api.moex_client import MOEXClient

logger = logging.getLogger(__name__)


@dataclass
class NSParams:
    """Параметры Nelson-Siegel на дату"""
    date: date
    b1: float  # Долгосрочный уровень
    b2: float  # Краткосрочный наклон
    b3: float  # Кривизна
    t1: float  # Масштаб времени (tau)


# По умолчанию загружаем 2 года истории
DEFAULT_HISTORY_DAYS = 730  # ~500 торговых дней


# ==========================================
# ФУНКЦИИ API
# ==========================================

def fetch_ns_params_by_date(
    target_date: date,
    client: MOEXClient = None
) -> Optional[NSParams]:
    """
    Получить параметры Nelson-Siegel за конкретную дату

    Endpoint: /engines/stock/zcyc?date=YYYY-MM-DD

    Args:
        target_date: Дата для получения параметров
        client: MOEXClient

    Returns:
        NSParams или None если нет данных
    """
    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        data = client.get_json(
            "/engines/stock/zcyc.json",
            {
                "iss.meta": "off",
                "date": target_date.strftime("%Y-%m-%d")
            }
        )

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
            b1_idx = columns.index('B1')  # Важно: B1 (заглавные!)
            b2_idx = columns.index('B2')
            b3_idx = columns.index('B3')
            t1_idx = columns.index('T1')
        except ValueError:
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

    finally:
        if use_context:
            client.__exit__(None, None, None)


def fetch_ns_params_history(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    days: Optional[int] = None,
    save_callback=None,
    progress_callback=None,
    batch_size: int = 100,
    client: MOEXClient = None
) -> pd.DataFrame:
    """
    Получить исторические параметры Nelson-Siegel

    Загружает данные ПО ДНЯМ через параллельные запросы.

    Args:
        start_date: Начальная дата (по умолчанию 2 года назад)
        end_date: Конечная дата (по умолчанию сегодня)
        days: Количество дней для загрузки (альтернатива start_date)
        save_callback: Функция для сохранения (df -> int)
        progress_callback: Функция для прогресса (current, total, date)
        batch_size: Размер батча для инкрементального сохранения
        client: MOEXClient

    Returns:
        DataFrame с колонками: date, b1, b2, b3, t1
    """
    if end_date is None:
        end_date = date.today()

    if start_date is None:
        history_days = days or DEFAULT_HISTORY_DAYS
        start_date = end_date - timedelta(days=history_days)

    logger.info(f"Период загрузки: {start_date} -- {end_date}")

    # Генерируем список торговых дней (без выходных)
    trading_days = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # 0-4 = пн-пт
            trading_days.append(current)
        current += timedelta(days=1)

    logger.info(f"Загрузка NS параметров за {len(trading_days)} дней")

    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        all_params = []
        batch_params = []
        total = len(trading_days)
        total_saved = 0

        # Подготавливаем запросы для параллельной загрузки
        for i, day in enumerate(trading_days):
            ns = fetch_ns_params_by_date(day, client)
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
                batch_params = []

            # Прогресс
            if progress_callback and (i % 50 == 0 or i == total - 1):
                progress_callback(i + 1, total, day)

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

        if save_callback:
            return pd.DataFrame()

        df = pd.DataFrame(all_params)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df = df.sort_index()
        return df

    finally:
        if use_context:
            client.__exit__(None, None, None)


def fetch_ns_params_incremental(
    last_date: date,
    save_callback=None,
    progress_callback=None,
    client: MOEXClient = None
) -> pd.DataFrame:
    """
    Получить параметры NS инкрементально (с last_date + 1 до сегодня)

    Args:
        last_date: Последняя дата в БД
        save_callback: Функция для сохранения
        progress_callback: Функция для прогресса
        client: MOEXClient

    Returns:
        DataFrame с новыми параметрами NS
    """
    start_date = last_date + timedelta(days=1)
    end_date = date.today()

    if start_date > end_date:
        logger.info("Данные уже актуальны")
        return pd.DataFrame()

    return fetch_ns_params_history(
        start_date=start_date,
        end_date=end_date,
        save_callback=save_callback,
        progress_callback=progress_callback,
        client=client
    )


def fetch_current_zcyc(client: MOEXClient = None) -> Dict[str, Any]:
    """
    Получить текущие параметры КБД (11 точек по срокам)

    Args:
        client: MOEXClient

    Returns:
        Словарь с текущими параметрами КБД
    """
    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        data = client.get_json("/engines/stock/zcyc.json", {"iss.meta": "off"})

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

    finally:
        if use_context:
            client.__exit__(None, None, None)


def fetch_current_clcyield(isin: str, client: MOEXClient = None) -> Optional[float]:
    """
    Получить текущий YTM по КБД для конкретной облигации

    Args:
        isin: ISIN облигации
        client: MOEXClient

    Returns:
        YTM по КБД (%) или None
    """
    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        data = client.get_json(
            "/engines/stock/zcyc/securities.json",
            {
                "iss.meta": "off",
                "securities": isin
            }
        )

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

    finally:
        if use_context:
            client.__exit__(None, None, None)


def fetch_all_clcyields(isins: List[str], client: MOEXClient = None) -> Dict[str, Optional[float]]:
    """
    Получить текущие YTM по КБД для списка облигаций

    Args:
        isins: Список ISIN
        client: MOEXClient

    Returns:
        Словарь {ISIN: clcyield}
    """
    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        data = client.get_json(
            "/engines/stock/zcyc/securities.json",
            {
                "iss.meta": "off",
                "securities": ",".join(isins)
            }
        )

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

    finally:
        if use_context:
            client.__exit__(None, None, None)


# ==========================================
# УДОБНЫЕ ФУНКЦИИ
# ==========================================

def get_ns_params_history(days: int = 365) -> pd.DataFrame:
    """
    Получить историю параметров Nelson-Siegel

    Args:
        days: Количество дней

    Returns:
        DataFrame с параметрами NS
    """
    start_date = date.today() - timedelta(days=days)
    return fetch_ns_params_history(start_date=start_date)


def get_zcyc_data_for_date(target_date: date, client: MOEXClient = None) -> pd.DataFrame:
    """
    Получить данные ZCYC (G-spread) за конкретную дату

    Args:
        target_date: Дата для получения данных
        client: MOEXClient

    Returns:
        DataFrame с колонками: date, secid, shortname, trdyield, clcyield,
                               duration_days, g_spread_bp
    """
    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        data = client.get_json(
            "/engines/stock/zcyc.json",
            {
                "iss.meta": "off",
                "date": target_date.strftime("%Y-%m-%d")
            }
        )

        securities = data.get("securities", {})
        if not securities.get("data"):
            return pd.DataFrame()

        df = pd.DataFrame(
            securities["data"],
            columns=securities.get("columns", [])
        )

        # Фильтруем только записи с данными
        df = df[df['clcyield'].notna() & df['trdyield'].notna()]

        if df.empty:
            return pd.DataFrame()

        # Выбираем нужные колонки
        result = pd.DataFrame({
            'date': pd.to_datetime(target_date),
            'secid': df['secid'],
            'shortname': df['shortname'],
            'trdyield': df['trdyield'].astype(float),
            'clcyield': df['clcyield'].astype(float),
            'duration_days': df['crtduration'].astype(float),
        })

        # G-spread в базисных пунктах
        result['g_spread_bp'] = (result['trdyield'] - result['clcyield']) * 100

        return result

    except Exception as e:
        logger.error(f"Ошибка при получении ZCYC за {target_date}: {e}")
        return pd.DataFrame()

    finally:
        if use_context:
            client.__exit__(None, None, None)


def get_zcyc_history(
    start_date: date,
    end_date: date = None,
    isin: str = None,
    progress_callback=None,
    use_cache: bool = True,
    save_callback=None,
    client: MOEXClient = None
) -> pd.DataFrame:
    """
    Получить историю ZCYC (G-spread) за период с кэшированием

    При use_cache=True:
    1. Проверяет кэш БД
    2. Загружает только недостающие даты с MOEX
    3. Сохраняет новые данные в кэш

    Args:
        start_date: Начальная дата
        end_date: Конечная дата (по умолчанию сегодня)
        isin: ISIN облигации для фильтрации
        progress_callback: Функция прогресса (current, total, date)
        use_cache: Использовать кэш БД
        save_callback: Функция для сохранения в БД (df -> int)
        client: MOEXClient

    Returns:
        DataFrame с ZCYC данными
    """
    if end_date is None:
        end_date = date.today()

    # Генерируем список торговых дней
    trading_days = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            trading_days.append(current)
        current += timedelta(days=1)

    all_data = []
    dates_to_fetch = trading_days.copy()

    # Проверяем кэш
    if use_cache and save_callback:
        try:
            from core.db import get_g_spread_repo
            repo = get_g_spread_repo()

            cached_df = repo.load_zcyc(isin=isin, start_date=start_date, end_date=end_date)
            all_cached_dates = repo.get_zcyc_cached_dates(
                isin=None,
                start_date=start_date,
                end_date=end_date
            )

            if not cached_df.empty:
                all_data.append(cached_df)

            dates_to_fetch = [d for d in trading_days if d not in all_cached_dates]

            empty_dates = repo.load_empty_dates(start_date=start_date, end_date=end_date)
            if empty_dates:
                dates_to_fetch = [d for d in dates_to_fetch if d not in empty_dates]

            logger.info(f"Из кэша: {len(cached_df)} записей, дат в кэше: {len(all_cached_dates)}, нужно загрузить: {len(dates_to_fetch)} дней")
        except Exception as e:
            logger.warning(f"Ошибка при чтении кэша: {e}")

    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        # Загружаем недостающие данные
        if dates_to_fetch:
            total = len(dates_to_fetch)
            new_data = []

            for i, day in enumerate(dates_to_fetch):
                df = get_zcyc_data_for_date(day, client)

                if not df.empty:
                    if isin:
                        df = df[df['secid'] == isin]
                    if not df.empty:
                        new_data.append(df)

                if progress_callback and (i % 10 == 0 or i == total - 1):
                    progress_callback(i + 1, total, day)

            if new_data:
                new_df = pd.concat(new_data, ignore_index=True)
                all_data.append(new_df)

                if use_cache and save_callback:
                    try:
                        saved = save_callback(new_df)
                        logger.info(f"Сохранено в кэш: {saved} записей")
                    except Exception as e:
                        logger.warning(f"Ошибка при сохранении в кэш: {e}")

        if not all_data:
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)
        result = result.sort_values('date').reset_index(drop=True)

        logger.info(f"Всего загружено {len(result)} записей ZCYC за {len(trading_days)} дней")

        return result

    finally:
        if use_context:
            client.__exit__(None, None, None)


def get_zcyc_history_parallel(
    start_date: date,
    end_date: date = None,
    isin: str = None,
    progress_callback=None,
    use_cache: bool = True,
    save_callback=None,
    max_workers: int = 5,
    client: MOEXClient = None
) -> pd.DataFrame:
    """
    Параллельная загрузка истории ZCYC (G-spread) за период

    Использует MOEXClient.request_batch для параллельных запросов.
    Ускорение в 3-5 раз по сравнению с последовательной загрузкой.

    Args:
        start_date: Начальная дата
        end_date: Конечная дата
        isin: ISIN облигации для фильтрации
        progress_callback: Функция прогресса
        use_cache: Использовать кэш БД
        save_callback: Функция для сохранения в БД
        max_workers: Максимум параллельных запросов (default: 5)
        client: MOEXClient

    Returns:
        DataFrame с ZCYC данными
    """
    if end_date is None:
        end_date = date.today()

    # Генерируем список торговых дней
    trading_days = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            trading_days.append(current)
        current += timedelta(days=1)

    all_data = []
    dates_to_fetch = trading_days.copy()

    # Проверяем кэш
    # ВАЖНО: Проверяем кэш ДЛЯ КОНКРЕТНОГО ISIN!
    # MOEX ZCYC API возвращает данные для ВСЕХ облигаций сразу,
    # но нам нужно знать: есть ли данные для ЭТОГО ISIN на эти даты?
    # Если нет - загружаем (получим все облигации) и сохраняем все в БД
    if use_cache:
        try:
            from core.db import get_g_spread_repo
            repo = get_g_spread_repo()

            # Загружаем даты, для которых есть данные в кэше ДЛЯ ЭТОГО ISIN
            cached_dates_for_isin = repo.get_zcyc_cached_dates(
                isin=isin,  # Фильтруем по ISIN!
                start_date=start_date,
                end_date=end_date
            )

            # Загружаем кэшированные данные для нужного ISIN
            cached_df = repo.load_zcyc(isin=isin, start_date=start_date, end_date=end_date)

            if not cached_df.empty:
                all_data.append(cached_df)

            # Загружаем только те даты, которых нет в кэше ДЛЯ ЭТОГО ISIN
            dates_to_fetch = [d for d in trading_days if d not in cached_dates_for_isin]

            empty_dates = repo.load_empty_dates(start_date=start_date, end_date=end_date)
            if empty_dates:
                dates_to_fetch = [d for d in dates_to_fetch if d not in empty_dates]

            logger.info(f"Из кэша: {len(cached_df)} записей для {isin}, дат в кэше для ISIN: {len(cached_dates_for_isin)}, нужно загрузить: {len(dates_to_fetch)} дней")
        except Exception as e:
            logger.warning(f"Ошибка при чтении кэша: {e}")

    if not dates_to_fetch:
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            result = result.sort_values('date').reset_index(drop=True)
            return result
        return pd.DataFrame()

    use_context = client is None
    if use_context:
        client = MOEXClient(max_workers=max_workers)
        client.__enter__()

    try:
        # Параллельная загрузка через request_batch
        total = len(dates_to_fetch)
        new_data = []
        empty_dates = []

        # Подготавливаем запросы
        requests_list = [
            (
                "/engines/stock/zcyc.json",
                {"iss.meta": "off", "date": day.strftime("%Y-%m-%d")}
            )
            for day in dates_to_fetch
        ]

        # Запускаем параллельные запросы
        futures = client.request_batch(requests_list)

        # Собираем результаты
        completed = 0
        for i, (future, day) in enumerate(zip(futures, dates_to_fetch)):
            try:
                response = future.result(timeout=60)
                data = response.json()

                securities = data.get("securities", {})
                if securities.get("data"):
                    df = pd.DataFrame(
                        securities["data"],
                        columns=securities.get("columns", [])
                    )
                    df = df[df['clcyield'].notna() & df['trdyield'].notna()]

                    if not df.empty:
                        result_df = pd.DataFrame({
                            'date': pd.to_datetime(day),
                            'secid': df['secid'],
                            'shortname': df['shortname'],
                            'trdyield': df['trdyield'].astype(float),
                            'clcyield': df['clcyield'].astype(float),
                            'duration_days': df['crtduration'].astype(float),
                        })
                        result_df['g_spread_bp'] = (result_df['trdyield'] - result_df['clcyield']) * 100

                        # ОПТИМИЗАЦИЯ: НЕ фильтруем по ISIN при загрузке!
                        # Сохраняем ВСЕ облигации в БД, фильтруем только при возврате
                        if not result_df.empty:
                            new_data.append(result_df)
                else:
                    empty_dates.append(day)

            except Exception as e:
                logger.warning(f"Ошибка загрузки {day}: {e}")
                empty_dates.append(day)

            completed += 1
            if progress_callback and (completed % 10 == 0 or completed == total):
                progress_callback(completed, total, day)

        # Сохраняем пустые даты
        if empty_dates and use_cache:
            try:
                from core.db import get_g_spread_repo
                repo = get_g_spread_repo()
                saved_empty = repo.save_empty_dates(empty_dates)
                logger.info(f"Сохранено {saved_empty} пустых дат")
            except Exception as e:
                logger.warning(f"Ошибка при сохранении пустых дат: {e}")

        if new_data:
            new_df = pd.concat(new_data, ignore_index=True)
            all_data.append(new_df)

            if use_cache and save_callback:
                try:
                    saved = save_callback(new_df)
                    logger.info(f"Сохранено в кэш: {saved} записей")
                except Exception as e:
                    logger.warning(f"Ошибка при сохранении в кэш: {e}")

        if not all_data:
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)
        result = result.sort_values('date').reset_index(drop=True)

        # Фильтруем по ISIN только при возврате (если нужно)
        if isin:
            result = result[result['secid'] == isin]

        logger.info(f"Всего загружено {len(result)} записей ZCYC за {len(trading_days)} дней" + (f" (отфильтровано по {isin})" if isin else " (все облигации)"))

        return result

    finally:
        if use_context:
            client.__exit__(None, None, None)
