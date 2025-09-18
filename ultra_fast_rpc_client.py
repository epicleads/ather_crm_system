"""
Ultra-Fast RPC Client for Ather CRM System
Provides sub-1-second database operations using Supabase RPC functions
"""

import time
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date
import json
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)

@dataclass
class RPCResult:
    """Container for RPC operation results"""
    success: bool
    data: Any
    execution_time: float
    error: Optional[str] = None

class UltraFastRPCClient:
    """Ultra-fast database operations using Supabase RPC functions"""

    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.performance_log = []

    def _log_performance(self, operation_name: str):
        """Decorator to log RPC performance"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time

                    # Log performance
                    self.performance_log.append({
                        'operation': operation_name,
                        'execution_time': execution_time,
                        'timestamp': datetime.now().isoformat(),
                        'success': True
                    })

                    logger.info(f"🚀 {operation_name} completed in {execution_time:.3f}s")
                    return result

                except Exception as e:
                    execution_time = time.time() - start_time
                    self.performance_log.append({
                        'operation': operation_name,
                        'execution_time': execution_time,
                        'timestamp': datetime.now().isoformat(),
                        'success': False,
                        'error': str(e)
                    })
                    logger.error(f"❌ {operation_name} failed after {execution_time:.3f}s: {e}")
                    raise
            return wrapper
        return decorator

    @_log_performance("CRE Dashboard RPC")
    def get_cre_dashboard_ultra_fast(self, cre_name: str, filters: Dict[str, Any] = None) -> RPCResult:
        """
        Ultra-fast CRE dashboard data loading
        Target: < 300ms execution time
        """
        start_time = time.time()

        try:
            # Prepare RPC parameters
            params = {
                'p_cre_name': cre_name,
                'p_limit': filters.get('limit', 1000) if filters else 1000
            }

            # Apply optional filters
            if filters:
                if filters.get('final_status') and filters['final_status'] != 'All':
                    params['p_final_status'] = filters['final_status']
                if filters.get('lead_status') and filters['lead_status'] != 'All':
                    params['p_lead_status'] = filters['lead_status']
                if filters.get('date_from'):
                    params['p_date_from'] = filters['date_from']
                if filters.get('date_to'):
                    params['p_date_to'] = filters['date_to']
                if filters.get('source') and filters['source'] != 'All':
                    params['p_source'] = filters['source']

            # Execute RPC function
            result = self.supabase.rpc('get_cre_dashboard_optimized', params).execute()

            execution_time = time.time() - start_time

            return RPCResult(
                success=True,
                data=result.data,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return RPCResult(
                success=False,
                data=None,
                execution_time=execution_time,
                error=str(e)
            )

    @_log_performance("PS Dashboard RPC")
    def get_ps_dashboard_ultra_fast(self, ps_name: str, filters: Dict[str, Any] = None) -> RPCResult:
        """
        Ultra-fast PS dashboard data loading
        Target: < 300ms execution time
        """
        start_time = time.time()

        try:
            # Prepare RPC parameters
            params = {
                'p_ps_name': ps_name,
                'p_limit': filters.get('limit', 1000) if filters else 1000
            }

            # Apply optional filters
            if filters:
                if filters.get('final_status') and filters['final_status'] != 'All':
                    params['p_final_status'] = filters['final_status']
                if filters.get('lead_status') and filters['lead_status'] != 'All':
                    params['p_lead_status'] = filters['lead_status']
                if filters.get('date_from'):
                    params['p_date_from'] = filters['date_from']
                if filters.get('date_to'):
                    params['p_date_to'] = filters['date_to']

            # Execute RPC function
            result = self.supabase.rpc('get_ps_dashboard_optimized', params).execute()

            execution_time = time.time() - start_time

            return RPCResult(
                success=True,
                data=result.data,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return RPCResult(
                success=False,
                data=None,
                execution_time=execution_time,
                error=str(e)
            )

    @_log_performance("Duplicate Check RPC")
    def check_duplicates_ultra_fast(self, phone_numbers: List[str]) -> RPCResult:
        """
        Ultra-fast duplicate checking for multiple phone numbers
        Target: < 200ms execution time regardless of number of phones
        """
        start_time = time.time()

        try:
            if not phone_numbers:
                return RPCResult(
                    success=True,
                    data={'duplicates': {}, 'phones_checked': 0, 'duplicates_found': 0},
                    execution_time=0
                )

            # Execute RPC function
            result = self.supabase.rpc('check_duplicates_batch', {
                'phone_numbers': phone_numbers
            }).execute()

            execution_time = time.time() - start_time

            return RPCResult(
                success=True,
                data=result.data,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return RPCResult(
                success=False,
                data=None,
                execution_time=execution_time,
                error=str(e)
            )

    @_log_performance("Test Drive Update RPC")
    def update_test_drive_ultra_fast(self, lead_uid: str, test_drive_data: Dict[str, Any]) -> RPCResult:
        """
        Ultra-fast test drive operations
        Target: < 200ms execution time
        """
        start_time = time.time()

        try:
            # Prepare RPC parameters
            params = {
                'p_lead_uid': lead_uid,
                'p_test_drive_date': test_drive_data.get('test_drive_date'),
                'p_feedback': test_drive_data.get('feedback', ''),
                'p_status': test_drive_data.get('status', 'Completed')
            }

            # Execute RPC function
            result = self.supabase.rpc('update_test_drive_optimized', params).execute()

            execution_time = time.time() - start_time

            return RPCResult(
                success=True,
                data=result.data,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return RPCResult(
                success=False,
                data=None,
                execution_time=execution_time,
                error=str(e)
            )

    @_log_performance("Bulk Lead Creation RPC")
    def create_leads_bulk_ultra_fast(self, leads_data: List[Dict[str, Any]]) -> RPCResult:
        """
        Ultra-fast bulk lead creation with duplicate handling
        Target: < 500ms for 100 leads
        """
        start_time = time.time()

        try:
            if not leads_data:
                return RPCResult(
                    success=True,
                    data={'total_processed': 0, 'inserted': 0, 'duplicates_skipped': 0, 'errors': 0},
                    execution_time=0
                )

            # Convert to JSONB format for RPC
            leads_jsonb = json.dumps(leads_data)

            # Execute RPC function
            result = self.supabase.rpc('create_leads_bulk_optimized', {
                'leads_data': leads_jsonb
            }).execute()

            execution_time = time.time() - start_time

            return RPCResult(
                success=True,
                data=result.data,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return RPCResult(
                success=False,
                data=None,
                execution_time=execution_time,
                error=str(e)
            )

    @_log_performance("Analytics RPC")
    def get_analytics_ultra_fast(self, date_range: tuple = None, filters: Dict[str, Any] = None) -> RPCResult:
        """
        Ultra-fast analytics data loading
        Target: < 400ms execution time
        """
        start_time = time.time()

        try:
            # Prepare RPC parameters
            params = {}

            if date_range:
                params['p_date_from'] = date_range[0]
                params['p_date_to'] = date_range[1]

            if filters:
                if filters.get('cre_name'):
                    params['p_cre_name'] = filters['cre_name']
                if filters.get('ps_name'):
                    params['p_ps_name'] = filters['ps_name']
                if filters.get('branch'):
                    params['p_branch'] = filters['branch']

            # Execute RPC function
            result = self.supabase.rpc('get_analytics_optimized', params).execute()

            execution_time = time.time() - start_time

            return RPCResult(
                success=True,
                data=result.data,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return RPCResult(
                success=False,
                data=None,
                execution_time=execution_time,
                error=str(e)
            )

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for all RPC operations"""
        if not self.performance_log:
            return {'message': 'No operations recorded yet'}

        # Calculate statistics
        successful_ops = [op for op in self.performance_log if op['success']]
        failed_ops = [op for op in self.performance_log if not op['success']]

        execution_times = [op['execution_time'] for op in successful_ops]

        stats = {
            'total_operations': len(self.performance_log),
            'successful_operations': len(successful_ops),
            'failed_operations': len(failed_ops),
            'success_rate': (len(successful_ops) / len(self.performance_log)) * 100,
            'average_execution_time': sum(execution_times) / len(execution_times) if execution_times else 0,
            'fastest_operation': min(execution_times) if execution_times else 0,
            'slowest_operation': max(execution_times) if execution_times else 0,
            'sub_1_second_rate': (len([t for t in execution_times if t < 1.0]) / len(execution_times)) * 100 if execution_times else 0
        }

        # Operations breakdown
        operations_breakdown = {}
        for op in self.performance_log:
            op_name = op['operation']
            if op_name not in operations_breakdown:
                operations_breakdown[op_name] = {
                    'count': 0,
                    'avg_time': 0,
                    'success_count': 0
                }

            operations_breakdown[op_name]['count'] += 1
            if op['success']:
                operations_breakdown[op_name]['success_count'] += 1

        # Calculate average times per operation
        for op_name in operations_breakdown:
            op_times = [op['execution_time'] for op in self.performance_log
                       if op['operation'] == op_name and op['success']]
            operations_breakdown[op_name]['avg_time'] = sum(op_times) / len(op_times) if op_times else 0

        stats['operations_breakdown'] = operations_breakdown
        stats['recent_operations'] = self.performance_log[-10:]  # Last 10 operations

        return stats

    def clear_performance_log(self):
        """Clear the performance log"""
        self.performance_log.clear()
        logger.info("Performance log cleared")

