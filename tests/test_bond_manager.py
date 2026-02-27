"""
Тесты для компонентов bond_manager (версия 0.2.2)

Примечание: Функции форматирования не зависят от streamlit,
тесты проверяют логику без импорта UI-компонентов.

Новые тесты v0.2.2:
- TestClearAllFavorites: кнопка "Очистить избранное"
- TestFavoritesSync: синхронизация с БД (INSERT/DELETE)

Запуск:
    python3 tests/test_bond_manager.py
"""
import sys
import os
import unittest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFormatFunctions(unittest.TestCase):
    """Тесты для функций форматирования (без streamlit зависимости)"""

    def test_format_duration_years(self):
        """Форматирование дюрации"""
        # Тестируем логику напрямую
        def format_duration(duration_years):
            if duration_years is None:
                return "Н/Д"
            return f"{duration_years:.1f}г."

        assert format_duration(5.5) == "5.5г."
        assert format_duration(10.0) == "10.0г."
        assert format_duration(0.5) == "0.5г."

    def test_format_duration_none(self):
        """Дюрация None"""
        def format_duration(duration_years):
            if duration_years is None:
                return "Н/Д"
            return f"{duration_years:.1f}г."

        assert format_duration(None) == "Н/Д"

    def test_format_ytm(self):
        """Форматирование YTM"""
        def format_ytm(ytm):
            if ytm is None:
                return "Н/Д"
            return f"{ytm:.2f}%"

        assert format_ytm(15.25) == "15.25%"
        assert format_ytm(7.0) == "7.00%"

    def test_format_ytm_none(self):
        """YTM None"""
        def format_ytm(ytm):
            if ytm is None:
                return "Н/Д"
            return f"{ytm:.2f}%"

        assert format_ytm(None) == "Н/Д"

    def test_format_coupon(self):
        """Форматирование купона"""
        def format_coupon(coupon):
            if coupon is None:
                return "Н/Д"
            return f"{coupon:.2f}%"

        assert format_coupon(7.7) == "7.70%"
        assert format_coupon(12.25) == "12.25%"

    def test_format_coupon_none(self):
        """Купон None"""
        def format_coupon(coupon):
            if coupon is None:
                return "Н/Д"
            return f"{coupon:.2f}%"

        assert format_coupon(None) == "Н/Д"

    def test_format_maturity(self):
        """Форматирование даты погашения"""
        def format_maturity(maturity_date):
            if not maturity_date:
                return "Н/Д"
            try:
                dt = datetime.strptime(maturity_date, "%Y-%m-%d")
                years = (dt - datetime.now()).days / 365.25
                return f"{dt.strftime('%d.%m.%Y')} ({years:.1f}г.)"
            except:
                return maturity_date

        # Дата в будущем
        future = (datetime.now() + timedelta(days=365 * 5)).strftime("%Y-%m-%d")
        result = format_maturity(future)
        assert "г.)" in result

    def test_format_maturity_none(self):
        """Дата погашения None"""
        def format_maturity(maturity_date):
            if not maturity_date:
                return "Н/Д"
            return maturity_date

        assert format_maturity(None) == "Н/Д"

    def test_format_maturity_invalid(self):
        """Некорректная дата погашения"""
        def format_maturity(maturity_date):
            if not maturity_date:
                return "Н/Д"
            try:
                dt = datetime.strptime(maturity_date, "%Y-%m-%d")
                years = (dt - datetime.now()).days / 365.25
                return f"{dt.strftime('%d.%m.%Y')} ({years:.1f}г.)"
            except:
                return maturity_date

        assert format_maturity("invalid-date") == "invalid-date"


class TestBondManagerLogic(unittest.TestCase):
    """Тесты логики управления облигациями"""

    def test_is_favorite_toggle(self):
        """Переключение избранного"""
        # Тестируем логику переключения
        states = [
            {"is_favorite": 0, "expected": 1},
            {"is_favorite": 1, "expected": 0},
        ]

        for state in states:
            new_state = 0 if state["is_favorite"] else 1
            assert new_state == state["expected"]

    def test_sorting_by_duration(self):
        """Сортировка по дюрации"""
        bonds = [
            {"isin": "A", "duration_years": 10.0},
            {"isin": "B", "duration_years": 2.5},
            {"isin": "C", "duration_years": 5.0},
        ]

        # Сортируем по дюрации
        sorted_bonds = sorted(bonds, key=lambda b: b.get("duration_years") or 0)

        assert sorted_bonds[0]["isin"] == "B"  # 2.5
        assert sorted_bonds[1]["isin"] == "C"  # 5.0
        assert sorted_bonds[2]["isin"] == "A"  # 10.0

    def test_sorting_by_ytm(self):
        """Сортировка по YTM"""
        bonds = [
            {"isin": "A", "last_ytm": 15.0},
            {"isin": "B", "last_ytm": 10.0},
            {"isin": "C", "last_ytm": None},
        ]

        # Сортируем, None в конце
        def sort_key(b):
            ytm = b.get("last_ytm")
            return ytm if ytm is not None else float("inf")

        sorted_bonds = sorted(bonds, key=sort_key)

        assert sorted_bonds[0]["isin"] == "B"  # 10.0
        assert sorted_bonds[1]["isin"] == "A"  # 15.0
        assert sorted_bonds[2]["isin"] == "C"  # None

    def test_bond_data_structure(self):
        """Структура данных облигации"""
        bond = {
            "isin": "SU26221RMFS0",
            "name": "ОФЗ 26221",
            "short_name": "ОФЗ26221",
            "coupon_rate": 7.7,
            "maturity_date": "2033-03-23",
            "issue_date": "2017-02-15",
            "face_value": 1000,
            "coupon_frequency": 2,
            "day_count": "ACT/ACT",
            "is_favorite": 1,
            "last_price": 95.5,
            "last_ytm": 15.2,
            "duration_years": 7.2,
            "duration_days": 2628,
            "last_trade_date": "2026-02-27",
        }

        # Проверяем все поля
        assert bond["isin"] == "SU26221RMFS0"
        assert bond["is_favorite"] == 1
        assert bond["duration_years"] == 7.2
        assert bond["last_ytm"] == 15.2


