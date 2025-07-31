import os
from simple_salesforce import Salesforce
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
from supabase import create_client, Client
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any

# --- Load environment variables ---
load_dotenv()

SF_USERNAME = os.getenv('SF_USERNAME')
SF_PASSWORD = os.getenv('SF_PASSWORD')
SF_SECURITY_TOKEN = os.getenv('SF_SECURITY_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')

sf = Salesforce(username=SF_USERNAME, password=SF_PASSWORD, security_token=SF_SECURITY_TOKEN)
print("✅ Connected to Salesforce")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✅ Connected to Supabase")

IST = pytz.timezone('Asia/Kolkata')
now_ist = datetime.now(IST)
past_15_minutes = now_ist - timedelta(minutes=15)  # Changed from 24 hours to 15 minutes
start_time = past_15_minutes.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
end_time = now_ist.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

print(f"📅 Fetching leads from {past_15_minutes} IST to {now_ist} IST")

# ===============================================
# DUPLICATE HANDLER CLASS (Embedded)
# ===============================================

class DuplicateLeadsHandler:
    """
    Handles duplicate lead logic for any lead source (META, GOOGLE, BTL, OEM, etc.)
    """
    
    def __init__(self, supabase_client):
        """
        Initialize with Supabase client
        
        Args:
            supabase_client: Initialized Supabase client
        """
        self.supabase = supabase_client
    
    def check_existing_leads(self, phone_numbers: List[str]) -> Tuple[Dict[str, Dict], Dict[str, Dict]]:
        """
        Check for existing leads by phone number in both lead_master and duplicate_leads tables
        
        Args:
            phone_numbers: List of phone numbers to check
            
        Returns:
            Tuple of (master_records, duplicate_records) as dictionaries keyed by phone number
        """
        try:
            # Check lead_master table
            existing_master = self.supabase.table("lead_master").select("*").in_("customer_mobile_number", phone_numbers).execute()
            master_records = {row['customer_mobile_number']: row for row in existing_master.data}
            
            # Check duplicate_leads table
            existing_duplicate = self.supabase.table("duplicate_leads").select("*").in_("customer_mobile_number", phone_numbers).execute()
            duplicate_records = {row['customer_mobile_number']: row for row in existing_duplicate.data}
            
            print(f"📞 Found {len(master_records)} existing in lead_master and {len(duplicate_records)} in duplicate_leads")
            
            return master_records, duplicate_records
            
        except Exception as e:
            print(f"❌ Error checking existing leads: {e}")
            return {}, {}
    
    def is_duplicate_source(self, existing_record: Dict, new_source: str, new_sub_source: str) -> bool:
        """
        Check if the new source/sub_source combination already exists in the record
        
        Args:
            existing_record: Record from either lead_master or duplicate_leads table
            new_source: New source to check
            new_sub_source: New sub_source to check
            
        Returns:
            True if duplicate source combination exists, False otherwise
        """
        # For lead_master, check direct fields
        if 'source' in existing_record and 'sub_source' in existing_record:
            return (existing_record['source'] == new_source and 
                    existing_record['sub_source'] == new_sub_source)
        
        # For duplicate_leads, check all source slots
        for i in range(1, 11):  # source1 to source10
            if (existing_record.get(f'source{i}') == new_source and 
                existing_record.get(f'sub_source{i}') == new_sub_source):
                return True
        
        return False
    
    def find_next_available_source_slot(self, duplicate_record: Dict) -> Optional[int]:
        """
        Find the next available source slot (source1, source2, etc.) in duplicate_leads record
        
        Args:
            duplicate_record: Record from duplicate_leads table
            
        Returns:
            Next available slot number (1-10) or None if all slots are full
        """
        for i in range(1, 11):  # source1 to source10
            if duplicate_record.get(f'source{i}') is None:
                return i
        return None  # All slots are full
    
    def add_source_to_duplicate_record(self, duplicate_record: Dict, new_source: str, 
                                     new_sub_source: str, new_date: str) -> bool:
        """
        Add new source to existing duplicate_leads record
        
        Args:
            duplicate_record: Existing record from duplicate_leads table
            new_source: New source to add
            new_sub_source: New sub_source to add
            new_date: Date of the new lead
            
        Returns:
            True if successfully added, False otherwise
        """
        try:
            slot = self.find_next_available_source_slot(duplicate_record)
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
            
            self.supabase.table("duplicate_leads").update(update_data).eq('id', duplicate_record['id']).execute()
            print(f"✅ Added source{slot} to duplicate record: {duplicate_record['uid']} | Phone: {duplicate_record['customer_mobile_number']} | New Source: {new_source}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to add source to duplicate record: {e}")
            return False
    
    def create_duplicate_record(self, original_record: Dict, new_source: str, 
                              new_sub_source: str, new_date: str) -> bool:
        """
        Create new duplicate_leads record when a lead becomes duplicate
        
        Args:
            original_record: Original record from lead_master table
            new_source: New source that makes this a duplicate
            new_sub_source: New sub_source that makes this a duplicate
            new_date: Date of the new duplicate lead
            
        Returns:
            True if successfully created, False otherwise
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
            
            self.supabase.table("duplicate_leads").insert(duplicate_data).execute()
            print(f"✅ Created duplicate record: {original_record['uid']} | Phone: {original_record['customer_mobile_number']} | Sources: {original_record['source']} + {new_source}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create duplicate record: {e}")
            return False
    
    def process_leads_for_duplicates(self, new_leads_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Process a DataFrame of new leads and handle duplicates
        
        Args:
            new_leads_df: DataFrame containing new leads with columns:
                         ['customer_mobile_number', 'source', 'sub_source', 'date', ...]
                         
        Returns:
            Dictionary with processing results:
            {
                'new_leads': DataFrame of truly new leads to insert,
                'updated_duplicates': int count of duplicate records updated,
                'skipped_duplicates': int count of exact duplicates skipped,
                'master_records': dict of existing master records (for reference),
                'duplicate_records': dict of existing duplicate records (for reference)
            }
        """
        # Check existing records in both tables
        phone_list = new_leads_df['customer_mobile_number'].unique().tolist()
        master_records, duplicate_records = self.check_existing_leads(phone_list)
        
        # Process each lead
        new_leads = []
        updated_duplicates = 0
        skipped_duplicates = 0
        
        for _, row in new_leads_df.iterrows():
            phone = row['customer_mobile_number']
            current_source = row['source']
            current_sub_source = row['sub_source']
            current_date = row['date']
            
            # Check if phone exists in lead_master
            if phone in master_records:
                master_record = master_records[phone]
                
                # Check if this is a duplicate source/sub_source combination
                if self.is_duplicate_source(master_record, current_source, current_sub_source):
                    print(f"⚠️ Skipping duplicate: {phone} | Source: {current_source} | Sub-source: {current_sub_source}")
                    skipped_duplicates += 1
                    continue
                
                # Check if already exists in duplicate_leads
                if phone in duplicate_records:
                    duplicate_record = duplicate_records[phone]
                    
                    # Check if this source/sub_source already exists in duplicate record
                    if self.is_duplicate_source(duplicate_record, current_source, current_sub_source):
                        print(f"⚠️ Skipping duplicate: {phone} | Source: {current_source} | Sub-source: {current_sub_source}")
                        skipped_duplicates += 1
                        continue
                    
                    # Add to existing duplicate record
                    if self.add_source_to_duplicate_record(duplicate_record, current_source, current_sub_source, current_date):
                        updated_duplicates += 1
                        # Update local duplicate_records to avoid conflicts in same batch
                        duplicate_records[phone]['duplicate_count'] += 1
                else:
                    # Create new duplicate record
                    if self.create_duplicate_record(master_record, current_source, current_sub_source, current_date):
                        updated_duplicates += 1
                        # Add to local duplicate_records to avoid conflicts in same batch
                        duplicate_records[phone] = {
                            'customer_mobile_number': phone,
                            'duplicate_count': 2,
                            'source1': master_record['source'],
                            'source2': current_source,
                            'sub_source1': master_record['sub_source'],
                            'sub_source2': current_sub_source
                        }
            else:
                # Completely new lead - add to new_leads list
                new_leads.append(row)
        
        return {
            'new_leads': pd.DataFrame(new_leads) if new_leads else pd.DataFrame(),
            'updated_duplicates': updated_duplicates,
            'skipped_duplicates': skipped_duplicates,
            'master_records': master_records,
            'duplicate_records': duplicate_records
        }

