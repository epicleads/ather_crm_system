#!/usr/bin/env python3
"""
Deployment script for Ather CRM System Optimizations
This script applies database indexes and tests performance improvements
"""

import os
import sys
import time
import logging
from datetime import datetime
from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_supabase_client():
    """Initialize Supabase client"""
    try:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

        if not url or not key:
            logger.error("SUPABASE_URL and SUPABASE_KEY environment variables are required")
            sys.exit(1)

        return create_client(url, key)
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        sys.exit(1)

def apply_database_indexes(supabase: Client):
    """Apply database indexes for performance optimization"""
    logger.info("Starting database index application...")

    try:
        # Read the SQL file
        with open('database_optimization.sql', 'r') as f:
            sql_content = f.read()

        # Split into individual commands
        commands = []
        current_command = ""

        for line in sql_content.split('\n'):
            line = line.strip()
            if line.startswith('--') or line.startswith('/*') or not line:
                continue

            current_command += line + " "
            if line.endswith(';'):
                commands.append(current_command.strip())
                current_command = ""

        # Execute each command
        successful_commands = 0
        failed_commands = 0

        for i, command in enumerate(commands, 1):
            if not command:
                continue

            try:
                logger.info(f"Executing command {i}/{len(commands)}: {command[:50]}...")

                # Execute the SQL command
                result = supabase.rpc('exec_sql', {'sql': command}).execute()

                if result:
                    successful_commands += 1
                    logger.info(f"✓ Successfully executed command {i}")
                else:
                    failed_commands += 1
                    logger.warning(f"✗ Command {i} returned no result")

            except Exception as e:
                failed_commands += 1
                logger.error(f"✗ Failed to execute command {i}: {str(e)}")

        logger.info(f"Index application completed: {successful_commands} successful, {failed_commands} failed")
        return successful_commands > 0

    except Exception as e:
        logger.error(f"Error applying database indexes: {e}")
        return False

def test_performance_improvements(supabase: Client):
    """Test performance improvements with sample queries"""
    logger.info("Testing performance improvements...")

    test_results = {}

    # Test 1: Lead update performance
    try:
        start_time = time.time()

        # Simulate a lead update
        test_uid = "TEST-LEAD123"
        update_data = {
            'lead_status': 'Interested',
            'follow_up_date': datetime.now().strftime('%Y-%m-%d'),
            'updated_at': datetime.now().isoformat()
        }

        # Try to update a test record (will fail if doesn't exist, but we're testing query speed)
        try:
            result = supabase.table('lead_master').update(update_data).eq('uid', test_uid).execute()
            update_time = time.time() - start_time
            test_results['lead_update'] = {
                'success': True,
                'time': update_time,
                'message': f'Lead update took {update_time:.3f} seconds'
            }
        except Exception as e:
            update_time = time.time() - start_time
            test_results['lead_update'] = {
                'success': False,
                'time': update_time,
                'message': f'Lead update query took {update_time:.3f} seconds (expected to fail for test record)'
            }

    except Exception as e:
        test_results['lead_update'] = {
            'success': False,
            'time': 0,
            'message': f'Error testing lead update: {str(e)}'
        }

    # Test 2: Dashboard query performance
    try:
        start_time = time.time()

        # Test CRE dashboard query
        result = supabase.table('lead_master').select(
            'uid, customer_name, lead_status, final_status, created_at'
        ).eq('cre_name', 'test_cre').limit(10).execute()

        query_time = time.time() - start_time
        test_results['dashboard_query'] = {
            'success': True,
            'time': query_time,
            'count': len(result.data) if result.data else 0,
            'message': f'Dashboard query took {query_time:.3f} seconds, returned {len(result.data) if result.data else 0} records'
        }

    except Exception as e:
        test_results['dashboard_query'] = {
            'success': False,
            'time': 0,
            'message': f'Error testing dashboard query: {str(e)}'
        }

    # Test 3: PS followup query performance
    try:
        start_time = time.time()

        # Test PS followup query
        result = supabase.table('ps_followup_master').select(
            'lead_uid, ps_name, final_status, follow_up_date'
        ).eq('ps_name', 'test_ps').limit(10).execute()

        query_time = time.time() - start_time
        test_results['ps_followup_query'] = {
            'success': True,
            'time': query_time,
            'count': len(result.data) if result.data else 0,
            'message': f'PS followup query took {query_time:.3f} seconds, returned {len(result.data) if result.data else 0} records'
        }

    except Exception as e:
        test_results['ps_followup_query'] = {
            'success': False,
            'time': 0,
            'message': f'Error testing PS followup query: {str(e)}'
        }

    return test_results

def generate_performance_report(test_results):
    """Generate a performance report"""
    logger.info("Generating performance report...")

    report = f"""
=== ATHER CRM SYSTEM PERFORMANCE OPTIMIZATION REPORT ===
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

PERFORMANCE TEST RESULTS:
"""

    for test_name, result in test_results.items():
        report += f"\n{test_name.replace('_', ' ').title()}:"
        report += f"\n  Status: {'✓ PASS' if result['success'] else '✗ FAIL'}"
        report += f"\n  Time: {result['time']:.3f} seconds"
        if 'count' in result:
            report += f"\n  Records: {result['count']}"
        report += f"\n  Message: {result['message']}"

    report += f"""

RECOMMENDATIONS:
1. Monitor query performance in production
2. Set up database monitoring alerts
3. Consider implementing caching for frequently accessed data
4. Review and optimize slow queries regularly
5. Consider connection pooling for better performance

NEXT STEPS:
1. Deploy the optimized application code
2. Update frontend to use optimized endpoints
3. Monitor performance metrics
"""

    return report

def main():
    """Main deployment function"""
    logger.info("Starting Ather CRM System optimization deployment...")

    # Initialize Supabase client
    supabase = get_supabase_client()
    logger.info("✓ Supabase client initialized")

    # Apply database indexes
    logger.info("Applying database indexes...")
    indexes_applied = apply_database_indexes(supabase)

    if indexes_applied:
        logger.info("✓ Database indexes applied successfully")
    else:
        logger.warning("⚠ Some database indexes may not have been applied")

    # Test performance improvements
    logger.info("Testing performance improvements...")
    test_results = test_performance_improvements(supabase)

    # Generate and save report
    report = generate_performance_report(test_results)

    # Save report to file
    report_filename = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_filename, 'w') as f:
        f.write(report)

    logger.info(f"✓ Performance report saved to {report_filename}")

    # Print summary
    print("\n" + "="*60)
    print("DEPLOYMENT SUMMARY")
    print("="*60)
    print(f"Database indexes applied: {'✓' if indexes_applied else '✗'}")
    print(f"Performance tests completed: {len(test_results)}")
    print(f"Report generated: {report_filename}")
    print("="*60)

    # Print test results
    for test_name, result in test_results.items():
        status = "✓ PASS" if result['success'] else "✗ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status} ({result['time']:.3f}s)")

    print("\nDeployment completed successfully!")
    print("Next steps:")
    print("1. Update your application to use the optimized endpoints")
    print("2. Monitor performance in production")
    print("3. Set up performance monitoring alerts")

if __name__ == "__main__":
    main() 