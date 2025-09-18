"""
Performance Verification Script
Compare old vs new database operations to verify improvements
"""

import time
from datetime import datetime
from supabase import create_client
import os
from dotenv import load_dotenv

# Import optimizers
from database_performance_optimizer import create_database_optimizer
from query_optimization_patterns import create_query_optimizer

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY'))

# Initialize optimizers
db_optimizer = create_database_optimizer(supabase)
query_optimizer = create_query_optimizer(supabase)

def test_dashboard_performance():
    """Test dashboard query performance"""
    print("🔄 Testing Dashboard Performance...")

    # Test user (replace with actual user from your system)
    test_cre = "TEST_CRE_NAME"  # Replace with real CRE name

    # OLD METHOD (Sequential queries)
    print("\n📊 OLD METHOD:")
    start_time = time.time()

    try:
        # Simulate old dashboard queries
        leads = supabase.table('lead_master').select('*').eq('cre_name', test_cre).limit(100).execute()
        call_attempts = supabase.table('cre_call_attempts').select('*').eq('cre_name', test_cre).limit(50).execute()

        old_time = time.time() - start_time
        old_lead_count = len(leads.data) if leads.data else 0
        print(f"⏱️  OLD METHOD: {old_time:.3f}s | Leads: {old_lead_count}")

    except Exception as e:
        print(f"❌ OLD METHOD Error: {e}")
        old_time = None

    # NEW METHOD (Optimized)
    print("\n⚡ NEW METHOD:")
    start_time = time.time()

    try:
        dashboard_data = query_optimizer.optimize_dashboard_leads_query(
            user_type='cre',
            user_name=test_cre,
            filters={'limit': 100}
        )

        new_time = time.time() - start_time
        new_lead_count = len(dashboard_data.get('leads', []))
        print(f"⚡ NEW METHOD: {new_time:.3f}s | Leads: {new_lead_count}")

        # Calculate improvement
        if old_time:
            improvement = ((old_time - new_time) / old_time) * 100
            print(f"🚀 IMPROVEMENT: {improvement:.1f}% faster!")

    except Exception as e:
        print(f"❌ NEW METHOD Error: {e}")

def test_duplicate_check_performance():
    """Test duplicate checking performance"""
    print("\n🔄 Testing Duplicate Check Performance...")

    # Test with sample phone numbers (replace with real ones from your DB)
    test_phones = ["9876543210", "9876543211", "9876543212", "9876543213", "9876543214"]

    # OLD METHOD (Sequential checks)
    print("\n📊 OLD METHOD:")
    start_time = time.time()

    try:
        old_duplicates = {}
        for phone in test_phones:
            lead_check = supabase.table('lead_master').select('uid, source, sub_source').eq('customer_mobile_number', phone).execute()
            dup_check = supabase.table('duplicate_leads').select('uid, source1, source2').eq('customer_mobile_number', phone).execute()

            if lead_check.data or dup_check.data:
                old_duplicates[phone] = True

        old_time = time.time() - start_time
        print(f"⏱️  OLD METHOD: {old_time:.3f}s | Checked: {len(test_phones)} phones | Duplicates: {len(old_duplicates)}")

    except Exception as e:
        print(f"❌ OLD METHOD Error: {e}")
        old_time = None

    # NEW METHOD (Batch check)
    print("\n⚡ NEW METHOD:")
    start_time = time.time()

    try:
        result = query_optimizer.optimize_duplicate_check_query(test_phones)

        new_time = time.time() - start_time
        new_duplicates = len(result.get('duplicates', {}))
        print(f"⚡ NEW METHOD: {new_time:.3f}s | Checked: {result.get('phones_checked', 0)} phones | Duplicates: {new_duplicates}")

        # Calculate improvement
        if old_time:
            improvement = ((old_time - new_time) / old_time) * 100
            print(f"🚀 IMPROVEMENT: {improvement:.1f}% faster!")

    except Exception as e:
        print(f"❌ NEW METHOD Error: {e}")

