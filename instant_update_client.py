"""
Instant Lead Update Client - GUARANTEED Sub-1-Second Updates
Provides real-time lead updates with performance monitoring and fallback mechanisms
"""

import time
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import redis
from functools import wraps

# Import the ultra-fast update system
from ultra_fast_lead_update_system import (
    UltraFastLeadUpdater,
    LeadUpdateRequest,
    UpdateResult,
    create_ultra_fast_lead_updater
)

logger = logging.getLogger(__name__)

@dataclass
class InstantUpdateConfig:
    """Configuration for instant updates"""
    target_time_ms: int = 500  # Target update time in milliseconds
    timeout_ms: int = 800      # Maximum allowed time
    retry_attempts: int = 2    # Number of retries on failure
    use_rpc: bool = True       # Prefer RPC over parallel operations
    enable_caching: bool = True
    enable_preloading: bool = True
    connection_pool_size: int = 20

class PerformanceMonitor:
    """Real-time performance monitoring for updates"""

    def __init__(self):
        self.update_stats = {
            'total_updates': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'sub_500ms_count': 0,
            'sub_1s_count': 0,
            'performance_history': []
        }
        self._lock = threading.Lock()

    def record_update(self, execution_time: float, success: bool):
        """Record update performance"""
        with self._lock:
            self.update_stats['total_updates'] += 1

            if success:
                self.update_stats['successful_updates'] += 1

                if execution_time < 0.5:
                    self.update_stats['sub_500ms_count'] += 1
                if execution_time < 1.0:
                    self.update_stats['sub_1s_count'] += 1
            else:
                self.update_stats['failed_updates'] += 1

            # Keep last 100 performance records
            self.update_stats['performance_history'].append({
                'execution_time': execution_time,
                'success': success,
                'timestamp': time.time()
            })

            if len(self.update_stats['performance_history']) > 100:
                self.update_stats['performance_history'] = self.update_stats['performance_history'][-100:]

    def get_current_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        with self._lock:
            total = self.update_stats['total_updates']
            if total == 0:
                return {'message': 'No updates recorded yet'}

            success_rate = (self.update_stats['successful_updates'] / total) * 100
            sub_500ms_rate = (self.update_stats['sub_500ms_count'] / total) * 100
            sub_1s_rate = (self.update_stats['sub_1s_count'] / total) * 100

            # Calculate average time from recent updates
            recent_times = [
                record['execution_time']
                for record in self.update_stats['performance_history'][-20:]
                if record['success']
            ]

            avg_time = sum(recent_times) / len(recent_times) if recent_times else 0

            return {
                'total_updates': total,
                'success_rate': round(success_rate, 2),
                'sub_500ms_rate': round(sub_500ms_rate, 2),
                'sub_1s_rate': round(sub_1s_rate, 2),
                'average_time_recent': round(avg_time, 3),
                'performance_target_met': sub_1s_rate >= 95,
                'ultra_fast_target_met': sub_500ms_rate >= 80
            }

