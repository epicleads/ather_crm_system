#!/usr/bin/env python3
"""
Debug script for Uday3 branch database and auto-assign system
"""

import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from supabase import create_client

# Load environment variables
load_dotenv()

def test_uday3_database_connection():
    """Test Uday3 database connection"""
    print("🔍 Testing Uday3 Database Connection...")
    print("=" * 50)
    
    try:
        # Use Uday3 database credentials
        supabase_url = os.getenv('SUPABASE_URL_UDAY3')
        supabase_key = os.getenv('SUPABASE_ANON_KEY_UDAY3')
        
        if not supabase_url or not supabase_key:
            print("❌ Missing Uday3 database credentials")
            print("Please check SUPABASE_URL_UDAY3 and SUPABASE_ANON_KEY_UDAY3 secrets")
            return None
        
        print(f"✅ Database URL: {supabase_url[:30]}...")
        print(f"✅ Database Key: {supabase_key[:10]}...")
        
        supabase = create_client(supabase_url, supabase_key)
        
        # Test connection
        result = supabase.table("lead_master").select("id").limit(1).execute()
        print("✅ Uday3 database connection successful!")
        print(f"📊 Found {len(result.data)} records in lead_master table")
        
        return supabase
        
    except Exception as e:
        print(f"❌ Uday3 database connection failed: {e}")
        return None

def check_recent_meta_leads(supabase):
    """Check for recent Meta leads in the database"""
    print("\n🔍 Checking Recent Meta Leads...")
    print("=" * 50)
    
    try:
        # Get leads from last 24 hours
        yesterday = datetime.now() - timedelta(days=1)
        
        result = supabase.table("lead_master").select("*").eq("source", "META").gte("created_at", yesterday.isoformat()).execute()
        
        print(f"📊 Found {len(result.data)} Meta leads in last 24 hours")
        
        if result.data:
            print("\n📋 Recent Meta Leads:")
            for lead in result.data[:5]:  # Show first 5
                print(f"  - {lead.get('uid', 'N/A')} | {lead.get('customer_mobile_number', 'N/A')} | {lead.get('campaign', 'N/A')} | {lead.get('created_at', 'N/A')}")
        else:
            print("❌ No Meta leads found in last 24 hours")
            
        return result.data
        
    except Exception as e:
        print(f"❌ Error checking Meta leads: {e}")
        return []

def check_all_recent_leads(supabase):
    """Check all recent leads regardless of source"""
    print("\n🔍 Checking All Recent Leads...")
    print("=" * 50)
    
    try:
        # Get all leads from last 24 hours
        yesterday = datetime.now() - timedelta(days=1)
        
        result = supabase.table("lead_master").select("*").gte("created_at", yesterday.isoformat()).execute()
        
        print(f"📊 Found {len(result.data)} total leads in last 24 hours")
        
        if result.data:
            print("\n📋 Recent Leads by Source:")
            sources = {}
            for lead in result.data:
                source = lead.get('source', 'Unknown')
                sources[source] = sources.get(source, 0) + 1
            
            for source, count in sources.items():
                print(f"  - {source}: {count} leads")
        else:
            print("❌ No leads found in last 24 hours")
            
        return result.data
        
    except Exception as e:
        print(f"❌ Error checking recent leads: {e}")
        return []

def check_auto_assign_config(supabase):
    """Check auto-assign configuration"""
    print("\n🔍 Checking Auto-Assign Configuration...")
    print("=" * 50)
    
    try:
        # Check cre_auto_assign table
        result = supabase.table("cre_auto_assign").select("*").execute()
        
        print(f"📊 Found {len(result.data)} CRE auto-assign configurations")
        
        if result.data:
            print("\n📋 CRE Auto-Assign Configurations:")
            for config in result.data:
                cre_name = config.get('cre_name', 'N/A')
                sources = config.get('sources', [])
                print(f"  - {cre_name}: {sources}")
        else:
            print("❌ No CRE auto-assign configurations found")
            
        return result.data
        
    except Exception as e:
        print(f"❌ Error checking auto-assign config: {e}")
        return []

