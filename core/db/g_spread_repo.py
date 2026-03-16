"""
Репозиторий для работы с G-spread и параметрами Nelson-Siegel

Таблицы:
- ns_params: параметры Nelson-Siegel (КБД)
- g_spreads: рассчитанный G-spread по облигациям
Использует контекстный менеджер для безопасной работы с БД.
"""
from typing import Optional, Dict, List
from datetime import date, datetime
import pandas as pd
import logging

from .connection import get_db_connection, get_db_cursor

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
        
        saved_count = 0
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
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
            
            logger.info(f"Сохранено {saved_count} параметров Nelson-Siegel")
            return saved_count
            
        except Exception as e:
            logger.error(f"Ошибка сохранения NS params: {e}")
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
        
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        if df.empty:
            return pd.DataFrame()
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        return df
    
    def get_last_ns_params_date(self) -> Optional[date]:
        """Получить дату последних параметров NS в БД"""
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT MAX(date) as last_date
                FROM ns_params
            ''')
            row = cursor.fetchone()
        
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
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT b1, b2, b3, t1 FROM ns_params
                WHERE date = ?
            ''', (target_date.strftime('%Y-%m-%d'),))
            row = cursor.fetchone()
        
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
        with get_db_cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as cnt FROM ns_params')
            row = cursor.fetchone()
        
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
        
        saved_count = 0
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
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
                            float(row['ytm_bond']) if pd.notna(row.get('ytm_bond')) else None,
                            float(row['duration_years']) if pd.notna(row.get('duration_years')) else None,
                            float(row['ytm_kbd']) if pd.notna(row.get('ytm_kbd')) else None,
                            float(row['g_spread_bp']) if pd.notna(row.get('g_spread_bp')) else None
                        ))
                        saved_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Ошибка сохранения G-spread {date_str}: {e}")
            
            logger.info(f"Сохранено {saved_count} G-spread для {isin}")
            return saved_count
            
        except Exception as e:
            logger.error(f"Ошибка сохранения G-spread: {e}")
            return saved_count
    
    def load_g_spreads(
        self,
        isin: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        Загрузить G-spread для облигации из БД
        
        Args:
            isin: ISIN облигации
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            DataFrame с G-spread
        """
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
        
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        if df.empty:
            return pd.DataFrame()
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        return df
    
    def get_last_g_spread_date(self, isin: str) -> Optional[date]:
        """Получить дату последнего G-spread в БД для облигации"""
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT MAX(date) as last_date
                FROM g_spreads
                WHERE isin = ?
            ''', (isin,))
            row = cursor.fetchone()
        
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
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT ytm_bond, duration_years, ytm_kbd, g_spread_bp
                FROM g_spreads
                WHERE isin = ? AND date = ?
            ''', (isin, target_date.strftime('%Y-%m-%d')))
            row = cursor.fetchone()
        
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
        with get_db_cursor() as cursor:
            if isin:
                cursor.execute('SELECT COUNT(*) as cnt FROM g_spreads WHERE isin = ?', (isin,))
            else:
                cursor.execute('SELECT COUNT(*) as cnt FROM g_spreads')
            row = cursor.fetchone()
        
        return row['cnt'] if row else 0
    
    def delete_g_spreads(self, isin: str) -> int:
        """Удалить G-spread для облигации"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM g_spreads WHERE isin = ?', (isin,))
                deleted = cursor.rowcount
            
            logger.info(f"Удалено {deleted} G-spread для {isin}")
            return deleted
        except Exception as e:
            logger.error(f"Ошибка удаления G-spread: {e}")
            return 0
    
    # ==========================================
    # СТАТИСТИКА
    # ==========================================
    
    def get_stats(self) -> Dict:
        """Получить статистику по таблицам G-spread"""
        with get_db_connection() as conn:
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
            
            # Yearyields
            cursor.execute('SELECT COUNT(*) as cnt FROM yearyields')
            yy_count = cursor.fetchone()['cnt']
            
            cursor.execute('SELECT MIN(date) as min_d, MAX(date) as max_d FROM yearyields')
            yy_range = cursor.fetchone()
        
        return {
            'ns_params_count': ns_count,
            'g_spreads_count': gs_count,
            'g_spreads_by_isin': by_isin,
            'ns_params_date_range': (
                ns_range['min_d'] if ns_range else None,
                ns_range['max_d'] if ns_range else None
            ),
            'yearyields_count': yy_count,
            'yearyields_date_range': (
                yy_range['min_d'] if yy_range else None,
                yy_range['max_d'] if yy_range else None
            )
        }
    
    # ==========================================
    # ZCYC HISTORY RAW (сырые данные ZCYC от MOEX)
    # ==========================================
    
    def save_zcyc(self, df: pd.DataFrame) -> int:
        """
        Сохранить ZCYC данные в кэш
        
        Args:
            df: DataFrame с колонками: date, secid, shortname, trdyield, 
                clcyield, duration_days, g_spread_bp
                
        Returns:
            Количество сохранённых записей
        """
        if df.empty:
            return 0
        
        saved_count = 0
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                for _, row in df.iterrows():
                    try:
                        cursor.execute('''
                            INSERT OR REPLACE INTO zcyc_history_raw 
                            (date, secid, shortname, trdyield, clcyield, duration_days, g_spread_bp)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            str(row['date']) if isinstance(row['date'], str) else row['date'].strftime('%Y-%m-%d'),
                            row.get('secid'),
                            row.get('shortname'),
                            row.get('trdyield'),
                            row.get('clcyield'),
                            row.get('duration_days'),
                            row.get('g_spread_bp')
                        ))
                        saved_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Ошибка сохранения ZCYC: {e}")
            
            logger.info(f"Сохранено {saved_count} записей ZCYC")
            return saved_count
            
        except Exception as e:
            logger.error(f"Ошибка сохранения ZCYC: {e}")
            return saved_count
    
    def load_zcyc(
        self,
        isin: str = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        Загрузить ZCYC данные из кэша
        
        Args:
            isin: ISIN облигации для фильтрации
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            DataFrame с ZCYC данными
        """
        query = '''
            SELECT date, secid, shortname, trdyield, clcyield, duration_days, g_spread_bp
            FROM zcyc_history_raw
            WHERE 1=1
        '''
        params = []
        
        if isin:
            query += ' AND secid = ?'
            params.append(isin)
        
        if start_date:
            query += ' AND date >= ?'
            params.append(start_date.strftime('%Y-%m-%d'))
        
        if end_date:
            query += ' AND date <= ?'
            params.append(end_date.strftime('%Y-%m-%d'))
        
        query += ' ORDER BY date'
        
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        if df.empty:
            return pd.DataFrame()
        
        df['date'] = pd.to_datetime(df['date'])
        
        return df
    
    def get_zcyc_cached_dates(
        self,
        isin: str = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> set:
        """
        Получить множество дат, для которых есть ZCYC данные в кэше
        
        Args:
            isin: ISIN облигации (если None - все даты)
            start_date: Начальная дата (опционально)
            end_date: Конечная дата (опционально)
            
        Returns:
            Множество дат
        """
        query = 'SELECT DISTINCT date FROM zcyc_history_raw WHERE 1=1'
        params = []
        
        if isin:
            query += ' AND secid = ?'
            params.append(isin)
        
        if start_date:
            query += ' AND date >= ?'
            params.append(start_date.strftime('%Y-%m-%d'))
        
        if end_date:
            query += ' AND date <= ?'
            params.append(end_date.strftime('%Y-%m-%d'))
        
        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        
        return {datetime.strptime(row['date'], '%Y-%m-%d').date() for row in rows}
    
    def count_zcyc(self, isin: str = None) -> int:
        """Количество записей ZCYC в кэше"""
        with get_db_cursor() as cursor:
            if isin:
                cursor.execute('SELECT COUNT(*) as cnt FROM zcyc_history_raw WHERE secid = ?', (isin,))
            else:
                cursor.execute('SELECT COUNT(*) as cnt FROM zcyc_history_raw')
            row = cursor.fetchone()
        
        return row['cnt'] if row else 0
    
    def get_zcyc_date_range(self, isin: str = None) -> tuple:
        """Получить диапазон дат ZCYC в кэше"""
        with get_db_cursor() as cursor:
            if isin:
                cursor.execute(
                    'SELECT MIN(date) as min_d, MAX(date) as max_d FROM zcyc_history_raw WHERE secid = ?',
                    (isin,)
                )
            else:
                cursor.execute('SELECT MIN(date) as min_d, MAX(date) as max_d FROM zcyc_history_raw')
            
            row = cursor.fetchone()
        
        if row and row['min_d']:
            return (
                datetime.strptime(row['min_d'], '%Y-%m-%d').date(),
                datetime.strptime(row['max_d'], '%Y-%m-%d').date()
            )
        return (None, None)
    
    # ==========================================
    # ПУСТЫЕ ДАТЫ (праздники, когда нет торгов)
    # ==========================================
    
    def save_empty_date(self, empty_date: date) -> bool:
        """
        Сохранить дату, для которой MOEX вернул пустой ответ
        
        Args:
            empty_date: Дата без торгов (праздник)
            
        Returns:
            True если сохранено
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO zcyc_empty_dates (date)
                    VALUES (?)
                ''', (empty_date.strftime('%Y-%m-%d'),))
            return True
        except Exception as e:
            logger.warning(f"Ошибка сохранения пустой даты {empty_date}: {e}")
            return False
    
    def save_empty_dates(self, dates: list) -> int:
        """
        Сохранить несколько пустых дат
        
        Args:
            dates: Список дат
            
        Returns:
            Количество сохранённых
        """
        if not dates:
            return 0
        
        saved = 0
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                for d in dates:
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO zcyc_empty_dates (date)
                            VALUES (?)
                        ''', (d.strftime('%Y-%m-%d'),))
                        saved += 1
                    except Exception:
                        pass
            
            return saved
        except Exception as e:
            logger.error(f"Ошибка сохранения пустых дат: {e}")
            return saved
    
    def load_empty_dates(self, start_date: date = None, end_date: date = None) -> set:
        """
        Загрузить множество пустых дат
        
        Args:
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Множество дат
        """
        query = 'SELECT date FROM zcyc_empty_dates WHERE 1=1'
        params = []
        
        if start_date:
            query += ' AND date >= ?'
            params.append(start_date.strftime('%Y-%m-%d'))
        
        if end_date:
            query += ' AND date <= ?'
            params.append(end_date.strftime('%Y-%m-%d'))
        
        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        
        return {datetime.strptime(row['date'], '%Y-%m-%d').date() for row in rows}
    
    def count_empty_dates(self) -> int:
        """Количество пустых дат"""
        with get_db_cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as cnt FROM zcyc_empty_dates')
            row = cursor.fetchone()
        
        return row['cnt'] if row else 0
    
    # ==========================================
    # INTRADAY QUOTES (внутридневные котировки)
    # ==========================================
    
    def save_intraday_quotes(self, df: pd.DataFrame) -> int:
        """
        Сохранить текущие котировки в БД
        
        Args:
            df: DataFrame с колонками от fetch_current_bond_quotes()
                tradedate, tradetime, updatetime, secid, shortname, bidprice, bidyield,
                askprice, askyield, trdprice, trdyield, clcyield, crtyield,
                crtduration, g_spread_bp
                
        Returns:
            Количество сохранённых записей
        """
        if df.empty:
            return 0
        
        saved_count = 0
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                for _, row in df.iterrows():
                    try:
                        # Преобразуем дату и время
                        tradedate = str(row['tradedate'])[:10] if pd.notna(row['tradedate']) else None
                        tradetime = str(row['tradetime'])[:8] if pd.notna(row['tradetime']) else None
                        updatetime = str(row['updatetime'])[:8] if pd.notna(row['updatetime']) else None
                        
                        if not tradedate or not updatetime:
                            continue
                        
                        cursor.execute('''
                            INSERT OR REPLACE INTO intraday_quotes 
                            (tradedate, tradetime, updatetime, secid, shortname, 
                             bidprice, bidyield, askprice, askyield,
                             trdprice, trdyield, clcyield, crtyield,
                             crtduration, g_spread_bp, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                        ''', (
                            tradedate,
                            tradetime,
                            updatetime,
                            row.get('secid'),
                            row.get('shortname'),
                            float(row['bidprice']) if pd.notna(row.get('bidprice')) else None,
                            float(row['bidyield']) if pd.notna(row.get('bidyield')) else None,
                            float(row['askprice']) if pd.notna(row.get('askprice')) else None,
                            float(row['askyield']) if pd.notna(row.get('askyield')) else None,
                            float(row['trdprice']) if pd.notna(row.get('trdprice')) else None,
                            float(row['trdyield']) if pd.notna(row.get('trdyield')) else None,
                            float(row['clcyield']) if pd.notna(row.get('clcyield')) else None,
                            float(row['crtyield']) if pd.notna(row.get('crtyield')) else None,
                            int(row['crtduration']) if pd.notna(row.get('crtduration')) else None,
                            float(row['g_spread_bp']) if pd.notna(row.get('g_spread_bp')) else None
                        ))
                        saved_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Ошибка сохранения intraday {row.get('secid')}: {e}")
            
            logger.info(f"Сохранено {saved_count} intraday котировок")
            return saved_count
            
        except Exception as e:
            logger.error(f"Ошибка сохранения intraday quotes: {e}")
            return saved_count
    
    def load_intraday_quotes(
        self,
        tradedate: date = None,
        isins: List[str] = None,
        most_recent: bool = True
    ) -> pd.DataFrame:
        """
        Загрузить intraday котировки из БД
        
        Args:
            tradedate: Дата торгов (игнорируется если most_recent=True)
            isins: Список ISIN для фильтрации (None = все)
            most_recent: Если True, загружает последние данные (max tradedate)
            
        Returns:
            DataFrame с котировками
        """
        if most_recent:
            # Загружаем данные за последнюю торговую дату
            query = '''
                SELECT tradedate, tradetime, updatetime, secid, shortname,
                       bidprice, bidyield, askprice, askyield,
                       trdprice, trdyield, clcyield, crtyield,
                       crtduration, g_spread_bp, created_at
                FROM intraday_quotes
                WHERE tradedate = (SELECT MAX(tradedate) FROM intraday_quotes)
            '''
            params = []
        else:
            if tradedate is None:
                tradedate = date.today()
            
            query = '''
                SELECT tradedate, tradetime, updatetime, secid, shortname,
                       bidprice, bidyield, askprice, askyield,
                       trdprice, trdyield, clcyield, crtyield,
                       crtduration, g_spread_bp, created_at
                FROM intraday_quotes
                WHERE tradedate = ?
            '''
            params = [tradedate.strftime('%Y-%m-%d')]
        
        if isins:
            placeholders = ','.join(['?' for _ in isins])
            query += f' AND secid IN ({placeholders})'
            params.extend(isins)
        
        query += ' ORDER BY created_at'
        
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        if df.empty:
            return pd.DataFrame()
        
        # Добавляем datetime колонку для графиков (используем created_at)
        df['datetime'] = pd.to_datetime(df['created_at'])
        
        # Логируем загруженную дату
        loaded_date = df['tradedate'].iloc[0]
        logger.debug(f"Загружено {len(df)} intraday записей за {loaded_date}")
        
        return df
    
    def delete_intraday_quotes(self, tradedate: date = None) -> int:
        """
        Удалить intraday котировки за дату
        
        Args:
            tradedate: Дата для удаления (по умолчанию все, кроме сегодня)
            
        Returns:
            Количество удалённых записей
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                if tradedate:
                    cursor.execute(
                        'DELETE FROM intraday_quotes WHERE tradedate = ?',
                        (tradedate.strftime('%Y-%m-%d'),)
                    )
                else:
                    # Удалить все, кроме сегодня
                    today = date.today().strftime('%Y-%m-%d')
                    cursor.execute(
                        'DELETE FROM intraday_quotes WHERE tradedate < ?',
                        (today,)
                    )
                
                deleted = cursor.rowcount
            
            logger.info(f"Удалено {deleted} intraday котировок")
            return deleted
            
        except Exception as e:
            logger.error(f"Ошибка удаления intraday quotes: {e}")
            return 0
    
    def get_intraday_dates(self) -> List[date]:
        """
        Получить список дат с intraday данными
        
        Returns:
            Список дат
        """
        with get_db_cursor() as cursor:
            cursor.execute('SELECT DISTINCT tradedate FROM intraday_quotes ORDER BY tradedate')
            rows = cursor.fetchall()
        
        return [datetime.strptime(row['tradedate'], '%Y-%m-%d').date() for row in rows]
    
    def count_intraday_quotes(self, tradedate: date = None) -> int:
        """Количество intraday записей"""
        with get_db_cursor() as cursor:
            if tradedate:
                cursor.execute(
                    'SELECT COUNT(*) as cnt FROM intraday_quotes WHERE tradedate = ?',
                    (tradedate.strftime('%Y-%m-%d'),)
                )
            else:
                cursor.execute('SELECT COUNT(*) as cnt FROM intraday_quotes')
            row = cursor.fetchone()
        
        return row['cnt'] if row else 0
