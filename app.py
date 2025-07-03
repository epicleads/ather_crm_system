import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from supabase.client import create_client, Client
import csv
import openpyxl
import os
from datetime import datetime, timedelta, date
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename
import random
import string
import io
from dotenv import load_dotenv
from collections import defaultdict, Counter
import json
from auth import AuthManager, require_auth, require_admin, require_cre, require_ps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from security_verification import run_security_verification
import time
import gc
from flask_socketio import SocketIO, emit
# from redis import Redis  # REMOVE this line for local development

# Add this instead:
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from flask import send_file
import tempfile

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Reduce Flask log noise
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)

# Add custom Jinja2 filters
@app.template_filter('tojson')
def to_json(value):
    return json.dumps(value)


app.jinja_env.filters['tojsonfilter'] = to_json

# Get environment variables with fallback values for testing
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_ANON_KEY')
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'fallback-secret-key-change-this')

# Email configuration (add these to your .env file)
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
EMAIL_USER = os.environ.get('EMAIL_USER', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')

# Debug: Print to check if variables are loaded (remove in production)
print(f"SUPABASE_URL loaded: {SUPABASE_URL is not None}")
print(f"SUPABASE_KEY loaded: {SUPABASE_KEY is not None}")

# Validate required environment variables
if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL environment variable is required. Please check your .env file.")
if not SUPABASE_KEY:
    raise ValueError("SUPABASE_ANON_KEY environment variable is required. Please check your .env file.")

app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(hours=24)

# Initialize Supabase client
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase client initialized successfully")
    # Removed Supabase warm-up query for local development
except Exception as e:
    print(f"❌ Error initializing Supabase client: {e}")
    raise

# Initialize AuthManager
auth_manager = AuthManager(supabase)
# Store auth_manager in app config instead of direct attribute
app.config['AUTH_MANAGER'] = auth_manager

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["1000 per minute"]  # Use in-memory backend for local/dev
)

# Upload folder configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def send_email_to_ps(ps_email, ps_name, lead_data, cre_name):
    """Send email notification to PS when a lead is assigned"""
    try:
        if not EMAIL_USER or not EMAIL_PASSWORD:
            print("Email credentials not configured. Skipping email notification.")
            return False

        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = ps_email
        msg['Subject'] = f"New Lead Assigned - {lead_data['customer_name']}"

        # Email body
        body = f"""
        Dear {ps_name},

        A new lead has been assigned to you by {cre_name}.

        Lead Details:
        - Customer Name: {lead_data['customer_name']}
        - Mobile Number: {lead_data['customer_mobile_number']}
        - Source: {lead_data['source']}
        - Lead Category: {lead_data.get('lead_category', 'Not specified')}
        - Model Interested: {lead_data.get('model_interested', 'Not specified')}
        - Branch: {lead_data.get('branch', 'Not specified')}

        Please log in to the CRM system to view and update this lead.

        Best regards,
        Ather CRM System
        """

        msg.attach(MIMEText(body, 'plain'))

        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_USER, ps_email, text)
        server.quit()

        print(f"Email sent successfully to {ps_email}")
        return True

    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def read_csv_file(filepath):
    """Read CSV file and return list of dictionaries with memory optimization"""
    data = []
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            for row_num, row in enumerate(csv_reader):
                if row_num >= 10000:  # Limit to 10,000 rows
                    print(f"Warning: File contains more than 10,000 rows. Only processing first 10,000.")
                    break

                # Clean and validate row data
                cleaned_row = {}
                for key, value in row.items():
                    if key and value:  # Only include non-empty keys and values
                        cleaned_row[key.strip()] = str(value).strip()

                if cleaned_row:  # Only add non-empty rows
                    data.append(cleaned_row)

                # Memory management for large files
                if row_num % 1000 == 0 and row_num > 0:
                    print(f"Processed {row_num} rows...")

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        raise

    return data


def read_excel_file(filepath):
    """Read Excel file and return list of dictionaries with memory optimization"""
    data = []
    try:
        workbook = openpyxl.load_workbook(filepath, read_only=True)  # Read-only mode for memory efficiency
        sheet = workbook.active

        # Get headers from first row
        headers = []
        if sheet and sheet[1]:
            for cell in sheet[1]:
                if cell and cell.value:
                    headers.append(str(cell.value).strip())
                else:
                    headers.append(None)

        # Read data rows with limit
        row_count = 0
        if sheet:
            for row_num, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                if row_count >= 10000:  # Limit to 10,000 rows
                    print(f"Warning: File contains more than 10,000 rows. Only processing first 10,000.")
                    break

                row_data = {}
                has_data = False

                for i, value in enumerate(row):
                    if i < len(headers) and headers[i] and value is not None:
                        row_data[headers[i]] = str(value).strip()
                        has_data = True

                if has_data:  # Only add rows with actual data
                    data.append(row_data)
                    row_count += 1

                # Memory management for large files
                if row_count % 1000 == 0 and row_count > 0:
                    print(f"Processed {row_count} rows...")

        workbook.close()  # Explicitly close workbook

    except Exception as e:
        print(f"Error reading Excel file: {e}")
        raise

    return data


