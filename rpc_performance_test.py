"""
RPC Performance Test Script
Verify sub-1-second performance with Supabase RPC functions
"""

import time
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from supabase import create_client

# Import the ultra-fast RPC client
from ultra_fast_rpc_client import (
    create_ultra_fast_rpc_client,
    create_ultra_fast_dashboard,
    create_ultra_fast_operations
)

load_dotenv()

# Initialize Supabase client
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY'))

# Initialize ultra-fast clients
rpc_client = create_ultra_fast_rpc_client(supabase)
ultra_dashboard = create_ultra_fast_dashboard(supabase)
ultra_operations = create_ultra_fast_operations(supabase)

def test_rpc_dashboard_performance():
    """Test RPC dashboard performance - Target: < 300ms"""
    print("🚀 Testing RPC Dashboard Performance")
    print("=" * 50)

    # Test CRE Dashboard
    print("\n📊 CRE Dashboard RPC Test:")
    test_cre = "KUMARI"  # Replace with actual CRE name from your system

    try:
        start_time = time.time()
        result = rpc_client.get_cre_dashboard_ultra_fast(
            cre_name=test_cre,
            filters={
                'final_status': 'Pending',
                'limit': 500
            }
        )
        execution_time = time.time() - start_time

        if result.success:
            data = result.data
            leads_count = len(data.get('leads', [])) if data.get('leads') else 0
            print(f"✅ CRE Dashboard RPC: {execution_time:.3f}s | Leads: {leads_count}")

            # Check if sub-1-second
            if execution_time < 1.0:
                print(f"🎯 SUB-1-SECOND ACHIEVED! ({execution_time:.3f}s)")
            else:
                print(f"⚠️  Slower than 1s: {execution_time:.3f}s")

            # Show detailed stats
            if data and 'stats' in data:
                stats = data['stats']
                print(f"   📈 Total: {stats.get('total_count', 0)} | Won: {stats.get('won_count', 0)} | Conversion: {stats.get('conversion_rate', 0)}%")

        else:
            print(f"❌ CRE Dashboard RPC failed: {result.error}")

    except Exception as e:
        print(f"❌ CRE Dashboard test failed: {e}")

    # Test PS Dashboard
    print("\n📊 PS Dashboard RPC Test:")
    test_ps = "GOPAL"  # Replace with actual PS name from your system

    try:
        start_time = time.time()
        result = rpc_client.get_ps_dashboard_ultra_fast(
            ps_name=test_ps,
            filters={
                'final_status': 'Pending',
                'limit': 500
            }
        )
        execution_time = time.time() - start_time

        if result.success:
            data = result.data
            leads_count = len(data.get('leads', [])) if data.get('leads') else 0
            print(f"✅ PS Dashboard RPC: {execution_time:.3f}s | Leads: {leads_count}")

            # Check if sub-1-second
            if execution_time < 1.0:
                print(f"🎯 SUB-1-SECOND ACHIEVED! ({execution_time:.3f}s)")
            else:
                print(f"⚠️  Slower than 1s: {execution_time:.3f}s")

        else:
            print(f"❌ PS Dashboard RPC failed: {result.error}")

    except Exception as e:
        print(f"❌ PS Dashboard test failed: {e}")

def test_rpc_duplicate_check_performance():
    """Test RPC duplicate check performance - Target: < 200ms"""
    print("\n🔍 Testing RPC Duplicate Check Performance")
    print("=" * 50)

    # Test with multiple phone numbers
    test_phones = [
        "9876543210", "9876543211", "9876543212", "9876543213", "9876543214",
        "9876543215", "9876543216", "9876543217", "9876543218", "9876543219",
        "9876543220", "9876543221", "9876543222", "9876543223", "9876543224"
    ]

    print(f"\n📞 Testing duplicate check for {len(test_phones)} phone numbers:")

    try:
        start_time = time.time()
        result = rpc_client.check_duplicates_ultra_fast(test_phones)
        execution_time = time.time() - start_time

        if result.success:
            data = result.data
            phones_checked = data.get('phones_checked', 0)
            duplicates_found = data.get('duplicates_found', 0)

            print(f"✅ Duplicate Check RPC: {execution_time:.3f}s")
            print(f"   📞 Phones checked: {phones_checked}")
            print(f"   🔄 Duplicates found: {duplicates_found}")

            # Check if sub-1-second
            if execution_time < 1.0:
                print(f"🎯 SUB-1-SECOND ACHIEVED! ({execution_time:.3f}s)")
            else:
                print(f"⚠️  Slower than 1s: {execution_time:.3f}s")

            # Performance per phone
            time_per_phone = execution_time / len(test_phones)
            print(f"   ⚡ Time per phone: {time_per_phone:.4f}s")

        else:
            print(f"❌ Duplicate Check RPC failed: {result.error}")

    except Exception as e:
        print(f"❌ Duplicate check test failed: {e}")