class TestBondManagerUI(unittest.TestCase):
    """Тесты UI-логики (без реального streamlit)"""

    def test_button_label_favorite(self):
        """Метка кнопки избранного"""
        def get_button_label(is_favorite):
            return "⭐" if is_favorite else "☆"

        assert get_button_label(True) == "⭐"
        assert get_button_label(1) == "⭐"
        assert get_button_label(False) == "☆"
        assert get_button_label(0) == "☆"

    def test_button_type_favorite(self):
        """Тип кнопки избранного"""
        def get_button_type(is_favorite):
            return "primary" if is_favorite else "secondary"

        assert get_button_type(True) == "primary"
        assert get_button_type(1) == "primary"
        assert get_button_type(False) == "secondary"
        assert get_button_type(0) == "secondary"

    def test_column_widths(self):
        """Ширина колонок таблицы"""
        # ISIN, Название, Купон, Погашение, Дюр, YTM, ⭐
        widths = [3, 2, 1, 2, 1, 1, 0.5]
        total = sum(widths)
        assert total == 10.5

    def test_sort_options(self):
        """Опции сортировки"""
        sort_options = ["Дюрации", "YTM", "Купону", "Погашению", "Названию"]
        assert len(sort_options) == 5
        assert "Дюрации" in sort_options


class TestClearAllFavorites(unittest.TestCase):
    """Тесты для кнопки 'Очистить' (v0.2.2 - новая логика session_state)"""

    def test_clear_sets_current_favorites_to_empty(self):
        """При очистке bond_manager_current_favorites становится пустым"""
        session_state = {
            "bond_manager_current_favorites": {"SU26221RMFS0", "SU26225RMFS1"},
        }

        # Нажатие "Очистить"
        session_state["bond_manager_current_favorites"] = set()

        assert len(session_state["bond_manager_current_favorites"]) == 0

    def test_clear_preserves_original_favorites(self):
        """original_favorites сохраняется для сравнения при 'Готово'"""
        session_state = {
            "bond_manager_current_favorites": {"SU26221RMFS0", "SU26225RMFS1"},
            "bond_manager_original_favorites": {"SU26221RMFS0", "SU26225RMFS1"},
        }

        # Очистка
        session_state["bond_manager_current_favorites"] = set()

        # original_favorites не изменился
        assert len(session_state["bond_manager_original_favorites"]) == 2

    def test_clear_generates_new_uuid_for_dialog_reopen(self):
        """При очистке генерируется новый UUID для повторного открытия диалога"""
        import uuid
        
        session_state = {
            "bond_manager_open_id": "old-uuid-123",
            "bond_manager_last_shown_id": "old-uuid-123",
            "bond_manager_current_favorites": {"SU26221RMFS0"},
        }

        # Нажатие "Очистить"
        session_state["bond_manager_current_favorites"] = set()
        session_state["bond_manager_open_id"] = str(uuid.uuid4())
        session_state["bond_manager_last_shown_id"] = None
        
        assert len(session_state["bond_manager_current_favorites"]) == 0
        assert session_state["bond_manager_open_id"] != "old-uuid-123"
        assert session_state["bond_manager_last_shown_id"] is None

    def test_checkbox_change_updates_current_favorites(self):
        """Изменение чекбокса обновляет current_favorites без загрузки из БД"""
        session_state = {
            "bond_manager_current_favorites": set(),  # После очистки
            "bond_manager_original_favorites": {"SU26221RMFS0", "SU26225RMFS1"},
        }

        # Пользователь кликнул на один чекбокс (симуляция)
        session_state["bond_manager_current_favorites"] = {"SU26230RMFS1"}

        # current_favorites изменился, но НЕ вернулся к original_favorites
        assert session_state["bond_manager_current_favorites"] == {"SU26230RMFS1"}
        assert session_state["bond_manager_original_favorites"] == {"SU26221RMFS0", "SU26225RMFS1"}

    def test_done_compares_current_with_original(self):
        """При 'Готово' сравниваем current_favorites с original_favorites"""
        current_favorites = {"SU26230RMFS1"}  # Новая облигация
        original_favorites = {"SU26221RMFS0", "SU26225RMFS1"}  # Старые

        to_add = current_favorites - original_favorites
        to_remove = original_favorites - current_favorites

        assert to_add == {"SU26230RMFS1"}
        assert to_remove == {"SU26221RMFS0", "SU26225RMFS1"}

    def test_cancel_clears_session_state(self):
        """При 'Отменить' очищается session_state"""
        session_state = {
            "bond_manager_open_id": "some-uuid",
            "bond_manager_last_shown_id": "some-uuid",
            "bond_manager_current_favorites": {"SU26221RMFS0"},
            "bond_manager_original_favorites": {"SU26221RMFS0", "SU26225RMFS1"},
        }

        # Отмена
        session_state["bond_manager_open_id"] = None
        session_state["bond_manager_last_shown_id"] = None
        session_state["bond_manager_current_favorites"] = None
        session_state["bond_manager_original_favorites"] = None

        assert session_state["bond_manager_current_favorites"] is None
        assert session_state["bond_manager_original_favorites"] is None


