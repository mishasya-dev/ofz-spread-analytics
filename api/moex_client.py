"""
Единый клиент для MOEX API с context manager

Особенности:
- Контекстный менеджер для управления ресурсами
- Адаптивный rate limiting (max 5 workers)
- Future-based API для неблокирующих запросов
- Автоматический retry с backoff
- Авто-снижение workers при 429 (Too Many Requests)

Использование:
    with MOEXClient() as client:
        # Блокирующий запрос
        response = client.request_sync(url, params)

        # Неблокирующий запрос (Future)
        future = client.request(url, params)
        # ... делаем другие дела ...
        response = future.result(timeout=10)

        # Пакетный запрос
        futures = client.request_batch([
            (url1, params1),
            (url2, params2),
        ])
"""
import requests
import time
import logging
import threading
from typing import Dict, List, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)

# MOEX base URL
MOEX_BASE_URL = "https://iss.moex.com/iss"

# Default settings
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_WORKERS = 5
MIN_WORKERS = 1
MAX_WORKERS_LIMIT = 5  # Консервативный лимит для MOEX


@dataclass
class RateLimitState:
    """Состояние rate limiter'а"""
    current_workers: int = DEFAULT_MAX_WORKERS
    consecutive_429: int = 0  # Количество подряд идущих 429
    last_429_time: float = 0
    total_requests: int = 0
    total_errors: int = 0
    request_times: deque = field(default_factory=lambda: deque(maxlen=100))


