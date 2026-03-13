"""
Получение списка всех ОФЗ с Московской биржи

Использует MOEXClient для запросов.
"""
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import logging

from api.moex_client import MOEXClient, get_client

logger = logging.getLogger(__name__)


# ==========================================
# ФУНКЦИИ API
# ==========================================

def fetch_all_bonds(client: MOEXClient = None, market: str = "bonds") -> List[Dict[str, Any]]:
    """
    Получить список всех облигаций с MOEX

    Args:
        client: MOEXClient (если None, используется глобальный)
        market: Рынок (bonds для ОФЗ)

    Returns:
        Список словарей с данными облигаций
    """
    all_bonds = []
    start = 0
    batch_size = 100

    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        while True:
            data = client.get_json(
                f"/engines/stock/markets/{market}/securities.json",
                {
                    "iss.meta": "off",
                    "securities.columns": "SECID,NAME,SHORTNAME,FACEVALUE,FACEUNIT,COUPONPERCENT,MATDATE,ISQUALIFIEDINVESTOR",
                    "start": start,
                }
            )

            securities = data.get("securities", {})
            columns = securities.get("columns", [])
            rows = securities.get("data", [])

            if not rows:
                break

            for row in rows:
                bond = dict(zip(columns, row))

                # Фильтруем только рублёвые облигации
                if bond.get("FACEUNIT") != "SUR":
                    continue

                # Пропускаем для квалифицированных инвесторов
                if bond.get("ISQUALIFIEDINVESTOR") == 1:
                    continue

                all_bonds.append({
                    "isin": bond.get("SECID"),
                    "name": bond.get("NAME"),
                    "short_name": bond.get("SHORTNAME"),
                    "face_value": bond.get("FACEVALUE"),
                    "coupon_rate": bond.get("COUPONPERCENT"),
                    "maturity_date": bond.get("MATDATE"),
                })

            if len(rows) < batch_size:
                break

            start += batch_size

    finally:
        if use_context:
            client.__exit__(None, None, None)

    logger.info(f"Получено {len(all_bonds)} облигаций с MOEX")
    return all_bonds


def fetch_ofz_only(client: MOEXClient = None) -> List[Dict[str, Any]]:
    """
    Получить только ОФЗ облигации (оптимизировано - из marketdata)

    Args:
        client: MOEXClient (если None, используется глобальный)

    Returns:
        Список ОФЗ облигаций
    """
    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        data = client.get_json(
            "/engines/stock/markets/bonds/securities.json",
            {
                "iss.meta": "off",
                "securities.columns": "SECID,NAME,SHORTNAME,FACEVALUE,COUPONPERCENT,MATDATE",
                "marketdata.columns": "SECID,BOARDID",
            }
        )

        # Получаем ISIN с TQOB (только торгующиеся на основном рынке)
        marketdata = data.get("marketdata", {})
        md_rows = marketdata.get("data", [])
        tqob_isins = set()
        for row in md_rows:
            if row[1] == "TQOB":  # BOARDID
                tqob_isins.add(row[0])

        # Получаем securities
        securities = data.get("securities", {})
        columns = securities.get("columns", [])
        rows = securities.get("data", [])

        ofz_bonds = []
        seen_isins = set()

        for row in rows:
            bond = dict(zip(columns, row))
            isin = bond.get("SECID", "")

            # Убираем дубли
            if isin in seen_isins:
                continue

            # Только ОФЗ-ПД (26xxx, 25xxx, 24xxx)
            if not (isin.startswith("SU26") or isin.startswith("SU25") or isin.startswith("SU24")):
                continue

            # Только если торгуется на TQOB
            if isin not in tqob_isins:
                continue

            seen_isins.add(isin)
            ofz_bonds.append({
                "isin": isin,
                "name": bond.get("NAME"),
                "short_name": bond.get("SHORTNAME"),
                "face_value": bond.get("FACEVALUE"),
                "coupon_rate": bond.get("COUPONPERCENT"),
                "maturity_date": bond.get("MATDATE"),
            })

        logger.info(f"Найдено {len(ofz_bonds)} ОФЗ облигаций")
        return ofz_bonds

    finally:
        if use_context:
            client.__exit__(None, None, None)


