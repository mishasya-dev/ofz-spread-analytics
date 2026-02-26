"""
Тесты для таблицы bonds (версия 0.2.0)

Запуск:
    python3 tests/test_bonds.py
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
db_module.DB_PATH = os.path.join(TEMP_DIR, "test_bonds.db")

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


class TestBondsTableStructure:
    """Тесты структуры таблицы bonds"""

    def setup_method(self):
        """Setup для этого класса"""
        pass  # Не нужен reset_db для тестов структуры

    def test_table_exists(self):
        """Таблица bonds существует"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bonds'")
        result = cursor.fetchone()
        conn.close()
        assert result is not None, "Таблица bonds не найдена"

    def test_all_columns_exist(self):
        """Все необходимые колонки существуют"""
        required_columns = [
            'isin', 'name', 'short_name', 'coupon_rate', 'maturity_date',
            'issue_date', 'face_value', 'coupon_frequency', 'day_count',
            'is_favorite', 'last_price', 'last_ytm', 'duration_years',
            'duration_days', 'last_trade_date', 'last_updated', 'created_at'
        ]

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(bonds)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        for col in required_columns:
            assert col in existing_columns, f"Колонка {col} отсутствует"

    def test_isin_primary_key(self):
        """ISIN является первичным ключом"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(bonds)")
        for row in cursor.fetchall():
            if row[1] == 'isin':
                assert row[5] == 1, "ISIN должен быть PRIMARY KEY"
                break
        conn.close()

    def test_default_values(self):
        """Проверка значений по умолчанию"""
        db = get_db()

        # Сохраняем с минимальными данными
        db.save_bond({'isin': 'SU0000000000'})

        # Загружаем и проверяем defaults
        bond = db.load_bond('SU0000000000')
        assert bond['face_value'] == 1000, "face_value должен быть 1000"
        assert bond['coupon_frequency'] == 2, "coupon_frequency должен быть 2"
        assert bond['day_count'] == 'ACT/ACT', "day_count должен быть ACT/ACT"
        assert bond['is_favorite'] == 0, "is_favorite должен быть 0"

        # Очищаем
        reset_db()


class TestSaveBond:
    """Тесты сохранения облигаций"""

    def setup_method(self):
        reset_db()

    def test_save_bond_minimal(self):
        """Сохранение с минимальными данными"""
        db = get_db()
        result = db.save_bond({'isin': 'SU26221RMFS0'})
        assert result is True, "save_bond должен вернуть True"

    def test_save_bond_full(self):
        """Сохранение со всеми полями"""
        db = get_db()
        bond_data = {
            'isin': 'SU26221RMFS0',
            'name': 'ОФЗ 26221',
            'short_name': 'ОФЗ26221',
            'coupon_rate': 7.7,
            'maturity_date': '2033-03-23',
            'issue_date': '2017-02-15',
            'face_value': 1000,
            'coupon_frequency': 2,
            'day_count': 'ACT/ACT',
            'is_favorite': 1,
            'last_price': 95.5,
            'last_ytm': 15.2,
            'duration_years': 7.2,
            'duration_days': 2628,
            'last_trade_date': '2026-02-27'
        }
        result = db.save_bond(bond_data)
        assert result is True

    def test_save_bond_update(self):
        """Обновление существующей облигации"""
        db = get_db()

        # Первое сохранение
        db.save_bond({'isin': 'SU26221RMFS0', 'name': 'ОФЗ 26221'})

        # Второе сохранение с обновлением
        db.save_bond({'isin': 'SU26221RMFS0', 'name': 'ОФЗ 26221 UPDATED'})

        bond = db.load_bond('SU26221RMFS0')
        assert bond['name'] == 'ОФЗ 26221 UPDATED'

    def test_last_updated_set(self):
        """Поле last_updated устанавливается"""
        db = get_db()
        db.save_bond({'isin': 'SU26221RMFS0'})

        bond = db.load_bond('SU26221RMFS0')
        assert bond['last_updated'] is not None


class TestLoadBond:
    """Тесты загрузки облигаций"""

    def setup_method(self):
        reset_db()

    def test_load_existing_bond(self):
        """Загрузка существующей облигации"""
        db = get_db()
        db.save_bond({'isin': 'SU26221RMFS0', 'name': 'ОФЗ 26221'})

        bond = db.load_bond('SU26221RMFS0')
        assert bond is not None
        assert bond['isin'] == 'SU26221RMFS0'
        assert bond['name'] == 'ОФЗ 26221'

    def test_load_nonexistent_bond(self):
        """Загрузка несуществующей облигации"""
        db = get_db()
        bond = db.load_bond('SU9999999999')
        assert bond is None


class TestFavorites:
    """Тесты работы с избранными облигациями"""

    def setup_method(self):
        reset_db()

    def test_set_favorite(self):
        """Установка флага избранного"""
        db = get_db()
        db.save_bond({'isin': 'SU26221RMFS0', 'is_favorite': 0})

        result = db.set_favorite('SU26221RMFS0', True)
        assert result is True

        bond = db.load_bond('SU26221RMFS0')
        assert bond['is_favorite'] == 1

    def test_unset_favorite(self):
        """Снятие флага избранного"""
        db = get_db()
        db.save_bond({'isin': 'SU26221RMFS0', 'is_favorite': 1})

        result = db.set_favorite('SU26221RMFS0', False)
        assert result is True

        bond = db.load_bond('SU26221RMFS0')
        assert bond['is_favorite'] == 0

    def test_get_favorite_bonds(self):
        """Получение списка избранных"""
        db = get_db()

        # Добавляем несколько облигаций
        db.save_bond({'isin': 'SU26221RMFS0', 'duration_years': 7.0})
        db.save_bond({'isin': 'SU26225RMFS1', 'duration_years': 8.0})
        db.save_bond({'isin': 'SU26230RMFS1', 'duration_years': 5.0})

        # Отмечаем две как избранные
        db.set_favorite('SU26221RMFS0', True)
        db.set_favorite('SU26230RMFS1', True)

        favorites = db.get_favorite_bonds()
        assert len(favorites) == 2
        # Должны быть отсортированы по duration_years
        assert favorites[0]['isin'] == 'SU26230RMFS1'  # duration 5.0
        assert favorites[1]['isin'] == 'SU26221RMFS0'  # duration 7.0

    def test_get_all_bonds_favorites_first(self):
        """Все облигации: избранное в начале"""
        db = get_db()

        db.save_bond({'isin': 'SU26221RMFS0', 'duration_years': 7.0})
        db.save_bond({'isin': 'SU26225RMFS1', 'duration_years': 8.0})
        db.save_bond({'isin': 'SU26230RMFS1', 'duration_years': 5.0})

        db.set_favorite('SU26225RMFS1', True)

        all_bonds = db.get_all_bonds()
        assert all_bonds[0]['isin'] == 'SU26225RMFS1'  # Избранная первой


class TestUpdateMarketData:
    """Тесты обновления рыночных данных"""

    def setup_method(self):
        reset_db()

    def test_update_market_data(self):
        """Обновление рыночных данных"""
        db = get_db()
        db.save_bond({'isin': 'SU26221RMFS0'})

        result = db.update_bond_market_data(
            isin='SU26221RMFS0',
            last_price=96.5,
            last_ytm=15.3,
            duration_years=7.2,
            duration_days=2628,
            last_trade_date='2026-02-27'
        )
        assert result is True

        bond = db.load_bond('SU26221RMFS0')
        assert bond['last_price'] == 96.5
        assert bond['last_ytm'] == 15.3
        assert bond['duration_years'] == 7.2
        assert bond['duration_days'] == 2628
        assert bond['last_trade_date'] == '2026-02-27'


class TestDeleteBond:
    """Тесты удаления облигаций"""

    def setup_method(self):
        reset_db()

    def test_delete_existing_bond(self):
        """Удаление существующей облигации"""
        db = get_db()
        db.save_bond({'isin': 'SU26221RMFS0'})

        result = db.delete_bond('SU26221RMFS0')
        assert result is True

        bond = db.load_bond('SU26221RMFS0')
        assert bond is None

    def test_delete_nonexistent_bond(self):
        """Удаление несуществующей облигации"""
        db = get_db()
        result = db.delete_bond('SU9999999999')
        assert result is False


class TestBondsCount:
    """Тесты подсчёта облигаций"""

    def setup_method(self):
        reset_db()

    def test_empty_count(self):
        """Количество в пустой таблице"""
        db = get_db()
        assert db.get_bonds_count() == 0

    def test_count_after_save(self):
        """Количество после сохранения"""
        db = get_db()
        db.save_bond({'isin': 'SU26221RMFS0'})
        db.save_bond({'isin': 'SU26225RMFS1'})
        assert db.get_bonds_count() == 2


def run_tests():
    """Запуск всех тестов"""
    import traceback

    # Инициализация БД
    setup_module()

    test_classes = [
        TestBondsTableStructure,
        TestSaveBond,
        TestLoadBond,
        TestFavorites,
        TestUpdateMarketData,
        TestDeleteBond,
        TestBondsCount,
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