def check_unassigned_leads(supabase):
    """Check for unassigned leads"""
    print("\n🔍 Checking Unassigned Leads...")
    print("=" * 50)
    
    try:
        # Get unassigned leads from last 24 hours
        yesterday = datetime.now() - timedelta(days=1)
        
        result = supabase.table("lead_master").select("*").eq("assigned", False).gte("created_at", yesterday.isoformat()).execute()
        
        print(f"📊 Found {len(result.data)} unassigned leads in last 24 hours")
        
        if result.data:
            print("\n📋 Unassigned Leads:")
            for lead in result.data[:5]:  # Show first 5
                print(f"  - {lead.get('uid', 'N/A')} | {lead.get('source', 'N/A')} | {lead.get('customer_mobile_number', 'N/A')}")
        else:
            print("✅ No unassigned leads found (all leads are assigned)")
            
        return result.data
        
    except Exception as e:
        print(f"❌ Error checking unassigned leads: {e}")
        return []

def check_auto_assign_history(supabase):
    """Check auto-assign history"""
    print("\n🔍 Checking Auto-Assign History...")
    print("=" * 50)
    
    try:
        # Check if auto_assign_history table exists and has recent entries
        result = supabase.table("auto_assign_history").select("*").order("created_at", desc=True).limit(10).execute()
        
        print(f"📊 Found {len(result.data)} recent auto-assign history entries")
        
        if result.data:
            print("\n📋 Recent Auto-Assign History:")
            for entry in result.data:
                lead_uid = entry.get('lead_uid', 'N/A')
                cre_name = entry.get('cre_name', 'N/A')
                created_at = entry.get('created_at', 'N/A')
                print(f"  - {lead_uid} → {cre_name} | {created_at}")
        else:
            print("❌ No auto-assign history found")
            
        return result.data
        
    except Exception as e:
        print(f"❌ Error checking auto-assign history: {e}")
        return []

def main():
    """Run all debug tests"""
    print("🚀 Uday3 Database and Auto-Assign Debug Test")
    print("=" * 60)
    
    # Test 1: Database connection
    supabase = test_uday3_database_connection()
    
    if not supabase:
        print("\n❌ Cannot proceed without database connection")
        return
    
    # Test 2: Check recent Meta leads
    meta_leads = check_recent_meta_leads(supabase)
    
    # Test 3: Check all recent leads
    all_leads = check_all_recent_leads(supabase)
    
    # Test 4: Check auto-assign configuration
    auto_assign_config = check_auto_assign_config(supabase)
    
    # Test 5: Check unassigned leads
    unassigned_leads = check_unassigned_leads(supabase)
    
    # Test 6: Check auto-assign history
    auto_assign_history = check_auto_assign_history(supabase)
    
    print("\n" + "=" * 60)
    print("📊 FINAL DIAGNOSIS:")
    
    if not meta_leads:
        print("❌ ISSUE: No Meta leads found in database")
        print("   - Meta script may not be connecting to Uday3 database")
        print("   - Check if SUPABASE_URL_UDAY3 and SUPABASE_ANON_KEY_UDAY3 are correct")
    else:
        print("✅ Meta leads are being inserted into database")
    
    if not auto_assign_config:
        print("❌ ISSUE: No auto-assign configuration found")
        print("   - CRE auto-assign table may be empty")
        print("   - Need to configure which CREs handle which sources")
    else:
        print("✅ Auto-assign configuration exists")
    
    if unassigned_leads and auto_assign_config:
        print("❌ ISSUE: Unassigned leads exist but auto-assign not working")
        print("   - Auto-assign script may not be running")
        print("   - Check auto-assign trigger workflow")
    elif not unassigned_leads:
        print("✅ All leads are assigned (auto-assign working)")
    
    if not auto_assign_history:
        print("❌ ISSUE: No auto-assign history found")
        print("   - Auto-assign script may not be running")
        print("   - Check auto-assign trigger workflow")
    else:
        print("✅ Auto-assign history exists (auto-assign working)")

if __name__ == "__main__":
    main() 