# Initialize the duplicate handler
duplicate_handler = DuplicateLeadsHandler(supabase)

# ===============================================
# UPDATED HELPER FUNCTIONS
# ===============================================

def map_source_and_subsource(raw_source):
    """
    Maps raw source to (source, sub_source) tuple
    All sources now map to 'OEM' with appropriate sub_source
    """
    # Affiliate mapping - exact mapping from Salesforce to database
    affiliate_map = {
        'Bikewale': 'Affiliate Bikewale',
        'Bikewale-Q': 'Affiliate Bikewale',
        'Bikedekho': 'Affiliate Bikedekho',
        'Bikedekho-Q': 'Affiliate Bikedekho',
        '91 Wheels': 'Affiliate 91wheels',
        '91 Wheels-Q': 'Affiliate 91wheels'
    }
    
    # OEM Web sources
    oem_web = {
        'Website', 'Website_PO', 'Website_Optin', 'ai_chatbot', 'website_chatbot',
        'Newspaper Ad - WhatsApp'
    }
    
    # OEM Tele sources  
    oem_tele = {'Telephonic', 'cb', 'ivr_abandoned', 'ivr_callback', 'ivr_sales'}
    
    # Check affiliate mapping first
    if raw_source in affiliate_map:
        return ('OEM', affiliate_map[raw_source])
    elif raw_source in oem_web:
        return ('OEM', 'Web')
    elif raw_source in oem_tele:
        return ('OEM', 'Tele')
    else:
        # Log unmapped sources for debugging
        print(f"⚠️ Unmapped source found: {raw_source}")
        return (None, None)

