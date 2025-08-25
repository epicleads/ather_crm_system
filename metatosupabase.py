import os, requests, time, json, hashlib, threading
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Set, Optional, Tuple
import pandas as pd

# Environment setup
load_dotenv()
PAGE_TOKEN, PAGE_ID, SUPA_URL, SUPA_KEY = [os.getenv(k) for k in ["META_PAGE_ACCESS_TOKEN", "PAGE_ID", "SUPABASE_URL", "SUPABASE_ANON_KEY"]]
if not all([PAGE_TOKEN, PAGE_ID, SUPA_URL, SUPA_KEY]):
    raise SystemExit("❌ Check .env – missing values!")

supabase = create_client(SUPA_URL, SUPA_KEY)
_sequence_lock = threading.Lock()
_sequence_cache = None

def normalize_phone_number(phone: str) -> str:
    """Normalize phone to 10-digit format"""
    if not phone:
        return ""
    digits = ''.join(filter(str.isdigit, str(phone)))
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits

def generate_uid(source, mobile_number, sequence):
    """Generate UID following the same pattern as Knowlarity script"""
    source_map = {'GOOGLE': 'G', 'META': 'M', 'Affiliate': 'A', 'Know': 'K', 'Whatsapp': 'W', 'Tele': 'T', 'BTL': 'B'}
    source_char = source_map.get(source, 'X')
    sequence_char = chr(65 + (sequence % 26))
    mobile_last4 = str(mobile_number).replace(" ", "").replace("-", "")[-4:].zfill(4)
    seq_num = f"{(sequence % 9999) + 1:04d}"
    return f"{source_char}{sequence_char}-{mobile_last4}-{seq_num}"

def get_next_sequence_number(supabase):
    """Get the next sequence number for UID generation"""
    try:
        result = supabase.table("lead_master").select("id").order("id", desc=True).limit(1).execute()
        if result.data:
            return result.data[0]['id'] + 1
        else:
            return 1
    except Exception as e:
        print(f"❌ Error getting sequence number: {e}")
        return 1

def check_existing_leads(supabase, df_leads):
    """Check for existing leads by phone number in both lead_master and duplicate_leads tables"""
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

def find_next_available_source_slot(duplicate_record):
    """Find the next available source slot (source1, source2, etc.) in duplicate_leads record"""
    for i in range(1, 11):  # source1 to source10
        if duplicate_record.get(f'source{i}') is None:
            return i
    return None  # All slots are full

def add_source_to_duplicate_record(supabase, duplicate_record, new_source, new_sub_source, new_date):
    """Add new source to existing duplicate_leads record"""
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
    """Create new duplicate_leads record when a lead becomes duplicate"""
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
    """Check if the new source/sub_source combination already exists in the record"""
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

def insert_lead_safely(supabase, lead_data):
    """Insert lead with duplicate check at database level"""
    try:
        # First, check if this exact combination already exists
        existing = supabase.table("lead_master").select("id").eq(
            "customer_mobile_number", lead_data['customer_mobile_number']
        ).eq("source", lead_data['source']).eq("sub_source", lead_data['sub_source']).execute()
        
        if existing.data:
            print(f"⚠️ Database-level duplicate detected: {lead_data['customer_mobile_number']} | {lead_data['source']} | {lead_data['sub_source']}")
            return False
        
        # Insert if no duplicate found
        supabase.table("lead_master").insert(lead_data).execute()
        return True
        
    except Exception as e:
        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
            print(f"🛡️ Database constraint prevented duplicate: {lead_data['customer_mobile_number']}")
            return False
        else:
            print(f"❌ Database error: {e}")
            return False

