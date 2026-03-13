"""
Тесты для api/moex_bonds.py (версия 0.2.0)

Запуск:
    python3 tests/test_moex_bonds.py
"""
import sys
import os
import json
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timedelta

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.moex_bonds import (
    fetch_all_bonds,
    fetch_ofz_only,
    fetch_bond_details,
    fetch_market_data,
    fetch_all_ofz,
    fetch_ofz_with_market_data,
    filter_ofz_for_trading,
    fetch_and_filter_ofz,
    MIN_MATURITY_DAYS,
    MAX_TRADE_DAYS_AGO
)
from api.moex_client import MOEXClient


class TestFetchAllBonds(unittest.TestCase):
    """Тесты для fetch_all_bonds"""

    @patch('api.moex_bonds.MOEXClient')
    def test_fetch_all_bonds_basic(self, MockClient):
        """Базовое получение списка облигаций"""
        # Настраиваем мок для context manager
        mock_instance = MockClient.return_value
        mock_instance.__enter__ = Mock(return_value=mock_instance)
        mock_instance.__exit__ = Mock(return_value=False)
        mock_instance.get_json.return_value = {
            "securities": {
                "columns": ["SECID", "NAME", "SHORTNAME", "FACEVALUE", "FACEUNIT", "COUPONPERCENT", "MATDATE", "ISQUALIFIEDINVESTOR"],
                "data": [
                    ["SU26221RMFS0", "ОФЗ 26221", "ОФЗ26221", 1000, "SUR", 7.7, "2033-03-23", 0],
                    ["SU26225RMFS1", "ОФЗ 26225", "ОФЗ26225", 1000, "SUR", 7.25, "2034-05-10", 0],
                    ["RU000A0JX0J2", "Бонд РФ", "БОНД", 1000, "SUR", 8.0, "2030-01-01", 1],  # Для квалифицированных
                    ["XS1234567890", "Eurobond", "EURO", 1000, "USD", 5.0, "2030-01-01", 0],  # Не рубль
                ]
            }
        }

        bonds = fetch_all_bonds()

        # Должно быть 2 облигации (без квалифицированных и без USD)
        assert len(bonds) == 2
        assert bonds[0]["isin"] == "SU26221RMFS0"
        assert bonds[1]["isin"] == "SU26225RMFS1"

    @patch('api.moex_bonds.MOEXClient')
    def test_fetch_all_bonds_pagination(self, MockClient):
        """Пагинация при получении списка"""
        mock_instance = MockClient.return_value
        mock_instance.__enter__ = Mock(return_value=mock_instance)
        mock_instance.__exit__ = Mock(return_value=False)
        # Первый вызов - 100 записей, второй - 1 запись
        mock_instance.get_json.side_effect = [
            {
                "securities": {
                    "columns": ["SECID", "NAME", "SHORTNAME", "FACEVALUE", "FACEUNIT", "COUPONPERCENT", "MATDATE", "ISQUALIFIEDINVESTOR"],
                    "data": [
                        [f"SU262{i:03d}RMFS0", f"ОФЗ {i}", f"ОФЗ{i}", 1000, "SUR", 7.0, "2030-01-01", 0]
                        for i in range(100)
                    ]
                }
            },
            {
                "securities": {
                    "columns": ["SECID", "NAME", "SHORTNAME", "FACEVALUE", "FACEUNIT", "COUPONPERCENT", "MATDATE", "ISQUALIFIEDINVESTOR"],
                    "data": [
                        ["SU26299RMFS0", "ОФЗ 999", "ОФЗ999", 1000, "SUR", 7.0, "2030-01-01", 0]
                    ]
                }
            },
        ]

        bonds = fetch_all_bonds()

        # 100 + 1 = 101 облигация
        assert len(bonds) == 101
        assert mock_instance.get_json.call_count == 2


