"""
Получение исторических данных с Мосбиржи

Использует MOEXClient для запросов.
"""
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging
import inspect

from api.moex_client import MOEXClient

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
        caller_module = inspect.getmodule(frame)
        module_name = caller_module.__name__ if caller_module else "unknown"
        # Сокращаем имя модуля
        if module_name.startswith("services."):
            module_name = module_name.split(".", 1)[1]
        elif module_name.startswith("api."):
            module_name = module_name.split(".", 1)[1]
        return f"{module_name}.{caller_name}"
    except Exception:
        return "unknown"


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


def is_valid_ytm_row(
    row: list,
    board_idx: Optional[int],
    yield_idx: int,
    target_board: str = 'TQOB'
) -> bool:
    """
    Проверяет, подходит ли строка данных для сохранения.

    Фильтрует по критериям (в порядке проверки):
    1. Торговая площадка должна быть target_board
    2. Значение YTM должно быть (не None)

    Args:
        row: Строка данных из MOEX API
        board_idx: Индекс колонки BOARDID (может быть None)
        yield_idx: Индекс колонки YIELDCLOSE
        target_board: Целевая торговая площадка (default: 'TQOB')

    Returns:
        True если строка проходит все фильтры
    """
    # 1. Фильтр по площадке
    if board_idx is not None and row[board_idx] != target_board:
        return False

    # 2. Фильтр по наличию YTM
    if row[yield_idx] is None:
        return False

    return True


# ==========================================
# ФУНКЦИИ API
# ==========================================

def fetch_ytm_history(
    isin: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    board: str = "TQOB",
    client: MOEXClient = None,
    reason: str = None
) -> pd.DataFrame:
    """
    Получить историю YTM облигации

    Args:
        isin: ISIN код облигации
        start_date: Начальная дата
        end_date: Конечная дата
        board: Торговая площадка
        client: MOEXClient
        reason: Причина запроса (для логирования)

    Returns:
        DataFrame с историей YTM
    """
    caller = _get_caller_info()
    
    if start_date is None:
        start_date = date.today() - timedelta(days=365)
    if end_date is None:
        end_date = date.today()

    # Логируем запрос ДО его выполнения
    period_days = (end_date - start_date).days
    reason_str = f" reason={reason}" if reason else ""
    logger.info(f"[MOEX] fetch_ytm_history: isin={isin} period={start_date}..{end_date} ({period_days} дн.) caller={caller}{reason_str}")

    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        all_data = []
        start = 0
        batch_size = 100
        request_count = 0

        while True:
            request_count += 1
            data = client.get_json(
                f"/history/engines/stock/markets/bonds/securities/{isin}.json",
                {
                    "from": start_date.isoformat(),
                    "till": end_date.isoformat(),
                    "iss.meta": "off",
                    "start": start
                }
            )

            # Данные приходят в ключе 'history'
            history = data.get("history", {})
            columns = history.get("columns", [])
            rows = history.get("data", [])

            if not rows:
                break

            # Находим индексы нужных колонок
            try:
                date_idx = columns.index('TRADEDATE')
                yield_idx = columns.index('YIELDCLOSE')
                duration_idx = columns.index('DURATION') if 'DURATION' in columns else None
                board_idx = columns.index('BOARDID') if 'BOARDID' in columns else None
            except ValueError as e:
                logger.warning(f"Required columns not found for {isin}: {e}")
                break

            # Фильтруем строки с помощью is_valid_ytm_row
            valid_rows = filter(
                lambda r: is_valid_ytm_row(r, board_idx, yield_idx),
                rows
            )

            # Преобразуем в нужный формат
            for row in valid_rows:
                all_data.append({
                    "date": row[date_idx],
                    "ytm": row[yield_idx],
                    "duration_days": row[duration_idx] if duration_idx is not None and row[duration_idx] else None,
                    "secid": isin
                })

            if len(rows) < batch_size:
                break

            start += batch_size

        if not all_data:
            logger.info(f"[MOEX] fetch_ytm_history: isin={isin} → пусто (запросов: {request_count})")
            return pd.DataFrame()

        df = pd.DataFrame(all_data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df = df.sort_index()

        # Удаляем дубликаты дат (оставляем последнее значение)
        duplicates = df.index.duplicated().sum()
        if duplicates > 0:
            logger.warning(f"Удалено {duplicates} дубликатов дат для {isin}")
            df = df[~df.index.duplicated(keep='last')]

        # Конвертируем дюрацию из дней в годы
        if "duration_days" in df.columns:
            df["duration_years"] = df["duration_days"] / 365.25

        # Логируем результат
        date_range = ""
        if not df.empty:
            min_date = df.index.min().strftime('%Y-%m-%d')
            max_date = df.index.max().strftime('%Y-%m-%d')
            date_range = f" даты: {min_date}..{max_date}"
        logger.info(f"[MOEX] fetch_ytm_history: isin={isin} → {len(df)} записей (запросов: {request_count}){date_range}")

        return df

    except Exception as e:
        logger.error(f"Ошибка при получении истории для {isin}: {e}")
        return pd.DataFrame()

    finally:
        if use_context:
            client.__exit__(None, None, None)


def fetch_multi_bonds_history(
    isins: List[str],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    board: str = "TQOB",
    client: MOEXClient = None
) -> Dict[str, pd.DataFrame]:
    """
    Получить историю YTM для нескольких облигаций (последовательно)

    Args:
        isins: Список ISIN кодов
        start_date: Начальная дата
        end_date: Конечная дата
        board: Торговая площадка
        client: MOEXClient

    Returns:
        Словарь {ISIN: DataFrame}
    """
    results = {}

    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        for isin in isins:
            logger.info(f"Загрузка истории для {isin}...")
            df = fetch_ytm_history(isin, start_date, end_date, board, client)

            if not df.empty:
                results[isin] = df
            else:
                logger.warning(f"Нет данных для {isin}")

        return results

    finally:
        if use_context:
            client.__exit__(None, None, None)


def fetch_multi_bonds_history_parallel(
    isins: List[str],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    board: str = "TQOB",
    max_workers: int = 3,
    client: MOEXClient = None
) -> Dict[str, pd.DataFrame]:
    """
    Получить историю YTM для нескольких облигаций (параллельно)

    Args:
        isins: Список ISIN кодов
        start_date: Начальная дата
        end_date: Конечная дата
        board: Торговая площадка
        max_workers: Максимум параллельных запросов
        client: MOEXClient

    Returns:
        Словарь {ISIN: DataFrame}
    """
    if start_date is None:
        start_date = date.today() - timedelta(days=365)
    if end_date is None:
        end_date = date.today()

    use_context = client is None
    if use_context:
        client = MOEXClient(max_workers=max_workers)
        client.__enter__()

    try:
        results = {}

        # Подготавливаем запросы
        requests_list = [
            (
                f"/history/engines/stock/markets/bonds/securities/{isin}.json",
                {
                    "from": start_date.isoformat(),
                    "till": end_date.isoformat(),
                    "iss.meta": "off"
                }
            )
            for isin in isins
        ]

        # Запускаем параллельные запросы
        futures = client.request_batch(requests_list)

        # Собираем результаты
        for isin, future in zip(isins, futures):
            try:
                response = future.result(timeout=60)
                data = response.json()

                history = data.get("history", {})
                columns = history.get("columns", [])
                rows = history.get("data", [])

                if not rows:
                    continue

                # Находим индексы
                try:
                    date_idx = columns.index('TRADEDATE')
                    yield_idx = columns.index('YIELDCLOSE')
                    board_idx = columns.index('BOARDID') if 'BOARDID' in columns else None
                except ValueError:
                    continue

                all_data = []
                for row in rows:
                    if board_idx is not None and row[board_idx] != board:
                        continue
                    if row[yield_idx] is None:
                        continue

                    all_data.append({
                        "date": row[date_idx],
                        "ytm": row[yield_idx],
                        "secid": isin
                    })

                if all_data:
                    df = pd.DataFrame(all_data)
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date")
                    df = df.sort_index()
                    df = df[~df.index.duplicated(keep='last')]
                    results[isin] = df

            except Exception as e:
                logger.warning(f"Ошибка загрузки истории для {isin}: {e}")

        return results

    finally:
        if use_context:
            client.__exit__(None, None, None)


def fetch_bond_info(isin: str, client: MOEXClient = None) -> Dict[str, Any]:
    """
    Получить информацию об облигации

    Args:
        isin: ISIN код облигации
        client: MOEXClient

    Returns:
        Словарь с информацией об облигации
    """
    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        data = client.get_json(
            f"/securities/{isin}.json",
            {
                "iss.meta": "off",
                "iss.only": "description,boards"
            }
        )

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
            "coupon_rate": _parse_float(desc_data.get("COUPONPERCENT")),
            "maturity_date": desc_data.get("MATDATE"),
            "face_value": _parse_float(desc_data.get("FACEVALUE")),
            "board": board_info.get("boardid", "TQOB"),
            "lot_size": board_info.get("lotsize", 1),
        }

    except Exception as e:
        logger.error(f"Ошибка при получении информации для {isin}: {e}")
        return {"isin": isin, "error": str(e)}

    finally:
        if use_context:
            client.__exit__(None, None, None)


