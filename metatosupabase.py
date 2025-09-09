import os, requests, time, json, hashlib, threading
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Set, Optional, Tuple
import pandas as pd
import random

# Environment setup
load_dotenv()
PAGE_TOKEN, PAGE_ID, SUPA_URL, SUPA_KEY = [os.getenv(k) for k in ["META_PAGE_ACCESS_TOKEN", "PAGE_ID", "SUPABASE_URL", "SUPABASE_ANON_KEY"]]
if not all([PAGE_TOKEN, PAGE_ID, SUPA_URL, SUPA_KEY]):
    raise SystemExit("❌ Check .env – missing values!")

supabase = create_client(SUPA_URL, SUPA_KEY)
_sequence_lock = threading.Lock()
_sequence_cache = None

def validate_token_on_startup():
    """Validate token before starting the sync process"""
    print("🔐 Validating Meta API token...")
    
    try:
        # Test basic token validity
        response = requests.get(
            f"https://graph.facebook.com/v20.0/me",
            params={"access_token": PAGE_TOKEN},
            timeout=10
        )
        
        if response.status_code == 200:
            user_info = response.json()
            print(f"✅ Token valid for: {user_info.get('name', 'Unknown')}")
            
            # Test page access
            page_response = requests.get(
                f"https://graph.facebook.com/v20.0/{PAGE_ID}",
                params={"access_token": PAGE_TOKEN, "fields": "name"},
                timeout=10
            )
            
            if page_response.status_code == 200:
                page_info = page_response.json()
                print(f"✅ Page access confirmed: {page_info.get('name', 'Unknown')}")
                return True
            else:
                print(f"❌ Cannot access page {PAGE_ID}: {page_response.json()}")
                return False
                
        else:
            error_info = response.json()
            print(f"❌ Token validation failed: {error_info}")
            return False
            
    except Exception as e:
        print(f"❌ Token validation error: {e}")
        return False

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

def check_existing_leads_bulk(supabase, df_leads):
    """Optimized bulk check for existing leads"""
    try:
        phone_list = df_leads['customer_mobile_number'].unique().tolist()
        
        # Single query for lead_master - get only essential fields
        existing_master = supabase.table("lead_master").select("customer_mobile_number,source,sub_source,uid,id,date,customer_name").in_("customer_mobile_number", phone_list).execute()
        master_records = {row['customer_mobile_number']: row for row in existing_master.data}
        
        # Single query for duplicate_leads - get only essential fields
        duplicate_fields = "customer_mobile_number,uid,id,duplicate_count," + ",".join([f"source{i},sub_source{i}" for i in range(1, 11)])
        existing_duplicate = supabase.table("duplicate_leads").select(duplicate_fields).in_("customer_mobile_number", phone_list).execute()
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

def process_duplicates_batch(supabase, duplicate_updates):
    """Process multiple duplicate updates in batch"""
    if not duplicate_updates:
        return 0
    
    success_count = 0
    for update_data in duplicate_updates:
        try:
            supabase.table("duplicate_leads").update(update_data['data']).eq('id', update_data['id']).execute()
            success_count += 1
        except Exception as e:
            print(f"❌ Failed batch duplicate update: {e}")
    
    return success_count

def create_duplicate_records_batch(supabase, duplicate_records):
    """Create multiple duplicate records in batch"""
    if not duplicate_records:
        return 0
    
    try:
        supabase.table("duplicate_leads").insert(duplicate_records).execute()
        return len(duplicate_records)
    except Exception as e:
        print(f"❌ Failed batch duplicate creation: {e}")
        return 0

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

def insert_leads_batch(supabase, leads_batch):
    """Insert multiple leads in batch with error handling"""
    if not leads_batch:
        return 0, 0
    
    try:
        # Try batch insert first
        supabase.table("lead_master").insert(leads_batch).execute()
        return len(leads_batch), 0
    except Exception as e:
        # If batch fails, try individual inserts
        print(f"⚠️ Batch insert failed, trying individual inserts: {e}")
        success_count = 0
        failed_count = 0
        
        for lead in leads_batch:
            try:
                # Quick check for exact duplicate
                existing = supabase.table("lead_master").select("id").eq(
                    "customer_mobile_number", lead['customer_mobile_number']
                ).eq("source", lead['source']).eq("sub_source", lead['sub_source']).limit(1).execute()
                
                if not existing.data:
                    supabase.table("lead_master").insert(lead).execute()
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as individual_e:
                failed_count += 1
                
        return success_count, failed_count