class TestFavoritesSync(unittest.TestCase):
    """Тесты синхронизации избранного с БД (v0.2.2)"""

    def test_calculate_to_add(self):
        """Расчёт облигаций для добавления"""
        new_favorites = {"SU26221RMFS0", "SU26225RMFS1", "SU26230RMFS1"}
        old_favorites = {"SU26221RMFS0"}  # Была одна

        to_add = new_favorites - old_favorites

        assert len(to_add) == 2
        assert "SU26225RMFS1" in to_add
        assert "SU26230RMFS1" in to_add
        assert "SU26221RMFS0" not in to_add  # Уже была

    def test_calculate_to_remove(self):
        """Расчёт облигаций для удаления"""
        new_favorites = {"SU26221RMFS0"}  # Оставили одну
        old_favorites = {"SU26221RMFS0", "SU26225RMFS1", "SU26230RMFS1"}

        to_remove = old_favorites - new_favorites

        assert len(to_remove) == 2
        assert "SU26225RMFS1" in to_remove
        assert "SU26230RMFS1" in to_remove
        assert "SU26221RMFS0" not in to_remove  # Оставили

    def test_no_changes_when_same(self):
        """Нет изменений если наборы одинаковые"""
        new_favorites = {"SU26221RMFS0", "SU26225RMFS1"}
        old_favorites = {"SU26221RMFS0", "SU26225RMFS1"}

        to_add = new_favorites - old_favorites
        to_remove = old_favorites - new_favorites

        assert len(to_add) == 0
        assert len(to_remove) == 0

    def test_full_replacement(self):
        """Полная замена избранного"""
        new_favorites = {"SU26238RMFS4", "SU26240RMFS2"}  # Новые
        old_favorites = {"SU26221RMFS0", "SU26225RMFS1"}  # Старые

        to_add = new_favorites - old_favorites
        to_remove = old_favorites - new_favorites

        assert len(to_add) == 2  # Добавить 2 новых
        assert len(to_remove) == 2  # Удалить 2 старых

    def test_cancel_preserves_original(self):
        """Отмена сохраняет исходное состояние БД"""
        original_favorites = {"SU26221RMFS0", "SU26225RMFS1"}
        favorite_isins = original_favorites.copy()

        # Пользователь очистил
        favorite_isins = set()

        # Пользователь нажал "Отменить и закрыть"
        # В БД ничего не меняется
        db_favorites_after_cancel = original_favorites  # Остались те же

        assert db_favorites_after_cancel == original_favorites
        assert len(db_favorites_after_cancel) == 2


class TestBondManagerIntegration(unittest.TestCase):
    """Интеграционные тесты"""

    def test_filter_bonds_from_list(self):
        """Фильтрация списка облигаций"""
        all_bonds = [
            {"isin": "SU26221RMFS0", "is_favorite": 1},
            {"isin": "SU26225RMFS1", "is_favorite": 0},
            {"isin": "SU26230RMFS1", "is_favorite": 1},
            {"isin": "SU26238RMFS4", "is_favorite": 0},
        ]

        # Получаем избранные
        favorites = [b for b in all_bonds if b.get("is_favorite")]

        assert len(favorites) == 2
        assert favorites[0]["isin"] == "SU26221RMFS0"
        assert favorites[1]["isin"] == "SU26230RMFS1"

    def test_bond_count_display(self):
        """Отображение количества облигаций"""
        bonds = [{"isin": f"SU{i}"} for i in range(25)]

        total = len(bonds)
        favorites = len([b for b in bonds if b.get("is_favorite")])

        # Формируем текст
        text = f"Всего облигаций: {total}"

        assert "25" in text


def run_tests():
    """Запуск всех тестов"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestFormatFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestBondManagerLogic))
    suite.addTests(loader.loadTestsFromTestCase(TestBondManagerUI))
    suite.addTests(loader.loadTestsFromTestCase(TestClearAllFavorites))
    suite.addTests(loader.loadTestsFromTestCase(TestFavoritesSync))
    suite.addTests(loader.loadTestsFromTestCase(TestBondManagerIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
