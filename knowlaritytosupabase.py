import requests
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load .env credentials
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
KNOW_SR_KEY = os.getenv("KNOW_SR_KEY")
KNOW_X_API_KEY = os.getenv("KNOW_X_API_KEY")

# SR number to source mapping
number_to_source = {
    '+918929841338': 'Google',
    '+917353089911': 'Meta',
    '+919513249906': 'BTL',
    '+918071023606': 'BTL'
}

def generate_uid(source, mobile_number, sequence):
    source_map = {'Google': 'G', 'Meta': 'M', 'Affiliate': 'A', 'Know': 'K', 'Whatsapp': 'W', 'Tele': 'T', 'BTL': 'B'}
    source_char = source_map.get(source, 'X')
    sequence_char = chr(65 + (sequence % 26))
    mobile_last4 = str(mobile_number).replace(" ", "").replace("-", "")[-4:].zfill(4)
    seq_num = f"{(sequence % 9999) + 1:04d}"
    return f"{source_char}{sequence_char}-{mobile_last4}-{seq_num}"

class KnowlarityAPI:
    def __init__(self, sr_key, x_api_key, channel="Basic", base_url="https://kpi.knowlarity.com"):
        self.headers = {
            'channel': channel,
            'x-api-key': x_api_key,
            'authorization': sr_key,
            'content-type': 'application/json',
            'cache-control': 'no-cache'
        }
        self.base_url = base_url
        self.channel = channel

    def get_call_logs(self, start_date, end_date, limit=500):
        url = f"{self.base_url}/{self.channel}/v1/account/calllog"
        headers = self.headers.copy()
        headers.update({
            'start_time': f"{start_date} 00:00:00+05:30",
            'end_time': f"{end_date} 23:59:59+05:30"
        })
        try:
            resp = requests.get(url, headers=headers, params={'limit': limit})
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            print("❌ Request failed:", e)
        return {}

    def extract_records(self, response):
        return response.get('objects', []) if isinstance(response, dict) else []

def check_existing_leads(supabase, phone_numbers):
    """
    Check for existing leads by phone number in the database
    Returns a set of phone numbers that already exist
    """
    try:
        # Convert phone numbers to list for the query
        phone_list = list(phone_numbers)
        
        # Query database for existing phone numbers
        existing = supabase.table("lead_master").select("customer_mobile_number").in_("customer_mobile_number", phone_list).execute()
        
        # Return set of existing phone numbers
        existing_phones = {row['customer_mobile_number'] for row in existing.data}
        print(f"📞 Found {len(existing_phones)} existing phone numbers in database")
        
        return existing_phones
        
    except Exception as e:
        print(f"❌ Error checking existing leads: {e}")
        return set()

def get_next_sequence_number(supabase):
    """
    Get the next sequence number for UID generation
    """
    try:
        # Get the latest record to determine next sequence
        result = supabase.table("lead_master").select("id").order("id", desc=True).limit(1).execute()
        
        if result.data:
            return result.data[0]['id'] + 1
        else:
            return 1
            
    except Exception as e:
        print(f"❌ Error getting sequence number: {e}")
        return 1

