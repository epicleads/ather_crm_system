"""
Flask Integration for Instant Lead Updates
Drop-in replacement for existing Flask routes with sub-1-second performance
"""

import time
import json
from datetime import datetime
from flask import request, jsonify, session, flash, redirect, url_for
from functools import wraps
import logging

# Import instant update system
from instant_update_client import (
    create_instant_update_client,
    InstantUpdateConfig,
    monitor_update_performance
)

logger = logging.getLogger(__name__)

class FlaskInstantUpdates:
    """Flask integration for instant lead updates"""

    def __init__(self, app, supabase_factory, redis_client=None):
        self.app = app
        self.supabase_factory = supabase_factory
        self.redis_client = redis_client

        # Create instant update client
        config = InstantUpdateConfig(
            target_time_ms=500,
            timeout_ms=800,
            use_rpc=True,
            enable_caching=True
        )

        self.update_client = create_instant_update_client(
            supabase_factory,
            redis_client,
            target_time_ms=500
        )

        # Warm up system on startup
        self._warm_up_system()

    def _warm_up_system(self):
        """Warm up the update system"""
        try:
            # Get sample leads for warmup
            with self.update_client.updater.connection_pool.get_connection() as conn:
                sample_leads = conn.table('lead_master').select('uid').limit(5).execute()
                lead_uids = [lead['uid'] for lead in (sample_leads.data or [])]

            self.update_client.warm_up_system(lead_uids)
            logger.info("Flask instant update system warmed up successfully")

        except Exception as e:
            logger.warning(f"System warmup failed: {e}")

    def require_instant_auth(self, user_types=None):
        """Authentication decorator with performance optimization"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if 'username' not in session:
                    return jsonify({'success': False, 'error': 'Authentication required'}), 401

                user_type = session.get('user_type')
                if user_types and user_type not in user_types:
                    return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403

                # Optimize system for this user
                username = session['username']
                self._optimize_for_user(user_type, username)

                return func(*args, **kwargs)
            return wrapper
        return decorator

    def _optimize_for_user(self, user_type: str, username: str):
        """Optimize system for specific user"""
        # This could preload frequently accessed leads for the user
        # Implementation depends on your user patterns
        pass

    @monitor_update_performance(target_ms=500)
    def update_lead_endpoint(self):
        """Ultra-fast lead update endpoint"""
        start_time = time.time()

        try:
            # Get request data
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No data provided',
                    'execution_time': time.time() - start_time
                }), 400

            lead_uid = data.get('lead_uid')
            update_data = data.get('update_data', {})

            if not lead_uid:
                return jsonify({
                    'success': False,
                    'error': 'Lead UID required',
                    'execution_time': time.time() - start_time
                }), 400

            # Get user info from session
            user_type = session.get('user_type')
            user_name = session.get('username')

            if not user_type or not user_name:
                return jsonify({
                    'success': False,
                    'error': 'User authentication required',
                    'execution_time': time.time() - start_time
                }), 401

            # Perform instant update
            result = self.update_client.update_lead_instantly(
                lead_uid=lead_uid,
                update_data=update_data,
                user_type=user_type,
                user_name=user_name
            )

            # Return result
            response_data = {
                'success': result.success,
                'execution_time': result.execution_time,
                'operations_completed': result.operations_completed,
                'cache_updated': result.cache_updated,
                'lead_uid': result.lead_uid,
                'method': 'INSTANT_UPDATE'
            }

            if not result.success:
                response_data['error'] = result.error

            # Log performance achievement
            if result.execution_time < 0.5:
                logger.info(f"🚀 ULTRA-FAST UPDATE: {result.execution_time:.3f}s for {lead_uid}")
            elif result.execution_time < 1.0:
                logger.info(f"⚡ FAST UPDATE: {result.execution_time:.3f}s for {lead_uid}")

            return jsonify(response_data), 200 if result.success else 500

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Update endpoint error: {e}")

            return jsonify({
                'success': False,
                'error': str(e),
                'execution_time': execution_time,
                'method': 'INSTANT_UPDATE'
            }), 500

    @monitor_update_performance(target_ms=1000)
    def batch_update_endpoint(self):
        """Ultra-fast batch update endpoint"""
        start_time = time.time()

        try:
            data = request.get_json()
            if not data or 'updates' not in data:
                return jsonify({
                    'success': False,
                    'error': 'Updates array required',
                    'execution_time': time.time() - start_time
                }), 400

            updates = data['updates']
            if not isinstance(updates, list):
                return jsonify({
                    'success': False,
                    'error': 'Updates must be an array',
                    'execution_time': time.time() - start_time
                }), 400

            # Add user info to each update
            user_type = session.get('user_type')
            user_name = session.get('username')

            for update in updates:
                update['user_type'] = user_type
                update['user_name'] = user_name

            # Perform batch update
            results = self.update_client.batch_update_leads_instantly(updates)

            # Summarize results
            successful = len([r for r in results if r.success])
            failed = len([r for r in results if not r.success])
            avg_time = sum(r.execution_time for r in results) / len(results)

            response_data = {
                'success': failed == 0,
                'total_updates': len(updates),
                'successful_updates': successful,
                'failed_updates': failed,
                'average_execution_time': avg_time,
                'total_execution_time': time.time() - start_time,
                'method': 'INSTANT_BATCH_UPDATE'
            }

            logger.info(f"Batch update: {successful}/{len(updates)} successful in {avg_time:.3f}s avg")

            return jsonify(response_data), 200

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Batch update error: {e}")

            return jsonify({
                'success': False,
                'error': str(e),
                'execution_time': execution_time,
                'method': 'INSTANT_BATCH_UPDATE'
            }), 500

    def update_with_conflict_resolution_endpoint(self):
        """Update with optimistic locking"""
        start_time = time.time()

        try:
            data = request.get_json()
            lead_uid = data.get('lead_uid')
            update_data = data.get('update_data', {})
            expected_version = data.get('expected_version')

            user_type = session.get('user_type')
            user_name = session.get('username')

            # Perform update with conflict resolution
            result = self.update_client.update_with_optimistic_locking(
                lead_uid=lead_uid,
                update_data=update_data,
                user_type=user_type,
                user_name=user_name,
                expected_version=expected_version
            )

            response_data = {
                'success': result.success,
                'execution_time': result.execution_time,
                'lead_uid': result.lead_uid,
                'method': 'CONFLICT_RESOLUTION_UPDATE'
            }

            if not result.success:
                response_data['error'] = result.error

            return jsonify(response_data), 200 if result.success else 409

        except Exception as e:
            execution_time = time.time() - start_time
            return jsonify({
                'success': False,
                'error': str(e),
                'execution_time': execution_time
            }), 500

    def get_performance_stats_endpoint(self):
        """Get real-time performance statistics"""
        try:
            stats = self.update_client.get_performance_stats()
            return jsonify(stats), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

# Drop-in replacement functions for existing routes

def replace_cre_update_route(app, supabase_factory, redis_client=None):
    """Replace existing CRE update route with instant updates"""

    flask_updates = FlaskInstantUpdates(app, supabase_factory, redis_client)

    @app.route('/update_lead_cre', methods=['POST'])
    @flask_updates.require_instant_auth(['cre', 'admin'])
    def update_lead_cre_instant():
        """Ultra-fast CRE lead update"""
        return flask_updates.update_lead_endpoint()

def replace_ps_update_route(app, supabase_factory, redis_client=None):
    """Replace existing PS update route with instant updates"""

    flask_updates = FlaskInstantUpdates(app, supabase_factory, redis_client)

    @app.route('/update_lead_ps', methods=['POST'])
    @flask_updates.require_instant_auth(['ps', 'admin'])
    def update_lead_ps_instant():
        """Ultra-fast PS lead update"""
        return flask_updates.update_lead_endpoint()

def add_instant_update_routes(app, supabase_factory, redis_client=None):
    """Add all instant update routes to Flask app"""

    flask_updates = FlaskInstantUpdates(app, supabase_factory, redis_client)

    # Main update endpoints
    @app.route('/api/instant/update_lead', methods=['POST'])
    @flask_updates.require_instant_auth()
    def instant_update_lead():
        return flask_updates.update_lead_endpoint()

    @app.route('/api/instant/batch_update', methods=['POST'])
    @flask_updates.require_instant_auth()
    def instant_batch_update():
        return flask_updates.batch_update_endpoint()

    @app.route('/api/instant/update_with_lock', methods=['POST'])
    @flask_updates.require_instant_auth()
    def instant_update_with_lock():
        return flask_updates.update_with_conflict_resolution_endpoint()

    # Performance monitoring
    @app.route('/api/instant/performance_stats', methods=['GET'])
    @flask_updates.require_instant_auth(['admin'])
    def instant_performance_stats():
        return flask_updates.get_performance_stats_endpoint()

    # Health check
    @app.route('/api/instant/health', methods=['GET'])
    def instant_health_check():
        try:
            stats = flask_updates.update_client.get_performance_stats()
            client_stats = stats.get('client_stats', {})

            is_healthy = (
                client_stats.get('sub_1s_rate', 0) >= 95 and
                client_stats.get('success_rate', 0) >= 95
            )

            return jsonify({
                'status': 'healthy' if is_healthy else 'degraded',
                'sub_1s_rate': client_stats.get('sub_1s_rate', 0),
                'success_rate': client_stats.get('success_rate', 0),
                'average_time': client_stats.get('average_time_recent', 0),
                'timestamp': datetime.now().isoformat()
            }), 200

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500

    return flask_updates

# JavaScript client-side code for instant updates
INSTANT_UPDATE_JS = """
// Ultra-Fast Lead Update JavaScript Client
class InstantUpdateClient {
    constructor() {
        this.updateInProgress = false;
        this.performanceLog = [];
    }

