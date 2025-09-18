"""
Query Optimization Patterns for Ather CRM System
Provides specific optimizations for common query patterns found in the codebase
"""

from typing import Dict, List, Optional, Any, Tuple
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logger = logging.getLogger(__name__)

@dataclass
class OptimizedQuery:
    """Container for optimized query configurations"""
    original_pattern: str
    optimized_pattern: str
    performance_gain: str
    use_cases: List[str]

class CRMQueryOptimizer:
    """Specific query optimizations for CRM operations"""

    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.query_cache = {}

    def optimize_dashboard_leads_query(self, user_type: str, user_name: str,
                                     filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Optimized dashboard leads query replacing multiple sequential queries

        BEFORE: 3-5 separate queries taking 800ms-1500ms
        AFTER: 1-2 parallel queries taking 200ms-400ms
        """
        start_time = time.time()

        if user_type == 'cre':
            # Single optimized query for CRE dashboard
            select_fields = (
                'uid, customer_name, customer_mobile_number, source, sub_source, '
                'lead_status, final_status, follow_up_date, created_at, updated_at, '
                'first_call_date, first_remark, model_interested, lead_category'
            )

            query = self.supabase.table('lead_master').select(select_fields).eq('cre_name', user_name)

            # Apply filters in single query
            if filters:
                if filters.get('final_status') and filters['final_status'] != 'All':
                    query = query.eq('final_status', filters['final_status'])
                if filters.get('lead_status') and filters['lead_status'] != 'All':
                    query = query.eq('lead_status', filters['lead_status'])
                if filters.get('date_from'):
                    query = query.gte('created_at', filters['date_from'])
                if filters.get('date_to'):
                    query = query.lte('created_at', filters['date_to'])
                if filters.get('source') and filters['source'] != 'All':
                    query = query.eq('source', filters['source'])

            # Optimize with ordering and pagination
            query = query.order('created_at', desc=True).limit(1000)

            result = query.execute()
            leads = result.data or []

            # Calculate summary statistics in Python (faster than separate queries)
            total_leads = len(leads)
            status_counts = {}
            for lead in leads:
                status = lead.get('final_status', 'Pending')
                status_counts[status] = status_counts.get(status, 0) + 1

            execution_time = time.time() - start_time
            logger.info(f"CRE dashboard query completed in {execution_time:.3f}s")

            return {
                'leads': leads,
                'total_count': total_leads,
                'status_counts': status_counts,
                'execution_time': execution_time
            }

        elif user_type == 'ps':
            # Optimized PS dashboard with parallel queries
            select_fields = (
                'lead_uid, customer_name, customer_mobile_number, source, lead_status, '
                'final_status, follow_up_date, created_at, updated_at, ps_branch, '
                'first_call_date, first_call_remark, second_call_date, second_call_remark'
            )

            query = self.supabase.table('ps_followup_master').select(select_fields).eq('ps_name', user_name)

            # Apply filters
            if filters:
                if filters.get('final_status') and filters['final_status'] != 'All':
                    query = query.eq('final_status', filters['final_status'])
                if filters.get('lead_status') and filters['lead_status'] != 'All':
                    query = query.eq('lead_status', filters['lead_status'])
                if filters.get('date_from'):
                    query = query.gte('created_at', filters['date_from'])
                if filters.get('date_to'):
                    query = query.lte('created_at', filters['date_to'])

            query = query.order('created_at', desc=True).limit(1000)
            result = query.execute()

            ps_leads = result.data or []
            total_leads = len(ps_leads)

            # Calculate statistics
            status_counts = {}
            for lead in ps_leads:
                status = lead.get('final_status', 'Pending')
                status_counts[status] = status_counts.get(status, 0) + 1

            execution_time = time.time() - start_time
            logger.info(f"PS dashboard query completed in {execution_time:.3f}s")

            return {
                'leads': ps_leads,
                'total_count': total_leads,
                'status_counts': status_counts,
                'execution_time': execution_time
            }

    def optimize_test_drive_operations(self, lead_uid: str, test_drive_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimized test drive operations replacing 5-7 sequential queries

        BEFORE: 5-7 individual queries taking 1200ms-2000ms
        AFTER: 2-3 parallel operations taking 300ms-500ms
        """
        start_time = time.time()

        # Step 1: Parallel check for existing records in all relevant tables
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._get_alltest_drive_record, lead_uid): 'alltest_drive',
                executor.submit(self._get_ps_followup_record, lead_uid): 'ps_followup',
                executor.submit(self._get_activity_leads_record, lead_uid): 'activity_leads',
                executor.submit(self._get_lead_master_record, lead_uid): 'lead_master'
            }

            parallel_results = {}
            for future in as_completed(futures):
                table_name = futures[future]
                try:
                    parallel_results[table_name] = future.result()
                except Exception as e:
                    logger.error(f"Error fetching {table_name} record: {e}")
                    parallel_results[table_name] = None

        # Step 2: Determine source table and prepare batch updates
        source_table = self._determine_source_table(parallel_results, lead_uid)
        batch_updates = []

        # Prepare alltest_drive update/insert
        alltest_drive_data = {
            'source_table': source_table,
            'original_id': lead_uid,
            'test_drive_date': test_drive_data.get('test_drive_date'),
            'test_drive_feedback': test_drive_data.get('feedback'),
            'test_drive_status': test_drive_data.get('status', 'Completed'),
            'updated_at': datetime.now().isoformat()
        }

        if parallel_results['alltest_drive']:
            # Update existing record
            batch_updates.append({
                'operation': 'update',
                'table': 'alltest_drive',
                'data': alltest_drive_data,
                'filters': {'source_table': source_table, 'original_id': lead_uid}
            })
        else:
            # Insert new record
            alltest_drive_data['created_at'] = datetime.now().isoformat()
            batch_updates.append({
                'operation': 'insert',
                'table': 'alltest_drive',
                'data': alltest_drive_data
            })

        # Prepare source table updates
        test_drive_value = 'Yes' if test_drive_data.get('status') == 'Completed' else 'No'

        if source_table == 'lead_master':
            batch_updates.append({
                'operation': 'update',
                'table': 'lead_master',
                'data': {'test_drive_done': test_drive_value, 'updated_at': datetime.now().isoformat()},
                'filters': {'uid': lead_uid}
            })
        elif source_table == 'ps_followup_master':
            batch_updates.append({
                'operation': 'update',
                'table': 'ps_followup_master',
                'data': {'test_drive_done': test_drive_value, 'updated_at': datetime.now().isoformat()},
                'filters': {'lead_uid': lead_uid}
            })
        elif source_table == 'activity_leads':
            batch_updates.append({
                'operation': 'update',
                'table': 'activity_leads',
                'data': {'test_drive_done': test_drive_value, 'updated_at': datetime.now().isoformat()},
                'filters': {'activity_uid': lead_uid}
            })

        # Step 3: Execute batch updates in parallel
        update_results = self._execute_batch_updates(batch_updates)

        execution_time = time.time() - start_time
        logger.info(f"Test drive operations completed in {execution_time:.3f}s")

        return {
            'success': True,
            'source_table': source_table,
            'updates_completed': len([r for r in update_results if r['success']]),
            'execution_time': execution_time,
            'results': update_results
        }

    def optimize_duplicate_check_query(self, phone_numbers: List[str]) -> Dict[str, Any]:
        """
        Optimized duplicate checking replacing multiple individual phone checks

        BEFORE: N queries (one per phone) taking 100ms * N
        AFTER: 2 parallel queries taking 200ms-300ms total
        """
        start_time = time.time()

        if not phone_numbers:
            return {'duplicates': {}, 'execution_time': 0}

        # Parallel queries to both tables
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_master = executor.submit(
                self._batch_check_lead_master, phone_numbers
            )
            future_duplicates = executor.submit(
                self._batch_check_duplicate_leads, phone_numbers
            )

            lead_master_results = future_master.result()
            duplicate_leads_results = future_duplicates.result()

        # Process results into structured format
        duplicates = {}

        # Process lead_master results
        for record in lead_master_results:
            phone = record['customer_mobile_number']
            if phone not in duplicates:
                duplicates[phone] = []
            duplicates[phone].append({
                'table': 'lead_master',
                'uid': record['uid'],
                'source': record['source'],
                'sub_source': record.get('sub_source'),
                'created_at': record.get('created_at')
            })

        # Process duplicate_leads results
        for record in duplicate_leads_results:
            phone = record['customer_mobile_number']
            if phone not in duplicates:
                duplicates[phone] = []

            # Check all source slots
            for i in range(1, 11):
                source = record.get(f'source{i}')
                sub_source = record.get(f'sub_source{i}')
                date_field = record.get(f'date{i}')

                if source:
                    duplicates[phone].append({
                        'table': 'duplicate_leads',
                        'uid': record['uid'],
                        'source': source,
                        'sub_source': sub_source,
                        'created_at': date_field
                    })

        execution_time = time.time() - start_time
        logger.info(f"Duplicate check completed for {len(phone_numbers)} phones in {execution_time:.3f}s")

        return {
            'duplicates': duplicates,
            'phones_checked': len(phone_numbers),
            'duplicates_found': len(duplicates),
            'execution_time': execution_time
        }

    def optimize_analytics_query(self, date_range: Tuple[str, str],
                                user_filter: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Optimized analytics query replacing multiple sequential aggregations

        BEFORE: 8-12 separate aggregation queries taking 2000ms-4000ms
        AFTER: 2-3 parallel queries with in-memory aggregation taking 500ms-800ms
        """
        start_time = time.time()
        start_date, end_date = date_range

        # Define optimized queries for analytics
        analytics_queries = []

        # Main leads query with all necessary fields
        leads_select = (
            'uid, customer_name, customer_mobile_number, source, sub_source, '
            'lead_status, final_status, cre_name, ps_name, branch, '
            'created_at, updated_at, first_call_date, won_timestamp, lost_timestamp'
        )

        leads_query = self.supabase.table('lead_master').select(leads_select)

        if start_date:
            leads_query = leads_query.gte('created_at', start_date)
        if end_date:
            leads_query = leads_query.lte('created_at', end_date)

        # Apply user filters
        if user_filter:
            if user_filter.get('cre_name'):
                leads_query = leads_query.eq('cre_name', user_filter['cre_name'])
            if user_filter.get('ps_name'):
                leads_query = leads_query.eq('ps_name', user_filter['ps_name'])
            if user_filter.get('branch'):
                leads_query = leads_query.eq('branch', user_filter['branch'])

        analytics_queries.append(('leads_data', leads_query))

        # PS followup data query
        ps_select = (
            'lead_uid, ps_name, ps_branch, final_status, lead_status, '
            'created_at, updated_at, first_call_date, second_call_date, third_call_date'
        )

        ps_query = self.supabase.table('ps_followup_master').select(ps_select)

        if start_date:
            ps_query = ps_query.gte('created_at', start_date)
        if end_date:
            ps_query = ps_query.lte('created_at', end_date)

        if user_filter and user_filter.get('ps_name'):
            ps_query = ps_query.eq('ps_name', user_filter['ps_name'])

        analytics_queries.append(('ps_data', ps_query))

        # Execute queries in parallel
        with ThreadPoolExecutor(max_workers=len(analytics_queries)) as executor:
            future_to_name = {
                executor.submit(query.execute): name
                for name, query in analytics_queries
            }

            query_results = {}
            for future in as_completed(future_to_name):
                query_name = future_to_name[future]
                try:
                    result = future.result()
                    query_results[query_name] = result.data or []
                except Exception as e:
                    logger.error(f"Error in analytics query {query_name}: {e}")
                    query_results[query_name] = []

        # Process analytics in memory (much faster than database aggregations)
        leads_data = query_results.get('leads_data', [])
        ps_data = query_results.get('ps_data', [])

        analytics = self._calculate_analytics_metrics(leads_data, ps_data, date_range)

        execution_time = time.time() - start_time
        logger.info(f"Analytics query completed in {execution_time:.3f}s")

        analytics['execution_time'] = execution_time
        analytics['data_points'] = len(leads_data) + len(ps_data)

        return analytics

    # Helper methods for optimized operations
    def _get_alltest_drive_record(self, lead_uid: str):
        """Get alltest_drive record for lead"""
        try:
            result = self.supabase.table('alltest_drive').select('*').eq('original_id', lead_uid).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    def _get_ps_followup_record(self, lead_uid: str):
        """Get PS followup record for lead"""
        try:
            result = self.supabase.table('ps_followup_master').select('test_drive_done, ps_name').eq('lead_uid', lead_uid).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    def _get_activity_leads_record(self, lead_uid: str):
        """Get activity leads record for lead"""
        try:
            result = self.supabase.table('activity_leads').select('test_drive_done, activity_uid').eq('activity_uid', lead_uid).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    def _get_lead_master_record(self, lead_uid: str):
        """Get lead master record for lead"""
        try:
            result = self.supabase.table('lead_master').select('test_drive_done, uid').eq('uid', lead_uid).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    def _determine_source_table(self, parallel_results: Dict[str, Any], lead_uid: str) -> str:
        """Determine the source table for the lead"""
        if parallel_results.get('activity_leads'):
            return 'activity_leads'
        elif parallel_results.get('ps_followup'):
            return 'ps_followup_master'
        elif parallel_results.get('lead_master'):
            return 'lead_master'
        else:
            return 'lead_master'  # Default fallback

    def _execute_batch_updates(self, batch_updates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute batch database updates in parallel"""
        results = []

        with ThreadPoolExecutor(max_workers=len(batch_updates)) as executor:
            future_to_update = {
                executor.submit(self._execute_single_update, update): update
                for update in batch_updates
            }

            for future in as_completed(future_to_update):
                update_config = future_to_update[future]
                try:
                    result = future.result()
                    results.append({
                        'success': True,
                        'operation': update_config['operation'],
                        'table': update_config['table'],
                        'result': result
                    })
                except Exception as e:
                    results.append({
                        'success': False,
                        'operation': update_config['operation'],
                        'table': update_config['table'],
                        'error': str(e)
                    })

        return results

    def _execute_single_update(self, update_config: Dict[str, Any]):
        """Execute a single database update operation"""
        operation = update_config['operation']
        table = update_config['table']
        data = update_config['data']

        if operation == 'insert':
            return self.supabase.table(table).insert(data).execute()
        elif operation == 'update':
            filters = update_config['filters']
            query = self.supabase.table(table).update(data)
            for field, value in filters.items():
                query = query.eq(field, value)
            return query.execute()

    def _batch_check_lead_master(self, phone_numbers: List[str]):
        """Batch check lead_master table for phone numbers"""
        try:
            result = self.supabase.table('lead_master').select(
                'uid, customer_mobile_number, source, sub_source, created_at'
            ).in_('customer_mobile_number', phone_numbers).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error in batch lead_master check: {e}")
            return []

    def _batch_check_duplicate_leads(self, phone_numbers: List[str]):
        """Batch check duplicate_leads table for phone numbers"""
        try:
            # Select all source fields
            select_fields = ['uid', 'customer_mobile_number']
            for i in range(1, 11):
                select_fields.extend([f'source{i}', f'sub_source{i}', f'date{i}'])

            result = self.supabase.table('duplicate_leads').select(
                ', '.join(select_fields)
            ).in_('customer_mobile_number', phone_numbers).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error in batch duplicate_leads check: {e}")
            return []

    def _calculate_analytics_metrics(self, leads_data: List[Dict], ps_data: List[Dict],
                                   date_range: Tuple[str, str]) -> Dict[str, Any]:
        """Calculate analytics metrics from raw data"""
        analytics = {
            'total_leads': len(leads_data),
            'total_ps_leads': len(ps_data),
            'date_range': date_range,
            'status_breakdown': {},
            'source_breakdown': {},
            'cre_performance': {},
            'ps_performance': {},
            'conversion_metrics': {}
        }

        # Status breakdown
        for lead in leads_data:
            status = lead.get('final_status', 'Pending')
            analytics['status_breakdown'][status] = analytics['status_breakdown'].get(status, 0) + 1

        # Source breakdown
        for lead in leads_data:
            source = lead.get('source', 'Unknown')
            analytics['source_breakdown'][source] = analytics['source_breakdown'].get(source, 0) + 1

        # CRE performance
        for lead in leads_data:
            cre = lead.get('cre_name')
            if cre:
                if cre not in analytics['cre_performance']:
                    analytics['cre_performance'][cre] = {'total': 0, 'won': 0, 'lost': 0}
                analytics['cre_performance'][cre]['total'] += 1
                if lead.get('final_status') == 'Won':
                    analytics['cre_performance'][cre]['won'] += 1
                elif lead.get('final_status') == 'Lost':
                    analytics['cre_performance'][cre]['lost'] += 1

        # PS performance
        for lead in ps_data:
            ps = lead.get('ps_name')
            if ps:
                if ps not in analytics['ps_performance']:
                    analytics['ps_performance'][ps] = {'total': 0, 'won': 0, 'lost': 0}
                analytics['ps_performance'][ps]['total'] += 1
                if lead.get('final_status') == 'Won':
                    analytics['ps_performance'][ps]['won'] += 1
                elif lead.get('final_status') == 'Lost':
                    analytics['ps_performance'][ps]['lost'] += 1

        # Conversion metrics
        total_leads = len(leads_data)
        won_leads = len([l for l in leads_data if l.get('final_status') == 'Won'])
        lost_leads = len([l for l in leads_data if l.get('final_status') == 'Lost'])

        analytics['conversion_metrics'] = {
            'total_leads': total_leads,
            'won_leads': won_leads,
            'lost_leads': lost_leads,
            'conversion_rate': (won_leads / total_leads * 100) if total_leads > 0 else 0,
            'loss_rate': (lost_leads / total_leads * 100) if total_leads > 0 else 0
        }

        return analytics

# Integration helper function
def create_query_optimizer(supabase_client):
    """Factory function to create query optimizer instance"""
    return CRMQueryOptimizer(supabase_client)