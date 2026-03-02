"""
Кэш списка ОФЗ с MOEX

Архитектура:
- Список ОФЗ хранится в БД (таблица bonds)
- Метаданные кэша в cache_metadata (updated_at, ttl)
- Автообновление по расписанию (24ч TTL)
- Фоновая загрузка через threading

Использование:
    from core.ofz_cache import OFZCache

    cache = OFZCache()

    # Получить список (из кэша или загрузить)
    bonds = cache.get_ofz_list()

    # Принудительное обновление
    cache.refresh_async()  # в фоне
    cache.refresh_sync()   # с ожиданием
"""
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from .db.connection import get_connection

logger = logging.getLogger(__name__)

# TTL по умолчанию: 24 часа
DEFAULT_TTL_SECONDS = 86400


class OFZCache:
    """Кэш списка ОФЗ с автоматическим обновлением"""

    CACHE_TYPE = "ofz_list"

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        """
        Args:
            ttl_seconds: Время жизни кэша в секундах (по умолчанию 24ч)
        """
        self.ttl_seconds = ttl_seconds
        self._refresh_lock = threading.Lock()
        self._is_refreshing = False

    def get_cache_info(self) -> Optional[Dict]:
        """
        Получить информацию о кэше

        Returns:
            {'updated_at': datetime, 'is_expired': bool, 'count': int} или None
        """
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT updated_at, ttl_seconds
            FROM cache_metadata
            WHERE cache_type = ?
        ''', (self.CACHE_TYPE,))

        row = cursor.fetchone()

        # Количество облигаций в кэше
        cursor.execute('SELECT COUNT(*) as cnt FROM bonds')
        count = cursor.fetchone()['cnt']

        conn.close()

        if not row:
            return {
                'updated_at': None,
                'is_expired': True,
                'count': count
            }

        updated_at = datetime.strptime(row['updated_at'], '%Y-%m-%d %H:%M:%S')
        ttl = row['ttl_seconds'] or self.ttl_seconds
        is_expired = datetime.now() - updated_at > timedelta(seconds=ttl)

        return {
            'updated_at': updated_at,
            'is_expired': is_expired,
            'count': count
        }

    def is_cache_valid(self) -> bool:
        """Проверить, валиден ли кэш"""
        info = self.get_cache_info()
        return info is not None and not info['is_expired'] and info['count'] > 0

    def get_ofz_list(self) -> List[Dict[str, Any]]:
        """
        Получить список ОФЗ из БД

        Если кэш устарел - запускает фоновое обновление.
        Возвращает текущий кэш (может быть устаревшим).

        Returns:
            Список словарей с данными облигаций
        """
        info = self.get_cache_info()

        # Если кэш пустой - синхронная загрузка
        if info['count'] == 0:
            logger.info("Кэш ОФЗ пуст, загружаем синхронно")
            self.refresh_sync()
        # Если устарел - фоновое обновление
        elif info['is_expired']:
            logger.info("Кэш ОФЗ устарел, запускаем фоновое обновление")
            self.refresh_async()

        # Возвращаем из БД
        return self._load_from_db()

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """Загрузить список ОФЗ из БД"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT isin, name, short_name, coupon_rate, maturity_date,
                   issue_date, face_value, coupon_frequency, day_count,
                   last_price, last_ytm, duration_years, duration_days
            FROM bonds
            ORDER BY duration_years ASC
        ''')

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def refresh_sync(self) -> int:
        """
        Синхронное обновление кэша с MOEX

        Returns:
            Количество загруженных облигаций
        """
        if self._is_refreshing:
            logger.info("Обновление уже выполняется")
            return 0

        with self._refresh_lock:
            self._is_refreshing = True
            try:
                return self._do_refresh()
            finally:
                self._is_refreshing = False

    def refresh_async(self) -> bool:
        """
        Асинхронное обновление кэша в отдельном потоке

        Returns:
            True если запуск успешен, False если уже обновляется
        """
        if self._is_refreshing:
            return False

        thread = threading.Thread(target=self._background_refresh, daemon=True)
        thread.start()
        return True

    def _background_refresh(self):
        """Фоновое обновление (вызывается в отдельном потоке)"""
        if self._is_refreshing:
            return

        with self._refresh_lock:
            self._is_refreshing = True
            try:
                logger.info("Фоновое обновление кэша ОФЗ начато")
                count = self._do_refresh()
                logger.info(f"Фоновое обновление завершено: {count} облигаций")
            except Exception as e:
                logger.error(f"Ошибка фонового обновления: {e}")
            finally:
                self._is_refreshing = False

    def _do_refresh(self) -> int:
        """
        Выполнить загрузку с MOEX и сохранить в БД

        Returns:
            Количество загруженных облигаций
        """
        from api.moex_bonds import MOEXBondsFetcher, filter_ofz_for_trading

        fetcher = MOEXBondsFetcher()
        try:
            # Загружаем все ОФЗ
            all_bonds = fetcher.fetch_ofz_with_market_data(include_details=False)

            # Фильтруем для торговли
            filtered = filter_ofz_for_trading(all_bonds, require_trades=False)

            # Сохраняем в БД
            count = self._save_to_db(filtered)

            # Обновляем метаданные кэша
            self._update_cache_metadata()

            return count

        finally:
            fetcher.close()

    def _save_to_db(self, bonds: List[Dict]) -> int:
        """Сохранить список ОФЗ в БД"""
        conn = get_connection()
        cursor = conn.cursor()

        # Очищаем старые данные (кроме избранных)
        cursor.execute('DELETE FROM bonds WHERE is_favorite = 0')

        # Получаем список избранных ISIN
        cursor.execute('SELECT isin FROM bonds WHERE is_favorite = 1')
        favorite_isins = {row['isin'] for row in cursor.fetchall()}

        count = 0
        for bond in bonds:
            isin = bond.get('isin')
            is_favorite = isin in favorite_isins

            cursor.execute('''
                INSERT OR REPLACE INTO bonds (
                    isin, name, short_name, coupon_rate, maturity_date,
                    issue_date, face_value, coupon_frequency, day_count,
                    last_price, last_ytm, duration_years, duration_days,
                    is_favorite, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                isin,
                bond.get('name') or bond.get('short_name') or isin,
                bond.get('short_name'),
                bond.get('coupon_rate'),
                bond.get('maturity_date'),
                bond.get('issue_date'),
                bond.get('face_value', 1000),
                bond.get('coupon_frequency', 2),
                bond.get('day_count', 'ACT/ACT'),
                bond.get('last_price'),
                bond.get('last_ytm'),
                bond.get('duration_years'),
                bond.get('duration_days'),
                1 if is_favorite else 0,  # Сохраняем статус избранного
            ))
            count += 1

        conn.commit()
        conn.close()

        logger.info(f"Сохранено {count} облигаций в кэш")
        return count

    def _update_cache_metadata(self):
        """Обновить метаданные кэша"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO cache_metadata (cache_type, updated_at, ttl_seconds)
            VALUES (?, CURRENT_TIMESTAMP, ?)
        ''', (self.CACHE_TYPE, self.ttl_seconds))

        conn.commit()
        conn.close()


# Глобальный экземпляр
_cache_instance: Optional[OFZCache] = None


def get_ofz_cache() -> OFZCache:
    """Получить глобальный экземпляр кэша"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = OFZCache()
    return _cache_instance
