import requests
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load .env credentials
load_dotenv()

# UDAY3 Branch Testing - Prioritize UDAY3 variables
SUPABASE_URL = os.getenv('SUPABASE_URL_UDAY3') or os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY_UDAY3') or os.getenv("SUPABASE_ANON_KEY")

# Log which environment we're using
if os.getenv('SUPABASE_URL_UDAY3'):
    print("🔧 UDAY3 BRANCH: Using Uday3 database credentials")
else:
    print("🔧 FALLBACK: Using main database credentials")

KNOW_SR_KEY = os.getenv("KNOW_SR_KEY")
KNOW_X_API_KEY = os.getenv("KNOW_X_API_KEY")

# UPDATED: SR number to source mapping with clean source names and sub_source
number_to_source_mapping = {
    '+918929841338': {'source': 'META', 'sub_source': 'Meta Know'},
    '+917353089911': {'source': 'GOOGLE', 'sub_source': 'Google Know'},
    '+919513249906': {'source': 'BTL', 'sub_source': 'BTL Know'},
    '+918071023606': {'source': 'BTL', 'sub_source': 'BTL Know'}
}

def generate_uid(source, mobile_number, sequence):
    source_map = {'GOOGLE': 'G', 'META': 'M', 'Affiliate': 'A', 'Know': 'K', 'Whatsapp': 'W', 'Tele': 'T', 'BTL': 'B'}
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

    def test_api_connection(self):
        """Test API connection with minimal parameters"""
        url = f"{self.base_url}/{self.channel}/v1/account/calllog"
        
        # Test with just limit parameter
        params = {'limit': 5}
        
        try:
            resp = requests.get(url, headers=self.headers, params=params)
            print(f"🧪 Test API Status: {resp.status_code}")
            
            if resp.status_code == 200:
                result = resp.json()
                print(f"📊 Test Result: {result.get('meta', {})}")
                return True
            else:
                print(f"❌ Test Failed: {resp.text}")
                return False
                
        except Exception as e:
            print(f"❌ Test Exception: {e}")
            return False

    def get_call_logs(self, start_date, end_date, limit=500):
        url = f"{self.base_url}/{self.channel}/v1/account/calllog"
        
        # FIXED: Put date parameters in query params, not headers
        params = {
            'start_time': f"{start_date} 00:00:00+05:30",
            'end_time': f"{end_date} 23:59:59+05:30",
            'limit': limit
        }
        
        print(f"🔍 API Request Details:")
        print(f"URL: {url}")
        print(f"Params: {params}")
        print(f"Headers: {self.headers}")
        
        try:
            resp = requests.get(url, headers=self.headers, params=params)
            print(f"📡 Response Status: {resp.status_code}")
            
            if resp.status_code == 200:
                json_response = resp.json()
                print(f"📊 Total records found: {json_response.get('meta', {}).get('total_count', 0)}")
                return json_response
            else:
                print(f"❌ API Error: {resp.status_code}")
                print(f"Response: {resp.text}")
                
                # Try POST method as fallback
                print("🔄 Trying POST method as fallback...")
                return self.get_call_logs_post(start_date, end_date, limit)
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return {}

    def get_call_logs_post(self, start_date, end_date, limit=500):
        """Fallback POST method"""
        url = f"{self.base_url}/{self.channel}/v1/account/calllog"
        
        # Try POST method with JSON body
        payload = {
            'start_time': f"{start_date} 00:00:00+05:30",
            'end_time': f"{end_date} 23:59:59+05:30",
            'limit': limit
        }
        
        try:
            resp = requests.post(url, headers=self.headers, json=payload)
            print(f"📡 POST Response Status: {resp.status_code}")
            
            if resp.status_code == 200:
                json_response = resp.json()
                print(f"📊 POST Total records found: {json_response.get('meta', {}).get('total_count', 0)}")
                return json_response
            else:
                print(f"❌ POST Error: {resp.status_code} - {resp.text}")
                return {}
                
        except Exception as e:
            print(f"❌ POST Request failed: {e}")
            return {}

    def extract_records(self, response):
        return response.get('objects', []) if isinstance(response, dict) else []

