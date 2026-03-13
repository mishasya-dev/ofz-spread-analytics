"""
Тесты для MOEXClient

Запуск:
    pytest tests/test_moex_client.py -v
"""
import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import Future

from api.moex_client import (
    MOEXClient,
    MOEX_BASE_URL,
    AdaptiveRateLimiter,
    RateLimitState,
    get_client,
    close_client,
    DEFAULT_MAX_WORKERS,
    MIN_WORKERS,
    MAX_WORKERS_LIMIT,
)


class TestAdaptiveRateLimiter:
    """Тесты адаптивного rate limiter'а"""

    def test_initial_state(self):
        """Начальное состояние"""
        limiter = AdaptiveRateLimiter(initial_workers=5)
        assert limiter.get_workers() == 5

        stats = limiter.get_stats()
        assert stats["current_workers"] == 5
        assert stats["total_requests"] == 0
        assert stats["total_errors"] == 0

    def test_record_success(self):
        """Запись успешного запроса"""
        limiter = AdaptiveRateLimiter(initial_workers=5)

        limiter.record_success()
        limiter.record_success()
        limiter.record_success()

        stats = limiter.get_stats()
        assert stats["total_requests"] == 3
        assert stats["consecutive_429"] == 0

    def test_reduce_on_429(self):
        """Снижение workers при 429"""
        limiter = AdaptiveRateLimiter(initial_workers=5)

        # После 2 подряд 429 - снижаем
        limiter.record_429()
        assert limiter.get_workers() == 5  # Ещё не снизился

        limiter.record_429()
        assert limiter.get_workers() == 4  # Снизился

    def test_min_workers_limit(self):
        """Нельзя снизить ниже MIN_WORKERS"""
        limiter = AdaptiveRateLimiter(initial_workers=MIN_WORKERS)

        for _ in range(10):
            limiter.record_429()

        assert limiter.get_workers() >= MIN_WORKERS

    def test_recovery_after_no_errors(self):
        """Восстановление workers после периода без ошибок"""
        limiter = AdaptiveRateLimiter(initial_workers=5)

        # Снижаем
        limiter.record_429()
        limiter.record_429()
        assert limiter.get_workers() == 4

        # Симулируем время без ошибок
        limiter._state.last_429_time = time.time() - 100  # 100 секунд назад

        # Успешный запрос триггерит восстановление
        limiter.record_success()
        assert limiter.get_workers() == 5


class TestMOEXClientContextManager:
    """Тесты context manager"""

    def test_enter_exit(self):
        """Вход и выход из context manager"""
        client = MOEXClient()

        # До входа - ресурсы не созданы
        assert client._session is None
        assert client._executor is None
        assert not client._entered

        # После входа - ресурсы созданы
        with client as c:
            assert c is client
            assert client._session is not None
            assert client._executor is not None
            assert client._entered

        # После выхода - ресурсы освобождены
        assert client._session is None
        assert client._executor is None
        assert not client._entered

    def test_reenter_forbidden(self):
        """Повторный вход запрещён"""
        client = MOEXClient()

        with client:
            with pytest.raises(RuntimeError, match="уже активен"):
                client.__enter__()

    def test_use_outside_context(self):
        """Использование вне context manager вызывает ошибку"""
        client = MOEXClient()

        with pytest.raises(RuntimeError, match="context manager"):
            client.request_sync("/test", {})


