import os
from simple_salesforce import Salesforce
from dotenv import load_dotenv
from datetime import datetime
import pytz
from supabase import create_client, Client

# --- Load environment variables ---
load_dotenv()

SF_USERNAME = os.getenv('SF_USERNAME')
SF_PASSWORD = os.getenv('SF_PASSWORD')
SF_SECURITY_TOKEN = os.getenv('SF_SECURITY_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')

# --- Connect to Salesforce ---
sf = Salesforce(username=SF_USERNAME, password=SF_PASSWORD, security_token=SF_SECURITY_TOKEN)
print("✅ Connected to Salesforce")

# --- Connect to Supabase ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✅ Connected to Supabase")

# --- Define today's IST time window ---
IST = pytz.timezone('Asia/Kolkata')
today = datetime.now(IST).date()
today_start = today.strftime('%Y-%m-%dT00:00:00Z')
today_end = today.strftime('%Y-%m-%dT23:59:59Z')

# --- Map lead source to internal tags ---
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
    oem_tele = {
        'Telephonic', 'cb', 'ivr_abandoned', 'ivr_callback', 'ivr_sales'
    }

    if raw_source in affiliate_map:
        return affiliate_map[raw_source]
    elif raw_source in oem_web:
        return 'OEM Web'
    elif raw_source in oem_tele:
        return 'OEM Tele'
    else:
        return None

# --- UID generator ---
def generate_uid(source, mobile_number, sequence):
    source_map = {
        'Google': 'G',
        'Meta': 'M',
        'Affiliate': 'A',
        'Know': 'K',
        'Tele': 'T',
        'OEM': 'W'
    }

    base_source = source.split()[0] if source else ''
    if base_source == "OEM" and "Web" in source:
        base_source = "OEM"
    elif base_source == "OEM" and "Tele" in source:
        base_source = "Tele"

    source_char = source_map.get(base_source, 'X')
    sequence_char = chr(65 + (sequence % 26))

    mobile_str = str(mobile_number).replace(' ', '').replace('-', '')
    mobile_last4 = mobile_str[-4:] if len(mobile_str) >= 4 else mobile_str.zfill(4)

    seq_num = f"{(sequence % 9999) + 1:04d}"

    return f"{source_char}{sequence_char}-{mobile_last4}-{seq_num}"

# --- Fetch today's leads from Salesforce ---
query = f"""
    SELECT Id, Name, Phone, LeadSource, CreatedDate
    FROM Lead
    WHERE CreatedDate >= {today_start} AND CreatedDate <= {today_end}
"""
results = sf.query_all(query)['records']
print(f"\n📦 Total leads fetched today: {len(results)}")

count = 0
skipped = 0
for i, lead in enumerate(results):
    raw_source = lead.get("LeadSource")
    name = lead.get("Name", "Unknown")
    phone = lead.get("Phone", "").replace(" ", "").replace("-", "")
    created = lead.get("CreatedDate")

    if not raw_source or not phone:
        skipped += 1
        continue

    mapped_source = map_source(raw_source)
    if not mapped_source:
        skipped += 1
        continue

    uid = generate_uid(mapped_source, phone, i)
    if not uid:
        skipped += 1
        continue

    # --- Check if UID already exists ---
    try:
        exists = supabase.table("lead_master").select("uid").eq("uid", uid).execute()
        if exists.data:
            continue
    except Exception as e:
        print(f"⚠️  Error checking existing UID: {e}")
        skipped += 1
        continue

    # --- Parse date ---
    try:
        created_date_obj = datetime.fromisoformat(created.replace("Z", "+00:00"))
        created_date = created_date_obj.date().isoformat()
    except Exception as e:
        print("⚠️  Failed to parse created date:", e)
        skipped += 1
        continue

    # --- Print for confirmation ---
    print(f"\n🎯 NEW LEAD #{count+1}")
    print(f"  Name    : {name}")
    print(f"  Phone   : {phone}")
    print(f"  Source  : {mapped_source}")
    print(f"  UID     : {uid}")
    print(f"  Date    : {created_date}")

    # --- Insert into Supabase ---
    try:
        response = supabase.table("lead_master").insert({
            "uid": uid,
            "date": created_date,
            "customer_name": name,
            "customer_mobile_number": phone,
            "source": mapped_source
        }).execute()

        if response.data:
            print("✅ Inserted into Supabase.")
            count += 1
        else:
            print("❌ Insert failed: No data returned")
            skipped += 1
            
    except Exception as e:
        print(f"❌ Insert failed with error: {e}")
        skipped += 1

# --- Final Summary ---
print(f"\n✅ Total new leads inserted: {count}")
print(f"🚫 Skipped (invalid/duplicate/unmapped): {skipped}")