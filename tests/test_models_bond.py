"""
Тесты для модели Bond (models/bond.py)

Проверяет:
- Bond dataclass: создание, конвертация
- Bond.from_dict() — создание из словаря
- Bond.from_db_row() — создание из строки БД
- Bond.to_dict() — конвертация в словарь
- Bond.get_years_to_maturity() — расчёт лет до погашения
- Bond.format_label() — форматирование метки
- BondPair dataclass

Запуск:
    python3 tests/test_models_bond.py
"""
import sys
import os
import unittest
from datetime import datetime, timedelta
from dataclasses import fields

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBondDataclass(unittest.TestCase):
    """Тесты для dataclass Bond"""

    def setUp(self):
        """Импортируем Bond"""
        from models.bond import Bond
        self.Bond = Bond

    def test_bond_required_isin(self):
        """ISIN — обязательное поле"""
        bond = self.Bond(isin='SU26221RMFS0')
        
        self.assertEqual(bond.isin, 'SU26221RMFS0')

    def test_bond_defaults(self):
        """Значения по умолчанию"""
        bond = self.Bond(isin='TEST')
        
        self.assertEqual(bond.name, '')
        self.assertEqual(bond.short_name, '')
        self.assertIsNone(bond.coupon_rate)
        self.assertEqual(bond.maturity_date, '')
        self.assertEqual(bond.face_value, 1000.0)
        self.assertEqual(bond.coupon_frequency, 2)
        self.assertEqual(bond.day_count_convention, 'ACT/ACT')
        self.assertFalse(bond.is_favorite)
        self.assertIsNone(bond.last_price)
        self.assertIsNone(bond.last_ytm)
        self.assertIsNone(bond.duration_years)

    def test_bond_all_fields(self):
        """Все поля при создании"""
        bond = self.Bond(
            isin='SU26221RMFS0',
            name='ОФЗ 26221',
            short_name='ОФЗ26221',
            coupon_rate=7.7,
            maturity_date='2033-03-23',
            issue_date='2017-02-15',
            face_value=1000,
            coupon_frequency=2,
            day_count_convention='ACT/ACT',
            is_favorite=True,
            last_price=95.5,
            last_ytm=14.72,
            duration_years=7.2
        )
        
        self.assertEqual(bond.isin, 'SU26221RMFS0')
        self.assertEqual(bond.name, 'ОФЗ 26221')
        self.assertEqual(bond.coupon_rate, 7.7)
        self.assertEqual(bond.maturity_date, '2033-03-23')
        self.assertTrue(bond.is_favorite)
        self.assertEqual(bond.last_price, 95.5)
        self.assertEqual(bond.last_ytm, 14.72)


class TestBondFromDict(unittest.TestCase):
    """Тесты для Bond.from_dict()"""

    def setUp(self):
        from models.bond import Bond
        self.Bond = Bond

    def test_from_dict_minimal(self):
        """Минимальный словарь — name = isin если нет name"""
        bond = self.Bond.from_dict({'isin': 'TEST'})
        
        self.assertEqual(bond.isin, 'TEST')
        # name = isin если нет name и short_name
        self.assertEqual(bond.name, 'TEST')

    def test_from_dict_full(self):
        """Полный словарь"""
        data = {
            'isin': 'SU26221RMFS0',
            'name': 'ОФЗ 26221',
            'short_name': 'ОФЗ26221',
            'coupon_rate': 7.7,
            'maturity_date': '2033-03-23',
            'issue_date': '2017-02-15',
            'face_value': 1000,
            'coupon_frequency': 2,
            'day_count_convention': 'ACT/ACT',
            'day_count': 'ACT/ACT',  # Альтернативное имя
            'is_favorite': 1,
            'last_price': 95.5,
            'last_ytm': 14.72,
            'duration_years': 7.2
        }
        
        bond = self.Bond.from_dict(data)
        
        self.assertEqual(bond.isin, 'SU26221RMFS0')
        self.assertEqual(bond.name, 'ОФЗ 26221')
        self.assertTrue(bond.is_favorite)

    def test_from_dict_name_fallback(self):
        """Fallback name = short_name = isin"""
        data = {
            'isin': 'SU26221RMFS0',
            'short_name': 'ОФЗ26221'
        }
        
        bond = self.Bond.from_dict(data)
        
        # name берётся из short_name если name пустой
        self.assertEqual(bond.name, 'ОФЗ26221')

    def test_from_dict_day_count_fallback(self):
        """day_count_convention с fallback на day_count"""
        data = {
            'isin': 'TEST',
            'day_count': 'ACT/360'  # Альтернативное имя из БД
        }
        
        bond = self.Bond.from_dict(data)
        
        self.assertEqual(bond.day_count_convention, 'ACT/360')

    def test_from_dict_is_favorite_conversion(self):
        """Конвертация is_favorite из int в bool"""
        bond1 = self.Bond.from_dict({'isin': 'TEST', 'is_favorite': 1})
        bond0 = self.Bond.from_dict({'isin': 'TEST', 'is_favorite': 0})
        bond_none = self.Bond.from_dict({'isin': 'TEST'})
        
        self.assertTrue(bond1.is_favorite)
        self.assertFalse(bond0.is_favorite)
        self.assertFalse(bond_none.is_favorite)