# Integration classes for easy replacement
class UltraFastDashboard:
    """Drop-in replacement for existing dashboard operations"""

    def __init__(self, supabase_client):
        self.rpc_client = UltraFastRPCClient(supabase_client)

    def get_cre_dashboard_data(self, cre_name: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ultra-fast CRE dashboard data"""
        result = self.rpc_client.get_cre_dashboard_ultra_fast(cre_name, filters)

        if result.success:
            dashboard_data = result.data
            dashboard_data['execution_time'] = result.execution_time
            dashboard_data['method'] = 'RPC_OPTIMIZED'
            return dashboard_data
        else:
            raise Exception(f"Dashboard RPC failed: {result.error}")

    def get_ps_dashboard_data(self, ps_name: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ultra-fast PS dashboard data"""
        result = self.rpc_client.get_ps_dashboard_ultra_fast(ps_name, filters)

        if result.success:
            dashboard_data = result.data
            dashboard_data['execution_time'] = result.execution_time
            dashboard_data['method'] = 'RPC_OPTIMIZED'
            return dashboard_data
        else:
            raise Exception(f"PS Dashboard RPC failed: {result.error}")

class UltraFastOperations:
    """Drop-in replacement for existing database operations"""

    def __init__(self, supabase_client):
        self.rpc_client = UltraFastRPCClient(supabase_client)

    def check_duplicates(self, phone_numbers: List[str]) -> Dict[str, Any]:
        """Ultra-fast duplicate checking"""
        result = self.rpc_client.check_duplicates_ultra_fast(phone_numbers)

        if result.success:
            return result.data
        else:
            raise Exception(f"Duplicate check RPC failed: {result.error}")

    def update_test_drive(self, lead_uid: str, test_drive_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ultra-fast test drive operations"""
        result = self.rpc_client.update_test_drive_ultra_fast(lead_uid, test_drive_data)

        if result.success:
            return result.data
        else:
            raise Exception(f"Test drive RPC failed: {result.error}")

    def create_leads_bulk(self, leads_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ultra-fast bulk lead creation"""
        result = self.rpc_client.create_leads_bulk_ultra_fast(leads_data)

        if result.success:
            return result.data
        else:
            raise Exception(f"Bulk lead creation RPC failed: {result.error}")

    def get_analytics(self, date_range: tuple = None, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ultra-fast analytics"""
        result = self.rpc_client.get_analytics_ultra_fast(date_range, filters)

        if result.success:
            return result.data
        else:
            raise Exception(f"Analytics RPC failed: {result.error}")

# Factory functions for easy integration
def create_ultra_fast_rpc_client(supabase_client):
    """Create ultra-fast RPC client"""
    return UltraFastRPCClient(supabase_client)

def create_ultra_fast_dashboard(supabase_client):
    """Create ultra-fast dashboard operations"""
    return UltraFastDashboard(supabase_client)

def create_ultra_fast_operations(supabase_client):
    """Create ultra-fast database operations"""
    return UltraFastOperations(supabase_client)

# Performance monitoring decorator for existing functions
def monitor_rpc_performance(operation_name: str):
    """Decorator to monitor any function's performance"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.info(f"🚀 {operation_name} completed in {execution_time:.3f}s")

                # Add execution time to result if it's a dict
                if isinstance(result, dict):
                    result['execution_time'] = execution_time
                    result['method'] = 'RPC_OPTIMIZED'

                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"❌ {operation_name} failed after {execution_time:.3f}s: {e}")
                raise
        return wrapper
    return decorator