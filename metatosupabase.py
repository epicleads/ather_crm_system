import os, requests, time, json, hashlib, threading
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Set, Optional, Tuple

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

def check_existing_leads_for_consolidation(phone_numbers: Set[str]) -> Dict[str, Dict]:
    """Check existing leads by normalized phone numbers"""
    if not phone_numbers:
        return {}
    
    normalized_phones = {normalize_phone_number(p) for p in phone_numbers if normalize_phone_number(p)}
    if not normalized_phones:
        return {}
    
    try:
        result = supabase.table("lead_master").select("*").execute()
        existing_leads = {}
        
        for row in result.data:
            normalized_existing = normalize_phone_number(row.get('customer_mobile_number', ''))
            if normalized_existing in normalized_phones:
                existing_leads[normalized_existing] = row
        
        print(f"📞 Found {len(existing_leads)} existing phone numbers")
        return existing_leads
    except Exception as e:
        print(f"❌ Error checking leads: {e}")
        return {}

def combine_sources(existing: str, new: str) -> str:
    """Combine sources without duplicates - e.g., 'Google,Meta' + 'BTL' = 'BTL,Google,Meta'"""
    existing_set = set(existing.split(',')) if existing else set()
    new_set = {new} if new else set()
    existing_set.discard('')
    new_set.discard('')
    return ','.join(sorted(existing_set.union(new_set)))

def generate_consistent_uid_from_phone(mobile: str) -> str:
    """Generate consistent UID from normalized phone"""
    normalized = normalize_phone_number(mobile)
    if not normalized:
        normalized = str(int(time.time()))[-10:]
    
    phone_hash = hashlib.md5(normalized.encode()).hexdigest()[:8].upper()
    mobile_last4 = normalized[-4:].zfill(4) if len(normalized) >= 4 else normalized.zfill(4)
    return f"M{phone_hash[:4]}-{mobile_last4}"

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
                    'campaign_name': campaign_name,
                    'source_name': "Meta"  # Changed: Just "Meta" instead of "Meta(campaign_name)"
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