class TestBondFromDbRow(unittest.TestCase):
    """Тесты для Bond.from_db_row()"""

    def setUp(self):
        from models.bond import Bond
        self.Bond = Bond

    def test_from_db_row_dict(self):
        """Создание из словаря (имитация sqlite3.Row)"""
        row = {
            'isin': 'SU26221RMFS0',
            'name': 'ОФЗ 26221',
            'coupon_rate': 7.7,
            'maturity_date': '2033-03-23',
            'is_favorite': 1
        }
        
        bond = self.Bond.from_db_row(row)
        
        self.assertEqual(bond.isin, 'SU26221RMFS0')
        self.assertEqual(bond.name, 'ОФЗ 26221')
        self.assertTrue(bond.is_favorite)


class TestBondToDict(unittest.TestCase):
    """Тесты для Bond.to_dict()"""

    def setUp(self):
        from models.bond import Bond
        self.Bond = Bond

    def test_to_dict_full(self):
        """Конвертация в словарь"""
        bond = self.Bond(
            isin='SU26221RMFS0',
            name='ОФЗ 26221',
            coupon_rate=7.7,
            maturity_date='2033-03-23',
            is_favorite=True,
            last_ytm=14.72
        )
        
        result = bond.to_dict()
        
        self.assertEqual(result['isin'], 'SU26221RMFS0')
        self.assertEqual(result['name'], 'ОФЗ 26221')
        self.assertEqual(result['coupon_rate'], 7.7)
        self.assertEqual(result['is_favorite'], 1)  # bool → int

    def test_to_dict_has_all_fields(self):
        """Словарь содержит все поля"""
        bond = self.Bond(isin='TEST')
        result = bond.to_dict()
        
        expected_keys = {
            'isin', 'name', 'short_name', 'coupon_rate', 'maturity_date',
            'issue_date', 'face_value', 'coupon_frequency', 'day_count_convention',
            'is_favorite', 'last_price', 'last_ytm', 'duration_years',
            'duration_days', 'last_trade_date', 'last_updated'
        }
        
        self.assertEqual(set(result.keys()), expected_keys)


class TestBondToDbDict(unittest.TestCase):
    """Тесты для Bond.to_db_dict()"""

    def setUp(self):
        from models.bond import Bond
        self.Bond = Bond

    def test_to_db_dict_day_count_field(self):
        """Поле day_count (не day_count_convention)"""
        bond = self.Bond(
            isin='TEST',
            day_count_convention='ACT/ACT'
        )
        
        result = bond.to_db_dict()
        
        self.assertIn('day_count', result)
        self.assertEqual(result['day_count'], 'ACT/ACT')

    def test_to_db_dict_excludes_updated(self):
        """Нет last_updated (автозаполняется БД)"""
        bond = self.Bond(isin='TEST')
        result = bond.to_db_dict()
        
        self.assertNotIn('last_updated', result)


class TestBondMethods(unittest.TestCase):
    """Тесты методов Bond"""

    def setUp(self):
        from models.bond import Bond
        self.Bond = Bond

    def test_get_display_name_with_name(self):
        """display_name = name если есть"""
        bond = self.Bond(isin='TEST', name='ОФЗ 26221')
        
        self.assertEqual(bond.get_display_name(), 'ОФЗ 26221')

    def test_get_display_name_fallback_short_name(self):
        """display_name = short_name если name пустой"""
        bond = self.Bond(isin='TEST', short_name='ОФЗ26221')
        
        self.assertEqual(bond.get_display_name(), 'ОФЗ26221')

    def test_get_display_name_fallback_isin(self):
        """display_name = isin если всё пусто"""
        bond = self.Bond(isin='SU26221RMFS0')
        
        self.assertEqual(bond.get_display_name(), 'SU26221RMFS0')

    def test_get_years_to_maturity_valid(self):
        """Расчёт лет до погашения"""
        future = (datetime.now() + timedelta(days=365*5)).strftime('%Y-%m-%d')
        bond = self.Bond(isin='TEST', maturity_date=future)
        
        years = bond.get_years_to_maturity()
        
        self.assertAlmostEqual(years, 5.0, delta=0.2)

    def test_get_years_to_maturity_empty(self):
        """Пустая дата погашения"""
        bond = self.Bond(isin='TEST', maturity_date='')
        
        years = bond.get_years_to_maturity()
        
        self.assertEqual(years, 0)

    def test_get_years_to_maturity_invalid(self):
        """Некорректная дата"""
        bond = self.Bond(isin='TEST', maturity_date='invalid-date')
        
        years = bond.get_years_to_maturity()
        
        self.assertEqual(years, 0)


