"""
Тесты для контекстного менеджера БД

Модуль тестирует:
- get_db_connection() - контекстный менеджер для соединения
- get_db_cursor() - контекстный менеджер для курсора
- Автоматическое закрытие соединений
- Rollback при ошибках
"""
import pytest
import sqlite3
import tempfile
import os
from unittest.mock import patch, MagicMock
from datetime import datetime

# Мок streamlit до импорта
import sys
sys.modules['streamlit'] = MagicMock()


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def temp_db():
    """Временная БД для тестов"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Создаём таблицы
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Таблица bonds
    cursor.execute('''
        CREATE TABLE bonds (
            isin TEXT PRIMARY KEY,
            name TEXT,
            coupon_rate REAL,
            maturity_date TEXT
        )
    ''')
    
    # Таблица для тестирования транзакций
    cursor.execute('''
        CREATE TABLE test_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            value TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def mock_db_path(temp_db):
    """Мок пути к БД"""
    import core.db.connection as db_module
    original_path = db_module.DB_PATH
    db_module.DB_PATH = temp_db
    
    yield temp_db
    
    db_module.DB_PATH = original_path


# ============================================
# TestGetDbConnection
# ============================================

class TestGetDbConnection:
    """Тесты контекстного менеджера get_db_connection()"""
    
    def test_basic_usage(self, mock_db_path):
        """Базовое использование контекстного менеджера"""
        from core.db.connection import get_db_connection
        
        with get_db_connection() as conn:
            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            assert result is not None
    
    def test_connection_closed_after_context(self, mock_db_path):
        """Соединение закрывается после выхода из контекста"""
        from core.db.connection import get_db_connection
        
        with get_db_connection() as conn:
            pass
        
        # После выхода из контекста соединение должно быть закрыто
        # Попытка выполнить запрос должна вызвать ошибку
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute('SELECT 1')
    
    def test_connection_closed_on_exception(self, mock_db_path):
        """Соединение закрывается даже при исключении"""
        from core.db.connection import get_db_connection
        
        conn_ref = None
        try:
            with get_db_connection() as conn:
                conn_ref = conn
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Соединение должно быть закрыто
        assert conn_ref is not None
        with pytest.raises(sqlite3.ProgrammingError):
            conn_ref.execute('SELECT 1')
    
    def test_auto_commit_on_success(self, mock_db_path):
        """Автоматический commit при успешном выходе"""
        from core.db.connection import get_db_connection
        
        # Вставляем данные
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO bonds (isin, name) VALUES (?, ?)",
                ('TEST001', 'Test Bond')
            )
        
        # Проверяем, что данные сохранены
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bonds WHERE isin = ?", ('TEST001',))
            row = cursor.fetchone()
            assert row is not None
            assert row['name'] == 'Test Bond'
    
    def test_rollback_on_exception(self, mock_db_path):
        """Rollback при исключении"""
        from core.db.connection import get_db_connection
        
        # Вставляем данные и вызываем исключение
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO bonds (isin, name) VALUES (?, ?)",
                ('TEST002', 'Test Bond 2')
                )
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Данные должны быть откачены
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bonds WHERE isin = ?", ('TEST002',))
            row = cursor.fetchone()
            assert row is None
    
    def test_row_factory_set(self, mock_db_path):
        """row_factory установлен на sqlite3.Row"""
        from core.db.connection import get_db_connection
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO bonds (isin, name) VALUES (?, ?)",
                ('TEST003', 'Test Bond 3')
            )
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bonds WHERE isin = ?", ('TEST003',))
            row = cursor.fetchone()
            # Доступ по имени колонки
            assert row['isin'] == 'TEST003'
            assert row['name'] == 'Test Bond 3'
    
    def test_multiple_operations_in_context(self, mock_db_path):
        """Несколько операций в одном контексте"""
        from core.db.connection import get_db_connection
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Несколько вставок
            for i in range(5):
                cursor.execute(
                    "INSERT INTO bonds (isin, name) VALUES (?, ?)",
                    (f'TEST{i:03d}', f'Test Bond {i}')
                )
            
            # Проверка в том же контексте
            cursor.execute("SELECT COUNT(*) as cnt FROM bonds")
            row = cursor.fetchone()
            assert row['cnt'] == 5


# ============================================
# TestGetDbCursor
# ============================================

class TestGetDbCursor:
    """Тесты контекстного менеджера get_db_cursor()"""
    
    def test_basic_usage(self, mock_db_path):
        """Базовое использование курсора"""
        from core.db.connection import get_db_cursor
        
        with get_db_cursor() as cursor:
            cursor.execute('SELECT 1 as value')
            result = cursor.fetchone()
            assert result['value'] == 1
    
    def test_insert_and_select(self, mock_db_path):
        """Вставка и выборка данных"""
        from core.db.connection import get_db_cursor
        
        # Вставка
        with get_db_cursor() as cursor:
            cursor.execute(
                "INSERT INTO bonds (isin, name) VALUES (?, ?)",
                ('CURSOR001', 'Cursor Test Bond')
            )
        
        # Выборка
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM bonds WHERE isin = ?", ('CURSOR001',))
            row = cursor.fetchone()
            assert row is not None
            assert row['name'] == 'Cursor Test Bond'
    
    def test_multiple_queries_same_cursor(self, mock_db_path):
        """Несколько запросов через один курсор"""
        from core.db.connection import get_db_cursor
        
        with get_db_cursor() as cursor:
            # Вставка
            cursor.execute(
                "INSERT INTO bonds (isin, name) VALUES (?, ?)",
                ('CURSOR002', 'Test')
            )
            
            # Выборка
            cursor.execute("SELECT COUNT(*) as cnt FROM bonds")
            row = cursor.fetchone()
            assert row['cnt'] == 1


# ============================================
# TestComparisonWithManualApproach
# ============================================

class TestComparisonWithManualApproach:
    """Сравнение контекстного менеджера с ручным подходом"""
    
    def test_manual_approach_with_exception_leaks_connection(self, mock_db_path):
        """Демонстрация проблемы ручного подхода"""
        from core.db.connection import get_connection
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Вставка данных
        cursor.execute(
            "INSERT INTO test_table (value) VALUES (?)",
            ('before_exception',)
        )
        conn.commit()
        
        # Имитация исключения до conn.close()
        # Закомментируем conn.close() чтобы показать проблему
        try:
            cursor.execute(
                "INSERT INTO test_table (value) VALUES (?)",
                ('exception_case',)
            )
            # Если здесь исключение - conn.close() не будет вызван!
            raise ValueError("Simulated error")
            # conn.close()  # Не будет вызван!
        except ValueError:
            pass
        
        # Соединение всё ещё открыто!
        # Это демонстрация - в реальном коде это утечка
        # Проверим что можем выполнить запрос на "утекшем" соединении
        cursor2 = conn.cursor()
        cursor2.execute('SELECT 1')
        assert cursor2.fetchone() is not None
        
        # Закроем вручную для cleanup
        conn.close()
    
    def test_context_manager_handles_exception(self, mock_db_path):
        """Контекстный менеджер корректно обрабатывает исключение"""
        from core.db.connection import get_db_connection
        
        # Сначала вставим данные
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO test_table (value) VALUES (?)",
                ('safe_data',)
            )
        
        # Теперь попробуем с исключением
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO test_table (value) VALUES (?)",
                    ('will_be_rolled_back',)
                )
                raise ValueError("Simulated error")
        except ValueError:
            pass
        
        # Проверяем что safe_data есть, а will_be_rolled_back откачен
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test_table WHERE value = ?", ('safe_data',))
            assert cursor.fetchone() is not None
            
            cursor.execute("SELECT * FROM test_table WHERE value = ?", ('will_be_rolled_back',))
            assert cursor.fetchone() is None


# ============================================
# TestEdgeCases
# ============================================

class TestEdgeCases:
    """Тесты граничных случаев"""
    
    def test_nested_contexts(self, mock_db_path):
        """Вложенные контексты (разные соединения)"""
        from core.db.connection import get_db_connection
        
        with get_db_connection() as conn1:
            cursor1 = conn1.cursor()
            cursor1.execute(
                "INSERT INTO test_table (value) VALUES (?)",
                ('outer',)
            )
            
            # Вложенный контекст - новое соединение
            with get_db_connection() as conn2:
                cursor2 = conn2.cursor()
                # Внешняя транзакция ещё не закоммичена
                # Но внутренняя видит только закомиченные данные
                cursor2.execute("SELECT * FROM test_table WHERE value = ?", ('outer',))
                # В SQLite read committed - видим только закомиченное
                # Так что здесь может быть None или row в зависимости от изоляции
    
    def test_empty_context(self, mock_db_path):
        """Пустой контекст"""
        from core.db.connection import get_db_connection
        
        # Просто входим и выходим
        with get_db_connection():
            pass
        
        # Ничего не должно сломаться
    
    def test_context_returns_connection_object(self, mock_db_path):
        """Контекст возвращает объект соединения"""
        from core.db.connection import get_db_connection
        
        with get_db_connection() as conn:
            # Можно использовать все методы Connection
            assert hasattr(conn, 'cursor')
            assert hasattr(conn, 'commit')
            assert hasattr(conn, 'rollback')
            assert hasattr(conn, 'close')


# ============================================
# Run tests directly
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