def main():
    client = KnowlarityAPI(KNOW_SR_KEY, KNOW_X_API_KEY)
    
    # Get past 24 hours instead of just today
    from datetime import timedelta
    now = datetime.now()
    yesterday = now - timedelta(hours=24)
    
    start_date = yesterday.strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")
    
    print(f"🔍 Fetching call logs from {start_date} to {end_date}")
    records = client.extract_records(client.get_call_logs(start_date, end_date))
    df = pd.DataFrame(records)

    if df.empty:
        print(f"❌ No call logs from {start_date} to {end_date}")
        return

    df = df[df['knowlarity_number'].isin(number_to_source)].copy()
    if df.empty:
        print("⚠ No known SR calls (Google/Meta/BTL) found.")
        return

    df['source'] = df['knowlarity_number'].map(number_to_source)
    df['customer_mobile_number'] = df['customer_number']
    df['customer_name'] = 'No Name(Knowlarity)'
    
    # FIX: Convert date to string format for JSON serialization
    df['date'] = pd.to_datetime(df['start_time']).dt.date.astype(str)
    
    # Remove duplicates within the current batch first
    df = df.drop_duplicates(subset=['customer_mobile_number', 'source']).reset_index(drop=True)
    
    print(f"📊 Found {len(df)} unique leads in current batch")
    
    # Initialize Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # ENHANCED DUPLICATE CHECK: Check for existing phone numbers in database
    phone_numbers = set(df['customer_mobile_number'].tolist())
    existing_phones = check_existing_leads(supabase, phone_numbers)
    
    # Filter out leads that already exist in database
    df_new = df[~df['customer_mobile_number'].isin(existing_phones)].copy()
    
    if df_new.empty:
        print("✅ No new leads to insert. All phone numbers already exist in database.")
        
        # Show which phone numbers were skipped
        skipped_phones = df[df['customer_mobile_number'].isin(existing_phones)]['customer_mobile_number'].tolist()
        print(f"📱 Skipped phone numbers (already exist): {skipped_phones}")
        return
    
    print(f"🆕 Found {len(df_new)} truly new leads to insert")
    
    # Get starting sequence number for UID generation
    sequence_start = get_next_sequence_number(supabase)
    
    # Generate UIDs for new leads only
    df_new['uid'] = [generate_uid(row['source'], row['customer_mobile_number'], sequence_start + idx) 
                     for idx, row in df_new.iterrows()]
    
    # Additional UID uniqueness check (extra safety)
    existing_uids_result = supabase.table("lead_master").select("uid").execute()
    existing_uids = {row['uid'] for row in existing_uids_result.data}
    
    # Re-generate UIDs if any conflicts (shouldn't happen with proper sequence)
    uid_conflicts = df_new[df_new['uid'].isin(existing_uids)]
    if not uid_conflicts.empty:
        print(f"⚠️ Found {len(uid_conflicts)} UID conflicts, regenerating...")
        for idx in uid_conflicts.index:
            sequence_start += 1000  # Jump ahead to avoid conflicts
            df_new.at[idx, 'uid'] = generate_uid(
                df_new.at[idx, 'source'], 
                df_new.at[idx, 'customer_mobile_number'], 
                sequence_start
            )
    
    # FIX: Convert timestamps to ISO format strings for JSON serialization
    current_time = datetime.now().isoformat()
    df_new['created_at'] = df_new['updated_at'] = current_time

    # Add default nulls
    default_fields = {
        'cre_name': None, 'lead_category': None, 'model_interested': None, 'branch': None, 'ps_name': None,
        'assigned': 'No', 'lead_status': 'Pending', 'follow_up_date': None,
        'first_call_date': None, 'first_remark': None, 'second_call_date': None, 'second_remark': None,
        'third_call_date': None, 'third_remark': None, 'fourth_call_date': None, 'fourth_remark': None,
        'fifth_call_date': None, 'fifth_remark': None, 'sixth_call_date': None, 'sixth_remark': None,
        'seventh_call_date': None, 'seventh_remark': None, 'final_status': 'Pending'
    }
    for col, val in default_fields.items():
        df_new[col] = val

    # Select final columns
    final_cols = ['uid', 'date', 'customer_name', 'customer_mobile_number', 'source',
                  'cre_name', 'lead_category', 'model_interested', 'branch', 'ps_name',
                  'assigned', 'lead_status', 'follow_up_date',
                  'first_call_date', 'first_remark', 'second_call_date', 'second_remark',
                  'third_call_date', 'third_remark', 'fourth_call_date', 'fourth_remark',
                  'fifth_call_date', 'fifth_remark', 'sixth_call_date', 'sixth_remark',
                  'seventh_call_date', 'seventh_remark', 'final_status',
                  'created_at', 'updated_at']
    df_new = df_new[final_cols]

    print(f"🚀 Inserting {len(df_new)} new leads...")
    
    # Insert new leads
    successful_inserts = 0
    failed_inserts = 0
    
    for row in df_new.to_dict(orient="records"):
        try:
            supabase.table("lead_master").insert(row).execute()
            print(f"✅ Inserted UID: {row['uid']} | Phone: {row['customer_mobile_number']}")
            successful_inserts += 1
        except Exception as e:
            print(f"❌ Failed to insert {row['uid']} | Phone: {row['customer_mobile_number']}: {e}")
            failed_inserts += 1
    
    # Summary
    print(f"\n📊 SUMMARY:")
    print(f"✅ Successfully inserted: {successful_inserts}")
    print(f"❌ Failed insertions: {failed_inserts}")
    print(f"📱 Duplicate phone numbers skipped: {len(existing_phones)}")
    print(f"🎯 Total leads processed: {len(df)}")

if __name__ == "__main__":
    main()