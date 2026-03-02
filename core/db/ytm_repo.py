"""
Репозиторий YTM (Yield to Maturity)

Содержит операции для работы с дневными и внутридневными YTM.
"""
from typing import Optional, Dict
from datetime import date, datetime, timedelta
import pandas as pd
import logging

from .connection import get_connection

logger = logging.getLogger(__name__)


class YTMRepository:
    """Репозиторий для работы с YTM"""
    
    # ==========================================
    # ДНЕВНЫЕ YTM (DAILY)
    # ==========================================
    
    def save_daily_ytm(self, isin: str, df: pd.DataFrame) -> int:
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
    # ВНУТРИДНЕВНЫЕ YTM (INTRADAY)
    # ==========================================
    
    def save_intraday_ytm(self, isin: str, interval: str, df: pd.DataFrame) -> int:
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
    # СТАТИСТИКА
    # ==========================================
    
    def count_daily_ytm(self, isin: str = None) -> int:
        """Количество записей дневных YTM"""
        conn = get_connection()
        cursor = conn.cursor()

        if isin:
            cursor.execute('SELECT COUNT(*) as cnt FROM daily_ytm WHERE isin = ?', (isin,))
        else:
            cursor.execute('SELECT COUNT(*) as cnt FROM daily_ytm')

        row = cursor.fetchone()
        conn.close()

        return row['cnt'] if row else 0

    def count_intraday_ytm(self, isin: str = None, interval: str = None) -> int:
        """Количество записей внутридневных YTM"""
        conn = get_connection()
        cursor = conn.cursor()

        query = 'SELECT COUNT(*) as cnt FROM intraday_ytm WHERE 1=1'
        params = []

        if isin:
            query += ' AND isin = ?'
            params.append(isin)
        if interval:
            query += ' AND interval = ?'
            params.append(interval)

        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()

        return row['cnt'] if row else 0

    def count_intraday_by_interval(self) -> Dict[str, int]:
        """Количество записей по интервалам"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT interval, COUNT(*) as cnt
            FROM intraday_ytm
            GROUP BY interval
        ''')
        rows = cursor.fetchall()
        conn.close()

        return {row['interval']: row['cnt'] for row in rows}

    # ==========================================
    # ВАЛИДАЦИЯ YTM
    # ==========================================

    def get_daily_ytm_for_date(self, isin: str, target_date: date) -> Optional[float]:
        """
        Получить официальный YIELDCLOSE за конкретную дату

        Args:
            isin: ISIN облигации
            target_date: Дата

        Returns:
            YTM или None
        """
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT ytm FROM daily_ytm
            WHERE isin = ? AND date = ?
        ''', (isin, target_date.strftime('%Y-%m-%d')))

        row = cursor.fetchone()
        conn.close()

        return row['ytm'] if row else None

    def get_last_candle_ytm(self, isin: str, interval: str, target_date: date) -> Optional[float]:
        """
        Получить YTM последней свечи за указанный день

        Args:
            isin: ISIN облигации
            interval: Интервал свечей ("1", "10", "60")
            target_date: Дата для поиска

        Returns:
            ytm последней свечи или None
        """
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT ytm FROM intraday_ytm
            WHERE isin = ? AND interval = ? AND date(datetime) = ?
            ORDER BY datetime DESC
            LIMIT 1
        ''', (isin, interval, target_date.strftime('%Y-%m-%d')))

        row = cursor.fetchone()
        conn.close()

        return row['ytm'] if row else None

    def validate_ytm_accuracy(self, isin: str, interval: str = "60", days: int = 5) -> Dict:
        """
        Сравнить YTM последних свечей с официальным YIELDCLOSE за несколько дней

        Args:
            isin: ISIN облигации
            interval: Интервал свечей
            days: Количество дней для проверки

        Returns:
            {
                'valid': bool,
                'days_checked': int,
                'avg_diff_bp': float,
                'max_diff_bp': float,
                'max_diff_date': date,
                'details': [
                    {
                        'date': date,
                        'calculated': float,
                        'official': float,
                        'diff_bp': float,
                        'valid': bool
                    }, ...
                ]
            }
        """
        conn = get_connection()
        cursor = conn.cursor()

        # Получаем последние N дней с YIELDCLOSE
        cursor.execute('''
            SELECT date, ytm FROM daily_ytm
            WHERE isin = ?
            ORDER BY date DESC
            LIMIT ?
        ''', (isin, days))

        daily_rows = cursor.fetchall()

        if not daily_rows:
            conn.close()
            return {
                'valid': True,
                'days_checked': 0,
                'avg_diff_bp': 0,
                'max_diff_bp': 0,
                'max_diff_date': None,
                'details': [],
                'reason': 'no_daily_data'
            }

        details = []
        total_diff = 0
        max_diff = 0
        max_diff_date = None
        valid_days = 0
        days_checked = 0

        for row in daily_rows:
            day_date = datetime.strptime(row['date'], '%Y-%m-%d').date()
            official_ytm = row['ytm']

            # Пропускаем сегодня (неполный торговый день)
            if day_date >= date.today():
                continue

            # Получаем YTM последней свечи за этот день
            cursor.execute('''
                SELECT ytm FROM intraday_ytm
                WHERE isin = ? AND interval = ? AND date(datetime) = ?
                ORDER BY datetime DESC
                LIMIT 1
            ''', (isin, interval, row['date']))

            candle_row = cursor.fetchone()

            if candle_row and official_ytm is not None:
                calculated_ytm = candle_row['ytm']
                diff_bp = abs(calculated_ytm - official_ytm) * 100
                is_valid = diff_bp <= 5.0

                details.append({
                    'date': day_date,
                    'calculated': round(calculated_ytm, 4),
                    'official': round(official_ytm, 4),
                    'diff_bp': round(diff_bp, 2),
                    'valid': is_valid
                })

                total_diff += diff_bp
                days_checked += 1

                if diff_bp > max_diff:
                    max_diff = diff_bp
                    max_diff_date = day_date

                if is_valid:
                    valid_days += 1

        conn.close()

        if days_checked == 0:
            return {
                'valid': True,
                'days_checked': 0,
                'avg_diff_bp': 0,
                'max_diff_bp': 0,
                'max_diff_date': None,
                'details': [],
                'reason': 'no_matching_data'
            }

        avg_diff = total_diff / days_checked

        return {
            'valid': valid_days == days_checked,  # Все дни должны быть валидны
            'days_checked': days_checked,
            'valid_days': valid_days,
            'avg_diff_bp': round(avg_diff, 2),
            'max_diff_bp': round(max_diff, 2),
            'max_diff_date': max_diff_date,
            'details': details
        }
