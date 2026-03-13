"""
Репозиторий спредов

Содержит операции для работы со спредами между облигациями.
Использует контекстный менеджер для безопасной работы с БД.
"""
from typing import Optional, Dict
from datetime import date, datetime
import pandas as pd
import logging

from .connection import get_db_connection, get_db_cursor

logger = logging.getLogger(__name__)


class SpreadsRepository:
    """Репозиторий для работы со спредами"""
    
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
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO spreads 
                (isin_1, isin_2, mode, interval, datetime, ytm_1, ytm_2, spread_bp, signal, p25, p75)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (isin_1, isin_2, mode, interval, datetime_val, ytm_1, ytm_2, spread_bp, signal, p25, p75))
            spread_id = cursor.lastrowid

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

        saved_count = 0

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

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

            logger.info(f"Сохранено {saved_count} спредов для {isin_1}/{isin_2} ({mode})")
            return saved_count
            
        except Exception as e:
            logger.error(f"Ошибка пакетного сохранения спредов: {e}")
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

        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        if df.empty:
            return pd.DataFrame()

        # Используем format='mixed' для разных форматов datetime
        df['datetime'] = pd.to_datetime(df['datetime'], format='mixed')
        df = df.set_index('datetime')

        # Для совместимости
        df['spread'] = df['spread_bp']

        return df

    def count_spreads(self) -> int:
        """Количество записей спредов"""
        with get_db_cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as cnt FROM spreads')
            row = cursor.fetchone()

        return row['cnt'] if row else 0

    def count_by_mode(self) -> Dict[str, int]:
        """Количество записей по режимам"""
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT mode, COUNT(*) as cnt 
                FROM spreads 
                GROUP BY mode
            ''')
            rows = cursor.fetchall()

        return {row['mode']: row['cnt'] for row in rows}