def map_lead_with_source(raw: dict, source_name: str, campaign_name: str, existing_lead_data: dict = None) -> Optional[dict]:
    """Map raw lead data to database format"""
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
    
    uid = existing_lead_data['uid'] if existing_lead_data else generate_consistent_uid_from_phone(normalized_phone)
    now_iso = datetime.now().isoformat()
    
    return {
        "uid": uid, "date": created, "customer_name": name, "customer_mobile_number": normalized_phone,
        "source": source_name, "campaign": campaign_name,  # Added: campaign column
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
        campaign_name, source_name = form['campaign_name'], form['source_name']
        leads = all_form_leads.get(form_id, [])
        
        print(f"📄 {form_name} ({form_id})")
        print(f"   📊 Campaign: {campaign_name} | Source: {source_name}")
        
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
    """Enhanced sync with source consolidation"""
    print(f"🔄 Enhanced sync starting...")
    print(f"🎯 One Phone Number = One UID across all sources")
    
    forms = meta_api.get_forms_with_campaign_info_safe()
    all_form_leads = meta_api.get_form_leads_parallel([f['id'] for f in forms])
    
    all_new_leads = []
    all_phone_numbers = set()
    form_data = {f['id']: f for f in forms}
    
    for form_id, leads in all_form_leads.items():
        form_info = form_data.get(form_id, {})
        source_name = form_info.get('source_name', 'Meta')  # Changed: Just "Meta"
        campaign_name = form_info.get('campaign_name', 'Unknown Campaign')  # Campaign name separately
        valid_leads = 0
        
        for raw_lead in leads:
            mapped_lead = map_lead_with_source(raw_lead, source_name, campaign_name)  # Pass both source and campaign
            if mapped_lead and mapped_lead["customer_mobile_number"]:
                all_new_leads.append(mapped_lead)
                all_phone_numbers.add(mapped_lead["customer_mobile_number"])
                valid_leads += 1
        
        if valid_leads > 0:
            print(f"✅ {form_info.get('name', form_id)}: {valid_leads} leads")
    
    if not all_new_leads:
        print("📭 No valid leads found.")
        return
    
    print(f"\n📊 Collected {len(all_new_leads)} leads, {len(all_phone_numbers)} unique phones")
    
    existing_leads_data = check_existing_leads_for_consolidation(all_phone_numbers)
    new_leads, update_leads = [], []
    
    # Analyze leads for source consolidation
    for lead in all_new_leads:
        normalized_phone = lead['customer_mobile_number']
        new_source = lead['source']
        
        if normalized_phone in existing_leads_data:
            # EXISTING PHONE: Check if we need to add new source
            existing_record = existing_leads_data[normalized_phone]
            existing_source = existing_record.get('source', '')
            existing_sources = set(existing_source.split(',')) if existing_source else set()
            existing_sources.discard('')
            
            # Only update if new source is not already present
            if new_source not in existing_sources:
                combined_source = combine_sources(existing_source, new_source)
                update_leads.append({
                    'phone': normalized_phone, 'uid': existing_record['uid'], 'id': existing_record['id'],
                    'existing_source': existing_source, 'new_source': combined_source
                })
                print(f"🔄 Will consolidate: {normalized_phone} (UID: {existing_record['uid']}) | {existing_source} → {combined_source}")
            else:
                print(f"✅ Phone {normalized_phone} already has source: {new_source}")
        else:
            # NEW PHONE: Generate consistent UID
            lead['uid'] = generate_consistent_uid_from_phone(normalized_phone)
            new_leads.append(lead)
            print(f"🆕 New phone {normalized_phone} → UID: {lead['uid']} | Campaign: {lead['campaign']}")  # Updated: Show campaign info
    
    # Process updates
    successful_updates = 0
    if update_leads:
        print(f"\n🔄 Updating {len(update_leads)} existing records...")
        for update in update_leads:
            try:
                supabase.table("lead_master").update({
                    'source': update['new_source'],
                    'updated_at': datetime.now().isoformat()
                }).eq('id', update['id']).execute()
                print(f"✅ Updated {update['uid']}: {update['new_source']}")
                successful_updates += 1
            except Exception as e:
                print(f"❌ Failed {update['phone']}: {e}")
    
    # Process new leads
    inserted = 0
    if new_leads:
        print(f"\n🆕 Inserting {len(new_leads)} new leads...")
        batch_size = 100
        
        for i in range(0, len(new_leads), batch_size):
            batch = new_leads[i:i + batch_size]
            try:
                response = supabase.table("lead_master").insert(batch).execute()
                batch_inserted = len(response.data) if response.data else len(batch)
                inserted += batch_inserted
                print(f"✅ Batch {i//batch_size + 1}: {batch_inserted} leads")
            except Exception as e:
                print(f"❌ Batch failed: {e}")
                for lead in batch:
                    try:
                        supabase.table("lead_master").insert(lead).execute()
                        inserted += 1
                    except:
                        pass
    
    print(f"\n📊 SUMMARY:")
    print(f"✅ New leads inserted: {inserted}")
    print(f"🔄 Records updated with consolidated sources: {successful_updates}")
    print(f"📱 Total phones processed: {len(all_phone_numbers)}")
    print(f"\n🎯 SOURCE CONSOLIDATION EXAMPLES:")
    print(f"   • Same phone from Google + Meta → 'Google,Meta'")
    print(f"   • Same phone from Meta + BTL → 'BTL,Meta'") 
    print(f"   • Same UID maintained across all sources")
    print(f"   • Phone variations (91-XXX, 0XXX, XXX) treated as same number")
    print(f"   • Campaign names stored separately in 'campaign' column")

# Compatibility functions
def preview_field_names():
    preview_field_names_optimized()

def sync_to_db():
    sync_to_db_optimized()

if __name__ == "__main__":
    preview_field_names()
    sync_to_db()