def test_parallel_operations():
    """Test parallel vs sequential operations"""
    print("\n🔄 Testing Parallel Operations...")

    # OLD METHOD (Sequential)
    print("\n📊 OLD METHOD (Sequential):")
    start_time = time.time()

    try:
        result1 = supabase.table('lead_master').select('uid, customer_name').limit(10).execute()
        result2 = supabase.table('ps_followup_master').select('lead_uid, ps_name').limit(10).execute()
        result3 = supabase.table('Branch Head').select('"Name", "Branch"').limit(5).execute()

        old_time = time.time() - start_time
        old_total = len(result1.data or []) + len(result2.data or []) + len(result3.data or [])
        print(f"⏱️  OLD METHOD: {old_time:.3f}s | Total records: {old_total}")

    except Exception as e:
        print(f"❌ OLD METHOD Error: {e}")
        old_time = None

    # NEW METHOD (Parallel)
    print("\n⚡ NEW METHOD (Parallel):")
    start_time = time.time()

    try:
        operations = [
            {
                'operation_id': 'leads',
                'table': 'lead_master',
                'select_fields': 'uid, customer_name',
                'limit': 10
            },
            {
                'operation_id': 'ps_followup',
                'table': 'ps_followup_master',
                'select_fields': 'lead_uid, ps_name',
                'limit': 10
            },
            {
                'operation_id': 'branch_heads',
                'table': 'Branch Head',
                'select_fields': '"Name", "Branch"',
                'limit': 5
            }
        ]

        results = db_optimizer.parallel_select_operations(operations)

        new_time = time.time() - start_time
        new_total = sum(len(data or []) for data in results.values())
        print(f"⚡ NEW METHOD: {new_time:.3f}s | Total records: {new_total}")

        # Calculate improvement
        if old_time:
            improvement = ((old_time - new_time) / old_time) * 100
            print(f"🚀 IMPROVEMENT: {improvement:.1f}% faster!")

    except Exception as e:
        print(f"❌ NEW METHOD Error: {e}")

def test_cache_functionality():
    """Test caching functionality"""
    print("\n🔄 Testing Cache Functionality...")

    test_user = "TEST_USER"  # Replace with real user

    # First call (should hit database)
    print("\n📊 First call (cache miss):")
    start_time = time.time()
    data1 = db_optimizer.get_dashboard_data_optimized('cre', test_user)
    first_time = time.time() - start_time
    print(f"⏱️  First call: {first_time:.3f}s")

    # Second call (should hit cache)
    print("\n⚡ Second call (cache hit):")
    start_time = time.time()
    data2 = db_optimizer.get_dashboard_data_optimized('cre', test_user)
    second_time = time.time() - start_time
    print(f"⚡ Second call: {second_time:.3f}s")

    # Verify cache improvement
    if first_time > 0:
        cache_improvement = ((first_time - second_time) / first_time) * 100
        print(f"🚀 CACHE IMPROVEMENT: {cache_improvement:.1f}% faster!")

    # Show cache stats
    cache_stats = db_optimizer.get_cache_stats()
    print(f"📊 Cache Stats: {cache_stats}")

def run_verification():
    """Run all verification tests"""
    print("🔍 DATABASE OPTIMIZATION VERIFICATION")
    print("=" * 50)
    print(f"📅 Test Time: {datetime.now()}")
    print()

    try:
        test_dashboard_performance()
        print("\n" + "="*50)

        test_duplicate_check_performance()
        print("\n" + "="*50)

        test_parallel_operations()
        print("\n" + "="*50)

        test_cache_functionality()
        print("\n" + "="*50)

        print("\n✅ VERIFICATION COMPLETE!")
        print("📊 Check the performance improvements above")

    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        db_optimizer.cleanup()

if __name__ == "__main__":
    run_verification()