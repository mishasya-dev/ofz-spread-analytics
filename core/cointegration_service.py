"""
Сервис фонового анализа коинтеграции для избранных пар облигаций.

Функции:
- Генерация пар из избранного
- Фоновая проверка коинтеграции
- Кэширование результатов
- Проверка объёма данных (data_days, low_data флаг)
"""
import logging
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional, Any
from itertools import combinations
from concurrent.futures import ThreadPoolExecutor, Future
import threading
import pandas as pd

logger = logging.getLogger(__name__)

# Минимум дней для надёжного анализа
MIN_DATA_DAYS = 360


class CointegrationResult:
    """Результат анализа пары"""
    
    def __init__(
        self,
        bond1_isin: str,
        bond2_isin: str,
        is_cointegrated: bool,
        pvalue: Optional[float] = None,
        half_life: Optional[float] = None,
        hedge_ratio: Optional[float] = None,
        data_days: int = 0,
        adf_bond1_pvalue: Optional[float] = None,
        adf_bond2_pvalue: Optional[float] = None,
        both_nonstationary: bool = False,
        error: Optional[str] = None,
        checked_at: Optional[datetime] = None
    ):
        self.bond1_isin = bond1_isin
        self.bond2_isin = bond2_isin
        self.is_cointegrated = is_cointegrated
        self.pvalue = pvalue
        self.half_life = half_life
        self.hedge_ratio = hedge_ratio
        self.data_days = data_days
        self.adf_bond1_pvalue = adf_bond1_pvalue
        self.adf_bond2_pvalue = adf_bond2_pvalue
        self.both_nonstationary = both_nonstationary
        self.low_data = data_days < MIN_DATA_DAYS if data_days > 0 else False
        self.error = error
        self.checked_at = checked_at or datetime.now()
    
    @property
    def key(self) -> str:
        """Ключ для хранения: ISIN1-ISIN2 (по алфавиту)"""
        isins = sorted([self.bond1_isin, self.bond2_isin])
        return f"{isins[0]}-{isins[1]}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'bond1_isin': self.bond1_isin,
            'bond2_isin': self.bond2_isin,
            'is_cointegrated': self.is_cointegrated,
            'pvalue': self.pvalue,
            'half_life': self.half_life,
            'hedge_ratio': self.hedge_ratio,
            'data_days': self.data_days,
            'adf_bond1_pvalue': self.adf_bond1_pvalue,
            'adf_bond2_pvalue': self.adf_bond2_pvalue,
            'both_nonstationary': self.both_nonstationary,
            'low_data': self.low_data,
            'error': self.error,
            'checked_at': self.checked_at.isoformat() if self.checked_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CointegrationResult':
        """Десериализация из словаря"""
        checked_at = data.get('checked_at')
        if isinstance(checked_at, str):
            checked_at = datetime.fromisoformat(checked_at)
        
        return cls(
            bond1_isin=data['bond1_isin'],
            bond2_isin=data['bond2_isin'],
            is_cointegrated=data.get('is_cointegrated', False),
            pvalue=data.get('pvalue'),
            half_life=data.get('half_life'),
            hedge_ratio=data.get('hedge_ratio'),
            data_days=data.get('data_days', 0),
            adf_bond1_pvalue=data.get('adf_bond1_pvalue'),
            adf_bond2_pvalue=data.get('adf_bond2_pvalue'),
            both_nonstationary=data.get('both_nonstationary', False),
            error=data.get('error'),
            checked_at=checked_at
        )


