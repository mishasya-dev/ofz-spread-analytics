"""
Отправка торговых сигналов в различные системы
"""
import json
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
import logging
import time

from .formatters import (
    SignalFormatter,
    JSONFormatter,
    TelegramFormatter,
    WebhookFormatter,
    get_formatter
)

logger = logging.getLogger(__name__)


class SenderStatus(Enum):
    """Статус отправки"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    PENDING = "pending"


@dataclass
class SenderResult:
    """Результат отправки"""
    status: SenderStatus
    message: str
    timestamp: datetime
    channel: str
    response_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "channel": self.channel,
            "response_data": self.response_data,
            "error": self.error
        }


class BaseSender(ABC):
    """Базовый класс отправителя"""
    
    @abstractmethod
    def send(self, signal: Any) -> SenderResult:
        """Отправить сигнал"""
        pass
    
    @abstractmethod
    def send_batch(self, signals: List[Any]) -> SenderResult:
        """Отправить пакет сигналов"""
        pass


class WebhookSender(BaseSender):
    """Отправитель через Webhook"""
    
    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        retries: int = 3,
        custom_fields: Optional[Dict[str, Any]] = None
    ):
        """
        Инициализация
        
        Args:
            url: URL webhook
            headers: Дополнительные заголовки
            timeout: Таймаут запроса
            retries: Количество повторных попыток
            custom_fields: Дополнительные поля в payload
        """
        self.url = url
        self.headers = headers or {}
        self.headers.setdefault("Content-Type", "application/json")
        self.timeout = timeout
        self.retries = retries
        self.formatter = WebhookFormatter(custom_fields)
    
    def send(self, signal: Any) -> SenderResult:
        """Отправить сигнал через webhook"""
        formatted = self.formatter.format(signal)
        
        for attempt in range(self.retries):
            try:
                response = requests.post(
                    self.url,
                    data=formatted.content,
                    headers=self.headers,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                
                return SenderResult(
                    status=SenderStatus.SUCCESS,
                    message="Signal sent successfully",
                    timestamp=datetime.now(),
                    channel="webhook",
                    response_data={"status_code": response.status_code}
                )
                
            except requests.exceptions.Timeout:
                logger.warning(f"Webhook timeout, attempt {attempt + 1}")
                time.sleep(1)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Webhook error: {e}")
                if attempt == self.retries - 1:
                    return SenderResult(
                        status=SenderStatus.FAILED,
                        message=f"Failed to send signal: {e}",
                        timestamp=datetime.now(),
                        channel="webhook",
                        error=str(e)
                    )
                time.sleep(1)
        
        return SenderResult(
            status=SenderStatus.TIMEOUT,
            message="Webhook request timed out",
            timestamp=datetime.now(),
            channel="webhook"
        )
    
    def send_batch(self, signals: List[Any]) -> SenderResult:
        """Отправить пакет сигналов"""
        formatted = self.formatter.format_batch(signals)
        
        for attempt in range(self.retries):
            try:
                response = requests.post(
                    self.url,
                    data=formatted.content,
                    headers=self.headers,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                
                return SenderResult(
                    status=SenderStatus.SUCCESS,
                    message=f"Batch of {len(signals)} signals sent successfully",
                    timestamp=datetime.now(),
                    channel="webhook",
                    response_data={"status_code": response.status_code}
                )
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Webhook batch error: {e}")
                if attempt == self.retries - 1:
                    return SenderResult(
                        status=SenderStatus.FAILED,
                        message=f"Failed to send batch: {e}",
                        timestamp=datetime.now(),
                        channel="webhook",
                        error=str(e)
                    )
                time.sleep(1)
        
        return SenderResult(
            status=SenderStatus.TIMEOUT,
            message="Webhook batch request timed out",
            timestamp=datetime.now(),
            channel="webhook"
        )


class TelegramSender(BaseSender):
    """Отправитель в Telegram"""
    
    API_URL = "https://api.telegram.org/bot{token}/sendMessage"
    
    def __init__(
        self,
        token: str,
        chat_id: str,
        timeout: int = 30,
        retries: int = 3,
        parse_mode: str = "HTML"
    ):
        """
        Инициализация
        
        Args:
            token: Токен бота Telegram
            chat_id: ID чата или канала
            timeout: Таймаут запроса
            retries: Количество повторных попыток
            parse_mode: Режим парсинга (HTML, Markdown)
        """
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout
        self.retries = retries
        self.parse_mode = parse_mode
        self.formatter = TelegramFormatter()
    
    def send(self, signal: Any) -> SenderResult:
        """Отправить сигнал в Telegram"""
        formatted = self.formatter.format(signal)
        
        url = self.API_URL.format(token=self.token)
        
        payload = {
            "chat_id": self.chat_id,
            "text": formatted.content,
            "parse_mode": self.parse_mode
        }
        
        for attempt in range(self.retries):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                result = response.json()
                
                if result.get("ok"):
                    return SenderResult(
                        status=SenderStatus.SUCCESS,
                        message="Signal sent to Telegram",
                        timestamp=datetime.now(),
                        channel="telegram",
                        response_data=result
                    )
                else:
                    return SenderResult(
                        status=SenderStatus.FAILED,
                        message=f"Telegram API error: {result.get('description')}",
                        timestamp=datetime.now(),
                        channel="telegram",
                        error=result.get('description')
                    )
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Telegram error: {e}")
                if attempt == self.retries - 1:
                    return SenderResult(
                        status=SenderStatus.FAILED,
                        message=f"Failed to send to Telegram: {e}",
                        timestamp=datetime.now(),
                        channel="telegram",
                        error=str(e)
                    )
                time.sleep(1)
        
        return SenderResult(
            status=SenderStatus.TIMEOUT,
            message="Telegram request timed out",
            timestamp=datetime.now(),
            channel="telegram"
        )
    
    def send_batch(self, signals: List[Any]) -> SenderResult:
        """Отправить пакет сигналов в Telegram"""
        formatted = self.formatter.format_batch(signals)
        
        url = self.API_URL.format(token=self.token)
        
        payload = {
            "chat_id": self.chat_id,
            "text": formatted.content,
            "parse_mode": self.parse_mode
        }
        
        for attempt in range(self.retries):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                result = response.json()
                
                if result.get("ok"):
                    return SenderResult(
                        status=SenderStatus.SUCCESS,
                        message=f"Batch of {len(signals)} signals sent to Telegram",
                        timestamp=datetime.now(),
                        channel="telegram",
                        response_data=result
                    )
                else:
                    return SenderResult(
                        status=SenderStatus.FAILED,
                        message=f"Telegram API error: {result.get('description')}",
                        timestamp=datetime.now(),
                        channel="telegram",
                        error=result.get('description')
                    )
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Telegram batch error: {e}")
                if attempt == self.retries - 1:
                    return SenderResult(
                        status=SenderStatus.FAILED,
                        message=f"Failed to send batch to Telegram: {e}",
                        timestamp=datetime.now(),
                        channel="telegram",
                        error=str(e)
                    )
                time.sleep(1)
        
        return SenderResult(
            status=SenderStatus.TIMEOUT,
            message="Telegram batch request timed out",
            timestamp=datetime.now(),
            channel="telegram"
        )


class APISender(BaseSender):
    """Отправитель через REST API"""
    
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        retries: int = 3
    ):
        """
        Инициализация
        
        Args:
            endpoint: URL API endpoint
            api_key: API ключ
            headers: Дополнительные заголовки
            timeout: Таймаут запроса
            retries: Количество повторных попыток
        """
        self.endpoint = endpoint
        self.api_key = api_key
        self.headers = headers or {}
        self.headers.setdefault("Content-Type", "application/json")
        self.headers.setdefault("Authorization", f"Bearer {api_key}")
        self.timeout = timeout
        self.retries = retries
        self.formatter = JSONFormatter()
    
    def send(self, signal: Any) -> SenderResult:
        """Отправить сигнал через API"""
        formatted = self.formatter.format(signal)
        
        for attempt in range(self.retries):
            try:
                response = requests.post(
                    self.endpoint,
                    data=formatted.content,
                    headers=self.headers,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                
                return SenderResult(
                    status=SenderStatus.SUCCESS,
                    message="Signal sent via API",
                    timestamp=datetime.now(),
                    channel="api",
                    response_data=response.json() if response.content else None
                )
                
            except requests.exceptions.RequestException as e:
                logger.error(f"API error: {e}")
                if attempt == self.retries - 1:
                    return SenderResult(
                        status=SenderStatus.FAILED,
                        message=f"Failed to send via API: {e}",
                        timestamp=datetime.now(),
                        channel="api",
                        error=str(e)
                    )
                time.sleep(1)
        
        return SenderResult(
            status=SenderStatus.TIMEOUT,
            message="API request timed out",
            timestamp=datetime.now(),
            channel="api"
        )
    
    def send_batch(self, signals: List[Any]) -> SenderResult:
        """Отправить пакет сигналов через API"""
        formatted = self.formatter.format_batch(signals)
        
        for attempt in range(self.retries):
            try:
                response = requests.post(
                    self.endpoint,
                    data=formatted.content,
                    headers=self.headers,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                
                return SenderResult(
                    status=SenderStatus.SUCCESS,
                    message=f"Batch of {len(signals)} signals sent via API",
                    timestamp=datetime.now(),
                    channel="api",
                    response_data=response.json() if response.content else None
                )
                
            except requests.exceptions.RequestException as e:
                logger.error(f"API batch error: {e}")
                if attempt == self.retries - 1:
                    return SenderResult(
                        status=SenderStatus.FAILED,
                        message=f"Failed to send batch via API: {e}",
                        timestamp=datetime.now(),
                        channel="api",
                        error=str(e)
                    )
                time.sleep(1)
        
        return SenderResult(
            status=SenderStatus.TIMEOUT,
            message="API batch request timed out",
            timestamp=datetime.now(),
            channel="api"
        )


class SignalSender:
    """
    Главный класс для отправки сигналов
    
    Поддерживает множественные каналы отправки.
    """
    
    def __init__(self):
        """Инициализация"""
        self._senders: Dict[str, BaseSender] = {}
        self._history: List[Dict[str, Any]] = []
    
    def add_webhook(
        self,
        name: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> None:
        """
        Добавить webhook отправитель
        
        Args:
            name: Имя канала
            url: URL webhook
            headers: Заголовки
            **kwargs: Дополнительные параметры
        """
        self._senders[name] = WebhookSender(url, headers, **kwargs)
        logger.info(f"Added webhook sender: {name}")
    
    def add_telegram(
        self,
        name: str,
        token: str,
        chat_id: str,
        **kwargs
    ) -> None:
        """
        Добавить Telegram отправитель
        
        Args:
            name: Имя канала
            token: Токен бота
            chat_id: ID чата
            **kwargs: Дополнительные параметры
        """
        self._senders[name] = TelegramSender(token, chat_id, **kwargs)
        logger.info(f"Added Telegram sender: {name}")
    
    def add_api(
        self,
        name: str,
        endpoint: str,
        api_key: str,
        **kwargs
    ) -> None:
        """
        Добавить API отправитель
        
        Args:
            name: Имя канала
            endpoint: URL endpoint
            api_key: API ключ
            **kwargs: Дополнительные параметры
        """
        self._senders[name] = APISender(endpoint, api_key, **kwargs)
        logger.info(f"Added API sender: {name}")
    
    def send_to(
        self,
        channel: str,
        signal: Any
    ) -> SenderResult:
        """
        Отправить сигнал в конкретный канал
        
        Args:
            channel: Имя канала
            signal: Торговый сигнал
            
        Returns:
            SenderResult
        """
        if channel not in self._senders:
            return SenderResult(
                status=SenderStatus.FAILED,
                message=f"Unknown channel: {channel}",
                timestamp=datetime.now(),
                channel=channel,
                error="Channel not found"
            )
        
        sender = self._senders[channel]
        result = sender.send(signal)
        
        self._record_result(channel, result)
        
        return result
    
    def send_to_all(self, signal: Any) -> Dict[str, SenderResult]:
        """
        Отправить сигнал во все каналы
        
        Args:
            signal: Торговый сигнал
            
        Returns:
            Словарь {channel_name: SenderResult}
        """
        results = {}
        
        for name, sender in self._senders.items():
            result = sender.send(signal)
            results[name] = result
            self._record_result(name, result)
        
        return results
    
    def broadcast_batch(
        self,
        signals: List[Any],
        channels: Optional[List[str]] = None
    ) -> Dict[str, SenderResult]:
        """
        Разослать пакет сигналов
        
        Args:
            signals: Список сигналов
            channels: Список каналов (по умолчанию все)
            
        Returns:
            Словарь {channel_name: SenderResult}
        """
        results = {}
        
        target_channels = channels or list(self._senders.keys())
        
        for name in target_channels:
            if name not in self._senders:
                results[name] = SenderResult(
                    status=SenderStatus.FAILED,
                    message=f"Unknown channel: {name}",
                    timestamp=datetime.now(),
                    channel=name
                )
                continue
            
            sender = self._senders[name]
            result = sender.send_batch(signals)
            results[name] = result
            self._record_result(name, result)
        
        return results
    
    def get_history(
        self,
        limit: int = 100,
        channel: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Получить историю отправок
        
        Args:
            limit: Максимум записей
            channel: Фильтр по каналу
            
        Returns:
            Список записей истории
        """
        history = self._history
        
        if channel:
            history = [h for h in history if h.get("channel") == channel]
        
        return history[-limit:]
    
    def clear_history(self) -> None:
        """Очистить историю"""
        self._history.clear()
    
    def list_channels(self) -> List[str]:
        """Получить список каналов"""
        return list(self._senders.keys())
    
    def remove_channel(self, name: str) -> bool:
        """
        Удалить канал
        
        Args:
            name: Имя канала
            
        Returns:
            True если удалён
        """
        if name in self._senders:
            del self._senders[name]
            return True
        return False
    
    def _record_result(
        self,
        channel: str,
        result: SenderResult
    ) -> None:
        """Записать результат в историю"""
        record = {
            "channel": channel,
            "status": result.status.value,
            "message": result.message,
            "timestamp": result.timestamp.isoformat(),
            "error": result.error
        }
        
        self._history.append(record)
        
        # Ограничиваем историю
        if len(self._history) > 1000:
            self._history = self._history[-1000:]


def create_sender_from_config(config: Dict[str, Any]) -> SignalSender:
    """
    Создать SignalSender из конфигурации
    
    Args:
        config: Конфигурация с ключами:
            - webhooks: List[Dict] с полями name, url, headers
            - telegram: List[Dict] с полями name, token, chat_id
            - apis: List[Dict] с полями name, endpoint, api_key
            
    Returns:
        Настроенный SignalSender
    """
    sender = SignalSender()
    
    # Webhooks
    for wh in config.get("webhooks", []):
        sender.add_webhook(
            name=wh["name"],
            url=wh["url"],
            headers=wh.get("headers")
        )
    
    # Telegram
    for tg in config.get("telegram", []):
        sender.add_telegram(
            name=tg["name"],
            token=tg["token"],
            chat_id=tg["chat_id"]
        )
    
    # API endpoints
    for api in config.get("apis", []):
        sender.add_api(
            name=api["name"],
            endpoint=api["endpoint"],
            api_key=api["api_key"]
        )
    
    return sender