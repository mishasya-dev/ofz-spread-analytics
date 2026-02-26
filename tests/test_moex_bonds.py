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
from datetime import datetime

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.moex_bonds import MOEXBondsFetcher, fetch_all_ofz, fetch_ofz_with_market_data


class TestMOEXBondsFetcher(unittest.TestCase):
    """Тесты для MOEXBondsFetcher"""

    def setUp(self):
        """Создаём fetcher для каждого теста"""
        self.fetcher = MOEXBondsFetcher()

    def tearDown(self):
        """Закрываем fetcher после каждого теста"""
        self.fetcher.close()


class TestFetchAllBonds(TestMOEXBondsFetcher):
    """Тесты для fetch_all_bonds"""

    @patch('api.moex_bonds.MOEXBondsFetcher._make_request')
    def test_fetch_all_bonds_basic(self, mock_request):
        """Базовое получение списка облигаций"""
        # Мокаем ответ
        mock_response = Mock()
        mock_response.json.return_value = {
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
        mock_request.return_value = mock_response

        bonds = self.fetcher.fetch_all_bonds()

        # Должно быть 2 облигации (без квалифицированных и без USD)
        assert len(bonds) == 2
        assert bonds[0]["isin"] == "SU26221RMFS0"
        assert bonds[1]["isin"] == "SU26225RMFS1"

    @patch('api.moex_bonds.MOEXBondsFetcher._make_request')
    def test_fetch_all_bonds_pagination(self, mock_request):
        """Пагинация при получении списка"""
        # Первый вызов - 100 записей
        mock_response1 = Mock()
        mock_response1.json.return_value = {
            "securities": {
                "columns": ["SECID", "NAME", "SHORTNAME", "FACEVALUE", "FACEUNIT", "COUPONPERCENT", "MATDATE", "ISQUALIFIEDINVESTOR"],
                "data": [
                    [f"SU262{i:03d}RMFS0", f"ОФЗ {i}", f"ОФЗ{i}", 1000, "SUR", 7.0, "2030-01-01", 0]
                    for i in range(100)
                ]
            }
        }
        # Второй вызов - меньше 100 записей (конец)
        mock_response2 = Mock()
        mock_response2.json.return_value = {
            "securities": {
                "columns": ["SECID", "NAME", "SHORTNAME", "FACEVALUE", "FACEUNIT", "COUPONPERCENT", "MATDATE", "ISQUALIFIEDINVESTOR"],
                "data": [
                    ["SU26299RMFS0", "ОФЗ 999", "ОФЗ999", 1000, "SUR", 7.0, "2030-01-01", 0]
                ]
            }
        }

        mock_request.side_effect = [mock_response1, mock_response2]

        bonds = self.fetcher.fetch_all_bonds()

        # 100 + 1 = 101 облигация
        assert len(bonds) == 101
        assert mock_request.call_count == 2


class TestFetchOfzOnly(TestMOEXBondsFetcher):
    """Тесты для fetch_ofz_only"""

    @patch('api.moex_bonds.MOEXBondsFetcher.fetch_all_bonds')
    def test_fetch_ofz_only(self, mock_fetch_all):
        """Фильтрация только ОФЗ"""
        mock_fetch_all.return_value = [
            {"isin": "SU26221RMFS0", "name": "ОФЗ 26221"},
            {"isin": "SU26225RMFS1", "name": "ОФЗ 26225"},
            {"isin": "SU25000RMFS0", "name": "ОФЗ 25000"},
            {"isin": "RU000A0JX0J2", "name": "Корпоративный бонд"},
            {"isin": "XS1234567890", "name": "Евробонд"},
        ]

        ofz = self.fetcher.fetch_ofz_only()

        # Только SU26... и SU25...
        assert len(ofz) == 3
        isins = [b["isin"] for b in ofz]
        assert "SU26221RMFS0" in isins
        assert "SU26225RMFS1" in isins
        assert "SU25000RMFS0" in isins
        assert "RU000A0JX0J2" not in isins


class TestFetchBondDetails(TestMOEXBondsFetcher):
    """Тесты для fetch_bond_details"""

    @patch('api.moex_bonds.MOEXBondsFetcher._make_request')
    def test_fetch_bond_details(self, mock_request):
        """Получение детальной информации"""
        mock_response = Mock()
        mock_response.json.return_value = {
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
        mock_request.return_value = mock_response

        details = self.fetcher.fetch_bond_details("SU26221RMFS0")

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


class TestFetchMarketData(TestMOEXBondsFetcher):
    """Тесты для fetch_market_data"""

    @patch('api.moex_bonds.MOEXBondsFetcher._make_request')
    def test_fetch_market_data_success(self, mock_request):
        """Успешное получение рыночных данных"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "marketdata": {
                "columns": ["BOARDID", "YIELD", "DURATION", "MARKETPRICE", "LASTTRADEDATE"],
                "data": [
                    ["TQOB", 15.2, 2628, 95.5, "2026-02-27"],
                ]
            }
        }
        mock_request.return_value = mock_response

        data = self.fetcher.fetch_market_data("SU26221RMFS0")

        assert data["isin"] == "SU26221RMFS0"
        assert data["has_data"] is True
        assert data["last_ytm"] == 15.2
        assert data["duration_days"] == 2628
        assert data["duration_years"] == 2628 / 365.25
        assert data["last_price"] == 95.5
        assert data["last_trade_date"] == "2026-02-27"

    @patch('api.moex_bonds.MOEXBondsFetcher._make_request')
    def test_fetch_market_data_no_tqob(self, mock_request):
        """Нет данных на TQOB"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "marketdata": {
                "columns": ["BOARDID", "YIELD", "DURATION", "MARKETPRICE"],
                "data": [
                    ["TQBR", None, None, None],  # Не TQOB
                ]
            }
        }
        mock_request.return_value = mock_response

        data = self.fetcher.fetch_market_data("SU26221RMFS0")

        assert data["has_data"] is False