def check_existing_leads(supabase, df_leads):
    """
    Check for existing leads by phone number in both lead_master and duplicate_leads tables
    """
    try:
        phone_list = df_leads['customer_mobile_number'].unique().tolist()
        
        # Check lead_master table
        existing_master = supabase.table("lead_master").select("*").in_("customer_mobile_number", phone_list).execute()
        master_records = {row['customer_mobile_number']: row for row in existing_master.data}
        
        # Check duplicate_leads table
        existing_duplicate = supabase.table("duplicate_leads").select("*").in_("customer_mobile_number", phone_list).execute()
        duplicate_records = {row['customer_mobile_number']: row for row in existing_duplicate.data}
        
        print(f"📞 Found {len(master_records)} existing in lead_master and {len(duplicate_records)} in duplicate_leads")
        
        return master_records, duplicate_records
        
    except Exception as e:
        print(f"❌ Error checking existing leads: {e}")
        return {}, {}

def get_next_sequence_number(supabase):
    """
    Get the next sequence number for UID generation
    """
    try:
        result = supabase.table("lead_master").select("id").order("id", desc=True).limit(1).execute()
        if result.data:
            return result.data[0]['id'] + 1
        else:
            return 1
    except Exception as e:
        print(f"❌ Error getting sequence number: {e}")
        return 1

def process_individual_leads(df):
    """
    Process leads individually - no consolidation at all
    Each record becomes a separate lead entry
    """
    result_leads = []
    
    for _, row in df.iterrows():
        # Each row becomes an individual lead
        lead_record = row.copy()
        print(f"📱 Processing: {row['customer_mobile_number']} | Source: {row['source']} | Sub-source: {row['sub_source']}")
        result_leads.append(lead_record)
    
    return pd.DataFrame(result_leads)

def find_next_available_source_slot(duplicate_record):
    """
    Find the next available source slot (source1, source2, etc.) in duplicate_leads record
    """
    for i in range(1, 11):  # source1 to source10
        if duplicate_record.get(f'source{i}') is None:
            return i
    return None  # All slots are full

def add_source_to_duplicate_record(supabase, duplicate_record, new_source, new_sub_source, new_date):
    """
    Add new source to existing duplicate_leads record
    """
    try:
        slot = find_next_available_source_slot(duplicate_record)
        if slot is None:
            print(f"⚠️ All source slots full for phone: {duplicate_record['customer_mobile_number']}")
            return False
        
        # Update the record with new source in the available slot
        update_data = {
            f'source{slot}': new_source,
            f'sub_source{slot}': new_sub_source,
            f'date{slot}': new_date,
            'duplicate_count': duplicate_record['duplicate_count'] + 1,
            'updated_at': datetime.now().isoformat()
        }
        
        supabase.table("duplicate_leads").update(update_data).eq('id', duplicate_record['id']).execute()
        print(f"✅ Added source{slot} to duplicate record: {duplicate_record['uid']} | Phone: {duplicate_record['customer_mobile_number']} | New Source: {new_source}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to add source to duplicate record: {e}")
        return False

