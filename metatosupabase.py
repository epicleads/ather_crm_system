import os, requests, time, json, hashlib, threading, asyncio
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Set, Optional, Tuple
import pandas as pd
import aiohttp
import warnings
warnings.filterwarnings("ignore")

# Environment setup
load_dotenv()
PAGE_TOKEN, PAGE_ID, SUPA_URL, SUPA_KEY = [os.getenv(k) for k in ["META_PAGE_ACCESS_TOKEN", "PAGE_ID", "SUPABASE_URL", "SUPABASE_ANON_KEY"]]

if not all([PAGE_TOKEN, PAGE_ID, SUPA_URL, SUPA_KEY]):
    raise SystemExit("❌ Check .env – missing values!")

supabase = create_client(SUPA_URL, SUPA_KEY)

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
    """Generate UID following the same pattern"""
    source_map = {'GOOGLE': 'G', 'META': 'M', 'Affiliate': 'A', 'Know': 'K', 'Whatsapp': 'W', 'Tele': 'T', 'BTL': 'B'}
    source_char = source_map.get(source, 'X')
    sequence_char = chr(65 + (sequence % 26))
    mobile_last4 = str(mobile_number).replace(" ", "").replace("-", "")[-4:].zfill(4)
    seq_num = f"{(sequence % 9999) + 1:04d}"
    return f"{source_char}{sequence_char}-{mobile_last4}-{seq_num}"

def get_next_sequence_batch(supabase, batch_size=200):
    """Get next sequence numbers in batch"""
    try:
        result = supabase.table("lead_master").select("id").order("id", desc=True).limit(1).execute()
        if result.data:
            start_seq = result.data[0]['id'] + 1
        else:
            start_seq = 1
        return list(range(start_seq, start_seq + batch_size))
    except Exception as e:
        print(f"❌ Error getting sequence numbers: {e}")
        return list(range(1, batch_size + 1))

def is_within_past_24_hours(created_time_str: str) -> bool:
    """Validate if lead is actually within past 24 hours"""
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
            twenty_four_hours_ago = now - timedelta(hours=24)
            
            is_recent = twenty_four_hours_ago <= created_time_utc <= now
            return is_recent
            
        except (ValueError, TypeError):
            continue
    
    return False

# ==================== DUPLICATE HANDLING FUNCTIONS ====================

def check_existing_leads_comprehensive(supabase, phone_numbers: List[str]):
    """Comprehensive check for existing leads in both tables"""
    try:
        if not phone_numbers:
            return {}, {}
        
        # Check lead_master table
        existing_master = supabase.table("lead_master")\
            .select("*")\
            .in_("customer_mobile_number", phone_numbers)\
            .execute()
        
        master_records = {row['customer_mobile_number']: row for row in existing_master.data}
        
        # Check duplicate_leads table
        existing_duplicate = supabase.table("duplicate_leads")\
            .select("*")\
            .in_("customer_mobile_number", phone_numbers)\
            .execute()
        
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

def process_leads_with_duplicates(supabase, unique_leads, master_records, duplicate_records):
    """Process leads with comprehensive duplicate handling"""
    new_leads = []
    updated_duplicates = 0
    skipped_duplicates = 0
    sequence_numbers = get_next_sequence_batch(supabase, len(unique_leads))
    sequence_idx = 0
    
    for lead in unique_leads:
        phone = lead['customer_mobile_number']
        current_source = lead['source']
        current_sub_source = lead['sub_source']
        current_date = lead['date']
        
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
                lead['uid'] = generate_uid(current_source, phone, sequence_numbers[sequence_idx])
                sequence_idx += 1
                new_leads.append(lead)
                
        except Exception as e:
            print(f"❌ Error processing lead {phone}: {e}")
            continue
    
    return new_leads, updated_duplicates, skipped_duplicates

