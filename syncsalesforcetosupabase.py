import os
from simple_salesforce import Salesforce
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
from supabase import create_client, Client

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
past_24_hours = now_ist - timedelta(hours=24)
start_time = past_24_hours.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
end_time = now_ist.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

print(f"📅 Fetching leads from {past_24_hours} IST to {now_ist} IST")

def map_source(raw_source):
    affiliate_map = {
        'Bikewale': 'Affiliate Bikewale',
        'Bikewale-Q': 'Affiliate Bikewale',
        'Bikedekho': 'Affiliate Bikedekho',
        'Bikedekho-Q': 'Affiliate Bikedekho',
        '91 Wheels': 'Affiliate 91wheels',
        '91 Wheels-Q': 'Affiliate 91wheels'
    }
    oem_web = {
        'Website', 'Website_PO', 'Website_Optin', 'ai_chatbot', 'website_chatbot',
        'Newspaper Ad - WhatsApp'
    }
    oem_tele = {'Telephonic', 'cb', 'ivr_abandoned', 'ivr_callback', 'ivr_sales'}

    if raw_source in affiliate_map:
        return affiliate_map[raw_source]
    elif raw_source in oem_web:
        return 'OEM Web'
    elif raw_source in oem_tele:
        return 'OEM Tele'
    return None

def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = ''.join(filter(str.isdigit, str(phone)))
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits

def generate_uid(source, mobile_number, sequence):
    source_map = {
        'OEM': 'O', 'Affiliate': 'A', 'Web': 'W', 'Tele': 'T',
        'Bikewale': 'B', 'Bikedekho': 'D', '91wheels': 'N'
    }
    source_key = source.split()[0] if source else 'Unknown'
    if 'Bikewale' in source:
        source_key = 'Bikewale'
    elif 'Bikedekho' in source:
        source_key = 'Bikedekho'
    elif '91wheels' in source:
        source_key = '91wheels'
    source_char = source_map.get(source_key, 'S')
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

def check_existing_leads(supabase, phone_numbers):
    if not phone_numbers:
        return {}
    try:
        existing = supabase.table("lead_master").select("*").in_("customer_mobile_number", phone_numbers).execute()
        return {row['customer_mobile_number']: row for row in existing.data}
    except Exception as e:
        print(f"❌ Error checking existing leads: {e}")
        return {}

def combine_sources(existing: str, new: str) -> str:
    parts = set(existing.split(',') if existing else [])
    parts.add(new)
    return ','.join(sorted(filter(None, parts)))

query = f"""
    SELECT Id, Name, Phone, LeadSource, CreatedDate
    FROM Lead
    WHERE CreatedDate >= {start_time} AND CreatedDate <= {end_time}
"""
results = sf.query_all(query)['records']
print(f"\n📦 Total leads fetched (past 24 hours): {len(results)}")

if not results:
    print("❌ No leads found in the specified time range")
    exit()

leads_by_phone = {}
for lead in results:
    raw_source = lead.get("LeadSource")
    name = lead.get("Name", "Unknown")
    raw_phone = lead.get("Phone", "")
    created = lead.get("CreatedDate")

    if not raw_source or not raw_phone:
        continue

    mapped_source = map_source(raw_source)
    if not mapped_source:
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
            'sources': set()
        }

    leads_by_phone[phone]['sources'].add(mapped_source)

print(f"📱 Found {len(leads_by_phone)} unique phone numbers")

phone_list = list(leads_by_phone.keys())
existing_records = check_existing_leads(supabase, phone_list)

new_leads = []
update_leads = []

