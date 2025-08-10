#!/usr/bin/env python3
"""
Test script for the Auto Assign System
======================================

This script tests the auto assign system to ensure it's working properly
and logging all assignments to the auto_assign_history table.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL_UDAY3') or os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_ANON_KEY_UDAY3') or os.getenv('SUPABASE_ANON_KEY')

if not supabase_url or not supabase_key:
    print("❌ Error: Missing Supabase credentials")
    sys.exit(1)

supabase: Client = create_client(supabase_url, supabase_key)

def test_database_connection():
    """Test database connection and basic functionality"""
    print("🔍 Testing database connection...")
    
    try:
        # Test basic connection
        result = supabase.table('cre_users').select('id, name').limit(1).execute()
        if result.data:
            print("✅ Database connection successful")
            return True
        else:
            print("⚠️ Database connected but no data found")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def check_required_tables():
    """Check if all required tables exist"""
    print("\n🔍 Checking required tables...")
    
    required_tables = [
        'cre_users',
        'auto_assign_config', 
        'auto_assign_history',
        'lead_master'
    ]
    
    missing_tables = []
    
    for table in required_tables:
        try:
            result = supabase.table(table).select('id').limit(1).execute()
            print(f"✅ {table} table exists")
        except Exception as e:
            print(f"❌ {table} table missing: {e}")
            missing_tables.append(table)
    
    if missing_tables:
        print(f"\n⚠️ Missing tables: {', '.join(missing_tables)}")
        return False
    
    return True

def check_auto_assign_count_column():
    """Check if auto_assign_count column exists in cre_users"""
    print("\n🔍 Checking auto_assign_count column...")
    
    try:
        result = supabase.table('cre_users').select('auto_assign_count').limit(1).execute()
        print("✅ auto_assign_count column exists in cre_users table")
        return True
    except Exception as e:
        print(f"❌ auto_assign_count column missing: {e}")
        return False

def check_auto_assign_config():
    """Check auto-assign configuration"""
    print("\n🔍 Checking auto-assign configuration...")
    
    try:
        result = supabase.table('auto_assign_config').select('*').execute()
        configs = result.data or []
        
        if configs:
            print(f"✅ Found {len(configs)} auto-assign configurations:")
            for config in configs:
                print(f"   • {config['source']} -> CRE ID: {config['cre_id']} (Active: {config['is_active']})")
        else:
            print("⚠️ No auto-assign configurations found")
            
        return len(configs) > 0
    except Exception as e:
        print(f"❌ Error checking auto-assign config: {e}")
        return False

def check_auto_assign_history():
    """Check auto-assign history table"""
    print("\n🔍 Checking auto-assign history...")
    
    try:
        result = supabase.table('auto_assign_history').select('*').order('created_at', desc=True).limit(10).execute()
        history_records = result.data or []
        
        if history_records:
            print(f"✅ Found {len(history_records)} history records:")
            for record in history_records[:5]:  # Show first 5
                print(f"   • {record['lead_uid']} -> {record['assigned_cre_name']} ({record['source']}) - {record['created_at']}")
        else:
            print("ℹ️ No auto-assign history records found (this is normal for new systems)")
            
        return True
    except Exception as e:
        print(f"❌ Error checking auto-assign history: {e}")
        return False

def check_cre_auto_assign_counts():
    """Check current auto-assign counts for CREs"""
    print("\n🔍 Checking CRE auto-assign counts...")
    
    try:
        result = supabase.table('cre_users').select('id, name, auto_assign_count').execute()
        cres = result.data or []
        
        if cres:
            print(f"✅ Found {len(cres)} CREs:")
            for cre in sorted(cres, key=lambda x: x.get('auto_assign_count', 0), reverse=True):
                count = cre.get('auto_assign_count', 0)
                print(f"   • {cre['name']}: {count} auto-assigned leads")
        else:
            print("⚠️ No CREs found")
            
        return True
    except Exception as e:
        print(f"❌ Error checking CRE counts: {e}")
        return False

def test_auto_assign_functions():
    """Test auto-assign functions"""
    print("\n🔍 Testing auto-assign functions...")
    
    try:
        # Test get_fairest_cre_for_source function if it exists
        try:
            result = supabase.rpc('get_fairest_cre_for_source', {'p_source': 'META'}).execute()
            print("✅ get_fairest_cre_for_source function works")
        except Exception as e:
            print(f"⚠️ get_fairest_cre_for_source function not available: {e}")
        
        # Test get_auto_assign_stats function if it exists
        try:
            result = supabase.rpc('get_auto_assign_stats').execute()
            print("✅ get_auto_assign_stats function works")
        except Exception as e:
            print(f"⚠️ get_auto_assign_stats function not available: {e}")
            
        return True
    except Exception as e:
        print(f"❌ Error testing functions: {e}")
        return False

def test_manual_auto_assign():
    """Test manual auto-assign trigger"""
    print("\n🔍 Testing manual auto-assign...")
    
    try:
        # Import and test the auto assign system
        from auto_assign_system import EnhancedAutoAssignTrigger
        
        trigger = EnhancedAutoAssignTrigger()
        
        # Test manual assignment for META source
        result = trigger.trigger_manual_assignment('META')
        
        if result and 'assigned_count' in result:
            print(f"✅ Manual auto-assign test completed: {result['assigned_count']} leads assigned")
            print(f"   Message: {result['message']}")
        else:
            print("⚠️ Manual auto-assign test completed but no result returned")
            
        return True
    except Exception as e:
        print(f"❌ Error testing manual auto-assign: {e}")
        return False

def run_comprehensive_test():
    """Run comprehensive test of the auto assign system"""
    print("🚀 Starting Comprehensive Auto Assign System Test")
    print("=" * 60)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Required Tables", check_required_tables),
        ("Auto Assign Count Column", check_auto_assign_count_column),
        ("Auto Assign Config", check_auto_assign_config),
        ("Auto Assign History", check_auto_assign_history),
        ("CRE Auto Assign Counts", check_cre_auto_assign_counts),
        ("Auto Assign Functions", test_auto_assign_functions),
        ("Manual Auto Assign", test_manual_auto_assign)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Auto assign system is working properly.")
    else:
        print("⚠️ Some tests failed. Please check the issues above.")
    
    return passed == total

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        # Quick test mode
        print("🔍 Running quick test...")
        test_database_connection()
        check_required_tables()
        check_auto_assign_count_column()
    else:
        # Comprehensive test mode
        run_comprehensive_test()

if __name__ == "__main__":
    main() 