def bulk_insert_with_individual_fallback(supabase, leads_data: List[dict], batch_size: int = 100):
    """Bulk insert with individual fallback and comprehensive duplicate handling"""
    successful = 0
    failed = 0
    
    if not leads_data:
        return 0, 0
    
    # Process in batches
    for i in range(0, len(leads_data), batch_size):
        batch = leads_data[i:i + batch_size]
        
        try:
            # Attempt bulk insert
            supabase.table("lead_master").insert(batch).execute()
            successful += len(batch)
            print(f"✅ Batch inserted: {len(batch)} leads")
            
        except Exception as e:
            print(f"⚠️ Batch insert failed, trying individual inserts...")
            
            # Individual insert fallback with duplicate handling
            for lead in batch:
                if insert_lead_safely(supabase, lead):
                    successful += 1
                    print(f"✅ Inserted: {lead['uid']} | {lead['customer_name']} | {lead['customer_mobile_number']}")
                else:
                    failed += 1
        
        # Small delay between batches
        if i + batch_size < len(leads_data):
            time.sleep(0.2)
    
    return successful, failed

# ==================== META API CLASS (Same as before) ====================

class RobustMetaAPI:
    def __init__(self, page_token: str):
        self.page_token = page_token
        self.api_version = "v21.0"
        self._campaign_cache = {}
        self.semaphore = asyncio.Semaphore(3)
    
    async def _make_robust_request(self, session, url: str, params: dict = None, max_retries: int = 3) -> dict:
        """Make API request with robust error handling and retries"""
        
        for attempt in range(max_retries):
            async with self.semaphore:
                try:
                    await asyncio.sleep(1 + attempt)
                    
                    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', 300))
                            print(f"⏳ Rate limited, waiting {retry_after}s...")
                            await asyncio.sleep(retry_after)
                            continue
                        elif response.status == 500:
                            wait_time = (2 ** attempt) * 5
                            print(f"⚠️ Server error (attempt {attempt + 1}/{max_retries}), waiting {wait_time}s...")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                print(f"❌ Server error after {max_retries} attempts, skipping this request")
                                return {}
                        else:
                            print(f"⚠️ HTTP {response.status} error")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return {}
                
                except Exception as e:
                    print(f"❌ Request error (attempt {attempt + 1}/{max_retries}): {str(e)[:100]}...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        return {}
        
        return {}
    
    def get_campaign_name_safe(self, form_id: str, form_name: str) -> str:
        """Safe campaign name generation with caching"""
        if form_id in self._campaign_cache:
            return self._campaign_cache[form_id]
        
        try:
            cleaned = str(form_name).strip() if form_name else f"Form-{form_id}"
            cleaned = cleaned.replace('@', 'at').replace('&', 'and').replace('-copy', '').replace('_copy', '')
            cleaned = ' '.join(word.capitalize() for word in cleaned.split() if word)
            result = cleaned or f"Form-{form_id}"
        except Exception as e:
            result = f"Form-{form_id}"
        
        self._campaign_cache[form_id] = result
        return result
    
    async def fetch_forms_robust(self):
        """Fetch forms with robust error handling"""
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=60)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            url = f"https://graph.facebook.com/{self.api_version}/{PAGE_ID}/leadgen_forms"
            params = {
                "access_token": self.page_token,
                "fields": "id,name,status",
                "limit": 100
            }
            
            response = await self._make_robust_request(session, url, params)
            forms = response.get("data", [])
            
            enhanced_forms = []
            for form in forms:
                try:
                    campaign_name = self.get_campaign_name_safe(form['id'], form.get('name', f'Form-{form["id"]}'))
                    enhanced_forms.append({**form, 'campaign_name': campaign_name})
                except Exception as e:
                    continue
            
            return enhanced_forms
    
    async def fetch_form_leads_robust(self, session, form_id: str, since_hours: int = 24):
        """Fetch leads for a single form with validation"""
        try:
            since_time = int((datetime.now(timezone.utc) - timedelta(hours=since_hours)).timestamp())
            
            url = f"https://graph.facebook.com/{self.api_version}/{form_id}/leads"
            params = {
                "access_token": self.page_token,
                "limit": 50,
                "since": since_time
            }
            
            all_leads = []
            page_count = 0
            max_pages = 10
            consecutive_old_pages = 0
            
            while url and page_count < max_pages and consecutive_old_pages < 3:
                response = await self._make_robust_request(session, url, params)
                
                if not response.get("data"):
                    break
                
                leads = response["data"]
                recent_leads = []
                
                # Filter leads to ENSURE they're within 24 hours
                for lead in leads:
                    created_time = lead.get("created_time", "")
                    if is_within_past_24_hours(created_time):
                        recent_leads.append(lead)
                
                all_leads.extend(recent_leads)
                page_count += 1
                
                if not recent_leads:
                    consecutive_old_pages += 1
                else:
                    consecutive_old_pages = 0
                
                paging = response.get("paging", {})
                url = paging.get("next")
                params = None
                
                if not url:
                    break
                
                await asyncio.sleep(0.5)
            
            return form_id, all_leads
            
        except Exception as e:
            print(f"❌ Error fetching leads for form {form_id}: {str(e)[:100]}...")
            return form_id, []
    
    async def fetch_all_leads_batch_safe(self, form_ids: List[str]):
        """Fetch all leads in safe batches"""
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=120)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            all_results = {}
            
            # Process forms in small batches of 5
            batch_size = 5
            for i in range(0, len(form_ids), batch_size):
                batch = form_ids[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(form_ids) + batch_size - 1) // batch_size
                
                print(f"📥 Processing batch {batch_num}/{total_batches} ({len(batch)} forms)...")
                
                tasks = [self.fetch_form_leads_robust(session, form_id) for form_id in batch]
                
                try:
                    results = await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True), 
                        timeout=300
                    )
                    
                    for result in results:
                        if isinstance(result, tuple) and len(result) == 2:
                            form_id, leads = result
                            all_results[form_id] = leads
                            if leads:
                                print(f"   ✅ Form {form_id}: {len(leads)} recent leads")
                        elif isinstance(result, Exception):
                            print(f"   ❌ Exception: {str(result)[:100]}...")
                
                except asyncio.TimeoutError:
                    print(f"   ⏰ Batch {batch_num} timeout, continuing with next batch...")
                
                if i + batch_size < len(form_ids):
                    wait_time = 5
                    print(f"   ⏳ Waiting {wait_time}s before next batch...")
                    await asyncio.sleep(wait_time)
            
            return all_results