def create_duplicate_record(supabase, original_record, new_source, new_sub_source, new_date):
    """
    Create new duplicate_leads record when a lead becomes duplicate
    """
    try:
        duplicate_data = {
            'uid': original_record['uid'],
            'customer_mobile_number': original_record['customer_mobile_number'],
            'customer_name': original_record['customer_name'],
            'original_lead_id': original_record['id'],
            'source1': original_record['source'],
            'sub_source1': original_record['sub_source'],
            'date1': original_record['date'],
            'source2': new_source,
            'sub_source2': new_sub_source,
            'date2': new_date,
            'duplicate_count': 2,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Initialize remaining slots as None
        for i in range(3, 11):
            duplicate_data[f'source{i}'] = None
            duplicate_data[f'sub_source{i}'] = None
            duplicate_data[f'date{i}'] = None
        
        supabase.table("duplicate_leads").insert(duplicate_data).execute()
        print(f"✅ Created duplicate record: {original_record['uid']} | Phone: {original_record['customer_mobile_number']} | Sources: {original_record['source']} + {new_source}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create duplicate record: {e}")
        return False

def is_duplicate_source(existing_record, new_source, new_sub_source):
    """
    Check if the new source/sub_source combination already exists in the record
    """
    # For lead_master, check direct fields
    if 'source' in existing_record:
        return (existing_record['source'] == new_source and 
                existing_record['sub_source'] == new_sub_source)
    
    # For duplicate_leads, check all source slots
    for i in range(1, 11):
        if (existing_record.get(f'source{i}') == new_source and 
            existing_record.get(f'sub_source{i}') == new_sub_source):
            return True
    
    return False

def main():
    # Validate credentials first
    if not KNOW_SR_KEY or not KNOW_X_API_KEY:
        print("❌ Missing API credentials in environment variables")
        print(f"KNOW_SR_KEY: {'✅' if KNOW_SR_KEY else '❌'}")
        print(f"KNOW_X_API_KEY: {'✅' if KNOW_X_API_KEY else '❌'}")
        print(f"SUPABASE_URL: {'✅' if SUPABASE_URL else '❌'}")
        print(f"SUPABASE_KEY: {'✅' if SUPABASE_KEY else '❌'}")
        return
    
    print(f"🔑 API Credentials loaded successfully")
    
    client = KnowlarityAPI(KNOW_SR_KEY, KNOW_X_API_KEY)
    
    # Test connection first
    print("🧪 Testing API connection...")
    if not client.test_api_connection():
        print("❌ API connection test failed - check your credentials and network")
        return
    
    print("✅ API connection successful!")
    
    # Get past 24 hours
    now = datetime.now()
    yesterday = now - timedelta(hours=24)
    
    start_date = yesterday.strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")
    
    print(f"🔍 Fetching call logs from {start_date} to {end_date}")
    print(f"🎯 Enhanced duplicate handling - new duplicates go to duplicate_leads table")
    
    records = client.extract_records(client.get_call_logs(start_date, end_date))
    df = pd.DataFrame(records)

    if df.empty:
        print(f"❌ No call logs from {start_date} to {end_date}")
        return

    df = df[df['knowlarity_number'].isin(number_to_source_mapping)].copy()
    if df.empty:
        print("⚠ No known SR calls (Google/Meta/BTL) found.")
        return

    # Map to source and sub_source
    df['source'] = df['knowlarity_number'].map(lambda x: number_to_source_mapping[x]['source'])
    df['sub_source'] = df['knowlarity_number'].map(lambda x: number_to_source_mapping[x]['sub_source'])
    
    df['customer_mobile_number'] = df['customer_number']
    df['customer_name'] = 'No Name(Knowlarity)'
    df['date'] = pd.to_datetime(df['start_time']).dt.date.astype(str)
    
    # Process leads individually - no consolidation
    df_processed = process_individual_leads(df)
    
    print(f"📊 Found {len(df_processed)} individual lead records")
    
    # Initialize Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Check existing records in both tables
    master_records, duplicate_records = check_existing_leads(supabase, df_processed)
    
    # Process each lead with enhanced duplicate handling
    new_leads = []
    updated_duplicates = 0
    skipped_duplicates = 0
    
    print(f"\n🔄 Processing leads with duplicate handling logic:")
    print(f"   • New phone numbers → lead_master")
    print(f"   • Existing phones with new sources → duplicate_leads")
    print(f"   • Exact source/sub_source matches → skipped")
    
    for _, row in df_processed.iterrows():
        phone = row['customer_mobile_number']
        current_source = row['source']
        current_sub_source = row['sub_source']
        current_date = row['date']
        
        print(f"\n📱 Processing: {phone} | Source: {current_source} | Sub-source: {current_sub_source}")
        
        # Check if phone exists in lead_master
        if phone in master_records:
            master_record = master_records[phone]
            print(f"   📋 Found existing lead in lead_master: {master_record['uid']}")
            
            # Check if this is a duplicate source/sub_source combination
            if is_duplicate_source(master_record, current_source, current_sub_source):
                print(f"   ⚠️ Exact duplicate - skipping (same source/sub_source combination)")
                skipped_duplicates += 1
                continue
            
            print(f"   🔄 Different source detected - handling as duplicate")
            
            # Check if already exists in duplicate_leads
            if phone in duplicate_records:
                duplicate_record = duplicate_records[phone]
                print(f"   📋 Found existing duplicate record: {duplicate_record['uid']}")
                
                # Check if this source/sub_source already exists in duplicate record
                if is_duplicate_source(duplicate_record, current_source, current_sub_source):
                    print(f"   ⚠️ Source already exists in duplicate record - skipping")
                    skipped_duplicates += 1
                    continue
                
                # Add to existing duplicate record
                print(f"   ➕ Adding new source to existing duplicate record")
                if add_source_to_duplicate_record(supabase, duplicate_record, current_source, current_sub_source, current_date):
                    updated_duplicates += 1
                    # Update local duplicate_records to avoid conflicts in same batch
                    duplicate_records[phone]['duplicate_count'] += 1
            else:
                # Create new duplicate record
                print(f"   🆕 Creating new duplicate record")
                if create_duplicate_record(supabase, master_record, current_source, current_sub_source, current_date):
                    updated_duplicates += 1
                    # Add to local duplicate_records to avoid conflicts in same batch
                    duplicate_records[phone] = {
                        'customer_mobile_number': phone,
                        'duplicate_count': 2,
                        'source1': master_record['source'],
                        'source2': current_source,
                        'sub_source1': master_record['sub_source'],
                        'sub_source2': current_sub_source,
                        'uid': master_record['uid']
                    }
        else:
            # Completely new lead - add to new_leads list
            print(f"   🆕 New phone number - will add to lead_master")
            new_leads.append(row)
    
    # Process new leads
    if not new_leads:
        print("\n✅ No new leads to insert.")
    else:
        df_new = pd.DataFrame(new_leads)
        print(f"\n🆕 Processing {len(df_new)} new leads for lead_master insertion")
        
        # Generate UIDs for new leads
        sequence = get_next_sequence_number(supabase)
        uids = []
        
        for _, row in df_new.iterrows():
            new_uid = generate_uid(row['source'], row['customer_mobile_number'], sequence)
            uids.append(new_uid)
            sequence += 1
        
        df_new['uid'] = uids
        
        # Add timestamps and default fields
        current_time = datetime.now().isoformat()
        df_new['created_at'] = df_new['updated_at'] = current_time
        
        # Add default fields - no campaign for Knowlarity leads
        default_fields = {
            'campaign': None,
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
        final_cols = ['uid', 'date', 'customer_name', 'customer_mobile_number', 'source', 'sub_source', 'campaign',
                      'cre_name', 'lead_category', 'model_interested', 'branch', 'ps_name',
                      'assigned', 'lead_status', 'follow_up_date',
                      'first_call_date', 'first_remark', 'second_call_date', 'second_remark',
                      'third_call_date', 'third_remark', 'fourth_call_date', 'fourth_remark',
                      'fifth_call_date', 'fifth_remark', 'sixth_call_date', 'sixth_remark',
                      'seventh_call_date', 'seventh_remark', 'final_status',
                      'created_at', 'updated_at']
        df_new = df_new[final_cols]
        
        # Insert new leads
        successful_inserts = 0
        failed_inserts = 0
        
        print(f"\n📥 Inserting new leads into lead_master:")
        for row in df_new.to_dict(orient="records"):
            try:
                supabase.table("lead_master").insert(row).execute()
                print(f"   ✅ {row['uid']} | {row['customer_mobile_number']} | {row['source']} | {row['sub_source']}")
                successful_inserts += 1
            except Exception as e:
                print(f"   ❌ Failed {row['uid']} | {row['customer_mobile_number']}: {e}")
                failed_inserts += 1
        
        print(f"\n✅ Successfully inserted new leads: {successful_inserts}")
        if failed_inserts > 0:
            print(f"❌ Failed insertions: {failed_inserts}")
    
    # Enhanced Summary
    print(f"\n" + "="*60)
    print(f"📊 KNOWLARITY SYNC SUMMARY - ENHANCED DUPLICATE HANDLING")
    print(f"="*60)
    print(f"🆕 New leads inserted into lead_master: {len(new_leads) if new_leads else 0}")
    print(f"🔄 Duplicate records updated/created: {updated_duplicates}")
    print(f"⚠️ Skipped exact duplicates: {skipped_duplicates}")
    print(f"📱 Total records processed: {len(df_processed)}")
    print(f"🎯 Source mapping: Google Know, Meta Know, BTL Know")
    print(f"📋 Duplicate handling:")
    print(f"   • New phones → lead_master")
    print(f"   • Duplicate phones + different sources → duplicate_leads")
    print(f"   • Exact source/sub_source matches → skipped")
    print(f"="*60)

if __name__ == "__main__":
    main()