def test_rpc_test_drive_performance():
    """Test RPC test drive operations - Target: < 200ms"""
    print("\n🚗 Testing RPC Test Drive Performance")
    print("=" * 50)

    # Test with a sample lead UID (replace with actual UID from your system)
    test_lead_uid = "G-1234-ABC"  # Replace with actual lead UID

    test_drive_data = {
        'test_drive_date': '2024-01-15',
        'feedback': 'Excellent experience, customer loved the performance',
        'status': 'Completed'
    }

    print(f"\n🚗 Testing test drive update for lead: {test_lead_uid}")

    try:
        start_time = time.time()
        result = rpc_client.update_test_drive_ultra_fast(test_lead_uid, test_drive_data)
        execution_time = time.time() - start_time

        if result.success:
            data = result.data
            print(f"✅ Test Drive RPC: {execution_time:.3f}s")
            print(f"   🎯 Source table: {data.get('source_table')}")
            print(f"   📝 Operations: {len(data.get('operations_completed', []))}")

            # Check if sub-1-second
            if execution_time < 1.0:
                print(f"🎯 SUB-1-SECOND ACHIEVED! ({execution_time:.3f}s)")
            else:
                print(f"⚠️  Slower than 1s: {execution_time:.3f}s")

        else:
            print(f"❌ Test Drive RPC failed: {result.error}")

    except Exception as e:
        print(f"❌ Test drive test failed: {e}")

def test_rpc_analytics_performance():
    """Test RPC analytics performance - Target: < 400ms"""
    print("\n📊 Testing RPC Analytics Performance")
    print("=" * 50)

    # Test analytics for last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    print(f"\n📈 Testing analytics for date range: {start_date.date()} to {end_date.date()}")

    try:
        start_time = time.time()
        result = rpc_client.get_analytics_ultra_fast(
            date_range=(start_date.isoformat(), end_date.isoformat()),
            filters={
                'cre_name': None,  # All CREs
                'branch': None     # All branches
            }
        )
        execution_time = time.time() - start_time

        if result.success:
            data = result.data
            summary = data.get('summary', {})

            print(f"✅ Analytics RPC: {execution_time:.3f}s")
            print(f"   📊 Total leads: {summary.get('total_leads', 0)}")
            print(f"   🎯 Won leads: {summary.get('won_leads', 0)}")
            print(f"   📈 Conversion rate: {summary.get('conversion_rate', 0)}%")
            print(f"   🔍 Unique sources: {summary.get('unique_sources', 0)}")

            # Check if sub-1-second
            if execution_time < 1.0:
                print(f"🎯 SUB-1-SECOND ACHIEVED! ({execution_time:.3f}s)")
            else:
                print(f"⚠️  Slower than 1s: {execution_time:.3f}s")

        else:
            print(f"❌ Analytics RPC failed: {result.error}")

    except Exception as e:
        print(f"❌ Analytics test failed: {e}")

def test_rpc_bulk_operations():
    """Test RPC bulk operations performance"""
    print("\n📦 Testing RPC Bulk Operations Performance")
    print("=" * 50)

    # Create sample lead data
    sample_leads = []
    for i in range(50):  # Test with 50 leads
        sample_leads.append({
            'uid': f'TEST-{i:04d}-RPC',
            'customer_name': f'Test Customer {i}',
            'customer_mobile_number': f'98765432{i:02d}',
            'source': 'META',
            'sub_source': 'Facebook',
            'campaign': 'Test Campaign',
            'cre_name': 'TEST_CRE',
            'lead_category': 'Hot',
            'model_interested': 'Ather 450X',
            'branch': 'Test Branch',
            'assigned': 'No',
            'lead_status': 'Pending',
            'final_status': 'Pending',
            'date': datetime.now().date().isoformat()
        })

    print(f"\n📦 Testing bulk creation of {len(sample_leads)} leads:")

    try:
        start_time = time.time()
        result = rpc_client.create_leads_bulk_ultra_fast(sample_leads)
        execution_time = time.time() - start_time

        if result.success:
            data = result.data
            print(f"✅ Bulk Creation RPC: {execution_time:.3f}s")
            print(f"   📝 Total processed: {data.get('total_processed', 0)}")
            print(f"   ✅ Inserted: {data.get('inserted', 0)}")
            print(f"   🔄 Duplicates skipped: {data.get('duplicates_skipped', 0)}")
            print(f"   ❌ Errors: {data.get('errors', 0)}")

            # Performance per lead
            time_per_lead = execution_time / len(sample_leads)
            print(f"   ⚡ Time per lead: {time_per_lead:.4f}s")

            # Check if sub-1-second
            if execution_time < 1.0:
                print(f"🎯 SUB-1-SECOND ACHIEVED! ({execution_time:.3f}s)")
            else:
                print(f"⚠️  Slower than 1s: {execution_time:.3f}s")

        else:
            print(f"❌ Bulk Creation RPC failed: {result.error}")

    except Exception as e:
        print(f"❌ Bulk operations test failed: {e}")

