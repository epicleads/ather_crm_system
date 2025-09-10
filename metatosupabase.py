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
    def __init__(self, page_token: str, max_workers: int = 2):
        self.page_token = page_token
        self.max_workers = max_workers
        self.session = requests.Session()
        self._campaign_cache = {}
        self.api_version = "v21.0"  # Updated to latest stable version
        self.request_delay = 1.0  # Increased delay to 1 second
        self.retry_attempts = 3
        self.backoff_factor = 2
    
    def _make_request(self, url: str, params: dict = None) -> dict:
        """Make API request with improved error handling and exponential backoff"""
        for attempt in range(self.retry_attempts):
            try:
                # Add rate limiting delay
                time.sleep(self.request_delay)
                
                response = self.session.get(url, params=params, timeout=30)  # Increased timeout
                
                # Handle rate limiting with exponential backoff
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    backoff_time = retry_after + (self.backoff_factor ** attempt)
                    print(f"⏳ Rate limited (attempt {attempt + 1}). Waiting {backoff_time} seconds...")
                    time.sleep(backoff_time)
                    continue
                
                # Handle other HTTP errors
                if response.status_code >= 400:
                    print(f"⚠️ HTTP {response.status_code} error: {response.text}")
                    if attempt < self.retry_attempts - 1:
                        wait_time = self.backoff_factor ** attempt
                        print(f"⏳ Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        response.raise_for_status()
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                print(f"⏰ Request timeout (attempt {attempt + 1})")
                if attempt < self.retry_attempts - 1:
                    wait_time = self.backoff_factor ** attempt
                    time.sleep(wait_time)
                    continue
                else:
                    print("❌ Max timeout retries reached")
                    return {}
                    
            except requests.exceptions.RequestException as e:
                print(f"⚠️ API error (attempt {attempt + 1}): {e}")
                if attempt < self.retry_attempts - 1:
                    wait_time = self.backoff_factor ** attempt
                    time.sleep(wait_time)
                    continue
                else:
                    print("❌ Max request retries reached")
                    return {}
        
        return {}
    
    def get_campaign_name_safe(self, form_id: str, form_name: str) -> str:
        """Get campaign name safely from form name"""
        if form_id in self._campaign_cache:
            return self._campaign_cache[form_id]
        
        try:
            # Clean form name more safely
            cleaned = str(form_name).strip() if form_name else f"Form-{form_id}"
            cleaned = cleaned.replace('@', 'at').replace('&', 'and')
            cleaned = cleaned.replace('-copy', '').replace('_copy', '')
            cleaned = ' '.join(cleaned.split())  # Normalize whitespace
            
            # Capitalize words safely
            cleaned = ' '.join(word.capitalize() for word in cleaned.split() if word)
            
        except Exception as e:
            print(f"⚠️ Error cleaning form name: {e}")
            cleaned = f"Form-{form_id}"
        
        self._campaign_cache[form_id] = cleaned or f"Form-{form_id}"
        return self._campaign_cache[form_id]
    
    def get_paginated_optimized(self, endpoint: str, **params) -> List[dict]:
        """Get paginated data with improved error handling and time filtering"""
        params["access_token"] = self.page_token
        params["limit"] = 20  # Further reduced limit
        
        # Add time filter for past 24 hours to reduce data load
        if "leads" in endpoint:
            yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
            params["since"] = int(yesterday.timestamp())
        
        all_data = []
        next_url = f"https://graph.facebook.com/{self.api_version}/{endpoint}"
        consecutive_old_pages = 0
        page_count = 0
        max_pages = 10  # Further reduced max pages
        
        while next_url and consecutive_old_pages < 2 and page_count < max_pages:
            print(f"📄 Fetching page {page_count + 1}...")
            
            response = self._make_request(next_url, params if not next_url.startswith("https://") or not all_data else None)
            
            if not response or "data" not in response:
                print("⚠️ No data in response, stopping pagination")
                break
            
            page_data = response["data"]
            if not page_data:
                print("📭 Empty page, stopping pagination")
                break
            
            page_count += 1
            
            if "leads" in endpoint:
                # Filter for recent data
                recent_data = []
                for item in page_data:
                    if self._is_within_past_24_hours(item.get("created_time", "")):
                        recent_data.append(item)
                
                all_data.extend(recent_data)
                
                if not recent_data:
                    consecutive_old_pages += 1
                    print(f"⏰ No recent leads on page {page_count}, consecutive old pages: {consecutive_old_pages}")
                else:
                    consecutive_old_pages = 0
                    print(f"✅ Found {len(recent_data)} recent leads on page {page_count}")
                    
                if consecutive_old_pages >= 2:
                    print("🛑 Too many consecutive pages without recent data, stopping")
                    break
            else:
                all_data.extend(page_data)
            
            # Check for next page
            paging = response.get("paging", {})
            next_url = paging.get("next")
            
            if next_url:
                params = {}  # Clear params for subsequent requests
                time.sleep(1)  # Additional delay between pages
            else:
                print("📄 No more pages available")
                break
        
        print(f"📊 Retrieved {len(all_data)} total records from {page_count} pages")
        return all_data
    
    def _is_within_past_24_hours(self, created_time_str: str) -> bool:
        """Check if timestamp is within past 24 hours with improved parsing"""
        if not created_time_str:
            return False
        
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",      # ISO with timezone
            "%Y-%m-%dT%H:%M:%S.%f%z",   # ISO with microseconds and timezone
            "%Y-%m-%dT%H:%M:%SZ",       # ISO with Z timezone
            "%Y-%m-%dT%H:%M:%S",        # ISO without timezone
            "%Y-%m-%d %H:%M:%S"         # Standard format
        ]
        
        for fmt in formats:
            try:
                created_time = datetime.strptime(created_time_str, fmt)
                
                # Handle timezone awareness
                if created_time.tzinfo:
                    created_time_utc = created_time.astimezone(timezone.utc).replace(tzinfo=None)
                else:
                    created_time_utc = created_time
                
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                is_recent = (now - timedelta(hours=24)) <= created_time_utc <= now
                
                return is_recent
                
            except (ValueError, TypeError) as e:
                continue
                
        print(f"⚠️ Unable to parse timestamp: {created_time_str}")
        return False
    
    def get_forms_with_campaign_info_safe(self) -> List[dict]:
        """Get forms with campaign info - with improved error handling"""
        if not hasattr(self, '_enhanced_forms_cache'):
            print("📋 Fetching forms...")
            
            forms_response = self._make_request(
                f"https://graph.facebook.com/{self.api_version}/{PAGE_ID}/leadgen_forms",
                {
                    "access_token": self.page_token, 
                    "fields": "id,name,status,created_time", 
                    "limit": 100
                }
            )
            
            base_forms = forms_response.get("data", [])
            
            if not base_forms:
                print("⚠️ No forms found or API error")
                self._enhanced_forms_cache = []
                return []
            
            print(f"📋 Found {len(base_forms)} forms")
            
            enhanced_forms = []
            for form in base_forms:
                try:
                    campaign_name = self.get_campaign_name_safe(
                        form['id'], 
                        form.get('name', f'Form-{form["id"]}')
                    )
                    enhanced_forms.append({
                        **form,
                        'campaign_name': campaign_name
                    })
                except Exception as e:
                    print(f"⚠️ Error processing form {form.get('id', 'unknown')}: {e}")
                    continue
            
            self._enhanced_forms_cache = enhanced_forms
            print(f"✅ Enhanced {len(enhanced_forms)} forms")
            
        return self._enhanced_forms_cache
    
    def get_form_leads_parallel(self, form_ids: List[str]) -> Dict[str, List[dict]]:
        """Fetch leads from multiple forms with improved parallel processing"""
        results = {}
        
        if not form_ids:
            print("⚠️ No form IDs provided")
            return results
        
        def fetch_form_leads(form_id: str) -> Tuple[str, List[dict]]:
            try:
                print(f"🔄 Fetching leads for form: {form_id}")
                time.sleep(0.5)  # Delay between form requests
                leads = self.get_paginated_optimized(f"{form_id}/leads")
                print(f"✅ Form {form_id}: {len(leads)} leads")
                return form_id, leads
            except Exception as e:
                print(f"❌ Error fetching leads for form {form_id}: {e}")
                return form_id, []
        
        # Process forms in smaller batches
        batch_size = 2  # Further reduced batch size
        form_batches = [form_ids[i:i + batch_size] for i in range(0, len(form_ids), batch_size)]
        
        for batch_num, batch in enumerate(form_batches, 1):
            print(f"🔄 Processing batch {batch_num}/{len(form_batches)} with {len(batch)} forms...")
            
            with ThreadPoolExecutor(max_workers=min(len(batch), self.max_workers)) as executor:
                future_to_form = {executor.submit(fetch_form_leads, fid): fid for fid in batch}
                
                for future in as_completed(future_to_form):
                    try:
                        form_id, leads = future.result(timeout=60)  # 60 second timeout per form
                        results[form_id] = leads
                    except Exception as e:
                        form_id = future_to_form[future]
                        print(f"❌ Timeout/error for form {form_id}: {e}")
                        results[form_id] = []
            
            # Longer delay between batches
            if batch_num < len(form_batches):
                wait_time = 3
                print(f"⏳ Waiting {wait_time} seconds between batches...")
                time.sleep(wait_time)
        
        total_leads = sum(len(leads) for leads in results.values())
        print(f"📊 Total leads collected: {total_leads}")
        
        return results


