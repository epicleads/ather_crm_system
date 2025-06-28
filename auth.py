import bcrypt
import secrets
import string
from datetime import datetime, timedelta
from functools import wraps
from flask import session, request, redirect, url_for, flash, current_app
import hashlib
import hmac
import pyotp
import qrcode
import io
import base64
from supabase import Client


class AuthManager:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.max_login_attempts = 5
        self.lockout_duration = 30  # minutes
        self.session_timeout = 24 * 60  # 24 hours in minutes

    def generate_salt(self) -> str:
        """Generate a random salt for password hashing"""
        return bcrypt.gensalt().decode('utf-8')

    def hash_password(self, password: str, salt: str = None) -> tuple:
        """Hash password with salt"""
        if salt is None:
            salt = self.generate_salt()

        # Use bcrypt for hashing
        password_bytes = password.encode('utf-8')
        salt_bytes = salt.encode('utf-8')
        hashed = bcrypt.hashpw(password_bytes, salt_bytes)

        return hashed.decode('utf-8'), salt

    def verify_password(self, password: str, hashed_password: str, salt: str) -> bool:
        """Verify password against hash"""
        try:
            password_bytes = password.encode('utf-8')
            salt_bytes = salt.encode('utf-8')
            hashed_bytes = hashed_password.encode('utf-8')

            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception as e:
            print(f"Password verification error: {e}")
            return False

    def is_account_locked(self, user_data: dict) -> bool:
        """Check if account is locked due to failed attempts"""
        if not user_data.get('account_locked_until'):
            return False

        locked_until = datetime.fromisoformat(user_data['account_locked_until'].replace('Z', '+00:00'))
        return datetime.now() < locked_until

    def lock_account(self, user_id: int, user_type: str):
        """Lock account for specified duration"""
        locked_until = datetime.now() + timedelta(minutes=self.lockout_duration)

        update_data = {
            'failed_login_attempts': self.max_login_attempts,
            'account_locked_until': locked_until.isoformat()
        }

        table_name = f"{user_type}_users"
        self.supabase.table(table_name).update(update_data).eq('id', user_id).execute()

        self.log_audit_event(
            user_id=user_id,
            user_type=user_type,
            action='ACCOUNT_LOCKED',
            details={'locked_until': locked_until.isoformat(), 'reason': 'Too many failed login attempts'}
        )

    def increment_failed_attempts(self, user_id: int, user_type: str, current_attempts: int):
        """Increment failed login attempts"""
        new_attempts = current_attempts + 1

        update_data = {'failed_login_attempts': new_attempts}

        if new_attempts >= self.max_login_attempts:
            locked_until = datetime.now() + timedelta(minutes=self.lockout_duration)
            update_data['account_locked_until'] = locked_until.isoformat()

        table_name = f"{user_type}_users"
        self.supabase.table(table_name).update(update_data).eq('id', user_id).execute()

    def reset_failed_attempts(self, user_id: int, user_type: str):
        """Reset failed login attempts after successful login"""
        update_data = {
            'failed_login_attempts': 0,
            'account_locked_until': None,
            'last_login': datetime.now().isoformat()
        }

        table_name = f"{user_type}_users"
        self.supabase.table(table_name).update(update_data).eq('id', user_id).execute()

    def create_session(self, user_id: int, user_type: str, user_data: dict) -> str:
        """Create secure session"""
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(minutes=self.session_timeout)

        session_data = {
            'session_id': session_id,
            'user_id': user_id,
            'user_type': user_type,
            'ip_address': request.environ.get('REMOTE_ADDR'),
            'user_agent': request.environ.get('HTTP_USER_AGENT', ''),
            'expires_at': expires_at.isoformat(),
            'is_active': True
        }

        try:
            self.supabase.table('user_sessions').insert(session_data).execute()

            # Set session data
            session.permanent = True
            session['session_id'] = session_id
            session['user_id'] = user_id
            session['user_type'] = user_type
            session['username'] = user_data.get('username')
            session['user_name'] = user_data.get('name', user_data.get('username'))

            if user_type == 'cre':
                session['cre_name'] = user_data.get('name')
                session['cre_id'] = user_id
            elif user_type == 'ps':
                session['ps_name'] = user_data.get('name')
                session['ps_id'] = user_id
                session['branch'] = user_data.get('branch')

            return session_id
        except Exception as e:
            print(f"Error creating session: {e}")
            return None

    def validate_session(self, session_id: str) -> bool:
        """Validate if session is still active and not expired"""
        try:
            result = self.supabase.table('user_sessions').select('*').eq('session_id', session_id).eq('is_active',
                                                                                                      True).execute()

            if not result.data:
                return False

            session_data = result.data[0]
            expires_at = datetime.fromisoformat(session_data['expires_at'].replace('Z', '+00:00'))

            if datetime.now() > expires_at:
                # Session expired, deactivate it
                self.deactivate_session(session_id)
                return False

            # Update last activity
            self.supabase.table('user_sessions').update({
                'last_activity': datetime.now().isoformat()
            }).eq('session_id', session_id).execute()

            return True
        except Exception as e:
            print(f"Error validating session: {e}")
            return False

    def deactivate_session(self, session_id: str):
        """Deactivate a session"""
        try:
            self.supabase.table('user_sessions').update({
                'is_active': False
            }).eq('session_id', session_id).execute()
        except Exception as e:
            print(f"Error deactivating session: {e}")

    def deactivate_all_user_sessions(self, user_id: int, user_type: str, except_session: str = None):
        """Deactivate all sessions for a user except the current one"""
        try:
            query = self.supabase.table('user_sessions').update({
                'is_active': False
            }).eq('user_id', user_id).eq('user_type', user_type)

            if except_session:
                query = query.neq('session_id', except_session)

            query.execute()
        except Exception as e:
            print(f"Error deactivating user sessions: {e}")

    def authenticate_user(self, username: str, password: str, user_type: str) -> tuple:
        """Authenticate user with enhanced security"""
        try:
            # Replace the existing rate limit and logging calls with:
            try:
                # Check rate limiting
                ip_address = request.environ.get('REMOTE_ADDR')
                if not self.check_rate_limit(ip_address):
                    flash('Too many login attempts. Please try again later.', 'error')
                    return False, "Rate limited", None

                # Log login attempt
                self.log_login_attempt(username, user_type, False)  # Initially false, will update if successful
            except Exception as e:
                print(f"Warning: Could not check rate limit or log attempt: {e}")
                # Continue with authentication even if logging fails

            # Get user data
            table_name = f"{user_type}_users"
            result = self.supabase.table(table_name).select('*').eq('username', username).execute()

            if not result.data:
                return False, "Invalid credentials", None

            user_data = result.data[0]

            # Check if account is active
            if not user_data.get('is_active', True):
                self.log_audit_event(
                    user_id=user_data['id'],
                    user_type=user_type,
                    action='LOGIN_ATTEMPT_INACTIVE_ACCOUNT',
                    details={'username': username}
                )
                return False, "Account is deactivated", None

            # Check if account is locked
            if self.is_account_locked(user_data):
                locked_until = datetime.fromisoformat(user_data['account_locked_until'].replace('Z', '+00:00'))
                return False, f"Account is locked until {locked_until.strftime('%Y-%m-%d %H:%M:%S')}", None

            # Verify password
            password_valid = False

            # Check if user has new hashed password
            if user_data.get('password_hash') and user_data.get('salt'):
                password_valid = self.verify_password(password, user_data['password_hash'], user_data['salt'])
            else:
                # Fallback to old plain text password (for migration)
                if user_data.get('password') == password:
                    password_valid = True
                    # Migrate to hashed password
                    self.migrate_user_password(user_data['id'], user_type, password)

            if not password_valid:
                # Increment failed attempts
                current_attempts = user_data.get('failed_login_attempts', 0)
                self.increment_failed_attempts(user_data['id'], user_type, current_attempts)

                remaining_attempts = self.max_login_attempts - (current_attempts + 1)
                if remaining_attempts <= 0:
                    return False, "Account has been locked due to too many failed attempts", None
                else:
                    return False, f"Invalid credentials. {remaining_attempts} attempts remaining", None

            # Successful authentication
            # Replace the success logging with:
            try:
                self.reset_failed_attempts(user_data['id'], user_type)
                self.log_login_attempt(username, user_type, True)

                self.log_audit_event(
                    user_id=user_data['id'],
                    user_type=user_type,
                    action='LOGIN_SUCCESS',
                    details={'username': username}
                )
            except Exception as e:
                print(f"Warning: Could not log successful authentication: {e}")
                # Continue anyway since authentication was successful

            return True, "Login successful", user_data

        except Exception as e:
            print(f"Authentication error: {e}")
            return False, "Authentication error occurred", None

    def migrate_user_password(self, user_id: int, user_type: str, plain_password: str):
        """Migrate plain text password to hashed password"""
        try:
            password_hash, salt = self.hash_password(plain_password)

            update_data = {
                'password_hash': password_hash,
                'salt': salt,
                'password_changed_at': datetime.now().isoformat()
            }

            table_name = f"{user_type}_users"
            self.supabase.table(table_name).update(update_data).eq('id', user_id).execute()

            print(f"Migrated password for user {user_id} in {table_name}")
        except Exception as e:
            print(f"Error migrating password: {e}")

    def change_password(self, user_id: int, user_type: str, old_password: str, new_password: str) -> tuple:
        """Change user password with validation"""
        try:
            # Get current user data
            table_name = f"{user_type}_users"
            result = self.supabase.table(table_name).select('*').eq('id', user_id).execute()

            if not result.data:
                return False, "User not found"

            user_data = result.data[0]

            # Verify old password
            old_password_valid = False
            if user_data.get('password_hash') and user_data.get('salt'):
                old_password_valid = self.verify_password(old_password, user_data['password_hash'], user_data['salt'])
            else:
                old_password_valid = user_data.get('password') == old_password

            if not old_password_valid:
                self.log_audit_event(
                    user_id=user_id,
                    user_type=user_type,
                    action='PASSWORD_CHANGE_FAILED',
                    details={'reason': 'Invalid old password'}
                )
                return False, "Current password is incorrect"

            # Validate new password strength
            if not self.validate_password_strength(new_password):
                return False, "Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character"

            # Hash new password
            password_hash, salt = self.hash_password(new_password)

            update_data = {
                'password_hash': password_hash,
                'salt': salt,
                'password_changed_at': datetime.now().isoformat(),
                'password': None  # Remove old plain text password
            }

            self.supabase.table(table_name).update(update_data).eq('id', user_id).execute()

            # Deactivate all other sessions for this user
            current_session = session.get('session_id')
            self.deactivate_all_user_sessions(user_id, user_type, current_session)

            self.log_audit_event(
                user_id=user_id,
                user_type=user_type,
                action='PASSWORD_CHANGED',
                details={'changed_at': datetime.now().isoformat()}
            )

            return True, "Password changed successfully"

        except Exception as e:
            print(f"Error changing password: {e}")
            return False, "Error changing password"

    def validate_password_strength(self, password: str) -> bool:
        """Validate password strength"""
        if len(password) < 8:
            return False

        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)

        return has_upper and has_lower and has_digit and has_special

    def generate_password_reset_token(self, username: str, user_type: str) -> tuple:
        """Generate password reset token"""
        try:
            print(f"Generating reset token for username: {username}, user_type: {user_type}")

            # Get user data
            table_name = f"{user_type}_users"
            result = self.supabase.table(table_name).select('*').eq('username', username).execute()

            if not result.data:
                print(f"User not found in table: {table_name}")
                return False, "User not found", None

            user_data = result.data[0]
            print(f"User found: {user_data['id']}")

            # Generate secure token
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=1)  # Token expires in 1 hour

            token_data = {
                'user_id': user_data['id'],
                'user_type': user_type,
                'token': token,
                'expires_at': expires_at.isoformat(),
                'used': False,
                'created_at': datetime.now().isoformat()
            }

            print(f"Creating token with expiry: {expires_at}")
            token_result = self.supabase.table('password_reset_tokens').insert(token_data).execute()

            if not token_result.data:
                print("Failed to create token")
                return False, "Failed to create reset token", None

            print("Token created successfully")

            self.log_audit_event(
                user_id=user_data['id'],
                user_type=user_type,
                action='PASSWORD_RESET_REQUESTED',
                details={'token_expires': expires_at.isoformat()}
            )

            return True, "Reset token generated", token

        except Exception as e:
            print(f"Error generating reset token: {e}")
            import traceback
            traceback.print_exc()
            return False, f"Error generating reset token: {str(e)}", None

    def reset_password_with_token(self, token: str, new_password: str) -> tuple:
        """Reset password using token"""
        try:
            print(f"Attempting to reset password with token: {token[:10]}...")

            # Validate token
            result = self.supabase.table('password_reset_tokens').select('*').eq('token', token).eq('used',
                                                                                                    False).execute()

            if not result.data:
                print("Token not found or already used")
                return False, "Invalid or expired token"

            token_data = result.data[0]
            print(f"Token data found for user_id: {token_data['user_id']}, user_type: {token_data['user_type']}")

            expires_at = datetime.fromisoformat(token_data['expires_at'].replace('Z', '+00:00'))

            # Make both datetimes timezone-aware for comparison
            current_time = datetime.now()
            if expires_at.tzinfo is not None:
                # If expires_at is timezone-aware, make current_time timezone-aware too
                from datetime import timezone
                current_time = datetime.now(timezone.utc)
                # Convert expires_at to UTC if it's not already
                if expires_at.tzinfo != timezone.utc:
                    expires_at = expires_at.astimezone(timezone.utc)

            if current_time > expires_at:
                print("Token has expired")
                return False, "Token has expired"

            # Validate new password
            if not self.validate_password_strength(new_password):
                print("Password does not meet strength requirements")
                return False, "Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character"

            # Hash new password
            password_hash, salt = self.hash_password(new_password)
            print("Password hashed successfully")

            # Update user password
            table_name = f"{token_data['user_type']}_users"
            update_data = {
                'password_hash': password_hash,
                'salt': salt,
                'password_changed_at': datetime.now().isoformat(),
                'failed_login_attempts': 0,
                'account_locked_until': None,
                'password': None  # Remove old plain text password
            }

            print(f"Updating password in table: {table_name}")
            update_result = self.supabase.table(table_name).update(update_data).eq('id',
                                                                                   token_data['user_id']).execute()

            if not update_result.data:
                print("Failed to update user password")
                return False, "Failed to update password"

            print("Password updated successfully")

            # Mark token as used
            self.supabase.table('password_reset_tokens').update({'used': True}).eq('token', token).execute()
            print("Token marked as used")

            # Deactivate all sessions for this user
            self.deactivate_all_user_sessions(token_data['user_id'], token_data['user_type'])
            print("All user sessions deactivated")

            self.log_audit_event(
                user_id=token_data['user_id'],
                user_type=token_data['user_type'],
                action='PASSWORD_RESET_COMPLETED',
                details={'reset_at': datetime.now().isoformat()}
            )

            print("Password reset completed successfully")
            return True, "Password reset successfully"

        except Exception as e:
            print(f"Error resetting password: {e}")
            import traceback
            traceback.print_exc()
            return False, f"Error resetting password: {str(e)}"

    def log_audit_event(self, user_id: int = None, user_type: str = None, action: str = '',
                        resource: str = None, resource_id: str = None, details: dict = None):
        """Log audit event"""
        try:
            audit_data = {
                'user_id': user_id,
                'user_type': user_type,
                'action': action,
                'resource': resource,
                'resource_id': resource_id,
                'ip_address': request.environ.get('REMOTE_ADDR'),
                'user_agent': request.environ.get('HTTP_USER_AGENT', ''),
                'details': details or {},
                'timestamp': datetime.now().isoformat()
            }

            self.supabase.table('audit_logs').insert(audit_data).execute()
        except Exception as e:
            print(f"Error logging audit event: {e}")

    def log_login_attempt(self, username: str, user_type: str, success: bool):
        """Log login attempt for rate limiting"""
        try:
            attempt_data = {
                'ip_address': request.environ.get('REMOTE_ADDR'),
                'username': username,
                'user_type': user_type,
                'success': success,
                'timestamp': datetime.now().isoformat()
            }

            self.supabase.table('login_attempts').insert(attempt_data).execute()
        except Exception as e:
            print(f"Error logging login attempt: {e}")

    def check_rate_limit(self, ip_address: str, time_window: int = 15) -> bool:
        """Check if IP is rate limited"""
        try:
            since = datetime.now() - timedelta(minutes=time_window)

            result = self.supabase.table('login_attempts').select('*').eq('ip_address', ip_address).gte('timestamp',
                                                                                                        since.isoformat()).execute()

            if len(result.data) > 20:  # Max 20 attempts per 15 minutes
                return False

            return True
        except Exception as e:
            print(f"Error checking rate limit: {e}")
            return True  # Allow on error

    def get_user_sessions(self, user_id: int, user_type: str) -> list:
        """Get active sessions for a user"""
        try:
            result = self.supabase.table('user_sessions').select('*').eq('user_id', user_id).eq('user_type',
                                                                                                user_type).eq(
                'is_active', True).execute()
            return result.data or []
        except Exception as e:
            print(f"Error getting user sessions: {e}")
            return []

    def get_audit_logs(self, user_id: int = None, user_type: str = None, limit: int = 100) -> list:
        """Get audit logs"""
        try:
            query = self.supabase.table('audit_logs').select('*')

            if user_id:
                query = query.eq('user_id', user_id)
            if user_type:
                query = query.eq('user_type', user_type)

            result = query.order('timestamp', desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            print(f"Error getting audit logs: {e}")
            return []


def require_auth(user_types=None):
    """Decorator to require authentication"""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'session_id' not in session:
                flash('Please log in to access this page', 'error')
                return redirect(url_for('index'))

            # Validate session
            auth_manager = current_app.auth_manager
            if not auth_manager.validate_session(session['session_id']):
                session.clear()
                flash('Your session has expired. Please log in again', 'error')
                return redirect(url_for('index'))

            # Check user type if specified
            if user_types and session.get('user_type') not in user_types:
                flash('Access denied', 'error')
                return redirect(url_for('index'))

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def require_admin(f):
    """Decorator to require admin access"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_type') != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


def require_cre(f):
    """Decorator to require CRE access"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_type') != 'cre':
            flash('CRE access required', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


def require_ps(f):
    """Decorator to require PS access"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_type') != 'ps':
            flash('PS access required', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function
