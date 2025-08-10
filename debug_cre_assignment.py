#!/usr/bin/env python3
"""
Debug script to test CRE assignment functionality
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase import create_client, Client

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL_UDAY3') or os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_ANON_KEY_UDAY3') or os.getenv('SUPABASE_ANON_KEY')

if not supabase_url or not supabase_key:
    print("❌ Error: Supabase credentials not found!")
    sys.exit(1)

supabase: Client = create_client(supabase_url, supabase_key)

def test_cre_users():
    """Test if CRE users can be fetched"""
    print("🔍 Testing CRE users fetch...")
    try:
        cre_users = supabase.table('cre_users').select('*').execute()
        print(f"✅ Found {len(cre_users.data)} CRE users:")
        for cre in cre_users.data:
            print(f"  - ID: {cre['id']}, Name: {cre['name']}, Active: {cre.get('is_active', True)}")
        return cre_users.data
    except Exception as e:
        print(f"❌ Error fetching CRE users: {e}")
        return []

def test_lead_master():
    """Test lead_master table structure"""
    print("\n🔍 Testing lead_master table...")
    try:
        # Get recent leads
        leads = supabase.table('lead_master').select('*').order('created_at', desc=True).limit(5).execute()
        print(f"✅ Found {len(leads.data)} recent leads:")
        for lead in leads.data:
            print(f"  - UID: {lead['uid']}, CRE: {lead.get('cre_name', 'None')}, Assigned: {lead.get('assigned', 'None')}")
        return leads.data
    except Exception as e:
        print(f"❌ Error fetching leads: {e}")
        return []

def test_duplicate_leads():
    """Test duplicate_leads table"""
    print("\n🔍 Testing duplicate_leads table...")
    try:
        duplicates = supabase.table('duplicate_leads').select('*').order('created_at', desc=True).limit(5).execute()
        print(f"✅ Found {len(duplicates.data)} duplicate records:")
        for dup in duplicates.data:
            print(f"  - UID: {dup['uid']}, Sources: {dup.get('source1', 'None')}, {dup.get('source2', 'None')}")
        return duplicates.data
    except Exception as e:
        print(f"❌ Error fetching duplicates: {e}")
        return []

def test_cre_assignment():
    """Test CRE assignment logic"""
    print("\n🔍 Testing CRE assignment logic...")
    
    # Get a CRE user
    cre_users = supabase.table('cre_users').select('*').limit(1).execute()
    if not cre_users.data:
        print("❌ No CRE users found!")
        return
    
    cre_user = cre_users.data[0]
    print(f"✅ Using CRE: {cre_user['name']} (ID: {cre_user['id']})")
    
    # Test lead data preparation
    from datetime import datetime
    
    test_lead_data = {
        'uid': 'TEST-1234-5678',
        'customer_name': 'Test Customer',
        'customer_mobile_number': '9876543210',
        'source': 'META',
        'sub_source': 'Meta Know',
        'date': datetime.now().strftime('%Y-%m-%d'),
        'assigned': 'Yes',
        'final_status': 'Pending',
        'cre_name': cre_user['name'],
        'lead_status': 'Pending',
        'lead_category': 'Cold',
        'cre_assigned_at': datetime.now().isoformat(),
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    
    print(f"✅ Test lead data prepared:")
    for key, value in test_lead_data.items():
        print(f"  - {key}: {value}")
    
    return test_lead_data

if __name__ == "__main__":
    print("🚀 Starting CRE assignment debug...")
    print(f"📡 Supabase URL: {supabase_url}")
    print(f"🔑 Supabase Key: {supabase_key[:10]}...")
    
    # Run tests
    cre_users = test_cre_users()
    leads = test_lead_master()
    duplicates = test_duplicate_leads()
    test_data = test_cre_assignment()
    
    print("\n📊 Summary:")
    print(f"  - CRE Users: {len(cre_users)}")
    print(f"  - Recent Leads: {len(leads)}")
    print(f"  - Duplicate Records: {len(duplicates)}")
    
    if leads:
        assigned_leads = [l for l in leads if l.get('cre_name')]
        unassigned_leads = [l for l in leads if not l.get('cre_name')]
        print(f"  - Assigned Leads: {len(assigned_leads)}")
        print(f"  - Unassigned Leads: {len(unassigned_leads)}")
    
    print("\n✅ Debug complete!") 