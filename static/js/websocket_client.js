/**
 * WebSocket Client for Ather CRM System
 * Handles real-time communication between frontend and backend
 */

// Lightweight logger with levels
const CRM_LOG_LEVELS = { error: 0, warn: 1, info: 2, debug: 3 };
class CRMLogger {
    constructor(namespace = 'CRM', level = null) {
        const saved = (typeof window !== 'undefined' && window.localStorage)
            ? window.localStorage.getItem('crmLogLevel')
            : null;
        const envLevel = (typeof window !== 'undefined' && window.CRM_LOG_LEVEL)
            ? window.CRM_LOG_LEVEL
            : null;
        const initial = (level || envLevel || saved || 'warn').toLowerCase();
        this.level = CRM_LOG_LEVELS[initial] !== undefined ? initial : 'warn';
        this.namespace = namespace;
    }
    setLevel(level) {
        const lvl = (level || '').toLowerCase();
        if (CRM_LOG_LEVELS[lvl] === undefined) return;
        this.level = lvl;
        try { window.localStorage && window.localStorage.setItem('crmLogLevel', lvl); } catch (e) {}
    }
    shouldLog(target) { return CRM_LOG_LEVELS[target] <= CRM_LOG_LEVELS[this.level]; }
    fmt(args) { return [`[${this.namespace}]`, ...args]; }
    debug(...args) { if (this.shouldLog('debug')) console.debug(...this.fmt(args)); }
    info(...args)  { if (this.shouldLog('info'))  console.info(...this.fmt(args)); }
    warn(...args)  { if (this.shouldLog('warn'))  console.warn(...this.fmt(args)); }
    error(...args) { if (this.shouldLog('error')) console.error(...this.fmt(args)); }
}

class CRMWebSocketClient {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.isAuthenticated = false;
        this.userInfo = null;
        this.eventHandlers = new Map();
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.log = new CRMLogger('WS');
        
