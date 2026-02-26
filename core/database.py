"""
SQLite база данных для хранения исторических данных ОФЗ
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
    
    # Таблица облигаций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bonds (
            isin TEXT PRIMARY KEY,
            name TEXT,
            coupon_rate REAL,
            maturity_date TEXT,
            face_value REAL DEFAULT 1000,
            coupon_frequency INTEGER DEFAULT 2,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица свечей
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
    
    # Индекс для быстрого поиска
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_candles_isin_interval 
        ON candles(isin, interval)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_candles_datetime 
        ON candles(datetime)
    ''')
    
    # Таблица снимков (snapshots)
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
    
    # Таблица метаданных обновлений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS update_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isin TEXT NOT NULL,
            interval TEXT NOT NULL,
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
    # СВЕЧИ
    # ==========================================
    
    def save_candles(
        self, 
        isin: str, 
        interval: str, 
        df: pd.DataFrame
    ) -> int:
        """
        Сохранить свечи в БД
        
        Args:
            isin: ISIN облигации
            interval: Интервал ('1', '10', '60')
            df: DataFrame со свечами (index=datetime, columns=open,high,low,close,volume,ytm_*)
            
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
                # Преобразуем datetime в строку
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
                    isin,
                    interval,
                    dt_str,
                    row.get('open'),
                    row.get('high'),
                    row.get('low'),
                    row.get('close'),
                    row.get('volume'),
                    row.get('ytm_open'),
                    row.get('ytm_high'),
                    row.get('ytm_low'),
                    row.get('ytm_close')
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
        """
        Загрузить свечи из БД
        
        Args:
            isin: ISIN облигации
            interval: Интервал
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            DataFrame со свечами
        """
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
        """
        Получить дату/время последней свечи в БД
        
        Args:
            isin: ISIN облигации
            interval: Интервал
            
        Returns:
            datetime последней свечи или None
        """
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
    
    def save_bond(self, bond_config: Dict) -> bool:
        """Сохранить информацию об облигации"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO bonds 
                (isin, name, coupon_rate, maturity_date, face_value, coupon_frequency)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                bond_config.get('isin'),
                bond_config.get('name'),
                bond_config.get('coupon_rate'),
                bond_config.get('maturity_date'),
                bond_config.get('face_value', 1000),
                bond_config.get('coupon_frequency', 2)
            ))
            conn.commit()
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
    
    # ==========================================
    # ЛОГ ОБНОВЛЕНИЙ
    # ==========================================
    
    def log_update(
        self,
        isin: str,
        interval: str,
        last_datetime: str,
        records_added: int
    ):
        """Записать информацию об обновлении"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO update_log (isin, interval, last_datetime, records_added)
            VALUES (?, ?, ?, ?)
        ''', (isin, interval, last_datetime, records_added))
        
        conn.commit()
        conn.close()
    
    def get_last_update(self, isin: str, interval: str) -> Optional[Dict]:
        """Получить информацию о последнем обновлении"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM update_log
            WHERE isin = ? AND interval = ?
            ORDER BY updated_at DESC
            LIMIT 1
        ''', (isin, interval))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    # ==========================================
    # СТАТИСТИКА
    # ==========================================
    
    def get_stats(self) -> Dict:
        """Получить статистику БД"""
        conn = get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Количество свечей
        cursor.execute('SELECT COUNT(*) as cnt FROM candles')
        stats['candles_count'] = cursor.fetchone()['cnt']
        
        # Количество снимков
        cursor.execute('SELECT COUNT(*) as cnt FROM snapshots')
        stats['snapshots_count'] = cursor.fetchone()['cnt']
        
        # Количество облигаций
        cursor.execute('SELECT COUNT(*) as cnt FROM bonds')
        stats['bonds_count'] = cursor.fetchone()['cnt']
        
        # Свечи по интервалам
        cursor.execute('''
            SELECT interval, COUNT(*) as cnt 
            FROM candles 
            GROUP BY interval
        ''')
        stats['by_interval'] = {row['interval']: row['cnt'] for row in cursor.fetchall()}
        
        # Последняя свеча
        cursor.execute('SELECT MAX(datetime) as last_dt FROM candles')
        row = cursor.fetchone()
        stats['last_candle'] = row['last_dt'] if row else None
        
        conn.close()
        
        return stats
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> int:
        """Удалить старые данные"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cutoff = (date.today() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
        
        # Удаляем старые свечи
        cursor.execute('DELETE FROM candles WHERE datetime < ?', (cutoff,))
        candles_deleted = cursor.rowcount
        
        # Удаляем старые снимки
        cursor.execute('DELETE FROM snapshots WHERE timestamp < ?', (cutoff,))
        snapshots_deleted = cursor.rowcount
        
        # Удаляем старые логи
        cursor.execute('DELETE FROM update_log WHERE updated_at < ?', (cutoff,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Удалено: {candles_deleted} свечей, {snapshots_deleted} снимков")
        return candles_deleted + snapshots_deleted
    
    def vacuum(self):
        """Оптимизировать БД (VACUUM)"""
        conn = get_connection()
        conn.execute('VACUUM')
        conn.close()
        logger.info("VACUUM выполнен")


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
