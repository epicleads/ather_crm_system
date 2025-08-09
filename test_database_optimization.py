#!/usr/bin/env python3
"""
Test Database Optimization Script
Safely applies database optimizations and checks for existing tables
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_database_optimization():
    """Test and apply database optimizations safely"""
    
    try:
        # Import required modules
        from supabase import create_client, Client
        from optimized_lead_operations import apply_database_indexes
        
        # Initialize Supabase client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")
        
        if not url or not key:
            print("❌ Error: SUPABASE_URL and SUPABASE_ANON_KEY environment variables are required")
            return False
            
        supabase: Client = create_client(url, key)
        
        print("🔍 Checking existing tables...")
        
        # Check which tables exist
        existing_tables = []
        tables_to_check = [
            'lead_master',
            'duplicate_leads', 
            'ps_followup_master',
            'cre_call_attempts',
            'ps_call_attempts',
            'cre_users',
            'ps_users',
            'admin_users',
            'activity_leads',
            'walkin_leads',
            'audit_log'
        ]
        
        for table in tables_to_check:
            try:
                # Try to select one row to check if table exists
                result = supabase.table(table).select('*').limit(1).execute()
                existing_tables.append(table)
                print(f"✅ Table '{table}' exists")
            except Exception as e:
                if "does not exist" in str(e) or "42P01" in str(e):
                    print(f"⚠️  Table '{table}' does not exist (will be skipped)")
                else:
                    print(f"❓ Table '{table}' status unknown: {e}")
        
        print(f"\n📊 Found {len(existing_tables)} existing tables out of {len(tables_to_check)} checked")
        
        if 'lead_master' not in existing_tables:
            print("❌ Error: lead_master table is required but not found!")
            return False
        
        print("\n🚀 Applying database optimizations...")
        
        # Apply optimizations
        success = apply_database_indexes(supabase)
        
        if success:
            print("✅ Database optimizations applied successfully!")
            
            # Test a simple query to verify performance
            print("\n🧪 Testing query performance...")
            try:
                import time
                start_time = time.time()
                
                # Test a simple query
                result = supabase.table('lead_master').select('uid, customer_name').limit(10).execute()
                
                end_time = time.time()
                query_time = (end_time - start_time) * 1000  # Convert to milliseconds
                
                print(f"✅ Test query completed in {query_time:.2f}ms")
                print(f"📊 Retrieved {len(result.data) if result.data else 0} records")
                
            except Exception as e:
                print(f"⚠️  Performance test failed: {e}")
            
            return True
        else:
            print("❌ Failed to apply database optimizations")
            return False
            
    except Exception as e:
        print(f"❌ Error during database optimization: {e}")
        return False

def check_performance_improvements():
    """Check if performance improvements are working"""
    
    try:
        from supabase import create_client, Client
        
        # Initialize Supabase client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")
        
        if not url or not key:
            print("❌ Error: SUPABASE_URL and SUPABASE_ANON_KEY environment variables are required")
            return False
            
        supabase: Client = create_client(url, key)
        
        print("\n📈 Performance Test Results:")
        
        # Test 1: Simple select query
        import time
        
        start_time = time.time()
        result1 = supabase.table('lead_master').select('uid').limit(1).execute()
        end_time = time.time()
        test1_time = (end_time - start_time) * 1000
        
        print(f"✅ Simple select query: {test1_time:.2f}ms")
        
        # Test 2: Filtered query (should use index)
        start_time = time.time()
        result2 = supabase.table('lead_master').select('uid, customer_name').eq('final_status', 'Pending').limit(5).execute()
        end_time = time.time()
        test2_time = (end_time - start_time) * 1000
        
        print(f"✅ Filtered query (final_status): {test2_time:.2f}ms")
        
        # Test 3: Phone number lookup (should use index)
        start_time = time.time()
        result3 = supabase.table('lead_master').select('uid, customer_name').eq('customer_mobile_number', '9876543210').execute()
        end_time = time.time()
        test3_time = (end_time - start_time) * 1000
        
        print(f"✅ Phone number lookup: {test3_time:.2f}ms")
        
        # Performance assessment
        if test1_time < 100 and test2_time < 200 and test3_time < 100:
            print("\n🎉 Excellent performance! All queries are fast.")
            return True
        elif test1_time < 500 and test2_time < 1000 and test3_time < 500:
            print("\n✅ Good performance! Queries are reasonably fast.")
            return True
        else:
            print("\n⚠️  Performance could be better. Consider checking indexes.")
            return False
            
    except Exception as e:
        print(f"❌ Error during performance test: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Database Optimization Test Script")
    print("=" * 50)
    
    # Test database optimization
    success = test_database_optimization()
    
    if success:
        print("\n" + "=" * 50)
        # Check performance improvements
        check_performance_improvements()
        
        print("\n🎯 Next Steps:")
        print("1. Test the optimized lead creation: /add_lead_optimized")
        print("2. Monitor performance: /performance_metrics")
        print("3. Check cache statistics in the performance dashboard")
    else:
        print("\n❌ Database optimization failed. Please check the errors above.")
        sys.exit(1)
