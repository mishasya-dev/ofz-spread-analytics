"""
Тесты для api/moex_bonds.py

Запуск:
    python3 tests/test_moex_bonds.py
"""
import sys
import os
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
    fetch_all_market_data,
    fetch_ofz_with_market_data,
    fetch_all_ofz,
    filter_ofz_for_trading,
    fetch_and_filter_ofz,
    MIN_MATURITY_DAYS,
    MAX_TRADE_DAYS_AGO,
    _parse_float,
    _parse_int,
)


class TestFetchAllBonds(unittest.TestCase):
    """Тесты для fetch_all_bonds"""

    @patch('api.moex_bonds.MOEXClient')
    def test_fetch_all_bonds_basic(self, MockClient):
        """Базовое получение списка облигаций"""
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.get_json.return_value = {
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
        MockClient.return_value = mock_client

        bonds = fetch_all_bonds()

        # Должно быть 2 облигации (без квалифицированных и без USD)
        assert len(bonds) == 2
        assert bonds[0]["isin"] == "SU26221RMFS0"
        assert bonds[1]["isin"] == "SU26225RMFS1"

    @patch('api.moex_bonds.MOEXClient')
    def test_fetch_all_bonds_pagination(self, MockClient):
        """Пагинация при получении списка"""
        # Первый вызов - 100 записей
        first_response = {
            "securities": {
                "columns": ["SECID", "NAME", "SHORTNAME", "FACEVALUE", "FACEUNIT", "COUPONPERCENT", "MATDATE", "ISQUALIFIEDINVESTOR"],
                "data": [
                    [f"SU262{i:03d}RMFS0", f"ОФЗ {i}", f"ОФЗ{i}", 1000, "SUR", 7.0, "2030-01-01", 0]
                    for i in range(100)
                ]
            }
        }
        # Второй вызов - меньше 100 записей (конец)
        second_response = {
            "securities": {
                "columns": ["SECID", "NAME", "SHORTNAME", "FACEVALUE", "FACEUNIT", "COUPONPERCENT", "MATDATE", "ISQUALIFIEDINVESTOR"],
                "data": [
                    ["SU26299RMFS0", "ОФЗ 999", "ОФЗ999", 1000, "SUR", 7.0, "2030-01-01", 0]
                ]
            }
        }

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.get_json.side_effect = [first_response, second_response]
        MockClient.return_value = mock_client

        bonds = fetch_all_bonds()

        # 100 + 1 = 101 облигация
        assert len(bonds) == 101


class TestFetchOfzOnly(unittest.TestCase):
    """Тесты для fetch_ofz_only"""

    @patch('api.moex_bonds.MOEXClient')
    def test_fetch_ofz_only_filters_ofz(self, MockClient):
        """Фильтрация только ОФЗ"""
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.get_json.return_value = {
            "marketdata": {
                "columns": ["SECID", "BOARDID"],
                "data": [
                    ["SU26221RMFS0", "TQOB"],
                    ["SU26225RMFS1", "TQOB"],
                    ["RU000A0JX0J2", "TQBR"],  # Не TQOB
                ]
            },
            "securities": {
                "columns": ["SECID", "NAME", "SHORTNAME", "FACEVALUE", "COUPONPERCENT", "MATDATE"],
                "data": [
                    ["SU26221RMFS0", "ОФЗ 26221", "ОФЗ26221", 1000, 7.7, "2033-03-23"],
                    ["SU26225RMFS1", "ОФЗ 26225", "ОФЗ26225", 1000, 7.25, "2034-05-10"],
                    ["RU000A0JX0J2", "Корпоратив", "КОРП", 1000, 8.0, "2030-01-01"],
                ]
            }
        }
        MockClient.return_value = mock_client

        ofz = fetch_ofz_only()

        # Только 2 ОФЗ (SU26xxx, на TQOB)
        assert len(ofz) == 2
        isins = [b["isin"] for b in ofz]
        assert "SU26221RMFS0" in isins
        assert "SU26225RMFS1" in isins
        assert "RU000A0JX0J2" not in isins


class TestFetchBondDetails(unittest.TestCase):
    """Тесты для fetch_bond_details"""

    @patch('api.moex_bonds.MOEXClient')
    def test_fetch_bond_details(self, MockClient):
        """Получение детальной информации"""
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.get_json.return_value = {
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
        MockClient.return_value = mock_client

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
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.get_json.return_value = {
            "marketdata": {
                "columns": ["BOARDID", "YIELD", "DURATION", "MARKETPRICE", "LASTTRADEDATE"],
                "data": [
                    ["TQOB", 15.2, 2628, 95.5, "2026-02-27"],
                ]
            }
        }
        MockClient.return_value = mock_client

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
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.get_json.return_value = {
            "marketdata": {
                "columns": ["BOARDID", "YIELD", "DURATION", "MARKETPRICE"],
                "data": [
                    ["TQBR", None, None, None],  # Не TQOB
                ]
            }
        }
        MockClient.return_value = mock_client

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
        mock_fetch.assert_called_once()


class TestParseFunctions(unittest.TestCase):
    """Тесты для функций парсинга"""

    def test_parse_float(self):
        """Тест _parse_float"""
        assert _parse_float(7.7) == 7.7
        assert _parse_float("7.7") == 7.7
        assert _parse_float(None) is None
        assert _parse_float("invalid") is None

    def test_parse_int(self):
        """Тест _parse_int"""
        assert _parse_int(2) == 2
        assert _parse_int("2") == 2
        assert _parse_int("2.5") == 2  # float to int
        assert _parse_int(None) is None
        assert _parse_int("invalid") is None


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
                "duration_days": 2000,
                "duration_years": 5.5,
                "has_trades": True,
                "num_trades": 10,
            },
        ]

    def test_filter_basic(self):
        """Базовая фильтрация"""
        filtered = filter_ofz_for_trading(self.test_bonds)

        # Только одна облигация должна пройти
        assert len(filtered) == 1
        assert filtered[0]["isin"] == "SU26221RMFS0"

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
        bonds = [
            {
                "isin": "SU26221RMFS0",
                "name": "ОФЗ 26221",
                "maturity_date": (self.today + timedelta(days=3650)).strftime("%Y-%m-%d"),
                "duration_days": 3000,
                "duration_years": 8.2,
                "has_trades": True,
                "num_trades": 100,
            },
            {
                "isin": "SU26225RMFS1",
                "name": "ОФЗ 26225",
                "maturity_date": (self.today + timedelta(days=730)).strftime("%Y-%m-%d"),
                "duration_days": 1000,
                "duration_years": 2.7,
                "has_trades": True,
                "num_trades": 50,
            },
            {
                "isin": "SU26230RMFS1",
                "name": "ОФЗ 26230",
                "maturity_date": (self.today + timedelta(days=1825)).strftime("%Y-%m-%d"),
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

    def test_filter_empty_list(self):
        """Пустой список на входе"""
        filtered = filter_ofz_for_trading([])
        assert len(filtered) == 0


class TestFilterRequireTrades(unittest.TestCase):
    """Тесты для параметра require_trades"""

    def setUp(self):
        """Подготовка тестовых данных"""
        self.today = date.today()

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
        ]

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

    def test_require_trades_true_on_weekend(self):
        """Выходной: require_trades=True НЕ показывает облигации без торгов"""
        filtered = filter_ofz_for_trading(
            self.bonds_no_trades,
            require_trades=True
        )
        
        assert len(filtered) == 0

    def test_require_trades_false_on_weekend(self):
        """Выходной: require_trades=False показывает облигации без торгов"""
        filtered = filter_ofz_for_trading(
            self.bonds_no_trades,
            require_trades=False
        )
        
        assert len(filtered) == 1


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
    suite.addTests(loader.loadTestsFromTestCase(TestParseFunctions))
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