class TestFetchOfzOnly(unittest.TestCase):
    """Тесты для fetch_ofz_only"""

    @patch('api.moex_bonds.MOEXClient')
    def test_fetch_ofz_only_returns_ofz_only(self, MockClient):
        """Фильтрация только ОФЗ"""
        mock_instance = MockClient.return_value
        mock_instance.__enter__ = Mock(return_value=mock_instance)
        mock_instance.__exit__ = Mock(return_value=False)
        mock_instance.get_json.return_value = {
            "securities": {
                "columns": ["SECID", "NAME", "SHORTNAME", "FACEVALUE", "COUPONPERCENT", "MATDATE"],
                "data": [
                    ["SU26221RMFS0", "ОФЗ 26221", "ОФЗ26221", 1000, 7.7, "2033-03-23"],
                    ["SU26225RMFS1", "ОФЗ 26225", "ОФЗ26225", 1000, 7.25, "2034-05-10"],
                ]
            },
            "marketdata": {
                "data": [
                    ["SU26221RMFS0", "TQOB"],
                    ["SU26225RMFS1", "TQOB"],
                ]
            }
        }

        ofz = fetch_ofz_only()

        # Проверяем что все возвращённые ISIN начинаются с SU26, SU25 или SU24
        for bond in ofz:
            isin = bond.get("isin", "")
            assert isin.startswith("SU26") or isin.startswith("SU25") or isin.startswith("SU24"), \
                f"ISIN {isin} не является ОФЗ-ПД"


class TestFetchBondDetails(unittest.TestCase):
    """Тесты для fetch_bond_details"""

    @patch('api.moex_bonds.MOEXClient')
    def test_fetch_bond_details(self, MockClient):
        """Получение детальной информации"""
        mock_instance = MockClient.return_value
        mock_instance.__enter__ = Mock(return_value=mock_instance)
        mock_instance.__exit__ = Mock(return_value=False)
        mock_instance.get_json.return_value = {
            "description": {
                "data": [
                    ["NAME", "string", "ОФЗ 26221"],
                    ["SHORTNAME", "string", "ОФЗ26221"],
                    ["COUPONPERCENT", "double", 7.7],
                    ["MATDATE", "date", "2033-03-23"],
                    ["ISSUEDATE", "date", "2017-02-15"],
                    ["FACEVALUE", "double", 1000],
                    ["COUPONFREQUENCY", "int", 2],
                    ["DAYCOUNTCONVENTION", "string", "ACT/ACT"],
                ]
            },
            "boards": {
                "columns": ["boardid", "DURATION", "MARKETPRICE", "YIELD", "LASTTRADEDATE"],
                "data": [
                    ["TQOB", 2628, 95.5, 15.2, "2026-02-27"],
                ]
            }
        }

        details = fetch_bond_details("SU26221RMFS0")

        assert details["isin"] == "SU26221RMFS0"
        assert details["name"] == "ОФЗ 26221"
        assert details["short_name"] == "ОФЗ26221"
        assert details["coupon_rate"] == 7.7
        assert details["maturity_date"] == "2033-03-23"
        assert details["issue_date"] == "2017-02-15"
        assert details["face_value"] == 1000
        assert details["coupon_frequency"] == 2
        assert details["day_count"] == "ACT/ACT"
        assert details["duration_days"] == 2628
        assert details["last_price"] == 95.5
        assert details["last_ytm"] == 15.2


