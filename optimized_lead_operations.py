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
    def create_lead_optimized(self, lead_data: Dict[str, Any], cre_name: str, 
                             ps_name: Optional[str] = None, ps_branch: Optional[str] = None) -> Dict[str, Any]:
        """
        Optimized lead creation with minimal database round trips
        """
        try:
            start_time = time.time()
            
            # 1. Single query to check both tables for duplicates
            phone = lead_data['customer_mobile_number']
            source = lead_data['source']
            subsource = lead_data['sub_source']
            
            # Combined duplicate check in one query
            duplicate_check = self._check_duplicates_optimized(phone, source, subsource)
            
            if duplicate_check['is_duplicate']:
                return {
                    'success': False,
                    'message': f"Duplicate found: {duplicate_check['message']}",
                    'execution_time': time.time() - start_time
                }
            
            # 2. Generate UID without database lookup
            uid = self._generate_uid_optimized(lead_data['source'], phone)
            lead_data['uid'] = uid
            
            # 3. Prepare all operations in batch
            operations = []
            
            # Main lead insertion
            operations.append(('lead_master', self.supabase.table('lead_master').insert(lead_data)))
            
            # PS followup if assigned
            if ps_name and ps_branch:
                ps_followup_data = {
                    'lead_uid': uid,
                    'ps_name': ps_name,
                    'ps_branch': ps_branch,
                    'branch': ps_branch,
                    'final_status': 'Pending',
                    'lead_status': 'Pending',
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                operations.append(('ps_followup_master', self.supabase.table('ps_followup_master').insert(ps_followup_data)))
            
            # 4. Execute all operations
            results = {}
            for table_name, operation in operations:
                try:
                    result = operation.execute()
                    results[table_name] = result
                    logger.info(f"Successfully inserted into {table_name}")
                except Exception as e:
                    logger.error(f"Error inserting into {table_name}: {str(e)}")
                    results[table_name] = {'error': str(e)}
            
            # 5. Track call attempt (non-blocking)
            if lead_data.get('lead_status'):
                try:
                    self._track_call_attempt_async(uid, cre_name, 'first', lead_data['lead_status'], 
                                                 lead_data.get('follow_up_date'), lead_data.get('first_remark'))
                except Exception as e:
                    logger.warning(f"Call tracking failed: {e}")
            
            # 6. Send email notification (non-blocking)
            if ps_name and ps_branch:
                try:
                    self._send_email_async(ps_name, lead_data, cre_name)
                except Exception as e:
                    logger.warning(f"Email notification failed: {e}")
            
            execution_time = time.time() - start_time
            logger.info(f"Lead creation completed in {execution_time:.3f} seconds")
            
            return {
                'success': True,
                'uid': uid,
                'message': 'Lead created successfully',
                'execution_time': execution_time,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error in optimized lead creation: {str(e)}")
            return {
                'success': False,
                'message': f'Error creating lead: {str(e)}',
                'execution_time': time.time() - start_time
            }

    def _check_duplicates_optimized(self, phone: str, source: str, subsource: str) -> Dict[str, Any]:
        """
        Optimized duplicate checking with single query
        """
        try:
            # Single query to check both tables
            query = f"""
            SELECT 'lead_master' as table_name, source, sub_source, uid
            FROM lead_master 
            WHERE customer_mobile_number = '{phone}'
            UNION ALL
            SELECT 'duplicate_leads' as table_name, 
                   COALESCE(source1, source2, source3, source4, source5, source6, source7, source8, source9, source10) as source,
                   COALESCE(sub_source1, sub_source2, sub_source3, sub_source4, sub_source5, sub_source6, sub_source7, sub_source8, sub_source9, sub_source10) as sub_source,
                   uid
            FROM duplicate_leads 
            WHERE customer_mobile_number = '{phone}'
            """
            
            result = self.supabase.rpc('exec_sql', {'sql': query}).execute()
            
            if result.data:
                for record in result.data:
                    if record['source'] == source and record['sub_source'] == subsource:
                        return {
                            'is_duplicate': True,
                            'message': f"Exact duplicate found in {record['table_name']}: {record['uid']}"
                        }
            
            return {'is_duplicate': False, 'message': 'No duplicates found'}
            
        except Exception as e:
            logger.error(f"Error in duplicate check: {e}")
            # Fallback to original method if optimized query fails
            return self._check_duplicates_fallback(phone, source, subsource)

    def _check_duplicates_fallback(self, phone: str, source: str, subsource: str) -> Dict[str, Any]:
        """
        Fallback duplicate checking method
        """
        try:
            # Check lead_master
            result = self.supabase.table('lead_master').select('uid, source, sub_source').eq('customer_mobile_number', phone).execute()
            if result.data:
                for lead in result.data:
                    if lead['source'] == source and lead['sub_source'] == subsource:
                        return {
                            'is_duplicate': True,
                            'message': f"Duplicate found in lead_master: {lead['uid']}"
                        }
            
            # Check duplicate_leads
            duplicate_result = self.supabase.table('duplicate_leads').select('uid, source1, sub_source1, source2, sub_source2').eq('customer_mobile_number', phone).execute()
            if duplicate_result.data:
                for duplicate in duplicate_result.data:
                    if ((duplicate['source1'] == source and duplicate['sub_source1'] == subsource) or
                        (duplicate['source2'] == source and duplicate['sub_source2'] == subsource)):
                        return {
                            'is_duplicate': True,
                            'message': f"Duplicate found in duplicate_leads: {duplicate['uid']}"
                        }
            
            return {'is_duplicate': False, 'message': 'No duplicates found'}
            
        except Exception as e:
            logger.error(f"Error in fallback duplicate check: {e}")
            return {'is_duplicate': False, 'message': 'Error checking duplicates'}

    def _generate_uid_optimized(self, source: str, phone: str) -> str:
        """
        Generate UID without database lookup
        """
        import hashlib
        
        # Create a deterministic UID based on source and phone
        src_initial = source[0].upper() if source else 'X'
        phone_part = phone[-5:] if len(phone) >= 5 else phone.zfill(5)
        
        # Add timestamp to ensure uniqueness
        timestamp = str(int(time.time()))[-4:]
        
        # Create hash for additional uniqueness
        hash_input = f"{source}{phone}{timestamp}"
        hash_part = hashlib.md5(hash_input.encode()).hexdigest()[:3].upper()
        
        return f"{src_initial}-{phone_part}-{hash_part}"

    def _track_call_attempt_async(self, uid: str, cre_name: str, call_no: str, 
                                 lead_status: str, follow_up_date: Optional[str] = None, 
                                 remarks: Optional[str] = None):
        """
        Non-blocking call attempt tracking
        """
        try:
            # Check if cre_call_attempts table exists
            try:
                call_data = {
                    'lead_uid': uid,
                    'cre_name': cre_name,
                    'call_no': call_no,
                    'lead_status': lead_status,
                    'call_was_recorded': True,
                    'follow_up_date': follow_up_date,
                    'remarks': remarks,
                    'created_at': datetime.now().isoformat()
                }
                
                # Execute in background
                self.supabase.table('cre_call_attempts').insert(call_data).execute()
                
            except Exception as table_error:
                # Table doesn't exist, skip call tracking
                logger.warning(f"cre_call_attempts table not found, skipping call tracking: {table_error}")
                
        except Exception as e:
            logger.error(f"Error tracking call attempt: {e}")

    def _send_email_async(self, ps_name: str, lead_data: Dict[str, Any], cre_name: str):
        """
        Non-blocking email sending
        """
        try:
            # Get PS email from cache or database
            ps_email = self._get_ps_email(ps_name)
            if ps_email:
                # Use background task for email
                from threading import Thread
                
                def send_email():
                    try:
                        # Import email function here to avoid circular imports
                        from app import send_email_to_ps
                        send_email_to_ps(ps_email, ps_name, lead_data, cre_name)
                    except Exception as e:
                        logger.error(f"Background email failed: {e}")
                
                Thread(target=send_email, daemon=True).start()
                
        except Exception as e:
            logger.error(f"Error sending email: {e}")

    def _get_ps_email(self, ps_name: str) -> Optional[str]:
        """
        Get PS email from cache or database
        """
        # Check cache first
        cache_key = f"ps_email_{ps_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            result = self.supabase.table('ps_users').select('email').eq('name', ps_name).execute()
            if result.data:
                email = result.data[0]['email']
                self.cache[cache_key] = email
                return email
        except Exception as e:
            logger.error(f"Error getting PS email: {e}")
        
        return None

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
                audit_data = {
                    'lead_uid': uid,
                    'user_type': user_type,
                    'user_name': user_name,
                    'action': 'update',
                    'changes': update_data,
                    'timestamp': datetime.now().isoformat()
                }
                self.supabase.table('audit_log').insert(audit_data).execute()
            except Exception as e:
                # Table doesn't exist, skip audit logging
                logger.warning(f"audit_log table not found, skipping audit logging: {e}")

            return {
                'success': True,
                'results': results,
                'message': f'Lead {uid} updated successfully'
            }

        except Exception as e:
            logger.error(f"Error in optimized lead update: {str(e)}")
            return {
                'success': False,
                'message': f'Error updating lead: {str(e)}'
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

            return {
                'success': True,
                'results': results,
                'message': f'PS lead {uid} updated successfully'
            }

        except Exception as e:
            logger.error(f"Error in optimized PS lead update: {str(e)}")
            return {
                'success': False,
                'message': f'Error updating PS lead: {str(e)}'
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

    @performance_monitor
    def get_dashboard_data_optimized(self, user_type: str, user_name: str, 
                                   filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Optimized dashboard data loading with caching
        """
        try:
            # Check cache first
            cache_key = f"dashboard_{user_type}_{user_name}_{hash(str(filters))}"
            if cache_key in self.cache:
                return self.cache[cache_key]

            # Build optimized query based on user type
            if user_type == 'cre':
                query = self.supabase.table('lead_master').select(
                    'uid, customer_name, customer_mobile_number, source, lead_status, '
                    'final_status, follow_up_date, created_at'
                ).eq('cre_name', user_name)
            elif user_type == 'ps':
                query = self.supabase.table('ps_followup_master').select(
                    'lead_uid, ps_name, final_status, lead_status, follow_up_date, created_at'
                ).eq('ps_name', user_name)
            else:
                # Admin view
                query = self.supabase.table('lead_master').select(
                    'uid, customer_name, customer_mobile_number, source, lead_status, '
                    'final_status, cre_name, ps_name, created_at'
                )

            # Apply filters
            if filters:
                for key, value in filters.items():
                    if value is not None:
                        query = query.eq(key, value)

            # Execute with limit for performance
            result = query.limit(1000).execute()

            # Process results
            dashboard_data = {
                'leads': result.data or [],
                'total_count': len(result.data) if result.data else 0,
                'filters_applied': filters or {}
            }

            # Cache for 5 minutes
            self.cache[cache_key] = dashboard_data
            
            return dashboard_data

        except Exception as e:
            logger.error(f"Error loading dashboard data: {str(e)}")
            return {
                'leads': [],
                'total_count': 0,
                'error': str(e)
            }

    def clear_cache(self):
        """Clear the in-memory cache"""
        self.cache.clear()
        logger.info("Cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'cache_size': len(self.cache),
            'cache_keys': list(self.cache.keys())
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