# Initialize with reduced workers
meta_api = MetaAPIOptimized(PAGE_TOKEN, max_workers=2)


def map_lead_with_source(raw: dict, campaign_name: str) -> Optional[dict]:
    """Map raw lead data to database format with improved error handling"""
    try:
        if not meta_api._is_within_past_24_hours(raw.get("created_time", "")):
            return None
        
        field_data = raw.get("field_data", [])
        if not field_data:
            return None
        
        # Safely extract field answers
        answers = {}
        for field in field_data:
            try:
                field_name = field.get("name", "").lower()
                field_values = field.get("values", [])
                if field_values and field_values[0]:
                    answers[field_name] = str(field_values[0]).strip()
            except Exception as e:
                print(f"⚠️ Error processing field {field}: {e}")
                continue
        
        # Try multiple field name variations
        name_fields = ["full_name", "full name", "name", "customer_name", "first_name", "last_name"]
        phone_fields = ["phone_number", "contact_number", "phone", "mobile", "mobile_number", "cell"]
        
        name = ""
        for field in name_fields:
            if field in answers:
                name = answers[field]
                break
        
        phone = ""
        for field in phone_fields:
            if field in answers:
                phone = answers[field]
                break
        
        if not (name or phone):
            print("⚠️ No name or phone found in lead data")
            return None
        
        normalized_phone = normalize_phone_number(phone)
        if not normalized_phone:
            print(f"⚠️ Invalid phone number: {phone}")
            return None
        
        # Safely parse date
        created_time = raw.get("created_time", "")
        try:
            if created_time and len(created_time) >= 10:
                created = created_time[:10]  # YYYY-MM-DD format
                # Validate date format
                datetime.strptime(created, "%Y-%m-%d")
            else:
                created = datetime.now(timezone.utc).date().isoformat()
        except ValueError:
            created = datetime.now(timezone.utc).date().isoformat()
        
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
        
    except Exception as e:
        print(f"❌ Error mapping lead data: {e}")
        return None