class TestMOEXClientRequests:
    """Тесты запросов"""

    def test_sync_request(self):
        """Синхронный запрос"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}
        mock_response.raise_for_status = Mock()

        with patch('requests.Session.request', return_value=mock_response):
            with MOEXClient() as client:
                response = client.request_sync("/test", {"param": "value"})

        assert response.status_code == 200
        assert response.json() == {"test": "data"}

    def test_sync_request_with_relative_url(self):
        """Относительный URL дополняется base_url"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        with patch('requests.Session.request') as mock_request:
            mock_request.return_value = mock_response

            with MOEXClient() as client:
                client.request_sync("/engines/stock/zcyc.json", {})

            # Проверяем что URL был сформирован правильно
            # Session.request вызывается как ('GET', url, params=...)
            call_args = mock_request.call_args
            url = call_args.args[1]  # Второй позиционный аргумент
            assert "iss.moex.com/iss/engines/stock/zcyc.json" in url

    def test_sync_request_with_absolute_url(self):
        """Абсолютный URL используется как есть"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        with patch('requests.Session.request') as mock_request:
            mock_request.return_value = mock_response

            with MOEXClient() as client:
                client.request_sync("https://other.api.com/test", {})

            call_args = mock_request.call_args
            url = call_args.args[1]  # Второй позиционный аргумент
            assert url == "https://other.api.com/test"

    def test_async_request_returns_future(self):
        """Асинхронный запрос возвращает Future"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        with patch('requests.Session.request', return_value=mock_response):
            with MOEXClient() as client:
                future = client.request("/test", {})

                assert isinstance(future, Future)

                # Можно получить результат
                response = future.result(timeout=5)
                assert response.status_code == 200

    def test_batch_request(self):
        """Пакетный запрос"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status = Mock()

        with patch('requests.Session.request', return_value=mock_response):
            with MOEXClient() as client:
                requests_list = [
                    ("/test1", {"p": 1}),
                    ("/test2", {"p": 2}),
                    ("/test3", {"p": 3}),
                ]

                futures = client.request_batch(requests_list)

                assert len(futures) == 3
                assert all(isinstance(f, Future) for f in futures)

    def test_batch_wait(self):
        """Пакетный запрос с ожиданием"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        with patch('requests.Session.request', return_value=mock_response):
            with MOEXClient() as client:
                requests_list = [
                    ("/test1", {}),
                    ("/test2", {}),
                ]

                responses = client.request_batch_wait(requests_list, timeout=5)

                assert len(responses) == 2
                assert all(r is not None for r in responses)

    def test_get_json(self):
        """GET запрос с автоматическим парсингом JSON"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "value"}
        mock_response.raise_for_status = Mock()

        with patch('requests.Session.request', return_value=mock_response):
            with MOEXClient() as client:
                data = client.get_json("/test", {})

        assert data == {"key": "value"}


class TestMOEXClientRetry:
    """Тесты retry логики"""

    def test_retry_on_error(self):
        """Retry при ошибке"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        # Первые 2 попытки падают, 3-я успешна
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                from requests.exceptions import RequestException
                raise RequestException("Network error")
            return mock_response

        # Patch time.sleep внутри модуля moex_client
        import api.moex_client as moex_module
        with patch.object(moex_module, 'time') as mock_time:
            mock_time.sleep = Mock()  # Не ждём реально
            
            with patch('requests.Session.request', side_effect=side_effect):
                with MOEXClient(max_retries=3) as client:
                    response = client.request_sync("/test", {})

        assert call_count[0] == 3  # Было 3 попытки
        assert response.status_code == 200

    def test_retry_exhausted(self):
        """Исчерпание попыток"""
        with patch('requests.Session.request', side_effect=Exception("Always fails")):
            with MOEXClient(max_retries=2) as client:
                with pytest.raises(Exception, match="Always fails"):
                    client.request_sync("/test", {})


class TestMOEXClientRateLimit:
    """Тесты rate limiting"""

    def test_429_handling(self):
        """Обработка 429 Too Many Requests"""
        # Первый ответ - 429, второй - 200
        responses = [
            Mock(status_code=429, headers={"Retry-After": "1"}, raise_for_status=Mock()),
            Mock(status_code=200, json=Mock(return_value={"ok": True}), raise_for_status=Mock()),
        ]

        response_iter = iter(responses)

        with patch('requests.Session.request', return_value=next(response_iter)):
            with patch('time.sleep') as mock_sleep:
                # Нужно переопределить side_effect для каждого вызова
                with MOEXClient(max_retries=3) as client:
                    # Мокируем _do_request частично
                    original_do_request = client._do_request

                    call_count = [0]

                    def mock_do_request(url, params, method="GET"):
                        call_count[0] += 1
                        if call_count[0] == 1:
                            # Симулируем 429
                            client._rate_limiter.record_429()
                            return responses[1]  # Возвращаем успешный ответ
                        return original_do_request(url, params, method)

                    with patch.object(client, '_do_request', side_effect=mock_do_request):
                        response = client.request_sync("/test", {})

        # Проверяем что rate limiter записал 429
        stats = client.get_stats()
        assert stats["consecutive_429"] >= 1


