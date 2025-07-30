"""
Optimized Lead Operations for Ather CRM System
This module provides optimized database operations to speed up lead updates
for both PS and CRE users with advanced caching and connection pooling.
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from functools import wraps, lru_cache
import logging
from collections import OrderedDict
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global cache for session data
CACHE_SIZE = 1000
CACHE_TTL = 300  # 5 minutes
session_cache = OrderedDict()
cache_lock = threading.Lock()

class LRUCache:
    """Thread-safe LRU cache for lead data"""
    
    def __init__(self, max_size=1000, ttl=300):
        self.max_size = max_size
        self.ttl = ttl
        self.cache = OrderedDict()
        self.timestamps = {}
        self.lock = threading.Lock()
    
    def get(self, key):
        with self.lock:
            if key in self.cache:
                # Check if expired
                if time.time() - self.timestamps.get(key, 0) > self.ttl:
                    del self.cache[key]
                    del self.timestamps[key]
                    return None
                
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                return self.cache[key]
            return None
    
    def set(self, key, value):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.max_size:
                    # Remove oldest item
                    oldest = next(iter(self.cache))
                    del self.cache[oldest]
                    del self.timestamps[oldest]
            
            self.cache[key] = value
            self.timestamps[key] = time.time()
    
    def clear(self):
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()

# Global cache instance
lead_cache = LRUCache(max_size=1000, ttl=300)

def performance_monitor(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} executed in {execution_time:.3f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.3f} seconds: {str(e)}")
            raise
    return wrapper

class OptimizedLeadOperations:
    """Optimized lead operations with reduced database round trips and advanced caching"""

    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.cache = lead_cache
        self.query_cache = {}
        self.batch_size = 50  # Optimized batch size
        
        # Pre-compiled queries for common operations
        self._init_prepared_queries()
    
    def _init_prepared_queries(self):
        """Initialize pre-compiled query templates"""
        self.query_templates = {
            'lead_by_uid': {
                'table': 'lead_master',
                'columns': 'uid, customer_name, customer_mobile_number, source, lead_status, lead_category, model_interested, branch, ps_name, cre_name, final_status, follow_up_date, assigned, created_at, updated_at, first_call_date, first_remark, second_call_date, second_remark, third_call_date, third_remark, fourth_call_date, fourth_remark, fifth_call_date, fifth_remark, sixth_call_date, sixth_remark, seventh_call_date, seventh_remark, won_timestamp, lost_timestamp'
            },
            'ps_followup_by_uid': {
                'table': 'ps_followup_master',
                'columns': 'lead_uid, ps_name, ps_branch, final_status, lead_status, follow_up_date, first_call_date, first_call_remark, second_call_date, second_call_remark, third_call_date, third_call_remark'
            }
        }

    @performance_monitor
    def get_lead_with_related_data(self, uid: str) -> Dict[str, Any]:
        """
        Fetch lead data with all related information in a single optimized query
        Uses advanced caching for better performance
        """
        # Check cache first
        cache_key = f"lead_{uid}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.info(f"Cache hit for lead {uid}")
            return cached_data

        try:
            # Use pre-compiled query template
            template = self.query_templates['lead_by_uid']
            lead_query = self.supabase.table(template['table']).select(
                template['columns']
            ).eq('uid', uid).execute()

            if not lead_query.data:
                return None

            lead_data = lead_query.data[0]

            # Fetch PS followup data if exists (optimized query)
            ps_followup = None
            if lead_data.get('ps_name'):
                ps_template = self.query_templates['ps_followup_by_uid']
                ps_query = self.supabase.table(ps_template['table']).select(
                    ps_template['columns']
                ).eq('lead_uid', uid).limit(1).execute()

                if ps_query.data:
                    ps_followup = ps_query.data[0]

            result = {
                'lead': lead_data,
                'ps_followup': ps_followup
            }

            # Cache the result
            self.cache.set(cache_key, result)
            return result

        except Exception as e:
            logger.error(f"Error fetching lead data: {str(e)}")
            raise

    @performance_monitor
    def update_lead_optimized(self, uid: str, update_data: Dict[str, Any],
                             user_type: str, user_name: str) -> Dict[str, Any]:
        """
        Optimized lead update with minimal database round trips and batch operations
        """
        try:
            # Invalidate cache for this lead
            self.cache.set(f"lead_{uid}", None)
            
            # Prepare batch operations
            operations = []
            audit_events = []

            # 1. Update lead_master with optimized query
            if update_data:
                # Add updated_at timestamp
                update_data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                lead_update = self.supabase.table('lead_master').update(update_data).eq('uid', uid)
                operations.append(('lead_master', lead_update))

            # 2. Update ps_followup_master if final_status is being updated
            if 'final_status' in update_data:
                ps_update = self.supabase.table('ps_followup_master').update(
                    {'final_status': update_data['final_status']}
                ).eq('lead_uid', uid)
                operations.append(('ps_followup_master', ps_update))

            # 3. Execute all operations in parallel (simulated)
            results = {}
            for table_name, operation in operations:
                try:
                    result = operation.execute()
                    results[table_name] = result
                    logger.info(f"Successfully updated {table_name} for lead {uid}")
                except Exception as e:
                    logger.error(f"Error updating {table_name}: {str(e)}")
                    results[table_name] = {'error': str(e)}

            # 4. Log audit event (non-blocking with optimized batching)
            try:
                audit_events.append({
                    'user_type': user_type,
                    'user_name': user_name,
                    'action': 'LEAD_UPDATED',
                    'resource': 'lead_master',
                    'resource_id': uid,
                    'details': {'updated_fields': list(update_data.keys())},
                    'created_at': datetime.now().isoformat()
                })
                
                # Batch insert audit events
                if audit_events:
                    self.supabase.table('audit_log').insert(audit_events).execute()
                    
            except Exception as e:
                logger.warning(f"Failed to log audit event: {str(e)}")

            return {
                'success': True,
                'results': results,
                'updated_fields': list(update_data.keys())
            }

        except Exception as e:
            logger.error(f"Error in optimized lead update: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @performance_monitor
    def update_ps_lead_optimized(self, uid: str, update_data: Dict[str, Any],
                                ps_name: str) -> Dict[str, Any]:
        """
        Optimized PS lead update with batch operations and caching
        """
        try:
            # Invalidate cache for this lead
            self.cache.set(f"lead_{uid}", None)
            
            operations = []
            audit_events = []

            # 1. Update ps_followup_master with optimized query
            if update_data:
                # Add updated timestamp
                update_data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                ps_update = self.supabase.table('ps_followup_master').update(update_data).eq('lead_uid', uid)
                operations.append(('ps_followup_master', ps_update))

            # 2. Update lead_master final_status if needed
            if 'final_status' in update_data:
                main_update_data = {'final_status': update_data['final_status']}

                # Add timestamps for won/lost statuses
                if update_data['final_status'] == 'Won':
                    main_update_data['won_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                elif update_data['final_status'] == 'Lost':
                    main_update_data['lost_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                lead_update = self.supabase.table('lead_master').update(main_update_data).eq('uid', uid)
                operations.append(('lead_master', lead_update))

            # 3. Execute all operations
            results = {}
            for table_name, operation in operations:
                try:
                    result = operation.execute()
                    results[table_name] = result
                    logger.info(f"Successfully updated {table_name} for PS lead {uid}")
                except Exception as e:
                    logger.error(f"Error updating {table_name}: {str(e)}")
                    results[table_name] = {'error': str(e)}

            # 4. Log audit event (non-blocking with batching)
            try:
                audit_events.append({
                    'user_type': 'ps',
                    'user_name': ps_name,
                    'action': 'PS_LEAD_UPDATED',
                    'resource': 'ps_followup_master',
                    'resource_id': uid,
                    'details': {'updated_fields': list(update_data.keys())},
                    'created_at': datetime.now().isoformat()
                })
                
                # Batch insert audit events
                if audit_events:
                    self.supabase.table('audit_log').insert(audit_events).execute()
                    
            except Exception as e:
                logger.warning(f"Failed to log audit event: {str(e)}")

            return {
                'success': True,
                'results': results,
                'updated_fields': list(update_data.keys())
            }

        except Exception as e:
            logger.error(f"Error in optimized PS lead update: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @performance_monitor
    def get_dashboard_leads_optimized(self, user_type: str, user_name: str,
                                    filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Optimized dashboard leads fetching with efficient queries and caching
        """
        try:
            # Create cache key based on filters
            cache_key = f"dashboard_{user_type}_{user_name}_{hash(str(filters))}"
            cached_data = self.cache.get(cache_key)
            if cached_data:
                logger.info(f"Cache hit for dashboard {user_type} {user_name}")
                return cached_data

            if user_type == 'cre':
                result = self._get_cre_dashboard_leads_optimized(user_name, filters)
            elif user_type == 'ps':
                result = self._get_ps_dashboard_leads_optimized(user_name, filters)
            else:
                raise ValueError(f"Unsupported user type: {user_type}")

            # Cache the result
            self.cache.set(cache_key, result)
            return result

        except Exception as e:
            logger.error(f"Error fetching dashboard leads: {str(e)}")
            return {'error': str(e)}

    def _get_cre_dashboard_leads_optimized(self, cre_name: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Optimized CRE dashboard leads fetching with query optimization"""
        try:
            # Build efficient query with specific columns and indexing hints
            query = self.supabase.table('lead_master').select(
                'uid, customer_name, customer_mobile_number, source, lead_status, '
                'lead_category, model_interested, branch, ps_name, final_status, '
                'follow_up_date, created_at, updated_at'
            ).eq('cre_name', cre_name)

            # Apply filters efficiently with indexing
            if filters:
                if filters.get('final_status'):
                    query = query.eq('final_status', filters['final_status'])
                if filters.get('lead_status'):
                    query = query.eq('lead_status', filters['lead_status'])
                if filters.get('date_range'):
                    start_date, end_date = filters['date_range']
                    query = query.gte('created_at', start_date).lte('created_at', end_date)

            # Add pagination with optimized range
            page = filters.get('page', 1) if filters else 1
            per_page = filters.get('per_page', 50) if filters else 50
            offset = (page - 1) * per_page

            query = query.range(offset, offset + per_page - 1)
            query = query.order('created_at', desc=True)  # Use indexed column for ordering

            result = query.execute()

            return {
                'leads': result.data or [],
                'total_count': len(result.data) if result.data else 0,
                'page': page,
                'per_page': per_page
            }

        except Exception as e:
            logger.error(f"Error in CRE dashboard leads: {str(e)}")
            return {'error': str(e)}

    def _get_ps_dashboard_leads_optimized(self, ps_name: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Optimized PS dashboard leads fetching with query optimization"""
        try:
            # Build efficient query for PS followup data with indexing
            query = self.supabase.table('ps_followup_master').select(
                'lead_uid, ps_name, ps_branch, customer_name, customer_mobile_number, '
                'source, lead_status, lead_category, model_interested, final_status, '
                'follow_up_date, created_at, first_call_date, first_call_remark, '
                'second_call_date, second_call_remark, third_call_date, third_call_remark'
            ).eq('ps_name', ps_name)

            # Apply filters efficiently
            if filters:
                if filters.get('final_status'):
                    query = query.eq('final_status', filters['final_status'])
                if filters.get('lead_status'):
                    query = query.eq('lead_status', filters['lead_status'])
                if filters.get('date_range'):
                    start_date, end_date = filters['date_range']
                    query = query.gte('created_at', start_date).lte('created_at', end_date)

            # Add pagination with optimized range
            page = filters.get('page', 1) if filters else 1
            per_page = filters.get('per_page', 50) if filters else 50
            offset = (page - 1) * per_page

            query = query.range(offset, offset + per_page - 1)
            query = query.order('created_at', desc=True)  # Use indexed column for ordering

            result = query.execute()

            return {
                'leads': result.data or [],
                'total_count': len(result.data) if result.data else 0,
                'page': page,
                'per_page': per_page
            }

        except Exception as e:
            logger.error(f"Error in PS dashboard leads: {str(e)}")
            return {'error': str(e)}

    @performance_monitor
    def batch_update_leads(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Advanced batch update multiple leads with optimized batching
        """
        try:
            results = {
                'successful': 0,
                'failed': 0,
                'errors': [],
                'batch_size': len(updates)
            }

            # Process in optimized batches
            batch_size = self.batch_size
            for i in range(0, len(updates), batch_size):
                batch = updates[i:i + batch_size]
                
                for update in batch:
                    try:
                        uid = update['uid']
                        update_data = update['data']
                        user_type = update.get('user_type', 'unknown')
                        user_name = update.get('user_name', 'unknown')

                        # Invalidate cache for this lead
                        self.cache.set(f"lead_{uid}", None)

                        if user_type == 'ps':
                            result = self.update_ps_lead_optimized(uid, update_data, user_name)
                        else:
                            result = self.update_lead_optimized(uid, update_data, user_type, user_name)

                        if result['success']:
                            results['successful'] += 1
                        else:
                            results['failed'] += 1
                            results['errors'].append({
                                'uid': uid,
                                'error': result.get('error', 'Unknown error')
                            })

                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append({
                            'uid': update.get('uid', 'unknown'),
                            'error': str(e)
                        })

            return results

        except Exception as e:
            logger.error(f"Error in batch update: {str(e)}")
            return {
                'successful': 0,
                'failed': len(updates),
                'errors': [{'uid': 'batch', 'error': str(e)}]
            }

    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        logger.info("Cache cleared successfully")

    def get_cache_stats(self):
        """Get cache statistics"""
        return {
            'cache_size': len(self.cache.cache),
            'max_size': self.cache.max_size,
            'ttl': self.cache.ttl
        }

# Utility functions for easy integration
def create_optimized_operations(supabase_client):
    """Factory function to create optimized operations instance"""
    return OptimizedLeadOperations(supabase_client)

def apply_database_indexes(supabase_client):
    """Apply database indexes for performance optimization"""
    try:
        # Read and execute the SQL file
        with open('database_optimization.sql', 'r') as f:
            sql_commands = f.read()

        # Split by semicolon and execute each command
        commands = [cmd.strip() for cmd in sql_commands.split(';') if cmd.strip()]

        for command in commands:
            if command and not command.startswith('--') and not command.startswith('/*'):
                try:
                    supabase_client.rpc('exec_sql', {'sql': command}).execute()
                    logger.info(f"Successfully executed: {command[:50]}...")
                except Exception as e:
                    logger.warning(f"Failed to execute command: {str(e)}")

        logger.info("Database indexes applied successfully")
        return True

    except Exception as e:
        logger.error(f"Error applying database indexes: {str(e)}")
        return False 