class MetaAPIOptimized:
    def __init__(self, page_token: str, max_workers: int = 5):
        self.page_token = page_token
        self.max_workers = max_workers
        self.session = requests.Session()
        self._campaign_cache = {}
        self.api_version = "v18.0"
    
    def _make_request(self, url: str, params: dict = None) -> dict:
        """Make API request with error handling"""
        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"⚠️ API error: {e}")
            return {}
    
    def get_campaign_name_safe(self, form_id: str, form_name: str) -> str:
        """Get campaign name safely from form name"""
        if form_id in self._campaign_cache:
            return self._campaign_cache[form_id]
        
        cleaned = form_name.strip().replace('@', 'at').replace('&', 'and').replace('-copy', '').replace('_copy', '').replace('  ', ' ')
        try:
            cleaned = ' '.join(word.capitalize() for word in cleaned.split())
        except:
            pass
        
        self._campaign_cache[form_id] = cleaned or "Unknown Campaign"
        return self._campaign_cache[form_id]
    
    def get_paginated_optimized(self, endpoint: str, **params) -> List[dict]:
        """Get paginated data with early termination"""
        params["access_token"] = self.page_token
        params["limit"] = 100
        
        all_data = []
        next_url = f"https://graph.facebook.com/{self.api_version}/{endpoint}"
        consecutive_old_pages = 0
        
        while next_url and consecutive_old_pages < 3:
            response = self._make_request(next_url, params if not next_url.startswith("https://") or not all_data else None)
            
            if not response or "data" not in response:
                break
            
            page_data = response["data"]
            if not page_data:
                break
            
            if "leads" in endpoint:
                recent_data = [item for item in page_data if self._is_within_past_24_hours(item.get("created_time", ""))]
                all_data.extend(recent_data)
                
                if not recent_data:
                    consecutive_old_pages += 1
                else:
                    consecutive_old_pages = 0
                    
                if consecutive_old_pages >= 3:
                    break
            else:
                all_data.extend(page_data)
            
            next_url = response.get("paging", {}).get("next")
            if next_url:
                params = {}
            else:
                break
        
        return all_data
    
    def _is_within_past_24_hours(self, created_time_str: str) -> bool:
        """Check if timestamp is within past 24 hours"""
        if not created_time_str:
            return False
        
        formats = ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]
        
        for fmt in formats:
            try:
                created_time = datetime.strptime(created_time_str, fmt)
                if created_time.tzinfo:
                    created_time_utc = created_time.astimezone(timezone.utc).replace(tzinfo=None)
                else:
                    created_time_utc = created_time
                
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                return (now - timedelta(hours=24)) <= created_time_utc <= now
            except ValueError:
                continue
        return False
    
    def get_forms_with_campaign_info_safe(self) -> List[dict]:
        """Get forms with campaign info"""
        if not hasattr(self, '_enhanced_forms_cache'):
            base_forms = self._make_request(
                f"https://graph.facebook.com/{self.api_version}/{PAGE_ID}/leadgen_forms",
                {"access_token": self.page_token, "fields": "id,name,status"}
            ).get("data", [])
            
            enhanced_forms = []
            for form in base_forms:
                campaign_name = self.get_campaign_name_safe(form['id'], form.get('name', f'Form-{form["id"]}'))
                enhanced_forms.append({
                    **form,
                    'campaign_name': campaign_name
                })
            
            self._enhanced_forms_cache = enhanced_forms
        return self._enhanced_forms_cache
    
    def get_form_leads_parallel(self, form_ids: List[str]) -> Dict[str, List[dict]]:
        """Fetch leads from multiple forms in parallel"""
        results = {}
        
        def fetch_form_leads(form_id: str) -> Tuple[str, List[dict]]:
            return form_id, self.get_paginated_optimized(f"{form_id}/leads")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_form = {executor.submit(fetch_form_leads, fid): fid for fid in form_ids}
            
            for future in as_completed(future_to_form):
                try:
                    form_id, leads = future.result()
                    results[form_id] = leads
                except Exception as e:
                    form_id = future_to_form[future]
                    print(f"❌ Error fetching leads for form {form_id}: {e}")
                    results[form_id] = []
        return results

meta_api = MetaAPIOptimized(PAGE_TOKEN)

def map_lead_with_source(raw: dict, campaign_name: str) -> Optional[dict]:
    """Map raw lead data to database format with META source"""
    if not meta_api._is_within_past_24_hours(raw.get("created_time", "")):
        return None
    
    field_data = raw.get("field_data", [])
    if not field_data:
        return None
    
    answers = {field["name"].lower(): field["values"][0] for field in field_data if field.get("values") and field["values"][0]}
    
    name = answers.get("full_name") or answers.get("full name") or answers.get("name") or ""
    phone = answers.get("phone_number") or answers.get("contact_number") or answers.get("phone") or answers.get("mobile") or ""
    
    if not (name or phone):
        return None
    
    normalized_phone = normalize_phone_number(phone)
    if not normalized_phone:
        return None
    
    created_time = raw.get("created_time", "")
    created = created_time[:10] if created_time and len(created_time) >= 10 and created_time.count('-') == 2 else datetime.now(timezone.utc).date().isoformat()
    
    now_iso = datetime.now().isoformat()
    
    return {
        "date": created, 
        "customer_name": name, 
        "customer_mobile_number": normalized_phone,
        "source": "META",  # Fixed source
        "sub_source": "Meta",  # Fixed sub_source
        "campaign": campaign_name,
        "cre_name": None, "lead_category": None, "model_interested": None,
        "branch": None, "ps_name": None, "assigned": "No", "lead_status": "Pending",
        "follow_up_date": None, "first_call_date": None, "first_remark": None,
        "second_call_date": None, "second_remark": None, "third_call_date": None, "third_remark": None,
        "fourth_call_date": None, "fourth_remark": None, "fifth_call_date": None, "fifth_remark": None,
        "sixth_call_date": None, "sixth_remark": None, "seventh_call_date": None, "seventh_remark": None,
        "final_status": "Pending", "created_at": now_iso, "updated_at": now_iso
    }