class TestFetchMarketData(unittest.TestCase):
    """Тесты для fetch_market_data"""

    @patch('api.moex_bonds.MOEXClient')
    def test_fetch_market_data_success(self, MockClient):
        """Успешное получение рыночных данных"""
        mock_instance = MockClient.return_value
        mock_instance.__enter__ = Mock(return_value=mock_instance)
        mock_instance.__exit__ = Mock(return_value=False)
        mock_instance.get_json.return_value = {
            "marketdata": {
                "columns": ["SECID", "BOARDID", "YIELD", "DURATION", "MARKETPRICE", "LASTTRADEDATE"],
                "data": [
                    ["SU26221RMFS0", "TQOB", 15.2, 2628, 95.5, "2026-02-27"],
                ]
            }
        }

        data = fetch_market_data("SU26221RMFS0")

        assert data["isin"] == "SU26221RMFS0"
        assert data["has_data"] is True
        assert data["last_ytm"] == 15.2
        assert data["duration_days"] == 2628
        assert data["duration_years"] == 2628 / 365.25
        assert data["last_price"] == 95.5
        assert data["last_trade_date"] == "2026-02-27"

    @patch('api.moex_bonds.MOEXClient')
    def test_fetch_market_data_no_tqob(self, MockClient):
        """Нет данных на TQOB"""
        mock_instance = MockClient.return_value
        mock_instance.__enter__ = Mock(return_value=mock_instance)
        mock_instance.__exit__ = Mock(return_value=False)
        mock_instance.get_json.return_value = {
            "marketdata": {
                "columns": ["SECID", "BOARDID", "YIELD", "DURATION", "MARKETPRICE"],
                "data": [
                    ["SU26221RMFS0", "TQBR", None, None, None],  # Не TQOB
                ]
            }
        }

        data = fetch_market_data("SU26221RMFS0")

        assert data["has_data"] is False


class TestConvenienceFunctions(unittest.TestCase):
    """Тесты для удобных функций"""

    @patch('api.moex_bonds.fetch_ofz_only')
    def test_fetch_all_ofz(self, mock_fetch):
        """Функция fetch_all_ofz"""
        mock_fetch.return_value = [{"isin": "SU26221RMFS0"}]

        result = fetch_all_ofz()

        assert len(result) == 1

    @patch('api.moex_bonds.fetch_ofz_only')
    @patch('api.moex_bonds.fetch_all_market_data')
    def test_fetch_ofz_with_market_data(self, mock_market, mock_fetch):
        """Функция fetch_ofz_with_market_data"""
        mock_fetch.return_value = [{"isin": "SU26221RMFS0"}]
        mock_market.return_value = {"SU26221RMFS0": {"has_data": True, "last_ytm": 15.2}}

        result = fetch_ofz_with_market_data()

        assert len(result) == 1


