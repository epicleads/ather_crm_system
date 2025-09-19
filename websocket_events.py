from typing import Any, Dict, Optional
import logging
from datetime import datetime
import time


class WebSocketManager:
    """Room-based WebSocket manager with Redis support for scaling."""

    def __init__(self, socketio: Any, supabase: Any, auth_manager: Any) -> None:
        self.socketio = socketio
        self.supabase = supabase
        self.auth_manager = auth_manager
        self.active_users: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("websocket")
        self.connection_count = 0
        self.max_connections = 1000  # Prevent memory issues
        
        # Room definitions
        self.rooms = {
            'admin': 'admin_room',
            'cre': 'cre_room', 
            'ps': 'ps_room',
            'branch_head': 'branch_head_room'
        }

    def register_events(self) -> None:
        """Register all WebSocket event handlers."""
        self.logger.info("Registering WebSocket event handlers")
        
        @self.socketio.on('connect')
        def on_connect():
            self._handle_connect()
            
        @self.socketio.on('disconnect')
        def on_disconnect():
            self._handle_disconnect()
            
        @self.socketio.on('authenticate')
        def on_authenticate(data):
            self._handle_authenticate(data)
            
        @self.socketio.on('join_lead_room')
        def on_join_lead_room(data):
            self._handle_join_lead_room(data)
            
        @self.socketio.on('leave_lead_room')
        def on_leave_lead_room(data):
            self._handle_leave_lead_room(data)
            
        @self.socketio.on('dashboard_data_request')
        def on_dashboard_request(data):
            self._handle_dashboard_request(data)

    def _handle_connect(self):
        """Handle new WebSocket connection."""
        self.connection_count += 1
        self.logger.info(f"User connected: {self.socketio.request.sid} (Total: {self.connection_count})")
        
        # Check connection limits
        if self.connection_count > self.max_connections:
            self.logger.warning(f"Connection limit exceeded: {self.connection_count}")
            self.socketio.emit('error', {'message': 'Server at capacity'})
            self.socketio.disconnect()
            return
            
        # Store basic connection info
        self.active_users[self.socketio.request.sid] = {
            'connected_at': datetime.now(),
            'authenticated': False,
            'user_id': None,
            'user_type': None,
            'rooms': set()
        }

    def _handle_disconnect(self):
        """Handle WebSocket disconnection."""
        sid = self.socketio.request.sid
        if sid in self.active_users:
            user_info = self.active_users[sid]
            self.logger.info(f"User disconnected: {sid} (User: {user_info.get('user_id', 'unknown')})")
            
            # Leave all rooms
            for room in user_info.get('rooms', set()):
                self.socketio.leave_room(room, sid=sid)
                
            del self.active_users[sid]
            self.connection_count = max(0, self.connection_count - 1)

    def _handle_authenticate(self, data):
        """Handle user authentication."""
        try:
            user_id = data.get('user_id')
            user_type = data.get('user_type')
            username = data.get('username')
            branch = data.get('branch')
            
            if not all([user_id, user_type, username]):
                self.socketio.emit('auth_error', {'message': 'Missing required fields'})
                return
                
            # Store user info
            sid = self.socketio.request.sid
            if sid in self.active_users:
                self.active_users[sid].update({
                    'authenticated': True,
                    'user_id': user_id,
                    'user_type': user_type,
                    'username': username,
                    'branch': branch
                })
                
                # Join appropriate role-based room
                room_name = self.rooms.get(user_type)
                if room_name:
                    self.socketio.join_room(room_name, sid=sid)
                    self.active_users[sid]['rooms'].add(room_name)
                    
                # Join branch room if applicable
                if branch and user_type in ['ps', 'branch_head']:
                    branch_room = f"branch_{branch}"
                    self.socketio.join_room(branch_room, sid=sid)
                    self.active_users[sid]['rooms'].add(branch_room)
                
                self.logger.info(f"User authenticated: {username} ({user_type}) - {sid}")
                self.socketio.emit('auth_success', {'user_id': user_id, 'user_type': user_type})
            else:
                self.socketio.emit('auth_error', {'message': 'Connection not found'})
                
        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            self.socketio.emit('auth_error', {'message': 'Authentication failed'})

    def _handle_join_lead_room(self, data):
        """Handle joining a specific lead room."""
        try:
            lead_uid = data.get('lead_uid')
            if not lead_uid:
                return
                
            sid = self.socketio.request.sid
            if sid in self.active_users and self.active_users[sid]['authenticated']:
                room_name = f"lead_{lead_uid}"
                self.socketio.join_room(room_name, sid=sid)
                self.active_users[sid]['rooms'].add(room_name)
                self.logger.debug(f"User joined lead room: {lead_uid}")
                self.socketio.emit('joined_lead_room', {'lead_uid': lead_uid})
        except Exception as e:
            self.logger.error(f"Error joining lead room: {e}")

    def _handle_leave_lead_room(self, data):
        """Handle leaving a specific lead room."""
        try:
            lead_uid = data.get('lead_uid')
            if not lead_uid:
                return
                
            sid = self.socketio.request.sid
            if sid in self.active_users:
                room_name = f"lead_{lead_uid}"
                self.socketio.leave_room(room_name, sid=sid)
                self.active_users[sid]['rooms'].discard(room_name)
                self.logger.debug(f"User left lead room: {lead_uid}")
                self.socketio.emit('left_lead_room', {'lead_uid': lead_uid})
        except Exception as e:
            self.logger.error(f"Error leaving lead room: {e}")

    def _handle_dashboard_request(self, data):
        """Handle dashboard data requests - move to background task."""
        try:
            user_type = data.get('user_type')
            user_id = data.get('user_id')
            
            if not user_type or not user_id:
                return
                
            # Move heavy DB work to background task
            self.socketio.start_background_task(self._fetch_dashboard_data, user_type, user_id)
            
        except Exception as e:
            self.logger.error(f"Error handling dashboard request: {e}")

    def _fetch_dashboard_data(self, user_type, user_id):
        """Background task to fetch dashboard data."""
        try:
            if user_type == 'admin':
                data = self.get_accurate_count('lead_master')
                self.socketio.emit('admin_dashboard_data', {'leads_count': data}, room=f"user_{user_id}")
            elif user_type == 'cre':
                data = self.get_accurate_count('lead_master', {'assigned_cre': user_id})
                self.socketio.emit('cre_dashboard_data', {'assigned_leads': data}, room=f"user_{user_id}")
            # Add other user types as needed
        except Exception as e:
            self.logger.error(f"Error fetching dashboard data: {e}")
            self.socketio.emit('dashboard_data_error', {'error': str(e)}, room=f"user_{user_id}")

    # Room-based notification methods
    def notify_lead_assignment(self, lead_uid, cre_name, ps_name, ps_id, source):
        """Notify specific PS about lead assignment."""
        try:
            data = {
                'lead_uid': lead_uid,
                'cre_name': cre_name,
                'ps_name': ps_name,
                'source': source,
                'timestamp': datetime.now().isoformat()
            }
            # Notify specific PS
            self.socketio.emit('lead_assigned_notification', data, room=f"user_{ps_id}")
            # Notify lead room
            self.socketio.emit('lead_assigned_notification', data, room=f"lead_{lead_uid}")
            self.logger.info(f"Lead assignment notification sent: {lead_uid} -> PS {ps_id}")
        except Exception as e:
            self.logger.error(f"Error sending lead assignment notification: {e}")

    def notify_lead_status_update(self, lead_uid, new_status, updated_by, remarks=""):
        """Notify about lead status changes."""
        try:
            data = {
                'lead_uid': lead_uid,
                'new_status': new_status,
                'updated_by': updated_by,
                'remarks': remarks,
                'timestamp': datetime.now().isoformat()
            }
            # Notify lead room
            self.socketio.emit('lead_status_changed', data, room=f"lead_{lead_uid}")
            self.logger.info(f"Lead status update notification sent: {lead_uid} -> {new_status}")
        except Exception as e:
            self.logger.error(f"Error sending lead status notification: {e}")

    def notify_call_attempt(self, lead_uid, call_number, status, user_type, username):
        """Notify about call attempts."""
        try:
            data = {
                'lead_uid': lead_uid,
                'call_number': call_number,
                'status': status,
                'user_type': user_type,
                'username': username,
                'timestamp': datetime.now().isoformat()
            }
            # Notify lead room
            self.socketio.emit('call_attempt_logged', data, room=f"lead_{lead_uid}")
            self.logger.debug(f"Call attempt notification sent: {lead_uid}")
        except Exception as e:
            self.logger.error(f"Error sending call attempt notification: {e}")

    # Legacy compatibility methods (now use room-based approach)
    def send_admin_dashboard_data(self, user_id):
        """Send admin dashboard data to specific user."""
        self.socketio.start_background_task(self._fetch_dashboard_data, 'admin', user_id)

    def send_cre_dashboard_data(self, user_id):
        """Send CRE dashboard data to specific user."""
        self.socketio.start_background_task(self._fetch_dashboard_data, 'cre', user_id)

    def send_ps_dashboard_data(self, user_id):
        """Send PS dashboard data to specific user."""
        self.socketio.start_background_task(self._fetch_dashboard_data, 'ps', user_id)

    def send_branch_head_dashboard_data(self, user_id):
        """Send branch head dashboard data to specific user."""
        self.socketio.start_background_task(self._fetch_dashboard_data, 'branch_head', user_id)

    def get_accurate_count(self, table_name, filters=None):
        """Get accurate count from database."""
        try:
            if not self.supabase:
                return 0
                
            query = self.supabase.table(table_name).select('*', count='exact')
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            result = query.execute()
            return result.count if hasattr(result, 'count') else 0
        except Exception as e:
            self.logger.error(f"Error getting count from {table_name}: {e}")
            return 0

    def broadcast_lead_update(self, lead_uid, update_data):
        """Legacy method - now uses room-based notifications."""
        self.notify_lead_status_update(
            lead_uid, 
            update_data.get('new_status', 'Unknown'),
            update_data.get('updated_by', 'System'),
            update_data.get('remarks', '')
        )

    def notify_user(self, user_id, user_type, event, data):
        """Notify specific user by ID."""
        try:
            self.socketio.emit(event, data, room=f"user_{user_id}")
        except Exception as e:
            self.logger.error(f"Error notifying user {user_id}: {e}")

    def get_active_users(self):
        """Get active user statistics."""
        return {
            'total_connections': self.connection_count,
            'authenticated_users': len([u for u in self.active_users.values() if u.get('authenticated')]),
            'users_by_type': self._get_users_by_type(),
            'room_counts': self._get_room_counts()
        }

    def _get_users_by_type(self):
        """Get user count by type."""
        counts = {}
        for user in self.active_users.values():
            if user.get('authenticated'):
                user_type = user.get('user_type', 'unknown')
                counts[user_type] = counts.get(user_type, 0) + 1
        return counts

    def _get_room_counts(self):
        """Get room membership counts."""
        room_counts = {}
        for user in self.active_users.values():
            for room in user.get('rooms', set()):
                room_counts[room] = room_counts.get(room, 0) + 1
        return room_counts