class TestConvenienceFunctions(unittest.TestCase):
    """Тесты для удобных функций"""

    @patch('api.moex_bonds.get_fetcher')
    def test_fetch_all_ofz(self, mock_get_fetcher):
        """Функция fetch_all_ofz"""
        mock_fetcher = Mock()
        mock_fetcher.fetch_ofz_only.return_value = [{"isin": "SU26221RMFS0"}]
        mock_get_fetcher.return_value = mock_fetcher

        result = fetch_all_ofz()

        assert len(result) == 1
        mock_fetcher.fetch_ofz_only.assert_called_once()

    @patch('api.moex_bonds.get_fetcher')
    def test_fetch_ofz_with_market_data(self, mock_get_fetcher):
        """Функция fetch_ofz_with_market_data"""
        mock_fetcher = Mock()
        mock_fetcher.fetch_ofz_with_market_data.return_value = [{"isin": "SU26221RMFS0", "last_ytm": 15.2}]
        mock_get_fetcher.return_value = mock_fetcher

        result = fetch_ofz_with_market_data(include_details=True)

        assert len(result) == 1
        mock_fetcher.fetch_ofz_with_market_data.assert_called_once_with(include_details=True)


class TestParseFunctions(TestMOEXBondsFetcher):
    """Тесты для функций парсинга"""

    def test_parse_float(self):
        """Тест _parse_float"""
        assert self.fetcher._parse_float(7.7) == 7.7
        assert self.fetcher._parse_float("7.7") == 7.7
        assert self.fetcher._parse_float(None) is None
        assert self.fetcher._parse_float("invalid") is None

    def test_parse_int(self):
        """Тест _parse_int"""
        assert self.fetcher._parse_int(2) == 2
        assert self.fetcher._parse_int("2") == 2
        assert self.fetcher._parse_int("2.5") == 2  # float to int
        assert self.fetcher._parse_int(None) is None
        assert self.fetcher._parse_int("invalid") is None


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

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