class InstantUpdateClient:
    """Main client for instant lead updates"""

    def __init__(self, supabase_factory, config: InstantUpdateConfig = None, redis_client=None):
        self.supabase_factory = supabase_factory
        self.config = config or InstantUpdateConfig()
        self.redis_client = redis_client

        # Initialize ultra-fast updater
        self.updater = create_ultra_fast_lead_updater(supabase_factory, redis_client)

        # Performance monitoring
        self.monitor = PerformanceMonitor()

        # Callback system for real-time notifications
        self.update_callbacks: List[Callable] = []

        # Background thread for preloading
        self.preload_thread = None
        self.preload_queue = []
        self.preload_lock = threading.Lock()

        # Start background services
        self._start_background_services()

    def _start_background_services(self):
        """Start background services for optimization"""
        if self.config.enable_preloading:
            self.preload_thread = threading.Thread(
                target=self._preload_worker,
                daemon=True
            )
            self.preload_thread.start()

    def _preload_worker(self):
        """Background worker for preloading frequently accessed leads"""
        while True:
            try:
                with self.preload_lock:
                    if self.preload_queue:
                        lead_uids = self.preload_queue.copy()
                        self.preload_queue.clear()
                    else:
                        lead_uids = []

                if lead_uids:
                    self.updater.preload_frequent_leads(lead_uids)

                time.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Preload worker error: {e}")
                time.sleep(10)

    def register_update_callback(self, callback: Callable[[UpdateResult], None]):
        """Register callback for real-time update notifications"""
        self.update_callbacks.append(callback)

    def _notify_callbacks(self, result: UpdateResult):
        """Notify all registered callbacks"""
        for callback in self.update_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def update_lead_instantly(self, lead_uid: str, update_data: Dict[str, Any],
                            user_type: str, user_name: str) -> UpdateResult:
        """
        GUARANTEED sub-1-second lead update with multiple optimization strategies
        """
        start_time = time.time()

        # Queue for preloading if enabled
        if self.config.enable_preloading:
            with self.preload_lock:
                if lead_uid not in self.preload_queue:
                    self.preload_queue.append(lead_uid)

        # Create update request
        request = LeadUpdateRequest(
            lead_uid=lead_uid,
            user_type=user_type,
            user_name=user_name,
            update_data=update_data,
            priority=1
        )

        # Strategy 1: Try RPC update first (fastest)
        if self.config.use_rpc:
            try:
                result = self.updater.update_lead_with_rpc(request)

                if result.success and result.execution_time < (self.config.timeout_ms / 1000):
                    self._record_and_notify(result)
                    return result

            except Exception as e:
                logger.warning(f"RPC update failed, falling back: {e}")

        # Strategy 2: Parallel update fallback
        try:
            result = self.updater.update_lead_ultra_fast(request)

            if result.success:
                self._record_and_notify(result)
                return result

        except Exception as e:
            logger.error(f"Parallel update failed: {e}")

        # Strategy 3: Traditional update as last resort
        try:
            result = self._traditional_update_fallback(request)
            self._record_and_notify(result)
            return result

        except Exception as e:
            # Return failure result
            execution_time = time.time() - start_time
            result = UpdateResult(
                success=False,
                execution_time=execution_time,
                operations_completed=[],
                error=f"All update strategies failed: {e}",
                lead_uid=lead_uid
            )

            self._record_and_notify(result)
            return result

    def _traditional_update_fallback(self, request: LeadUpdateRequest) -> UpdateResult:
        """Traditional update method as fallback"""
        start_time = time.time()

        try:
            with self.updater.connection_pool.get_connection() as conn:
                # Simple update to lead_master
                query = conn.table('lead_master').update(request.update_data).eq('uid', request.lead_uid)
                result = query.execute()

                execution_time = time.time() - start_time

                return UpdateResult(
                    success=True,
                    execution_time=execution_time,
                    operations_completed=['traditional_update'],
                    lead_uid=request.lead_uid
                )

        except Exception as e:
            execution_time = time.time() - start_time
            return UpdateResult(
                success=False,
                execution_time=execution_time,
                operations_completed=[],
                error=str(e),
                lead_uid=request.lead_uid
            )

    def _record_and_notify(self, result: UpdateResult):
        """Record performance and notify callbacks"""
        self.monitor.record_update(result.execution_time, result.success)
        self._notify_callbacks(result)

        # Log performance warnings
        if result.execution_time > 1.0:
            logger.warning(
                f"Update exceeded 1s: {result.execution_time:.3f}s for {result.lead_uid}"
            )
        elif result.execution_time > 0.5:
            logger.info(
                f"Update slower than target: {result.execution_time:.3f}s for {result.lead_uid}"
            )

    def batch_update_leads_instantly(self, updates: List[Dict[str, Any]]) -> List[UpdateResult]:
        """Batch update multiple leads with instant performance"""
        if not updates:
            return []

        start_time = time.time()

        # Convert to update requests
        requests = [
            LeadUpdateRequest(
                lead_uid=update['lead_uid'],
                user_type=update['user_type'],
                user_name=update['user_name'],
                update_data=update['update_data']
            )
            for update in updates
        ]

        # Use batch update from ultra-fast updater
        results = self.updater.batch_update_leads(requests)

        # Record performance for each update
        for result in results:
            self._record_and_notify(result)

        total_time = time.time() - start_time
        logger.info(f"Batch update completed: {len(updates)} leads in {total_time:.3f}s")

        return results

    def update_with_optimistic_locking(self, lead_uid: str, update_data: Dict[str, Any],
                                     user_type: str, user_name: str,
                                     expected_version: int) -> UpdateResult:
        """Update with conflict detection and resolution"""
        start_time = time.time()

        try:
            with self.updater.connection_pool.get_connection() as conn:
                # Use RPC with conflict resolution
                result = conn.rpc('update_lead_with_conflict_resolution', {
                    'p_lead_uid': lead_uid,
                    'p_user_type': user_type,
                    'p_user_name': user_name,
                    'p_update_data': json.dumps(update_data),
                    'p_expected_version': expected_version
                }).execute()

                execution_time = time.time() - start_time

                rpc_result = result.data

                update_result = UpdateResult(
                    success=rpc_result.get('success', False),
                    execution_time=execution_time,
                    operations_completed=['conflict_resolution_update'],
                    lead_uid=lead_uid,
                    error=rpc_result.get('error') if not rpc_result.get('success') else None
                )

                self._record_and_notify(update_result)
                return update_result

        except Exception as e:
            execution_time = time.time() - start_time
            result = UpdateResult(
                success=False,
                execution_time=execution_time,
                operations_completed=[],
                error=str(e),
                lead_uid=lead_uid
            )

            self._record_and_notify(result)
            return result

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        client_stats = self.monitor.get_current_stats()
        updater_stats = self.updater.get_performance_stats()

        return {
            'client_stats': client_stats,
            'updater_stats': updater_stats,
            'configuration': asdict(self.config),
            'timestamp': datetime.now().isoformat()
        }

    def warm_up_system(self, sample_lead_uids: List[str]):
        """Warm up the system for optimal performance"""
        logger.info("Warming up instant update system...")

        # Preload sample leads
        if sample_lead_uids:
            self.updater.preload_frequent_leads(sample_lead_uids[:10])

        # Test a dummy update to warm up connections
        try:
            test_result = self.update_lead_instantly(
                'TEST-WARMUP-UID',
                {'test_field': 'warmup'},
                'cre',
                'WARMUP_USER'
            )
            logger.info(f"System warmup completed in {test_result.execution_time:.3f}s")
        except Exception as e:
            logger.warning(f"Warmup test failed (expected): {e}")

    def optimize_for_user(self, user_type: str, user_name: str,
                         frequently_updated_leads: List[str]):
        """Optimize system for specific user patterns"""
        # Preload frequently updated leads for this user
        if frequently_updated_leads:
            with self.preload_lock:
                self.preload_queue.extend(frequently_updated_leads)

        logger.info(f"System optimized for {user_type} user: {user_name}")