def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = ''.join(filter(str.isdigit, str(phone)))
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits

def generate_uid(sub_source, mobile_number, sequence):
    """
    Updated UID generation based on sub_source instead of source
    """
    source_map = {
        'Web': 'W', 'Tele': 'T',
        'Affiliate Bikewale': 'B', 'Affiliate Bikedekho': 'D', 'Affiliate 91wheels': 'N'
    }
    
    source_char = source_map.get(sub_source, 'S')
    sequence_char = chr(65 + (sequence % 26))
    mobile_last4 = str(mobile_number).replace(' ', '').replace('-', '')[-4:]
    seq_num = f"{(sequence % 9999) + 1:04d}"
    return f"{source_char}{sequence_char}-{mobile_last4}-{seq_num}"

def get_next_sequence_number(supabase):
    try:
        result = supabase.table("lead_master").select("id").order("id", desc=True).limit(1).execute()
        return result.data[0]['id'] + 1 if result.data else 1
    except Exception as e:
        print(f"❌ Error getting sequence number: {e}")
        return 1

# ===============================================
# MAIN PROCESSING LOGIC
# ===============================================

query = f"""
    SELECT Id, Name, Phone, LeadSource, CreatedDate
    FROM Lead
    WHERE CreatedDate >= {start_time} AND CreatedDate <= {end_time}
"""
results = sf.query_all(query)['records']
print(f"\n📦 Total leads fetched (past 15 minutes): {len(results)}")

if not results:
    print("❌ No leads found in the specified time range")
    exit()

# Process leads with combined sub_sources per phone
leads_by_phone = {}
unmapped_sources = set()  # Track all unmapped sources

