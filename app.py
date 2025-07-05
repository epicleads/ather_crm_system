from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from gevent import monkey
monkey.patch_all()
import json
import os
import time
from datetime import datetime, timedelta
from functools import wraps
import gc
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from supabase.client import create_client

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Create cache directory if it doesn't exist
cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flask_cache')
os.makedirs(cache_dir, exist_ok=True)

# Initialize cache with filesystem backend
cache = Cache(app, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': cache_dir,
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_THRESHOLD': 1000
})

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Authentication decorators
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Please log in first.')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def require_cre(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'cre_logged_in' not in session:
            flash('Please log in first.')
            return redirect(url_for('cre_login'))
        return f(*args, **kwargs)
    return decorated_function

def require_ps(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'ps_logged_in' not in session:
            flash('Please log in first.')
            return redirect(url_for('ps_login'))
        return f(*args, **kwargs)
    return decorated_function

# Main route
@app.route('/')
def index():
    if 'admin_logged_in' in session:
        return redirect(url_for('admin_dashboard'))
    elif 'cre_logged_in' in session:
        return redirect(url_for('cre_dashboard'))
    elif 'ps_logged_in' in session:
        return redirect(url_for('ps_dashboard'))
    return render_template('index.html')

@app.route('/unified_login', methods=['GET', 'POST'])
def unified_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # For testing purposes, use simple admin login
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            session['username'] = username
            return redirect(url_for('admin_dashboard'))
        
        flash('Invalid username or password')
        return redirect(url_for('index'))
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('index'))

# Password Reset Routes
@app.route('/password_reset_request', methods=['GET', 'POST'])
def password_reset_request():
    if request.method == 'POST':
        email = request.form.get('email')
        # Here you would normally send a password reset email
        flash('If an account exists with that email, you will receive password reset instructions.')
        return redirect(url_for('index'))
    return render_template('password_reset_request.html')

@app.route('/password_reset/<token>', methods=['GET', 'POST'])
def password_reset(token):
    if request.method == 'POST':
        new_password = request.form.get('password')
        # Here you would normally verify the token and update the password
        flash('Your password has been updated.')
        return redirect(url_for('index'))
    return render_template('password_reset.html')

# Admin routes
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            session['username'] = username
            return redirect(url_for('admin_dashboard'))
        flash('Invalid username or password')
        return redirect(url_for('admin_login'))
    return render_template('admin_login.html')

@app.route('/admin_dashboard')
@require_admin
@cache.cached(timeout=60)
def admin_dashboard():
    return render_template('admin_dashboard.html')

# CRE routes
@app.route('/cre_login', methods=['GET', 'POST'])
def cre_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Add your CRE authentication logic here
        session['cre_logged_in'] = True
        return redirect(url_for('cre_dashboard'))
    return render_template('cre_login.html')

@app.route('/cre_dashboard')
@require_cre
@cache.cached(timeout=60, query_string=True)
def cre_dashboard():
    # Add your CRE dashboard logic here
    return render_template('cre_dashboard.html')

# PS routes
@app.route('/ps_login', methods=['GET', 'POST'])
def ps_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Add your PS authentication logic here
        session['ps_logged_in'] = True
        return redirect(url_for('ps_dashboard'))
    return render_template('ps_login.html')

@app.route('/ps_dashboard')
@require_ps
@cache.cached(timeout=60, query_string=True)
def ps_dashboard():
    # Add your PS dashboard logic here
    return render_template('ps_dashboard.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