class TestFilterOfzForTrading(unittest.TestCase):
    """Тесты для filter_ofz_for_trading"""

    def setUp(self):
        """Подготовка тестовых данных"""
        self.today = date.today()

        # Создаём тестовые облигации
        self.test_bonds = [
            # Подходит по всем критериям
            {
                "isin": "SU26221RMFS0",
                "name": "ОФЗ 26221",
                "maturity_date": (self.today + timedelta(days=365)).strftime("%Y-%m-%d"),
                "last_trade_date": self.today.strftime("%Y-%m-%d"),
                "duration_days": 2000,
                "duration_years": 5.5,
                "has_trades": True,
                "num_trades": 100,
            },
            # Слишком короткий срок до погашения (< 0.5 года)
            {
                "isin": "SU26222RMFS0",
                "name": "ОФЗ 26222",
                "maturity_date": (self.today + timedelta(days=100)).strftime("%Y-%m-%d"),
                "last_trade_date": self.today.strftime("%Y-%m-%d"),
                "duration_days": 100,
                "duration_years": 0.3,
                "has_trades": True,
                "num_trades": 50,
            },
            # Нет торгов (has_trades=False)
            {
                "isin": "SU26223RMFS0",
                "name": "ОФЗ 26223",
                "maturity_date": (self.today + timedelta(days=365)).strftime("%Y-%m-%d"),
                "last_trade_date": (self.today - timedelta(days=15)).strftime("%Y-%m-%d"),
                "duration_days": 2000,
                "duration_years": 5.5,
                "has_trades": False,
                "num_trades": 0,
            },
            # Нет дюрации
            {
                "isin": "SU26224RMFS0",
                "name": "ОФЗ 26224",
                "maturity_date": (self.today + timedelta(days=365)).strftime("%Y-%m-%d"),
                "last_trade_date": self.today.strftime("%Y-%m-%d"),
                "duration_days": None,
                "duration_years": None,
                "has_trades": True,
                "num_trades": 30,
            },
            # Не ОФЗ-ПД (другой ISIN)
            {
                "isin": "RU000A0JX0J2",
                "name": "Корпоративный бонд",
                "maturity_date": (self.today + timedelta(days=365)).strftime("%Y-%m-%d"),
                "last_trade_date": self.today.strftime("%Y-%m-%d"),
                "duration_days": 2000,
                "duration_years": 5.5,
                "has_trades": True,
                "num_trades": 10,
            },
            # Погашена (отрицательный срок)
            {
                "isin": "SU26225RMFS1",
                "name": "ОФЗ 26225",
                "maturity_date": (self.today - timedelta(days=10)).strftime("%Y-%m-%d"),
                "last_trade_date": (self.today - timedelta(days=15)).strftime("%Y-%m-%d"),
                "duration_days": 0,
                "duration_years": 0,
                "has_trades": False,
                "num_trades": 0,
            },
        ]

    def test_filter_basic(self):
        """Базовая фильтрация"""
        filtered = filter_ofz_for_trading(self.test_bonds)

        # Только одна облигация должна пройти
        assert len(filtered) == 1
        assert filtered[0]["isin"] == "SU26221RMFS0"

    def test_filter_maturity_threshold(self):
        """Фильтрация по сроку до погашения"""
        # Устанавливаем строгий порог
        filtered = filter_ofz_for_trading(
            self.test_bonds,
            min_maturity_days=200  # ~0.55 года
        )

        # Облигация с 100 днями до погашения не пройдёт
        isins = [b["isin"] for b in filtered]
        assert "SU26222RMFS0" not in isins

    def test_filter_trade_date(self):
        """Фильтрация по дате торгов"""
        filtered = filter_ofz_for_trading(
            self.test_bonds,
            max_trade_days_ago=5
        )

        # Облигация с торгами 15 дней назад не пройдёт
        isins = [b["isin"] for b in filtered]
        assert "SU26223RMFS0" not in isins

    def test_filter_without_duration_check(self):
        """Фильтрация без проверки дюрации"""
        filtered = filter_ofz_for_trading(
            self.test_bonds,
            require_duration=False
        )

        # Должно пройти больше облигаций
        isins = [b["isin"] for b in filtered]
        assert "SU26221RMFS0" in isins
        # SU26224RMFS0 тоже пройдёт, потому что require_duration=False
        assert "SU26224RMFS0" in isins

    def test_filter_sorting_by_duration(self):
        """Сортировка по дюрации"""
        # Создаём облигации с разной дюрацией
        bonds = [
            {
                "isin": "SU26221RMFS0",
                "name": "ОФЗ 26221",
                "maturity_date": (self.today + timedelta(days=3650)).strftime("%Y-%m-%d"),
                "last_trade_date": self.today.strftime("%Y-%m-%d"),
                "duration_days": 3000,
                "duration_years": 8.2,
                "has_trades": True,
                "num_trades": 100,
            },
            {
                "isin": "SU26225RMFS1",
                "name": "ОФЗ 26225",
                "maturity_date": (self.today + timedelta(days=730)).strftime("%Y-%m-%d"),
                "last_trade_date": self.today.strftime("%Y-%m-%d"),
                "duration_days": 1000,
                "duration_years": 2.7,
                "has_trades": True,
                "num_trades": 50,
            },
            {
                "isin": "SU26230RMFS1",
                "name": "ОФЗ 26230",
                "maturity_date": (self.today + timedelta(days=1825)).strftime("%Y-%m-%d"),
                "last_trade_date": self.today.strftime("%Y-%m-%d"),
                "duration_days": 2000,
                "duration_years": 5.5,
                "has_trades": True,
                "num_trades": 75,
            },
        ]

        filtered = filter_ofz_for_trading(bonds)

        # Должны быть отсортированы по дюрации
        assert len(filtered) == 3
        assert filtered[0]["isin"] == "SU26225RMFS1"  # 2.7 года
        assert filtered[1]["isin"] == "SU26230RMFS1"  # 5.5 лет
        assert filtered[2]["isin"] == "SU26221RMFS0"  # 8.2 года

    def test_filter_adds_fields(self):
        """Добавляются вычисленные поля"""
        filtered = filter_ofz_for_trading(self.test_bonds)

        if filtered:
            assert "days_to_maturity" in filtered[0]
            assert "is_filtered" in filtered[0]
            assert filtered[0]["is_filtered"] is True

    def test_filter_ofz_24_series(self):
        """ОФЗ 24 серии проходят (ОФЗ-ПД)"""
        bonds = [
            {
                "isin": "SU24000RMFS0",
                "name": "ОФЗ 24000",
                "maturity_date": (self.today + timedelta(days=365)).strftime("%Y-%m-%d"),
                "last_trade_date": self.today.strftime("%Y-%m-%d"),
                "duration_days": 2000,
                "duration_years": 5.5,
                "has_trades": True,
                "num_trades": 50,
            }
        ]

        filtered = filter_ofz_for_trading(bonds)
        assert len(filtered) == 1

    def test_filter_empty_list(self):
        """Пустой список на входе"""
        filtered = filter_ofz_for_trading([])
        assert len(filtered) == 0

    def test_filter_no_maturity_date(self):
        """Нет даты погашения"""
        bonds = [
            {
                "isin": "SU26221RMFS0",
                "name": "ОФЗ 26221",
                "maturity_date": None,
                "last_trade_date": self.today.strftime("%Y-%m-%d"),
                "duration_days": 2000,
            }
        ]

        filtered = filter_ofz_for_trading(bonds)
        assert len(filtered) == 0

    def test_filter_no_trade_date(self):
        """Нет даты торгов"""
        bonds = [
            {
                "isin": "SU26221RMFS0",
                "name": "ОФЗ 26221",
                "maturity_date": (self.today + timedelta(days=365)).strftime("%Y-%m-%d"),
                "last_trade_date": None,
                "duration_days": 2000,
            }
        ]

        filtered = filter_ofz_for_trading(bonds)
        assert len(filtered) == 0