def map_lead_with_validation(raw: dict, campaign_name: str) -> Optional[dict]:
    """Map lead with proper 24-hour validation"""
    try:
        # First validate the timestamp
        created_time = raw.get("created_time", "")
        if not is_within_past_24_hours(created_time):
            return None
        
        field_data = raw.get("field_data", [])
        if not field_data:
            return None
        
        # Fast field extraction
        answers = {}
        for field in field_data:
            try:
                field_name = field.get("name", "").lower()
                field_values = field.get("values", [])
                if field_values and field_values[0]:
                    answers[field_name] = str(field_values[0]).strip()
            except:
                continue
        
        # Field matching
        name_fields = ["full_name", "full name", "name", "customer_name", "first_name", "last_name"]
        phone_fields = ["phone_number", "contact_number", "phone", "mobile", "mobile_number", "cell"]
        
        name = ""
        for field in name_fields:
            if field in answers and answers[field]:
                name = answers[field]
                break
        
        phone = ""
        for field in phone_fields:
            if field in answers and answers[field]:
                phone = answers[field]
                break
        
        if not phone:
            return None
        
        normalized_phone = normalize_phone_number(phone)
        if not normalized_phone:
            return None
        
        # Parse date properly
        try:
            if created_time and len(created_time) >= 10:
                created = created_time[:10]
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
        return None