class CointegrationService:
    """
    Сервис анализа коинтеграции для избранных пар.
    
    Features:
    - Фоновая проверка через ThreadPoolExecutor
    - Кэширование результатов
    - Метаданные о количестве данных
    """
    
    def __init__(self, max_workers: int = 2):
        """
        Args:
            max_workers: Количество параллельных потоков
        """
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._results: Dict[str, CointegrationResult] = {}
        self._is_running = False
    
    @staticmethod
    def generate_pairs(favorite_isins: List[str]) -> List[Tuple[str, str]]:
        """
        Генерирует все уникальные пары из списка ISIN.
        
        Args:
            favorite_isins: Список ISIN избранных облигаций
            
        Returns:
            Список кортежей (isin1, isin2)
            
        Examples:
            >>> generate_pairs(['A', 'B', 'C'])
            [('A', 'B'), ('A', 'C'), ('B', 'C')]
        """
        if len(favorite_isins) < 2:
            return []
        
        return list(combinations(favorite_isins, 2))
    
    @staticmethod
    def get_pair_key(isin1: str, isin2: str) -> str:
        """
        Генерирует ключ для пары (ISIN всегда по алфавиту).
        
        Это гарантирует что 'A-B' == 'B-A'.
        """
        isins = sorted([isin1, isin2])
        return f"{isins[0]}-{isins[1]}"
    
    def analyze_pair(
        self,
        bond1_isin: str,
        bond2_isin: str,
        db=None
    ) -> CointegrationResult:
        """
        Анализирует одну пару облигаций.
        
        Args:
            bond1_isin: ISIN первой облигации
            bond2_isin: ISIN второй облигации
            db: Экземпляр DatabaseManager
            
        Returns:
            CointegrationResult с результатами анализа
        """
        from core.cointegration import CointegrationAnalyzer
        from core.database import get_db
        from datetime import timedelta
        
        if db is None:
            db = get_db()
        
        try:
            # Загружаем данные из БД
            start_date = date.today() - timedelta(days=730)  # До 2 лет
            
            df1 = db.load_daily_ytm(bond1_isin, start_date=start_date)
            df2 = db.load_daily_ytm(bond2_isin, start_date=start_date)
            
            if df1.empty or df2.empty:
                return CointegrationResult(
                    bond1_isin=bond1_isin,
                    bond2_isin=bond2_isin,
                    is_cointegrated=False,
                    data_days=0,
                    error="Нет данных в БД"
                )
            
            # Анализ коинтеграции (синхронизация внутри analyze_pair)
            analyzer = CointegrationAnalyzer()
            result = analyzer.analyze_pair(df1['ytm'], df2['ytm'])
            
            # Проверка на ошибку
            if 'error' in result:
                return CointegrationResult(
                    bond1_isin=bond1_isin,
                    bond2_isin=bond2_isin,
                    is_cointegrated=False,
                    data_days=result.get('n_observations', 0),
                    error=result['error']
                )
            
            # Извлекаем данные из результата
            eg = result.get('engle_granger', {})
            n_obs = result.get('n_observations', 0)
            
            return CointegrationResult(
                bond1_isin=bond1_isin,
                bond2_isin=bond2_isin,
                is_cointegrated=result.get('is_cointegrated', False),
                pvalue=eg.get('pvalue'),
                half_life=result.get('half_life'),
                hedge_ratio=result.get('hedge_ratio'),
                data_days=n_obs,
                adf_bond1_pvalue=eg.get('ytm1_adf_pvalue'),
                adf_bond2_pvalue=eg.get('ytm2_adf_pvalue'),
                both_nonstationary=result.get('both_nonstationary', False)
            )
            
        except Exception as e:
            logger.error(f"Ошибка анализа {bond1_isin}-{bond2_isin}: {e}")
            return CointegrationResult(
                bond1_isin=bond1_isin,
                bond2_isin=bond2_isin,
                is_cointegrated=False,
                error=str(e)
            )
    
    def run_background(
        self,
        favorite_isins: List[str],
        db=None,
        on_complete=None
    ) -> int:
        """
        Запускает фоновый анализ всех пар из избранного.
        
        Args:
            favorite_isins: Список ISIN избранных облигаций
            db: Экземпляр DatabaseManager
            on_complete: Callback при завершении (results: Dict)
            
        Returns:
            Количество запущенных задач
        """
        pairs = self.generate_pairs(favorite_isins)
        
        if not pairs:
            logger.info("Нет пар для анализа")
            return 0
        
        with self._lock:
            self._is_running = True
            self._results.clear()
        
        logger.info(f"Запуск фонового анализа {len(pairs)} пар")
        
        def analyze_all():
            results = {}
            for isin1, isin2 in pairs:
                key = self.get_pair_key(isin1, isin2)
                result = self.analyze_pair(isin1, isin2, db)
                results[key] = result
            
            with self._lock:
                self._results = results
                self._is_running = False
            
            # Сохраняем в БД
            self._save_results_to_db(results, db)
            
            if on_complete:
                on_complete(results)
            
            logger.info(f"Анализ завершён: {len(results)} пар")
        
        self._executor.submit(analyze_all)
        
        return len(pairs)
    
    def _save_results_to_db(
        self,
        results: Dict[str, 'CointegrationResult'],
        db=None
    ):
        """Сохраняет результаты в БД"""
        from core.database import get_db
        
        if db is None:
            db = get_db()
        
        try:
            for key, result in results.items():
                db.save_cointegration_result(result.to_dict())
            logger.info(f"Сохранено {len(results)} результатов коинтеграции в БД")
        except Exception as e:
            logger.error(f"Ошибка сохранения результатов: {e}")
    
    def get_result(self, isin1: str, isin2: str) -> Optional[CointegrationResult]:
        """
        Получает результат для конкретной пары.
        
        Args:
            isin1: ISIN первой облигации
            isin2: ISIN второй облигации
            
        Returns:
            CointegrationResult или None
        """
        key = self.get_pair_key(isin1, isin2)
        return self._results.get(key)
    
    def get_all_results(self) -> Dict[str, CointegrationResult]:
        """Возвращает все результаты"""
        return self._results.copy()
    
    def is_running(self) -> bool:
        """Проверяет, идёт ли анализ"""
        return self._is_running
    
    def load_cached_results(self, db=None, max_age_hours: int = 24) -> int:
        """
        Загружает кэшированные результаты из БД.
        
        Args:
            db: Экземпляр DatabaseManager
            max_age_hours: Максимальный возраст результатов в часах
            
        Returns:
            Количество загруженных результатов
        """
        from core.database import get_db
        from datetime import timedelta
        
        if db is None:
            db = get_db()
        
        try:
            if hasattr(db, 'load_cointegration_results'):
                results = db.load_cointegration_results(
                    max_age=timedelta(hours=max_age_hours)
                )
                
                for key, data in results.items():
                    self._results[key] = CointegrationResult.from_dict(data)
                
                logger.info(f"Загружено {len(results)} кэшированных результатов")
                return len(results)
        except Exception as e:
            logger.error(f"Ошибка загрузки кэша: {e}")
        
        return 0
    
    def shutdown(self):
        """Завершает работу executor"""
        self._executor.shutdown(wait=False)


# Глобальный экземпляр сервиса
_service_instance: Optional[CointegrationService] = None
_service_lock = threading.Lock()


def get_cointegration_service() -> CointegrationService:
    """Получить глобальный экземпляр сервиса"""
    global _service_instance
    
    with _service_lock:
        if _service_instance is None:
            _service_instance = CointegrationService()
        return _service_instance