def fetch_bond_details(isin: str, client: MOEXClient = None) -> Dict[str, Any]:
    """
    Получить детальную информацию об облигации

    Args:
        isin: ISIN облигации
        client: MOEXClient

    Returns:
        Словарь с детальной информацией
    """
    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        data = client.get_json(f"/securities/{isin}.json", {"iss.meta": "off"})

        # Парсим описание
        description = data.get("description", {})
        desc_data = {}
        for row in description.get("data", []):
            if len(row) >= 3:
                desc_data[row[0]] = row[2]

        # Парсим boards для получения дюрации и цены
        boards = data.get("boards", {})
        boards_data = boards.get("data", [])
        board_columns = boards.get("columns", [])

        board_info = {}
        for row in boards_data:
            board_dict = dict(zip(board_columns, row))
            if board_dict.get("boardid") == "TQOB":
                board_info = board_dict
                break

        return {
            "isin": isin,
            "name": desc_data.get("NAME", ""),
            "short_name": desc_data.get("SHORTNAME", ""),
            "coupon_rate": _parse_float(desc_data.get("COUPONPERCENT")),
            "maturity_date": desc_data.get("MATDATE"),
            "issue_date": desc_data.get("ISSUEDATE"),
            "face_value": _parse_float(desc_data.get("FACEVALUE")) or 1000,
            "coupon_frequency": _parse_int(desc_data.get("COUPONFREQUENCY")) or 2,
            "day_count": desc_data.get("DAYCOUNTCONVENTION", "ACT/ACT"),
            "duration_days": _parse_float(board_info.get("DURATION")),
            "duration_years": None,
            "last_price": _parse_float(board_info.get("MARKETPRICE")),
            "last_ytm": _parse_float(board_info.get("YIELD")),
            "last_trade_date": board_info.get("LASTTRADEDATE"),
        }

    except Exception as e:
        logger.error(f"Ошибка при получении деталей для {isin}: {e}")
        return {"isin": isin, "error": str(e)}

    finally:
        if use_context:
            client.__exit__(None, None, None)


