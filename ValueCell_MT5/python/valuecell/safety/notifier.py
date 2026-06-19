"""
Notification System - Alert mechanism for trading events

Sends notifications via:
1. Telegram Bot (primary)
2. Console/File logs (always)
3. Discord Webhook (optional - TODO)

Events:
- Trade execution (BUY/SELL)
- Position closed (TP/SL hit)
- Signal rejected
- Circuit breaker opened
- System errors
- Daily summary
"""

import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
from enum import Enum


class NotificationType(Enum):
    """Notification types with emojis"""
    TRADE_OPENED = "🟢"
    TRADE_CLOSED = "🔴"
    SIGNAL_REJECTED = "❌"
    CIRCUIT_BREAKER = "🚨"
    SYSTEM_ERROR = "⚠️"
    DAILY_SUMMARY = "📊"
    INFO = "ℹ️"


class Notifier:
    """
    Notification System - Sends alerts via Telegram and other channels.
    
    Features:
    - Telegram bot integration
    - Message formatting with emojis
    - Error handling (silent failures)
    - Rate limiting (prevent spam)
    - Configurable channels
    """
    
    def __init__(
        self,
        telegram_enabled: bool = True,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None
    ):
        """
        Initialize Notifier.
        
        Args:
            telegram_enabled: Enable Telegram notifications
            telegram_bot_token: Telegram bot token (from .env or param)
            telegram_chat_id: Telegram chat ID (from .env or param)
        """
        self.name = "Notifier"
        self.version = "1.0.0"
        
        # Telegram configuration
        self.telegram_enabled = telegram_enabled
        self.telegram_bot_token = telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        
        # Validate Telegram config
        if self.telegram_enabled:
            if not self.telegram_bot_token or not self.telegram_chat_id:
                logger.warning(
                    "⚠️ Telegram enabled but credentials missing! "
                    "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"
                )
                self.telegram_enabled = False
            else:
                logger.info(f"✅ {self.name} v{self.version} initialized | Telegram: Enabled")
        else:
            logger.info(f"✅ {self.name} v{self.version} initialized | Telegram: Disabled")
        
        # Rate limiting
        self.last_notification_time = {}
        self.min_interval_seconds = 5  # Minimum 5s between same notification types
    
    def notify_trade_opened(
        self,
        signal: str,
        ticket: int,
        entry_price: float,
        lot_size: float,
        sl_price: float,
        tp_price: float,
        confidence: float
    ):
        """Notify when trade is opened"""
        message = f"""
{NotificationType.TRADE_OPENED.value} *TRADE OPENED*

*Signal:* {signal}
*Ticket:* #{ticket}
*Entry:* {entry_price:.2f}
*Lot Size:* {lot_size:.2f}
*SL:* {sl_price:.2f}
*TP:* {tp_price:.2f}
*Confidence:* {confidence:.1%}

_Time:_ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self._send_notification(message, NotificationType.TRADE_OPENED)
    
    def notify_trade_closed(
        self,
        ticket: int,
        signal: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        close_reason: str
    ):
        """Notify when trade is closed"""
        emoji = "✅" if pnl > 0 else "❌"
        pnl_text = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}"
        
        message = f"""
{NotificationType.TRADE_CLOSED.value} *TRADE CLOSED* {emoji}

*Ticket:* #{ticket}
*Signal:* {signal}
*Entry:* {entry_price:.2f}
*Exit:* {exit_price:.2f}
*P&L:* {pnl_text}
*Reason:* {close_reason}

_Time:_ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self._send_notification(message, NotificationType.TRADE_CLOSED)
    
    def notify_signal_rejected(
        self,
        signal: str,
        reason: str,
        confidence: float
    ):
        """Notify when signal is rejected"""
        message = f"""
{NotificationType.SIGNAL_REJECTED.value} *SIGNAL REJECTED*

*Signal:* {signal}
*Confidence:* {confidence:.1%}
*Reason:* {reason}

_Time:_ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self._send_notification(message, NotificationType.SIGNAL_REJECTED)
    
    def notify_circuit_breaker_opened(
        self,
        breaker_type: str,
        reason: str,
        cooldown_minutes: int
    ):
        """Notify when circuit breaker opens"""
        message = f"""
{NotificationType.CIRCUIT_BREAKER.value} *CIRCUIT BREAKER OPENED!*

⚠️ *ALL TRADING IS BLOCKED* ⚠️

*Type:* {breaker_type}
*Reason:* {reason}
*Cooldown:* {cooldown_minutes} minutes

