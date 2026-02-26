"""
Получение списка всех ОФЗ с Московской биржи

Используется для динамического управления облигациями в версии 0.2.0
"""
import requests
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import logging
import time as time_module

logger = logging.getLogger(__name__)


class MOEXBondsFetcher:
    """Получение списка облигаций с MOEX"""

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

    def fetch_all_bonds(self, market: str = "bonds") -> List[Dict[str, Any]]:
        """
        Получить список всех облигаций с MOEX

        Args:
            market: Рынок (bonds для ОФЗ)

        Returns:
            Список словарей с данными облигаций
        """
        url = f"{self.MOEX_BASE_URL}/engines/stock/markets/{market}/securities.json"
        params = {
            "iss.meta": "off",
            "securities.columns": "SECID,NAME,SHORTNAME,FACEVALUE,FACEUNIT,COUPONPERCENT,MATDATE,ISQUALIFIEDINVESTOR"
        }

        all_bonds = []
        start = 0
        batch_size = 100

        while True:
            params["start"] = start

            try:
                response = self._make_request(url, params)
                data = response.json()

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

            except Exception as e:
                logger.error(f"Ошибка при получении списка облигаций: {e}")
                break

        logger.info(f"Получено {len(all_bonds)} облигаций с MOEX")
        return all_bonds

    def fetch_ofz_only(self) -> List[Dict[str, Any]]:
        """
        Получить только ОФЗ облигации

        Returns:
            Список ОФЗ облигаций
        """
        all_bonds = self.fetch_all_bonds()

        # Фильтруем ОФЗ по ISIN (SU26..., SU25...)
        ofz_bonds = []
        for bond in all_bonds:
            isin = bond.get("isin", "")
            # ОФЗ имеют ISIN вида SU26xxxRMFSx, SU25xxxRMFSx, SU24xxxRMFSx
            if isin.startswith("SU26") or isin.startswith("SU25") or isin.startswith("SU24"):
                ofz_bonds.append(bond)

        logger.info(f"Найдено {len(ofz_bonds)} ОФЗ облигаций")
        return ofz_bonds

    def fetch_bond_details(self, isin: str) -> Dict[str, Any]:
        """
        Получить детальную информацию об облигации

        Args:
            isin: ISIN облигации

        Returns:
            Словарь с детальной информацией
        """
        url = f"{self.MOEX_BASE_URL}/securities/{isin}.json"
        params = {
            "iss.meta": "off"
        }

        try:
            response = self._make_request(url, params)
            data = response.json()

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
                "coupon_rate": self._parse_float(desc_data.get("COUPONPERCENT")),
                "maturity_date": desc_data.get("MATDATE"),
                "issue_date": desc_data.get("ISSUEDATE"),
                "face_value": self._parse_float(desc_data.get("FACEVALUE")) or 1000,
                "coupon_frequency": self._parse_int(desc_data.get("COUPONFREQUENCY")) or 2,
                "day_count": desc_data.get("DAYCOUNTCONVENTION", "ACT/ACT"),
                "duration_days": self._parse_float(board_info.get("DURATION")),
                "duration_years": None,
                "last_price": self._parse_float(board_info.get("MARKETPRICE")),
                "last_ytm": self._parse_float(board_info.get("YIELD")),
                "last_trade_date": board_info.get("LASTTRADEDATE"),
            }

        except Exception as e:
            logger.error(f"Ошибка при получении деталей для {isin}: {e}")
            return {"isin": isin, "error": str(e)}

    def fetch_market_data(self, isin: str) -> Dict[str, Any]:
        """
        Получить рыночные данные облигации (YTM, дюрация, цена)

        Args:
            isin: ISIN облигации

        Returns:
            Словарь с рыночными данными
        """
        url = f"{self.MOEX_BASE_URL}/engines/stock/markets/bonds/securities/{isin}.json"
        params = {
            "iss.meta": "off"
        }

        try:
            response = self._make_request(url, params)
            data = response.json()

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
                        # Получаем индексы колонок
                        def get_value(col_name):
                            if col_name in md_columns:
                                idx = md_columns.index(col_name)
                                return row[idx] if idx < len(row) else None
                            return None

                        duration_days = self._parse_float(get_value("DURATION"))
                        duration_years = duration_days / 365.25 if duration_days else None

                        result.update({
                            "has_data": True,
                            "last_price": self._parse_float(get_value("MARKETPRICE")),
                            "last_ytm": self._parse_float(get_value("YIELD")),
                            "duration_days": duration_days,
                            "duration_years": duration_years,
                            "last_trade_date": get_value("LASTTRADEDATE"),
                        })
                        break

            return result

        except Exception as e:
            logger.error(f"Ошибка при получении рыночных данных для {isin}: {e}")
            return {"isin": isin, "has_data": False, "error": str(e)}

    def fetch_all_market_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить рыночные данные для ВСЕХ облигаций одним запросом (оптимизировано)

        Returns:
            Словарь {isin: {ytm, duration_days, price, last_trade_date, ...}}
        """
        url = f"{self.MOEX_BASE_URL}/engines/stock/markets/bonds/securities.json"
        params = {
            "iss.meta": "off",
            "securities.columns": "SECID",
            "marketdata.columns": "SECID,BOARDID,YIELD,DURATION,MARKETPRICE,LASTTRADEDATE",
        }

        try:
            response = self._make_request(url, params)
            data = response.json()

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

                duration_days = self._parse_float(row_dict.get("DURATION"))
                duration_years = duration_days / 365.25 if duration_days else None

                result[isin] = {
                    "isin": isin,
                    "has_data": True,
                    "last_ytm": self._parse_float(row_dict.get("YIELD")),
                    "last_price": self._parse_float(row_dict.get("MARKETPRICE")),
                    "duration_days": duration_days,
                    "duration_years": duration_years,
                    "last_trade_date": row_dict.get("LASTTRADEDATE"),
                }

            logger.info(f"Получены рыночные данные для {len(result)} облигаций (пакетный запрос)")
            return result

        except Exception as e:
            logger.error(f"Ошибка при пакетном получении рыночных данных: {e}")
            return {}

    def fetch_ofz_with_market_data(
        self,
        include_details: bool = False,
        delay: float = 0.1,
        use_batch: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Получить ОФЗ с рыночными данными

        Args:
            include_details: Загружать детальную информацию (медленнее)
            delay: Задержка между запросами (только если use_batch=False)
            use_batch: Использовать пакетный запрос (быстрее, рекомендуется)

        Returns:
            Список ОФЗ с рыночными данными
        """
        ofz_bonds = self.fetch_ofz_only()
        result = []

        if use_batch:
            # ОПТИМИЗИРОВАННЫЙ ПУТЬ: один запрос для всех рыночных данных
            all_market_data = self.fetch_all_market_data()

            for bond in ofz_bonds:
                isin = bond["isin"]
                market_data = all_market_data.get(isin, {"has_data": False})

                bond_data = {
                    **bond,
                    "last_price": market_data.get("last_price"),
                    "last_ytm": market_data.get("last_ytm"),
                    "duration_days": market_data.get("duration_days"),
                    "duration_years": market_data.get("duration_years"),
                    "last_trade_date": market_data.get("last_trade_date"),
                    "has_market_data": market_data.get("has_data", False),
                }

                # Детали загружаем только если нужно (медленно)
                if include_details:
                    details = self.fetch_bond_details(isin)
                    bond_data.update({
                        "issue_date": details.get("issue_date"),
                        "coupon_frequency": details.get("coupon_frequency"),
                        "day_count": details.get("day_count"),
                    })
                    time_module.sleep(delay)

                result.append(bond_data)

        else:
            # МЕДЛЕННЫЙ ПУТЬ: отдельный запрос для каждой облигации
            for i, bond in enumerate(ofz_bonds):
                isin = bond["isin"]

                market_data = self.fetch_market_data(isin)

                bond_data = {
                    **bond,
                    "last_price": market_data.get("last_price"),
                    "last_ytm": market_data.get("last_ytm"),
                    "duration_days": market_data.get("duration_days"),
                    "duration_years": market_data.get("duration_years"),
                    "last_trade_date": market_data.get("last_trade_date"),
                    "has_market_data": market_data.get("has_data", False),
                }

                if include_details:
                    details = self.fetch_bond_details(isin)
                    bond_data.update({
                        "issue_date": details.get("issue_date"),
                        "coupon_frequency": details.get("coupon_frequency"),
                        "day_count": details.get("day_count"),
                    })

                result.append(bond_data)

                if (i + 1) % 20 == 0:
                    logger.info(f"Обработано {i + 1}/{len(ofz_bonds)} облигаций")

                time_module.sleep(delay)

        logger.info(f"Получено {len(result)} ОФЗ с рыночными данными")
        return result

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

    @staticmethod
    def _parse_int(value: Any) -> Optional[int]:
        """Парсинг целого числа"""
        if value is None:
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def close(self):
        """Закрыть сессию"""
        self._session.close()


