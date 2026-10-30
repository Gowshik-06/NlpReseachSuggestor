"""
DRIUT Notification Boundary & Dispatcher.

Provides a clean abstraction boundary for user notifications triggered by
newly discovered research updates and impact classifications.
Supports future multi-channel dispatch (Email, Webhooks, In-App WebSockets).
Currently runs in safe structured logging mode without sending real external emails or webhooks.
"""
from typing import Optional, Dict, Any
from app.core.logging import get_logger

logger = get_logger(__name__)


class NotificationDispatcher:
    def __init__(self, mode: str = "log_stub"):
        self.mode = mode
        self.dispatched_count = 0

    def dispatch_alert_notification(
        self,
        user_id: str,
        saved_paper_title: str,
        trigger_paper_title: str,
        relationship_type: str,
        confidence_score: float,
        explanation: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Dispatch notification to user about a newly classified research update.
        Safely records the event to logs without external side-effects.
        """
        self.dispatched_count += 1
        logger.info(
            "[DRIUT NOTIFICATION BOUNDARY] Alert #%d dispatched for user '%s': [%s (%.0f%%)] "
            "Saved Paper: '%s' ➔ Trigger Paper: '%s'. Explanation: %s",
            self.dispatched_count,
            user_id,
            relationship_type,
            confidence_score * 100,
            saved_paper_title,
            trigger_paper_title,
            explanation,
        )
        return True


# Global dispatcher instance
notification_dispatcher = NotificationDispatcher()