    async updateLead(leadUid, updateData, showSpinner = true) {
        if (this.updateInProgress) {
            console.warn('Update already in progress');
            return;
        }

        this.updateInProgress = true;
        const startTime = performance.now();

        try {
            // Show instant feedback
            if (showSpinner) {
                this.showUpdateSpinner(leadUid);
            }

            const response = await fetch('/api/instant/update_lead', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    lead_uid: leadUid,
                    update_data: updateData
                })
            });

            const result = await response.json();
            const clientExecutionTime = performance.now() - startTime;

            // Log performance
            this.logPerformance(result.execution_time, clientExecutionTime, result.success);

            if (result.success) {
                this.showUpdateSuccess(leadUid, result.execution_time);

                // Update UI immediately
                this.updateLeadUI(leadUid, updateData);
            } else {
                this.showUpdateError(leadUid, result.error);
            }

            return result;

        } catch (error) {
            const clientExecutionTime = performance.now() - startTime;
            this.logPerformance(null, clientExecutionTime, false);
            this.showUpdateError(leadUid, error.message);
            throw error;

        } finally {
            this.updateInProgress = false;
            if (showSpinner) {
                this.hideUpdateSpinner(leadUid);
            }
        }
    }

    async batchUpdateLeads(updates) {
        const startTime = performance.now();

        try {
            const response = await fetch('/api/instant/batch_update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    updates: updates
                })
            });

            const result = await response.json();
            const clientExecutionTime = performance.now() - startTime;

            console.log(`Batch update: ${result.successful_updates}/${result.total_updates} in ${result.average_execution_time.toFixed(3)}s`);

            return result;

        } catch (error) {
            console.error('Batch update failed:', error);
            throw error;
        }
    }

    showUpdateSpinner(leadUid) {
        const button = document.querySelector(`[data-lead-uid="${leadUid}"] .update-btn`);
        if (button) {
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
            button.disabled = true;
        }
    }

    hideUpdateSpinner(leadUid) {
        const button = document.querySelector(`[data-lead-uid="${leadUid}"] .update-btn`);
        if (button) {
            button.innerHTML = '<i class="fas fa-save"></i> Update';
            button.disabled = false;
        }
    }

    showUpdateSuccess(leadUid, executionTime) {
        const timeText = executionTime < 0.5 ?
            `🚀 Ultra-fast: ${(executionTime * 1000).toFixed(0)}ms` :
            `⚡ Fast: ${(executionTime * 1000).toFixed(0)}ms`;

        // Show success toast
        this.showToast(`Lead updated successfully! ${timeText}`, 'success');
    }

    showUpdateError(leadUid, error) {
        this.showToast(`Update failed: ${error}`, 'error');
    }

    updateLeadUI(leadUid, updateData) {
        // Update the lead row in the table immediately
        const leadRow = document.querySelector(`[data-lead-uid="${leadUid}"]`);
        if (leadRow) {
            for (const [field, value] of Object.entries(updateData)) {
                const cell = leadRow.querySelector(`[data-field="${field}"]`);
                if (cell) {
                    cell.textContent = value;
                    // Add flash effect
                    cell.classList.add('flash-update');
                    setTimeout(() => cell.classList.remove('flash-update'), 1000);
                }
            }
        }
    }

    showToast(message, type) {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;

        // Add to page
        document.body.appendChild(toast);

        // Show and auto-hide
        setTimeout(() => toast.classList.add('show'), 100);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => document.body.removeChild(toast), 300);
        }, 3000);
    }

    logPerformance(serverTime, clientTime, success) {
        this.performanceLog.push({
            serverTime,
            clientTime,
            success,
            timestamp: Date.now()
        });

        // Keep only last 50 entries
        if (this.performanceLog.length > 50) {
            this.performanceLog = this.performanceLog.slice(-50);
        }
    }

    getPerformanceStats() {
        const successfulUpdates = this.performanceLog.filter(log => log.success);
        const avgServerTime = successfulUpdates.reduce((sum, log) => sum + log.serverTime, 0) / successfulUpdates.length;
        const avgClientTime = successfulUpdates.reduce((sum, log) => sum + log.clientTime, 0) / successfulUpdates.length;

        return {
            totalUpdates: this.performanceLog.length,
            successfulUpdates: successfulUpdates.length,
            averageServerTime: avgServerTime,
            averageClientTime: avgClientTime,
            sub500msRate: (successfulUpdates.filter(log => log.serverTime < 500).length / successfulUpdates.length) * 100
        };
    }
}

// Global instance
const instantUpdateClient = new InstantUpdateClient();

// CSS for flash effects and toasts
const instantUpdateCSS = `
.flash-update {
    background-color: #d4edda !important;
    transition: background-color 1s ease;
}

.toast {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 12px 24px;
    border-radius: 4px;
    color: white;
    font-weight: bold;
    z-index: 10000;
    opacity: 0;
    transform: translateX(100%);
    transition: all 0.3s ease;
}

.toast.show {
    opacity: 1;
    transform: translateX(0);
}

.toast-success {
    background-color: #28a745;
}

.toast-error {
    background-color: #dc3545;
}
`;

// Add CSS to page
const styleSheet = document.createElement('style');
styleSheet.textContent = instantUpdateCSS;
document.head.appendChild(styleSheet);
"""

def add_instant_update_js(app):
    """Add JavaScript client code to Flask app"""

    @app.route('/static/js/instant-update.js')
    def instant_update_js():
        from flask import Response
        return Response(INSTANT_UPDATE_JS, mimetype='application/javascript')

    return INSTANT_UPDATE_JS