_Time:_ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self._send_notification(message, NotificationType.CIRCUIT_BREAKER, force=True)
    
    def notify_system_error(
        self,
        error: str,
        context: str = ""
    ):
        """Notify system error"""
        message = f"""
{NotificationType.SYSTEM_ERROR.value} *SYSTEM ERROR*

*Error:* {error}
{f'*Context:* {context}' if context else ''}

_Time:_ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self._send_notification(message, NotificationType.SYSTEM_ERROR)
    
    def notify_daily_summary(
        self,
        total_trades: int,
        wins: int,
        losses: int,
        total_pnl: float,
        win_rate: float
    ):
        """Notify daily trading summary"""
        emoji = "✅" if total_pnl > 0 else "❌"
        pnl_text = f"+${total_pnl:.2f}" if total_pnl > 0 else f"-${abs(total_pnl):.2f}"
        
        message = f"""
{NotificationType.DAILY_SUMMARY.value} *DAILY SUMMARY* {emoji}

*Total Trades:* {total_trades}
*Wins:* {wins}
*Losses:* {losses}
*Win Rate:* {win_rate:.1%}
*Total P&L:* {pnl_text}

_Date:_ {datetime.now().strftime('%Y-%m-%d')}
"""
        self._send_notification(message, NotificationType.DAILY_SUMMARY)
    
    def notify_info(self, message: str):
        """Send info notification"""
        formatted_message = f"""
{NotificationType.INFO.value} *INFO*

{message}

_Time:_ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self._send_notification(formatted_message, NotificationType.INFO)
    
    def _send_notification(
        self,
        message: str,
        notification_type: NotificationType,
        force: bool = False
    ):
        """
        Send notification via configured channels.
        
        Args:
            message: Message text
            notification_type: Type of notification
            force: Force send (ignore rate limiting)
        """
        # Check rate limiting
        if not force and not self._check_rate_limit(notification_type):
            logger.debug(f"Rate limit: Skipping {notification_type.name} notification")
            return
        
        # Always log to console
        logger.info(f"📢 Notification: {notification_type.name}")
        
        # Send via Telegram
        if self.telegram_enabled:
            self._send_telegram(message)
    
    def _send_telegram(self, message: str):
        """Send message via Telegram Bot API"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=payload, timeout=5)
            
            if response.status_code == 200:
                logger.debug("✅ Telegram notification sent")
            else:
                logger.warning(f"⚠️ Telegram notification failed: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"⚠️ Telegram notification error: {e}")
    
    def _check_rate_limit(self, notification_type: NotificationType) -> bool:
        """
        Check if notification can be sent (rate limiting).
        
        Returns:
            True if allowed, False if rate limited
        """
        now = datetime.now()
        last_time = self.last_notification_time.get(notification_type)
        
        if last_time:
            elapsed = (now - last_time).total_seconds()
            if elapsed < self.min_interval_seconds:
                return False
        
        self.last_notification_time[notification_type] = now
        return True
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Telegram connection"""
        if not self.telegram_enabled:
            return {
                "success": False,
                "message": "Telegram not enabled"
            }
        
        try:
            # Send test message
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": "✅ Test notification from Trading System\n\nTelegram connection is working!"
            }
            
            response = requests.post(url, json=payload, timeout=5)
            
            if response.status_code == 200:
                logger.info("✅ Telegram test notification sent successfully")
                return {
                    "success": True,
                    "message": "Telegram connection successful"
                }
            else:
                logger.error(f"❌ Telegram test failed: {response.status_code}")
                return {
                    "success": False,
                    "message": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"❌ Telegram test error: {e}")
            return {
                "success": False,
                "message": str(e)
            }
    
    def get_info(self) -> Dict[str, Any]:
        """Get notifier information"""
        return {
            "name": self.name,
            "version": self.version,
            "telegram": {
                "enabled": self.telegram_enabled,
                "configured": bool(self.telegram_bot_token and self.telegram_chat_id)
            },
            "rate_limit_seconds": self.min_interval_seconds
        }


# ========== STANDALONE TESTING ==========

if __name__ == "__main__":
    logger.info("Testing Notifier...")
    
    # Initialize (will try to load from .env)
    notifier = Notifier(telegram_enabled=True)
    
    # Get info
    info = notifier.get_info()
    logger.info(f"Notifier: {info['name']} v{info['version']}")
    logger.info(f"Telegram enabled: {info['telegram']['enabled']}")
    logger.info(f"Telegram configured: {info['telegram']['configured']}")
    
    # Test connection (if configured)
    if info['telegram']['enabled'] and info['telegram']['configured']:
        logger.info("\nTesting Telegram connection...")
        result = notifier.test_connection()
        logger.info(f"Result: {result['message']}")
    else:
        logger.info("\nTelegram not configured - skipping test")
        logger.info("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env to enable")
    
    logger.info("\n✅ Notifier test complete!")