class TestFilterRequireTrades(unittest.TestCase):
    """Тесты для параметра require_trades - работа в выходные и торговые дни"""

    def setUp(self):
        """Подготовка тестовых данных"""
        self.today = date.today()
        
        # Облигации БЕЗ торгов (выходной/праздник)
        self.bonds_no_trades = [
            {
                "isin": "SU26221RMFS0",
                "name": "ОФЗ 26221",
                "maturity_date": (self.today + timedelta(days=365)).strftime("%Y-%m-%d"),
                "duration_days": 2000,
                "duration_years": 5.5,
                "has_trades": False,
                "num_trades": 0,
            },
            {
                "isin": "SU26225RMFS1",
                "name": "ОФЗ 26225",
                "maturity_date": (self.today + timedelta(days=730)).strftime("%Y-%m-%d"),
                "duration_days": 1500,
                "duration_years": 4.1,
                "has_trades": False,
                "num_trades": None,
            },
        ]

        # Облигации С торговлей (будний день)
        self.bonds_with_trades = [
            {
                "isin": "SU26230RMFS1",
                "name": "ОФЗ 26230",
                "maturity_date": (self.today + timedelta(days=365)).strftime("%Y-%m-%d"),
                "duration_days": 2000,
                "duration_years": 5.5,
                "has_trades": True,
                "num_trades": 150,
            },
        ]

        # Смешанный список
        self.bonds_mixed = self.bonds_no_trades + self.bonds_with_trades

    def test_require_trades_true_on_trading_day(self):
        """Торговый день: require_trades=True показывает только с торгами"""
        filtered = filter_ofz_for_trading(
            self.bonds_with_trades,
            require_trades=True
        )
        
        assert len(filtered) == 1
        assert filtered[0]["isin"] == "SU26230RMFS1"

    def test_require_trades_true_on_weekend(self):
        """Выходной: require_trades=True НЕ показывает облигации без торгов"""
        filtered = filter_ofz_for_trading(
            self.bonds_no_trades,
            require_trades=True
        )
        
        # Все отфильтрованы - нет торгов!
        assert len(filtered) == 0

    def test_require_trades_false_on_weekend(self):
        """Выходной: require_trades=False показывает облигации без торгов"""
        filtered = filter_ofz_for_trading(
            self.bonds_no_trades,
            require_trades=False
        )
        
        # Все проходят!
        assert len(filtered) == 2
        isins = [b["isin"] for b in filtered]
        assert "SU26221RMFS0" in isins
        assert "SU26225RMFS1" in isins

    def test_require_trades_false_on_trading_day(self):
        """Торговый день: require_trades=False показывает все облигации"""
        filtered = filter_ofz_for_trading(
            self.bonds_with_trades,
            require_trades=False
        )
        
        assert len(filtered) == 1

    def test_require_trades_false_mixed_bonds(self):
        """Смешанный список: require_trades=False показывает все"""
        filtered = filter_ofz_for_trading(
            self.bonds_mixed,
            require_trades=False
        )
        
        # Все 3 облигации проходят
        assert len(filtered) == 3

    def test_require_trades_true_mixed_bonds(self):
        """Смешанный список: require_trades=True показывает только с торгами"""
        filtered = filter_ofz_for_trading(
            self.bonds_mixed,
            require_trades=True
        )
        
        # Только 1 с торгами
        assert len(filtered) == 1
        assert filtered[0]["isin"] == "SU26230RMFS1"

    def test_require_trades_with_has_trades_flag(self):
        """Проверка по флагу has_trades=True"""
        bonds = [
            {
                "isin": "SU26221RMFS0",
                "name": "ОФЗ 26221",
                "maturity_date": (self.today + timedelta(days=365)).strftime("%Y-%m-%d"),
                "duration_days": 2000,
                "has_trades": True,  # Флаг установлен
                "num_trades": 0,     # Но num_trades=0 (неожиданно)
            }
        ]
        
        filtered = filter_ofz_for_trading(bonds, require_trades=True)
        # Должно пройти по флагу has_trades
        assert len(filtered) == 1

    def test_require_trades_with_num_trades_only(self):
        """Проверка только по num_trades (has_trades отсутствует)"""
        bonds = [
            {
                "isin": "SU26221RMFS0",
                "name": "ОФЗ 26221",
                "maturity_date": (self.today + timedelta(days=365)).strftime("%Y-%m-%d"),
                "duration_days": 2000,
                "num_trades": 50,  # Есть торги
                # has_trades отсутствует
            }
        ]
        
        filtered = filter_ofz_for_trading(bonds, require_trades=True)
        # Должно пройти по num_trades
        assert len(filtered) == 1

    def test_require_trades_false_with_require_duration_false(self):
        """Комбинация: require_trades=False + require_duration=False"""
        bonds = [
            {
                "isin": "SU26221RMFS0",
                "name": "ОФЗ 26221",
                "maturity_date": (self.today + timedelta(days=365)).strftime("%Y-%m-%d"),
                # Нет дюрации
                "duration_days": None,
                "num_trades": 0,
            }
        ]
        
        filtered = filter_ofz_for_trading(
            bonds,
            require_trades=False,
            require_duration=False
        )
        
        # Проходит: нет требования торгов, нет требования дюрации
        assert len(filtered) == 1

    def test_bond_manager_scenario_weekend(self):
        """Сценарий bond_manager в выходной:require_trades=False"""
        # Симулируем выходной - MOEX вернул облигации без торгов
        weekend_bonds = [
            {
                "isin": "SU26221RMFS0",
                "name": "ОФЗ 26221",
                "maturity_date": (self.today + timedelta(days=365)).strftime("%Y-%m-%d"),
                "duration_days": 2000,
                "duration_years": 5.5,
                "last_ytm": 15.2,
                "num_trades": 0,
            },
            {
                "isin": "SU26225RMFS1",
                "name": "ОФЗ 26225", 
                "maturity_date": (self.today + timedelta(days=730)).strftime("%Y-%m-%d"),
                "duration_days": 1500,
                "duration_years": 4.1,
                "last_ytm": 14.8,
                "num_trades": 0,
            },
        ]
        
        # bond_manager вызывает с require_trades=False
        filtered = filter_ofz_for_trading(weekend_bonds, require_trades=False)
        
        # Облигации показываются пользователю
        assert len(filtered) == 2

    def test_bond_manager_scenario_trading_day(self):
        """Сценарий bond_manager в торговый день"""
        # Симулируем торговый день - часть облигаций с торгами
        trading_day_bonds = [
            {
                "isin": "SU26221RMFS0",
                "name": "ОФЗ 26221",
                "maturity_date": (self.today + timedelta(days=365)).strftime("%Y-%m-%d"),
                "duration_days": 2000,
                "duration_years": 5.5,
                "last_ytm": 15.2,
                "num_trades": 150,
            },
            {
                "isin": "SU26225RMFS1",
                "name": "ОФЗ 26225",
                "maturity_date": (self.today + timedelta(days=730)).strftime("%Y-%m-%d"),
                "duration_days": 1500,
                "duration_years": 4.1,
                "last_ytm": 14.8,
                "num_trades": 80,
            },
        ]
        
        # bond_manager вызывает с require_trades=False (показываем все)
        filtered = filter_ofz_for_trading(trading_day_bonds, require_trades=False)
        
        assert len(filtered) == 2


