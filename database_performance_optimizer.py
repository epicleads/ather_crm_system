"""
Advanced Database Performance Optimizer for Ather CRM System
Provides batching, parallel operations, query optimization, and connection pooling
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
from datetime import datetime
from dataclasses import dataclass
from contextlib import contextmanager
import threading
from functools import wraps
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class QueryConfig:
    """Configuration for optimized queries"""
    batch_size: int = 100
    max_workers: int = 5
    retry_attempts: int = 3
    timeout_seconds: int = 30
    cache_ttl: int = 300  # 5 minutes

class DatabaseConnectionPool:
    """Thread-safe connection pool for Supabase clients"""

    def __init__(self, supabase_factory, pool_size: int = 10):
        self.supabase_factory = supabase_factory
        self.pool_size = pool_size
        self._pool = []
        self._lock = threading.Lock()
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize the connection pool"""
        for _ in range(self.pool_size):
            self._pool.append(self.supabase_factory())

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        with self._lock:
            if self._pool:
                conn = self._pool.pop()
            else:
                # Create new connection if pool is empty
                conn = self.supabase_factory()

        try:
            yield conn
        finally:
            with self._lock:
                if len(self._pool) < self.pool_size:
                    self._pool.append(conn)

class AdvancedDatabaseOptimizer:
    """Advanced database optimizer with batching, parallel processing, and caching"""

    def __init__(self, supabase_client, config: QueryConfig = None):
        self.supabase = supabase_client
        self.config = config or QueryConfig()
        self.cache = {}
        self.cache_timestamps = {}
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        self._lock = threading.Lock()

    def performance_monitor(self, operation_name: str):
        """Decorator to monitor performance of database operations"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    logger.info(f"{operation_name} completed in {execution_time:.3f}s")
                    return result
                except Exception as e:
                    execution_time = time.time() - start_time
                    logger.error(f"{operation_name} failed after {execution_time:.3f}s: {str(e)}")
                    raise
            return wrapper
        return decorator

    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        return f"{args}_{kwargs}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid"""
        if cache_key not in self.cache_timestamps:
            return False

        age = time.time() - self.cache_timestamps[cache_key]
        return age < self.config.cache_ttl

    def _cache_result(self, cache_key: str, result: Any):
        """Cache the result with timestamp"""
        with self._lock:
            self.cache[cache_key] = result
            self.cache_timestamps[cache_key] = time.time()

    @performance_monitor("Parallel Select Operations")
    def parallel_select_operations(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute multiple SELECT operations in parallel

        Args:
            operations: List of operation configs with keys:
                - table: table name
                - select_fields: fields to select (default: '*')
                - filters: dict of field->value filters
                - limit: optional limit
                - order_by: optional ordering
                - operation_id: unique identifier for this operation

        Returns:
            Dict mapping operation_id to results
        """
        def execute_select(operation):
            try:
                table_name = operation['table']
                select_fields = operation.get('select_fields', '*')
                filters = operation.get('filters', {})
                limit = operation.get('limit')
                order_by = operation.get('order_by')
                operation_id = operation.get('operation_id', f"op_{id(operation)}")

                # Build query
                query = self.supabase.table(table_name).select(select_fields)

                # Apply filters
                for field, value in filters.items():
                    if isinstance(value, list):
                        query = query.in_(field, value)
                    else:
                        query = query.eq(field, value)

                # Apply ordering
                if order_by:
                    if isinstance(order_by, dict):
                        query = query.order(order_by['field'], desc=order_by.get('desc', False))
                    else:
                        query = query.order(order_by)

                # Apply limit
                if limit:
                    query = query.limit(limit)

                result = query.execute()
                return operation_id, result.data

            except Exception as e:
                logger.error(f"Error in parallel select operation {operation.get('operation_id', 'unknown')}: {e}")
                return operation.get('operation_id', f"op_{id(operation)}"), None

        # Execute operations in parallel
        futures = [self._executor.submit(execute_select, op) for op in operations]
        results = {}

        for future in as_completed(futures, timeout=self.config.timeout_seconds):
            try:
                operation_id, data = future.result()
                results[operation_id] = data
            except Exception as e:
                logger.error(f"Future execution error: {e}")

        return results

    @performance_monitor("Batch Insert Operations")
    def optimized_batch_insert(self, table_name: str, records: List[Dict[str, Any]],
                             batch_size: int = None) -> Dict[str, Any]:
        """
        Optimized batch insert with automatic batching and error handling
        """
        batch_size = batch_size or self.config.batch_size
        successful = 0
        failed = 0
        errors = []

        # Process in smaller batches
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]

            try:
                # Try bulk insert first
                result = self.supabase.table(table_name).insert(batch).execute()
                successful += len(batch)
                logger.info(f"Batch inserted {len(batch)} records to {table_name}")

            except Exception as e:
                logger.warning(f"Batch insert failed for {table_name}, trying individual inserts: {e}")

                # Fallback to individual inserts
                for record in batch:
                    try:
                        self.supabase.table(table_name).insert(record).execute()
                        successful += 1
                    except Exception as individual_error:
                        failed += 1
                        errors.append({
                            'record': record,
                            'error': str(individual_error)
                        })

            # Small delay between batches to avoid overwhelming the database
            if i + batch_size < len(records):
                time.sleep(0.1)

        return {
            'successful': successful,
            'failed': failed,
            'errors': errors,
            'total_processed': len(records)
        }

    @performance_monitor("Batch Update Operations")
    def optimized_batch_update(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Optimized batch update operations

        Args:
            updates: List of update configs with keys:
                - table: table name
                - data: update data
                - filters: dict of field->value filters for WHERE clause
                - update_id: unique identifier
        """
        def execute_update(update_config):
            try:
                table_name = update_config['table']
                update_data = update_config['data']
                filters = update_config['filters']
                update_id = update_config.get('update_id', f"update_{id(update_config)}")

                # Build update query
                query = self.supabase.table(table_name).update(update_data)

                # Apply filters
                for field, value in filters.items():
                    query = query.eq(field, value)

                result = query.execute()
                return update_id, True, result.data

            except Exception as e:
                logger.error(f"Error in batch update {update_config.get('update_id', 'unknown')}: {e}")
                return update_config.get('update_id', f"update_{id(update_config)}"), False, str(e)

        # Execute updates in parallel
        futures = [self._executor.submit(execute_update, update) for update in updates]
        results = {
            'successful': 0,
            'failed': 0,
            'details': {}
        }

        for future in as_completed(futures, timeout=self.config.timeout_seconds):
            try:
                update_id, success, data = future.result()
                if success:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                results['details'][update_id] = {'success': success, 'data': data}
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Future execution error in batch update: {e}")

        return results

    @performance_monitor("Optimized Dashboard Query")
    def get_dashboard_data_optimized(self, user_type: str, user_name: str,
                                   filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Optimized dashboard data loading with parallel queries and caching
        """
        cache_key = self._get_cache_key(user_type, user_name, json.dumps(filters or {}, sort_keys=True))

        # Check cache first
        if self._is_cache_valid(cache_key):
            logger.info(f"Returning cached dashboard data for {user_type}:{user_name}")
            return self.cache[cache_key]

        # Prepare parallel operations based on user type
        operations = []

        if user_type == 'cre':
            # CRE dashboard operations
            operations = [
                {
                    'operation_id': 'leads',
                    'table': 'lead_master',
                    'select_fields': 'uid, customer_name, customer_mobile_number, source, lead_status, final_status, follow_up_date, created_at',
                    'filters': {'cre_name': user_name},
                    'limit': 1000,
                    'order_by': {'field': 'created_at', 'desc': True}
                },
                {
                    'operation_id': 'call_attempts',
                    'table': 'cre_call_attempts',
                    'select_fields': 'lead_uid, call_no, lead_status, created_at',
                    'filters': {'cre_name': user_name},
                    'limit': 500
                }
            ]
        elif user_type == 'ps':
            # PS dashboard operations
            operations = [
                {
                    'operation_id': 'ps_leads',
                    'table': 'ps_followup_master',
                    'select_fields': 'lead_uid, customer_name, customer_mobile_number, source, lead_status, final_status, follow_up_date, created_at',
                    'filters': {'ps_name': user_name},
                    'limit': 1000,
                    'order_by': {'field': 'created_at', 'desc': True}
                },
                {
                    'operation_id': 'ps_calls',
                    'table': 'ps_call_attempts',
                    'select_fields': 'lead_uid, call_no, lead_status, created_at',
                    'filters': {'ps_name': user_name},
                    'limit': 500
                }
            ]

        # Apply additional filters
        if filters:
            for operation in operations:
                if filters.get('final_status'):
                    operation['filters']['final_status'] = filters['final_status']
                if filters.get('date_range'):
                    start_date, end_date = filters['date_range']
                    # Add date range filtering logic here

        # Execute parallel operations
        results = self.parallel_select_operations(operations)

        # Process and combine results
        dashboard_data = {
            'user_type': user_type,
            'user_name': user_name,
            'data': results,
            'generated_at': datetime.now().isoformat(),
            'cache_key': cache_key
        }

        # Cache the results
        self._cache_result(cache_key, dashboard_data)

        return dashboard_data

    @performance_monitor("Duplicate Check Optimization")
    def optimized_duplicate_check(self, phone_numbers: List[str],
                                source_data: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Optimized duplicate checking using batch operations and intelligent querying
        """
        if not phone_numbers:
            return {'duplicates': {}, 'new_leads': source_data}

        # Batch check multiple tables in parallel
        operations = [
            {
                'operation_id': 'lead_master_check',
                'table': 'lead_master',
                'select_fields': 'uid, customer_mobile_number, source, sub_source',
                'filters': {'customer_mobile_number': phone_numbers}
            },
            {
                'operation_id': 'duplicate_leads_check',
                'table': 'duplicate_leads',
                'select_fields': 'uid, customer_mobile_number, source1, sub_source1, source2, sub_source2, source3, sub_source3',
                'filters': {'customer_mobile_number': phone_numbers}
            }
        ]

        results = self.parallel_select_operations(operations)

        # Process duplicate results
        lead_master_data = results.get('lead_master_check', []) or []
        duplicate_leads_data = results.get('duplicate_leads_check', []) or []

        # Build duplicate map
        duplicates = {}
        for record in lead_master_data:
            phone = record['customer_mobile_number']
            if phone not in duplicates:
                duplicates[phone] = []
            duplicates[phone].append({
                'table': 'lead_master',
                'uid': record['uid'],
                'source': record['source'],
                'sub_source': record['sub_source']
            })

        for record in duplicate_leads_data:
            phone = record['customer_mobile_number']
            if phone not in duplicates:
                duplicates[phone] = []

            # Check all source slots
            for i in range(1, 4):  # Check first 3 source slots
                source = record.get(f'source{i}')
                sub_source = record.get(f'sub_source{i}')
                if source:
                    duplicates[phone].append({
                        'table': 'duplicate_leads',
                        'uid': record['uid'],
                        'source': source,
                        'sub_source': sub_source
                    })

        # Identify truly new leads
        new_leads = []
        for lead_data in source_data:
            phone = lead_data.get('customer_mobile_number')
            source = lead_data.get('source')
            sub_source = lead_data.get('sub_source')

            is_duplicate = False
            if phone in duplicates:
                for dup in duplicates[phone]:
                    if dup['source'] == source and dup['sub_source'] == sub_source:
                        is_duplicate = True
                        break

            if not is_duplicate:
                new_leads.append(lead_data)

        return {
            'duplicates': duplicates,
            'new_leads': new_leads,
            'duplicate_count': len([k for k, v in duplicates.items() if v]),
            'new_lead_count': len(new_leads)
        }

    @performance_monitor("Optimized Lead Transfer")
    def optimized_lead_transfer(self, transfer_operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Optimized lead transfer operations with batch processing

        Args:
            transfer_operations: List of transfer configs with keys:
                - lead_uid: UID of lead to transfer
                - from_user: current assigned user
                - to_user: new assigned user
                - user_type: 'cre' or 'ps'
                - transfer_reason: optional reason
        """
        # Group operations by type for better batching
        cre_transfers = []
        ps_transfers = []

        for op in transfer_operations:
            if op['user_type'] == 'cre':
                cre_transfers.append(op)
            elif op['user_type'] == 'ps':
                ps_transfers.append(op)

        # Prepare batch updates
        batch_updates = []

        # CRE transfers
        for transfer in cre_transfers:
            batch_updates.append({
                'update_id': f"cre_transfer_{transfer['lead_uid']}",
                'table': 'lead_master',
                'data': {
                    'cre_name': transfer['to_user'],
                    'updated_at': datetime.now().isoformat(),
                    'transfer_reason': transfer.get('transfer_reason', 'Admin Transfer')
                },
                'filters': {'uid': transfer['lead_uid']}
            })

        # PS transfers
        for transfer in ps_transfers:
            batch_updates.append({
                'update_id': f"ps_transfer_{transfer['lead_uid']}",
                'table': 'ps_followup_master',
                'data': {
                    'ps_name': transfer['to_user'],
                    'updated_at': datetime.now().isoformat(),
                    'transfer_reason': transfer.get('transfer_reason', 'Admin Transfer')
                },
                'filters': {'lead_uid': transfer['lead_uid']}
            })

            # Also update lead_master
            batch_updates.append({
                'update_id': f"ps_master_transfer_{transfer['lead_uid']}",
                'table': 'lead_master',
                'data': {
                    'ps_name': transfer['to_user'],
                    'updated_at': datetime.now().isoformat()
                },
                'filters': {'uid': transfer['lead_uid']}
            })

        # Execute batch updates
        results = self.optimized_batch_update(batch_updates)

        return {
            'total_transfers': len(transfer_operations),
            'successful_updates': results['successful'],
            'failed_updates': results['failed'],
            'cre_transfers': len(cre_transfers),
            'ps_transfers': len(ps_transfers),
            'details': results['details']
        }

    def clear_cache(self):
        """Clear all cached data"""
        with self._lock:
            self.cache.clear()
            self.cache_timestamps.clear()
        logger.info("Cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            valid_entries = 0
            for key in self.cache_timestamps:
                if self._is_cache_valid(key):
                    valid_entries += 1

            return {
                'total_entries': len(self.cache),
                'valid_entries': valid_entries,
                'expired_entries': len(self.cache) - valid_entries,
                'cache_hit_ratio': valid_entries / len(self.cache) if self.cache else 0
            }

    def cleanup(self):
        """Cleanup resources"""
        self._executor.shutdown(wait=True)
        self.clear_cache()

# Factory function for easy integration
def create_database_optimizer(supabase_client, config: QueryConfig = None):
    """Factory function to create database optimizer instance"""
    return AdvancedDatabaseOptimizer(supabase_client, config)

# Example usage and integration helpers
class DatabaseOptimizationIntegrator:
    """Helper class to integrate database optimizations into existing codebase"""

    def __init__(self, supabase_client):
        self.optimizer = create_database_optimizer(supabase_client)
        self.original_client = supabase_client

    def replace_sequential_selects_with_parallel(self, table_queries: List[Dict[str, Any]]):
        """Replace multiple sequential SELECT operations with parallel execution"""
        return self.optimizer.parallel_select_operations(table_queries)

    def optimize_dashboard_endpoint(self, user_type: str, user_name: str, filters: Dict = None):
        """Drop-in replacement for dashboard data loading"""
        return self.optimizer.get_dashboard_data_optimized(user_type, user_name, filters)

    def optimize_bulk_operations(self, operation_type: str, data: List[Dict[str, Any]], **kwargs):
        """Optimize bulk database operations"""
        if operation_type == 'insert':
            table_name = kwargs.get('table_name')
            return self.optimizer.optimized_batch_insert(table_name, data)
        elif operation_type == 'update':
            return self.optimizer.optimized_batch_update(data)
        else:
            raise ValueError(f"Unsupported operation type: {operation_type}")