class MetaAPIOptimized:
    def __init__(self, page_token: str, max_workers: int = 5):  # Increased workers
        self.page_token = page_token
        self.max_workers = max_workers
        self.session = requests.Session()
        self._campaign_cache = {}
        self.api_version = "v20.0"
        
        # Optimized session configuration
        self.session.headers.update({
            'User-Agent': 'CRM-Lead-Sync/1.0',
            'Connection': 'keep-alive'
        })
    
    def _make_request_fast(self, url: str, params: dict = None, max_retries: int = 2) -> dict:
        """Faster API request with reduced retries for speed"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=20)  # Reduced timeout
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    print(f"❌ Request failed: {url}")
                    return {}
                
                # Quick retry with minimal delay
                wait_time = 1 + (attempt * 0.5)
                time.sleep(wait_time)
        
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
    
    def get_paginated_fast(self, endpoint: str, **params) -> List[dict]:
        """Faster paginated data retrieval with optimized limits"""
        params["access_token"] = self.page_token
        params["limit"] = 100  # Increased limit for faster retrieval
        
        all_data = []
        next_url = f"https://graph.facebook.com/{self.api_version}/{endpoint}"
        consecutive_old_pages = 0
        page_count = 0
        max_pages = 10  # Reduced max pages for faster processing
        
        while next_url and consecutive_old_pages < 2 and page_count < max_pages:
            response = self._make_request_fast(
                next_url, 
                params if not next_url.startswith("https://") or not all_data else None
            )
            
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
                    
                if consecutive_old_pages >= 2:  # Reduced threshold
                    break
            else:
                all_data.extend(page_data)
            
            next_url = response.get("paging", {}).get("next")
            page_count += 1
            
            # Minimal pause
            if next_url:
                time.sleep(0.1)  # Reduced delay
                params = {}
            else:
                break
        
        return all_data
    
    def _is_within_past_24_hours(self, created_time_str: str) -> bool:
        """Check if timestamp is within past 24 hours"""
        if not created_time_str:
            return False
        
        formats = ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"]
        
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
    
    def get_forms_fast(self) -> List[dict]:
        """Get forms quickly"""
        if not hasattr(self, '_enhanced_forms_cache'):
            print("🔍 Fetching forms...")
            base_forms_response = self._make_request_fast(
                f"https://graph.facebook.com/{self.api_version}/{PAGE_ID}/leadgen_forms",
                {"access_token": self.page_token, "fields": "id,name,status", "limit": 100}
            )
            
            base_forms = base_forms_response.get("data", [])
            print(f"📋 Found {len(base_forms)} forms")
            
            enhanced_forms = []
            for form in base_forms:
                campaign_name = self.get_campaign_name_safe(form['id'], form.get('name', f'Form-{form["id"]}'))
                enhanced_forms.append({
                    **form,
                    'campaign_name': campaign_name
                })
            
            self._enhanced_forms_cache = enhanced_forms
        return self._enhanced_forms_cache
    
    def get_form_leads_parallel_fast(self, form_ids: List[str]) -> Dict[str, List[dict]]:
        """Fast parallel lead fetching"""
        results = {}
        
        def fetch_form_leads_fast(form_id: str) -> Tuple[str, List[dict]]:
            try:
                leads = self.get_paginated_fast(f"{form_id}/leads")
                return form_id, leads
            except Exception as e:
                print(f"❌ Error for form {form_id}")
                return form_id, []
        
        # Process all forms in parallel with increased workers
        batch_size = 8  # Increased batch size
        total_batches = (len(form_ids) + batch_size - 1) // batch_size
        
        for batch_num, i in enumerate(range(0, len(form_ids), batch_size), 1):
            batch = form_ids[i:i + batch_size]
            print(f"🔄 Batch {batch_num}/{total_batches} ({len(batch)} forms)")
            
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(batch))) as executor:
                future_to_form = {executor.submit(fetch_form_leads_fast, fid): fid for fid in batch}
                
                for future in as_completed(future_to_form):
                    form_id, leads = future.result()
                    results[form_id] = leads
            
            # Minimal pause between batches
            if i + batch_size < len(form_ids):
                time.sleep(0.5)  # Reduced pause
        
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
        "source": "META",
        "sub_source": "Meta",
        "campaign": campaign_name,
        "cre_name": None, "lead_category": None, "model_interested": None,
        "branch": None, "ps_name": None, "assigned": "No", "lead_status": "Pending",
        "follow_up_date": None, "first_call_date": None, "first_remark": None,
        "second_call_date": None, "second_remark": None, "third_call_date": None, "third_remark": None,
        "fourth_call_date": None, "fourth_remark": None, "fifth_call_date": None, "fifth_remark": None,
        "sixth_call_date": None, "sixth_remark": None, "seventh_call_date": None, "seventh_remark": None,
        "final_status": "Pending", "created_at": now_iso, "updated_at": now_iso
    }

def sync_to_db_fast():
    """Fast optimized sync with batch processing"""
    print(f"🚀 FAST Meta API sync starting...")
    print(f"🎯 Source: META | Sub-source: Meta")
    
    # Get forms and leads quickly
    forms = meta_api.get_forms_fast()
    all_form_leads = meta_api.get_form_leads_parallel_fast([f['id'] for f in forms])
    
    # Process leads quickly
    all_new_leads = []
    form_data = {f['id']: f for f in forms}
    
    for form_id, leads in all_form_leads.items():
        form_info = form_data.get(form_id, {})
        campaign_name = form_info.get('campaign_name', 'Unknown Campaign')
        
        for raw_lead in leads:
            mapped_lead = map_lead_with_source(raw_lead, campaign_name)
            if mapped_lead and mapped_lead["customer_mobile_number"]:
                all_new_leads.append(mapped_lead)
    
    if not all_new_leads:
        print("📭 No valid leads found.")
        return
    
    print(f"📊 Collected {len(all_new_leads)} leads from Meta")
    
    # Fast deduplication using set for O(1) lookups
    seen_combinations = set()
    deduplicated_leads = []
    
    for lead in all_new_leads:
        combination = (lead['customer_mobile_number'], lead['source'], lead['sub_source'])
        if combination not in seen_combinations:
            seen_combinations.add(combination)
            deduplicated_leads.append(lead)
    
    print(f"🧹 After deduplication: {len(deduplicated_leads)} leads")
    
    # Convert to DataFrame
    df_processed = pd.DataFrame(deduplicated_leads)
    
    # Bulk check existing records
    master_records, duplicate_records = check_existing_leads_bulk(supabase, df_processed)
    
    # Fast processing
    new_leads = []
    duplicate_updates = []
    new_duplicate_records = []
    skipped_count = 0
    
    for _, row in df_processed.iterrows():
        phone = row['customer_mobile_number']
        current_source = row['source']
        current_sub_source = row['sub_source']
        current_date = row['date']
        
        if phone in master_records:
            master_record = master_records[phone]
            
            if is_duplicate_source(master_record, current_source, current_sub_source):
                skipped_count += 1
                continue
            
            if phone in duplicate_records:
                duplicate_record = duplicate_records[phone]
                if is_duplicate_source(duplicate_record, current_source, current_sub_source):
                    skipped_count += 1
                    continue
                
                slot = find_next_available_source_slot(duplicate_record)
                if slot:
                    update_data = {
                        f'source{slot}': current_source,
                        f'sub_source{slot}': current_sub_source,
                        f'date{slot}': current_date,
                        'duplicate_count': duplicate_record['duplicate_count'] + 1,
                        'updated_at': datetime.now().isoformat()
                    }
                    duplicate_updates.append({'id': duplicate_record['id'], 'data': update_data})
            else:
                # Create new duplicate record
                duplicate_data = {
                    'uid': master_record['uid'],
                    'customer_mobile_number': phone,
                    'customer_name': row['customer_name'],
                    'original_lead_id': master_record['id'],
                    'source1': master_record['source'],
                    'sub_source1': master_record['sub_source'],
                    'date1': master_record.get('date', current_date),
                    'source2': current_source,
                    'sub_source2': current_sub_source,
                    'date2': current_date,
                    'duplicate_count': 2,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                
                # Initialize remaining slots
                for i in range(3, 11):
                    duplicate_data[f'source{i}'] = None
                    duplicate_data[f'sub_source{i}'] = None
                    duplicate_data[f'date{i}'] = None
                
                new_duplicate_records.append(duplicate_data)
        else:
            new_leads.append(row)
    
    # Batch process results
    successful_inserts = 0
    failed_inserts = 0
    
    if new_leads:
        print(f"🆕 Processing {len(new_leads)} new leads in batches...")
        
        # Generate UIDs
        sequence = get_next_sequence_number(supabase)
        leads_with_uids = []
        
        for i, lead in enumerate(new_leads):
            new_uid = generate_uid(lead['source'], lead['customer_mobile_number'], sequence + i)
            lead_dict = lead.to_dict() if hasattr(lead, 'to_dict') else dict(lead)
            lead_dict['uid'] = new_uid
            
            # Final columns
            final_cols = ['uid', 'date', 'customer_name', 'customer_mobile_number', 'source', 'sub_source', 'campaign',
                          'cre_name', 'lead_category', 'model_interested', 'branch', 'ps_name',
                          'assigned', 'lead_status', 'follow_up_date',
                          'first_call_date', 'first_remark', 'second_call_date', 'second_remark',
                          'third_call_date', 'third_remark', 'fourth_call_date', 'fourth_remark',
                          'fifth_call_date', 'fifth_remark', 'sixth_call_date', 'sixth_remark',
                          'seventh_call_date', 'seventh_remark', 'final_status',
                          'created_at', 'updated_at']
            
            final_lead = {col: lead_dict.get(col) for col in final_cols}
            leads_with_uids.append(final_lead)
        
        # Batch insert with chunks
        chunk_size = 50
        for i in range(0, len(leads_with_uids), chunk_size):
            chunk = leads_with_uids[i:i + chunk_size]
            success, failed = insert_leads_batch(supabase, chunk)
            successful_inserts += success
            failed_inserts += failed
    
    # Process duplicates in batches
    updated_duplicates = 0
    if duplicate_updates:
        updated_duplicates += process_duplicates_batch(supabase, duplicate_updates)
    
    if new_duplicate_records:
        updated_duplicates += create_duplicate_records_batch(supabase, new_duplicate_records)
    
    # Summary
    print(f"\n📊 FAST SYNC SUMMARY:")
    print(f"✅ New leads inserted: {successful_inserts}")
    print(f"❌ Failed insertions: {failed_inserts}")
    print(f"🔄 Duplicate records updated/created: {updated_duplicates}")
    print(f"⚠️ Skipped exact duplicates: {skipped_count}")
    print(f"📱 Total records processed: {len(all_new_leads)}")
    print(f"🚀 Processing completed in optimized batch mode")

def quick_preview():
    """Quick preview without detailed analysis"""
    print("🔍 QUICK FORM PREVIEW")
    print("=" * 50)
    
    forms = meta_api.get_forms_fast()
    all_form_leads = meta_api.get_form_leads_parallel_fast([f['id'] for f in forms])
    
    total_recent = 0
    active_forms = 0
    
    for form in forms:
        leads = all_form_leads.get(form['id'], [])
        recent_leads = sum(1 for lead in leads if meta_api._is_within_past_24_hours(lead.get("created_time", "")))
        
        if recent_leads > 0:
            active_forms += 1
            total_recent += recent_leads
            print(f"✅ {form['name']}: {recent_leads} recent leads")
    
    print(f"\n📊 QUICK SUMMARY:")
    print(f"📋 Total Forms: {len(forms)}")
    print(f"✅ Active Forms: {active_forms}")
    print(f"📱 Total Recent Leads: {total_recent}")
    print("=" * 50)

def test_token_and_permissions():
    """Test if token is valid and has required permissions"""
    
    # Test token validity
    response = requests.get(
        f"https://graph.facebook.com/v20.0/me",
        params={"access_token": PAGE_TOKEN}
    )
    
    if response.status_code == 200:
        print("✅ Token is valid")
        print(f"📱 Token belongs to: {response.json().get('name')}")
        
        # Test permissions
        perm_response = requests.get(
            f"https://graph.facebook.com/v20.0/me/permissions",
            params={"access_token": PAGE_TOKEN}
        )
        
        if perm_response.status_code == 200:
            permissions = perm_response.json().get('data', [])
            active_perms = [p['permission'] for p in permissions if p.get('status') == 'granted']
            required_perms = ["leads_retrieval", "pages_read_engagement"]
            
            print(f"📋 Active permissions: {active_perms}")
            missing = [p for p in required_perms if p not in active_perms]
            
            if missing:
                print(f"❌ Missing permissions: {missing}")
                return False
            else:
                print("✅ All required permissions granted")
                return True
        else:
            print("❌ Could not check permissions")
            return False
    else:
        print(f"❌ Token is invalid: {response.json()}")
        return False

if __name__ == "__main__":
    # Validate token first
    if not validate_token_on_startup():
        print("\n🛑 TOKEN VALIDATION FAILED")
        print("=" * 50)
        print("📖 INSTRUCTIONS TO FIX:")
        print("1. Go to Meta Business Manager: https://business.facebook.com")
        print("2. Navigate to Business Settings → System Users")
        print("3. Generate new token with permissions:")
        print("   - leads_retrieval")
        print("   - pages_read_engagement")
        print("   - pages_manage_ads")
        print("4. Update your .env file with new token")
        print("5. Run the script again")
        print("=" * 50)
        
        # Optional: Test the token manually
        print("\n🔧 You can also test your current token:")
        test_token_and_permissions()
        exit(1)
    
    # Continue with optimized script
    print("\n🚀 FAST META SYNC MODE")
    print("=" * 50)
    
    # Quick preview
    quick_preview()
    
    # Fast sync
    print("\n" + "=" * 50)
    print("🚀 STARTING FAST SYNC")
    print("=" * 50)
    sync_to_db_fast()