def sync_to_db_optimized():
    """Enhanced sync with proper error handling and duplicate management"""
    print(f"🔄 Meta API sync starting with improved error handling...")
    print(f"🎯 Source: META | Sub-source: Meta")
    
    try:
        forms = meta_api.get_forms_with_campaign_info_safe()
        
        if not forms:
            print("❌ No forms available for sync")
            return
        
        # Process all forms but with improved rate limiting
        all_form_leads = meta_api.get_form_leads_parallel([f['id'] for f in forms])
        
        all_new_leads = []
        form_data = {f['id']: f for f in forms}
        
        for form_id, leads in all_form_leads.items():
            form_info = form_data.get(form_id, {})
            campaign_name = form_info.get('campaign_name', 'Unknown Campaign')
            valid_leads = 0
            
            for raw_lead in leads:
                try:
                    mapped_lead = map_lead_with_source(raw_lead, campaign_name)
                    if mapped_lead and mapped_lead["customer_mobile_number"]:
                        all_new_leads.append(mapped_lead)
                        valid_leads += 1
                except Exception as e:
                    print(f"❌ Error mapping lead: {e}")
                    continue
            
            if valid_leads > 0:
                print(f"✅ {form_info.get('name', form_id)}: {valid_leads} leads")
        
        if not all_new_leads:
            print("📭 No valid leads found.")
            return
        
        print(f"\n📊 Collected {len(all_new_leads)} leads from Meta")
        
        # Remove intra-batch duplicates
        seen_combinations = set()
        deduplicated_leads = []
        intra_batch_duplicates = 0
        
        for lead in all_new_leads:
            phone = lead['customer_mobile_number']
            source = lead['source']
            sub_source = lead['sub_source']
            combination = (phone, source, sub_source)
            
            if combination in seen_combinations:
                print(f"🔄 Removing intra-batch duplicate: {phone} | Source: {source}")
                intra_batch_duplicates += 1
                continue
            
            seen_combinations.add(combination)
            deduplicated_leads.append(lead)
        
        if intra_batch_duplicates > 0:
            print(f"🧹 Removed {intra_batch_duplicates} intra-batch duplicates")
        
        # Convert to DataFrame for processing
        df_processed = pd.DataFrame(deduplicated_leads)
        
        # Check existing records
        master_records, duplicate_records = check_existing_leads(supabase, df_processed)
        
        # Process each lead
        new_leads = []
        updated_duplicates = 0
        skipped_duplicates = 0
        
        for _, row in df_processed.iterrows():
            phone = row['customer_mobile_number']
            current_source = row['source']
            current_sub_source = row['sub_source']
            current_date = row['date']
            
            try:
                # Check if phone exists in lead_master
                if phone in master_records:
                    master_record = master_records[phone]
                    
                    # Check if this is a duplicate source/sub_source combination
                    if is_duplicate_source(master_record, current_source, current_sub_source):
                        print(f"⚠️ Skipping duplicate: {phone} | Source: {current_source}")
                        skipped_duplicates += 1
                        continue
                    
                    # Handle duplicate logic
                    if phone in duplicate_records:
                        duplicate_record = duplicate_records[phone]
                        
                        if is_duplicate_source(duplicate_record, current_source, current_sub_source):
                            print(f"⚠️ Skipping duplicate: {phone} | Source: {current_source}")
                            skipped_duplicates += 1
                            continue
                        
                        # Add to existing duplicate record
                        if add_source_to_duplicate_record(supabase, duplicate_record, current_source, current_sub_source, current_date):
                            updated_duplicates += 1
                    else:
                        # Create new duplicate record
                        if create_duplicate_record(supabase, master_record, current_source, current_sub_source, current_date):
                            updated_duplicates += 1
                
                elif phone in duplicate_records:
                    # Phone exists in duplicate_leads but not in lead_master
                    duplicate_record = duplicate_records[phone]
                    
                    if is_duplicate_source(duplicate_record, current_source, current_sub_source):
                        print(f"⚠️ Skipping duplicate: {phone} | Source: {current_source}")
                        skipped_duplicates += 1
                        continue
                    
                    # Add to existing duplicate record
                    if add_source_to_duplicate_record(supabase, duplicate_record, current_source, current_sub_source, current_date):
                        updated_duplicates += 1
                
                else:
                    # Completely new lead - add UID and prepare for insertion
                    with _sequence_lock:
                        sequence = get_next_sequence_number(supabase)
                        row_dict = row.to_dict()
                        row_dict['uid'] = generate_uid(current_source, phone, sequence)
                        new_leads.append(row_dict)
                        
            except Exception as e:
                print(f"❌ Error processing lead {phone}: {e}")
                continue
        
        # Batch insert new leads
        if new_leads:
            print(f"\n📝 Attempting to insert {len(new_leads)} new leads...")
            
            successful_inserts = 0
            failed_inserts = 0
            
            # Process in smaller batches to avoid timeouts
            batch_size = 10
            for i in range(0, len(new_leads), batch_size):
                batch = new_leads[i:i + batch_size]
                
                for lead in batch:
                    if insert_lead_safely(supabase, lead):
                        successful_inserts += 1
                        print(f"✅ Inserted: {lead['uid']} | {lead['customer_name']} | {lead['customer_mobile_number']}")
                    else:
                        failed_inserts += 1
                
                # Small delay between batches
                if i + batch_size < len(new_leads):
                    time.sleep(0.5)
        
        # Final summary
        print(f"\n📊 SYNC SUMMARY:")
        print(f"✅ New leads inserted: {successful_inserts}")
        print(f"🔄 Duplicate records updated: {updated_duplicates}")
        print(f"⚠️ Skipped duplicates: {skipped_duplicates}")
        print(f"❌ Failed insertions: {failed_inserts}")
        print(f"📱 Total processed: {len(df_processed)}")
        
    except Exception as e:
        print(f"❌ Critical error in sync process: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main execution function - Direct sync to database"""
    try:
        print("🚀 Starting Meta Lead Direct Sync to Database...")
        print(f"⏰ Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Syncing leads from last 24 hours directly to Supabase...")
        
        # Direct sync execution
        sync_to_db_optimized()
            
    except KeyboardInterrupt:
        print("\n⏹️ Process interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🏁 Meta Lead Sync Process completed")


if __name__ == "__main__":
    main()