def batch_insert_leads(leads_data, batch_size=100):
    """Insert leads in batches to avoid overwhelming the database"""
    total_inserted = 0
    total_batches = (len(leads_data) + batch_size - 1) // batch_size

    print(f"Starting batch insert: {len(leads_data)} leads in {total_batches} batches")

    for i in range(0, len(leads_data), batch_size):
        batch = leads_data[i:i + batch_size]
        batch_num = (i // batch_size) + 1

        try:
            # Insert batch
            result = supabase.table('lead_master').insert(batch).execute()

            if result.data:
                batch_inserted = len(result.data)
                total_inserted += batch_inserted
                print(f"Batch {batch_num}/{total_batches}: Inserted {batch_inserted} leads")
            else:
                print(f"Batch {batch_num}/{total_batches}: No data returned from insert")

            # Small delay to prevent overwhelming the database
            eventlet.sleep(0.1)  # CHANGED from time.sleep(0.1)

            # Force garbage collection every 10 batches
            if batch_num % 10 == 0:
                gc.collect()

        except Exception as e:
            print(f"Error inserting batch {batch_num}: {e}")
            # Continue with next batch instead of failing completely
            continue

    print(f"Batch insert completed: {total_inserted} total leads inserted")
    return total_inserted


def generate_uid(source, mobile_number, sequence):
    """Generate UID based on source, mobile number, and sequence"""
    source_map = {
        'Google': 'G',
        'Meta': 'M',
        'Affiliate': 'A',
        'Know': 'K',
        'Whatsapp': 'W',
        'Tele': 'T',
        'Activity': 'AC'  # ADD THIS LINE if it's not there
    }

    source_char = source_map.get(source, 'X')

    # Get sequence character (A-Z)
    sequence_char = chr(65 + (sequence % 26))  # A=65 in ASCII

    # Get last 4 digits of mobile number
    mobile_str = str(mobile_number).replace(' ', '').replace('-', '')
    mobile_last4 = mobile_str[-4:] if len(mobile_str) >= 4 else mobile_str.zfill(4)

    # Generate sequence number (0001, 0002, etc.)
    seq_num = f"{(sequence % 9999) + 1:04d}"

    return f"{source_char}{sequence_char}-{mobile_last4}-{seq_num}"


def get_next_call_info(lead_data):
    """Determine the next available call number and which calls are completed"""
    call_order = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh']
    completed_calls = []
    next_call = 'first'

    for call_num in call_order:
        call_date_key = f'{call_num}_call_date'
        if lead_data.get(call_date_key):
            completed_calls.append(call_num)
        else:
            next_call = call_num
            break

    return next_call, completed_calls


def get_next_ps_call_info(ps_data):
    """Determine the next available PS call number and which calls are completed"""
    call_order = ['first', 'second', 'third']
    completed_calls = []
    next_call = 'first'

    for call_num in call_order:
        call_date_key = f'{call_num}_call_date'
        if ps_data.get(call_date_key):
            completed_calls.append(call_num)
        else:
            next_call = call_num
            break

    return next_call, completed_calls


def get_accurate_count(table_name, filters=None):
    """Get accurate count from Supabase table"""
    try:
        query = supabase.table(table_name).select('id')

        if filters:
            for key, value in filters.items():
                if value is not None:
                    query = query.eq(key, value)

        result = query.execute()

        # Count the returned data
        return len(result.data) if result.data else 0

    except Exception as e:
        print(f"Error getting count from {table_name}: {e}")
        return 0


def safe_get_data(table_name, filters=None, select_fields='*', limit=10000):
    """Safely get data from Supabase with error handling"""
    try:
        query = supabase.table(table_name).select(select_fields)

        if filters:
            for key, value in filters.items():
                if value is not None:
                    query = query.eq(key, value)

        # Add limit to prevent default 1000 row limitation
        if limit:
            query = query.limit(limit)

        result = query.execute()
        return result.data or []
    except Exception as e:
        print(f"Error fetching data from {table_name}: {e}")
        return []


def create_or_update_ps_followup(lead_data, ps_name, ps_branch):
    """Create or update PS followup record when lead is assigned to PS"""
    try:
        # Check if PS followup record already exists
        existing = supabase.table('ps_followup_master').select('*').eq('lead_uid', lead_data['uid']).execute()

        ps_followup_data = {
            'lead_uid': lead_data['uid'],
            'ps_name': ps_name,
            'ps_branch': ps_branch,
            'customer_name': lead_data.get('customer_name'),
            'customer_mobile_number': lead_data.get('customer_mobile_number'),
            'source': lead_data.get('source'),
            'cre_name': lead_data.get('cre_name'),
            'lead_category': lead_data.get('lead_category'),
            'model_interested': lead_data.get('model_interested'),
            'final_status': 'Pending'
        }

        if existing.data:
            # Update existing record
            supabase.table('ps_followup_master').update(ps_followup_data).eq('lead_uid', lead_data['uid']).execute()
        else:
            # Create new record
            supabase.table('ps_followup_master').insert(ps_followup_data).execute()

    except Exception as e:
        print(f"Error creating/updating PS followup: {e}")


def filter_leads_by_date(leads, filter_type, date_field='created_at'):
    """Filter leads based on date range"""
    if filter_type == 'all':
        return leads

    today = datetime.now().date()

    if filter_type == 'mtd':  # Month to Date
        start_date = today.replace(day=1)
    elif filter_type == 'week':
        start_date = today - timedelta(days=today.weekday())  # Start of current week (Monday)
    elif filter_type == 'month':
        start_date = today - timedelta(days=30)
    elif filter_type == 'quarter':
        start_date = today - timedelta(days=90)
    elif filter_type == 'year':
        start_date = today - timedelta(days=365)
    else:
        return leads

    filtered_leads = []
    for lead in leads:
        lead_date_str = lead.get(date_field)
        if lead_date_str:
            try:
                # Handle different date formats
                if 'T' in lead_date_str:  # ISO format with time
                    lead_date = datetime.fromisoformat(lead_date_str.replace('Z', '+00:00')).date()
                else:  # Date only format
                    lead_date = datetime.strptime(lead_date_str, '%Y-%m-%d').date()

                if lead_date >= start_date:
                    filtered_leads.append(lead)
            except (ValueError, TypeError):
                # If date parsing fails, include the lead
                filtered_leads.append(lead)
        else:
            # If no date field, include the lead
            filtered_leads.append(lead)

    return filtered_leads


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/unified_login', methods=['POST'])
@limiter.limit("1000 per minute")  # Now using Redis backend for rate limiting
def unified_login():
    start_time = time.time()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    t1 = time.time()
    user_types = ['admin', 'cre', 'ps']
    for user_type in user_types:
        t_user = time.time()
        success, message, user_data = auth_manager.authenticate_user(username, password, user_type)
        print(f"[PERF] unified_login: authenticate_user({user_type}) took {time.time() - t_user:.3f} seconds")
        if success:
            t2 = time.time()
            session_id = auth_manager.create_session(user_data['id'], user_type, user_data)
            print(f"[PERF] unified_login: create_session took {time.time() - t2:.3f} seconds")
            if session_id:
                flash(f'Welcome! Logged in as {user_type.upper()}', 'success')
                t3 = time.time()
                # Redirect to appropriate dashboard
                if user_type == 'admin':
                    print(f"[PERF] unified_login: redirect to admin_dashboard after {time.time() - t3:.3f} seconds")
                    print(f"[PERF] unified_login TOTAL took {time.time() - start_time:.3f} seconds")
                    return redirect(url_for('admin_dashboard'))
                elif user_type == 'cre':
                    print(f"[PERF] unified_login: redirect to cre_dashboard after {time.time() - t3:.3f} seconds")
                    print(f"[PERF] unified_login TOTAL took {time.time() - start_time:.3f} seconds")
                    return redirect(url_for('cre_dashboard'))
                elif user_type == 'ps':
                    print(f"[PERF] unified_login: redirect to ps_dashboard after {time.time() - t3:.3f} seconds")
                    print(f"[PERF] unified_login TOTAL took {time.time() - start_time:.3f} seconds")
                    return redirect(url_for('ps_dashboard'))
            else:
                flash('Error creating session', 'error')
                print(f"[PERF] unified_login: session creation failed after {time.time() - t2:.3f} seconds")
                print(f"[PERF] unified_login TOTAL took {time.time() - start_time:.3f} seconds")
                return redirect(url_for('index'))
    print(f"[PERF] unified_login: all user_type attempts took {time.time() - t1:.3f} seconds")
    flash('Invalid username or password', 'error')
    print(f"[PERF] unified_login TOTAL (invalid login) took {time.time() - start_time:.3f} seconds")
    return redirect(url_for('index'))


# Keep the old login routes for backward compatibility (redirect to unified login)
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        return unified_login()
    return redirect(url_for('index'))


@app.route('/cre_login', methods=['GET', 'POST'])
def cre_login():
    if request.method == 'POST':
        return unified_login()
    return redirect(url_for('index'))


@app.route('/ps_login', methods=['GET', 'POST'])
def ps_login():
    if request.method == 'POST':
        return unified_login()
    return redirect(url_for('index'))


@app.route('/password_reset_request', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def password_reset_request():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        user_type = request.form.get('user_type', '').strip()

        if not username or not user_type:
            flash('Please enter username and select user type', 'error')
            return render_template('password_reset_request.html')

        success, message, token = auth_manager.generate_password_reset_token(username, user_type)

        if success:
            # In a real application, you would send this token via email
            # For demo purposes, we'll show it in the flash message
            reset_url = url_for('password_reset', token=token, _external=True)
            flash(f'Password reset link: {reset_url}', 'success')
        else:
            flash(message, 'error')

    return render_template('password_reset_request.html')


@app.route('/password_reset/<token>', methods=['GET', 'POST'])
def password_reset(token):
    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not new_password or not confirm_password:
            flash('Please enter and confirm your new password', 'error')
            return render_template('password_reset.html', token=token)

        if new_password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('password_reset.html', token=token)

        success, message = auth_manager.reset_password_with_token(token, new_password)

        if success:
            flash('Password reset successfully. Please log in with your new password.', 'success')
            return redirect(url_for('index'))
        else:
            flash(message, 'error')

    return render_template('password_reset.html', token=token)


@app.route('/change_password', methods=['POST'])
@require_auth()
def change_password():
    current_password = request.form.get('current_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if not all([current_password, new_password, confirm_password]):
        flash('All fields are required', 'error')
        return redirect(url_for('security_settings'))

    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('security_settings'))

    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or not user_type:
        flash('Session information not found', 'error')
        return redirect(url_for('security_settings'))

    success, message = auth_manager.change_password(user_id, user_type, current_password, new_password)

    if success:
        flash('Password changed successfully', 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('security_settings'))


@app.route('/change_cre_password', methods=['GET', 'POST'])
@require_cre
def change_cre_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not all([current_password, new_password, confirm_password]):
            flash('All fields are required', 'error')
            return render_template('change_cre_password.html')

        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return render_template('change_cre_password.html')

        user_id = session.get('user_id')
        user_type = session.get('user_type')

        if not user_id or not user_type:
            flash('Session information not found', 'error')
            return render_template('change_cre_password.html')

        success, message = auth_manager.change_password(user_id, user_type, current_password, new_password)

        if success:
            flash('Password changed successfully', 'success')
            return redirect(url_for('cre_dashboard'))
        else:
            flash(message, 'error')

    return render_template('change_cre_password.html')


@app.route('/change_ps_password', methods=['GET', 'POST'])
@require_ps
def change_ps_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not all([current_password, new_password, confirm_password]):
            flash('All fields are required', 'error')
            return render_template('change_ps_password.html')

        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return render_template('change_ps_password.html')

        user_id = session.get('user_id')
        user_type = session.get('user_type')

        if not user_id or not user_type:
            flash('Session information not found', 'error')
            return render_template('change_ps_password.html')

        success, message = auth_manager.change_password(user_id, user_type, current_password, new_password)

        if success:
            flash('Password changed successfully', 'success')
            return redirect(url_for('ps_dashboard'))
        else:
            flash(message, 'error')

    return render_template('change_ps_password.html')


@app.route('/security_settings')
@require_auth()
def security_settings():
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or not user_type:
        flash('Session information not found', 'error')
        return redirect(url_for('index'))

    # Get active sessions
    sessions = auth_manager.get_user_sessions(user_id, user_type)

    # Get audit logs
    audit_logs = auth_manager.get_audit_logs(user_id, user_type, limit=20)

    return render_template('security_settings.html', sessions=sessions, audit_logs=audit_logs)


@app.route('/security_audit')
@require_admin
def security_audit():
    """Security audit dashboard"""
    return render_template('security_audit.html')


@app.route('/run_security_audit', methods=['POST'])
@require_admin
def run_security_audit():
    """Run comprehensive security audit"""
    try:
        # Run security verification
        audit_results = run_security_verification(supabase)

        # Log the security audit
        user_id = session.get('user_id')
        user_type = session.get('user_type')
        
        if user_id and user_type:
            auth_manager.log_audit_event(
                user_id=user_id,
                user_type=user_type,
                action='SECURITY_AUDIT_RUN',
                resource='security_audit',
                details={'overall_score': audit_results.get('overall_score', 0)}
            )

        return jsonify({
            'success': True,
            'results': audit_results
        })
    except Exception as e:
        print(f"Error running security audit: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        })


@app.route('/terminate_session', methods=['POST'])
@require_auth()
def terminate_session():
    try:
        data = request.get_json()
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({'success': False, 'message': 'Session ID required'})

        auth_manager.deactivate_session(session_id)

        user_id = session.get('user_id')
        user_type = session.get('user_type')
        
        if user_id and user_type:
            auth_manager.log_audit_event(
                user_id=user_id,
                user_type=user_type,
                action='SESSION_TERMINATED',
                details={'terminated_session': session_id}
            )

        return jsonify({'success': True, 'message': 'Session terminated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/terminate_all_sessions', methods=['POST'])
@require_auth()
def terminate_all_sessions():
    try:
        user_id = session.get('user_id')
        user_type = session.get('user_type')
        current_session = session.get('session_id')

        if user_id and user_type and current_session:
            auth_manager.deactivate_all_user_sessions(user_id, user_type, current_session)
            auth_manager.log_audit_event(
                user_id=user_id,
                user_type=user_type,
                action='ALL_SESSIONS_TERMINATED',
                details={'except_session': current_session}
            )
        else:
            return jsonify({'success': False, 'message': 'Session information not found'})

        return jsonify({'success': True, 'message': 'All other sessions terminated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/admin_dashboard')
@require_admin
def admin_dashboard():
    # Get counts for dashboard with better error handling and actual queries
    try:
        # Get actual counts from database with proper queries
        cre_count = get_accurate_count('cre_users')
        ps_count = get_accurate_count('ps_users')
        leads_count = get_accurate_count('lead_master')
        unassigned_leads = get_accurate_count('lead_master', {'assigned': 'No'})

        print(
            f"Dashboard counts - CRE: {cre_count}, PS: {ps_count}, Total Leads: {leads_count}, Unassigned: {unassigned_leads}")

    except Exception as e:
        print(f"Error getting dashboard counts: {e}")
        cre_count = ps_count = leads_count = unassigned_leads = 0

    # Log dashboard access
    user_id = session.get('user_id')
    user_type = session.get('user_type')
    if user_id and user_type:
        auth_manager.log_audit_event(
            user_id=user_id,
            user_type=user_type,
            action='DASHBOARD_ACCESS',
            resource='admin_dashboard'
        )

    return render_template('admin_dashboard.html',
                           cre_count=cre_count,
                           ps_count=ps_count,
                           leads_count=leads_count,
                           unassigned_leads=unassigned_leads)


@app.route('/upload_data', methods=['GET', 'POST'])
@require_admin
def upload_data():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)

        file = request.files['file']
        source = request.form.get('source', '').strip()

        if not source:
            flash('Please select a data source', 'error')
            return redirect(request.url)

        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)

        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(str(file.filename))
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            try:
                file.save(filepath)

                # Check file size
                file_size = os.path.getsize(filepath)
                if file_size > 50 * 1024 * 1024:  # 50MB limit
                    flash('File too large. Maximum size is 50MB.', 'error')
                    os.remove(filepath)
                    return redirect(request.url)

                print(f"Processing file: {filename} ({file_size / 1024 / 1024:.2f} MB)")

                # Read the file based on extension
                if filename.lower().endswith('.csv'):
                    data = read_csv_file(filepath)
                else:
                    data = read_excel_file(filepath)

                if not data:
                    flash('No valid data found in file', 'error')
                    os.remove(filepath)
                    return redirect(request.url)

                print(f"Read {len(data)} rows from file")

                # Get current sequence number for UID generation
                result = supabase.table('lead_master').select('uid').execute()
                current_count = len(result.data) if result.data else 0

                # Prepare leads data for batch insert
                leads_to_insert = []
                skipped_rows = 0

                for index, row in enumerate(data):
                    try:
                        # Validate required fields
                        required_fields = ['customer_name', 'customer_mobile_number', 'date']
                        if not all(key in row and str(row[key]).strip() for key in required_fields):
                            skipped_rows += 1
                            continue

                        uid = generate_uid(source, row['customer_mobile_number'],
                                           current_count + len(leads_to_insert) + 1)

                        lead_data = {
                            'uid': uid,
                            'date': str(row['date']).strip(),
                            'customer_name': str(row['customer_name']).strip(),
                            'customer_mobile_number': str(row['customer_mobile_number']).strip(),
                            'source': source,
                            'assigned': 'No',
                            'final_status': 'Pending'
                        }

                        leads_to_insert.append(lead_data)


                    except Exception as e:
                        print(f"Error processing row {index}: {e}")
                        skipped_rows += 1
                        continue

                if not leads_to_insert:
                    flash('No valid leads found to insert', 'error')
                    os.remove(filepath)
                    return redirect(request.url)

                print(f"Prepared {len(leads_to_insert)} leads for insertion")

                # Batch insert leads
                success_count = batch_insert_leads(leads_to_insert)

                # Log data upload
                auth_manager.log_audit_event(
                    user_id=session.get('user_id'),
                    user_type=session.get('user_type'),
                    action='DATA_UPLOAD',
                    resource='lead_master',
                    details={
                        'source': source,
                        'records_uploaded': success_count,
                        'filename': filename,
                        'file_size_mb': round(file_size / 1024 / 1024, 2),
                        'skipped_rows': skipped_rows
                    }
                )

                # Create success message
                message = f'Successfully uploaded {success_count} leads'
                if skipped_rows > 0:
                    message += f' ({skipped_rows} rows skipped due to missing data)'
                message += '. Please go to "Assign Leads" to assign them to CREs.'

                flash(message, 'success')

                # Clean up uploaded file
                os.remove(filepath)

            except Exception as e:
                print(f"Error processing file: {e}")
                flash(f'Error processing file: {str(e)}', 'error')
                if os.path.exists(filepath):
                    os.remove(filepath)
        else:
            flash('Invalid file format. Please upload CSV or Excel files only.', 'error')

    return render_template('upload_data.html')

@app.route('/assign_leads')
@require_admin
def assign_leads():
    try:
        # Fetch all unassigned leads in batches of 1000
        all_unassigned_leads = []
        batch_size = 1000
        offset = 0
        while True:
            result = supabase.table('lead_master').select('*').eq('assigned', 'No').range(offset, offset + batch_size - 1).execute()
            batch = result.data or []
            all_unassigned_leads.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size

        # Organize by source
        leads_by_source = {}
        for lead in all_unassigned_leads:
            source = lead.get('source', 'Unknown')
            leads_by_source.setdefault(source, []).append(lead)

        # Get CREs
        cres = safe_get_data('cre_users')

        # Get accurate total unassigned count
        actual_unassigned_count = get_accurate_count('lead_master', {'assigned': 'No'})

        # Get accurate per-source unassigned counts
        source_unassigned_counts = {}
        for source in leads_by_source.keys():
            source_unassigned_counts[source] = get_accurate_count('lead_master', {'assigned': 'No', 'source': source})

        return render_template('assign_leads.html',
                               unassigned_leads=all_unassigned_leads,
                               actual_unassigned_count=actual_unassigned_count,
                               cres=cres,
                               leads_by_source=leads_by_source,
                               source_unassigned_counts=source_unassigned_counts)
    except Exception as e:
        print(f"Error loading assign leads data: {e}")
        flash(f'Error loading data: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))


@app.route('/assign_leads_dynamic_action', methods=['POST'])
@require_admin
def assign_leads_dynamic_action():
    try:
        data = request.get_json()
        assignments = data.get('assignments', [])

        if not assignments:
            return jsonify({'success': False, 'message': 'No assignments provided'}), 400

        # Fetch all unassigned leads in batches
        all_unassigned = []
        batch_size = 1000
        offset = 0
        while True:
            result = supabase.table('lead_master').select('*').eq('assigned', 'No').range(offset, offset + batch_size - 1).execute()
            batch = result.data or []
            all_unassigned.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size

        leads_by_source = {}
        for lead in all_unassigned:
            source = lead.get('source', 'Unknown')
            leads_by_source.setdefault(source, []).append(lead)

        total_assigned = 0

        for assignment in assignments:
            cre_id = assignment.get('cre_id')
            source = assignment.get('source')
            quantity = assignment.get('quantity')

            if not cre_id or not source or not quantity:
                continue

            # Get CRE details
            cre_data = supabase.table('cre_users').select('*').eq('id', cre_id).execute()
            if not cre_data.data:
                continue

            cre = cre_data.data[0]
            leads = leads_by_source.get(source, [])

            if not leads:
                print(f"No unassigned leads found for source {source}")
                continue

            random.shuffle(leads)
            leads_to_assign = leads[:quantity]
            leads_by_source[source] = leads[quantity:]  # Remove assigned leads

            for lead in leads_to_assign:
                update_data = {
                    'cre_name': cre['name'],
                    'assigned': 'Yes',
                    'cre_assigned_at': datetime.now().isoformat()

                }

                try:
                    supabase.table('lead_master').update(update_data).eq('uid', lead['uid']).execute()
                    total_assigned += 1
                    print(f"Assigned lead {lead['uid']} to CRE {cre['name']} for source {source}")
                    if total_assigned % 100 == 0:
                        eventlet.sleep(0.1)
                except Exception as e:
                    print(f"Error assigning lead {lead['uid']}: {e}")

        print(f"Total leads assigned: {total_assigned}")
        return jsonify({'success': True, 'message': f'Total {total_assigned} leads assigned successfully'})

    except Exception as e:
        print(f"Error in dynamic lead assignment: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
@app.route('/add_cre', methods=['GET', 'POST'])
@require_admin
def add_cre():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()

        if not all([name, username, password, phone, email]):
            flash('All fields are required', 'error')
            return render_template('add_cre.html')

        if not auth_manager.validate_password_strength(password):
            flash(
                'Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character',
                'error')
            return render_template('add_cre.html')

        try:
            # Check if username already exists
            existing = supabase.table('cre_users').select('username').eq('username', username).execute()
            if existing.data:
                flash('Username already exists', 'error')
                return render_template('add_cre.html')

            # Hash password
            password_hash, salt = auth_manager.hash_password(password)

            # Replace the existing cre_data creation with this:
            cre_data = {
                'name': name,
                'username': username,
                'password': password,  # Keep for backward compatibility
                'password_hash': password_hash,
                'salt': salt,
                'phone': phone,
                'email': email,
                'is_active': True,
                'role': 'cre',
                'failed_login_attempts': 0
            }

            result = supabase.table('cre_users').insert(cre_data).execute()

            # Log CRE creation
            auth_manager.log_audit_event(
                user_id=session.get('user_id'),
                user_type=session.get('user_type'),
                action='CRE_CREATED',
                resource='cre_users',
                resource_id=str(result.data[0]['id']) if result.data else None,
                details={'cre_name': name, 'username': username}
            )

            flash('CRE added successfully', 'success')
            return redirect(url_for('manage_cre'))
        except Exception as e:
            flash(f'Error adding CRE: {str(e)}', 'error')

    return render_template('add_cre.html')


@app.route('/add_ps', methods=['GET', 'POST'])
@require_admin
def add_ps():
    branches = ['SOMAJIGUDA', 'ATTAPUR', 'BEGUMPET', 'KOMPALLY', 'MALAKPET', 'SRINAGAR COLONY', 'TOLICHOWKI',
                'VANASTHALIPURAM']

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        branch = request.form.get('branch', '').strip()

        if not all([name, username, password, phone, email, branch]):
            flash('All fields are required', 'error')
            return render_template('add_ps.html', branches=branches)

        if not auth_manager.validate_password_strength(password):
            flash(
                'Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character',
                'error')
            return render_template('add_ps.html', branches=branches)

        try:
            # Check if username already exists
            existing = supabase.table('ps_users').select('username').eq('username', username).execute()
            if existing.data:
                flash('Username already exists', 'error')
                return render_template('add_ps.html', branches=branches)

            # Hash password
            password_hash, salt = auth_manager.hash_password(password)

            # Replace the existing ps_data creation with this:
            ps_data = {
                'name': name,
                'username': username,
                'password': password,  # Keep for backward compatibility
                'password_hash': password_hash,
                'salt': salt,
                'phone': phone,
                'email': email,
                'branch': branch,
                'is_active': True,
                'role': 'ps',
                'failed_login_attempts': 0
            }

            result = supabase.table('ps_users').insert(ps_data).execute()

            # Log PS creation
            auth_manager.log_audit_event(
                user_id=session.get('user_id'),
                user_type=session.get('user_type'),
                action='PS_CREATED',
                resource='ps_users',
                resource_id=str(result.data[0]['id']) if result.data else None,
                details={'ps_name': name, 'username': username, 'branch': branch}
            )

            flash('Product Specialist added successfully', 'success')
            return redirect(url_for('manage_ps'))
        except Exception as e:
            flash(f'Error adding Product Specialist: {str(e)}', 'error')

    return render_template('add_ps.html', branches=branches)


@app.route('/manage_cre')
@require_admin
def manage_cre():
    try:
        cre_users = safe_get_data('cre_users')
        return render_template('manage_cre.html', cre_users=cre_users)
    except Exception as e:
        flash(f'Error loading CRE users: {str(e)}', 'error')
        return render_template('manage_cre.html', cre_users=[])


@app.route('/manage_ps')
@require_admin
def manage_ps():
    try:
        ps_users = safe_get_data('ps_users')
        return render_template('manage_ps.html', ps_users=ps_users)
    except Exception as e:
        flash(f'Error loading PS users: {str(e)}', 'error')
        return render_template('manage_ps.html', ps_users=[])


@app.route('/toggle_ps_status/<int:ps_id>', methods=['POST'])
@require_admin
def toggle_ps_status(ps_id):
    try:
        data = request.get_json()
        active_status = data.get('active', True)

        # Update PS status
        result = supabase.table('ps_users').update({
            'is_active': active_status
        }).eq('id', ps_id).execute()

        if result.data:
            # Log status change
            auth_manager.log_audit_event(
                user_id=session.get('user_id'),
                user_type=session.get('user_type'),
                action='PS_STATUS_CHANGED',
                resource='ps_users',
                resource_id=str(ps_id),
                details={'new_status': 'active' if active_status else 'inactive'}
            )

            return jsonify({'success': True, 'message': 'PS status updated successfully'})
        else:
            return jsonify({'success': False, 'message': 'PS not found'})

    except Exception as e:
        print(f"Error toggling PS status: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/manage_leads')
@require_admin
def manage_leads():
    try:
        leads = safe_get_data('lead_master')
        return render_template('manage_leads.html', leads=leads)
    except Exception as e:
        flash(f'Error loading leads: {str(e)}', 'error')
        return render_template('manage_leads.html', leads=[])


@app.route('/delete_leads', methods=['POST'])
@require_admin
def delete_leads():
    try:
        delete_type = request.form.get('delete_type')

        if delete_type == 'single':
            uid = request.form.get('uid')
            if not uid:
                return jsonify({'success': False, 'message': 'No UID provided'})

            # Delete from ps_followup_master first (foreign key constraint)
            supabase.table('ps_followup_master').delete().eq('lead_uid', uid).execute()

            # Delete from lead_master
            result = supabase.table('lead_master').delete().eq('uid', uid).execute()

            # Log deletion
            auth_manager.log_audit_event(
                user_id=session.get('user_id'),
                user_type=session.get('user_type'),
                action='LEAD_DELETED',
                resource='lead_master',
                resource_id=uid,
                details={'delete_type': 'single'}
            )

            return jsonify({'success': True, 'message': 'Lead deleted successfully'})

        elif delete_type == 'bulk':
            uids = request.form.getlist('uids')
            if not uids:
                return jsonify({'success': False, 'message': 'No leads selected'})

            # Delete from ps_followup_master first
            for uid in uids:
                supabase.table('ps_followup_master').delete().eq('lead_uid', uid).execute()

            # Delete from lead_master
            for uid in uids:
                supabase.table('lead_master').delete().eq('uid', uid).execute()

            # Log bulk deletion
            auth_manager.log_audit_event(
                user_id=session.get('user_id'),
                user_type=session.get('user_type'),
                action='LEADS_BULK_DELETED',
                resource='lead_master',
                details={'delete_type': 'bulk', 'count': len(uids), 'uids': uids}
            )

            return jsonify({'success': True, 'message': f'{len(uids)} leads deleted successfully'})

        else:
            return jsonify({'success': False, 'message': 'Invalid delete type'})

    except Exception as e:
        print(f"Error deleting leads: {e}")
        return jsonify({'success': False, 'message': f'Error deleting leads: {str(e)}'})


@app.route('/bulk_unassign_leads', methods=['POST'])
@require_admin
def bulk_unassign_leads():
    try:
        uids = request.form.getlist('uids')
        if not uids:
            return jsonify({'success': False, 'message': 'No leads selected'})

        # Update leads to unassigned
        for uid in uids:
            supabase.table('lead_master').update({
                'cre_name': None,
                'assigned': 'No',
                'ps_name': None
            }).eq('uid', uid).execute()

            # Also remove from PS followup if exists
            supabase.table('ps_followup_master').delete().eq('lead_uid', uid).execute()

        # Log bulk unassignment
        auth_manager.log_audit_event(
            user_id=session.get('user_id'),
            user_type=session.get('user_type'),
            action='LEADS_BULK_UNASSIGNED',
            resource='lead_master',
            details={'count': len(uids), 'uids': uids}
        )

        return jsonify({'success': True, 'message': f'{len(uids)} leads unassigned successfully'})

    except Exception as e:
        print(f"Error unassigning leads: {e}")
        return jsonify({'success': False, 'message': f'Error unassigning leads: {str(e)}'})


@app.route('/delete_cre/<int:cre_id>')
@require_admin
def delete_cre(cre_id):
    try:
        # Get CRE name before deletion for updating leads
        cre_result = supabase.table('cre_users').select('name').eq('id', cre_id).execute()
        if cre_result.data:
            cre_name = cre_result.data[0]['name']

            # Update leads assigned to this CRE to unassigned
            supabase.table('lead_master').update({
                'cre_name': None,
                'assigned': 'No'
            }).eq('cre_name', cre_name).execute()

            # Delete the CRE user
            supabase.table('cre_users').delete().eq('id', cre_id).execute()

            # Log CRE deletion
            auth_manager.log_audit_event(
                user_id=session.get('user_id'),
                user_type=session.get('user_type'),
                action='CRE_DELETED',
                resource='cre_users',
                resource_id=str(cre_id),
                details={'cre_name': cre_name}
            )

            flash('CRE deleted successfully', 'success')
        else:
            flash('CRE not found', 'error')
    except Exception as e:
        flash(f'Error deleting CRE: {str(e)}', 'error')

    return redirect(url_for('manage_cre'))


@app.route('/delete_ps/<int:ps_id>')
@require_admin
def delete_ps(ps_id):
    try:
        # Get PS name before deletion for updating leads
        ps_result = supabase.table('ps_users').select('name').eq('id', ps_id).execute()
        if ps_result.data:
            ps_name = ps_result.data[0]['name']

            # Update leads assigned to this PS to unassigned
            supabase.table('lead_master').update({
                'ps_name': None
            }).eq('ps_name', ps_name).execute()

            # Delete the PS user
            supabase.table('ps_users').delete().eq('id', ps_id).execute()

            # Log PS deletion
            auth_manager.log_audit_event(
                user_id=session.get('user_id'),
                user_type=session.get('user_type'),
                action='PS_DELETED',
                resource='ps_users',
                resource_id=str(ps_id),
                details={'ps_name': ps_name}
            )

            flash('Product Specialist deleted successfully', 'success')
        else:
            flash('Product Specialist not found', 'error')
    except Exception as e:
        flash(f'Error deleting Product Specialist: {str(e)}', 'error')

    return redirect(url_for('manage_ps'))


@app.route('/add_lead', methods=['GET', 'POST'])
@require_cre
def add_lead():
    from datetime import datetime, date
    branches = ['SOMAJIGUDA', 'ATTAPUR', 'TOLICHOWKI', 'KOMPALLY', 'SRINAGAR COLONY', 'MALAKPET', 'VANASTHALIPURAM']
    ps_users = safe_get_data('ps_users')
    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        customer_mobile_number = request.form.get('customer_mobile_number', '').strip()
        source = request.form.get('source', '').strip()
        lead_status = request.form.get('lead_status', '').strip()
        lead_category = request.form.get('lead_category', '').strip()
        model_interested = request.form.get('model_interested', '').strip()
        branch = request.form.get('branch', '').strip()
        ps_name = request.form.get('ps_name', '').strip()
        final_status = request.form.get('final_status', 'Pending').strip()
        follow_up_date = request.form.get('follow_up_date', '').strip()
        remark = request.form.get('remark', '').strip()
        date_now = datetime.now().strftime('%Y-%m-%d')
        # Validation
        if not customer_name or not customer_mobile_number or not source:
            flash('Please fill all required fields', 'error')
            return render_template('add_lead.html', branches=branches, ps_users=ps_users)
        # UID: Source initial (uppercase) + '-' + first 5 letters of name (no spaces, uppercase) + last 5 digits of phone
        src_initial = source[0].upper() if source else 'X'
        name_part = ''.join(customer_name.split()).upper()[:5]
        phone_part = customer_mobile_number[-5:] if len(customer_mobile_number) >= 5 else customer_mobile_number
        uid = f"{src_initial}-{name_part}{phone_part}"
        # CRE name from session
        cre_name = session.get('cre_name')
        # Prepare lead data
        lead_data = {
            'uid': uid,
            'date': date_now,
            'customer_name': customer_name,
            'customer_mobile_number': customer_mobile_number,
            'source': source,
            'lead_status': lead_status,
            'lead_category': lead_category,
            'model_interested': model_interested,
            'branch': branch,
            'ps_name': ps_name if ps_name else None,
            'final_status': final_status,
            'follow_up_date': follow_up_date if follow_up_date else None,
            'assigned': 'No',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'first_remark': remark,
            'cre_name': cre_name,
            'first_call_date': date_now
        }
        try:
            supabase.table('lead_master').insert(lead_data).execute()
            flash('Lead added successfully!', 'success')
            return redirect(url_for('cre_dashboard'))
        except Exception as e:
            flash(f'Error adding lead: {str(e)}', 'error')
            return render_template('add_lead.html', branches=branches, ps_users=ps_users)
    return render_template('add_lead.html', branches=branches, ps_users=ps_users)


@app.route('/cre_dashboard')
@require_cre
def cre_dashboard():
    start_time = time.time()
    cre_name = session.get('cre_name')
    today = datetime.now().date()

    try:
        t0 = time.time()
        # Get all leads assigned to this CRE
        all_leads = safe_get_data('lead_master', {'cre_name': cre_name})
        print(f"[PERF] cre_dashboard: safe_get_data('lead_master') took {time.time() - t0:.3f} seconds")

        t1 = time.time()
        # Get pending leads (assigned but no first call date), sorted by cre_assigned_at ascending
        pending_leads = sorted(
            [lead for lead in all_leads if not lead.get('first_call_date')],
            key=lambda l: l.get('cre_assigned_at') or ''
        )
        print(f"[PERF] cre_dashboard: pending_leads filter/sort took {time.time() - t1:.3f} seconds")

        t2 = time.time()
        # Get today's followups
        todays_followups = [
            lead for lead in all_leads
            if lead.get('follow_up_date') and lead.get('follow_up_date').startswith(str(today))
        ]
        print(f"[PERF] cre_dashboard: todays_followups filter took {time.time() - t2:.3f} seconds")

        t3 = time.time()
        # Get attended leads (leads with at least one call)
        attended_leads = [lead for lead in all_leads if lead.get('first_call_date')]
        print(f"[PERF] cre_dashboard: attended_leads filter took {time.time() - t3:.3f} seconds")

        t4 = time.time()
        # Get leads assigned to PS
        assigned_to_ps = [lead for lead in all_leads if lead.get('ps_name')]
        print(f"[PERF] cre_dashboard: assigned_to_ps filter took {time.time() - t4:.3f} seconds")

        t5 = time.time()
        # Get won leads (leads with final status "Won")
        won_leads = [lead for lead in all_leads if lead.get('final_status') == 'Won']
        # Get lost leads (leads with final status "Lost")
        lost_leads = [lead for lead in all_leads if lead.get('final_status') == 'Lost']
        print(f"[PERF] cre_dashboard: won/lost_leads filter took {time.time() - t5:.3f} seconds")

        # --- Walk-in Follow-up Section ---
        t6 = time.time()
        walkin_followups = []
        try:
            walkin_followups = [lead for lead in safe_get_data('walkin_data', {'walkin_cre_name': cre_name, 'walkin_followup_date': str(today)})]
        except Exception as e:
            walkin_followups = []
        print(f"[PERF] cre_dashboard: walkin_followups fetch/filter took {time.time() - t6:.3f} seconds")

        t7 = time.time()
        result = render_template('cre_dashboard.html',
                               pending_leads=pending_leads,
                               todays_followups=todays_followups,
                               attended_leads=attended_leads,
                               assigned_to_ps=assigned_to_ps,
                               won_leads=won_leads,
                               lost_leads=lost_leads,
                               walkin_followups=walkin_followups)
        print(f"[PERF] cre_dashboard: render_template took {time.time() - t7:.3f} seconds")
        print(f"[PERF] cre_dashboard TOTAL took {time.time() - start_time:.3f} seconds")
        return result
    except Exception as e:
        print(f"[PERF] cre_dashboard failed after {time.time() - start_time:.3f} seconds")
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('cre_dashboard.html',
                               pending_leads=[],
                               todays_followups=[],
                               attended_leads=[],
                               assigned_to_ps=[],
                               won_leads=[],
                               lost_leads=[])


@app.route('/update_lead/<uid>', methods=['GET', 'POST'])
@require_cre
def update_lead(uid):
    try:
        # Get lead data
        lead_result = supabase.table('lead_master').select('*').eq('uid', uid).execute()
        if not lead_result.data:
            flash('Lead not found', 'error')
            return redirect(url_for('cre_dashboard'))

        lead_data = lead_result.data[0]

        # Verify this lead belongs to the current CRE
        if lead_data.get('cre_name') != session.get('cre_name'):
            flash('Access denied - This lead is not assigned to you', 'error')
            return redirect(url_for('cre_dashboard'))

        # Get next call info
        next_call, completed_calls = get_next_call_info(lead_data)

        # Get PS users for branch selection
        ps_users = safe_get_data('ps_users')

        # Model options
        rizta_models = [
            'Rizta S Mono (2.9 kWh)',
            'Rizta S Super Matte (2.9 kWh)',
            'Rizta Z Mono (2.9 kWh)',
            'Rizta Z Duo (2.9 kWh)',
            'Rizta Z Super Matte (2.9 kWh)',
            'Rizta Z Mono (3.7 kWh)',
            'Rizta Z Duo (3.7 kWh)',
            'Rizta Z Super Matte (3.7 kWh)'
        ]

        x450_models = [
            '450 X (2.9 kWh)',
            '450 X (3.7 kWh)',
            '450 X (2.9 kWh) Pro Pack',
            '450 X (3.7 kWh) Pro Pack',
            '450 Apex STD'
        ]

        branches = ['SOMAJIGUDA', 'ATTAPUR', 'TOLICHOWKI', 'KOMPALLY', 'SRINAGAR COLONY', 'MALAKPET', 'VANASTHALIPURAM']

        lead_statuses = [
            'Busy on another Call', 'RNR', 'Call me Back', 'Interested',
            'Not Interested', 'Did Not Inquire', 'Lost to Competition',
            'Lost to Co Dealer', 'Call Disconnected', 'Wrong Number'
        ]

        if request.method == 'POST':
            update_data = {}

            # Update basic fields
            if request.form.get('customer_name'):
                update_data['customer_name'] = request.form['customer_name']

            if request.form.get('source'):
                update_data['source'] = request.form['source']

            if request.form.get('lead_category'):
                update_data['lead_category'] = request.form['lead_category']

            if request.form.get('model_interested'):
                update_data['model_interested'] = request.form['model_interested']

            if request.form.get('branch'):
                update_data['branch'] = request.form['branch']

            # Handle PS assignment and email notification
            ps_name = request.form.get('ps_name')
            if ps_name and ps_name != lead_data.get('ps_name'):
                update_data['ps_name'] = ps_name
                update_data['assigned'] = 'Yes'
                update_data['ps_assigned_at'] = datetime.now().isoformat()

                # Get PS details for followup creation
                ps_user = next((ps for ps in ps_users if ps['name'] == ps_name), None)
                if ps_user:
                    # Create PS followup record
                    updated_lead_data = {**lead_data, **update_data}
                    create_or_update_ps_followup(updated_lead_data, ps_name, ps_user['branch'])

                # Send email to PS
                try:
                    if ps_user:
                        lead_data_for_email = {**lead_data, **update_data}
                        socketio.start_background_task(send_email_to_ps, ps_user['email'], ps_user['name'], lead_data_for_email, session.get('cre_name'))
                        flash(f'Lead assigned to {ps_name} and email notification sent', 'success')
                    else:
                        flash(f'Lead assigned to {ps_name}', 'success')
                except Exception as e:
                    print(f"Error sending email: {e}")
                    flash(f'Lead assigned to {ps_name} (email notification failed)', 'warning')

            if request.form.get('lead_status'):
                status = request.form['lead_status']
                update_data['lead_status'] = status
                
                # Automatically set final status to Lost for certain lead statuses
                if status in ['Lost to Co Dealer', 'Wrong Number']:
                    update_data['final_status'] = 'Lost'
                # If a fresh status, update cre_assigned_at to now
                if status in ['Call Disconnected', 'Busy on another Call', 'RNR', 'Call me Back']:
                    update_data['cre_assigned_at'] = datetime.now().isoformat()

            if request.form.get('follow_up_date'):
                update_data['follow_up_date'] = request.form['follow_up_date']

            if request.form.get('final_status'):
                final_status = request.form['final_status']
                update_data['final_status'] = final_status
                if final_status == 'Won':
                    update_data['won_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                elif final_status == 'Lost':
                    update_data['lost_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Handle call dates and remarks - only record for actual conversations
            if request.form.get('call_date') and request.form.get('call_remark'):
                lead_status = request.form.get('lead_status', '')

                # Only record call date and remark if it's an actual conversation
                non_conversation_statuses = ['Call me Back', 'RNR', 'Busy on another Call', 'Call Disconnected']

                if lead_status not in non_conversation_statuses:
                    # This was an actual conversation, record both call date and remark
                    update_data[f'{next_call}_call_date'] = request.form['call_date']
                    update_data[f'{next_call}_remark'] = request.form['call_remark']

            try:
                if update_data:
                    supabase.table('lead_master').update(update_data).eq('uid', uid).execute()

                    # Keep ps_followup_master.final_status in sync if final_status is updated and PS followup exists
                    if 'final_status' in update_data and lead_data.get('ps_name'):
                        ps_result = supabase.table('ps_followup_master').select('lead_uid').eq('lead_uid', uid).execute()
                        if ps_result.data:
                            supabase.table('ps_followup_master').update({'final_status': update_data['final_status']}).eq('lead_uid', uid).execute()

                    # Log lead update
                    auth_manager.log_audit_event(
                        user_id=session.get('user_id'),
                        user_type=session.get('user_type'),
                        action='LEAD_UPDATED',
                        resource='lead_master',
                        resource_id=uid,
                        details={'updated_fields': list(update_data.keys())}
                    )

                    flash('Lead updated successfully', 'success')
                else:
                    flash('No changes to update', 'info')
                return redirect(url_for('cre_dashboard'))
            except Exception as e:
                flash(f'Error updating lead: {str(e)}', 'error')

        # Fetch PS call summary from ps_followup_master
        ps_call_summary = {}
        if lead_data.get('ps_name'):
            ps_result = supabase.table('ps_followup_master').select('*').eq('lead_uid', uid).execute()
            if ps_result.data:
                ps_followup = ps_result.data[0]
                call_order = ['first', 'second', 'third']
                for call in call_order:
                    date_key = f"{call}_call_date"
                    remark_key = f"{call}_call_remark"
                    ps_call_summary[call] = {
                        "date": ps_followup.get(date_key),
                        "remark": ps_followup.get(remark_key)
                    }

        return render_template('update_lead.html',
                               lead=lead_data,
                               ps_users=ps_users,
                               rizta_models=rizta_models,
                               x450_models=x450_models,
                               branches=branches,
                               lead_statuses=lead_statuses,
                               next_call=next_call,
                               completed_calls=completed_calls,
                               today=date.today(),
                               ps_call_summary=ps_call_summary)

    except Exception as e:
        flash(f'Error loading lead: {str(e)}', 'error')
        return redirect(url_for('cre_dashboard'))


@app.route('/ps_dashboard')
@require_ps
def ps_dashboard():
    start_time = time.time()
    ps_name = session.get('ps_name')
    today = datetime.now().date()

    try:
        t0 = time.time()
        # Get all assigned leads
        assigned_leads = safe_get_data('ps_followup_master', {'ps_name': ps_name})
        print(f"[PERF] ps_dashboard: safe_get_data('ps_followup_master') took {time.time() - t0:.3f} seconds")

        t1 = time.time()
        # Get pending leads (assigned but no first call date)
        pending_leads = [lead for lead in assigned_leads if not lead.get('first_call_date')]
        print(f"[PERF] ps_dashboard: pending_leads filter took {time.time() - t1:.3f} seconds")

        t2 = time.time()
        # Get today's followups
        todays_followups = [
            lead for lead in assigned_leads
            if lead.get('follow_up_date') and lead.get('follow_up_date').startswith(str(today))
        ]
        print(f"[PERF] ps_dashboard: todays_followups filter took {time.time() - t2:.3f} seconds")

        t3 = time.time()
        # Get attended leads (leads with at least one call)
        attended_leads = [lead for lead in assigned_leads if lead.get('first_call_date')]
        print(f"[PERF] ps_dashboard: attended_leads filter took {time.time() - t3:.3f} seconds")

        t4 = time.time()
        # Get lost leads (assigned leads with final status "Lost")
        lost_leads = [lead for lead in assigned_leads if lead.get('final_status') == 'Lost']
        print(f"[PERF] ps_dashboard: lost_leads filter took {time.time() - t4:.3f} seconds")

        t5 = time.time()
        result = render_template('ps_dashboard.html',
                               assigned_leads=assigned_leads,
                               pending_leads=pending_leads,
                               todays_followups=todays_followups,
                               attended_leads=attended_leads,
                               lost_leads=lost_leads)
        print(f"[PERF] ps_dashboard: render_template took {time.time() - t5:.3f} seconds")
        print(f"[PERF] ps_dashboard TOTAL took {time.time() - start_time:.3f} seconds")
        return result
    except Exception as e:
        print(f"[PERF] ps_dashboard failed after {time.time() - start_time:.3f} seconds")
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('ps_dashboard.html',
                               assigned_leads=[],
                               pending_leads=[],
                               todays_followups=[],
                               attended_leads=[])


@app.route('/update_ps_lead/<uid>', methods=['GET', 'POST'])
@require_ps
def update_ps_lead(uid):
    try:
        # Get PS followup data
        ps_result = supabase.table('ps_followup_master').select('*').eq('lead_uid', uid).execute()
        if not ps_result.data:
            flash('Lead not found', 'error')
            return redirect(url_for('ps_dashboard'))

        ps_data = ps_result.data[0]

        # Fetch CRE call summary from lead_master
        lead_result = supabase.table('lead_master').select('*').eq('uid', uid).execute()
        cre_call_summary = {}
        if lead_result.data:
            lead = lead_result.data[0]
            call_order = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh']
            for call in call_order:
                date_key = f"{call}_call_date"
                remark_key = f"{call}_remark"
                cre_call_summary[call] = {
                    "date": lead.get(date_key),
                    "remark": lead.get(remark_key)
                }
        else:
            cre_call_summary = {}

        # Verify this lead belongs to the current PS
        if ps_data.get('ps_name') != session.get('ps_name'):
            flash('Access denied - This lead is not assigned to you', 'error')
            return redirect(url_for('ps_dashboard'))

        # Get next call info for PS (only 3 calls)
        next_call, completed_calls = get_next_ps_call_info(ps_data)

        if request.method == 'POST':
            update_data = {}

            if request.form.get('follow_up_date'):
                update_data['follow_up_date'] = request.form['follow_up_date']

            if request.form.get('final_status'):
                final_status = request.form['final_status']
                update_data['final_status'] = final_status
                if final_status == 'Won':
                    update_data['won_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                elif final_status == 'Lost':
                    update_data['lost_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Handle call dates and remarks for the next available call
            if request.form.get('call_date'):
                update_data[f'{next_call}_call_date'] = request.form['call_date']

            if request.form.get('call_remark'):
                update_data[f'{next_call}_call_remark'] = request.form['call_remark']
                # Emit notification to CRE dashboard
                socketio.emit(
                    'ps_remark_added',
                    {
                        'customer_name': ps_data.get('customer_name'),
                        'ps_remark': request.form['call_remark'],
                        'ps_name': ps_data.get('ps_name')
                    }
                )

            try:
                if update_data:
                    supabase.table('ps_followup_master').update(update_data).eq('lead_uid', uid).execute()

                    # Also update the main lead table final status
                    if request.form.get('final_status'):
                        final_status = request.form['final_status']
                        main_update_data = {'final_status': final_status}
                        if final_status == 'Won':
                            main_update_data['won_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        elif final_status == 'Lost':
                            main_update_data['lost_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        supabase.table('lead_master').update(main_update_data).eq('uid', uid).execute()

                    # Log PS lead update
                    auth_manager.log_audit_event(
                        user_id=session.get('user_id'),
                        user_type=session.get('user_type'),
                        action='PS_LEAD_UPDATED',
                        resource='ps_followup_master',
                        resource_id=uid,
                        details={'updated_fields': list(update_data.keys())}
                    )

                    flash('Lead updated successfully', 'success')
                else:
                    flash('No changes to update', 'info')
                return redirect(url_for('ps_dashboard'))
            except Exception as e:
                flash(f'Error updating lead: {str(e)}', 'error')

        return render_template('update_ps_lead.html',
                               lead=ps_data,
                               next_call=next_call,
                               completed_calls=completed_calls,
                               today=date.today(),
                               cre_call_summary=cre_call_summary)

    except Exception as e:
        flash(f'Error loading lead: {str(e)}', 'error')
        return redirect(url_for('ps_dashboard'))


@app.route('/logout')
@require_auth()
def logout():
    # Log logout
    auth_manager.log_audit_event(
        user_id=session.get('user_id'),
        user_type=session.get('user_type'),
        action='LOGOUT',
        details={'session_id': session.get('session_id')}
    )

    # Deactivate session
    if session.get('session_id'):
        auth_manager.deactivate_session(session.get('session_id'))

    session.clear()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('index'))


def generate_walkin_uid(source, mobile_number, sequence):
    """Generate UID for walk-in customers"""
    source_map = {
        'Walk-in': 'W',
        'Referral': 'R',
        'Social Media': 'S',
        'Website': 'WB',
        'Advertisement': 'A',
        'Other': 'O'
    }

    source_char = source_map.get(source, 'X')

    # Get sequence character (A-Z)
    sequence_char = chr(65 + (sequence % 26))  # A=65 in ASCII

    # Get last 4 digits of mobile number
    mobile_str = str(mobile_number).replace(' ', '').replace('-', '')
    mobile_last4 = mobile_str[-4:] if len(mobile_str) >= 4 else mobile_str.zfill(4)

    # Generate sequence number (0001, 0002, etc.)
    seq_num = f"{(sequence % 9999) + 1:04d}"

    return f"{source_char}{sequence_char}-{mobile_last4}-{seq_num}"


def send_quotation_email(customer_email, customer_name, quotation_data, pdf_path=None):
    """Send quotation email to walk-in customer with PDF attachment"""
    try:
        if not EMAIL_USER or not EMAIL_PASSWORD:
            print("Email credentials not configured. Skipping quotation email.")
            return False

        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = customer_email
        msg['Subject'] = f"Ather Quotation - {quotation_data['model_interested']}"

        # Email body with quotation details
        body = f"""
        Dear {customer_name},

        Thank you for visiting our Ather showroom. We are pleased to provide you with the quotation for your selected model.

        Quotation Details:
        - Model: {quotation_data['model_interested']}
        - Price: ₹{int(float(quotation_data['quotation_amount'])):,}
        - Branch: {quotation_data['ps_branch']}
        - Quotation ID: {quotation_data['uid']}

        Additional Details:
        {quotation_data.get('quotation_details', 'Standard configuration')}

        Key Features:
        • Zero emissions, 100% electric
        • Advanced connectivity features
        • Fast charging capability
        • Comprehensive warranty
        • Pan-India service network

        Next Steps:
        1. Visit our showroom for a test ride
        2. Explore financing options
        3. Book your Ather scooter

        Please find the detailed quotation attached as a PDF.

        For any queries or to schedule a test ride, please contact us:
        Phone: +91-XXXXXXXXXX
        Email: {EMAIL_USER}

        We look forward to welcoming you to the Ather family!

        Best regards,
        {quotation_data['ps_name']}
        Ather Energy - {quotation_data['ps_branch']} Branch
        """

        msg.attach(MIMEText(body, 'plain'))

        # Attach PDF if provided
        if pdf_path and os.path.exists(pdf_path):
            try:
                from email.mime.application import MIMEApplication
                with open(pdf_path, 'rb') as pdf_file:
                    pdf_attachment = MIMEApplication(pdf_file.read(), _subtype='pdf')
                    pdf_attachment.add_header('Content-Disposition', 'attachment',
                                              filename=f"Ather_Quotation_{quotation_data['uid']}.pdf")
                    msg.attach(pdf_attachment)
                print("PDF attached to email successfully")
            except Exception as e:
                print(f"Error attaching PDF: {e}")

        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        try:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            text = msg.as_string()
            server.sendmail(EMAIL_USER, customer_email, text)
            print(f"Quotation email sent successfully to {customer_email}")
            return True
        except Exception as e:
            print(f"Error logging in or sending email: {e}")
            return False
        finally:
            try:
                server.quit()
            except Exception as e:
                print(f"Error quitting server: {e}")

    except Exception as e:
        print(f"Error sending quotation email: {e}")
        return False


# Replace the `generate_quotation_pdf` function with this new implementation:
def generate_quotation_pdf(quotation_data):
    """Generate PDF quotation for walk-in customer using ReportLab with exact RAAM ATHER format"""
    try:
        # Create a temporary file for the PDF
        temp_dir = tempfile.gettempdir()
        pdf_filename = f"quotation_{quotation_data['uid']}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)

        # Create the PDF document
        doc = SimpleDocTemplate(pdf_path, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch)

        # Get styles
        styles = getSampleStyleSheet()

        # Custom styles to match exact format
        company_style = ParagraphStyle(
            'CompanyStyle',
            parent=styles['Normal'],
            fontSize=24,
            spaceAfter=5,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#147a49'),  # Green color for RAAM
            fontName='Helvetica-Bold'
        )

        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=20,
            alignment=TA_RIGHT,
            textColor=colors.HexColor('#2c3e50'),
            fontName='Helvetica-Bold'
        )

        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=4,
            fontName='Helvetica'
        )

        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.HexColor('#147a49'),
            fontName='Helvetica-Bold'
        )

        # Build the PDF content
        story = []

        # Header with logo and title - Fixed logo handling
        logo_element = None
        try:
            # Try multiple possible logo paths
            possible_paths = [
                'static/images/raam-ather-logo.png',
                'public/images/raam-ather-logo.png',
                os.path.join(os.path.dirname(__file__), 'static', 'images', 'raam-ather-logo.png'),
                os.path.join(os.path.dirname(__file__), 'public', 'images', 'raam-ather-logo.png')
            ]

            logo_loaded = False
            for logo_path in possible_paths:
                if os.path.exists(logo_path):
                    try:
                        logo_element = Image(logo_path, width=2 * inch, height=0.6 * inch)
                        logo_loaded = True
                        print(f"Logo loaded successfully from: {logo_path}")
                        break
                    except Exception as e:
                        print(f"Failed to load logo from {logo_path}: {e}")
                        continue

            if not logo_loaded:
                print("Logo file not found, using text fallback")
                # Fallback to styled text
                logo_element = Paragraph(
                    '<font color="#147a49" size="20"><b>RAAM</b></font><br/>'
                    '<font color="#2c3e50" size="16"><b>ATHER</b></font>',
                    company_style
                )
        except Exception as e:
            print(f"Error loading logo: {e}")
            # Text fallback
            logo_element = Paragraph(
                '<font color="#147a49" size="20"><b>RAAM</b></font><br/>'
                '<font color="#2c3e50" size="16"><b>ATHER</b></font>',
                company_style
            )

        # Header table with logo and title
        header_data = [[logo_element, Paragraph("Customer Quotation", title_style)]]
        header_table = Table(header_data, colWidths=[3 * inch, 4 * inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))

        story.append(header_table)

        # Add line separator
        line = Table([['']], colWidths=[7 * inch])
        line.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 2, colors.HexColor('#147a49')),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        story.append(line)

        # Quotation info box
        info_data = [
            [f"Quotation ID: {quotation_data['uid']}"],
            [f"Executive: {quotation_data['psName']}"],
            [f"Mobile: {quotation_data.get('executiveMobile', 'N/A')}"],
            [f"Date: {quotation_data['date']}"],
            [f"Branch: {quotation_data['branch']}"]
        ]

        info_table = Table(info_data, colWidths=[7 * inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
        ]))

        story.append(info_table)
        story.append(Spacer(1, 20))

        # Customer Details Header
        story.append(Paragraph("Customer Details", header_style))

        # Customer details table - exact format
        customer_data = [
            ['Full Name', quotation_data['customerName'], 'Mobile', quotation_data['customerMobile']],
            ['Email', quotation_data['email'], 'Address', quotation_data['address']],
            ['Occupation', quotation_data['occupation'], 'Lead Source', quotation_data['leadSource']],
            ['Lead Category', quotation_data['leadCategory'], 'Purchase Type', quotation_data['purchaseType']],
            ['Model', quotation_data['model'], 'Color', quotation_data['color']],
            ['Expected Delivery', quotation_data['expectedDate'], '', '']
        ]

        customer_table = Table(customer_data, colWidths=[1.2 * inch, 2.3 * inch, 1.2 * inch, 2.3 * inch])
        customer_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),  # First column bold
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),  # Third column bold
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        story.append(customer_table)
        story.append(Spacer(1, 25))

        # Pricing Summary
        story.append(Paragraph("Pricing Summary", header_style))

        # Calculate pricing based on model - exact calculations
        model_data = {
            "Rizta S Mono (2.9 kWh)": [114841, 17000],
            "Rizta S Super Matte (2.9 kWh)": [116841, 18000],
            "Rizta Z Mono (2.9 kWh)": [129841, 20000],
            "Rizta Z Duo (2.9 kWh)": [130841, 17000],
            "Rizta Z Super Matte (2.9 kWh)": [131841, 18000],
            "Rizta Z Mono (3.7 kWh)": [149842, 20000],
            "Rizta Z Duo (3.7 kWh)": [150842, 17000],
            "Rizta Z Super Matte (3.7 kWh)": [151842, 18000],
            "450 X (2.9 kWh)": [149047, 20000],
            "450 X (3.7 kWh)": [159046, 17000],
            "450 X (2.9 kWh) Pro Pack": [166047, 18000],
            "450 X (3.7 kWh) Pro Pack": [179046, 20000],
            "450 Apex STD": [189841, 0]
        }

        model_price = model_data.get(quotation_data['model'], [0, 0])[0]
        pro_pack_price = model_data.get(quotation_data['model'], [0, 0])[1]
        accessories_cost = int(quotation_data.get('accessories', 0))
        subsidy = 5000
        rto = 1000
        insurance = 5500
        ebw = 6000
        amc = 2500

        grand_total = model_price + pro_pack_price + accessories_cost + rto + insurance + ebw + amc - subsidy

        # Pricing table - exact format
        pricing_data = [
            ['Description', 'Amount (₹)'],
            ['Ex Showroom Price (incl. GST + Charger)', f'{model_price:,}'],
            ['PM E-Drive Subsidy', f'-{subsidy:,}'],
            ['Pro Pack', f'{pro_pack_price:,}'],
            ['RTO Registration', f'{rto:,}'],
            ['Insurance (Add-on)', f'{insurance:,}'],
            ['Accessories', f'{accessories_cost:,}'],
            ['EBW (Extended Battery Warranty)', f'{ebw:,}'],
            ['AMC (Annual Maintenance Contract)', f'{amc:,}'],
            ['Grand Total', f'₹{grand_total:,}']
        ]

        pricing_table = Table(pricing_data, colWidths=[5 * inch, 2 * inch])
        pricing_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            # Data rows
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -2), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            # Subsidy row highlight
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#e8f5e8')),
            # Grand total row
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#147a49')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
            # Grid and padding
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#ddd')),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        story.append(pricing_table)
        story.append(Spacer(1, 30))

        # Important Notes
        notes_text = """<b>Important Notes:</b><br/>
        • Vehicle delivery is subject to successful completion of PM-E Drive face verification.<br/>
        • This quotation is valid for 30 days from the date of issue.<br/>
        • Prices are subject to change without prior notice.<br/>
        • All government subsidies are subject to availability and eligibility criteria.<br/>
        • For financing options, please contact our sales team."""

        notes_para = Paragraph(notes_text, ParagraphStyle(
            'NotesStyle',
            parent=styles['Normal'],
            fontSize=10,
            leftIndent=15,
            rightIndent=15,
            spaceAfter=20,
            borderColor=colors.HexColor('#ffc107'),
            borderWidth=1,
            borderPadding=15,
            backColor=colors.HexColor('#fff8e1')
        ))

        story.append(notes_para)

        # Footer
        footer_text = f"""<b>Thank you for choosing Ather Energy!</b><br/>
        For any queries, please contact us at {quotation_data['branch']} branch<br/>
        Visit us: www.atherenergy.com | Call: 1800-123-ATHER"""

        footer_para = Paragraph(footer_text, ParagraphStyle(
            'FooterStyle',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#666'),
            borderColor=colors.HexColor('#eee'),
            borderWidth=1,
            borderPadding=15,
            spaceBefore=15
        ))

        story.append(footer_para)

        # Build the PDF
        doc.build(story)

        print(f"PDF generated successfully: {pdf_path}")
        return pdf_path

    except Exception as e:
        print(f"Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
        return None


def ensure_static_directories():
    """Ensure static directories exist"""
    try:
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        images_dir = os.path.join(static_dir, 'images')

        os.makedirs(static_dir, exist_ok=True)
        os.makedirs(images_dir, exist_ok=True)

        print(f"Static directories ensured: {images_dir}")
        return images_dir
    except Exception as e:
        print(f"Error creating static directories: {e}")
        return None


@app.route('/walkin', methods=['GET', 'POST'])
@require_ps
def walkin():
    """Standalone walk-in customer form"""
    if request.method == 'POST':
        # This would handle the walkin.html form submission
        # For now, redirect to the main walkin_customers route
        return redirect(url_for('walkin_customers'))

    return render_template('walkin.html')


@app.route('/walkin_customers', methods=['GET', 'POST'])
@require_ps
def walkin_customers():
    if request.method == 'POST':
        # Ensure static directories exist
        ensure_static_directories()
        # Get form data
        customer_name = request.form.get('customer_name', '').strip()
        customer_mobile = request.form.get('customer_mobile', '').strip()
        customer_email = request.form.get('customer_email', '').strip()
        customer_address = request.form.get('customer_address', '').strip()
        customer_age = request.form.get('customer_age', '').strip()
        occupation = request.form.get('occupation', '').strip()
        vehicle_usage = request.form.get('vehicle_usage', '').strip()
        daily_travel = request.form.get('daily_travel', '').strip()
        lead_source = request.form.get('lead_source', '').strip()
        lead_category = request.form.get('lead_category', '').strip()
        purchase_type = request.form.get('purchase_type', '').strip()
        model_interested = request.form.get('model_interested', '').strip()
        color = request.form.get('color', '').strip()
        pro_pack = request.form.get('pro_pack', '').strip()
        expected_delivery = request.form.get('expected_delivery', '').strip()
        accessories = request.form.get('accessories', '0').strip()
        quotation_details = request.form.get('quotation_details', '').strip()
        follow_up_date = request.form.get('follow_up_date', '').strip()
        status = request.form.get('status', 'Pending').strip()
        remarks = request.form.get('remarks', '').strip()

        # Validate required fields
        if not all([customer_name, customer_mobile, lead_source, model_interested]):
            flash('Please fill all required fields', 'error')
            return render_template('walkin_customers.html', today=datetime.now().strftime('%Y-%m-%d'))

        try:
            # Get current sequence number for UID generation
            result = supabase.table('walkin_data').select('uid').execute()
            current_count = len(result.data) if result.data else 0

            # Generate UID
            uid = generate_walkin_uid(lead_source, customer_mobile, current_count + 1)

            # Prepare quotation data for PDF
            quotation_data = {
                'uid': uid,
                'psName': session.get('ps_name'),
                'executiveMobile': session.get('phone', 'N/A'),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'branch': session.get('branch'),
                'customerName': customer_name,
                'customerMobile': customer_mobile,
                'email': customer_email if customer_email else 'N/A',
                'address': customer_address if customer_address else 'N/A',
                'occupation': occupation if occupation else 'N/A',
                'leadSource': lead_source,
                'leadCategory': lead_category if lead_category else 'N/A',
                'purchaseType': purchase_type if purchase_type else 'N/A',
                'model': model_interested,
                'color': color if color else 'N/A',
                'expectedDate': expected_delivery if expected_delivery else 'N/A',
                'accessories': accessories if accessories else '0'
            }

            # Generate PDF quotation
            pdf_path = generate_quotation_pdf(quotation_data)

            # Calculate quotation amount based on model
            model_data = {
                "Rizta S Mono (2.9 kWh)": [114841, 17000],
                "Rizta S Super Matte (2.9 kWh)": [116841, 18000],
                "Rizta Z Mono (2.9 kWh)": [129841, 20000],
                "Rizta Z Duo (2.9 kWh)": [130841, 17000],
                "Rizta Z Super Matte (2.9 kWh)": [131841, 18000],
                "Rizta Z Mono (3.7 kWh)": [149842, 20000],
                "Rizta Z Duo (3.7 kWh)": [150842, 17000],
                "Rizta Z Super Matte (3.7 kWh)": [151842, 18000],
                "450 X (2.9 kWh)": [149047, 20000],
                "450 X (3.7 kWh)": [159046, 17000],
                "450 X (2.9 kWh) Pro Pack": [166047, 18000],
                "450 X (3.7 kWh) Pro Pack": [179046, 20000],
                "450 Apex STD": [189841, 0]
            }

            model_price = model_data.get(model_interested, [0, 0])[0]
            pro_pack_price = model_data.get(model_interested, [0, 0])[1] if pro_pack == 'Yes' else 0
            accessories_cost = int(accessories) if accessories else 0

            # Calculate total (Ex-showroom + Pro Pack + Accessories + RTO + Insurance + EBW + AMC - Subsidy)
            total_amount = model_price + pro_pack_price + accessories_cost + 1000 + 5500 + 6000 + 2500 - 5000

            # Prepare walk-in data for database
            walkin_data = {
                'uid': uid,
                'ps_name': session.get('ps_name'),
                'ps_branch': session.get('branch'),
                'customer_name': customer_name,
                'customer_mobile_number': customer_mobile,
                'customer_email': customer_email if customer_email else None,
                'customer_address': customer_address if customer_address else None,
                'customer_age': int(customer_age) if customer_age else None,
                'occupation': occupation if occupation else None,
                'vehicle_usage': vehicle_usage if vehicle_usage else None,
                'daily_travel_distance': int(daily_travel) if daily_travel else None,
                'lead_source': lead_source,
                'lead_category': lead_category if lead_category else None,
                'purchase_type': purchase_type if purchase_type else None,
                'model_interested': model_interested,
                'color': color if color else None,
                'pro_pack': pro_pack if pro_pack else 'No',
                'expected_delivery_date': expected_delivery if expected_delivery else None,
                'accessories': accessories_cost,
                'quotation_amount': total_amount,
                'quotation_details': quotation_details if quotation_details else None,
                'remarks': remarks if remarks else None,
                'follow_up_date': follow_up_date if follow_up_date else None,
                'status': status,
                'pdf_path': pdf_path
            }

            # --- Walk-in Follow-up Assignment Logic ---
            cres = safe_get_data('cre_users')
            cre_names = [cre['name'] for cre in cres]
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            cre_followup_counts = {cre: 0 for cre in cre_names}
            existing_followups = safe_get_data('walkin_data', {'walkin_followup_date': tomorrow})
            for lead in existing_followups:
                cre = lead.get('walkin_cre_name')
                if cre in cre_followup_counts:
                    cre_followup_counts[cre] += 1
            assigned_cre = min(cre_followup_counts, key=cre_followup_counts.get) if cre_followup_counts else None
            walkin_data['walkin_cre_name'] = assigned_cre
            walkin_data['walkin_followup_date'] = tomorrow

            # Insert walk-in data into the database
            result = supabase.table('walkin_data').insert(walkin_data).execute()

            if result.data:
                # Log walk-in customer creation
                auth_manager.log_audit_event(
                    user_id=session.get('user_id'),
                    user_type=session.get('user_type'),
                    action='WALKIN_CUSTOMER_CREATED',
                    resource='walkin_data',
                    resource_id=uid,
                    details={
                        'customer_name': customer_name,
                        'model_interested': model_interested,
                        'quotation_amount': total_amount
                    }
                )
                # Send quotation email with PDF if email is provided
                if customer_email and pdf_path:
                    quotation_email_data = {
                        'uid': uid,
                        'model_interested': model_interested,
                        'quotation_amount': str(total_amount),
                        'quotation_details': quotation_details,
                        'ps_name': session.get('ps_name'),
                        'ps_branch': session.get('branch')
                    }

                    socketio.start_background_task(send_quotation_email, customer_email, customer_name, quotation_email_data, pdf_path)

                    if email_sent:
                        flash(f'Walk-in customer added successfully! Quotation PDF sent to {customer_email}', 'success')
                    else:
                        flash('Walk-in customer added successfully! (Email sending failed)', 'warning')
                else:
                    flash('Walk-in customer added successfully!', 'success')

                return redirect(url_for('ps_dashboard'))
            else:
                flash('Error saving walk-in customer data', 'error')

        except Exception as e:
            print(f"Error creating walk-in customer: {e}")
            flash(f'Error creating walk-in customer: {str(e)}', 'error')

    return render_template('walkin_customers.html', today=datetime.now().strftime('%Y-%m-%d'))


@app.route('/download_quotation_pdf/<uid>')
@require_ps
def download_quotation_pdf(uid):
    """Download PDF quotation for walk-in customer"""
    try:
        # Get walk-in customer data
        result = supabase.table('walkin_data').select('*').eq('uid', uid).execute()

        if not result.data:
            flash('Walk-in customer not found', 'error')
            return redirect(url_for('view_walkin_customers'))

        walkin_data = result.data[0]

        # Verify this walk-in customer belongs to the current PS
        if walkin_data.get('ps_name') != session.get('ps_name'):
            flash('Access denied - This quotation does not belong to you', 'error')
            return redirect(url_for('view_walkin_customers'))

        # Check if PDF already exists
        existing_pdf_path = walkin_data.get('pdf_path')
        if existing_pdf_path and os.path.exists(existing_pdf_path):
            pdf_path = existing_pdf_path
        else:
            # Generate new PDF
            quotation_data = {
                'uid': walkin_data['uid'],
                'psName': walkin_data['ps_name'],
                'executiveMobile': session.get('phone', 'N/A'),
                'date': walkin_data.get('created_at', datetime.now().strftime('%Y-%m-%d')),
                'branch': walkin_data['ps_branch'],
                'customerName': walkin_data['customer_name'],
                'customerMobile': walkin_data['customer_mobile_number'],
                'email': walkin_data.get('customer_email', 'N/A'),
                'address': walkin_data.get('customer_address', 'N/A'),
                'occupation': walkin_data.get('occupation', 'N/A'),
                'leadSource': walkin_data['lead_source'],
                'leadCategory': walkin_data.get('lead_category', 'N/A'),
                'purchaseType': walkin_data.get('purchase_type', 'N/A'),
                'model': walkin_data['model_interested'],
                'color': walkin_data.get('color', 'N/A'),
                'expectedDate': walkin_data.get('expected_delivery_date', 'N/A'),
                'accessories': str(walkin_data.get('accessories', 0))
            }

            pdf_path = generate_quotation_pdf(quotation_data)

            if not pdf_path:
                flash('Error generating PDF quotation', 'error')
                return redirect(url_for('view_walkin_customers'))

            # Update database with new PDF path
            supabase.table('walkin_data').update({'pdf_path': pdf_path}).eq('uid', uid).execute()

        # Log PDF download
        auth_manager.log_audit_event(
            user_id=session.get('user_id'),
            user_type=session.get('user_type'),
            action='QUOTATION_PDF_DOWNLOADED',
            resource='walkin_data',
            resource_id=uid,
            details={'customer_name': walkin_data['customer_name']}
        )

        # Send file
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"Ather_Quotation_{uid}.pdf",
            mimetype='application/pdf'
        )

    except Exception as e:
        print(f"Error downloading PDF: {e}")
        flash(f'Error downloading PDF: {str(e)}', 'error')
        return redirect(url_for('view_walkin_customers'))


@app.route('/view_walkin_customers')
@require_ps
def view_walkin_customers():
    """View walk-in customers for current PS"""
    try:
        ps_name = session.get('ps_name')
        walkin_customers = safe_get_data('walkin_data', {'ps_name': ps_name})

        # Log access
        auth_manager.log_audit_event(
            user_id=session.get('user_id'),
            user_type=session.get('user_type'),
            action='WALKIN_CUSTOMERS_VIEWED',
            resource='walkin_data',
            details={'ps_name': ps_name, 'count': len(walkin_customers)}
        )

        return render_template('view_walkin_customers.html', walkin_customers=walkin_customers)

    except Exception as e:
        flash(f'Error loading walk-in customers: {str(e)}', 'error')
        return redirect(url_for('ps_dashboard'))


@app.route('/analytics')
@require_admin
def analytics():
    try:
        # Get filter period or custom date range from query parameter
        period = request.args.get('period', '30')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        today = datetime.now().date()
        start_date = None
        end_date = None
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except Exception:
                start_date = None
                end_date = None
        elif period == 'all':
            start_date = None
        else:
            days = int(period) if period.isdigit() else 30
            start_date = today - timedelta(days=days)
            end_date = today

        # Get all data
        all_leads = safe_get_data('lead_master')
        all_cres = safe_get_data('cre_users')
        all_ps = safe_get_data('ps_users')
        ps_followups = safe_get_data('ps_followup_master')

        # Filter leads by date if needed
        filtered_leads = []
        for lead in all_leads:
            lead_date_str = lead.get('created_at') or lead.get('date')
            if lead_date_str:
                try:
                    if 'T' in lead_date_str:
                        lead_date = datetime.fromisoformat(lead_date_str.replace('Z', '+00:00')).date()
                    else:
                        lead_date = datetime.strptime(lead_date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    filtered_leads.append(lead)
                    continue
                if start_date and end_date:
                    if start_date <= lead_date <= end_date:
                        filtered_leads.append(lead)
                elif start_date:
                    if lead_date >= start_date:
                        filtered_leads.append(lead)
                else:
                    filtered_leads.append(lead)
            else:
                filtered_leads.append(lead)
        leads = filtered_leads

        # Calculate KPIs
        total_leads = len(leads)
        won_leads = len([l for l in leads if l.get('final_status') == 'Won'])
        conversion_rate = round((won_leads / total_leads * 100) if total_leads > 0 else 0, 1)

        # Calculate average response time (days to first call)
        response_times = []
        for lead in leads:
            if lead.get('first_call_date') and lead.get('date'):
                try:
                    lead_date = datetime.strptime(lead['date'], '%Y-%m-%d').date()
                    call_date = datetime.strptime(lead['first_call_date'], '%Y-%m-%d').date()
                    response_times.append((call_date - lead_date).days)
                except (ValueError, TypeError):
                    continue
        avg_response_time = f"{round(sum(response_times) / len(response_times), 1)} days" if response_times else "N/A"

        # Active CREs (CREs with leads assigned)
        active_cres = len(set([l.get('cre_name') for l in leads if l.get('cre_name')]))
        total_cres = len(all_cres)

        # Source distribution
        source_counts = Counter([l.get('source', 'Unknown') for l in leads])
        source_labels = list(source_counts.keys())
        source_data = list(source_counts.values())

        # Lead trends (last 30 days)
        trend_data = []
        trend_labels = []
        for i in range(29, -1, -1):
            date = today - timedelta(days=i)
            count = len([l for l in leads if l.get('date') == str(date)])
            trend_data.append(count)
            trend_labels.append(date.strftime('%m/%d'))

        # Top performing CREs with new parameters
        cre_performance = defaultdict(lambda: {'total': 0, 'hot': 0, 'warm': 0, 'cold': 0, 'won': 0, 'lost': 0, 'calls': []})
        for lead in leads:
            cre_name = lead.get('cre_name')
            if cre_name:
                cre_performance[cre_name]['total'] += 1
                # Hot/Warm/Cold by lead_category
                category = (lead.get('lead_category') or '').strip().lower()
                if category == 'hot':
                    cre_performance[cre_name]['hot'] += 1
                elif category == 'warm':
                    cre_performance[cre_name]['warm'] += 1
                elif category == 'cold':
                    cre_performance[cre_name]['cold'] += 1
                # Won/Lost by final_status
                if (lead.get('final_status') or '').strip().lower() == 'won':
                    cre_performance[cre_name]['won'] += 1
                elif (lead.get('final_status') or '').strip().lower() == 'lost':
                    cre_performance[cre_name]['lost'] += 1
                # Count calls made
                call_count = 0
                call_fields = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh']
                for call_field in call_fields:
                    if lead.get(f'{call_field}_call_date'):
                        call_count += 1
                cre_performance[cre_name]['calls'].append(call_count)

        # Calculate conversion rates and average calls for CREs
        top_cres = []
        for cre_name, data in cre_performance.items():
            total_calls = sum(data['calls'])
            avg_calls = round(total_calls / len(data['calls']), 1) if data['calls'] else 0
            conversion_rate_cre = round((data['won'] / data['total'] * 100) if data['total'] > 0 else 0, 1)
            top_cres.append({
                'name': cre_name,
                'total_leads': data['total'],
                'hot': data['hot'],
                'warm': data['warm'],
                'cold': data['cold'],
                'won_leads': data['won'],
                'lost_leads': data['lost'],
                'conversion_rate': conversion_rate_cre,
                'avg_calls': avg_calls
            })
        # Sort by won leads and take top 5
        top_cres = sorted(top_cres, key=lambda x: x['won_leads'], reverse=True)[:5]

        # Lead categories (add Won and Lost as categories)
        category_counts = Counter([l.get('lead_category', 'None') for l in leads])
        won_count = len([l for l in leads if (l.get('final_status') or '').strip().lower() == 'won'])
        lost_count = len([l for l in leads if (l.get('final_status') or '').strip().lower() == 'lost'])
        total_leads = len(leads)
        lead_categories = []
        # Add regular categories
        for category, count in category_counts.items():
            percentage = round((count / total_leads * 100) if total_leads > 0 else 0, 1)
            lead_categories.append({
                'name': category,
                'count': count,
                'percentage': percentage
            })
        # Add Won and Lost as categories
        if won_count > 0:
            lead_categories.append({
                'name': 'Won',
                'count': won_count,
                'percentage': round((won_count / total_leads * 100) if total_leads > 0 else 0, 1)
            })
        if lost_count > 0:
            lead_categories.append({
                'name': 'Lost',
                'count': lost_count,
                'percentage': round((lost_count / total_leads * 100) if total_leads > 0 else 0, 1)
            })

        # Model interest
        model_counts = Counter([l.get('model_interested', 'Not specified') for l in leads])
        model_interest = []
        for model, count in model_counts.items():
            percentage = round((count / total_leads * 100) if total_leads > 0 else 0, 1)
            model_interest.append({
                'name': model,
                'count': count,
                'percentage': percentage
            })

        # Branch performance
        branch_performance = []
        branches = set([ps.get('branch') for ps in all_ps if ps.get('branch')])
        for branch in branches:
            branch_ps = [ps for ps in all_ps if ps.get('branch') == branch]
            ps_names = [ps['name'] for ps in branch_ps]
            branch_leads = [l for l in leads if l.get('ps_name') in ps_names]
            branch_won = len([l for l in branch_leads if l.get('final_status') == 'Won'])
            success_rate = round((branch_won / len(branch_leads) * 100) if branch_leads else 0, 1)
            branch_performance.append({
                'name': branch,
                'ps_count': len(branch_ps),
                'assigned_leads': len(branch_leads),
                'won_leads': branch_won,
                'success_rate': success_rate
            })

        # Funnel data
        assigned_cre = len([l for l in leads if l.get('cre_name')])
        first_call = len([l for l in leads if l.get('first_call_date')])
        assigned_ps = len([l for l in leads if l.get('ps_name')])
        funnel = {
            'total': total_leads,
            'assigned_cre': assigned_cre,
            'assigned_cre_percent': round((assigned_cre / total_leads * 100) if total_leads > 0 else 0, 1),
            'first_call': first_call,
            'first_call_percent': round((first_call / total_leads * 100) if total_leads > 0 else 0, 1),
            'assigned_ps': assigned_ps,
            'assigned_ps_percent': round((assigned_ps / total_leads * 100) if total_leads > 0 else 0, 1),
            'won': won_leads,
            'won_percent': round((won_leads / total_leads * 100) if total_leads > 0 else 0, 1)
        }

        # Recent activities (mock data for now)
        recent_activities = [
            {
                'title': 'New Lead Assigned',
                'description': 'Lead assigned to CRE for follow-up',
                'time': '2 hours ago'
            },
            {
                'title': 'Lead Converted',
                'description': 'Customer purchased Rizta Z model',
                'time': '4 hours ago'
            },
            {
                'title': 'Follow-up Scheduled',
                'description': 'PS scheduled follow-up call',
                'time': '6 hours ago'
            }
        ]

        # Calculate leads growth (mock calculation)
        leads_growth = 15

        # Create analytics object that matches template expectations
        analytics = {
            'total_leads': total_leads,
            'leads_growth': leads_growth,
            'conversion_rate': conversion_rate,
            'avg_response_time': avg_response_time,
            'active_cres': active_cres,
            'total_cres': total_cres,
            'source_labels': source_labels,
            'source_data': source_data,
            'trend_labels': trend_labels,
            'trend_data': trend_data,
            'top_cres': top_cres,
            'lead_categories': lead_categories,
            'model_interest': model_interest,
            'branch_performance': branch_performance,
            'funnel': funnel,
            'recent_activities': recent_activities
        }

        # Log analytics access
        auth_manager.log_audit_event(
            user_id=session.get('user_id'),
            user_type=session.get('user_type'),
            action='ANALYTICS_ACCESS',
            resource='analytics',
            details={'period': period, 'start_date': start_date_str, 'end_date': end_date_str}
        )

        return render_template('analytics.html', analytics=analytics)

    except Exception as e:
        print(f"Error in analytics: {e}")
        flash(f'Error loading analytics: {str(e)}', 'error')
        # Return empty analytics object to prevent template errors
        empty_analytics = {
            'total_leads': 0,
            'leads_growth': 0,
            'conversion_rate': 0,
            'avg_response_time': "N/A",
            'active_cres': 0,
            'total_cres': 0,
            'source_labels': [],
            'source_data': [],
            'trend_labels': [],
            'trend_data': [],
            'top_cres': [],
            'lead_categories': [],
            'model_interest': [],
            'branch_performance': [],
            'funnel': {
                'total': 0,
                'assigned_cre': 0,
                'assigned_cre_percent': 0,
                'first_call': 0,
                'first_call_percent': 0,
                'assigned_ps': 0,
                'assigned_ps_percent': 0,
                'won': 0,
                'won_percent': 0
            },
            'recent_activities': []
        }
        return render_template('analytics.html', analytics=empty_analytics)


@app.route('/branch_performance/<branch_name>')
@require_admin
def branch_performance(branch_name):
    """Get detailed PS performance for a specific branch"""
    try:
        # Get all PS users in this branch
        branch_ps_users = safe_get_data('ps_users', {'branch': branch_name})

        if not branch_ps_users:
            return jsonify({
                'success': False,
                'message': f'No PS users found in {branch_name} branch'
            })

        # Get all leads and PS followups
        all_leads = safe_get_data('lead_master')
        all_ps_followups = safe_get_data('ps_followup_master')

        # Calculate performance for each PS in the branch
        ps_performance = []
        total_branch_leads = 0
        total_branch_won = 0

        for ps_user in branch_ps_users:
            ps_name = ps_user['name']

            # Get PS followup data for this PS
            ps_leads = [f for f in all_ps_followups if f.get('ps_name') == ps_name]

            # Calculate metrics
            total_leads = len(ps_leads)
            pending_leads = len([l for l in ps_leads if l.get('final_status') == 'Pending'])
            in_progress_leads = len([l for l in ps_leads if l.get('final_status') == 'In Progress'])
            won_leads = len([l for l in ps_leads if l.get('final_status') == 'Won'])
            lost_leads = len([l for l in ps_leads if l.get('final_status') == 'Lost'])

            # Calculate success rate
            success_rate = round((won_leads / total_leads * 100) if total_leads > 0 else 0, 1)

            # Calculate average calls
            total_calls = 0
            for lead in ps_leads:
                call_count = 0
                for call_num in ['first', 'second', 'third']:
                    if lead.get(f'{call_num}_call_date'):
                        call_count += 1
                total_calls += call_count

            avg_calls = round(total_calls / total_leads, 1) if total_leads > 0 else 0

            # Get last activity (most recent call date)
            last_activity = None
            for lead in ps_leads:
                for call_num in ['third', 'second', 'first']:  # Check in reverse order
                    call_date = lead.get(f'{call_num}_call_date')
                    if call_date:
                        try:
                            activity_date = datetime.strptime(call_date, '%Y-%m-%d').date()
                            if not last_activity or activity_date > last_activity:
                                last_activity = activity_date
                        except (ValueError, TypeError):
                            continue
                        break

            last_activity_str = last_activity.strftime('%Y-%m-%d') if last_activity else None

            ps_performance.append({
                'name': ps_user['name'],
                'username': ps_user['username'],
                'phone': ps_user.get('phone', 'N/A'),
                'email': ps_user.get('email', 'N/A'),
                'total_leads': total_leads,
                'pending_leads': pending_leads,
                'in_progress_leads': in_progress_leads,
                'won_leads': won_leads,
                'lost_leads': lost_leads,
                'success_rate': success_rate,
                'avg_calls': avg_calls,
                'last_activity': last_activity_str
            })

            total_branch_leads += total_leads
            total_branch_won += won_leads

        # Calculate branch summary
        branch_success_rate = round((total_branch_won / total_branch_leads * 100) if total_branch_leads > 0 else 0, 1)

        summary = {
            'total_ps': len(branch_ps_users),
            'total_leads': total_branch_leads,
            'won_leads': total_branch_won,
            'success_rate': branch_success_rate
        }

        # Log branch performance access
        auth_manager.log_audit_event(
            user_id=session.get('user_id'),
            user_type=session.get('user_type'),
            action='BRANCH_PERFORMANCE_ACCESS',
            resource='branch_performance',
            details={'branch': branch_name}
        )

        return jsonify({
            'success': True,
            'data': {
                'branch_name': branch_name,
                'summary': summary,
                'ps_performance': ps_performance
            }
        })

    except Exception as e:
        print(f"Error getting branch performance for {branch_name}: {e}")
        return jsonify({
            'success': False,
            'message': f'Error loading branch performance: {str(e)}'
        })


@app.route('/export_leads')
@require_admin
def export_leads():
    """Export leads dashboard"""
    try:
        # Get all leads for counting
        all_leads = safe_get_data('lead_master')

        # Count by final status
        won_count = len([l for l in all_leads if l.get('final_status') == 'Won'])
        lost_count = len([l for l in all_leads if l.get('final_status') == 'Lost'])
        pending_count = len([l for l in all_leads if l.get('final_status') == 'Pending'])
        in_progress_count = len([l for l in all_leads if l.get('final_status') == 'In Progress'])

        # Count by lead category
        hot_count = len([l for l in all_leads if l.get('lead_category') == 'Hot'])
        warm_count = len([l for l in all_leads if l.get('lead_category') == 'Warm'])
        cold_count = len([l for l in all_leads if l.get('lead_category') == 'Cold'])
        not_interested_count = len([l for l in all_leads if l.get('lead_category') == 'Not Interested'])

        # Log export dashboard access
        auth_manager.log_audit_event(
            user_id=session.get('user_id'),
            user_type=session.get('user_type'),
            action='EXPORT_DASHBOARD_ACCESS',
            resource='export_leads'
        )

        return render_template('export_leads.html',
                               won_count=won_count,
                               lost_count=lost_count,
                               pending_count=pending_count,
                               in_progress_count=in_progress_count,
                               hot_count=hot_count,
                               warm_count=warm_count,
                               cold_count=cold_count,
                               not_interested_count=not_interested_count)

    except Exception as e:
        flash(f'Error loading export dashboard: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))


@app.route('/get_filtered_leads')
@require_admin
def get_filtered_leads():
    """Get filtered leads based on filter type and value"""
    try:
        filter_type = request.args.get('filter_type')
        filter_value = request.args.get('filter_value')

        if not filter_type or not filter_value:
            return jsonify({'success': False, 'message': 'Filter type and value are required'})

        # Get all leads
        all_leads = safe_get_data('lead_master')

        # Filter based on type
        if filter_type == 'final_status':
            filtered_leads = [l for l in all_leads if l.get('final_status') == filter_value]
        elif filter_type == 'lead_category':
            filtered_leads = [l for l in all_leads if l.get('lead_category') == filter_value]
        else:
            return jsonify({'success': False, 'message': 'Invalid filter type'})

        # Log filtered leads access
        auth_manager.log_audit_event(
            user_id=session.get('user_id'),
            user_type=session.get('user_type'),
            action='FILTERED_LEADS_ACCESS',
            resource='lead_master',
            details={'filter_type': filter_type, 'filter_value': filter_value, 'result_count': len(filtered_leads)}
        )

        return jsonify({
            'success': True,
            'leads': filtered_leads,
            'count': len(filtered_leads)
        })

    except Exception as e:
        print(f"Error getting filtered leads: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/export_leads_csv')
@require_admin
def export_leads_csv():
    """Export filtered leads to CSV"""
    try:
        filter_type = request.args.get('filter_type')
        filter_value = request.args.get('filter_value')

        if not filter_type or not filter_value:
            return jsonify({'success': False, 'message': 'Filter type and value are required'})

        # Get all leads
        all_leads = safe_get_data('lead_master')

        # Filter based on type
        if filter_type == 'final_status':
            filtered_leads = [l for l in all_leads if l.get('final_status') == filter_value]
        elif filter_type == 'lead_category':
            filtered_leads = [l for l in all_leads if l.get('lead_category') == filter_value]
        else:
            return jsonify({'success': False, 'message': 'Invalid filter type'})

        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        headers = [
            'UID', 'Date', 'Customer Name', 'Mobile Number', 'Source', 'CRE Name', 'PS Name',
            'Lead Category', 'Model Interested', 'Branch', 'Lead Status', 'Final Status',
            'Follow Up Date', 'First Call Date', 'First Remark', 'Second Call Date', 'Second Remark',
            'Third Call Date', 'Third Remark', 'Fourth Call Date', 'Fourth Remark',
            'Fifth Call Date', 'Fifth Remark', 'Sixth Call Date', 'Sixth Remark',
            'Seventh Call Date', 'Seventh Remark', 'Assigned'
        ]
        writer.writerow(headers)

        # Write data rows
        for lead in filtered_leads:
            row = [
                lead.get('uid', ''),
                lead.get('date', ''),
                lead.get('customer_name', ''),
                lead.get('customer_mobile_number', ''),
                lead.get('source', ''),
                lead.get('cre_name', ''),
                lead.get('ps_name', ''),
                lead.get('lead_category', ''),
                lead.get('model_interested', ''),
                lead.get('branch', ''),
                lead.get('lead_status', ''),
                lead.get('final_status', ''),
                lead.get('follow_up_date', ''),
                lead.get('first_call_date', ''),
                lead.get('first_remark', ''),
                lead.get('second_call_date', ''),
                lead.get('second_remark', ''),
                lead.get('third_call_date', ''),
                lead.get('third_remark', ''),
                lead.get('fourth_call_date', ''),
                lead.get('fourth_remark', ''),
                lead.get('fifth_call_date', ''),
                lead.get('fifth_remark', ''),
                lead.get('sixth_call_date', ''),
                lead.get('sixth_remark', ''),
                lead.get('seventh_call_date', ''),
                lead.get('seventh_remark', ''),
                lead.get('assigned', '')
            ]
            writer.writerow(row)

        # Log CSV export
        auth_manager.log_audit_event(
            user_id=session.get('user_id'),
            user_type=session.get('user_type'),
            action='CSV_EXPORT',
            resource='lead_master',
            details={'filter_type': filter_type, 'filter_value': filter_value, 'exported_count': len(filtered_leads)}
        )

        # Create response
        output.seek(0)
        response = app.response_class(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=leads_{filter_type}_{filter_value}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            }
        )

        return response

    except Exception as e:
        print(f"Error exporting CSV: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/get_leads_by_date_range')
@require_admin
def get_leads_by_date_range():
    """Get leads filtered by date range"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        date_field = request.args.get('date_field', 'date')

        if not start_date or not end_date:
            return jsonify({'success': False, 'message': 'Start date and end date are required'})

        # Validate date format
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD'})

        # Validate date field
        valid_date_fields = ['date', 'first_call_date', 'follow_up_date', 'created_at']
        if date_field not in valid_date_fields:
            return jsonify({'success': False, 'message': 'Invalid date field'})

        # Get all leads
        all_leads = safe_get_data('lead_master')

        # Filter by date range
        filtered_leads = []
        for lead in all_leads:
            lead_date_str = lead.get(date_field)
            if lead_date_str:
                try:
                    # Handle different date formats
                    if 'T' in lead_date_str:  # ISO format with time
                        lead_date = datetime.fromisoformat(lead_date_str.replace('Z', '+00:00')).date()
                    else:  # Date only format
                        lead_date = datetime.strptime(lead_date_str, '%Y-%m-%d').date()

                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()

                    if start_date_obj <= lead_date <= end_date_obj:
                        filtered_leads.append(lead)
                except (ValueError, TypeError):
                    # Skip leads with invalid dates
                    continue

        # Log date range filter access
        auth_manager.log_audit_event(
            user_id=session.get('user_id'),
            user_type=session.get('user_type'),
            action='DATE_RANGE_FILTER_ACCESS',
            resource='lead_master',
            details={
                'start_date': start_date,
                'end_date': end_date,
                'date_field': date_field,
                'result_count': len(filtered_leads)
            }
        )

        return jsonify({
            'success': True,
            'leads': filtered_leads,
            'count': len(filtered_leads)
        })

    except Exception as e:
        print(f"Error getting leads by date range: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/export_leads_by_date_csv')
@require_admin
def export_leads_by_date_csv():
    """Export leads filtered by date range to CSV"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        date_field = request.args.get('date_field', 'date')

        if not start_date or not end_date:
            return jsonify({'success': False, 'message': 'Start date and end date are required'})

        # Validate date format
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD'})

        # Validate date field
        valid_date_fields = ['date', 'first_call_date', 'follow_up_date', 'created_at']
        if date_field not in valid_date_fields:
            return jsonify({'success': False, 'message': 'Invalid date field'})

        # Get all leads
        all_leads = safe_get_data('lead_master')

        # Filter by date range
        filtered_leads = []
        for lead in all_leads:
            lead_date_str = lead.get(date_field)
            if lead_date_str:
                try:
                    # Handle different date formats
                    if 'T' in lead_date_str:  # ISO format with time
                        lead_date = datetime.fromisoformat(lead_date_str.replace('Z', '+00:00')).date()
                    else:  # Date only format
                        lead_date = datetime.strptime(lead_date_str, '%Y-%m-%d').date()

                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()

                    if start_date_obj <= lead_date <= end_date_obj:
                        filtered_leads.append(lead)
                except (ValueError, TypeError):
                    # Skip leads with invalid dates
                    continue

        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        headers = [
            'UID', 'Date', 'Customer Name', 'Mobile Number', 'Source', 'CRE Name', 'PS Name',
            'Lead Category', 'Model Interested', 'Branch', 'Lead Status', 'Final Status',
            'Follow Up Date', 'First Call Date', 'First Remark', 'Second Call Date', 'Second Remark',
            'Third Call Date', 'Third Remark', 'Fourth Call Date', 'Fourth Remark',
            'Fifth Call Date', 'Fifth Remark', 'Sixth Call Date', 'Sixth Remark',
            'Seventh Call Date', 'Seventh Remark', 'Assigned', 'Created At'
        ]
        writer.writerow(headers)

        # Write data rows
        for lead in filtered_leads:
            row = [
                lead.get('uid', ''),
                lead.get('date', ''),
                lead.get('customer_name', ''),
                lead.get('customer_mobile_number', ''),
                lead.get('source', ''),
                lead.get('cre_name', ''),
                lead.get('ps_name', ''),
                lead.get('lead_category', ''),
                lead.get('model_interested', ''),
                lead.get('branch', ''),
                lead.get('lead_status', ''),
                lead.get('final_status', ''),
                lead.get('follow_up_date', ''),
                lead.get('first_call_date', ''),
                lead.get('first_remark', ''),
                lead.get('second_call_date', ''),
                lead.get('second_remark', ''),
                lead.get('third_call_date', ''),
                lead.get('third_remark', ''),
                lead.get('fourth_call_date', ''),
                lead.get('fourth_remark', ''),
                lead.get('fifth_call_date', ''),
                lead.get('fifth_remark', ''),
                lead.get('sixth_call_date', ''),
                lead.get('sixth_remark', ''),
                lead.get('seventh_call_date', ''),
                lead.get('seventh_remark', ''),
                lead.get('assigned', ''),
                lead.get('created_at', '')
            ]
            writer.writerow(row)

        # Log CSV export
        auth_manager.log_audit_event(
            user_id=session.get('user_id'),
            user_type=session.get('user_type'),
            action='DATE_RANGE_CSV_EXPORT',
            resource='lead_master',
            details={
                'start_date': start_date,
                'end_date': end_date,
                'date_field': date_field,
                'exported_count': len(filtered_leads)
            }
        )

        # Create response
        output.seek(0)
        response = app.response_class(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=leads_date_range_{start_date}_to_{end_date}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            }
        )

        return response

    except Exception as e:
        print(f"Error exporting date range CSV: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/activity_event', methods=['GET', 'POST'])
@require_ps
def activity_event():
    """Add event/activity leads for PS"""
    if request.method == 'POST':
        # Get form data for multiple customers
        customer_names = request.form.getlist('customer_name[]')
        customer_phones = request.form.getlist('customer_phone_number[]')
        customer_locations = request.form.getlist('customer_location[]')
        customer_professions = request.form.getlist('customer_profession[]')
        genders = request.form.getlist('gender[]')
        interested_models = request.form.getlist('interested_model[]')
        remarks_list = request.form.getlist('remarks[]')
        lead_statuses = request.form.getlist('lead_status[]')
        months = request.form.getlist('month[]')
        dates = request.form.getlist('date[]')
        
        # Get activity details
        activity_name = request.form.get('activity_name', '').strip()
        activity_location = request.form.get('activity_location', '').strip()
        
        # Validation
        if not activity_name or not activity_location:
            flash('Please fill activity details', 'error')
            return render_template('activity_event.html', now=datetime.now())
        
        if not customer_names or not customer_phones:
            flash('Please add at least one customer lead', 'error')
            return render_template('activity_event.html', now=datetime.now())
        
        try:
            leads_added = 0
            
            for i in range(len(customer_names)):
                if customer_names[i] and customer_phones[i]:  # Only process if name and phone are provided
                    # Generate UID for event lead
                    uid = f"E-{activity_name[:3].upper()}-{customer_phones[i][-4:]}"
                    
                    # Create event lead data strictly matching activity_leads schema
                    event_lead_data = {
                        'activity_uid': uid,
                        'activity_name': activity_name,
                        'activity_location': activity_location,
                        'ps_name': session.get('ps_name'),
                        'location': session.get('branch'),
                        'customer_name': customer_names[i].strip(),
                        'customer_location': customer_locations[i].strip() if i < len(customer_locations) else '',
                        'customer_profession': customer_professions[i].strip() if i < len(customer_professions) else '',
                        'gender': genders[i] if i < len(genders) else 'MALE',
                        'interested_model': interested_models[i].strip() if i < len(interested_models) else '',
                        'remarks': remarks_list[i].strip() if i < len(remarks_list) else '',
                        'lead_status': lead_statuses[i] if i < len(lead_statuses) else 'WARM',
                        'month': months[i] if i < len(months) else datetime.now().strftime('%b'),
                        'date': dates[i] if i < len(dates) else datetime.now().strftime('%Y-%m-%d'),
                        'customer_phone_number': customer_phones[i].strip(),
                        'created_at': datetime.now().isoformat(),
                        'lead_category': lead_statuses[i] if i < len(lead_statuses) else 'WARM'
                    }
                    # Insert into activity_leads
                    result = supabase.table('activity_leads').insert(event_lead_data).execute()
                    if result.data:
                        leads_added += 1
            
            if leads_added > 0:
                flash(f'{leads_added} event lead(s) added successfully!', 'success')
                return redirect(url_for('ps_dashboard'))
            else:
                flash('Error adding event leads', 'error')
                
        except Exception as e:
            flash(f'Error adding event leads: {str(e)}', 'error')
    
    return render_template('activity_event.html', now=datetime.now())


@app.route('/view_event_leads')
@require_ps
def view_event_leads():
    """View all event/activity leads for current PS"""
    try:
        ps_name = session.get('ps_name')
        # Get event leads for this PS from activity_leads table
        event_leads = safe_get_data('activity_leads', {'ps_name': ps_name})
        
        # Transform data to match template expectations
        transformed_leads = []
        for lead in event_leads:
            transformed_lead = {
                'activity_name': lead.get('activity_name', ''),
                'activity_location': lead.get('activity_location', ''),
                'ps_name': lead.get('ps_name', ''),
                'location': lead.get('location', ''),
                'customer_name': lead.get('customer_name', ''),
                'customer_phone_number': lead.get('customer_phone_number', ''),
                'customer_location': lead.get('customer_location', ''),
                'customer_profession': lead.get('customer_profession', ''),
                'gender': lead.get('gender', ''),
                'interested_model': lead.get('interested_model', ''),
                'remarks': lead.get('remarks', ''),
                'lead_status': lead.get('lead_status', ''),
                'month': lead.get('month', ''),
                'date': lead.get('date', '')
            }
            transformed_leads.append(transformed_lead)
        
        return render_template('view_event_leads.html', event_leads=transformed_leads)
        
    except Exception as e:
        flash(f'Error loading event leads: {str(e)}', 'error')
        return redirect(url_for('ps_dashboard'))


@app.route('/resend_quotation_email/<uid>', methods=['POST'])
@require_ps
def resend_quotation_email(uid):
    """Resend quotation email to walk-in customer"""
    try:
        # Get walk-in customer data
        result = supabase.table('walkin_data').select('*').eq('uid', uid).execute()

        if not result.data:
            return jsonify({'success': False, 'message': 'Walk-in customer not found'})

        walkin_data = result.data[0]

        # Verify this walk-in customer belongs to the current PS
        if walkin_data.get('ps_name') != session.get('ps_name'):
            return jsonify({'success': False, 'message': 'Access denied - This customer does not belong to you'})

        # Check if customer has email
        if not walkin_data.get('customer_email'):
            return jsonify({'success': False, 'message': 'Customer email not available'})

        # Check if PDF exists, generate if not
        existing_pdf_path = walkin_data.get('pdf_path')
        if not existing_pdf_path or not os.path.exists(existing_pdf_path):
            # Generate new PDF
            quotation_data = {
                'uid': walkin_data['uid'],
                'psName': walkin_data['ps_name'],
                'executiveMobile': session.get('phone', 'N/A'),
                'date': walkin_data.get('created_at', datetime.now().strftime('%Y-%m-%d')),
                'branch': walkin_data['ps_branch'],
                'customerName': walkin_data['customer_name'],
                'customerMobile': walkin_data['customer_mobile_number'],
                'email': walkin_data.get('customer_email', 'N/A'),
                'address': walkin_data.get('customer_address', 'N/A'),
                'occupation': walkin_data.get('occupation', 'N/A'),
                'leadSource': walkin_data['lead_source'],
                'leadCategory': walkin_data.get('lead_category', 'N/A'),
                'purchaseType': walkin_data.get('purchase_type', 'N/A'),
                'model': walkin_data['model_interested'],
                'color': walkin_data.get('color', 'N/A'),
                'expectedDate': walkin_data.get('expected_delivery_date', 'N/A'),
                'accessories': str(walkin_data.get('accessories', 0))
            }

            pdf_path = generate_quotation_pdf(quotation_data)

            if not pdf_path:
                return jsonify({'success': False, 'message': 'Error generating PDF quotation'})

            # Update database with new PDF path
            supabase.table('walkin_data').update({'pdf_path': pdf_path}).eq('uid', uid).execute()
        else:
            pdf_path = existing_pdf_path

        # Prepare quotation email data
        quotation_email_data = {
            'uid': walkin_data['uid'],
            'model_interested': walkin_data['model_interested'],
            'quotation_amount': str(walkin_data.get('quotation_amount', 0)),
            'quotation_details': walkin_data.get('quotation_details', ''),
            'ps_name': walkin_data['ps_name'],
            'ps_branch': walkin_data['ps_branch']
        }

        # Send email
        email_sent = send_quotation_email(
            walkin_data['customer_email'],
            walkin_data['customer_name'],
            quotation_email_data,
            pdf_path
        )

        if email_sent:
            # Log email resend
            auth_manager.log_audit_event(
                user_id=session.get('user_id'),
                user_type=session.get('user_type'),
                action='QUOTATION_EMAIL_RESENT',
                resource='walkin_data',
                resource_id=uid,
                details={
                    'customer_name': walkin_data['customer_name'],
                    'customer_email': walkin_data['customer_email']
                }
            )

            return jsonify({
                'success': True,
                'message': f'Quotation email sent successfully to {walkin_data["customer_email"]}'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to send email. Please check email configuration.'
            })

    except Exception as e:
        print(f"Error resending quotation email: {e}")
        return jsonify({
            'success': False,
            'message': f'Error resending email: {str(e)}'
        })

@app.route('/source_analysis_data')
@require_admin
def source_analysis_data():
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        today = datetime.now().date()
        start_date = None
        end_date = None
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except Exception:
                start_date = None
                end_date = None
        sources = [
            'Google (KNOW)', 'Google', 'Meta(KNOW)', 'Know', 'OEM Web', 'OEM Tele',
            'Affiliate Bikewale', 'Affiliate 91wheels', 'Affiliate Bikedekho',
            'BTL (KNOW)', 'Meta'
        ]
        all_leads = safe_get_data('lead_master')
        all_followups = safe_get_data('ps_followup_master')
        def in_date_range(lead):
            lead_date_str = lead.get('created_at') or lead.get('date')
            if not lead_date_str:
                return True
            try:
                if 'T' in lead_date_str:
                    lead_date = datetime.fromisoformat(lead_date_str.replace('Z', '+00:00')).date()
                else:
                    lead_date = datetime.strptime(lead_date_str, '%Y-%m-%d').date()
            except Exception:
                return True
            if start_date and end_date:
                return start_date <= lead_date <= end_date
            elif start_date:
                return lead_date >= start_date
            else:
                return True
        leads = [l for l in all_leads if in_date_range(l)]
        data = {}
        for source in sources:
            data[source] = {
                'calls_allocated': 0,
                'calls_attempted': 0,
                'calls_connected': 0,
                'pending_total': 0,
                'pending_interested': 0,
                'pending_hot': 0,
                'pending_warm': 0,
                'pending_cold': 0,
                'pending_callback': 0,
                'pending_rnr': 0,
                'pending_disconnected': 0,
                'closed_lost_total': 0,
                'closed_lost_competition': 0,
                'closed_lost_not_interested': 0,
                'closed_lost_did_not_enquire': 0,
                'closed_lost_wrong_lead': 0,
                'closed_lost_rnr_lost': 0,
                'closed_lost_finance_reject': 0,
                'closed_lost_co_dealer': 0,
                'sales_pipeline_total': 0,
                'call_progress': {},
                'latest_remark': '',
            }
        def get_source(lead):
            s = lead.get('source', '').strip()
            for src in sources:
                if s.lower() == src.lower():
                    return src
            for src in sources:
                if src.lower() in s.lower():
                    return src
            return None
        for lead in leads:
            src = get_source(lead)
            if not src:
                continue
            data[src]['calls_allocated'] += 1
            attempted = any(lead.get(f'{c}_call_date') for c in ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh'])
            if attempted:
                data[src]['calls_attempted'] += 1
            call_statuses = [lead.get(f'{c}_call_status', '').lower() for c in ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh']]
            connected = any(s and s not in ['rnr', 'busy', 'busy on another call'] for s in call_statuses)
            if connected:
                data[src]['calls_connected'] += 1
            status = (lead.get('lead_status') or '').strip().lower()
            if status in ['interested', 'call back', 'rnr', 'call disconnected']:
                data[src]['pending_total'] += 1
                if status == 'interested':
                    data[src]['pending_interested'] += 1
                    cat = (lead.get('lead_category') or '').strip().lower()
                    if cat == 'hot':
                        data[src]['pending_hot'] += 1
                    elif cat == 'warm':
                        data[src]['pending_warm'] += 1
                    elif cat == 'cold':
                        data[src]['pending_cold'] += 1
                elif status == 'call back':
                    data[src]['pending_callback'] += 1
                elif status == 'rnr':
                    data[src]['pending_rnr'] += 1
                elif status == 'call disconnected':
                    data[src]['pending_disconnected'] += 1
            # --- NEW LOGIC: Use latest follow-up for final_status and lead_status for lost reasons ---
            uid = lead.get('uid')
            latest_final_status = (lead.get('final_status') or '').strip().lower()
            latest_lost_reason = (lead.get('lost_reason') or '').strip().lower()
            latest_lead_status = (lead.get('lead_status') or '').strip().lower()
            if uid:
                followups = [f for f in all_followups if f.get('lead_uid') == uid]
                if followups:
                    latest_fu = max(followups, key=lambda f: f.get('created_at', ''))
                    if latest_fu.get('final_status'):
                        latest_final_status = latest_fu.get('final_status').strip().lower()
                    if latest_fu.get('lost_reason'):
                        latest_lost_reason = latest_fu.get('lost_reason').strip().lower()
                    if latest_fu.get('lead_status'):
                        latest_lead_status = latest_fu.get('lead_status').strip().lower()
            # --- END NEW LOGIC ---
            if latest_final_status == 'lost':
                data[src]['closed_lost_total'] += 1
                # Use lead_status for lost reason
                if latest_lead_status == 'rnr-lost':
                    data[src]['closed_lost_rnr_lost'] += 1
                elif latest_lead_status == 'did not enquire':
                    data[src]['closed_lost_did_not_enquire'] += 1
                elif latest_lead_status == 'not interested':
                    data[src]['closed_lost_not_interested'] += 1
                elif latest_lead_status == 'lost to competition':
                    data[src]['closed_lost_competition'] += 1
                elif latest_lead_status == 'lost to co-dealer':
                    data[src]['closed_lost_co_dealer'] += 1
                elif latest_lead_status == 'finance rejected':
                    data[src]['closed_lost_finance_reject'] += 1
                elif latest_lead_status == 'wrong lead':
                    data[src]['closed_lost_wrong_lead'] += 1
            if latest_final_status == 'won':
                data[src]['sales_pipeline_total'] += 1
            call_progress = None
            for idx, c in enumerate(['seventh', 'sixth', 'fifth', 'fourth', 'third', 'second', 'first']):
                if lead.get(f'{c}_call_date'):
                    call_progress = c.capitalize()
                    break
            if call_progress:
                data[src]['call_progress'][lead.get('uid')] = call_progress
            if uid:
                followups = [f for f in all_followups if f.get('lead_uid') == uid]
                if followups:
                    latest = max(followups, key=lambda f: f.get('created_at', ''))
                    data[src]['latest_remark'] = latest.get('remark', '')
        total_row = {k: sum(data[src][k] for src in sources) if isinstance(data[sources[0]][k], int) else {} for k in data[sources[0]].keys()}
        data['Total'] = total_row
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    socketio.run(app, debug=True)
