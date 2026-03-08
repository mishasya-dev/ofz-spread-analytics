"""
Репозиторий для работы с G-spread и параметрами Nelson-Siegel

Таблицы:
- ns_params: параметры Nelson-Siegel (КБД)
- g_spreads: рассчитанный G-spread по облигациям
"""
from typing import Optional, Dict, List
from datetime import date, datetime
import pandas as pd
import logging

from .connection import get_connection

logger = logging.getLogger(__name__)


class GSpreadRepository:
    """Репозиторий для работы с G-spread и параметрами NS"""
    
    # ==========================================
    # ПАРАМЕТРЫ NELSON-SIEGEL
    # ==========================================
    
    def save_ns_params(self, df: pd.DataFrame) -> int:
        """
        Сохранить параметры Nelson-Siegel в БД
        
        Args:
            df: DataFrame с колонками: b1, b2, b3, t1
                индекс = date
                
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
                    date_str = idx.strftime('%Y-%m-%d')
                else:
                    date_str = str(idx)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO ns_params 
                    (date, b1, b2, b3, t1)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    date_str,
                    float(row['b1']) if pd.notna(row['b1']) else None,
                    float(row['b2']) if pd.notna(row['b2']) else None,
                    float(row['b3']) if pd.notna(row['b3']) else None,
                    float(row['t1']) if pd.notna(row['t1']) else None
                ))
                saved_count += 1
                
            except Exception as e:
                logger.warning(f"Ошибка сохранения NS params {date_str}: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Сохранено {saved_count} параметров Nelson-Siegel")
        return saved_count
    
    def load_ns_params(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        Загрузить параметры Nelson-Siegel из БД
        
        Args:
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            DataFrame с колонками: b1, b2, b3, t1
        """
        conn = get_connection()
        
        query = '''
            SELECT date, b1, b2, b3, t1
            FROM ns_params
            WHERE 1=1
        '''
        params = []
        
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
    
    def get_last_ns_params_date(self) -> Optional[date]:
        """Получить дату последних параметров NS в БД"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT MAX(date) as last_date
            FROM ns_params
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if row and row['last_date']:
            return datetime.strptime(row['last_date'], '%Y-%m-%d').date()
        return None
    
    def get_ns_params_for_date(self, target_date: date) -> Optional[Dict]:
        """
        Получить параметры NS на конкретную дату
        
        Args:
            target_date: Дата
            
        Returns:
            Словарь {b1, b2, b3, t1} или None
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT b1, b2, b3, t1 FROM ns_params
            WHERE date = ?
        ''', (target_date.strftime('%Y-%m-%d'),))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'b1': row['b1'],
                'b2': row['b2'],
                'b3': row['b3'],
                't1': row['t1']
            }
        return None
    
    def count_ns_params(self) -> int:
        """Количество записей параметров NS"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as cnt FROM ns_params')
        row = cursor.fetchone()
        conn.close()
        
        return row['cnt'] if row else 0
    
    # ==========================================
    # G-SPREAD
    # ==========================================
    
    def save_g_spreads(self, isin: str, df: pd.DataFrame) -> int:
        """
        Сохранить рассчитанные G-spread для облигации
        
        Args:
            isin: ISIN облигации
            df: DataFrame с колонками: ytm_bond, duration_years, ytm_kbd, g_spread_bp
                индекс = date
                
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
                    date_str = idx.strftime('%Y-%m-%d')
                else:
                    date_str = str(idx)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO g_spreads 
                    (isin, date, ytm_bond, duration_years, ytm_kbd, g_spread_bp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    isin,
                    date_str,
                    float(row['ytm_bond']) if pd.notna(row['ytm_bond']) else None,
                    float(row['duration_years']) if pd.notna(row['duration_years']) else None,
                    float(row['ytm_kbd']) if pd.notna(row['ytm_kbd']) else None,
                    float(row['g_spread_bp']) if pd.notna(row['g_spread_bp']) else None
                ))
                saved_count += 1
                
            except Exception as e:
                logger.warning(f"Ошибка сохранения G-spread {date_str}: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Сохранено {saved_count} G-spread для {isin}")
        return saved_count
    
    def load_g_spreads(
        self,
        isin: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        Загрузить G-sread для облигации
        
        Args:
            isin: ISIN облигации
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            DataFrame с G-spread
        """
        conn = get_connection()
        
        query = '''
            SELECT date, ytm_bond, duration_years, ytm_kbd, g_spread_bp
            FROM g_spreads
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
    
    def get_last_g_spread_date(self, isin: str) -> Optional[date]:
        """Получить дату последнего G-spread для облигации"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT MAX(date) as last_date
            FROM g_spreads
            WHERE isin = ?
        ''', (isin,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row and row['last_date']:
            return datetime.strptime(row['last_date'], '%Y-%m-%d').date()
        return None
    
    def get_g_spread_for_date(
        self,
        isin: str,
        target_date: date
    ) -> Optional[Dict]:
        """
        Получить G-spread на конкретную дату
        
        Args:
            isin: ISIN облигации
            target_date: Дата
            
        Returns:
            Словарь с данными или None
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ytm_bond, duration_years, ytm_kbd, g_spread_bp
            FROM g_spreads
            WHERE isin = ? AND date = ?
        ''', (isin, target_date.strftime('%Y-%m-%d')))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'ytm_bond': row['ytm_bond'],
                'duration_years': row['duration_years'],
                'ytm_kbd': row['ytm_kbd'],
                'g_spread_bp': row['g_spread_bp']
            }
        return None
    
    def count_g_spreads(self, isin: str = None) -> int:
        """Количество записей G-spread"""
        conn = get_connection()
        cursor = conn.cursor()
        
        if isin:
            cursor.execute('SELECT COUNT(*) as cnt FROM g_spreads WHERE isin = ?', (isin,))
        else:
            cursor.execute('SELECT COUNT(*) as cnt FROM g_spreads')
        
        row = cursor.fetchone()
        conn.close()
        
        return row['cnt'] if row else 0
    
    def delete_g_spreads(self, isin: str) -> int:
        """Удалить G-spread для облигации"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM g_spreads WHERE isin = ?', (isin,))
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        logger.info(f"Удалено {deleted} G-spread для {isin}")
        return deleted
    
    # ==========================================
    # СТАТИСТИКА
    # ==========================================
    
    def get_stats(self) -> Dict:
        """Получить статистику по таблицам G-spread"""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Параметры NS
        cursor.execute('SELECT COUNT(*) as cnt FROM ns_params')
        ns_count = cursor.fetchone()['cnt']
        
        # G-spreads
        cursor.execute('SELECT COUNT(*) as cnt FROM g_spreads')
        gs_count = cursor.fetchone()['cnt']
        
        # G-spreads по облигациям
        cursor.execute('''
            SELECT isin, COUNT(*) as cnt
            FROM g_spreads
            GROUP BY isin
        ''')
        by_isin = {row['isin']: row['cnt'] for row in cursor.fetchall()}
        
        # Диапазон дат NS
        cursor.execute('SELECT MIN(date) as min_d, MAX(date) as max_d FROM ns_params')
        ns_range = cursor.fetchone()
        
        conn.close()
        
        return {
            'ns_params_count': ns_count,
            'g_spreads_count': gs_count,
            'g_spreads_by_isin': by_isin,
            'ns_params_date_range': (
                ns_range['min_d'] if ns_range else None,
                ns_range['max_d'] if ns_range else None
            )
        }
