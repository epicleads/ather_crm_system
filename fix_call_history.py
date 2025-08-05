#!/usr/bin/env python3
"""
Fix call attempt history for existing auto-assigned leads
"""

import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from supabase import create_client
from pytz import timezone

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL_UDAY3')  # Use Uday3 database
supabase_key = os.getenv('SUPABASE_ANON_KEY_UDAY3')
supabase = create_client(supabase_url, supabase_key)

# IST Timezone
IST_TIMEZONE = timezone('Asia/Kolkata')

def get_ist_timestamp():
    """Get current timestamp in IST timezone"""
    return datetime.now(IST_TIMEZONE)

def fix_call_attempt_history():
    """Fix call attempt history for existing auto-assigned leads"""
    print("🔧 Fixing call attempt history for auto-assigned leads...")
    print("=" * 60)
    
    try:
        # Get leads that are assigned but don't have call attempt history
        leads_result = supabase.table('lead_master').select('uid, cre_name, assigned').eq('assigned', True).execute()
        
        if not leads_result.data:
            print("❌ No assigned leads found")
            return
        
        print(f"📊 Found {len(leads_result.data)} assigned leads")
        
        fixed_count = 0
        skipped_count = 0
        
        for lead in leads_result.data:
            lead_uid = lead.get('uid')
            cre_name = lead.get('cre_name')
            
            if not lead_uid or not cre_name:
                print(f"⚠️ Skipping lead {lead_uid}: Missing UID or CRE name")
                skipped_count += 1
                continue
            
            # Check if call attempt history already exists
            existing_history = supabase.table('cre_call_attempt_history').select('id').eq('uid', lead_uid).execute()
            
            if existing_history.data:
                print(f"✅ Lead {lead_uid} already has call history - skipping")
                skipped_count += 1
                continue
            
            # Get CRE ID
            cre_result = supabase.table('cre_users').select('id').eq('name', cre_name).execute()
            if not cre_result.data:
                print(f"⚠️ Skipping lead {lead_uid}: CRE {cre_name} not found")
                skipped_count += 1
                continue
            
            cre_id = cre_result.data[0]['id']
            
            # Create call attempt history record
            call_attempt_data = {
                'uid': lead_uid,
                'call_no': 1,  # First call attempt
                'attempt': 1,   # First attempt
                'status': 'Pending',  # Initial status
                'cre_name': cre_name,
                'cre_id': cre_id,
                'created_at': get_ist_timestamp().isoformat(),
                'update_ts': get_ist_timestamp().isoformat()
            }
            
            supabase.table('cre_call_attempt_history').insert(call_attempt_data).execute()
            print(f"✅ Created call history for {lead_uid} → {cre_name}")
            fixed_count += 1
        
        print("\n" + "=" * 60)
        print("📊 FIX SUMMARY:")
        print(f"✅ Fixed: {fixed_count} leads")
        print(f"⏭️ Skipped: {skipped_count} leads")
        print(f"📱 Total processed: {len(leads_result.data)} leads")
        
    except Exception as e:
        print(f"❌ Error fixing call attempt history: {e}")

def check_call_history_status():
    """Check the status of call attempt history"""
    print("\n🔍 Checking call attempt history status...")
    print("=" * 60)
    
    try:
        # Get all assigned leads
        assigned_leads = supabase.table('lead_master').select('uid, cre_name, assigned').eq('assigned', True).execute()
        
        if not assigned_leads.data:
            print("❌ No assigned leads found")
            return
        
        print(f"📊 Total assigned leads: {len(assigned_leads.data)}")
        
        with_history = 0
        without_history = 0
        
        for lead in assigned_leads.data:
            lead_uid = lead.get('uid')
            
            # Check if call history exists
            history_result = supabase.table('cre_call_attempt_history').select('id').eq('uid', lead_uid).execute()
            
            if history_result.data:
                with_history += 1
            else:
                without_history += 1
                print(f"❌ Missing call history: {lead_uid} → {lead.get('cre_name')}")
        
        print(f"\n📊 CALL HISTORY STATUS:")
        print(f"✅ With call history: {with_history}")
        print(f"❌ Without call history: {without_history}")
        print(f"📱 Total assigned leads: {len(assigned_leads.data)}")
        
    except Exception as e:
        print(f"❌ Error checking call history status: {e}")

def main():
    """Run the fix script"""
    print("🚀 Call Attempt History Fix Script")
    print("=" * 60)
    
    # Check current status
    check_call_history_status()
    
    # Fix missing call history
    fix_call_attempt_history()
    
    # Check status again
    check_call_history_status()

if __name__ == "__main__":
    main() 