"""
Форматирование сигналов для различных каналов отправки
"""
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FormattedSignal:
    """Отформатированный сигнал"""
    content: str
    content_type: str  # "json", "text", "html"
    metadata: Dict[str, Any]


class SignalFormatter(ABC):
    """Базовый класс форматтера сигналов"""
    
    @abstractmethod
    def format(self, signal: Any) -> FormattedSignal:
        """
        Отформатировать одиночный сигнал
        
        Args:
            signal: Торговый сигнал
            
        Returns:
            FormattedSignal
        """
        pass
    
    @abstractmethod
    def format_batch(self, signals: List[Any]) -> FormattedSignal:
        """
        Отформатировать пакет сигналов
        
        Args:
            signals: Список сигналов
            
        Returns:
            FormattedSignal
        """
        pass


class JSONFormatter(SignalFormatter):
    """Форматтер для JSON"""
    
    def __init__(self, pretty: bool = False):
        """
        Инициализация
        
        Args:
            pretty: Форматировать с отступами
        """
        self.pretty = pretty
    
    def format(self, signal: Any) -> FormattedSignal:
        """Отформатировать сигнал в JSON"""
        if hasattr(signal, 'to_dict'):
            data = signal.to_dict()
        elif isinstance(signal, dict):
            data = signal
        else:
            data = {"signal": str(signal)}
        
        # Добавляем метаданные
        data["_meta"] = {
            "formatted_at": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        if self.pretty:
            content = json.dumps(data, indent=2, ensure_ascii=False)
        else:
            content = json.dumps(data, ensure_ascii=False)
        
        return FormattedSignal(
            content=content,
            content_type="json",
            metadata={"signal_type": type(signal).__name__}
        )
    
    def format_batch(self, signals: List[Any]) -> FormattedSignal:
        """Отформатировать пакет сигналов в JSON"""
        data = {
            "signals": [],
            "count": len(signals),
            "generated_at": datetime.now().isoformat()
        }
        
        for signal in signals:
            if hasattr(signal, 'to_dict'):
                data["signals"].append(signal.to_dict())
            elif isinstance(signal, dict):
                data["signals"].append(signal)
            else:
                data["signals"].append({"signal": str(signal)})
        
        if self.pretty:
            content = json.dumps(data, indent=2, ensure_ascii=False)
        else:
            content = json.dumps(data, ensure_ascii=False)
        
        return FormattedSignal(
            content=content,
            content_type="json",
            metadata={"signal_count": len(signals)}
        )


class TelegramFormatter(SignalFormatter):
    """Форматтер для Telegram"""
    
    # Эмодзи для типов сигналов
    SIGNAL_EMOJI = {
        "STRONG_BUY": "🟢🟢",
        "BUY": "🟢",
        "NEUTRAL": "⚪",
        "SELL": "🔴",
        "STRONG_SELL": "🔴🔴",
        "NO_DATA": "❓"
    }
    
    # Эмодзи для направлений
    DIRECTION_EMOJI = {
        "LONG_SHORT": "📈",
        "SHORT_LONG": "📉",
        "FLAT": "➡️"
    }
    
    def __init__(self, include_details: bool = True):
        """
        Инициализация
        
        Args:
            include_details: Включать детальную информацию
        """
        self.include_details = include_details
    
    def format(self, signal: Any) -> FormattedSignal:
        """Отформатировать сигнал для Telegram"""
        if hasattr(signal, 'to_dict'):
            data = signal.to_dict()
        elif isinstance(signal, dict):
            data = signal
        else:
            data = {"signal": str(signal)}
        
        lines = self._build_message(data)
        content = "\n".join(lines)
        
        return FormattedSignal(
            content=content,
            content_type="html",
            metadata={"parse_mode": "HTML"}
        )
    
    def format_batch(self, signals: List[Any]) -> FormattedSignal:
        """Отформатировать пакет сигналов для Telegram"""
        lines = [
            "<b>📊 OFZ Analytics - Торговые сигналы</b>",
            f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            f"🔢 Сигналов: {len(signals)}",
            ""
        ]
        
        for signal in signals:
            if hasattr(signal, 'to_dict'):
                data = signal.to_dict()
            elif isinstance(signal, dict):
                data = signal
            else:
                continue
            
            # Краткий формат для пакета
            signal_type = data.get("signal_type", "UNKNOWN")
            emoji = self.SIGNAL_EMOJI.get(signal_type, "❓")
            pair = data.get("pair_name", "N/A")
            spread = data.get("spread_bp", 0)
            
            lines.append(f"{emoji} <b>{pair}</b>")
            lines.append(f"   Спред: {spread:.1f} б.п.")
            
            if self.include_details:
                direction = data.get("direction", "FLAT")
                dir_emoji = self.DIRECTION_EMOJI.get(direction, "➡️")
                lines.append(f"   Направление: {dir_emoji} {direction}")
            
            lines.append("")
        
        content = "\n".join(lines)
        
        return FormattedSignal(
            content=content,
            content_type="html",
            metadata={"parse_mode": "HTML"}
        )
    
    def _build_message(self, data: Dict[str, Any]) -> List[str]:
        """Построить сообщение"""
        signal_type = data.get("signal_type", "UNKNOWN")
        emoji = self.SIGNAL_EMOJI.get(signal_type, "❓")
        
        lines = [
            f"<b>{emoji} {signal_type}</b>",
            "",
            f"📋 <b>Пара:</b> {data.get('pair_name', 'N/A')}",
        ]
        
        direction = data.get("direction", "FLAT")
        dir_emoji = self.DIRECTION_EMOJI.get(direction, "➡️")
        lines.append(f"📍 <b>Направление:</b> {dir_emoji} {direction}")
        
        if self.include_details:
            lines.extend([
                "",
                "<b>📊 Параметры:</b>",
                f"  • Спред: {data.get('spread_bp', 0):.1f} б.п.",
                f"  • Средний: {data.get('spread_mean', 0):.1f} б.п.",
                f"  • Z-score: {data.get('spread_zscore', 0):.2f}",
                f"  • Перцентиль: {data.get('percentile_rank', 50):.1f}%",
                "",
                "<b>💰 Прогноз:</b>",
                f"  • Ожидаемый возврат: {data.get('expected_return_bp', 0):.1f} б.п.",
                f"  • Уверенность: {data.get('confidence', 0)*100:.0f}%",
            ])
        
        lines.extend([
            "",
            f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            "<i>OFZ Analytics Bot</i>"
        ])
        
        return lines


class WebhookFormatter(SignalFormatter):
    """Форматтер для Webhook"""
    
    def __init__(self, custom_fields: Optional[Dict[str, Any]] = None):
        """
        Инициализация
        
        Args:
            custom_fields: Дополнительные поля для включения
        """
        self.custom_fields = custom_fields or {}
    
    def format(self, signal: Any) -> FormattedSignal:
        """Отформатировать сигнал для Webhook"""
        if hasattr(signal, 'to_dict'):
            data = signal.to_dict()
        elif isinstance(signal, dict):
            data = signal
        else:
            data = {"signal": str(signal)}
        
        # Структура webhook
        webhook_data = {
            "event": "signal_generated",
            "timestamp": datetime.now().isoformat(),
            "data": data,
            **self.custom_fields
        }
        
        content = json.dumps(webhook_data, ensure_ascii=False)
        
        return FormattedSignal(
            content=content,
            content_type="json",
            metadata={"event": "signal_generated"}
        )
    
    def format_batch(self, signals: List[Any]) -> FormattedSignal:
        """Отформатировать пакет сигналов для Webhook"""
        signals_data = []
        
        for signal in signals:
            if hasattr(signal, 'to_dict'):
                signals_data.append(signal.to_dict())
            elif isinstance(signal, dict):
                signals_data.append(signal)
        
        webhook_data = {
            "event": "batch_signals",
            "timestamp": datetime.now().isoformat(),
            "count": len(signals_data),
            "signals": signals_data,
            **self.custom_fields
        }
        
        content = json.dumps(webhook_data, ensure_ascii=False)
        
        return FormattedSignal(
            content=content,
            content_type="json",
            metadata={"event": "batch_signals", "count": len(signals)}
        )


class CSVFormatter(SignalFormatter):
    """Форматтер для CSV"""
    
    def __init__(self, delimiter: str = ","):
        """
        Инициализация
        
        Args:
            delimiter: Разделитель
        """
        self.delimiter = delimiter
    
    def format(self, signal: Any) -> FormattedSignal:
        """Не поддерживается для одиночного сигнала"""
        raise NotImplementedError("CSV formatter only supports batch formatting")
    
    def format_batch(self, signals: List[Any]) -> FormattedSignal:
        """Отформатировать пакет сигналов в CSV"""
        if not signals:
            return FormattedSignal(
                content="",
                content_type="csv",
                metadata={"signal_count": 0}
            )
        
        # Собираем все ключи
        all_keys = set()
        signal_dicts = []
        
        for signal in signals:
            if hasattr(signal, 'to_dict'):
                data = signal.to_dict()
            elif isinstance(signal, dict):
                data = signal
            else:
                data = {"signal": str(signal)}
            
            signal_dicts.append(data)
            all_keys.update(data.keys())
        
        # Сортируем ключи
        keys = sorted(all_keys)
        
        # Строим CSV
        lines = [self.delimiter.join(keys)]
        
        for data in signal_dicts:
            row = []
            for key in keys:
                value = data.get(key, "")
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                row.append(str(value))
            lines.append(self.delimiter.join(row))
        
        content = "\n".join(lines)
        
        return FormattedSignal(
            content=content,
            content_type="csv",
            metadata={"signal_count": len(signals)}
        )


def get_formatter(format_type: str, **kwargs) -> SignalFormatter:
    """
    Получить форматтер по типу
    
    Args:
        format_type: Тип форматтера ("json", "telegram", "webhook", "csv")
        **kwargs: Аргументы для форматтера
        
    Returns:
        SignalFormatter
    """
    formatters = {
        "json": JSONFormatter,
        "telegram": TelegramFormatter,
        "webhook": WebhookFormatter,
        "csv": CSVFormatter
    }
    
    formatter_class = formatters.get(format_type.lower())
    
    if not formatter_class:
        raise ValueError(f"Unknown formatter type: {format_type}")
    
    return formatter_class(**kwargs)