def get_latest_ytm(isin: str, board: str = "TQOB", client: MOEXClient = None) -> Optional[float]:
    """
    Получить последнее значение YTM

    Args:
        isin: ISIN код облигации
        board: Торговая площадка
        client: MOEXClient

    Returns:
        YTM или None
    """
    df = fetch_ytm_history(
        isin,
        start_date=date.today() - timedelta(days=7),
        board=board,
        client=client
    )

    if df.empty or "ytm" not in df.columns:
        return None

    return df["ytm"].iloc[-1]


def get_trading_data(
    isin: str,
    board: str = "TQOB",
    client: MOEXClient = None
) -> Dict[str, Any]:
    """
    Получить текущие торговые данные

    Args:
        isin: ISIN код облигации
        board: Торговая площадка
        client: MOEXClient

    Returns:
        Словарь с торговыми данными
    """
    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        data = client.get_json(
            f"/engines/stock/markets/bonds/securities/{isin}.json",
            {"iss.meta": "off"}
        )

        # Парсим marketdata
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

    finally:
        if use_context:
            client.__exit__(None, None, None)


# ==========================================
# УДОБНЫЕ ФУНКЦИИ
# ==========================================

def get_ytm_history(isin: str, days: int = 365) -> pd.DataFrame:
    """
    Получить историю YTM за указанный период

    Args:
        isin: ISIN код облигации
        days: Количество дней

    Returns:
        DataFrame с историей
    """
    start_date = date.today() - timedelta(days=days)
    return fetch_ytm_history(isin, start_date=start_date)


# ==========================================
# HELPERS
# ==========================================

def _parse_float(value: Any) -> Optional[float]:
    """Парсинг числа с плавающей точкой"""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
