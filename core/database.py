"""
SQLite база данных для хранения исторических данных ОФЗ

Таблицы:
- bonds: информация об облигациях
- candles: сырые свечи с MOEX
- daily_ytm: дневные YTM с MOEX (без расчёта)
- intraday_ytm: рассчитанные YTM из цен свечей
- spreads: спреды между облигациями
- snapshots: снимки состояния
- update_log: лог обновлений
"""
import sqlite3
import os
import json
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Путь к БД
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ofz_data.db")


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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(isin, interval, datetime)
        )
    ''')
    
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
    
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")


class DatabaseManager:
    """Менеджер для работы с БД"""
    
    def __init__(self):
        init_database()
    
    # ==========================================
    # ДНЕВНЫЕ YTM (DAILY MODE)
    # ==========================================
    
    def save_daily_ytm(
        self, 
        isin: str, 
        df: pd.DataFrame
    ) -> int:
        """
        Сохранить дневные YTM с MOEX
        
        Args:
            isin: ISIN облигации
            df: DataFrame с колонками: date, ytm, price, duration_days
            
        Returns:
            Количество сохранённых записей
        """
        if df.empty:
            return 0
        
        conn = get_connection()
        cursor = conn.cursor()
        
        saved_count = 0
        
        for idx, row in df.iterrows():
            try:
                # Дата
                if isinstance(idx, pd.Timestamp):
                    date_str = idx.strftime('%Y-%m-%d')
                elif hasattr(row, 'date'):
                    date_str = row['date'].strftime('%Y-%m-%d') if isinstance(row['date'], (datetime, pd.Timestamp)) else str(row['date'])
                else:
                    date_str = str(idx)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_ytm 
                    (isin, date, ytm, price, duration_days)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    isin,
                    date_str,
                    row.get('ytm'),
                    row.get('price'),
                    row.get('duration_days')
                ))
                saved_count += 1
                
            except Exception as e:
                logger.warning(f"Ошибка сохранения daily YTM {date_str}: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Сохранено {saved_count} дневных YTM для {isin}")
        return saved_count
    
    def load_daily_ytm(
        self,
        isin: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        Загрузить дневные YTM из БД
        
        Args:
            isin: ISIN облигации
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            DataFrame с YTM
        """
        conn = get_connection()
        
        query = '''
            SELECT date, ytm, price, duration_days
            FROM daily_ytm
            WHERE isin = ?
        '''
        params = [isin]
        
        if start_date:
            query += ' AND date >= ?'
            params.append(start_date.strftime('%Y-%m-%d'))
        
        if end_date:
            query += ' AND date <= ?'
            params.append(end_date.strftime('%Y-%m-%d'))
        
        query += ' ORDER BY date'
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return pd.DataFrame()
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        return df
    
    def get_last_daily_ytm_date(self, isin: str) -> Optional[date]:
        """Получить дату последнего дневного YTM в БД"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT MAX(date) as last_date
            FROM daily_ytm
            WHERE isin = ?
        ''', (isin,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row and row['last_date']:
            return datetime.strptime(row['last_date'], '%Y-%m-%d').date()
        return None
    
    # ==========================================
    # РАССЧИТАННЫЕ YTM (INTRADAY MODE)
    # ==========================================
    
    def save_intraday_ytm(
        self, 
        isin: str, 
        interval: str, 
        df: pd.DataFrame
    ) -> int:
        """
        Сохранить рассчитанные YTM из цен свечей
        
        Args:
            isin: ISIN облигации
            interval: Интервал ('1', '10', '60')
            df: DataFrame с колонками: close (price), ytm_close, accrued_interest
            
        Returns:
            Количество сохранённых записей
        """
        if df.empty:
            return 0
        
        conn = get_connection()
        cursor = conn.cursor()
        
        saved_count = 0
        
        for idx, row in df.iterrows():
            try:
                if isinstance(idx, pd.Timestamp):
                    dt_str = idx.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    dt_str = str(idx)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO intraday_ytm 
                    (isin, interval, datetime, price_close, ytm, accrued_interest)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    isin,
                    interval,
                    dt_str,
                    row.get('close'),
                    row.get('ytm_close'),
                    row.get('accrued_interest')
                ))
                saved_count += 1
                
            except Exception as e:
                logger.warning(f"Ошибка сохранения intraday YTM {dt_str}: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Сохранено {saved_count} intraday YTM для {isin} (interval={interval})")
        return saved_count
    
    def load_intraday_ytm(
        self,
        isin: str,
        interval: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        Загрузить рассчитанные YTM из БД
        
        Args:
            isin: ISIN облигации
            interval: Интервал
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            DataFrame с YTM
        """
        conn = get_connection()
        
        query = '''
            SELECT datetime, price_close, ytm, accrued_interest
            FROM intraday_ytm
            WHERE isin = ? AND interval = ?
        '''
        params = [isin, interval]
        
        if start_date:
            query += ' AND datetime >= ?'
            params.append(start_date.strftime('%Y-%m-%d'))
        
        if end_date:
            query += ' AND datetime <= ?'
            params.append(end_date.strftime('%Y-%m-%d 23:59:59'))
        
        query += ' ORDER BY datetime'
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return pd.DataFrame()
        
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
        
        # Для совместимости с текущим кодом
        df['close'] = df['price_close']
        df['ytm_close'] = df['ytm']
        
        return df
    
    def get_last_intraday_ytm_datetime(
        self,
        isin: str,
        interval: str
    ) -> Optional[datetime]:
        """Получить datetime последнего рассчитанного YTM"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT MAX(datetime) as last_dt
            FROM intraday_ytm
            WHERE isin = ? AND interval = ?
        ''', (isin, interval))
        
        row = cursor.fetchone()
        conn.close()
        
        if row and row['last_dt']:
            return datetime.strptime(row['last_dt'], '%Y-%m-%d %H:%M:%S')
        return None
    
    # ==========================================
    # СПРЕДЫ
    # ==========================================
    
    def save_spread(
        self,
        isin_1: str,
        isin_2: str,
        mode: str,
        datetime_val: str,
        ytm_1: float,
        ytm_2: float,
        spread_bp: float,
        signal: str = None,
        interval: str = None,
        p25: float = None,
        p75: float = None
    ) -> int:
        """Сохранить спред"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO spreads 
            (isin_1, isin_2, mode, interval, datetime, ytm_1, ytm_2, spread_bp, signal, p25, p75)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (isin_1, isin_2, mode, interval, datetime_val, ytm_1, ytm_2, spread_bp, signal, p25, p75))
        
        spread_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return spread_id
    
    def save_spreads_batch(
        self,
        isin_1: str,
        isin_2: str,
        mode: str,
        df: pd.DataFrame,
        interval: str = None
    ) -> int:
        """
        Сохранить спреды пакетом
        
        Args:
            isin_1, isin_2: ISIN облигаций
            mode: 'daily' или 'intraday'
            df: DataFrame с колонками: datetime/date, ytm_1, ytm_2, spread_bp, signal
            interval: Интервал (для intraday)
            
        Returns:
            Количество сохранённых записей
        """
        if df.empty:
            return 0
        
        conn = get_connection()
        cursor = conn.cursor()
        
        saved_count = 0
        
        for idx, row in df.iterrows():
            try:
                # datetime
                if 'datetime' in df.columns:
                    dt_val = row['datetime']
                elif isinstance(idx, pd.Timestamp):
                    dt_val = idx
                else:
                    dt_val = row.get('date', idx)
                
                if isinstance(dt_val, pd.Timestamp):
                    dt_str = dt_val.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(dt_val, datetime):
                    dt_str = dt_val.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    dt_str = str(dt_val)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO spreads 
                    (isin_1, isin_2, mode, interval, datetime, ytm_1, ytm_2, spread_bp, signal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    isin_1, isin_2, mode, interval, dt_str,
                    row.get('ytm_1'), row.get('ytm_2'),
                    row.get('spread'), row.get('signal')
                ))
                saved_count += 1
                
            except Exception as e:
                logger.warning(f"Ошибка сохранения спреда: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Сохранено {saved_count} спредов для {isin_1}/{isin_2} ({mode})")
        return saved_count
    
    def load_spreads(
        self,
        isin_1: str,
        isin_2: str,
        mode: str,
        interval: str = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """Загрузить спреды из БД"""
        conn = get_connection()
        
        query = '''
            SELECT datetime, ytm_1, ytm_2, spread_bp, signal, p25, p75
            FROM spreads
            WHERE isin_1 = ? AND isin_2 = ? AND mode = ?
        '''
        params = [isin_1, isin_2, mode]
        
        if interval:
            query += ' AND interval = ?'
            params.append(interval)
        
        if start_date:
            query += ' AND datetime >= ?'
            params.append(start_date.strftime('%Y-%m-%d'))
        
        if end_date:
            query += ' AND datetime <= ?'
            params.append(end_date.strftime('%Y-%m-%d 23:59:59'))
        
        query += ' ORDER BY datetime'
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return pd.DataFrame()
        
        # Используем format='mixed' для разных форматов datetime
        df['datetime'] = pd.to_datetime(df['datetime'], format='mixed')
        df = df.set_index('datetime')
        
        # Для совместимости
        df['spread'] = df['spread_bp']
        
        return df
    
    # ==========================================
    # СВЕЧИ (оставляем для обратной совместимости)
    # ==========================================
    
    def save_candles(
        self, 
        isin: str, 
        interval: str, 
        df: pd.DataFrame
    ) -> int:
        """Сохранить свечи в БД"""
        if df.empty:
            return 0
        
        conn = get_connection()
        cursor = conn.cursor()
        
        saved_count = 0
        
        for idx, row in df.iterrows():
            try:
                if isinstance(idx, pd.Timestamp):
                    dt_str = idx.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    dt_str = str(idx)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO candles 
                    (isin, interval, datetime, open, high, low, close, volume, 
                     ytm_open, ytm_high, ytm_low, ytm_close)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    isin, interval, dt_str,
                    row.get('open'), row.get('high'), row.get('low'),
                    row.get('close'), row.get('volume'),
                    row.get('ytm_open'), row.get('ytm_high'),
                    row.get('ytm_low'), row.get('ytm_close')
                ))
                saved_count += 1
                
            except Exception as e:
                logger.warning(f"Ошибка сохранения свечи {dt_str}: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Сохранено {saved_count} свечей для {isin} (interval={interval})")
        return saved_count
    
    def load_candles(
        self,
        isin: str,
        interval: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """Загрузить свечи из БД"""
        conn = get_connection()
        
        query = '''
            SELECT datetime, open, high, low, close, volume,
                   ytm_open, ytm_high, ytm_low, ytm_close
            FROM candles
            WHERE isin = ? AND interval = ?
        '''
        params = [isin, interval]
        
        if start_date:
            query += ' AND datetime >= ?'
            params.append(start_date.strftime('%Y-%m-%d'))
        
        if end_date:
            query += ' AND datetime <= ?'
            params.append(end_date.strftime('%Y-%m-%d 23:59:59'))
        
        query += ' ORDER BY datetime'
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return pd.DataFrame()
        
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
        
        return df
    
    def get_last_candle_datetime(
        self,
        isin: str,
        interval: str
    ) -> Optional[datetime]:
        """Получить дату/время последней свечи в БД"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT MAX(datetime) as last_dt
            FROM candles
            WHERE isin = ? AND interval = ?
        ''', (isin, interval))
        
        row = cursor.fetchone()
        conn.close()
        
        if row and row['last_dt']:
            return datetime.strptime(row['last_dt'], '%Y-%m-%d %H:%M:%S')
        return None
    
    def get_candles_count(
        self,
        isin: str,
        interval: str
    ) -> int:
        """Получить количество свечей в БД"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as cnt
            FROM candles
            WHERE isin = ? AND interval = ?
        ''', (isin, interval))
        
        row = cursor.fetchone()
        conn.close()
        
        return row['cnt'] if row else 0
    
    # ==========================================
    # СНИМКИ (SNAPSHOTS)
    # ==========================================
    
    def save_snapshot(
        self,
        isin_1: str,
        isin_2: str,
        interval: str,
        ytm_1: float,
        ytm_2: float,
        spread_bp: float,
        signal: str,
        price_1: float = None,
        price_2: float = None,
        p25: float = None,
        p75: float = None
    ) -> int:
        """Сохранить снимок состояния"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO snapshots 
            (isin_1, isin_2, interval, ytm_1, ytm_2, price_1, price_2, 
             spread_bp, signal, p25, p75)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (isin_1, isin_2, interval, ytm_1, ytm_2, price_1, price_2,
              spread_bp, signal, p25, p75))
        
        snapshot_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return snapshot_id
    
    def load_snapshots(
        self,
        isin_1: str,
        isin_2: str,
        interval: str,
        hours: int = 24
    ) -> pd.DataFrame:
        """Загрузить снимки за последние N часов"""
        conn = get_connection()
        
        since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        
        query = '''
            SELECT * FROM snapshots
            WHERE isin_1 = ? AND isin_2 = ? AND interval = ?
            AND timestamp >= ?
            ORDER BY timestamp
        '''
        
        df = pd.read_sql_query(query, conn, params=[isin_1, isin_2, interval, since])
        conn.close()
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        return df
    
    # ==========================================
    # ОБЛИГАЦИИ
    # ==========================================

    def save_bond(self, bond_data: Dict) -> bool:
        """
        Сохранить информацию об облигации

        Args:
            bond_data: Словарь с данными облигации
                - isin (обязательно)
                - name, short_name
                - coupon_rate, maturity_date, issue_date
                - face_value, coupon_frequency, day_count
                - is_favorite (0 или 1)
                - last_price, last_ytm
                - duration_years, duration_days
                - last_trade_date

        Returns:
            True если успешно
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO bonds
                (isin, name, short_name, coupon_rate, maturity_date, issue_date,
                 face_value, coupon_frequency, day_count, is_favorite,
                 last_price, last_ytm, duration_years, duration_days,
                 last_trade_date, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                bond_data.get('isin'),
                bond_data.get('name'),
                bond_data.get('short_name'),
                bond_data.get('coupon_rate'),
                bond_data.get('maturity_date'),
                bond_data.get('issue_date'),
                bond_data.get('face_value', 1000),
                bond_data.get('coupon_frequency', 2),
                bond_data.get('day_count', 'ACT/ACT'),
                bond_data.get('is_favorite', 0),
                bond_data.get('last_price'),
                bond_data.get('last_ytm'),
                bond_data.get('duration_years'),
                bond_data.get('duration_days'),
                bond_data.get('last_trade_date'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            conn.commit()
            logger.debug(f"Сохранена облигация {bond_data.get('isin')}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения облигации: {e}")
            return False
        finally:
            conn.close()

    def load_bond(self, isin: str) -> Optional[Dict]:
        """Загрузить информацию об облигации"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM bonds WHERE isin = ?', (isin,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_all_bonds(self) -> List[Dict]:
        """Получить список всех облигаций из БД"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM bonds
            ORDER BY is_favorite DESC, duration_years
        ''')
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_favorite_bonds(self) -> List[Dict]:
        """Получить список избранных облигаций"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM bonds
            WHERE is_favorite = 1
            ORDER BY duration_years
        ''')
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def set_favorite(self, isin: str, is_favorite: bool = True) -> bool:
        """
        Установить/снять флаг избранного

        Args:
            isin: ISIN облигации
            is_favorite: True = избранное, False = не избранное

        Returns:
            True если успешно
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE bonds
                SET is_favorite = ?, last_updated = ?
                WHERE isin = ?
            ''', (1 if is_favorite else 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), isin))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка установки is_favorite: {e}")
            return False
        finally:
            conn.close()

    def clear_all_favorites(self) -> int:
        """
        Снять флаг избранного со всех облигаций

        Returns:
            Количество обновлённых записей
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE bonds
                SET is_favorite = 0, last_updated = ?
                WHERE is_favorite = 1
            ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            logger.error(f"Ошибка очистки избранного: {e}")
            return 0
        finally:
            conn.close()

    def update_bond_market_data(
        self,
        isin: str,
        last_price: float = None,
        last_ytm: float = None,
        duration_years: float = None,
        duration_days: float = None,
        last_trade_date: str = None
    ) -> bool:
        """
        Обновить рыночные данные облигации

        Args:
            isin: ISIN облигации
            last_price: Последняя цена
            last_ytm: Последний YTM
            duration_years: Дюрация в годах
            duration_days: Дюрация в днях
            last_trade_date: Дата последних торгов

        Returns:
            True если успешно
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE bonds
                SET last_price = ?, last_ytm = ?, duration_years = ?,
                    duration_days = ?, last_trade_date = ?, last_updated = ?
                WHERE isin = ?
            ''', (
                last_price, last_ytm, duration_years, duration_days,
                last_trade_date,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                isin
            ))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка обновления рыночных данных: {e}")
            return False
        finally:
            conn.close()

    def delete_bond(self, isin: str) -> bool:
        """Удалить облигацию из БД"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM bonds WHERE isin = ?', (isin,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка удаления облигации: {e}")
            return False
        finally:
            conn.close()

    def get_bonds_count(self) -> int:
        """Получить количество облигаций в БД"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) as cnt FROM bonds')
        row = cursor.fetchone()
        conn.close()

        return row['cnt'] if row else 0

    def migrate_config_bonds(self, bonds_config: Dict[str, Any]) -> int:
        """
        Миграция облигаций из config.py в БД при первом запуске

        Args:
            bonds_config: Словарь облигаций из config.py (AppConfig.bonds)

        Returns:
            Количество мигрированных облигаций
        """
        # Проверяем есть ли уже облигации
        if self.get_bonds_count() > 0:
            logger.info("Облигации уже есть в БД, миграция не нужна")
            return 0

        migrated = 0

        for isin, bond in bonds_config.items():
            try:
                self.save_bond({
                    'isin': isin,
                    'name': getattr(bond, 'name', ''),
                    'short_name': getattr(bond, 'name', ''),
                    'coupon_rate': getattr(bond, 'coupon_rate', None),
                    'maturity_date': getattr(bond, 'maturity_date', None),
                    'issue_date': getattr(bond, 'issue_date', None),
                    'face_value': getattr(bond, 'face_value', 1000),
                    'coupon_frequency': getattr(bond, 'coupon_frequency', 2),
                    'day_count': getattr(bond, 'day_count_convention', 'ACT/ACT'),
                    'is_favorite': 1,  # Все облигации из config - избранное
                })
                migrated += 1
            except Exception as e:
                logger.error(f"Ошибка миграции облигации {isin}: {e}")

        logger.info(f"Мигрировано {migrated} облигаций из config.py")
        return migrated

    def get_favorite_bonds_as_config(self) -> Dict[str, Any]:
        """
        Получить избранные облигации в формате, совместимом с config.py

        Returns:
            Словарь {ISIN: BondConfig-like dict}
        """
        favorites = self.get_favorite_bonds()

        result = {}
        for bond in favorites:
            isin = bond['isin']
            result[isin] = {
                'isin': isin,
                'name': bond.get('name') or bond.get('short_name') or isin,
                'short_name': bond.get('short_name') or isin,
                'maturity_date': bond.get('maturity_date', ''),
                'coupon_rate': bond.get('coupon_rate'),
                'face_value': bond.get('face_value', 1000),
                'coupon_frequency': bond.get('coupon_frequency', 2),
                'issue_date': bond.get('issue_date', ''),
                'day_count_convention': bond.get('day_count', 'ACT/ACT'),
            }

        return result
    
    # ==========================================
    # СТАТИСТИКА
    # ==========================================
    
    def get_stats(self) -> Dict:
        """Получить статистику БД"""
        conn = get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Количество записей в таблицах
        cursor.execute('SELECT COUNT(*) as cnt FROM bonds')
        stats['bonds_count'] = cursor.fetchone()['cnt']
        
        cursor.execute('SELECT COUNT(*) as cnt FROM candles')
        stats['candles_count'] = cursor.fetchone()['cnt']
        
        cursor.execute('SELECT COUNT(*) as cnt FROM daily_ytm')
        stats['daily_ytm_count'] = cursor.fetchone()['cnt']
        
        cursor.execute('SELECT COUNT(*) as cnt FROM intraday_ytm')
        stats['intraday_ytm_count'] = cursor.fetchone()['cnt']
        
        cursor.execute('SELECT COUNT(*) as cnt FROM spreads')
        stats['spreads_count'] = cursor.fetchone()['cnt']
        
        cursor.execute('SELECT COUNT(*) as cnt FROM snapshots')
        stats['snapshots_count'] = cursor.fetchone()['cnt']
        
        # Свечи по интервалам
        cursor.execute('''
            SELECT interval, COUNT(*) as cnt 
            FROM candles 
            GROUP BY interval
        ''')
        stats['candles_by_interval'] = {row['interval']: row['cnt'] for row in cursor.fetchall()}
        
        # Intraday YTM по интервалам
        cursor.execute('''
            SELECT interval, COUNT(*) as cnt 
            FROM intraday_ytm 
            GROUP BY interval
        ''')
        stats['intraday_by_interval'] = {row['interval']: row['cnt'] for row in cursor.fetchall()}
        
        # Спреды по режимам
        cursor.execute('''
            SELECT mode, COUNT(*) as cnt 
            FROM spreads 
            GROUP BY mode
        ''')
        stats['spreads_by_mode'] = {row['mode']: row['cnt'] for row in cursor.fetchall()}
        
        # Последние данные
        cursor.execute('SELECT MAX(date) as last_dt FROM daily_ytm')
        row = cursor.fetchone()
        stats['last_daily_ytm'] = row['last_dt'] if row else None
        
        cursor.execute('SELECT MAX(datetime) as last_dt FROM intraday_ytm')
        row = cursor.fetchone()
        stats['last_intraday_ytm'] = row['last_dt'] if row else None
        
        conn.close()
        
        return stats
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> int:
        """Удалить старые данные"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cutoff = (date.today() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
        
        total_deleted = 0
        
        # Удаляем старые свечи
        cursor.execute('DELETE FROM candles WHERE datetime < ?', (cutoff,))
        total_deleted += cursor.rowcount
        
        # Удаляем старые дневные YTM
        cursor.execute('DELETE FROM daily_ytm WHERE date < ?', (cutoff,))
        total_deleted += cursor.rowcount
        
        # Удаляем старые intraday YTM
        cursor.execute('DELETE FROM intraday_ytm WHERE datetime < ?', (cutoff,))
        total_deleted += cursor.rowcount
        
        # Удаляем старые спреды
        cursor.execute('DELETE FROM spreads WHERE datetime < ?', (cutoff,))
        total_deleted += cursor.rowcount
        
        # Удаляем старые снимки
        cursor.execute('DELETE FROM snapshots WHERE timestamp < ?', (cutoff,))
        total_deleted += cursor.rowcount
        
        conn.commit()
        conn.close()
        
        logger.info(f"Удалено {total_deleted} старых записей")
        return total_deleted
    
    def vacuum(self):
        """Оптимизировать БД (VACUUM)"""
        conn = get_connection()
        conn.execute('VACUUM')
        conn.close()
        logger.info("VACUUM выполнен")
    
    # ==========================================
    # ПОЛНОЕ ОБНОВЛЕНИЕ
    # ==========================================
    
    def clear_all_data(self):
        """Очистить все данные (кроме облигаций)"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM candles')
        cursor.execute('DELETE FROM daily_ytm')
        cursor.execute('DELETE FROM intraday_ytm')
        cursor.execute('DELETE FROM spreads')
        cursor.execute('DELETE FROM snapshots')
        cursor.execute('DELETE FROM update_log')
        
        conn.commit()
        conn.close()
        
        logger.info("Все данные очищены")


# ==========================================
# УДОБНЫЕ ФУНКЦИИ
# ==========================================

_db_manager = None

def get_db() -> DatabaseManager:
    """Получить singleton менеджер БД"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


# ==========================================
# ФУНКЦИИ СОВМЕСТИМОСТИ (из data_storage.py)
# ==========================================

def save_intraday_snapshot(
    bond1_data: Dict[str, Any],
    bond2_data: Dict[str, Any],
    spread_data: Dict[str, Any],
    interval: str
) -> int:
    """
    Сохранить снимок intraday данных (для совместимости)
    
    Args:
        bond1_data: Данные облигации 1 {isin, ytm, price, name}
        bond2_data: Данные облигации 2
        spread_data: Данные спреда {spread_bp, signal, p25, p75}
        interval: Интервал свечей
        
    Returns:
        ID снимка
    """
    db = get_db()
    
    return db.save_snapshot(
        isin_1=bond1_data.get('isin'),
        isin_2=bond2_data.get('isin'),
        interval=interval,
        ytm_1=bond1_data.get('ytm'),
        ytm_2=bond2_data.get('ytm'),
        price_1=bond1_data.get('price'),
        price_2=bond2_data.get('price'),
        spread_bp=spread_data.get('spread_bp'),
        signal=spread_data.get('signal'),
        p25=spread_data.get('p25'),
        p75=spread_data.get('p75')
    )


def load_intraday_history(
    isin_1: str = None,
    isin_2: str = None,
    interval: str = '60',
    hours: int = 168
) -> pd.DataFrame:
    """
    Загрузить историю intraday данных (для совместимости)
    
    Args:
        isin_1: ISIN облигации 1 (опционально)
        isin_2: ISIN облигации 2 (опционально)
        interval: Интервал
        hours: Количество часов
        
    Returns:
        DataFrame с историей
    """
    db = get_db()
    
    if isin_1 and isin_2:
        return db.load_snapshots(isin_1, isin_2, interval, hours=hours)
    
    # Если ISIN не указаны, загружаем все снимки
    conn = get_connection()
    
    since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    
    query = '''
        SELECT * FROM snapshots
        WHERE interval = ? AND timestamp >= ?
        ORDER BY timestamp
    '''
    
    df = pd.read_sql_query(query, conn, params=[interval, since])
    conn.close()
    
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
    
    return df


def get_saved_data_info() -> Dict[str, Any]:
    """
    Получить информацию о сохранённых данных (для совместимости)
    
    Returns:
        Словарь с информацией
    """
    db = get_db()
    stats = db.get_stats()
    
    return {
        'total_files': (
            stats.get('candles_count', 0) + 
            stats.get('daily_ytm_count', 0) + 
            stats.get('intraday_ytm_count', 0) +
            stats.get('spreads_count', 0) +
            stats.get('snapshots_count', 0)
        ),
        'snapshots': [{'count': stats.get('snapshots_count', 0)}],
        'candles': [{'count': stats.get('candles_count', 0)}],
        'oldest': None,
        'newest': stats.get('last_daily_ytm') or stats.get('last_intraday_ytm')
    }


def init_session_storage(st_session_state):
    """Инициализировать хранилище в session state"""
    if 'saved_snapshots' not in st_session_state:
        st_session_state.saved_snapshots = []
    
    if 'last_save_time' not in st_session_state:
        st_session_state.last_save_time = None


def should_save(st_session_state, interval_seconds: int = 60) -> bool:
    """
    Проверить нужно ли сохранять данные
    
    Args:
        st_session_state: Streamlit session state
        interval_seconds: Минимальный интервал между сохранениями
        
    Returns:
        True если нужно сохранить
    """
    if st_session_state.last_save_time is None:
        return True
    
    elapsed = (datetime.now() - st_session_state.last_save_time).total_seconds()
    return elapsed >= interval_seconds


def cleanup_old_data(days_to_keep: int = 90) -> int:
    """
    Удалить старые данные (для совместимости)
    
    Args:
        days_to_keep: Количество дней для хранения
        
    Returns:
        Количество удалённых записей
    """
    db = get_db()
    return db.cleanup_old_data(days_to_keep)