class TestFetchAndFilterOfz(unittest.TestCase):
    """Тесты для fetch_and_filter_ofz"""

    @patch('api.moex_bonds.fetch_ofz_with_market_data')
    def test_fetch_and_filter(self, mock_fetch):
        """Комбинированная функция"""
        mock_fetch.return_value = [
            {
                "isin": "SU26221RMFS0",
                "name": "ОФЗ 26221",
                "maturity_date": (date.today() + timedelta(days=365)).strftime("%Y-%m-%d"),
                "last_trade_date": date.today().strftime("%Y-%m-%d"),
                "duration_days": 2000,
                "duration_years": 5.5,
                "has_trades": True,
                "num_trades": 100,
            }
        ]

        result = fetch_and_filter_ofz()

        assert len(result) == 1
        mock_fetch.assert_called_once()


class TestConstants(unittest.TestCase):
    """Тесты для констант"""

    def test_min_maturity_days(self):
        """Проверка константы MIN_MATURITY_DAYS"""
        # 0.5 года ≈ 183 дня
        assert MIN_MATURITY_DAYS == 183

    def test_max_trade_days_ago(self):
        """Проверка константы MAX_TRADE_DAYS_AGO"""
        assert MAX_TRADE_DAYS_AGO == 10


def run_tests():
    """Запуск всех тестов"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestFetchAllBonds))
    suite.addTests(loader.loadTestsFromTestCase(TestFetchOfzOnly))
    suite.addTests(loader.loadTestsFromTestCase(TestFetchBondDetails))
    suite.addTests(loader.loadTestsFromTestCase(TestFetchMarketData))
    suite.addTests(loader.loadTestsFromTestCase(TestConvenienceFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestFilterOfzForTrading))
    suite.addTests(loader.loadTestsFromTestCase(TestFilterRequireTrades))
    suite.addTests(loader.loadTestsFromTestCase(TestFetchAndFilterOfz))
    suite.addTests(loader.loadTestsFromTestCase(TestConstants))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
