"""
Управление соединением с базой данных

Содержит функции для подключения и инициализации БД.
"""
import sqlite3
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Путь к БД
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ofz_data.db")


def ensure_db_dir():
    """Создать директорию для БД если не существует"""
    db_dir = os.path.dirname(DB_PATH)
    os.makedirs(db_dir, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Получить соединение с БД"""
    ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Инициализировать структуру БД"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # ==========================================
    # ТАБЛИЦА ОБЛИГАЦИЙ
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bonds (
            isin TEXT PRIMARY KEY,
            name TEXT,
            short_name TEXT,
            coupon_rate REAL,
            maturity_date TEXT,
            issue_date TEXT,
            face_value REAL DEFAULT 1000,
            coupon_frequency INTEGER DEFAULT 2,
            day_count TEXT DEFAULT 'ACT/ACT',
            is_favorite INTEGER DEFAULT 0,
            last_price REAL,
            last_ytm REAL,
            duration_years REAL,
            duration_days REAL,
            last_trade_date TEXT,
            last_updated TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Миграция: добавляем новые колонки если их нет
    new_columns = [
        ('short_name', 'TEXT'),
        ('issue_date', 'TEXT'),
        ('day_count', "TEXT DEFAULT 'ACT/ACT'"),
        ('is_favorite', 'INTEGER DEFAULT 0'),
        ('last_price', 'REAL'),
        ('last_ytm', 'REAL'),
        ('duration_years', 'REAL'),
        ('duration_days', 'REAL'),
        ('last_trade_date', 'TEXT'),
        ('last_updated', 'TEXT'),
    ]

    cursor.execute("PRAGMA table_info(bonds)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            cursor.execute(f'ALTER TABLE bonds ADD COLUMN {col_name} {col_type}')
            logger.info(f"Добавлена колонка {col_name} в таблицу bonds")
    
    # ==========================================
    # ТАБЛИЦА СЫРЫХ СВЕЧЕЙ (с MOEX)
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isin TEXT NOT NULL,
            interval TEXT NOT NULL,
            datetime TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            ytm_open REAL,
            ytm_high REAL,
            ytm_low REAL,
            ytm_close REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(isin, interval, datetime)
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_candles_isin_interval 
        ON candles(isin, interval)
    ''')
    
    # ==========================================
    # ТАБЛИЦА ДНЕВНЫХ YTM (с MOEX, без расчёта)
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_ytm (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isin TEXT NOT NULL,
            date TEXT NOT NULL,
            ytm REAL,
            price REAL,
            duration_days REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(isin, date)
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_daily_ytm_isin 
        ON daily_ytm(isin)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_daily_ytm_date 
        ON daily_ytm(date)
    ''')
    
    # ==========================================
    # ТАБЛИЦА РАССЧИТАННЫХ YTM (из цен свечей)
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS intraday_ytm (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isin TEXT NOT NULL,
            interval TEXT NOT NULL,
            datetime TEXT NOT NULL,
            price_close REAL,
            ytm REAL,
            accrued_interest REAL,
            volume REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(isin, interval, datetime)
        )
    ''')
    
    # Миграция: добавляем колонку volume если её нет
    cursor.execute("PRAGMA table_info(intraday_ytm)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if 'volume' not in existing_columns:
        cursor.execute('ALTER TABLE intraday_ytm ADD COLUMN volume REAL')
        logger.info("Добавлена колонка volume в таблицу intraday_ytm")
    
    # Миграция: добавляем колонку value (объём в рублях) если её нет
    if 'value' not in existing_columns:
        cursor.execute('ALTER TABLE intraday_ytm ADD COLUMN value REAL')
        logger.info("Добавлена колонка value в таблицу intraday_ytm")
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_intraday_ytm_isin_interval 
        ON intraday_ytm(isin, interval)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_intraday_ytm_datetime 
        ON intraday_ytm(datetime)
    ''')
    
    # ==========================================
    # ТАБЛИЦА СПРЕДОВ
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS spreads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isin_1 TEXT NOT NULL,
            isin_2 TEXT NOT NULL,
            mode TEXT NOT NULL,
            interval TEXT,
            datetime TEXT NOT NULL,
            ytm_1 REAL,
            ytm_2 REAL,
            spread_bp REAL,
            signal TEXT,
            p25 REAL,
            p75 REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_spreads_isins 
        ON spreads(isin_1, isin_2)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_spreads_mode 
        ON spreads(mode)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_spreads_datetime 
        ON spreads(datetime)
    ''')
    
    # ==========================================
    # ТАБЛИЦА СНИМКОВ (SNAPSHOTS)
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isin_1 TEXT NOT NULL,
            isin_2 TEXT NOT NULL,
            interval TEXT NOT NULL,
            ytm_1 REAL,
            ytm_2 REAL,
            price_1 REAL,
            price_2 REAL,
            spread_bp REAL,
            signal TEXT,
            p25 REAL,
            p75 REAL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp 
        ON snapshots(timestamp)
    ''')
    
    # ==========================================
    # ТАБЛИЦА ЛОГА ОБНОВЛЕНИЙ
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS update_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isin TEXT NOT NULL,
            mode TEXT NOT NULL,
            interval TEXT,
            last_datetime TEXT,
            records_added INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ==========================================
    # ТАБЛИЦА КЭША МЕТАДАННЫХ
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cache_metadata (
            cache_type TEXT PRIMARY KEY,
            updated_at TEXT,
            ttl_seconds INTEGER DEFAULT 86400,
            data_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ==========================================
    # ТАБЛИЦА КЭША КОИНТЕГРАЦИИ
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cointegration_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bond1_isin TEXT NOT NULL,
            bond2_isin TEXT NOT NULL,
            pair_key TEXT NOT NULL UNIQUE,
            is_cointegrated INTEGER DEFAULT 0,
            pvalue REAL,
            half_life REAL,
            hedge_ratio REAL,
            data_days INTEGER DEFAULT 0,
            adf_bond1_pvalue REAL,
            adf_bond2_pvalue REAL,
            both_nonstationary INTEGER DEFAULT 0,
            low_data INTEGER DEFAULT 0,
            error TEXT,
            checked_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Миграция: проверяем наличие колонок cointegration_cache
    cursor.execute("PRAGMA table_info(cointegration_cache)")
    coint_columns = {row[1] for row in cursor.fetchall()}
    
    # Если нет pair_key - пересоздаём таблицу (она могла быть создана в старой версии)
    if 'pair_key' not in coint_columns and len(coint_columns) > 0:
        logger.info("Миграция: пересоздание cointegration_cache с новой структурой")
        cursor.execute('DROP TABLE IF EXISTS cointegration_cache')
        cursor.execute('''
            CREATE TABLE cointegration_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bond1_isin TEXT NOT NULL,
                bond2_isin TEXT NOT NULL,
                pair_key TEXT NOT NULL UNIQUE,
                is_cointegrated INTEGER DEFAULT 0,
                pvalue REAL,
                half_life REAL,
                hedge_ratio REAL,
                data_days INTEGER DEFAULT 0,
                adf_bond1_pvalue REAL,
                adf_bond2_pvalue REAL,
                both_nonstationary INTEGER DEFAULT 0,
                low_data INTEGER DEFAULT 0,
                error TEXT,
                checked_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_cointegration_pair_key 
        ON cointegration_cache(pair_key)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_cointegration_checked_at 
        ON cointegration_cache(checked_at)
    ''')
    
    # ==========================================
    # ТАБЛИЦА ПАРАМЕТРОВ NELSON-SIEGEL (КБД)
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ns_params (
            date TEXT PRIMARY KEY,
            b1 REAL,
            b2 REAL,
            b3 REAL,
            t1 REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_ns_params_date 
        ON ns_params(date)
    ''')
    
    # ==========================================
    # ТАБЛИЦА G-SPREAD (рассчитанный)
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS g_spreads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isin TEXT NOT NULL,
            date TEXT NOT NULL,
            ytm_bond REAL,
            duration_years REAL,
            ytm_kbd REAL,
            g_spread_bp REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(isin, date)
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_g_spreads_isin 
        ON g_spreads(isin)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_g_spreads_date 
        ON g_spreads(date)
    ''')
    
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")