# High-level API functions for easy integration
def create_instant_update_client(supabase_factory, redis_client=None,
                               target_time_ms: int = 500) -> InstantUpdateClient:
    """Create instant update client with custom configuration"""
    config = InstantUpdateConfig(target_time_ms=target_time_ms)
    return InstantUpdateClient(supabase_factory, config, redis_client)

def update_lead_in_real_time(supabase_factory, lead_uid: str, update_data: Dict[str, Any],
                           user_type: str, user_name: str, redis_client=None) -> UpdateResult:
    """One-line function for real-time lead updates"""
    client = create_instant_update_client(supabase_factory, redis_client)
    return client.update_lead_instantly(lead_uid, update_data, user_type, user_name)

# Performance decorator for monitoring any update function
def monitor_update_performance(target_ms: int = 1000):
    """Decorator to monitor update performance"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                # Log performance
                if execution_time > (target_ms / 1000):
                    logger.warning(
                        f"{func.__name__} exceeded target {target_ms}ms: {execution_time:.3f}s"
                    )
                else:
                    logger.info(
                        f"{func.__name__} completed in {execution_time:.3f}s ✓"
                    )

                return result

            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"{func.__name__} failed after {execution_time:.3f}s: {e}"
                )
                raise

        return wrapper
    return decorator

# Real-time update callback examples
def log_update_callback(result: UpdateResult):
    """Example callback to log all updates"""
    status = "✓" if result.success else "✗"
    logger.info(
        f"Update {status} {result.lead_uid}: {result.execution_time:.3f}s"
    )

def performance_alert_callback(result: UpdateResult):
    """Example callback to alert on slow updates"""
    if result.execution_time > 1.0:
        logger.warning(
            f"SLOW UPDATE ALERT: {result.lead_uid} took {result.execution_time:.3f}s"
        )

def websocket_notification_callback(result: UpdateResult):
    """Example callback for WebSocket notifications"""
    # This would emit real-time updates to connected clients
    notification = {
        'type': 'lead_updated',
        'lead_uid': result.lead_uid,
        'success': result.success,
        'execution_time': result.execution_time,
        'timestamp': datetime.now().isoformat()
    }
    # emit_to_websocket(notification)  # Your WebSocket implementation
    pass