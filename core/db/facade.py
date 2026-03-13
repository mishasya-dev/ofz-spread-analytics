"""
Фасад базы данных

Предоставляет унифицированный интерфейс для работы с данными,
делегируя вызовы специализированным репозиториям.
"""
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

from .connection import get_connection
from .bonds_repo import BondsRepository
from .ytm_repo import YTMRepository
from .spreads_repo import SpreadsRepository

logger = logging.getLogger(__name__)


class DatabaseFacade:
    """
    Фасад для работы с базой данных.

    Делегирует вызовы специализированным репозиториям:
    - BondsRepository: облигации
    - YTMRepository: YTM данные
    - SpreadsRepository: спреды
    """

    def __init__(self):
        self._bonds_repo = BondsRepository()
        self._ytm_repo = YTMRepository()
        self._spreads_repo = SpreadsRepository()

    # ==========================================
    # ДНЕВНЫЕ YTM (делегирует YTMRepository)
    # ==========================================

    def save_daily_ytm(self, isin: str, df: pd.DataFrame) -> int:
        """Сохранить дневные YTM"""
        return self._ytm_repo.save_daily_ytm(isin, df)

    def load_daily_ytm(
        self,
        isin: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """Загрузить дневные YTM"""
        return self._ytm_repo.load_daily_ytm(isin, start_date, end_date)

    def get_last_daily_ytm_date(self, isin: str) -> Optional[date]:
        """Получить последнюю дату дневных YTM"""
        return self._ytm_repo.get_last_daily_ytm_date(isin)

    # ==========================================
    # INTRADAY YTM (делегирует YTMRepository)
    # ==========================================

    def save_intraday_ytm(self, isin: str, interval: str, df: pd.DataFrame) -> int:
        """Сохранить intraday YTM"""
        return self._ytm_repo.save_intraday_ytm(isin, interval, df)

    def load_intraday_ytm(
        self,
        isin: str,
        interval: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """Загрузить intraday YTM"""
        return self._ytm_repo.load_intraday_ytm(isin, interval, start_date, end_date)

    def get_last_intraday_ytm_datetime(
        self,
        isin: str,
        interval: str
    ) -> Optional[datetime]:
        """Получить последний datetime intraday YTM"""
        return self._ytm_repo.get_last_intraday_ytm_datetime(isin, interval)

    # ==========================================
    # ОБЛИГАЦИИ (делегирует BondsRepository)
    # ==========================================

    def save_bond(self, bond_data: Dict) -> bool:
        """Сохранить облигацию"""
        return self._bonds_repo.save(bond_data)

    def load_bond(self, isin: str) -> Optional[Dict]:
        """Загрузить облигацию"""
        return self._bonds_repo.load(isin)

    def get_all_bonds(self) -> List[Dict]:
        """Получить все облигации"""
        return self._bonds_repo.get_all()

    def get_favorite_bonds(self) -> List[Dict]:
        """Получить избранные облигации"""
        return self._bonds_repo.get_favorites()

    def set_favorite(self, isin: str, is_favorite: bool = True) -> bool:
        """Установить флаг избранного"""
        return self._bonds_repo.set_favorite(isin, is_favorite)

    def clear_all_favorites(self) -> int:
        """Снять все флаги избранного"""
        return self._bonds_repo.clear_all_favorites()

    def update_bond_market_data(
        self,
        isin: str,
        last_price: Optional[float] = None,
        last_ytm: Optional[float] = None,
        duration_years: Optional[float] = None,
        duration_days: Optional[float] = None
    ) -> bool:
        """Обновить рыночные данные облигации"""
        return self._bonds_repo.update_market_data(
            isin, last_price, last_ytm, duration_years, duration_days
        )

    def delete_bond(self, isin: str) -> bool:
        """Удалить облигацию"""
        return self._bonds_repo.delete(isin)

    def get_bonds_count(self) -> int:
        """Количество облигаций"""
        return self._bonds_repo.count()

    # ==========================================
    # СПРЕДЫ (делегирует SpreadsRepository)
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
        p25: float = None,
        p75: float = None,
        interval: str = None
    ) -> int:
        """Сохранить спред"""
        return self._spreads_repo.save_spread(
            isin_1, isin_2, mode, datetime_val, ytm_1, ytm_2,
            spread_bp, signal, p25, p75, interval
        )

    def load_spreads(
        self,
        isin_1: str,
        isin_2: str,
        mode: str,
        interval: str = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """Загрузить спреды"""
        return self._spreads_repo.load_spreads(
            isin_1, isin_2, mode, interval, start_date, end_date
        )

    # ==========================================
    # МИГРАЦИЯ И СТАТИСТИКА
    # ==========================================

    def migrate_config_bonds(self, bonds_config: Dict[str, Any]) -> int:
        """
        Мигрировать облигации из config.py в БД.

        Args:
            bonds_config: Словарь {isin: BondConfig}

        Returns:
            Количество мигрированных облигаций
        """
        migrated = 0
        for isin, bond in bonds_config.items():
            bond_data = {
                'isin': isin,
                'name': bond.name,
                'short_name': getattr(bond, 'short_name', bond.name),
                'coupon_rate': bond.coupon_rate,
                'maturity_date': bond.maturity_date,
                'issue_date': getattr(bond, 'issue_date', None),
                'face_value': getattr(bond, 'face_value', 1000),
                'coupon_frequency': getattr(bond, 'coupon_frequency', 2),
                'day_count': getattr(bond, 'day_count_convention', 'ACT/ACT'),
                'is_favorite': 1,  # По умолчанию все избранные
            }
            if self._bonds_repo.save(bond_data):
                migrated += 1
        return migrated

    def get_favorite_bonds_as_config(self) -> Dict[str, Any]:
        """
        Получить избранные облигации в формате config.py.

        Returns:
            Словарь {isin: {isin, name, maturity_date, coupon_rate, ...}}
        """
        favorites = self._bonds_repo.get_favorites()
        result = {}
        for bond in favorites:
            isin = bond['isin']
            result[isin] = {
                'isin': isin,
                'name': bond.get('name', ''),
                'short_name': bond.get('short_name', ''),
                'maturity_date': bond.get('maturity_date', ''),
                'coupon_rate': bond.get('coupon_rate'),
                'face_value': bond.get('face_value', 1000),
                'coupon_frequency': bond.get('coupon_frequency', 2),
                'issue_date': bond.get('issue_date', ''),
                'day_count_convention': bond.get('day_count', 'ACT/ACT'),
            }
        return result

    def get_stats(self) -> Dict:
        """Получить статистику базы данных"""
        conn = get_connection()
        cursor = conn.cursor()

        # Облигации
        cursor.execute('SELECT COUNT(*) as cnt FROM bonds')
        bonds_count = cursor.fetchone()['cnt']

        # Избранные
        cursor.execute('SELECT COUNT(*) as cnt FROM bonds WHERE is_favorite = 1')
        favorites_count = cursor.fetchone()['cnt']

        # Дневные YTM
        cursor.execute('SELECT COUNT(*) as cnt FROM daily_ytm')
        daily_ytm_count = cursor.fetchone()['cnt']

        # Intraday YTM
        cursor.execute('SELECT COUNT(*) as cnt FROM intraday_ytm')
        intraday_ytm_count = cursor.fetchone()['cnt']

        # Спреды
        cursor.execute('SELECT COUNT(*) as cnt FROM spreads')
        spreads_count = cursor.fetchone()['cnt']

        # Свечи
        cursor.execute('SELECT COUNT(*) as cnt FROM candles')
        candles_count = cursor.fetchone()['cnt']

        # Снимки
        cursor.execute('SELECT COUNT(*) as cnt FROM snapshots')
        snapshots_count = cursor.fetchone()['cnt']

        conn.close()

        return {
            'bonds_count': bonds_count,
            'favorites_count': favorites_count,
            'daily_ytm_count': daily_ytm_count,
            'intraday_ytm_count': intraday_ytm_count,
            'spreads_count': spreads_count,
            'candles_count': candles_count,
            'snapshots_count': snapshots_count,
        }

    # ==========================================
    # ВАЛИДАЦИЯ YTM
    # ==========================================

    def validate_ytm_accuracy(
        self,
        isin: str,
        interval: str = "60",
        days: int = 5
    ) -> Dict:
        """
        Сравнить YTM последних свечей с официальным YIELDCLOSE.

        Делегирует YTMRepository.
        """
        return self._ytm_repo.validate_ytm_accuracy(isin, interval, days)

    # ==========================================
    # КОИНТЕГРАЦИЯ
    # ==========================================

    def save_cointegration_result(self, result: Dict) -> bool:
        """
        Сохранить результат анализа коинтеграции.
        
        Args:
            result: Словарь с результатами (CointegrationResult.to_dict())
            
        Returns:
            True если сохранено успешно
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            pair_key = f"{result['bond1_isin']}-{result['bond2_isin']}"
            # Сортируем ISIN для key
            isins = sorted([result['bond1_isin'], result['bond2_isin']])
            pair_key = f"{isins[0]}-{isins[1]}"
            
            cursor.execute('''
                INSERT OR REPLACE INTO cointegration_cache (
                    bond1_isin, bond2_isin, pair_key,
                    is_cointegrated, pvalue, half_life, hedge_ratio,
                    data_days, adf_bond1_pvalue, adf_bond2_pvalue,
                    both_nonstationary, low_data, error, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                isins[0],
                isins[1],
                pair_key,
                1 if result.get('is_cointegrated') else 0,
                result.get('pvalue'),
                result.get('half_life'),
                result.get('hedge_ratio'),
                result.get('data_days', 0),
                result.get('adf_bond1_pvalue'),
                result.get('adf_bond2_pvalue'),
                1 if result.get('both_nonstationary') else 0,
                1 if result.get('low_data') else 0,
                result.get('error'),
                result.get('checked_at', datetime.now().isoformat())
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения коинтеграции: {e}")
            return False
        finally:
            conn.close()

    def load_cointegration_result(self, isin1: str, isin2: str) -> Optional[Dict]:
        """
        Загрузить результат коинтеграции для пары.
        
        Args:
            isin1: ISIN первой облигации
            isin2: ISIN второй облигации
            
        Returns:
            Словарь с результатами или None
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            isins = sorted([isin1, isin2])
            pair_key = f"{isins[0]}-{isins[1]}"
            
            cursor.execute('''
                SELECT * FROM cointegration_cache WHERE pair_key = ?
            ''', (pair_key,))
            
            row = cursor.fetchone()
            
            if row:
                return {
                    'bond1_isin': row['bond1_isin'],
                    'bond2_isin': row['bond2_isin'],
                    'is_cointegrated': bool(row['is_cointegrated']),
                    'pvalue': row['pvalue'],
                    'half_life': row['half_life'],
                    'hedge_ratio': row['hedge_ratio'],
                    'data_days': row['data_days'],
                    'adf_bond1_pvalue': row['adf_bond1_pvalue'],
                    'adf_bond2_pvalue': row['adf_bond2_pvalue'],
                    'both_nonstationary': bool(row['both_nonstationary']),
                    'low_data': bool(row['low_data']),
                    'error': row['error'],
                    'checked_at': row['checked_at']
                }
            return None
            
        except Exception as e:
            logger.error(f"Ошибка загрузки коинтеграции: {e}")
            return None
        finally:
            conn.close()

    def load_all_cointegration_results(self, max_age_hours: int = 24) -> Dict[str, Dict]:
        """
        Загрузить все результаты коинтеграции.
        
        Args:
            max_age_hours: Максимальный возраст результатов (часы)
            
        Returns:
            Словарь {pair_key: result}
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT * FROM cointegration_cache 
                WHERE datetime(checked_at) >= datetime('now', ?)
            ''', (f'-{max_age_hours} hours',))
            
            rows = cursor.fetchall()
            results = {}
            
            for row in rows:
                results[row['pair_key']] = {
                    'bond1_isin': row['bond1_isin'],
                    'bond2_isin': row['bond2_isin'],
                    'is_cointegrated': bool(row['is_cointegrated']),
                    'pvalue': row['pvalue'],
                    'half_life': row['half_life'],
                    'hedge_ratio': row['hedge_ratio'],
                    'data_days': row['data_days'],
                    'adf_bond1_pvalue': row['adf_bond1_pvalue'],
                    'adf_bond2_pvalue': row['adf_bond2_pvalue'],
                    'both_nonstationary': bool(row['both_nonstationary']),
                    'low_data': bool(row['low_data']),
                    'error': row['error'],
                    'checked_at': row['checked_at']
                }
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка загрузки всех результатов: {e}")
            return {}
        finally:
            conn.close()

    def get_cointegrated_pairs(self) -> List[Dict]:
        """
        Получить все коинтегрированные пары.
        
        Returns:
            Список пар с is_cointegrated = True
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT * FROM cointegration_cache 
                WHERE is_cointegrated = 1
                ORDER BY pvalue ASC
            ''')
            
            rows = cursor.fetchall()
            results = []
            
            for row in rows:
                results.append({
                    'bond1_isin': row['bond1_isin'],
                    'bond2_isin': row['bond2_isin'],
                    'pair_key': row['pair_key'],
                    'pvalue': row['pvalue'],
                    'half_life': row['half_life'],
                    'hedge_ratio': row['hedge_ratio'],
                    'data_days': row['data_days'],
                    'low_data': bool(row['low_data']),
                    'checked_at': row['checked_at']
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка получения коинтегрированных пар: {e}")
            return []
        finally:
            conn.close()

    def clear_cointegration_cache(
        self,
        bond1_isin: str = None,
        bond2_isin: str = None,
        period_days: int = None
    ) -> int:
        """
        Очистить кэш коинтеграции

        Args:
            bond1_isin: ISIN первой облигации (опционально)
            bond2_isin: ISIN второй облигации (опционально)
            period_days: Период (опционально)

        Returns:
            Количество удалённых записей
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            if bond1_isin and bond2_isin:
                isins = sorted([bond1_isin, bond2_isin])
                if period_days:
                    cursor.execute('''
                        DELETE FROM cointegration_cache
                        WHERE bond1_isin = ? AND bond2_isin = ? AND period_days = ?
                    ''', (isins[0], isins[1], period_days))
                else:
                    cursor.execute('''
                        DELETE FROM cointegration_cache
                        WHERE bond1_isin = ? AND bond2_isin = ?
                    ''', (isins[0], isins[1]))
            elif period_days:
                cursor.execute('DELETE FROM cointegration_cache WHERE period_days = ?', (period_days,))
            else:
                cursor.execute('DELETE FROM cointegration_cache')

            deleted = cursor.rowcount
            conn.commit()
            return deleted

        except Exception as e:
            logger.error(f"Ошибка очистки кэша коинтеграции: {e}")
            return 0
        finally:
            conn.close()

    # ==========================================
    # СТАРЫЙ API КОИНТЕГРАЦИИ (для совместимости)
    # ==========================================

    def get_cointegration_cache(
        self,
        bond1_isin: str,
        bond2_isin: str,
        period_days: int,
        ttl_hours: int = 24
    ) -> Optional[Dict]:
        """
        Получить кэшированный результат коинтеграции (старый API).

        Совместимость с core/database.py::DatabaseManager.

        Args:
            bond1_isin: ISIN первой облигации
            bond2_isin: ISIN второй облигации
            period_days: Период анализа в днях
            ttl_hours: Время жизни кэша в часах (default 24)

        Returns:
            Словарь с результатом или None если кэш устарел/отсутствует
        """
        result = self.load_cointegration_result(bond1_isin, bond2_isin)

        if result is None:
            return None

        # Проверяем TTL
        if 'checked_at' in result:
            try:
                checked_at = datetime.fromisoformat(result['checked_at'])
                age_hours = (datetime.now() - checked_at).total_seconds() / 3600
                if age_hours > ttl_hours:
                    logger.debug(f"Кэш коинтеграции устарел ({age_hours:.1f} ч. > {ttl_hours} ч.)")
                    return None
            except Exception:
                pass

        return result

    def save_cointegration_cache(
        self,
        bond1_isin: str,
        bond2_isin: str,
        period_days: int,
        result: Dict
    ) -> bool:
        """
        Сохранить результат коинтеграции в кэш (старый API).

        Совместимость с core/database.py::DatabaseManager.

        Args:
            bond1_isin: ISIN первой облигации
            bond2_isin: ISIN второй облигации
            period_days: Период анализа в днях
            result: Словарь с результатом анализа

        Returns:
            True если успешно
        """
        # Добавляем недостающие поля для нового API
        full_result = {
            'bond1_isin': bond1_isin,
            'bond2_isin': bond2_isin,
            'data_days': period_days,
            **result
        }
        return self.save_cointegration_result(full_result)

    # ==========================================
    # СВЕЧИ (для совместимости)
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
                    None, None, None, row.get('ytm_close')
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
                   ytm_close
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
        
        if 'ytm_close' in df.columns:
            df['ytm'] = df['ytm_close']
        
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
    # ОЧИСТКА ДАННЫХ
    # ==========================================
    
    def clear_intraday_ytm(
        self,
        isin: str,
        interval: str
    ) -> int:
        """Удалить intraday YTM данные для облигации"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM intraday_ytm
            WHERE isin = ? AND interval = ?
        ''', (isin, interval))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logger.info(f"Удалено {deleted} intraday YTM для {isin} (interval={interval})")
        
        return deleted

    def cleanup_old_data(self, days_to_keep: int = 90) -> int:
        """
        Удалить старые данные
        
        Args:
            days_to_keep: Количество дней для хранения
            
        Returns:
            Общее количество удалённых записей
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
        
        total_deleted = 0
        
        # Удаляем старые свечи
        cursor.execute('DELETE FROM candles WHERE datetime < ?', (cutoff_date,))
        total_deleted += cursor.rowcount
        
        # Удаляем старые intraday YTM
        cursor.execute('DELETE FROM intraday_ytm WHERE datetime < ?', (cutoff_date,))
        total_deleted += cursor.rowcount
        
        # Удаляем старые спреды
        cursor.execute('DELETE FROM spreads WHERE datetime < ?', (cutoff_date,))
        total_deleted += cursor.rowcount
        
        # Удаляем старые снимки
        cutoff_datetime = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('DELETE FROM snapshots WHERE timestamp < ?', (cutoff_datetime,))
        total_deleted += cursor.rowcount
        
        conn.commit()
        conn.close()
        
        if total_deleted > 0:
            logger.info(f"Удалено {total_deleted} старых записей (старше {days_to_keep} дней)")
        
        return total_deleted

    def vacuum(self):
        """Оптимизировать БД (VACUUM)"""
        conn = get_connection()
        conn.execute('VACUUM')
        conn.close()
        logger.info("VACUUM выполнен")

    def clear_all_data(self):
        """Очистить все таблицы БД"""
        conn = get_connection()
        cursor = conn.cursor()
        
        tables = ['candles', 'daily_ytm', 'intraday_ytm', 'spreads', 'snapshots', 
                  'cointegration_cache', 'ns_params', 'g_spreads', 'yearyields',
                  'zcyc_cache', 'zcyc_empty_dates']
        
        for table in tables:
            cursor.execute(f'DELETE FROM {table}')
        
        conn.commit()
        conn.close()
        logger.info("Все данные очищены")


# Глобальный экземпляр фасада
_facade_instance: Optional[DatabaseFacade] = None


def get_db_facade() -> DatabaseFacade:
    """Получить экземпляр фасада БД (синглтон)"""
    global _facade_instance
    if _facade_instance is None:
        _facade_instance = DatabaseFacade()
    return _facade_instance
