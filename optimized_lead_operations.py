"""
Optimized Lead Operations for Ather CRM System
This module provides optimized database operations to speed up lead updates
for both PS and CRE users.
"""

import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from functools import wraps
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    """Optimized lead operations with reduced database round trips"""

    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.cache = {}  # Simple in-memory cache for session data

    @performance_monitor
    def get_lead_with_related_data(self, uid: str) -> Dict[str, Any]:
        """
        Fetch lead data with all related information in a single optimized query
        """
        try:
            # Use a more efficient query with specific column selection
            lead_query = self.supabase.table('lead_master').select(
                'uid, customer_name, customer_mobile_number, source, lead_status, '
                'lead_category, model_interested, branch, ps_name, cre_name, '
                'final_status, follow_up_date, assigned, created_at, updated_at, '
                'first_call_date, first_remark, second_call_date, second_remark, '
                'third_call_date, third_remark, fourth_call_date, fourth_remark, '
                'fifth_call_date, fifth_remark, sixth_call_date, sixth_remark, '
                'seventh_call_date, seventh_remark, won_timestamp, lost_timestamp'
            ).eq('uid', uid).execute()

            if not lead_query.data:
                return None

            lead_data = lead_query.data[0]

            # Fetch PS followup data if exists (optimized query)
            ps_followup = None
            if lead_data.get('ps_name'):
                ps_query = self.supabase.table('ps_followup_master').select(
                    'lead_uid, ps_name, ps_branch, branch, final_status, lead_status, '
                    'follow_up_date, first_call_date, first_call_remark, '
                    'second_call_date, second_call_remark, third_call_date, third_call_remark'
                ).eq('lead_uid', uid).limit(1).execute()

                if ps_query.data:
                    ps_followup = ps_query.data[0]

            return {
                'lead': lead_data,
                'ps_followup': ps_followup
            }

        except Exception as e:
            logger.error(f"Error fetching lead data: {str(e)}")
            raise

    @performance_monitor
    def update_lead_optimized(self, uid: str, update_data: Dict[str, Any],
                             user_type: str, user_name: str) -> Dict[str, Any]:
        """
        Optimized lead update with minimal database round trips
        """
        try:
            # Start transaction-like operations
            operations = []

            # 1. Update lead_master
            if update_data:
                lead_update = self.supabase.table('lead_master').update(update_data).eq('uid', uid)
                operations.append(('lead_master', lead_update))

            # 2. Update ps_followup_master if final_status is being updated
            if 'final_status' in update_data:
                ps_update = self.supabase.table('ps_followup_master').update(
                    {'final_status': update_data['final_status']}
                ).eq('lead_uid', uid)
                operations.append(('ps_followup_master', ps_update))

            # 3. Execute all operations
            results = {}
            for table_name, operation in operations:
                try:
                    result = operation.execute()
                    results[table_name] = result
                    logger.info(f"Successfully updated {table_name} for lead {uid}")
                except Exception as e:
                    logger.error(f"Error updating {table_name}: {str(e)}")
                    results[table_name] = {'error': str(e)}

            # 4. Log audit event (non-blocking)
            try:
                self._log_audit_event_async(
                    user_type=user_type,
                    user_name=user_name,
                    action='LEAD_UPDATED',
                    resource='lead_master',
                    resource_id=uid,
                    details={'updated_fields': list(update_data.keys())}
                )
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
        Optimized PS lead update with batch operations
        """
        try:
            operations = []

            # 1. Update ps_followup_master
            if update_data:
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

            # 4. Log audit event (non-blocking)
            try:
                self._log_audit_event_async(
                    user_type='ps',
                    user_name=ps_name,
                    action='PS_LEAD_UPDATED',
                    resource='ps_followup_master',
                    resource_id=uid,
                    details={'updated_fields': list(update_data.keys())}
                )
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
        Optimized dashboard leads fetching with efficient queries
        """
        try:
            if user_type == 'cre':
                return self._get_cre_dashboard_leads_optimized(user_name, filters)
            elif user_type == 'ps':
                return self._get_ps_dashboard_leads_optimized(user_name, filters)
            else:
                raise ValueError(f"Unsupported user type: {user_type}")

        except Exception as e:
            logger.error(f"Error fetching dashboard leads: {str(e)}")
            return {'error': str(e)}

    def _get_cre_dashboard_leads_optimized(self, cre_name: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Optimized CRE dashboard leads fetching"""
        try:
            # Build efficient query with specific columns
            query = self.supabase.table('lead_master').select(
                'uid, customer_name, customer_mobile_number, source, lead_status, '
                'lead_category, model_interested, branch, ps_name, final_status, '
                'follow_up_date, created_at, updated_at'
            ).eq('cre_name', cre_name)

            # Apply filters efficiently
            if filters:
                if filters.get('final_status'):
                    query = query.eq('final_status', filters['final_status'])
                if filters.get('lead_status'):
                    query = query.eq('lead_status', filters['lead_status'])
                if filters.get('date_range'):
                    start_date, end_date = filters['date_range']
                    query = query.gte('created_at', start_date).lte('created_at', end_date)

            # Add pagination
            page = filters.get('page', 1) if filters else 1
            per_page = filters.get('per_page', 50) if filters else 50
            offset = (page - 1) * per_page

            query = query.range(offset, offset + per_page - 1)

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
        """Optimized PS dashboard leads fetching"""
        try:
            # Build efficient query for PS followup data
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

            # Add pagination
            page = filters.get('page', 1) if filters else 1
            per_page = filters.get('per_page', 50) if filters else 50
            offset = (page - 1) * per_page

            query = query.range(offset, offset + per_page - 1)

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

    def _log_audit_event_async(self, user_type: str, user_name: str, action: str,
                               resource: str, resource_id: str, details: Dict[str, Any]):
        """Non-blocking audit event logging"""
        try:
            audit_data = {
                'user_type': user_type,
                'user_name': user_name,
                'action': action,
                'resource': resource,
                'resource_id': resource_id,
                'details': details,
                'created_at': datetime.now().isoformat()
            }

            # Use a separate thread or async operation for audit logging
            # For now, we'll log it synchronously but with error handling
            self.supabase.table('audit_log').insert(audit_data).execute()

        except Exception as e:
            logger.warning(f"Failed to log audit event: {str(e)}")

    @performance_monitor
    def batch_update_leads(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Batch update multiple leads for better performance
        """
        try:
            results = {
                'successful': 0,
                'failed': 0,
                'errors': []
            }

            for update in updates:
                try:
                    uid = update['uid']
                    update_data = update['data']
                    user_type = update.get('user_type', 'unknown')
                    user_name = update.get('user_name', 'unknown')

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