"""
Comprehensive Test Suite for Instant Lead Updates
Verifies sub-1-second performance across all optimization strategies
"""

import time
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import random
import string
import statistics
from datetime import datetime
import os
from dotenv import load_dotenv
from supabase import create_client

# Import all instant update components
from instant_update_client import (
    create_instant_update_client,
    InstantUpdateConfig,
    update_lead_in_real_time
)
from ultra_fast_lead_update_system import (
    LeadUpdateRequest,
    create_ultra_fast_lead_updater
)

load_dotenv()

# Initialize Supabase
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY'))

class InstantUpdateTester:
    """Comprehensive tester for instant lead updates"""

    def __init__(self):
        self.test_results = {
            'individual_updates': [],
            'batch_updates': [],
            'concurrent_updates': [],
            'stress_tests': [],
            'performance_summary': {}
        }

        # Create instant update client
        self.client = create_instant_update_client(
            lambda: supabase,
            target_time_ms=500
        )

        # Test data
        self.test_leads = []
        self.setup_test_data()

    def setup_test_data(self):
        """Setup test lead data"""
        print("🔧 Setting up test data...")

        try:
            # Get existing leads for testing
            result = supabase.table('lead_master').select('uid, customer_name, cre_name').limit(10).execute()

            if result.data:
                self.test_leads = result.data
                print(f"✅ Found {len(self.test_leads)} existing leads for testing")
            else:
                print("⚠️ No existing leads found, will create test leads")
                self.create_test_leads()

        except Exception as e:
            print(f"❌ Error setting up test data: {e}")
            self.create_test_leads()

    def create_test_leads(self):
        """Create test leads if none exist"""
        print("📝 Creating test leads...")

        for i in range(5):
            test_uid = f"TEST-{int(time.time())}-{i:02d}"
            lead_data = {
                'uid': test_uid,
                'customer_name': f'Test Customer {i+1}',
                'customer_mobile_number': f'9876543{i:03d}',
                'source': 'TEST',
                'sub_source': 'Instant Update Test',
                'cre_name': 'TEST_CRE',
                'lead_status': 'Pending',
                'final_status': 'Pending',
                'assigned': 'No',
                'date': datetime.now().date().isoformat(),
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }

            try:
                supabase.table('lead_master').insert(lead_data).execute()
                self.test_leads.append({'uid': test_uid, 'customer_name': lead_data['customer_name']})
                print(f"✅ Created test lead: {test_uid}")

            except Exception as e:
                print(f"❌ Failed to create test lead: {e}")

    def test_individual_updates(self) -> Dict[str, Any]:
        """Test individual lead updates for sub-1-second performance"""
        print("\n🚀 Testing Individual Lead Updates")
        print("=" * 50)

        results = []

        for i, lead in enumerate(self.test_leads[:5]):
            print(f"\n📝 Test {i+1}: Updating {lead['uid']}")

            # Generate random update data
            update_data = {
                'lead_status': random.choice(['Pending', 'Follow-up', 'Hot', 'Warm']),
                'first_remark': f'Instant update test at {datetime.now().strftime("%H:%M:%S")}',
                'updated_at': datetime.now().isoformat()
            }

            # Perform update
            start_time = time.time()
            result = self.client.update_lead_instantly(
                lead_uid=lead['uid'],
                update_data=update_data,
                user_type='cre',
                user_name='TEST_USER'
            )
            total_time = time.time() - start_time

            # Analyze result
            server_time = result.execution_time
            success = result.success

            print(f"   Server time: {server_time:.3f}s")
            print(f"   Total time: {total_time:.3f}s")
            print(f"   Success: {'✅' if success else '❌'}")

            if server_time < 0.5:
                print(f"   🎯 ULTRA-FAST ACHIEVED! ({server_time:.3f}s)")
            elif server_time < 1.0:
                print(f"   ⚡ SUB-1-SECOND ACHIEVED! ({server_time:.3f}s)")
            else:
                print(f"   ⚠️  Slower than target: {server_time:.3f}s")

            results.append({
                'lead_uid': lead['uid'],
                'server_time': server_time,
                'total_time': total_time,
                'success': success,
                'target_met': server_time < 1.0,
                'ultra_fast': server_time < 0.5
            })

            # Small delay between tests
            time.sleep(0.5)

        # Calculate statistics
        successful_updates = [r for r in results if r['success']]
        avg_server_time = statistics.mean([r['server_time'] for r in successful_updates])
        sub_1s_rate = (len([r for r in results if r['target_met']]) / len(results)) * 100
        ultra_fast_rate = (len([r for r in results if r['ultra_fast']]) / len(results)) * 100

        summary = {
            'total_tests': len(results),
            'successful': len(successful_updates),
            'average_server_time': avg_server_time,
            'sub_1s_rate': sub_1s_rate,
            'ultra_fast_rate': ultra_fast_rate,
            'fastest_update': min([r['server_time'] for r in successful_updates]),
            'slowest_update': max([r['server_time'] for r in successful_updates])
        }

        print(f"\n📊 Individual Update Summary:")
        print(f"   Success rate: {(len(successful_updates)/len(results)*100):.1f}%")
        print(f"   Average time: {avg_server_time:.3f}s")
        print(f"   Sub-1s rate: {sub_1s_rate:.1f}%")
        print(f"   Ultra-fast rate: {ultra_fast_rate:.1f}%")

        self.test_results['individual_updates'] = results
        return summary

    def test_batch_updates(self) -> Dict[str, Any]:
        """Test batch update performance"""
        print("\n📦 Testing Batch Updates")
        print("=" * 50)

        if len(self.test_leads) < 3:
            print("⚠️ Not enough test leads for batch testing")
            return {}

        # Prepare batch update data
        batch_updates = []
        for lead in self.test_leads[:3]:
            batch_updates.append({
                'lead_uid': lead['uid'],
                'user_type': 'cre',
                'user_name': 'TEST_USER',
                'update_data': {
                    'lead_status': 'Follow-up',
                    'first_remark': f'Batch update test at {datetime.now().strftime("%H:%M:%S")}',
                    'updated_at': datetime.now().isoformat()
                }
            })

        print(f"📝 Testing batch update of {len(batch_updates)} leads...")

        # Perform batch update
        start_time = time.time()
        results = self.client.batch_update_leads_instantly(batch_updates)
        total_time = time.time() - start_time

        # Analyze results
        successful = len([r for r in results if r.success])
        avg_time = statistics.mean([r.execution_time for r in results if r.success])

        print(f"   Total time: {total_time:.3f}s")
        print(f"   Average per lead: {avg_time:.3f}s")
        print(f"   Success rate: {(successful/len(results)*100):.1f}%")

        summary = {
            'total_leads': len(batch_updates),
            'successful': successful,
            'total_time': total_time,
            'average_per_lead': avg_time,
            'success_rate': (successful / len(results)) * 100
        }

        self.test_results['batch_updates'] = results
        return summary

    def test_concurrent_updates(self) -> Dict[str, Any]:
        """Test concurrent updates from multiple threads"""
        print("\n🔄 Testing Concurrent Updates")
        print("=" * 50)

        if len(self.test_leads) < 5:
            print("⚠️ Not enough test leads for concurrent testing")
            return {}

        print(f"🧵 Testing 5 concurrent updates...")

        def update_single_lead(lead):
            update_data = {
                'lead_status': 'Hot',
                'first_remark': f'Concurrent test {threading.current_thread().name}',
                'updated_at': datetime.now().isoformat()
            }

            return self.client.update_lead_instantly(
                lead_uid=lead['uid'],
                update_data=update_data,
                user_type='cre',
                user_name='CONCURRENT_TEST'
            )

        # Execute concurrent updates
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(update_single_lead, lead)
                for lead in self.test_leads[:5]
            ]

            results = []
            for future in as_completed(futures, timeout=5.0):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"   ❌ Concurrent update failed: {e}")

        total_time = time.time() - start_time

        # Analyze concurrent performance
        successful = len([r for r in results if r.success])
        avg_time = statistics.mean([r.execution_time for r in results if r.success])
        max_time = max([r.execution_time for r in results if r.success])

        print(f"   Concurrent execution: {total_time:.3f}s")
        print(f"   Average per update: {avg_time:.3f}s")
        print(f"   Slowest update: {max_time:.3f}s")
        print(f"   Success rate: {(successful/len(results)*100):.1f}%")

        summary = {
            'concurrent_updates': len(results),
            'successful': successful,
            'total_time': total_time,
            'average_time': avg_time,
            'max_time': max_time,
            'success_rate': (successful / len(results)) * 100
        }

        self.test_results['concurrent_updates'] = results
        return summary

    def test_stress_performance(self) -> Dict[str, Any]:
        """Stress test with rapid sequential updates"""
        print("\n💪 Testing Stress Performance")
        print("=" * 50)

        if not self.test_leads:
            print("⚠️ No test leads available for stress testing")
            return {}

        lead = self.test_leads[0]
        num_updates = 10

        print(f"⚡ Performing {num_updates} rapid updates on {lead['uid']}...")

        results = []
        start_time = time.time()

        for i in range(num_updates):
            update_data = {
                'first_remark': f'Stress test update #{i+1} at {datetime.now().strftime("%H:%M:%S.%f")}',
                'updated_at': datetime.now().isoformat()
            }

            result = self.client.update_lead_instantly(
                lead_uid=lead['uid'],
                update_data=update_data,
                user_type='cre',
                user_name='STRESS_TEST'
            )

            results.append(result)

        total_time = time.time() - start_time

        # Analyze stress test results
        successful = len([r for r in results if r.success])
        execution_times = [r.execution_time for r in results if r.success]

        avg_time = statistics.mean(execution_times)
        min_time = min(execution_times)
        max_time = max(execution_times)
        median_time = statistics.median(execution_times)

        print(f"   Total time: {total_time:.3f}s")
        print(f"   Updates per second: {num_updates/total_time:.1f}")
        print(f"   Average time: {avg_time:.3f}s")
        print(f"   Fastest: {min_time:.3f}s")
        print(f"   Slowest: {max_time:.3f}s")
        print(f"   Median: {median_time:.3f}s")

        summary = {
            'total_updates': num_updates,
            'successful': successful,
            'total_time': total_time,
            'updates_per_second': num_updates / total_time,
            'average_time': avg_time,
            'min_time': min_time,
            'max_time': max_time,
            'median_time': median_time
        }

        self.test_results['stress_tests'] = results
        return summary

    def test_rpc_vs_parallel_performance(self) -> Dict[str, Any]:
        """Compare RPC vs parallel update performance"""
        print("\n⚡ Testing RPC vs Parallel Performance")
        print("=" * 50)

        if len(self.test_leads) < 2:
            print("⚠️ Need at least 2 leads for comparison testing")
            return {}

        lead1 = self.test_leads[0]
        lead2 = self.test_leads[1] if len(self.test_leads) > 1 else self.test_leads[0]

        # Test RPC update
        print("🚀 Testing RPC update...")
        rpc_update = {
            'lead_status': 'Hot',
            'first_remark': 'RPC performance test',
            'updated_at': datetime.now().isoformat()
        }

        rpc_result = self.client.update_lead_instantly(
            lead_uid=lead1['uid'],
            update_data=rpc_update,
            user_type='cre',
            user_name='RPC_TEST'
        )

        print(f"   RPC time: {rpc_result.execution_time:.3f}s")

        # Test parallel update (simulate by disabling RPC)
        print("🔄 Testing parallel update...")
        original_use_rpc = self.client.config.use_rpc
        self.client.config.use_rpc = False

        parallel_update = {
            'lead_status': 'Warm',
            'first_remark': 'Parallel performance test',
            'updated_at': datetime.now().isoformat()
        }

        parallel_result = self.client.update_lead_instantly(
            lead_uid=lead2['uid'],
            update_data=parallel_update,
            user_type='cre',
            user_name='PARALLEL_TEST'
        )

        print(f"   Parallel time: {parallel_result.execution_time:.3f}s")

        # Restore RPC setting
        self.client.config.use_rpc = original_use_rpc

        # Compare performance
        if rpc_result.success and parallel_result.success:
            improvement = ((parallel_result.execution_time - rpc_result.execution_time) / parallel_result.execution_time) * 100
            print(f"   🎯 RPC improvement: {improvement:.1f}%")

        return {
            'rpc_time': rpc_result.execution_time if rpc_result.success else None,
            'parallel_time': parallel_result.execution_time if parallel_result.success else None,
            'rpc_faster': rpc_result.execution_time < parallel_result.execution_time if both_success else None
        }

    def run_comprehensive_test(self):
        """Run all tests and generate comprehensive report"""
        print("🧪 INSTANT LEAD UPDATE COMPREHENSIVE TEST")
        print("=" * 60)
        print(f"📅 Test Time: {datetime.now()}")
        print(f"🎯 Target: All updates < 1 second (Preferred: < 500ms)")
        print()

        try:
            # Run all test categories
            individual_summary = self.test_individual_updates()
            batch_summary = self.test_batch_updates()
            concurrent_summary = self.test_concurrent_updates()
            stress_summary = self.test_stress_performance()
            comparison_summary = self.test_rpc_vs_parallel_performance()

            # Generate comprehensive performance summary
            self._generate_performance_report(
                individual_summary,
                batch_summary,
                concurrent_summary,
                stress_summary,
                comparison_summary
            )

        except Exception as e:
            print(f"❌ Test suite failed: {e}")
            import traceback
            traceback.print_exc()

    def _generate_performance_report(self, individual, batch, concurrent, stress, comparison):
        """Generate comprehensive performance report"""
        print("\n📊 COMPREHENSIVE PERFORMANCE REPORT")
        print("=" * 60)

        # Overall performance assessment
        if individual.get('sub_1s_rate', 0) >= 95:
            print("✅ PERFORMANCE TARGET MET: 95%+ updates < 1 second")
        else:
            print("❌ PERFORMANCE TARGET MISSED: < 95% updates under 1 second")

        if individual.get('ultra_fast_rate', 0) >= 80:
            print("🚀 ULTRA-FAST TARGET MET: 80%+ updates < 500ms")
        else:
            print("⚠️ ULTRA-FAST TARGET MISSED: < 80% updates under 500ms")

        # Detailed metrics
        print(f"\n📈 Key Performance Metrics:")
        print(f"   Individual Updates:")
        print(f"     • Average time: {individual.get('average_server_time', 0):.3f}s")
        print(f"     • Sub-1s rate: {individual.get('sub_1s_rate', 0):.1f}%")
        print(f"     • Ultra-fast rate: {individual.get('ultra_fast_rate', 0):.1f}%")

        if batch:
            print(f"   Batch Updates:")
            print(f"     • Average per lead: {batch.get('average_per_lead', 0):.3f}s")
            print(f"     • Success rate: {batch.get('success_rate', 0):.1f}%")

        if concurrent:
            print(f"   Concurrent Updates:")
            print(f"     • Average time: {concurrent.get('average_time', 0):.3f}s")
            print(f"     • Max time: {concurrent.get('max_time', 0):.3f}s")

        if stress:
            print(f"   Stress Test:")
            print(f"     • Updates per second: {stress.get('updates_per_second', 0):.1f}")
            print(f"     • Median time: {stress.get('median_time', 0):.3f}s")

        # System performance stats
        system_stats = self.client.get_performance_stats()
        client_stats = system_stats.get('client_stats', {})

        print(f"\n🔧 System Performance:")
        print(f"   • Total operations: {client_stats.get('total_updates', 0)}")
        print(f"   • Overall success rate: {client_stats.get('success_rate', 0):.1f}%")
        print(f"   • Sub-1s achievement: {client_stats.get('sub_1s_rate', 0):.1f}%")

        # Recommendations
        print(f"\n💡 Recommendations:")
        if individual.get('average_server_time', 1) > 0.5:
            print("   • Consider enabling more aggressive caching")
            print("   • Optimize database indexes")
            print("   • Use RPC functions for critical operations")

        if concurrent.get('max_time', 0) > 1.0:
            print("   • Increase connection pool size for concurrent operations")

        print(f"\n🎯 PERFORMANCE VERDICT:")
        if (individual.get('sub_1s_rate', 0) >= 95 and
            client_stats.get('success_rate', 0) >= 95):
            print("   ✅ INSTANT UPDATE SYSTEM PERFORMING EXCELLENTLY!")
        elif individual.get('sub_1s_rate', 0) >= 80:
            print("   ⚡ INSTANT UPDATE SYSTEM PERFORMING WELL - Minor optimization needed")
        else:
            print("   ⚠️ INSTANT UPDATE SYSTEM NEEDS OPTIMIZATION")

def run_instant_update_tests():
    """Main function to run all instant update tests"""
    print("🔧 Initializing instant update test system...")

    # Check if RPC functions are installed
    try:
        result = supabase.rpc('get_cre_dashboard_optimized', {
            'p_cre_name': 'TEST',
            'p_limit': 1
        }).execute()
        print("✅ RPC functions detected and working")
    except Exception as e:
        print(f"⚠️ RPC functions not available: {e}")
        print("   Please execute ultra_fast_update_rpc.sql in Supabase first!")

    # Run comprehensive tests
    tester = InstantUpdateTester()
    tester.run_comprehensive_test()

if __name__ == "__main__":
    print("🚀 INSTANT LEAD UPDATE TEST SUITE")
    print("=" * 40)
    print("Make sure you've executed the RPC functions first:")
    print("1. ultra_fast_update_rpc.sql")
    print("2. supabase_rpc_functions.sql")
    print()

    input("Press Enter to start comprehensive testing...")
    run_instant_update_tests()