        // Initialize connection
        this.init();
    }
    
    init() {
        try {
            // Connect to WebSocket server
            this.socket = io({
                transports: ['websocket', 'polling'],
                upgrade: true,
                rememberUpgrade: true,
                timeout: 20000
            });
            
            this.setupEventHandlers();
            
        } catch (error) {
            this.log.error('Failed to initialize WebSocket client:', error);
        }
    }
    
    setupEventHandlers() {
        // Connection events
        this.socket.on('connect', () => {
            this.log.info('WebSocket connected');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.triggerEvent('connected', { sid: this.socket.id });
            
            // Auto-authenticate if user info is available
            if (this.userInfo) {
                this.authenticate(this.userInfo);
            }
        });
        
        this.socket.on('disconnect', (reason) => {
            this.log.warn('WebSocket disconnected:', reason);
            this.isConnected = false;
            this.isAuthenticated = false;
            this.triggerEvent('disconnected', { reason });
            
            // Attempt to reconnect
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                setTimeout(() => {
                    this.reconnectAttempts++;
                    this.init();
                }, this.reconnectDelay * this.reconnectAttempts);
            }
        });
        
        this.socket.on('connect_error', (error) => {
            this.log.error('WebSocket connection error:', error);
            this.triggerEvent('connection_error', { error });
        });
        
        // Authentication events
        this.socket.on('auth_success', (data) => {
            this.log.info('WebSocket authentication successful');
            this.isAuthenticated = true;
            this.triggerEvent('auth_success', data);
        });
        
        this.socket.on('auth_error', (data) => {
            this.log.warn('WebSocket authentication failed:', data);
            this.isAuthenticated = false;
            this.triggerEvent('auth_error', data);
        });
        
        // Lead management events
        this.socket.on('lead_assigned_notification', (data) => {
            this.triggerEvent('lead_assigned', data);
            this.showNotification(data.message, 'success');
        });
        
        this.socket.on('lead_status_changed', (data) => {
            this.triggerEvent('lead_status_changed', data);
            this.updateLeadStatus(data);
        });
        
        this.socket.on('lead_updated', (data) => {
            this.triggerEvent('lead_updated', data);
            this.refreshLeadData(data.lead_uid);
        });
        
        this.socket.on('lead_assignment_update', (data) => {
            this.triggerEvent('lead_assignment_update', data);
            this.updateDashboardCounts();
        });
        
        // Call attempt events
        this.socket.on('call_attempt_logged', (data) => {
            this.triggerEvent('call_attempt_logged', data);
            this.updateCallHistory(data);
        });
        
        // Dashboard data events
        this.socket.on('admin_dashboard_data', (data) => {
            this.triggerEvent('admin_dashboard_data', data);
            this.updateAdminDashboard(data);
        });
        
        this.socket.on('cre_dashboard_data', (data) => {
            this.triggerEvent('cre_dashboard_data', data);
            this.updateCREDashboard(data);
        });
        
        this.socket.on('ps_dashboard_data', (data) => {
            this.triggerEvent('ps_dashboard_data', data);
            this.updatePSDashboard(data);
        });
        
        this.socket.on('branch_head_dashboard_data', (data) => {
            this.triggerEvent('branch_head_dashboard_data', data);
            this.updateBranchHeadDashboard(data);
        });
        
        // Chat events removed
        
        // User presence events
        this.socket.on('user_online', (data) => {
            this.triggerEvent('user_online', data);
            this.updateUserPresence(data, true);
        });
        
        this.socket.on('user_offline', (data) => {
            this.triggerEvent('user_offline', data);
            this.updateUserPresence(data, false);
        });
        
        // Lead room events
        this.socket.on('joined_lead_room', (data) => {
            this.log.debug('Joined lead room:', data.lead_uid);
        });
        
        this.socket.on('left_lead_room', (data) => {
            this.log.debug('Left lead room:', data.lead_uid);
        });
        
        // Error handling
        this.socket.on('dashboard_data_error', (data) => {
            this.log.error('Dashboard data error:', data);
            this.triggerEvent('dashboard_data_error', data);
        });
    }
    
    authenticate(userInfo) {
        if (!this.isConnected) {
            console.warn('Cannot authenticate: WebSocket not connected');
            return false;
        }
        
        this.userInfo = userInfo;
        
        const authData = {
            user_id: userInfo.user_id,
            user_type: userInfo.user_type,
            username: userInfo.username,
            branch: userInfo.branch
        };
        
        this.socket.emit('authenticate', authData);
        return true;
    }
    
    // Event handling
    on(event, handler) {
        if (!this.eventHandlers.has(event)) {
            this.eventHandlers.set(event, []);
        }
        this.eventHandlers.get(event).push(handler);
    }
    
    off(event, handler) {
        if (this.eventHandlers.has(event)) {
            const handlers = this.eventHandlers.get(event);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
    
    triggerEvent(event, data) {
        if (this.eventHandlers.has(event)) {
            this.eventHandlers.get(event).forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    this.log.error(`Error in event handler for ${event}:`, error);
                }
            });
        }
    }
    
    // Lead management
    joinLeadRoom(leadUid) {
        if (this.isAuthenticated) {
            this.socket.emit('join_lead_room', { lead_uid: leadUid });
        }
    }
    
    leaveLeadRoom(leadUid) {
        if (this.isAuthenticated) {
            this.socket.emit('leave_lead_room', { lead_uid: leadUid });
        }
    }
    
    notifyLeadAssignment(leadUid, creName, psName, source) {
        if (this.isAuthenticated) {
            this.socket.emit('lead_assigned', {
                lead_uid: leadUid,
                cre_name: creName,
                ps_name: psName,
                source: source
            });
        }
    }
    
    notifyLeadStatusUpdate(leadUid, status, remarks = '') {
        if (this.isAuthenticated) {
            this.socket.emit('lead_status_update', {
                lead_uid: leadUid,
                status: status,
                user_type: this.userInfo.user_type,
                username: this.userInfo.username,
                remarks: remarks
            });
        }
    }
    
    notifyCallAttempt(leadUid, callNumber, status) {
        if (this.isAuthenticated) {
            this.socket.emit('call_attempt_logged', {
                lead_uid: leadUid,
                call_number: callNumber,
                status: status,
                user_type: this.userInfo.user_type,
                username: this.userInfo.username
            });
        }
    }
    
    // Dashboard data
    requestDashboardData() {
        if (this.isAuthenticated) {
            this.socket.emit('dashboard_data_request', {
                user_type: this.userInfo.user_type,
                user_id: this.userInfo.user_id
            });
        }
    }
    
    // Chat functionality removed
    
    // Utility methods
    isReady() {
        return this.isConnected && this.isAuthenticated;
    }
    
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
    }
    
    // UI update methods
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }
    
    updateLeadStatus(data) {
        // Find and update lead status in the current page
        const leadElement = document.querySelector(`[data-lead-uid="${data.lead_uid}"]`);
        if (leadElement) {
            const statusElement = leadElement.querySelector('.lead-status');
            if (statusElement) {
                statusElement.textContent = data.new_status;
                statusElement.className = `lead-status badge bg-${this.getStatusColor(data.new_status)}`;
            }
            
            // Update timestamp
            const timestampElement = leadElement.querySelector('.last-updated');
            if (timestampElement) {
                timestampElement.textContent = `Updated: ${new Date(data.updated_at).toLocaleString()}`;
            }
        }
    }
    
    refreshLeadData(leadUid) {
        // Trigger a refresh of lead data
        this.triggerEvent('lead_data_refresh', { lead_uid: leadUid });
    }
    
    updateDashboardCounts() {
        // Request fresh dashboard data
        this.requestDashboardData();
    }
    
    updateCallHistory(data) {
        // Update call history display
        this.triggerEvent('call_history_updated', data);
    }
    
    updateAdminDashboard(data) {
        // Update admin dashboard counts
        this.updateDashboardElement('#cre-count', data.cre_count);
        this.updateDashboardElement('#ps-count', data.ps_count);
        this.updateDashboardElement('#leads-count', data.leads_count);
        this.updateDashboardElement('#unassigned-leads', data.unassigned_leads);
    }
    
    updateCREDashboard(data) {
        // Update CRE dashboard counts
        this.updateDashboardElement('#assigned-leads', data.assigned_leads);
        this.updateDashboardElement('#pending-leads', data.pending_leads);
    }
    
    updatePSDashboard(data) {
        // Update PS dashboard counts
        this.updateDashboardElement('#assigned-leads', data.assigned_leads);
        this.updateDashboardElement('#pending-leads', data.pending_leads);
    }
    
    updateBranchHeadDashboard(data) {
        // Update branch head dashboard counts
        this.updateDashboardElement('#branch-leads', data.branch_leads);
        this.updateDashboardElement('#branch-ps', data.branch_ps);
    }
    
    updateDashboardElement(selector, value) {
        const element = document.querySelector(selector);
        if (element) {
            element.textContent = value;
            
            // Add animation effect
            element.classList.add('updated');
            setTimeout(() => {
                element.classList.remove('updated');
            }, 1000);
        }
    }
    
    updateUserPresence(data, isOnline) {
        // Update user presence indicators
        const presenceElement = document.querySelector(`[data-user-id="${data.user_id}"] .user-presence`);
        if (presenceElement) {
            presenceElement.className = `user-presence badge ${isOnline ? 'bg-success' : 'bg-secondary'}`;
            presenceElement.textContent = isOnline ? 'Online' : 'Offline';
        }
    }
    
    // Chat display methods removed
    
    getStatusColor(status) {
        const statusColors = {
            'Pending': 'warning',
            'In Progress': 'info',
            'Qualified': 'primary',
            'Won': 'success',
            'Lost': 'danger',
            'Not Interested': 'secondary'
        };
        return statusColors[status] || 'secondary';
    }
}

// Global instance
window.crmWebSocket = new CRMWebSocketClient();

// Auto-authenticate when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Check if user is logged in and get user info
    const userInfo = window.crmUserInfo;
    if (userInfo && window.crmWebSocket) {
        window.crmWebSocket.authenticate(userInfo);
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CRMWebSocketClient;
}
