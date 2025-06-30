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

# SR number to source mapping - UPDATED
number_to_source = {
    '+918929841338': 'Meta(KNOW)',
    '+917353089911': 'Google(KNOW)',
    '+919513249906': 'BTL(KNOW)',
    '+918071023606': 'BTL(KNOW)'
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

def check_existing_leads(supabase, df_leads):
    """
    Check for existing leads by phone number in the database
    Returns a dictionary with phone_number as key and existing record data as value
    """
    try:
        # Get unique phone numbers from the current batch
        phone_list = df_leads['customer_mobile_number'].unique().tolist()
        
        # Query database for existing phone numbers - now include campaign column
        existing = supabase.table("lead_master").select("*").in_("customer_mobile_number", phone_list).execute()
        
        # Return dictionary with phone number as key and record data as value
        existing_records = {row['customer_mobile_number']: row for row in existing.data}
        print(f"📞 Found {len(existing_records)} existing phone numbers in database")
        
        return existing_records
        
    except Exception as e:
        print(f"❌ Error checking existing leads: {e}")
        return {}

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

def combine_sources_for_phone_number(df):
    """
    Combine multiple sources for the same phone number into a single row
    """
    # Group by phone number and combine sources
    grouped = df.groupby('customer_mobile_number').agg({
        'source': lambda x: ','.join(sorted(x.unique())),
        'date': 'first',  # Use the first date
        'customer_name': 'first',
        'start_time': 'first'  # Keep other fields from first occurrence
    }).reset_index()
    
    print(f"📱 Consolidated {len(df)} records into {len(grouped)} unique phone numbers")
    
    return grouped

def generate_uid_for_leads(supabase, df_leads):
    """
    Generate UIDs for new leads, reusing existing UIDs for same phone numbers
    """
    uids = []
    sequence = get_next_sequence_number(supabase)
    
    existing_records = check_existing_leads(supabase, df_leads)
    
    for _, row in df_leads.iterrows():
        phone = row['customer_mobile_number']
        
        if phone in existing_records:
            # Reuse existing UID
            existing_uid = existing_records[phone]['uid']
            uids.append(existing_uid)
            print(f"🔄 Reusing UID {existing_uid} for existing phone: {phone}")
        else:
            # Generate new UID
            # Use the first source for UID generation (since sources are combined)
            first_source = row['source'].split(',')[0].replace('(KNOW)', '')
            new_uid = generate_uid(first_source, phone, sequence)
            uids.append(new_uid)
            sequence += 1
            print(f"🆕 Generated new UID {new_uid} for phone: {phone}")
    
    return uids

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
    
    # NEW: Combine sources for same phone numbers
    df_combined = combine_sources_for_phone_number(df)
    
    print(f"📊 Found {len(df_combined)} unique phone numbers with combined sources")
    
    # Initialize Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Check existing records
    existing_records = check_existing_leads(supabase, df_combined)
    
    # Separate new leads from existing leads that need source updates
    new_leads = []
    update_leads = []
    
    for _, row in df_combined.iterrows():
        phone = row['customer_mobile_number']
        new_sources = set(row['source'].split(','))
        
        if phone in existing_records:
            # Check if we need to update sources
            existing_record = existing_records[phone]
            existing_sources = set(existing_record['source'].split(','))
            
            # If there are new sources not in existing record
            if not new_sources.issubset(existing_sources):
                combined_sources = existing_sources.union(new_sources)
                
                # IMPORTANT: Preserve existing campaign if it exists
                existing_campaign = existing_record.get('campaign', None)
                
                update_leads.append({
                    'phone': phone,
                    'uid': existing_record['uid'],
                    'id': existing_record['id'],
                    'new_source': ','.join(sorted(combined_sources)),
                    'existing_campaign': existing_campaign  # Keep existing campaign
                })
                print(f"🔄 Will update sources for {phone}: {existing_record['source']} → {','.join(sorted(combined_sources))}")
                if existing_campaign:
                    print(f"   📊 Preserving existing campaign: {existing_campaign}")
            else:
                print(f"✅ Phone {phone} already has all sources: {existing_record['source']}")
        else:
            # Completely new lead
            new_leads.append(row)
    
    # Convert new leads back to DataFrame
    df_new = pd.DataFrame(new_leads) if new_leads else pd.DataFrame()
    
    # Process updates first
    if update_leads:
        print(f"🔄 Updating {len(update_leads)} existing records with new sources...")
        for update in update_leads:
            try:
                # Update only source, preserve existing campaign
                update_data = {
                    'source': update['new_source'],
                    'updated_at': datetime.now().isoformat()
                }
                # Don't update campaign field - it should remain as is
                
                supabase.table("lead_master").update(update_data).eq('id', update['id']).execute()
                print(f"✅ Updated UID: {update['uid']} | Phone: {update['phone']} | Sources: {update['new_source']}")
                if update['existing_campaign']:
                    print(f"   📊 Campaign preserved: {update['existing_campaign']}")
            except Exception as e:
                print(f"❌ Failed to update {update['phone']}: {e}")
    
    # Process new leads
    if df_new.empty:
        print("✅ No completely new leads to insert.")
        if not update_leads:
            print("✅ All phone numbers already exist with same sources.")
        return
    
    print(f"🆕 Found {len(df_new)} completely new leads to insert")
    
    # Generate UIDs for new leads
    df_new['uid'] = generate_uid_for_leads(supabase, df_new)
    
    # Additional UID uniqueness check (extra safety)
    existing_uids_result = supabase.table("lead_master").select("uid").execute()
    existing_uids = {row['uid'] for row in existing_uids_result.data}
    
    uid_conflicts = df_new[df_new['uid'].isin(existing_uids)]
    if not uid_conflicts.empty:
        print(f"⚠️ Found {len(uid_conflicts)} UID conflicts, regenerating...")
        sequence_start = get_next_sequence_number(supabase) + 1000  # Jump ahead to avoid conflicts
        for idx in uid_conflicts.index:
            first_source = df_new.at[idx, 'source'].split(',')[0].replace('(KNOW)', '')
            df_new.at[idx, 'uid'] = generate_uid(
                first_source, 
                df_new.at[idx, 'customer_mobile_number'], 
                sequence_start
            )
            sequence_start += 1
    
    # FIX: Convert timestamps to ISO format strings for JSON serialization
    current_time = datetime.now().isoformat()
    df_new['created_at'] = df_new['updated_at'] = current_time

    # Add default nulls including campaign column
    default_fields = {
        'campaign': None,  # NEW: Campaign column - empty for Knowlarity leads
        'cre_name': None, 'lead_category': None, 'model_interested': None, 'branch': None, 'ps_name': None,
        'assigned': 'No', 'lead_status': 'Pending', 'follow_up_date': None,
        'first_call_date': None, 'first_remark': None, 'second_call_date': None, 'second_remark': None,
        'third_call_date': None, 'third_remark': None, 'fourth_call_date': None, 'fourth_remark': None,
        'fifth_call_date': None, 'fifth_remark': None, 'sixth_call_date': None, 'sixth_remark': None,
        'seventh_call_date': None, 'seventh_remark': None, 'final_status': 'Pending'
    }
    for col, val in default_fields.items():
        df_new[col] = val

    # Select final columns - include campaign column
    final_cols = ['uid', 'date', 'customer_name', 'customer_mobile_number', 'source', 'campaign',  # Added campaign
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
            print(f"✅ Inserted UID: {row['uid']} | Phone: {row['customer_mobile_number']} | Sources: {row['source']} | Campaign: {row['campaign'] or 'None'}")
            successful_inserts += 1
        except Exception as e:
            print(f"❌ Failed to insert {row['uid']} | Phone: {row['customer_mobile_number']}: {e}")
            failed_inserts += 1
    
    # Summary
    print(f"\n📊 SUMMARY:")
    print(f"✅ Successfully inserted new leads: {successful_inserts}")
    print(f"❌ Failed insertions: {failed_inserts}")
    print(f"🔄 Updated existing records with new sources: {len(update_leads)}")
    print(f"📱 Total unique phone numbers processed: {len(df_combined)}")
    print(f"📊 Campaign info: Knowlarity leads have empty campaign (compatible with Meta campaign data)")

if __name__ == "__main__":
    main()