def preview_field_names_optimized():
    """Preview field names with campaign info"""
    print(f"\n📝 Enhanced field-name preview for PAST 24 HOURS")
    
    forms = meta_api.get_forms_with_campaign_info_safe()
    all_form_leads = meta_api.get_form_leads_parallel([f['id'] for f in forms])
    
    global_set = set()
    total_leads_24h = 0
    
    for form in forms:
        form_id, form_name = form['id'], form['name']
        campaign_name = form['campaign_name']
        leads = all_form_leads.get(form_id, [])
        
        print(f"📄 {form_name} ({form_id})")
        print(f"   📊 Campaign: {campaign_name} | Source: META | Sub-source: Meta")
        
        local_fields = set()
        leads_count = 0
        
        for lead in leads:
            if meta_api._is_within_past_24_hours(lead.get("created_time", "")):
                leads_count += 1
                total_leads_24h += 1
                for fd in lead.get("field_data", []):
                    field_name = fd["name"]
                    local_fields.add(field_name)
                    global_set.add(field_name)
        
        if local_fields:
            print(f"   • Past 24h leads: {leads_count}")
            print("   • Fields: " + "  • ".join(sorted(local_fields)))
        else:
            print("   ⚠️  No leads in past 24 hours.")
        print()
    
    print(f"📊 TOTAL LEADS: {total_leads_24h}")
    print("🧾 ALL FIELDS:", ", ".join(sorted(global_set)), "\n")

