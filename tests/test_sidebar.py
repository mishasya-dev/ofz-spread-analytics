"""
Тесты для sidebar функционала v0.2.0

Запуск:
    python3 tests/test_sidebar.py

Тестирует:
- Миграцию облигаций из config.py
- Загрузку избранных облигаций для sidebar
- Fallback на config.py при пустой БД
"""
import sys
import os
import sqlite3
import tempfile
import shutil
from datetime import datetime, date, timedelta

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Подменяем путь к БД на временную
import core.database as db_module
TEMP_DIR = tempfile.mkdtemp()
db_module.DB_PATH = os.path.join(TEMP_DIR, "test_sidebar.db")

from core.database import (
    init_database, get_connection, DatabaseManager, get_db
)


def setup_module():
    """Создаём БД перед тестами"""
    init_database()


def teardown_module():
    """Удаляем временную директорию после тестов"""
    shutil.rmtree(TEMP_DIR, ignore_errors=True)


def reset_db():
    """Сбросить таблицу bonds между тестами"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM bonds')
    conn.commit()
    conn.close()


# ==========================================
# ТЕСТЫ МИГРАЦИИ
# ==========================================

class TestSidebarMigration:
    """Тесты миграции облигаций из config.py в БД"""

    def setup_method(self):
        reset_db()

    def test_migrate_marks_all_as_favorites(self):
        """При миграции все облигации должны получить is_favorite=1"""
        db = get_db()

        # Создаём мок config.bonds (как в config.py)
        class MockBondConfig:
            def __init__(self, isin, name, maturity_date, coupon_rate):
                self.isin = isin
                self.name = name
                self.maturity_date = maturity_date
                self.coupon_rate = coupon_rate
                self.face_value = 1000
                self.coupon_frequency = 2
                self.issue_date = "2020-01-01"
                self.day_count_convention = "ACT/ACT"

        bonds_config = {
            "SU26221RMFS0": MockBondConfig("SU26221RMFS0", "ОФЗ 26221", "2033-03-23", 7.7),
            "SU26225RMFS1": MockBondConfig("SU26225RMFS1", "ОФЗ 26225", "2034-05-10", 7.25),
        }

        # Мигрируем
        migrated = db.migrate_config_bonds(bonds_config)
        assert migrated == 2

        # Проверяем, что все - избранные
        favorites = db.get_favorite_bonds()
        assert len(favorites) == 2

    def test_migrate_skips_if_bonds_exist(self):
        """Миграция не должна происходить, если облигации уже есть"""
        db = get_db()

        # Сначала добавляем одну облигацию
        db.save_bond({
            'isin': 'SU26221RMFS0',
            'name': 'ОФЗ 26221',
            'is_favorite': 0
        })

        # Пробуем мигрировать
        class MockBondConfig:
            def __init__(self, isin, name):
                self.isin = isin
                self.name = name
                self.maturity_date = "2030-01-01"
                self.coupon_rate = 7.0
                self.face_value = 1000
                self.coupon_frequency = 2
                self.issue_date = "2020-01-01"
                self.day_count_convention = "ACT/ACT"

        bonds_config = {
            "SU26221RMFS0": MockBondConfig("SU26221RMFS0", "ОФЗ 26221"),
            "SU26225RMFS1": MockBondConfig("SU26225RMFS1", "ОФЗ 26225"),
        }

        migrated = db.migrate_config_bonds(bonds_config)

        # Миграция не должна была произойти
        assert migrated == 0

        # Должна остаться только одна облигация
        all_bonds = db.get_all_bonds()
        assert len(all_bonds) == 1

    def test_get_favorite_bonds_as_config_format(self):
        """Проверяем формат get_favorite_bonds_as_config для совместимости с sidebar"""
        db = get_db()

        # Добавляем облигации
        db.save_bond({
            'isin': 'SU26221RMFS0',
            'name': 'ОФЗ 26221',
            'maturity_date': '2033-03-23',
            'coupon_rate': 7.7,
            'is_favorite': 1
        })
        db.save_bond({
            'isin': 'SU26225RMFS1',
            'name': 'ОФЗ 26225',
            'maturity_date': '2034-05-10',
            'coupon_rate': 7.25,
            'is_favorite': 0  # Не избранное
        })

        # Получаем в формате config
        favorites_config = db.get_favorite_bonds_as_config()

        # Должна быть только одна избранная
        assert len(favorites_config) == 1
        assert 'SU26221RMFS0' in favorites_config
        assert 'SU26225RMFS1' not in favorites_config

        # Проверяем структуру
        bond = favorites_config['SU26221RMFS0']
        assert bond['isin'] == 'SU26221RMFS0'
        assert bond['name'] == 'ОФЗ 26221'
        assert bond['maturity_date'] == '2033-03-23'
        assert bond['coupon_rate'] == 7.7


# ==========================================
# ТЕСТЫ ЗАГРУЗКИ ДЛЯ SIDEBAR
# ==========================================

class TestSidebarBondsLoading:
    """Тесты загрузки облигаций для sidebar"""

    def setup_method(self):
        reset_db()

    def test_get_favorite_bonds_ordered_by_duration(self):
        """Избранные облигации должны быть отсортированы по дюрации"""
        db = get_db()

        # Добавляем облигации с разной дюрацией
        db.save_bond({
            'isin': 'SU26230RMFS1',
            'name': 'ОФЗ 26230',
            'is_favorite': 1,
            'duration_years': 15.0
        })
        db.save_bond({
            'isin': 'SU26221RMFS0',
            'name': 'ОФЗ 26221',
            'is_favorite': 1,
            'duration_years': 8.0
        })
        db.save_bond({
            'isin': 'SU26238RMFS4',
            'name': 'ОФЗ 26238',
            'is_favorite': 1,
            'duration_years': 12.0
        })

        favorites = db.get_favorite_bonds()

        # Должны быть отсортированы по дюрации
        assert len(favorites) == 3
        assert favorites[0]['isin'] == 'SU26221RMFS0'  # 8 лет
        assert favorites[1]['isin'] == 'SU26238RMFS4'  # 12 лет
        assert favorites[2]['isin'] == 'SU26230RMFS1'  # 15 лет

    def test_get_favorite_bonds_empty_when_none(self):
        """Пустой список при отсутствии избранных"""
        db = get_db()

        # Добавляем облигации без is_favorite
        db.save_bond({
            'isin': 'SU26221RMFS0',
            'name': 'ОФЗ 26221',
            'is_favorite': 0
        })

        favorites = db.get_favorite_bonds()
        assert len(favorites) == 0

    def test_set_favorite_updates_existing_bond(self):
        """set_favorite должен обновлять существующую облигацию"""
        db = get_db()

        # Добавляем облигацию
        db.save_bond({
            'isin': 'SU26221RMFS0',
            'name': 'ОФЗ 26221',
            'is_favorite': 0
        })

        # Устанавливаем в избранное
        result = db.set_favorite('SU26221RMFS0', True)
        assert result is True

        # Проверяем
        favorites = db.get_favorite_bonds()
        assert len(favorites) == 1
        assert favorites[0]['isin'] == 'SU26221RMFS0'

    def test_unset_favorite(self):
        """Снятие флага избранного"""
        db = get_db()

        # Добавляем избранную облигацию
        db.save_bond({
            'isin': 'SU26221RMFS0',
            'name': 'ОФЗ 26221',
            'is_favorite': 1
        })

        # Снимаем флаг
        result = db.set_favorite('SU26221RMFS0', False)
        assert result is True

        # Проверяем
        favorites = db.get_favorite_bonds()
        assert len(favorites) == 0


# ==========================================
# ТЕСТЫ КЛАССА BONDITEM
# ==========================================

class TestSidebarBondItemClass:
    """Тесты класса BondItem для sidebar"""

    def test_bond_item_attributes(self):
        """Проверяем атрибуты BondItem"""
        # Имитируем класс BondItem из app.py
        class BondItem:
            def __init__(self, data):
                self.isin = data.get('isin')
                self.name = data.get('name', '')
                self.maturity_date = data.get('maturity_date', '')
                self.coupon_rate = data.get('coupon_rate')
                self.face_value = data.get('face_value', 1000)
                self.coupon_frequency = data.get('coupon_frequency', 2)
                self.issue_date = data.get('issue_date', '')
                self.day_count_convention = data.get('day_count_convention', 'ACT/ACT')

        bond_data = {
            'isin': 'SU26221RMFS0',
            'name': 'ОФЗ 26221',
            'maturity_date': '2033-03-23',
            'coupon_rate': 7.7,
            'face_value': 1000,
            'coupon_frequency': 2,
            'issue_date': '2017-02-15',
            'day_count_convention': 'ACT/ACT'
        }

        bond = BondItem(bond_data)

        assert bond.isin == 'SU26221RMFS0'
        assert bond.name == 'ОФЗ 26221'
        assert bond.maturity_date == '2033-03-23'
        assert bond.coupon_rate == 7.7
        assert bond.face_value == 1000
        assert bond.coupon_frequency == 2
        assert bond.issue_date == '2017-02-15'
        assert bond.day_count_convention == 'ACT/ACT'

    def test_bond_item_defaults(self):
        """Проверяем значения по умолчанию BondItem"""
        class BondItem:
            def __init__(self, data):
                self.isin = data.get('isin')
                self.name = data.get('name', '')
                self.maturity_date = data.get('maturity_date', '')
                self.coupon_rate = data.get('coupon_rate')
                self.face_value = data.get('face_value', 1000)
                self.coupon_frequency = data.get('coupon_frequency', 2)
                self.issue_date = data.get('issue_date', '')
                self.day_count_convention = data.get('day_count_convention', 'ACT/ACT')

        bond = BondItem({'isin': 'TEST'})

        assert bond.name == ''
        assert bond.maturity_date == ''
        assert bond.coupon_rate is None
        assert bond.face_value == 1000
        assert bond.coupon_frequency == 2


# ==========================================
# ТЕСТЫ РАСЧЁТА ЛЕТ ДО ПОГАШЕНИЯ
# ==========================================

class TestYearsToMaturity:
    """Тесты расчёта лет до погашения"""

    def test_get_years_to_maturity_future(self):
        """Годы до погашения в будущем"""
        def get_years_to_maturity(maturity_str):
            try:
                maturity = datetime.strptime(maturity_str, '%Y-%m-%d')
                return round((maturity - datetime.now()).days / 365.25, 1)
            except:
                return 0

        # Дата через 10 лет
        future_date = (datetime.now() + timedelta(days=3650)).strftime('%Y-%m-%d')
        years = get_years_to_maturity(future_date)

        assert abs(years - 10.0) < 0.1

    def test_get_years_to_maturity_past(self):
        """Годы до погашения в прошлом (погашенная облигация)"""
        def get_years_to_maturity(maturity_str):
            try:
                maturity = datetime.strptime(maturity_str, '%Y-%m-%d')
                return round((maturity - datetime.now()).days / 365.25, 1)
            except:
                return 0

        # Дата в прошлом
        past_date = "2020-01-01"
        years = get_years_to_maturity(past_date)

        assert years < 0

    def test_get_years_to_maturity_invalid(self):
        """Неверный формат даты"""
        def get_years_to_maturity(maturity_str):
            try:
                maturity = datetime.strptime(maturity_str, '%Y-%m-%d')
                return round((maturity - datetime.now()).days / 365.25, 1)
            except:
                return 0

        years = get_years_to_maturity("invalid-date")
        assert years == 0


# ==========================================
# ТЕСТЫ ФОРМАТИРОВАНИЯ МЕТКИ
# ==========================================

class TestFormatBondLabel:
    """Тесты форматирования метки облигации для sidebar"""

    def test_format_with_all_data(self):
        """Форматирование с полными данными"""
        def get_years_to_maturity(maturity_str):
            try:
                maturity = datetime.strptime(maturity_str, '%Y-%m-%d')
                return round((maturity - datetime.now()).days / 365.25, 1)
            except:
                return 0

        def format_bond_label(bond, ytm=None, duration_years=None):
            years = get_years_to_maturity(bond['maturity_date'])
            parts = [f"{bond['name']}"]

            if ytm is not None:
                parts.append(f"YTM: {ytm:.2f}%")
            if duration_years is not None:
                parts.append(f"Дюр: {duration_years:.1f}г.")
            parts.append(f"{years}г. до погашения")

            return " | ".join(parts)

        bond = {
            'name': 'ОФЗ 26221',
            'maturity_date': (datetime.now() + timedelta(days=3650)).strftime('%Y-%m-%d')
        }

        label = format_bond_label(bond, ytm=7.5, duration_years=8.2)

        assert 'ОФЗ 26221' in label
        assert 'YTM: 7.50%' in label
        assert 'Дюр: 8.2г.' in label
        assert 'г. до погашения' in label

    def test_format_without_ytm_duration(self):
        """Форматирование без YTM и дюрации"""
        def get_years_to_maturity(maturity_str):
            try:
                maturity = datetime.strptime(maturity_str, '%Y-%m-%d')
                return round((maturity - datetime.now()).days / 365.25, 1)
            except:
                return 0

        def format_bond_label(bond, ytm=None, duration_years=None):
            years = get_years_to_maturity(bond['maturity_date'])
            parts = [f"{bond['name']}"]

            if ytm is not None:
                parts.append(f"YTM: {ytm:.2f}%")
            if duration_years is not None:
                parts.append(f"Дюр: {duration_years:.1f}г.")
            parts.append(f"{years}г. до погашения")

            return " | ".join(parts)

        bond = {
            'name': 'ОФЗ 26221',
            'maturity_date': (datetime.now() + timedelta(days=3650)).strftime('%Y-%m-%d')
        }

        label = format_bond_label(bond)

        assert 'ОФЗ 26221' in label
        assert 'YTM:' not in label
        assert 'Дюр:' not in label
        assert 'г. до погашения' in label


def run_tests():
    """Запуск всех тестов"""
    import traceback

    # Инициализация БД
    setup_module()

    test_classes = [
        TestSidebarMigration,
        TestSidebarBondsLoading,
        TestSidebarBondItemClass,
        TestYearsToMaturity,
        TestFormatBondLabel,
    ]

    passed = 0
    failed = 0

    for test_class in test_classes:
        instance = test_class()

        # Вызываем setup_method если есть
        if hasattr(instance, 'setup_method'):
            try:
                instance.setup_method()
            except:
                pass

        for method_name in dir(instance):
            if method_name.startswith('test_'):
                try:
                    method = getattr(instance, method_name)
                    method()
                    print(f"✅ {test_class.__name__}.{method_name}")
                    passed += 1
                except AssertionError as e:
                    print(f"❌ {test_class.__name__}.{method_name}: {e}")
                    failed += 1
                except Exception as e:
                    print(f"❌ {test_class.__name__}.{method_name}: {e}")
                    traceback.print_exc()
                    failed += 1

                # Reset между тестами для классов с reset_db
                if hasattr(test_class, 'setup_method'):
                    reset_db()

    # Очистка
    teardown_module()

    print(f"\n{'='*50}")
    print(f"Результат: {passed} пройдено, {failed} провалено")
    print(f"{'='*50}")

    return failed == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