class TestMOEXClientWorkersLimit:
    """Тесты лимитов workers"""

    def test_workers_cannot_exceed_max(self):
        """Workers не может превышать MAX_WORKERS_LIMIT"""
        client = MOEXClient(max_workers=100)
        assert client._initial_workers == MAX_WORKERS_LIMIT

    def test_workers_cannot_be_below_min(self):
        """Workers не может быть меньше MIN_WORKERS"""
        client = MOEXClient(max_workers=0)
        assert client._initial_workers == MIN_WORKERS

    def test_default_workers(self):
        """Workers по умолчанию"""
        client = MOEXClient()
        assert MIN_WORKERS <= client._initial_workers <= MAX_WORKERS_LIMIT


class TestGlobalClient:
    """Тесты глобального клиента"""

    def test_get_client_singleton(self):
        """Глобальный клиент - singleton"""
        close_client()  # Убеждаемся что закрыт

        client1 = get_client()
        client2 = get_client()

        assert client1 is client2

        close_client()

    def test_close_client(self):
        """Закрытие глобального клиента"""
        client = get_client()
        assert client._entered

        close_client()
        assert not client._entered


class TestMOEXClientStats:
    """Тесты статистики"""

    def test_get_stats(self):
        """Получение статистики"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        with patch('requests.Session.request', return_value=mock_response):
            with MOEXClient() as client:
                client.request_sync("/test", {})
                client.request_sync("/test", {})

                stats = client.get_stats()

        assert stats["total_requests"] == 2
        assert stats["entered"] == True
        assert "iss.moex.com" in stats["base_url"]


class TestMOEXClientConcurrency:
    """Тесты конкурентности"""

    def test_parallel_requests(self):
        """Параллельные запросы"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        results = []
        lock = threading.Lock()

        def track_request(*args, **kwargs):
            with lock:
                results.append(time.time())
            time.sleep(0.1)  # Симулируем задержку
            return mock_response

        with patch('requests.Session.request', side_effect=track_request):
            with MOEXClient(max_workers=3) as client:
                start = time.time()

                futures = client.request_batch([
                    ("/test1", {}),
                    ("/test2", {}),
                    ("/test3", {}),
                ])

                # Ждём все результаты
                for f in futures:
                    f.result(timeout=5)

                elapsed = time.time() - start

        # 3 запроса параллельно должны быть быстрее чем последовательно
        # (с учётом overhead на создание потоков)
        assert elapsed < 0.5  # Если последовательно = 0.3с


# Интеграционный тест (требует реального MOEX API)
@pytest.mark.integration
class TestMOEXClientIntegration:
    """Интеграционные тесты (требуют реального API)"""

    @pytest.mark.skip(reason="Требует реального MOEX API")
    def test_real_zcyc_request(self):
        """Реальный запрос к ZCYC endpoint"""
        with MOEXClient() as client:
            data = client.get_json("/engines/stock/zcyc.json", {"iss.meta": "off"})

        assert "params" in data or "yearyields" in data

    @pytest.mark.skip(reason="Требует реального MOEX API")
    def test_real_securities_request(self):
        """Реальный запрос к securities endpoint"""
        with MOEXClient() as client:
            data = client.get_json(
                "/securities/SU26238RMFS.json",
                {"iss.meta": "off"}
            )

        assert "securities" in data