async def sync_complete_with_duplicates():
    """Complete sync with full duplicate handling like your original script"""
    print("🚀 COMPLETE Meta API sync with full duplicate handling starting...")
    start_time = time.time()
    
    try:
        # Initialize API client
        meta_api = RobustMetaAPI(PAGE_TOKEN)
        
        # Step 1: Fetch forms
        print("📋 Fetching forms...")
        forms = await meta_api.fetch_forms_robust()
        
        if not forms:
            print("❌ No forms available")
            return
        
        print(f"✅ Found {len(forms)} forms in {time.time() - start_time:.2f}s")
        
        # Step 2: Fetch leads
        print(f"📥 Fetching leads from past 24 hours...")
        form_leads = await meta_api.fetch_all_leads_batch_safe([f['id'] for f in forms])
        
        total_raw_leads = sum(len(leads) for leads in form_leads.values())
        print(f"✅ Lead fetching completed in {time.time() - start_time:.2f}s")
        print(f"📊 Raw leads collected: {total_raw_leads}")
        
        # Step 3: Process and validate leads
        print("⚡ Processing leads with 24-hour validation...")
        all_leads = []
        form_data = {f['id']: f for f in forms}
        leads_by_form = {}
        
        for form_id, leads in form_leads.items():
            if not leads:
                continue
                
            form_info = form_data.get(form_id, {})
            campaign_name = form_info.get('campaign_name', 'Unknown Campaign')
            
            form_valid_leads = []
            for lead in leads:
                mapped_lead = map_lead_with_validation(lead, campaign_name)
                if mapped_lead and mapped_lead["customer_mobile_number"]:
                    all_leads.append(mapped_lead)
                    form_valid_leads.append(mapped_lead)
            
            if form_valid_leads:
                leads_by_form[form_info.get('name', form_id)] = len(form_valid_leads)
        
        if not all_leads:
            print("📭 No valid leads from past 24 hours found")
            return
        
        # Print leads by form
        print(f"\n📊 Valid leads by form (past 24 hours only):")
        for form_name, count in leads_by_form.items():
            print(f"   • {form_name}: {count} leads")
        
        print(f"\n📊 Total valid leads: {len(all_leads)}")
        
        # Step 4: Intra-batch deduplication
        print("🧹 Removing intra-batch duplicates...")
        seen_combinations = set()
        deduplicated_leads = []
        intra_batch_duplicates = 0
        
        for lead in all_leads:
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
        
        print(f"✅ Unique leads after intra-batch deduplication: {len(deduplicated_leads)}")
        
        # Step 5: Check existing leads in both tables
        print("🔍 Comprehensive duplicate checking...")
        phone_numbers = [lead['customer_mobile_number'] for lead in deduplicated_leads]
        master_records, duplicate_records = check_existing_leads_comprehensive(supabase, phone_numbers)
        
        # Step 6: Process leads with full duplicate handling
        print("🔄 Processing leads with duplicate management...")
        new_leads, updated_duplicates, skipped_duplicates = process_leads_with_duplicates(
            supabase, deduplicated_leads, master_records, duplicate_records
        )
        
        print(f"📝 New leads to insert: {len(new_leads)}")
        
        # Step 7: Insert new leads with safe handling
        if new_leads:
            print("💾 Inserting new leads...")
            insert_start = time.time()
            successful, failed = bulk_insert_with_individual_fallback(supabase, new_leads, batch_size=100)
            
            print(f"\n🎯 FINAL RESULTS:")
            print(f"   📥 Total raw leads collected: {total_raw_leads}")
            print(f"   ✅ Valid 24h leads processed: {len(all_leads)}")
            print(f"   🔄 After intra-batch deduplication: {len(deduplicated_leads)}")
            print(f"   ➕ New leads inserted: {successful}")
            print(f"   🔄 Duplicate sources updated: {updated_duplicates}")
            print(f"   ⏭️ Duplicate sources skipped: {skipped_duplicates}")
            print(f"   ❌ Failed insertions: {failed}")
            print(f"   ⚡ Insert time: {time.time() - insert_start:.2f}s")
            print(f"   🚀 TOTAL TIME: {time.time() - start_time:.2f}s")
        else:
            print("📭 No new leads to insert")
            print(f"\n🎯 SUMMARY:")
            print(f"   📥 Total raw leads: {total_raw_leads}")
            print(f"   ✅ Valid 24h leads: {len(all_leads)}")
            print(f"   🔄 Duplicate sources updated: {updated_duplicates}")
            print(f"   ⏭️ Duplicate sources skipped: {skipped_duplicates}")
            print(f"   🚀 TOTAL TIME: {time.time() - start_time:.2f}s")
            
    except Exception as e:
        print(f"❌ Critical error: {str(e)[:200]}...")
        import traceback
        traceback.print_exc()

# Main execution
if __name__ == "__main__":
    try:
        print(f"🕐 Current time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"📅 Fetching leads from: {(datetime.now(timezone.utc) - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S UTC')} onwards")
        print()
        
        asyncio.run(sync_complete_with_duplicates())
        
    except KeyboardInterrupt:
        print("\n⚠️ Sync interrupted by user")
    except Exception as e:
        print(f"❌ Script failed: {str(e)[:200]}...")
        import traceback
        traceback.print_exc()