class TestBondFormatLabel(unittest.TestCase):
    """Тесты для Bond.format_label()"""

    def setUp(self):
        from models.bond import Bond
        self.Bond = Bond

    def test_format_label_full(self):
        """Полная метка"""
        future = (datetime.now() + timedelta(days=365*8)).strftime('%Y-%m-%d')
        bond = self.Bond(
            isin='SU26221RMFS0',
            name='ОФЗ 26221',
            maturity_date=future,
            last_ytm=14.72
        )
        
        label = bond.format_label(ytm=14.72, duration_years=7.2)
        
        self.assertIn('ОФЗ 26221', label)
        self.assertIn('YTM: 14.72%', label)
        self.assertIn('Дюр: 7.2г.', label)
        self.assertIn('г. до погашения', label)

    def test_format_label_without_ytm(self):
        """Метка без YTM"""
        future = (datetime.now() + timedelta(days=365*8)).strftime('%Y-%m-%d')
        bond = self.Bond(
            isin='TEST',
            name='ОФЗ 26221',
            maturity_date=future
        )
        
        label = bond.format_label()
        
        self.assertIn('ОФЗ 26221', label)
        self.assertNotIn('YTM:', label)

    def test_format_label_uses_last_ytm(self):
        """Использует last_ytm если ytm=None"""
        future = (datetime.now() + timedelta(days=365*8)).strftime('%Y-%m-%d')
        bond = self.Bond(
            isin='TEST',
            name='ОФЗ',
            maturity_date=future,
            last_ytm=15.0
        )
        
        label = bond.format_label()  # ytm=None, должен использовать last_ytm
        
        self.assertIn('YTM: 15.00%', label)


class TestBondPair(unittest.TestCase):
    """Тесты для BondPair"""

    def setUp(self):
        from models.bond import Bond, BondPair
        self.Bond = Bond
        self.BondPair = BondPair

    def test_bond_pair_creation(self):
        """Создание пары"""
        bond1 = self.Bond(isin='SU26221RMFS0', name='ОФЗ 26221')
        bond2 = self.Bond(isin='SU26225RMFS1', name='ОФЗ 26225')
        
        pair = self.BondPair(bond1, bond2)
        
        self.assertEqual(pair.bond1, bond1)
        self.assertEqual(pair.bond2, bond2)

    def test_get_spread_bp(self):
        """Расчёт спреда в базисных пунктах"""
        bond1 = self.Bond(isin='B1', last_ytm=15.0)
        bond2 = self.Bond(isin='B2', last_ytm=14.5)
        
        pair = self.BondPair(bond1, bond2)
        spread = pair.get_spread_bp()
        
        # (15.0 - 14.5) * 100 = 50 б.п.
        self.assertEqual(spread, 50.0)

    def test_get_spread_bp_none_ytm(self):
        """None если YTM нет"""
        bond1 = self.Bond(isin='B1', last_ytm=15.0)
        bond2 = self.Bond(isin='B2', last_ytm=None)
        
        pair = self.BondPair(bond1, bond2)
        spread = pair.get_spread_bp()
        
        self.assertIsNone(spread)

    def test_get_label(self):
        """Метка пары"""
        bond1 = self.Bond(isin='B1', name='ОФЗ 26221')
        bond2 = self.Bond(isin='B2', name='ОФЗ 26225')
        
        pair = self.BondPair(bond1, bond2)
        label = pair.get_label()
        
        self.assertEqual(label, 'ОФЗ 26221 / ОФЗ 26225')


def run_tests():
    """Запуск всех тестов"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestBondDataclass))
    suite.addTests(loader.loadTestsFromTestCase(TestBondFromDict))
    suite.addTests(loader.loadTestsFromTestCase(TestBondFromDbRow))
    suite.addTests(loader.loadTestsFromTestCase(TestBondToDict))
    suite.addTests(loader.loadTestsFromTestCase(TestBondToDbDict))
    suite.addTests(loader.loadTestsFromTestCase(TestBondMethods))
    suite.addTests(loader.loadTestsFromTestCase(TestBondFormatLabel))
    suite.addTests(loader.loadTestsFromTestCase(TestBondPair))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