def test_performance_comparison():
    """Compare RPC vs Traditional methods"""
    print("\n⚡ RPC vs Traditional Performance Comparison")
    print("=" * 50)

    test_cre = "KUMARI"  # Replace with actual CRE name

    # Test Traditional method (if available)
    print("\n📊 Traditional Method:")
    try:
        start_time = time.time()
        # Simulate traditional dashboard query
        leads = supabase.table('lead_master').select('*').eq('cre_name', test_cre).limit(100).execute()
        traditional_time = time.time() - start_time
        traditional_count = len(leads.data) if leads.data else 0
        print(f"   ⏱️  Traditional: {traditional_time:.3f}s | Leads: {traditional_count}")
    except Exception as e:
        print(f"   ❌ Traditional method failed: {e}")
        traditional_time = None

    # Test RPC method
    print("\n⚡ RPC Method:")
    try:
        start_time = time.time()
        result = rpc_client.get_cre_dashboard_ultra_fast(test_cre, {'limit': 100})
        rpc_time = time.time() - start_time

        if result.success:
            rpc_count = len(result.data.get('leads', [])) if result.data.get('leads') else 0
            print(f"   🚀 RPC: {rpc_time:.3f}s | Leads: {rpc_count}")

            # Calculate improvement
            if traditional_time:
                improvement = ((traditional_time - rpc_time) / traditional_time) * 100
                print(f"\n🎯 PERFORMANCE IMPROVEMENT: {improvement:.1f}% faster!")
                print(f"   📈 Speed multiplier: {traditional_time / rpc_time:.1f}x")

        else:
            print(f"   ❌ RPC method failed: {result.error}")

    except Exception as e:
        print(f"   ❌ RPC method failed: {e}")

def show_performance_summary():
    """Show overall performance summary"""
    print("\n📊 Performance Summary")
    print("=" * 50)

    stats = rpc_client.get_performance_stats()

    if 'message' in stats:
        print(stats['message'])
        return

    print(f"Total operations: {stats['total_operations']}")
    print(f"Success rate: {stats['success_rate']:.1f}%")
    print(f"Average execution time: {stats['average_execution_time']:.3f}s")
    print(f"Fastest operation: {stats['fastest_operation']:.3f}s")
    print(f"Slowest operation: {stats['slowest_operation']:.3f}s")
    print(f"Sub-1-second rate: {stats['sub_1_second_rate']:.1f}%")

    print("\n📋 Operations Breakdown:")
    for op_name, op_stats in stats['operations_breakdown'].items():
        print(f"   {op_name}: {op_stats['avg_time']:.3f}s avg ({op_stats['count']} calls)")

def run_comprehensive_rpc_test():
    """Run all RPC performance tests"""
    print("🚀 ULTRA-FAST RPC PERFORMANCE TEST")
    print("=" * 60)
    print(f"📅 Test Time: {datetime.now()}")
    print(f"🎯 Target: All operations < 1 second")
    print()

    try:
        # Run all tests
        test_rpc_dashboard_performance()
        test_rpc_duplicate_check_performance()
        test_rpc_test_drive_performance()
        test_rpc_analytics_performance()
        test_rpc_bulk_operations()
        test_performance_comparison()

        # Show summary
        show_performance_summary()

        print("\n" + "=" * 60)
        print("✅ RPC PERFORMANCE TEST COMPLETED!")
        print("🎯 Check results above for sub-1-second achievements")

    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🔧 Make sure you've executed the RPC functions in Supabase SQL Editor first!")
    print("📄 File: supabase_rpc_functions.sql")
    print()

    input("Press Enter to start RPC performance tests...")
    run_comprehensive_rpc_test()