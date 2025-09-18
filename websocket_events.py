from typing import Any, Dict
import logging


class WebSocketManager:
    """No-op WebSocket manager stub. Socket features are disabled."""

    def __init__(self, socketio: Any, supabase: Any, auth_manager: Any) -> None:
        self.socketio = socketio
        self.supabase = supabase
        self.auth_manager = auth_manager
        self.active_users: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("websocket")

    def register_events(self) -> None:
        # WebSocket functionality disabled
        self.logger.info("WebSocket functionality is disabled (no-op register_events)")

    # The following methods are kept for API compatibility but do nothing
    def send_admin_dashboard_data(self, user_id):
        return

    def send_cre_dashboard_data(self, user_id):
        return

    def send_ps_dashboard_data(self, user_id):
        return

    def send_branch_head_dashboard_data(self, user_id):
        return

    def get_accurate_count(self, table_name, filters=None):
        return 0

    def broadcast_lead_update(self, lead_uid, update_data):
        return

    def notify_user(self, user_id, user_type, event, data):
        return

    def get_active_users(self):
        return {}