# ==========================================
# УДОБНЫЕ ФУНКЦИИ
# ==========================================

_fetcher = None


def get_fetcher() -> MOEXBondsFetcher:
    """Получить singleton fetcher"""
    global _fetcher
    if _fetcher is None:
        _fetcher = MOEXBondsFetcher()
    return _fetcher


def fetch_all_ofz() -> List[Dict[str, Any]]:
    """
    Получить список всех ОФЗ

    Returns:
        Список словарей с данными ОФЗ
    """
    fetcher = get_fetcher()
    return fetcher.fetch_ofz_only()


def fetch_ofz_with_market_data(include_details: bool = False) -> List[Dict[str, Any]]:
    """
    Получить ОФЗ с рыночными данными

    Args:
        include_details: Загружать детальную информацию

    Returns:
        Список ОФЗ с рыночными данными
    """
    fetcher = get_fetcher()
    return fetcher.fetch_ofz_with_market_data(include_details=include_details)


# ==========================================
# ФИЛЬТРАЦИЯ ОФЗ
# ==========================================

# Константы фильтрации
MIN_MATURITY_DAYS = 183  # 0.5 года
MAX_TRADE_DAYS_AGO = 10  # Торги за последние 10 дней


def filter_ofz_for_trading(
    bonds: List[Dict[str, Any]],
    min_maturity_days: int = MIN_MATURITY_DAYS,
    max_trade_days_ago: int = MAX_TRADE_DAYS_AGO,
    require_duration: bool = True
) -> List[Dict[str, Any]]:
    """
    Отфильтровать ОФЗ по критериям для торговли

    Критерии:
    - ОФЗ-ПД (26xxx, 25xxx, 24xxx) - постоянный купон
    - Срок до погашения > min_maturity_days (по умолчанию 183 дня = 0.5 года)
    - Торги за последние max_trade_days_ago дней (по умолчанию 10)
    - Наличие дюрации (если require_duration=True)

    Args:
        bonds: Список облигаций с данными (должны быть maturity_date, last_trade_date, duration_days)
        min_maturity_days: Минимальный срок до погашения в днях
        max_trade_days_ago: Максимальное количество дней с последней торговли
        require_duration: Требовать наличие дюрации

    Returns:
        Отфильтрованный список облигаций
    """
    today = date.today()
    cutoff_trade_date = today - timedelta(days=max_trade_days_ago)

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

        # 3. Проверка торгов за последние N дней
        last_trade_date = bond.get("last_trade_date")
        if last_trade_date:
            if isinstance(last_trade_date, str):
                try:
                    last_trade_date = datetime.strptime(last_trade_date, "%Y-%m-%d").date()
                except ValueError:
                    continue

            if last_trade_date < cutoff_trade_date:
                continue
        else:
            # Нет данных о торгах - пропускаем
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
    # Получаем ОФЗ с рыночными данными
    bonds = fetch_ofz_with_market_data(include_details=include_details)

    # Фильтруем
    return filter_ofz_for_trading(
        bonds,
        min_maturity_days=min_maturity_days,
        max_trade_days_ago=max_trade_days_ago
    )