for lead in results:
    raw_source = lead.get("LeadSource")
    name = lead.get("Name", "Unknown")
    raw_phone = lead.get("Phone", "")
    created = lead.get("CreatedDate")

    if not raw_source or not raw_phone:
        continue

    source, sub_source = map_source_and_subsource(raw_source)
    if not source or not sub_source:
        unmapped_sources.add(raw_source)
        continue

    phone = normalize_phone(raw_phone)
    if not phone:
        continue

    try:
        created_date = datetime.fromisoformat(created.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        continue

    if phone not in leads_by_phone:
        leads_by_phone[phone] = {
            'name': name,
            'phone': phone,
            'date': created_date,
            'source': source,  # Will always be 'OEM'
            'sub_sources': set()
        }

    leads_by_phone[phone]['sub_sources'].add(sub_source)

# Report unmapped sources if any
if unmapped_sources:
    print(f"\n⚠️ WARNING: Found {len(unmapped_sources)} unmapped sources:")
    for source in sorted(unmapped_sources):
        print(f"   - {source}")
    print("   These leads were skipped. Please update the mapping function if needed.\n")

print(f"📱 Found {len(leads_by_phone)} unique phone numbers")

if not leads_by_phone:
    print("❌ No valid leads to process")
    exit()

# Convert to DataFrame format for duplicate processing
processed_leads = []
current_time = datetime.now().isoformat()

for phone, lead_data in leads_by_phone.items():
    combined_sub_source = ','.join(sorted(lead_data['sub_sources']))
    
    processed_lead = {
        'date': lead_data['date'],
        'customer_name': lead_data['name'],
        'customer_mobile_number': phone,
        'source': lead_data['source'],  # Always 'OEM'
        'sub_source': combined_sub_source,
        'campaign': None,  # Will be preserved from existing records if any
        'cre_name': None,
        'lead_category': None,
        'model_interested': None,
        'branch': None,
        'ps_name': None,
        'assigned': 'No',
        'lead_status': 'Pending',
        'follow_up_date': None,
        'first_call_date': None,
        'first_remark': None,
        'second_call_date': None,
        'second_remark': None,
        'third_call_date': None,
        'third_remark': None,
        'fourth_call_date': None,
        'fourth_remark': None,
        'fifth_call_date': None,
        'fifth_remark': None,
        'sixth_call_date': None,
        'sixth_remark': None,
        'seventh_call_date': None,
        'seventh_remark': None,
        'final_status': 'Pending',
        'created_at': current_time,
        'updated_at': current_time
    }
    processed_leads.append(processed_lead)

# Convert to DataFrame
df_oem_leads = pd.DataFrame(processed_leads)
print(f"📊 Collected {len(df_oem_leads)} leads from Salesforce (OEM)")

# Process duplicates using the handler
print(f"🔄 OEM sync starting with duplicate handling...")
print(f"🎯 Source: OEM | Various sub-sources")
print(f"🎯 Each lead processed individually - duplicate handling active")

results = duplicate_handler.process_leads_for_duplicates(df_oem_leads)

# Handle new leads
new_leads_df = results['new_leads']
master_records = results['master_records']

if new_leads_df.empty:
    print("✅ No new leads to insert.")
else:
    print(f"🆕 Found {len(new_leads_df)} new leads to insert")
    
    # Generate UIDs for new leads
    sequence = get_next_sequence_number(supabase)
    uids = []
    
    for _, row in new_leads_df.iterrows():
        first_sub_source = row['sub_source'].split(',')[0]
        new_uid = generate_uid(first_sub_source, row['customer_mobile_number'], sequence)
        uids.append(new_uid)
        sequence += 1
    
    new_leads_df['uid'] = uids
    
    # Check for UID conflicts and regenerate if needed
    existing_uids_result = supabase.table("lead_master").select("uid").execute()
    existing_uids = {row['uid'] for row in existing_uids_result.data}
    
    uid_conflicts = []
    for i, row in new_leads_df.iterrows():
        if row['uid'] in existing_uids:
            uid_conflicts.append(i)
    
    if uid_conflicts:
        print(f"⚠️ Found {len(uid_conflicts)} UID conflicts, regenerating...")
        sequence_start = get_next_sequence_number(supabase) + 1000
        for i in uid_conflicts:
            row = new_leads_df.iloc[i]
            first_sub_source = row['sub_source'].split(',')[0]
            new_leads_df.at[i, 'uid'] = generate_uid(first_sub_source, row['customer_mobile_number'], sequence_start)
            sequence_start += 1
    
    # Preserve existing campaigns from master records
    for i, row in new_leads_df.iterrows():
        phone = row['customer_mobile_number']
        if phone in master_records and master_records[phone].get('campaign'):
            new_leads_df.at[i, 'campaign'] = master_records[phone]['campaign']
    
    # Select final columns
    final_cols = ['uid', 'date', 'customer_name', 'customer_mobile_number', 'source', 'sub_source', 'campaign',
                  'cre_name', 'lead_category', 'model_interested', 'branch', 'ps_name',
                  'assigned', 'lead_status', 'follow_up_date',
                  'first_call_date', 'first_remark', 'second_call_date', 'second_remark',
                  'third_call_date', 'third_remark', 'fourth_call_date', 'fourth_remark',
                  'fifth_call_date', 'fifth_remark', 'sixth_call_date', 'sixth_remark',
                  'seventh_call_date', 'seventh_remark', 'final_status',
                  'created_at', 'updated_at']
    new_leads_df = new_leads_df[final_cols]
    
    # Insert new leads
    successful_inserts = 0
    failed_inserts = 0
    
    print(f"🚀 Inserting {len(new_leads_df)} new leads...")
    
    for row in new_leads_df.to_dict(orient="records"):
        try:
            supabase.table("lead_master").insert(row).execute()
            print(f"✅ Inserted new lead: {row['uid']} | Phone: {row['customer_mobile_number']} | Sub-source: {row['sub_source']}")
            if row['campaign']:
                print(f"   📊 Campaign preserved: {row['campaign']}")
            successful_inserts += 1
        except Exception as e:
            print(f"❌ Failed to insert {row['uid']} | Phone: {row['customer_mobile_number']}: {e}")
            failed_inserts += 1
    
    print(f"✅ Successfully inserted new leads: {successful_inserts}")
    print(f"❌ Failed insertions: {failed_inserts}")

# Final Summary
print(f"\n📊 SUMMARY:")
print(f"✅ New leads inserted: {len(new_leads_df) if not new_leads_df.empty else 0}")
print(f"🔄 Duplicate records updated/created: {results['updated_duplicates']}")
print(f"⚠️ Skipped exact duplicates: {results['skipped_duplicates']}")
print(f"📱 Total records processed: {len(df_oem_leads)}")
print(f"🎯 Source: OEM | Various sub-sources (Web, Tele, Affiliate Bikewale, etc.)")
print(f"📊 Each lead processed individually with duplicate handling")
print(f"🔄 Duplicates with other sources (META, GOOGLE, BTL, etc.) handled via duplicate_leads table")
print(f"⏰ Time range: Past 15 minutes")

# Final report on unmapped sources
if unmapped_sources:
    print(f"\n⚠️ UNMAPPED SOURCES FOUND:")
    print(f"   {len(unmapped_sources)} unique unmapped sources were skipped")
    print(f"   Please review and update the mapping function if needed")