def fetch_market_data(isin: str, client: MOEXClient = None) -> Dict[str, Any]:
    """
    Получить рыночные данные облигации (YTM, дюрация, цена)

    Args:
        isin: ISIN облигации
        client: MOEXClient

    Returns:
        Словарь с рыночными данными
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

        marketdata = data.get("marketdata", {})
        md_columns = marketdata.get("columns", [])
        md_rows = marketdata.get("data", [])

        result = {
            "isin": isin,
            "has_data": False,
            "last_price": None,
            "last_ytm": None,
            "duration_days": None,
            "duration_years": None,
            "last_trade_date": None,
        }

        # Ищем данные на площадке TQOB
        for row in md_rows:
            if "BOARDID" in md_columns:
                board_idx = md_columns.index("BOARDID")
                if row[board_idx] == "TQOB":
                    def get_value(col_name):
                        if col_name in md_columns:
                            idx = md_columns.index(col_name)
                            return row[idx] if idx < len(row) else None
                        return None

                    duration_days = _parse_float(get_value("DURATION"))
                    duration_years = duration_days / 365.25 if duration_days else None

                    result.update({
                        "has_data": True,
                        "last_price": _parse_float(get_value("MARKETPRICE")),
                        "last_ytm": _parse_float(get_value("YIELD")),
                        "duration_days": duration_days,
                        "duration_years": duration_years,
                        "last_trade_date": get_value("LASTTRADEDATE"),
                    })
                    break

        return result

    except Exception as e:
        logger.error(f"Ошибка при получении рыночных данных для {isin}: {e}")
        return {"isin": isin, "has_data": False, "error": str(e)}

    finally:
        if use_context:
            client.__exit__(None, None, None)


def fetch_all_market_data(client: MOEXClient = None) -> Dict[str, Dict[str, Any]]:
    """
    Получить рыночные данные для ВСЕХ облигаций одним запросом (оптимизировано)

    Args:
        client: MOEXClient

    Returns:
        Словарь {isin: {ytm, duration_days, price, num_trades, ...}}
    """
    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        data = client.get_json(
            "/engines/stock/markets/bonds/securities.json",
            {
                "iss.meta": "off",
                "securities.columns": "SECID",
                "marketdata.columns": "SECID,BOARDID,YIELD,DURATION,MARKETPRICE,NUMTRADES,VALTODAY",
            }
        )

        # Парсим marketdata
        marketdata = data.get("marketdata", {})
        columns = marketdata.get("columns", [])
        rows = marketdata.get("data", [])

        result = {}

        for row in rows:
            row_dict = dict(zip(columns, row))

            # Только TQOB (основной рынок)
            if row_dict.get("BOARDID") != "TQOB":
                continue

            isin = row_dict.get("SECID")
            if not isin:
                continue

            duration_days = _parse_float(row_dict.get("DURATION"))
            duration_years = duration_days / 365.25 if duration_days else None
            num_trades = _parse_int(row_dict.get("NUMTRADES"))
            val_today = _parse_float(row_dict.get("VALTODAY"))

            result[isin] = {
                "isin": isin,
                "has_data": True,
                "last_ytm": _parse_float(row_dict.get("YIELD")),
                "last_price": _parse_float(row_dict.get("MARKETPRICE")),
                "duration_days": duration_days,
                "duration_years": duration_years,
                "num_trades": num_trades,
                "val_today": val_today,
                "has_trades": num_trades is not None and num_trades > 0,
            }

        logger.info(f"Получены рыночные данные для {len(result)} облигаций (пакетный запрос)")
        return result

    except Exception as e:
        logger.error(f"Ошибка при пакетном получении рыночных данных: {e}")
        return {}

    finally:
        if use_context:
            client.__exit__(None, None, None)


def fetch_ofz_with_market_data(
    client: MOEXClient = None,
    include_details: bool = False
) -> List[Dict[str, Any]]:
    """
    Получить ОФЗ с рыночными данными

    Args:
        client: MOEXClient
        include_details: Загружать детальную информацию (медленнее)

    Returns:
        Список ОФЗ с рыночными данными
    """
    use_context = client is None
    if use_context:
        client = MOEXClient()
        client.__enter__()

    try:
        ofz_bonds = fetch_ofz_only(client)
        result = []

        # ОПТИМИЗИРОВАННЫЙ ПУТЬ: один запрос для всех рыночных данных
        all_market_data = fetch_all_market_data(client)

        for bond in ofz_bonds:
            isin = bond["isin"]
            market_data = all_market_data.get(isin, {"has_data": False})

            bond_data = {
                **bond,
                "last_price": market_data.get("last_price"),
                "last_ytm": market_data.get("last_ytm"),
                "duration_days": market_data.get("duration_days"),
                "duration_years": market_data.get("duration_years"),
                "num_trades": market_data.get("num_trades"),
                "val_today": market_data.get("val_today"),
                "has_trades": market_data.get("has_trades", False),
                "has_market_data": market_data.get("has_data", False),
            }

            # Детали загружаем только если нужно (медленно)
            if include_details:
                details = fetch_bond_details(isin, client)
                bond_data.update({
                    "issue_date": details.get("issue_date"),
                    "coupon_frequency": details.get("coupon_frequency"),
                    "day_count": details.get("day_count"),
                })

            result.append(bond_data)

        logger.info(f"Получено {len(result)} ОФЗ с рыночными данными")
        return result

    finally:
        if use_context:
            client.__exit__(None, None, None)


# ==========================================
# УДОБНЫЕ ФУНКЦИИ (с context manager)
# ==========================================

def fetch_all_ofz() -> List[Dict[str, Any]]:
    """
    Получить список всех ОФЗ (с автоматическим context manager)

    Returns:
        Список словарей с данными ОФЗ
    """
    with MOEXClient() as client:
        return fetch_ofz_only(client)


# ==========================================
# ФИЛЬТРАЦИЯ ОФЗ
# ==========================================

# Константы фильтрации
MIN_MATURITY_DAYS = 183  # 0.5 года
MAX_TRADE_DAYS_AGO = 10  # Торги за последние 10 дней (не используется, оставлено для совместимости)


def filter_ofz_for_trading(
    bonds: List[Dict[str, Any]],
    min_maturity_days: int = MIN_MATURITY_DAYS,
    max_trade_days_ago: int = MAX_TRADE_DAYS_AGO,
    require_duration: bool = True,
    require_trades: bool = True
) -> List[Dict[str, Any]]:
    """
    Отфильтровать ОФЗ по критериям для торговли

    Критерии:
    - ОФЗ-ПД (26xxx, 25xxx, 24xxx) - постоянный купон
    - Срок до погашения > min_maturity_days (по умолчанию 183 дня = 0.5 года)
    - Наличие сделок (has_trades=True или num_trades > 0)
    - Наличие дюрации (если require_duration=True)

    Args:
        bonds: Список облигаций с данными (maturity_date, has_trades/num_trades, duration_days)
        min_maturity_days: Минимальный срок до погашения в днях
        max_trade_days_ago: Не используется (оставлено для совместимости)
        require_duration: Требовать наличие дюрации
        require_trades: Требовать наличие сделок сегодня

    Returns:
        Отфильтрованный список облигаций
    """
    today = date.today()

    filtered = []

    for bond in bonds:
        isin = bond.get("isin", "")

        # 1. Проверка ОФЗ-ПД (26xxx, 25xxx, 24xxx)
        if not (isin.startswith("SU26") or isin.startswith("SU25") or isin.startswith("SU24")):
            continue

        # 2. Проверка срока до погашения
        maturity_date = bond.get("maturity_date")
        if maturity_date:
            if isinstance(maturity_date, str):
                try:
                    maturity_date = datetime.strptime(maturity_date, "%Y-%m-%d").date()
                except ValueError:
                    continue

            days_to_maturity = (maturity_date - today).days
            if days_to_maturity <= min_maturity_days:
                continue
        else:
            # Нет даты погашения - пропускаем
            continue

        # 3. Проверка наличия торгов (по has_trades или num_trades)
        if require_trades:
            has_trades = bond.get("has_trades", False)
            num_trades = bond.get("num_trades", 0)
            if not has_trades and (num_trades is None or num_trades <= 0):
                continue

        # 4. Проверка дюрации
        if require_duration:
            duration_days = bond.get("duration_days")
            if duration_days is None or duration_days <= 0:
                continue

        # Добавляем вычисленные поля
        bond_filtered = {**bond}
        bond_filtered["days_to_maturity"] = days_to_maturity
        bond_filtered["is_filtered"] = True

        filtered.append(bond_filtered)

    # Сортируем по дюрации
    filtered.sort(key=lambda b: b.get("duration_years") or b.get("duration_days") or 0)

    logger.info(
        f"Фильтрация: {len(bonds)} -> {len(filtered)} облигаций "
        f"(maturity>{min_maturity_days}д, trades<{max_trade_days_ago}д)"
    )

    return filtered


def fetch_and_filter_ofz(
    min_maturity_days: int = MIN_MATURITY_DAYS,
    max_trade_days_ago: int = MAX_TRADE_DAYS_AGO,
    include_details: bool = False
) -> List[Dict[str, Any]]:
    """
    Получить и отфильтровать ОФЗ за один вызов

    Args:
        min_maturity_days: Минимальный срок до погашения в днях
        max_trade_days_ago: Максимальное количество дней с последней торговли
        include_details: Загружать детальную информацию

    Returns:
        Отфильтрованный список ОФЗ
    """
    with MOEXClient() as client:
        # Получаем ОФЗ с рыночными данными
        bonds = fetch_ofz_with_market_data(client, include_details=include_details)

        # Фильтруем
        return filter_ofz_for_trading(
            bonds,
            min_maturity_days=min_maturity_days,
            max_trade_days_ago=max_trade_days_ago
        )


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


def _parse_int(value: Any) -> Optional[int]:
    """Парсинг целого числа"""
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None
