from flask_socketio import emit, join_room, leave_room, disconnect
from flask import session, request
import json
from datetime import datetime
from auth import AuthManager
import time
from collections import deque, defaultdict

class WebSocketManager:
    def __init__(self, socketio, supabase, auth_manager):
        self.socketio = socketio
        self.supabase = supabase
        self.auth_manager = auth_manager
        self.active_users = {}  # Track active users and their rooms
        # Simple in-memory IP-based rate limit for socket connections
        self.ip_connect_events = defaultdict(lambda: deque())
        self.max_connects_per_window = 20  # connections
        self.connect_window_seconds = 60   # per 60 seconds
        
    def register_events(self):
        """Register all WebSocket event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection"""
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr) or 'unknown'
            now = time.time()
            q = self.ip_connect_events[client_ip]
            # Evict old entries
            while q and now - q[0] > self.connect_window_seconds:
                q.popleft()
            q.append(now)
            if len(q) > self.max_connects_per_window:
                print(f"[WS-RATE-LIMIT] Too many connections from {client_ip}; disconnecting SID {request.sid}")
                try:
                    emit('rate_limited', {'message': 'Too many socket connections. Please slow down.'})
                except Exception:
                    pass
                disconnect()
                return
            print(f"[WS-CONNECT] sid={request.sid} ip={client_ip} recent_connects={len(q)}/{self.max_connects_per_window}")
            emit('connection_status', {'status': 'connected', 'sid': request.sid})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection"""
            user_id = session.get('user_id')
            user_type = session.get('user_type')
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr) or 'unknown'
            
            if user_id and user_type:
                # Remove from active users
                if user_id in self.active_users:
                    del self.active_users[user_id]
                
                # Notify others in the same room
                room = f"{user_type}_{user_id}"
                emit('user_offline', {
                    'user_id': user_id,
                    'user_type': user_type,
                    'timestamp': datetime.now().isoformat()
                }, room=room, include_self=False)
                
                leave_room(room)
            
            print(f"[WS-DISCONNECT] sid={request.sid} ip={client_ip}")
        
        @self.socketio.on('authenticate')
        def handle_authentication(data):
            """Authenticate user and join appropriate rooms"""
            try:
                user_id = data.get('user_id')
                user_type = data.get('user_type')
                username = data.get('username')
                
                if not all([user_id, user_type, username]):
                    emit('auth_error', {'message': 'Missing authentication data'})
                    return
                
                # Join user-specific room
                user_room = f"{user_type}_{user_id}"
                join_room(user_room)
                
                # Join role-based room
                role_room = f"role_{user_type}"
                join_room(role_room)
                
                # Join branch room if applicable
                if user_type in ['ps', 'branch_head', 'rec']:
                    branch = data.get('branch')
                    if branch:
                        branch_room = f"branch_{branch}"
                        join_room(branch_room)
                
                # Track active user
                self.active_users[user_id] = {
                    'user_type': user_type,
                    'username': username,
                    'branch': data.get('branch'),
                    'connected_at': datetime.now().isoformat(),
                    'sid': request.sid
                }
                
                # Notify others in role room
                emit('user_online', {
                    'user_id': user_id,
                    'user_type': user_type,
                    'username': username,
                    'branch': data.get('branch'),
                    'timestamp': datetime.now().isoformat()
                }, room=role_room, include_self=False)
                
                emit('auth_success', {
                    'message': 'Successfully authenticated',
                    'rooms': [user_room, role_room]
                })
                
                print(f"User {username} ({user_type}) authenticated and joined rooms")
                
            except Exception as e:
                print(f"Authentication error: {e}")
                emit('auth_error', {'message': str(e)})
        
        @self.socketio.on('lead_assigned')
        def handle_lead_assignment(data):
            """Handle real-time lead assignment notifications"""
            try:
                lead_uid = data.get('lead_uid')
                cre_name = data.get('cre_name')
                ps_name = data.get('ps_name')
                source = data.get('source')
                
                # Notify CRE
                if cre_name:
                    cre_room = f"cre_{cre_name}"
                    emit('lead_assigned_notification', {
                        'type': 'cre_assignment',
                        'lead_uid': lead_uid,
                        'source': source,
                        'assigned_at': datetime.now().isoformat(),
                        'message': f'New lead {lead_uid} assigned to you from {source}'
                    }, room=cre_room)
                
                # Notify PS
                if ps_name:
                    ps_room = f"ps_{ps_name}"
                    emit('lead_assigned_notification', {
                        'type': 'ps_assignment',
                        'lead_uid': lead_uid,
                        'source': source,
                        'assigned_at': datetime.now().isoformat(),
                        'message': f'New lead {lead_uid} assigned to you from {source}'
                    }, room=ps_room)
                
                # Notify admin dashboard
                emit('lead_assignment_update', {
                    'lead_uid': lead_uid,
                    'cre_name': cre_name,
                    'ps_name': ps_name,
                    'source': source,
                    'assigned_at': datetime.now().isoformat()
                }, room='role_admin')
                
            except Exception as e:
                print(f"Lead assignment error: {e}")
        
        @self.socketio.on('lead_status_update')
        def handle_lead_status_update(data):
            """Handle real-time lead status updates"""
            try:
                lead_uid = data.get('lead_uid')
                new_status = data.get('status')
                user_type = data.get('user_type')
                username = data.get('username')
                remarks = data.get('remarks')
                
                # Notify all users in the same branch
                if user_type in ['ps', 'cre']:
                    user_info = self.active_users.get(session.get('user_id', ''), {})
                    branch = user_info.get('branch')
                    
                    if branch:
                        branch_room = f"branch_{branch}"
                        emit('lead_status_changed', {
                            'lead_uid': lead_uid,
                            'new_status': new_status,
                            'updated_by': username,
                            'user_type': user_type,
                            'remarks': remarks,
                            'updated_at': datetime.now().isoformat()
                        }, room=branch_room)
                
                # Notify admin dashboard
                emit('lead_status_update', {
                    'lead_uid': lead_uid,
                    'new_status': new_status,
                    'updated_by': username,
                    'user_type': user_type,
                    'remarks': remarks,
                    'updated_at': datetime.now().isoformat()
                }, room='role_admin')
                
            except Exception as e:
                print(f"Lead status update error: {e}")
        
        @self.socketio.on('call_attempt_logged')
        def handle_call_attempt(data):
            """Handle real-time call attempt logging"""
            try:
                lead_uid = data.get('lead_uid')
                call_number = data.get('call_number')
                status = data.get('status')
                user_type = data.get('user_type')
                username = data.get('username')
                
                # Notify relevant users
                notification_data = {
                    'lead_uid': lead_uid,
                    'call_number': call_number,
                    'status': status,
                    'updated_by': username,
                    'user_type': user_type,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Notify admin dashboard
                emit('call_attempt_logged', notification_data, room='role_admin')
                
                # Notify branch users
                user_info = self.active_users.get(session.get('user_id', ''), {})
                branch = user_info.get('branch')
                if branch:
                    branch_room = f"branch_{branch}"
                    emit('call_attempt_logged', notification_data, room=branch_room)
                
            except Exception as e:
                print(f"Call attempt logging error: {e}")
        
        @self.socketio.on('dashboard_data_request')
        def handle_dashboard_data_request(data):
            """Handle real-time dashboard data requests"""
            try:
                user_type = data.get('user_type')
                user_id = data.get('user_id')
                
                if user_type == 'admin':
                    # Send admin dashboard data
                    self.send_admin_dashboard_data(user_id)
                elif user_type == 'cre':
                    # Send CRE dashboard data
                    self.send_cre_dashboard_data(user_id)
                elif user_type == 'ps':
                    # Send PS dashboard data
                    self.send_ps_dashboard_data(user_id)
                elif user_type == 'branch_head':
                    # Send branch head dashboard data
                    self.send_branch_head_dashboard_data(user_id)
                
            except Exception as e:
                print(f"Dashboard data request error: {e}")
                emit('dashboard_data_error', {'message': str(e)})
        
        # Chat functionality removed
        
        @self.socketio.on('join_lead_room')
        def handle_join_lead_room(data):
            """Join a specific lead's room for real-time updates"""
            try:
                lead_uid = data.get('lead_uid')
                if lead_uid:
                    lead_room = f"lead_{lead_uid}"
                    join_room(lead_room)
                    emit('joined_lead_room', {'lead_uid': lead_uid})
            except Exception as e:
                print(f"Join lead room error: {e}")
        
        @self.socketio.on('leave_lead_room')
        def handle_leave_lead_room(data):
            """Leave a specific lead's room"""
            try:
                lead_uid = data.get('lead_uid')
                if lead_uid:
                    lead_room = f"lead_{lead_uid}"
                    leave_room(lead_room)
                    emit('left_lead_room', {'lead_uid': lead_uid})
            except Exception as e:
                print(f"Leave lead room error: {e}")
    
    def send_admin_dashboard_data(self, user_id):
        """Send real-time admin dashboard data"""
        try:
            # Get real-time counts
            cre_count = self.get_accurate_count('cre_users')
            ps_count = self.get_accurate_count('ps_users')
            leads_count = self.get_accurate_count('lead_master')
            unassigned_leads = self.get_accurate_count('lead_master', {'assigned': 'No'})
            
            dashboard_data = {
                'cre_count': cre_count,
                'ps_count': ps_count,
                'leads_count': leads_count,
                'unassigned_leads': unassigned_leads,
                'timestamp': datetime.now().isoformat()
            }
            
            emit('admin_dashboard_data', dashboard_data)
            
        except Exception as e:
            print(f"Error sending admin dashboard data: {e}")
    
    def send_cre_dashboard_data(self, user_id):
        """Send real-time CRE dashboard data"""
        try:
            # Get CRE-specific data
            user_info = self.active_users.get(user_id, {})
            cre_name = user_info.get('username')
            
            if cre_name:
                # Get assigned leads count
                assigned_leads = self.get_accurate_count('lead_master', {'cre_name': cre_name})
                pending_leads = self.get_accurate_count('lead_master', {'cre_name': cre_name, 'final_status': 'Pending'})
                
                dashboard_data = {
                    'assigned_leads': assigned_leads,
                    'pending_leads': pending_leads,
                    'timestamp': datetime.now().isoformat()
                }
                
                emit('cre_dashboard_data', dashboard_data)
                
        except Exception as e:
            print(f"Error sending CRE dashboard data: {e}")
    
    def send_ps_dashboard_data(self, user_id):
        """Send real-time PS dashboard data"""
        try:
            # Get PS-specific data
            user_info = self.active_users.get(user_id, {})
            ps_name = user_info.get('username')
            
            if ps_name:
                # Get assigned leads count
                assigned_leads = self.get_accurate_count('ps_followup_master', {'ps_name': ps_name})
                pending_leads = self.get_accurate_count('ps_followup_master', {'ps_name': ps_name, 'final_status': 'Pending'})
                
                dashboard_data = {
                    'assigned_leads': assigned_leads,
                    'pending_leads': pending_leads,
                    'timestamp': datetime.now().isoformat()
                }
                
                emit('ps_dashboard_data', dashboard_data)
                
        except Exception as e:
            print(f"Error sending PS dashboard data: {e}")
    
    def send_branch_head_dashboard_data(self, user_id):
        """Send real-time branch head dashboard data"""
        try:
            # Get branch-specific data
            user_info = self.active_users.get(user_id, {})
            branch = user_info.get('branch')
            
            if branch:
                # Get branch-specific counts
                branch_leads = self.get_accurate_count('lead_master', {'branch': branch})
                branch_ps = self.get_accurate_count('ps_users', {'branch': branch})
                
                dashboard_data = {
                    'branch_leads': branch_leads,
                    'branch_ps': branch_ps,
                    'timestamp': datetime.now().isoformat()
                }
                
                emit('branch_head_dashboard_data', dashboard_data)
                
        except Exception as e:
            print(f"Error sending branch head dashboard data: {e}")
    
    def get_accurate_count(self, table_name, filters=None):
        """Get accurate count from Supabase table"""
        try:
            query = self.supabase.table(table_name).select('id')
            
            if filters:
                for key, value in filters.items():
                    if value is not None:
                        query = query.eq(key, value)
            
            result = query.execute()
            return len(result.data) if result.data else 0
            
        except Exception as e:
            print(f"Error getting count from {table_name}: {e}")
            return 0
    
    def broadcast_lead_update(self, lead_uid, update_data):
        """Broadcast lead update to all relevant users"""
        try:
            # Join lead room and broadcast
            lead_room = f"lead_{lead_uid}"
            self.socketio.emit('lead_updated', {
                'lead_uid': lead_uid,
                'update_data': update_data,
                'timestamp': datetime.now().isoformat()
            }, room=lead_room)
            
        except Exception as e:
            print(f"Error broadcasting lead update: {e}")
    
    def notify_user(self, user_id, user_type, event, data):
        """Send notification to specific user"""
        try:
            user_room = f"{user_type}_{user_id}"
            self.socketio.emit(event, data, room=user_room)
            
        except Exception as e:
            print(f"Error notifying user: {e}")
    
    def get_active_users(self):
        """Get list of currently active users"""
        return self.active_users
