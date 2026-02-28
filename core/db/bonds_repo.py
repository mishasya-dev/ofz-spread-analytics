"""
Репозиторий облигаций

Содержит операции CRUD для облигаций.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from .connection import get_connection

logger = logging.getLogger(__name__)


class BondsRepository:
    """Репозиторий для работы с облигациями"""
    
    def save(self, bond_data: Dict) -> bool:
        """
        Сохранить информацию об облигации

        Args:
            bond_data: Словарь с данными облигации

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

    def load(self, isin: str) -> Optional[Dict]:
        """Загрузить информацию об облигации"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM bonds WHERE isin = ?', (isin,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_all(self) -> List[Dict]:
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

    def get_favorites(self) -> List[Dict]:
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

    def update_market_data(
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

    def delete(self, isin: str) -> bool:
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

    def count(self) -> int:
        """Получить количество облигаций в БД"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) as cnt FROM bonds')
        row = cursor.fetchone()
        conn.close()

        return row['cnt'] if row else 0

    def migrate_from_config(self, bonds_config: Dict[str, Any]) -> int:
        """
        Миграция облигаций из config.py в БД при первом запуске

        Args:
            bonds_config: Словарь облигаций из config.py (AppConfig.bonds)

        Returns:
            Количество мигрированных облигаций
        """
        if self.count() > 0:
            logger.info("Облигации уже есть в БД, миграция не нужна")
            return 0

        migrated = 0

        for isin, bond in bonds_config.items():
            try:
                self.save({
                    'isin': isin,
                    'name': getattr(bond, 'name', ''),
                    'short_name': getattr(bond, 'name', ''),
                    'coupon_rate': getattr(bond, 'coupon_rate', None),
                    'maturity_date': getattr(bond, 'maturity_date', None),
                    'issue_date': getattr(bond, 'issue_date', None),
                    'face_value': getattr(bond, 'face_value', 1000),
                    'coupon_frequency': getattr(bond, 'coupon_frequency', 2),
                    'day_count': getattr(bond, 'day_count_convention', 'ACT/ACT'),
                    'is_favorite': 1,
                })
                migrated += 1
            except Exception as e:
                logger.error(f"Ошибка миграции облигации {isin}: {e}")

        logger.info(f"Мигрировано {migrated} облигаций из config.py")
        return migrated

    def get_favorites_as_config(self) -> Dict[str, Any]:
        """
        Получить избранные облигации в формате, совместимом с config.py

        Returns:
            Словарь {ISIN: BondConfig-like dict}
        """
        favorites = self.get_favorites()

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
