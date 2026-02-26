"""
Тесты для модуля database.py
"""
import sys
import os
import tempfile
import shutil
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Цвета для вывода
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

test_results = []

def print_test(name, expected, actual, passed):
    status = f"{Colors.GREEN}✅ PASS{Colors.END}" if passed else f"{Colors.RED}❌ FAIL{Colors.END}"
    print(f"{status} {name}")
    print(f"   Ожидали:  {expected}")
    print(f"   Получили: {actual}")
    print()

def run_test(name, expected, actual, condition=None):
    if condition is None:
        passed = expected == actual
    else:
        passed = condition
    print_test(name, expected, actual, passed)
    test_results.append((name, passed))
    return passed


def test_database():
    """Запуск всех тестов БД"""
    
    # ==========================================
    # Создаём временную БД для тестов
    # ==========================================
    import core.database as db_module
    
    # Сохраняем оригинальный путь
    original_db_path = db_module.DB_PATH
    
    # Создаём временную директорию
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_ofz_data.db")
    db_module.DB_PATH = test_db_path
    
    print(f"{Colors.BLUE}Тестовая БД: {test_db_path}{Colors.END}\n")
    
    try:
        # ==========================================
        # ТЕСТ 1: Инициализация БД
        # ==========================================
        print(f"{Colors.BOLD}--- Инициализация БД ---{Colors.END}\n")
        
        db_module.init_database()
        
        run_test(
            "Файл БД создан",
            "exists = True",
            f"exists = {os.path.exists(test_db_path)}",
            os.path.exists(test_db_path)
        )
        
        # ==========================================
        # ТЕСТ 2: DatabaseManager
        # ==========================================
        print(f"{Colors.BOLD}--- DatabaseManager ---{Colors.END}\n")
        
        db = db_module.DatabaseManager()
        
        run_test(
            "DatabaseManager создан",
            "DatabaseManager",
            f"{type(db).__name__}",
            type(db).__name__ == 'DatabaseManager'
        )
        
        # ==========================================
        # ТЕСТ 3: Сохранение облигации
        # ==========================================
        print(f"{Colors.BOLD}--- Сохранение облигации ---{Colors.END}\n")
        
        bond_data = {
            'isin': 'TEST12345678',
            'name': 'Тестовая ОФЗ',
            'coupon_rate': 10.0,
            'maturity_date': '2030-12-15',
            'face_value': 1000,
            'coupon_frequency': 2
        }
        
        result = db.save_bond(bond_data)
        run_test(
            "Сохранение облигации",
            "True",
            str(result),
            result == True
        )
        
        # Загрузка облигации
        loaded_bond = db.load_bond('TEST12345678')
        run_test(
            "Загрузка облигации",
            "Тестовая ОФЗ",
            loaded_bond.get('name') if loaded_bond else "None",
            loaded_bond is not None and loaded_bond.get('name') == 'Тестовая ОФЗ'
        )
        
        # ==========================================
        # ТЕСТ 4: Сохранение свечей
        # ==========================================
        print(f"{Colors.BOLD}--- Сохранение свечей ---{Colors.END}\n")
        
        # Создаём тестовый DataFrame со свечами
        dates = pd.date_range(start='2025-01-01 10:00', periods=10, freq='H')
        candles_df = pd.DataFrame({
            'open': np.random.uniform(70, 72, 10),
            'high': np.random.uniform(72, 74, 10),
            'low': np.random.uniform(68, 70, 10),
            'close': np.random.uniform(70, 72, 10),
            'volume': np.random.randint(100, 1000, 10),
            'ytm_open': np.random.uniform(14, 15, 10),
            'ytm_high': np.random.uniform(14, 15, 10),
            'ytm_low': np.random.uniform(14, 15, 10),
            'ytm_close': np.random.uniform(14, 15, 10)
        }, index=dates)
        
        saved_count = db.save_candles('TEST12345678', '60', candles_df)
        
        run_test(
            "Сохранение 10 свечей",
            "10",
            str(saved_count),
            saved_count == 10
        )
        
        # ==========================================
        # ТЕСТ 5: Загрузка свечей
        # ==========================================
        print(f"{Colors.BOLD}--- Загрузка свечей ---{Colors.END}\n")
        
        loaded_df = db.load_candles('TEST12345678', '60')
        
        run_test(
            "Загрузка свечей из БД",
            "10 записей",
            f"{len(loaded_df)} записей",
            len(loaded_df) == 10
        )
        
        run_test(
            "Наличие колонок",
            "close, ytm_close",
            f"{', '.join([c for c in ['close', 'ytm_close'] if c in loaded_df.columns])}",
            'close' in loaded_df.columns and 'ytm_close' in loaded_df.columns
        )
        
        # ==========================================
        # ТЕСТ 6: Последняя свеча
        # ==========================================
        print(f"{Colors.BOLD}--- Последняя свеча ---{Colors.END}\n")
        
        last_dt = db.get_last_candle_datetime('TEST12345678', '60')
        
        run_test(
            "Получение последней свечи",
            "2025-01-01",
            f"{last_dt.strftime('%Y-%m-%d') if last_dt else 'None'}",
            last_dt is not None
        )
        
        # ==========================================
        # ТЕСТ 7: Количество свечей
        # ==========================================
        print(f"{Colors.BOLD}--- Количество свечей ---{Colors.END}\n")
        
        count = db.get_candles_count('TEST12345678', '60')
        
        run_test(
            "Количество свечей в БД",
            "10",
            str(count),
            count == 10
        )
        
        # ==========================================
        # ТЕСТ 8: Сохранение снимка
        # ==========================================
        print(f"{Colors.BOLD}--- Снимки (snapshots) ---{Colors.END}\n")
        
        snapshot_id = db.save_snapshot(
            isin_1='BOND1',
            isin_2='BOND2',
            interval='60',
            ytm_1=14.5,
            ytm_2=14.3,
            spread_bp=20.0,
            signal='BUY_SELL',
            p25=-10.0,
            p75=30.0
        )
        
        run_test(
            "Сохранение снимка",
            "id > 0",
            f"id = {snapshot_id}",
            snapshot_id > 0
        )
        
        # Загрузка снимков
        snapshots_df = db.load_snapshots('BOND1', 'BOND2', '60', hours=24)
        
        run_test(
            "Загрузка снимков",
            "1 запись",
            f"{len(snapshots_df)} записей",
            len(snapshots_df) == 1
        )
        
        # ==========================================
        # ТЕСТ 9: Статистика БД
        # ==========================================
        print(f"{Colors.BOLD}--- Статистика БД ---{Colors.END}\n")
        
        stats = db.get_stats()
        
        run_test(
            "Статистика: bonds_count",
            "1",
            str(stats.get('bonds_count')),
            stats.get('bonds_count') == 1
        )
        
        run_test(
            "Статистика: candles_count",
            "10",
            str(stats.get('candles_count')),
            stats.get('candles_count') == 10
        )
        
        run_test(
            "Статистика: snapshots_count",
            "1",
            str(stats.get('snapshots_count')),
            stats.get('snapshots_count') == 1
        )
        
        # ==========================================
        # ТЕСТ 10: Дубликаты (UNIQUE constraint)
        # ==========================================
        print(f"{Colors.BOLD}--- Проверка дубликатов ---{Colors.END}\n")
        
        # Пытаемся сохранить те же свечи
        saved_again = db.save_candles('TEST12345678', '60', candles_df)
        
        # Должно быть 10 (INSERT OR REPLACE)
        run_test(
            "Повторное сохранение (REPLACE)",
            "10 записей",
            f"{saved_again} записей",
            saved_again == 10
        )
        
        # Количество не должно увеличиться
        count_after = db.get_candles_count('TEST12345678', '60')
        run_test(
            "Количество не увеличилось",
            "10",
            str(count_after),
            count_after == 10
        )
        
        # ==========================================
        # ТЕСТ 11: Фильтрация по датам
        # ==========================================
        print(f"{Colors.BOLD}--- Фильтрация по датам ---{Colors.END}\n")
        
        # Добавим свечи за другой день
        dates2 = pd.date_range(start='2025-01-02 10:00', periods=5, freq='H')
        candles_df2 = pd.DataFrame({
            'open': np.random.uniform(70, 72, 5),
            'high': np.random.uniform(72, 74, 5),
            'low': np.random.uniform(68, 70, 5),
            'close': np.random.uniform(70, 72, 5),
            'volume': np.random.randint(100, 1000, 5),
            'ytm_open': np.random.uniform(14, 15, 5),
            'ytm_high': np.random.uniform(14, 15, 5),
            'ytm_low': np.random.uniform(14, 15, 5),
            'ytm_close': np.random.uniform(14, 15, 5)
        }, index=dates2)
        
        db.save_candles('TEST12345678', '60', candles_df2)
        
        # Загружаем только за 2025-01-01
        filtered_df = db.load_candles(
            'TEST12345678', '60',
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 1)
        )
        
        run_test(
            "Фильтрация по дате",
            "10 записей (только 01.01)",
            f"{len(filtered_df)} записей",
            len(filtered_df) == 10
        )
        
        # ==========================================
        # ТЕСТ 12: Удаление старых данных
        # ==========================================
        print(f"{Colors.BOLD}--- Очистка старых данных ---{Colors.END}\n")
        
        # Удаляем данные старше 1 дня (должно удалить все)
        deleted = db.cleanup_old_data(days_to_keep=1)
        
        run_test(
            "Очистка старых данных",
            "> 0 удалено",
            f"{deleted} удалено",
            deleted > 0
        )
        
        # Проверяем что данные удалены
        count_after_cleanup = db.get_candles_count('TEST12345678', '60')
        
        run_test(
            "Данные удалены",
            "0",
            str(count_after_cleanup),
            count_after_cleanup == 0
        )
        
        # ==========================================
        # ИТОГИ
        # ==========================================
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        
        passed = sum(1 for _, p in test_results if p)
        failed = sum(1 for _, p in test_results if not p)
        total = len(test_results)
        
        print(f"Всего тестов: {total}")
        print(f"{Colors.GREEN}Пройдено: {passed}{Colors.END}")
        print(f"{Colors.RED}Провалено: {failed}{Colors.END}")
        
        if failed > 0:
            print(f"\n{Colors.YELLOW}Проваленные тесты:{Colors.END}")
            for name, p in test_results:
                if not p:
                    print(f"  ❌ {name}")
        
        return failed == 0
        
    finally:
        # Восстанавливаем оригинальный путь
        db_module.DB_PATH = original_db_path
        
        # Удаляем временную директорию
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


if __name__ == "__main__":
    success = test_database()
    sys.exit(0 if success else 1)