for phone, lead_data in leads_by_phone.items():
    new_sources = lead_data['sources']
    combined_source = ','.join(sorted(new_sources))

    if phone in existing_records:
        existing_record = existing_records[phone]
        existing_sources = set(existing_record['source'].split(',')) if existing_record['source'] else set()

        if not new_sources.issubset(existing_sources):
            all_sources = existing_sources.union(new_sources)
            existing_campaign = existing_record.get('campaign', None)

            update_leads.append({
                'phone': phone,
                'uid': existing_record['uid'],
                'id': existing_record['id'],
                'new_source': ','.join(sorted(all_sources)),
                'existing_campaign': existing_campaign
            })
            print(f"🔄 Will update sources for {phone}: {existing_record['source']} → {','.join(sorted(all_sources))}")
            if existing_campaign:
                print(f"   📊 Preserving existing campaign: {existing_campaign}")
        else:
            print(f"✅ Phone {phone} already has all sources: {existing_record['source']}")
    else:
        new_leads.append({
            'name': lead_data['name'],
            'phone': phone,
            'date': lead_data['date'],
            'source': combined_source
        })

if update_leads:
    print(f"🔄 Updating {len(update_leads)} existing records with new sources...")
    for update in update_leads:
        try:
            update_data = {
                'source': update['new_source'],
                'updated_at': datetime.now().isoformat()
            }
            supabase.table("lead_master").update(update_data).eq('id', update['id']).execute()
            print(f"✅ Updated UID: {update['uid']} | Phone: {update['phone']} | Sources: {update['new_source']}")
            if update['existing_campaign']:
                print(f"   📊 Campaign preserved: {update['existing_campaign']}")
        except Exception as e:
            print(f"❌ Failed to update {update['phone']}: {e}")

if not new_leads:
    print("✅ No completely new leads to insert.")
    if not update_leads:
        print("✅ All phone numbers already exist with same sources.")
    exit()

print(f"🆕 Found {len(new_leads)} completely new leads to insert")

sequence = get_next_sequence_number(supabase)
for lead in new_leads:
    first_source = lead['source'].split(',')[0]
    lead['uid'] = generate_uid(first_source, lead['phone'], sequence)
    sequence += 1
    print(f"🆕 Generated UID {lead['uid']} for phone: {lead['phone']}")

existing_uids_result = supabase.table("lead_master").select("uid").execute()
existing_uids = {row['uid'] for row in existing_uids_result.data}
uid_conflicts = [lead for lead in new_leads if lead['uid'] in existing_uids]

if uid_conflicts:
    print(f"⚠️ Found {len(uid_conflicts)} UID conflicts, regenerating...")
    sequence_start = get_next_sequence_number(supabase) + 1000
    for lead in uid_conflicts:
        first_source = lead['source'].split(',')[0]
        lead['uid'] = generate_uid(first_source, lead['phone'], sequence_start)
        sequence_start += 1

current_time = datetime.now().isoformat()
successful_inserts = 0
failed_inserts = 0

print(f"🚀 Inserting {len(new_leads)} new leads...")

for lead in new_leads:
    existing_record = existing_records.get(lead['phone'])
    existing_campaign = existing_record['campaign'] if existing_record and 'campaign' in existing_record else None

    lead_record = {
        'uid': lead['uid'],
        'date': lead['date'],
        'customer_name': lead['name'],
        'customer_mobile_number': lead['phone'],
        'source': lead['source'],
        'campaign': existing_campaign,  # ✅ Preserve campaign from previous Meta entry
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

    try:
        supabase.table("lead_master").insert(lead_record).execute()
        print(f"✅ Inserted UID: {lead['uid']} | Phone: {lead['phone']} | Sources: {lead['source']} | Campaign: {existing_campaign or 'None'}")
        successful_inserts += 1
    except Exception as e:
        print(f"❌ Failed to insert {lead['uid']} | Phone: {lead['phone']}: {e}")
        failed_inserts += 1

print(f"\n📊 SUMMARY:")
print(f"✅ Successfully inserted new leads: {successful_inserts}")
print(f"❌ Failed insertions: {failed_inserts}")
print(f"🔄 Updated existing records with new sources: {len(update_leads)}")
print(f"📱 Total unique phone numbers processed: {len(leads_by_phone)}")
print(f"📊 Campaign info: Existing Meta campaigns preserved even if Salesforce adds sources")