class AdaptiveRateLimiter:
    """
    Адаптивный rate limiter

    Автоматически снижает количество workers при получении 429.
    Восстанавливает после периода без ошибок.
    """

    # Пороги для адаптации
    REDUCE_THRESHOLD = 2  # Снижаем workers после N подряд 429
    REDUCE_COOLDOWN = 10  # Секунд между снижениями
    RECOVER_AFTER = 60    # Секунд без ошибок для восстановления

    def __init__(self, initial_workers: int = DEFAULT_MAX_WORKERS):
        self._state = RateLimitState(current_workers=initial_workers)
        self._lock = threading.Lock()

    def get_workers(self) -> int:
        """Получить текущее количество workers"""
        with self._lock:
            return self._state.current_workers

    def record_success(self):
        """Записать успешный запрос"""
        with self._lock:
            self._state.total_requests += 1
            self._state.consecutive_429 = 0

            # Восстановление workers после периода без ошибок
            now = time.time()
            if (self._state.current_workers < DEFAULT_MAX_WORKERS and
                now - self._state.last_429_time > self.RECOVER_AFTER):
                self._state.current_workers = min(
                    self._state.current_workers + 1,
                    DEFAULT_MAX_WORKERS
                )
                logger.info(f"Rate limiter: восстановлено до {self._state.current_workers} workers")

    def record_429(self) -> int:
        """
        Записать 429 ошибку

        Returns:
            Новое количество workers
        """
        with self._lock:
            self._state.total_requests += 1
            self._state.total_errors += 1
            self._state.consecutive_429 += 1
            self._state.last_429_time = time.time()

            # Снижаем workers если нужно
            now = time.time()
            if (self._state.consecutive_429 >= self.REDUCE_THRESHOLD and
                self._state.current_workers > MIN_WORKERS):
                self._state.current_workers = max(
                    MIN_WORKERS,
                    self._state.current_workers - 1
                )
                logger.warning(
                    f"Rate limiter: снижено до {self._state.current_workers} workers "
                    f"(429 errors: {self._state.consecutive_429})"
                )
                self._state.consecutive_429 = 0

            return self._state.current_workers

    def record_error(self):
        """Записать другую ошибку"""
        with self._lock:
            self._state.total_requests += 1
            self._state.total_errors += 1

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику"""
        with self._lock:
            return {
                "current_workers": self._state.current_workers,
                "total_requests": self._state.total_requests,
                "total_errors": self._state.total_errors,
                "consecutive_429": self._state.consecutive_429,
            }


class MOEXClient:
    """
    Единый клиент для MOEX API

    Features:
    - Context manager для автоматического управления ресурсами
    - Future-based API для неблокирующих запросов
    - Адаптивный rate limiting
    - Автоматический retry с exponential backoff
    """

    def __init__(
        self,
        max_workers: int = DEFAULT_MAX_WORKERS,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_url: str = MOEX_BASE_URL
    ):
        """
        Инициализация клиента

        Args:
            max_workers: Максимальное количество параллельных запросов (1-5)
            timeout: Таймаут запроса в секундах
            max_retries: Количество повторных попыток
            base_url: Базовый URL MOEX API
        """
        # Ограничиваем workers
        self._initial_workers = min(max(max_workers, MIN_WORKERS), MAX_WORKERS_LIMIT)
        self._timeout = timeout
        self._max_retries = max_retries
        self._base_url = base_url

        # Инициализируем rate limiter
        self._rate_limiter = AdaptiveRateLimiter(self._initial_workers)

        # Ресурсы (создаются при входе в context manager)
        self._session: Optional[requests.Session] = None
        self._executor: Optional[ThreadPoolExecutor] = None
        self._entered = False

    def __enter__(self) -> 'MOEXClient':
        """Вход в context manager"""
        if self._entered:
            raise RuntimeError("MOEXClient уже активен")

        # Создаём сессию
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "OFZ-Analytics/2.0",
            "Accept": "application/json",
        })

        # Создаём executor с текущим количеством workers
        current_workers = self._rate_limiter.get_workers()
        self._executor = ThreadPoolExecutor(max_workers=current_workers)

        self._entered = True
        logger.debug(f"MOEXClient создан (workers={current_workers})")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Выход из context manager"""
        if not self._entered:
            return

        # shutdown executor
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=False)
            self._executor = None

        # close session
        if self._session:
            self._session.close()
            self._session = None

        self._entered = False
        logger.debug("MOEXClient закрыт")

    def _ensure_entered(self):
        """Проверить, что клиент активен"""
        if not self._entered:
            raise RuntimeError(
                "MOEXClient должен использоваться как context manager: "
                "with MOEXClient() as client: ..."
            )

    def _do_request(
        self,
        url: str,
        params: Dict,
        method: str = "GET"
    ) -> requests.Response:
        """
        Выполнить один запрос с retry и rate limiting

        Args:
            url: URL (полный или относительный)
            params: Параметры запроса
            method: HTTP метод

        Returns:
            Response объект

        Raises:
            requests.RequestException при исчерпании попыток
        """
        self._ensure_entered()

        # Формируем полный URL если нужно
        if not url.startswith("http"):
            url = f"{self._base_url}{url}"

        last_error = None

        for attempt in range(self._max_retries):
            try:
                response = self._session.request(
                    method,
                    url,
                    params=params,
                    timeout=self._timeout
                )

                # Проверяем на rate limit
                if response.status_code == 429:
                    self._rate_limiter.record_429()
                    retry_after = int(response.headers.get("Retry-After", 5))
                    logger.warning(f"429 Too Many Requests, ждём {retry_after}с")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()

                # Успешный запрос
                self._rate_limiter.record_success()
                return response

            except requests.exceptions.RequestException as e:
                last_error = e
                self._rate_limiter.record_error()

                # Exponential backoff
                wait_time = (attempt + 1) * 2
                logger.warning(
                    f"Попытка {attempt + 1}/{self._max_retries} не удалась: {e}, "
                    f"ждём {wait_time}с"
                )
                time.sleep(wait_time)

        raise last_error or requests.RequestException("Unknown error")

    def request_sync(
        self,
        url: str,
        params: Optional[Dict] = None,
        method: str = "GET"
    ) -> requests.Response:
        """
        Синхронный (блокирующий) запрос

        Args:
            url: URL (полный или относительный к base_url)
            params: Параметры запроса
            method: HTTP метод

        Returns:
            Response объект

        Example:
            with MOEXClient() as client:
                response = client.request_sync("/engines/stock/zcyc.json", {"date": "2025-01-15"})
                data = response.json()
        """
        return self._do_request(url, params or {}, method)

    def request(
        self,
        url: str,
        params: Optional[Dict] = None,
        method: str = "GET"
    ) -> Future:
        """
        Асинхронный (неблокирующий) запрос

        Возвращает Future, который можно использовать позже.

        Args:
            url: URL (полный или относительный к base_url)
            params: Параметры запроса
            method: HTTP метод

        Returns:
            Future с результатом запроса

        Example:
            with MOEXClient() as client:
                future = client.request("/engines/stock/zcyc.json", {"date": "2025-01-15"})

                # ... делаем другие дела ...

                response = future.result(timeout=10)
                data = response.json()
        """
        self._ensure_entered()

        # Обновляем executor если изменилось количество workers
        current_workers = self._rate_limiter.get_workers()
        if self._executor._max_workers != current_workers:
            # Создаём новый executor с новым количеством workers
            old_executor = self._executor
            self._executor = ThreadPoolExecutor(max_workers=current_workers)
            old_executor.shutdown(wait=False)

        return self._executor.submit(
            self._do_request,
            url,
            params or {},
            method
        )

    def request_batch(
        self,
        requests_list: List[Tuple[str, Dict]],
        method: str = "GET"
    ) -> List[Future]:
        """
        Пакетный запрос (несколько параллельных запросов)

        Args:
            requests_list: Список (url, params) для запросов
            method: HTTP метод

        Returns:
            Список Future с результатами

        Example:
            with MOEXClient() as client:
                futures = client.request_batch([
                    ("/securities/SU26238RMFS.json", {}),
                    ("/securities/SU26239RMFS.json", {}),
                ])

                for future in futures:
                    response = future.result(timeout=30)
                    # ...
        """
        return [
            self.request(url, params, method)
            for url, params in requests_list
        ]

    def request_batch_wait(
        self,
        requests_list: List[Tuple[str, Dict]],
        timeout: Optional[float] = None,
        method: str = "GET"
    ) -> List[requests.Response]:
        """
        Пакетный запрос с ожиданием всех результатов

        Args:
            requests_list: Список (url, params) для запросов
            timeout: Общий таймаут для всех запросов
            method: HTTP метод

        Returns:
            Список Response объектов (или None для failed)

        Example:
            with MOEXClient() as client:
                responses = client.request_batch_wait([
                    ("/securities/SU26238RMFS.json", {}),
                    ("/securities/SU26239RMFS.json", {}),
                ], timeout=60)

                for response in responses:
                    if response:
                        data = response.json()
        """
        futures = self.request_batch(requests_list, method)

        results = []
        for future in futures:
            try:
                response = future.result(timeout=timeout)
                results.append(response)
            except Exception as e:
                logger.warning(f"Пакетный запрос не удался: {e}")
                results.append(None)

        return results

    def get_json(
        self,
        url: str,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        GET запрос с автоматическим парсингом JSON

        Args:
            url: URL
            params: Параметры запроса

        Returns:
            Распарсенный JSON как dict

        Example:
            with MOEXClient() as client:
                data = client.get_json("/engines/stock/zcyc.json", {"date": "2025-01-15"})
        """
        response = self.request_sync(url, params)
        return response.json()

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику клиента"""
        stats = self._rate_limiter.get_stats()
        stats["entered"] = self._entered
        stats["base_url"] = self._base_url
        return stats


# Глобальный singleton для простых случаев (не recommended)
_global_client: Optional[MOEXClient] = None
_global_client_lock = threading.Lock()


def get_client() -> MOEXClient:
    """
    Получить глобальный экземпляр MOEXClient

    WARNING: Предпочтительнее использовать context manager:
        with MOEXClient() as client: ...

    Глобальный клиент не закрывается автоматически.
    """
    global _global_client
    with _global_client_lock:
        if _global_client is None:
            _global_client = MOEXClient()
            _global_client.__enter__()
        return _global_client


def close_client():
    """Закрыть глобальный клиент"""
    global _global_client
    with _global_client_lock:
        if _global_client is not None:
            _global_client.__exit__(None, None, None)
            _global_client = None