def sync_to_db_optimized():
    """Enhanced sync with proper intra-batch duplicate handling"""
    print(f"🔄 Meta API sync starting with duplicate handling...")
    print(f"🎯 Source: META | Sub-source: Meta")
    print(f"🎯 Each lead processed individually - duplicate handling active")
    
    forms = meta_api.get_forms_with_campaign_info_safe()
    all_form_leads = meta_api.get_form_leads_parallel([f['id'] for f in forms])
    
    all_new_leads = []
    form_data = {f['id']: f for f in forms}
    
    for form_id, leads in all_form_leads.items():
        form_info = form_data.get(form_id, {})
        campaign_name = form_info.get('campaign_name', 'Unknown Campaign')
        valid_leads = 0
        
        for raw_lead in leads:
            mapped_lead = map_lead_with_source(raw_lead, campaign_name)
            if mapped_lead and mapped_lead["customer_mobile_number"]:
                all_new_leads.append(mapped_lead)
                valid_leads += 1
        
        if valid_leads > 0:
            print(f"✅ {form_info.get('name', form_id)}: {valid_leads} leads")
    
    if not all_new_leads:
        print("📭 No valid leads found.")
        return
    
    print(f"\n📊 Collected {len(all_new_leads)} leads from Meta")
    
    # STEP 1: Remove intra-batch duplicates (same phone + same source/sub_source)
    seen_combinations = set()
    deduplicated_leads = []
    intra_batch_duplicates = 0
    
    for lead in all_new_leads:
        phone = lead['customer_mobile_number']
        source = lead['source']
        sub_source = lead['sub_source']
        combination = (phone, source, sub_source)
        
        if combination in seen_combinations:
            print(f"🔄 Removing intra-batch duplicate: {phone} | Source: {source} | Sub-source: {sub_source}")
            intra_batch_duplicates += 1
            continue
        
        seen_combinations.add(combination)
        deduplicated_leads.append(lead)
    
    if intra_batch_duplicates > 0:
        print(f"🧹 Removed {intra_batch_duplicates} intra-batch duplicates")
    
    # Convert to DataFrame for processing
    df_processed = pd.DataFrame(deduplicated_leads)
    
    # STEP 2: Check existing records in both tables
    master_records, duplicate_records = check_existing_leads(supabase, df_processed)
    
    # STEP 3: Process each lead
    new_leads = []
    updated_duplicates = 0
    skipped_duplicates = 0
    
    for _, row in df_processed.iterrows():
        phone = row['customer_mobile_number']
        current_source = row['source']
        current_sub_source = row['sub_source']
        current_date = row['date']
        
        # Check if phone exists in lead_master
        if phone in master_records:
            master_record = master_records[phone]
            
            # Check if this is a duplicate source/sub_source combination
            if is_duplicate_source(master_record, current_source, current_sub_source):
                print(f"⚠️ Skipping duplicate: {phone} | Source: {current_source} | Sub-source: {current_sub_source}")
                skipped_duplicates += 1
                continue
            
            # Check if already exists in duplicate_leads
            if phone in duplicate_records:
                duplicate_record = duplicate_records[phone]
                
                # Check if this source/sub_source already exists in duplicate record
                if is_duplicate_source(duplicate_record, current_source, current_sub_source):
                    print(f"⚠️ Skipping duplicate: {phone} | Source: {current_source} | Sub-source: {current_sub_source}")
                    skipped_duplicates += 1
                    continue
                
                # Add to existing duplicate record
                if add_source_to_duplicate_record(supabase, duplicate_record, current_source, current_sub_source, current_date):
                    updated_duplicates += 1
                    # Update local duplicate_records to avoid conflicts in same batch
                    duplicate_records[phone]['duplicate_count'] += 1
            else:
                # Create new duplicate record
                if create_duplicate_record(supabase, master_record, current_source, current_sub_source, current_date):
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
    
    # STEP 4: Process new leads ONE BY ONE to prevent race conditions
    successful_inserts = 0
    failed_inserts = 0
    
    if not new_leads:
        print("✅ No new leads to insert.")
    else:
        print(f"🆕 Found {len(new_leads)} new leads to insert")
        
        # Process each new lead individually
        sequence = get_next_sequence_number(supabase)
        
        for lead in new_leads:
            try:
                # Generate UID for this lead
                new_uid = generate_uid(lead['source'], lead['customer_mobile_number'], sequence)
                lead['uid'] = new_uid
                
                # Final columns check
                final_cols = ['uid', 'date', 'customer_name', 'customer_mobile_number', 'source', 'sub_source', 'campaign',
                              'cre_name', 'lead_category', 'model_interested', 'branch', 'ps_name',
                              'assigned', 'lead_status', 'follow_up_date',
                              'first_call_date', 'first_remark', 'second_call_date', 'second_remark',
                              'third_call_date', 'third_remark', 'fourth_call_date', 'fourth_remark',
                              'fifth_call_date', 'fifth_remark', 'sixth_call_date', 'sixth_remark',
                              'seventh_call_date', 'seventh_remark', 'final_status',
                              'created_at', 'updated_at']
                
                # Create final lead dict with only required columns
                final_lead = {col: lead.get(col) for col in final_cols}
                
                # Insert individual lead safely
                if insert_lead_safely(supabase, final_lead):
                    print(f"✅ Inserted new lead: {new_uid} | Phone: {lead['customer_mobile_number']} | Campaign: {lead['campaign']}")
                    successful_inserts += 1
                else:
                    failed_inserts += 1
                
                sequence += 1
                
            except Exception as e:
                print(f"❌ Failed to insert Phone: {lead['customer_mobile_number']}: {e}")
                failed_inserts += 1
    
    # Summary
    print(f"\n📊 SUMMARY:")
    print(f"🧹 Intra-batch duplicates removed: {intra_batch_duplicates}")
    print(f"✅ New leads inserted: {successful_inserts}")
    print(f"❌ Failed insertions: {failed_inserts}")
    print(f"🔄 Duplicate records updated/created: {updated_duplicates}")
    print(f"⚠️ Skipped exact duplicates: {skipped_duplicates}")
    print(f"📱 Total records processed: {len(all_new_leads)}")
    print(f"🎯 Source: META | Sub-source: Meta")
    print(f"📊 Each lead processed individually with duplicate handling")
    print(f"🔄 Duplicates with other sources handled via duplicate_leads table")

# Compatibility functions
def preview_field_names():
    preview_field_names_optimized()

def sync_to_db():
    sync_to_db_optimized()

if __name__ == "__main__":
    preview_field_names()
    sync_to_db()
