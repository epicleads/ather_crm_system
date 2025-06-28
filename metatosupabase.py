import os, requests, time
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime

# ─── ENV ─────────────────────────────────────────────
load_dotenv()
PAGE_TOKEN   = os.getenv("META_PAGE_ACCESS_TOKEN")
PAGE_ID      = os.getenv("PAGE_ID")
SUPA_URL     = os.getenv("SUPABASE_URL")
SUPA_KEY     = os.getenv("SUPABASE_ANON_KEY")          # or service-role key

if not all([PAGE_TOKEN, PAGE_ID, SUPA_URL, SUPA_KEY]):
    raise SystemExit("❌  Check .env – one or more values missing!")

supabase = create_client(SUPA_URL, SUPA_KEY)

# ─── UID GENERATION (from your app.py) ──────────────
def generate_uid(source, mobile_number, sequence):
    """Generate UID based on source, mobile number, and sequence"""
    source_map = {
        'Google': 'G',
        'Meta': 'M',
        'Affiliate': 'A',
        'Know': 'K',
        'Whatsapp': 'W',
        'Tele': 'T'
    }
    
    source_char = source_map.get(source, 'X')
    
    # Get sequence character (A-Z)
    sequence_char = chr(65 + (sequence % 26))  # A=65 in ASCII
    
    # Get last 4 digits of mobile number
    mobile_str = str(mobile_number).replace(' ', '').replace('-', '').replace('+', '')
    mobile_last4 = mobile_str[-4:] if len(mobile_str) >= 4 else mobile_str.zfill(4)
    
    # Generate sequence number (0001, 0002, etc.)
    seq_num = f"{(sequence % 9999) + 1:04d}"
    
    return f"{source_char}{sequence_char}-{mobile_last4}-{seq_num}"

def get_next_sequence_for_source(source):
    """Get the next sequence number for a given source"""
    try:
        # Get count of existing records for this source
        result = supabase.table("lead_master")\
            .select("id", count="exact")\
            .eq("source", source)\
            .execute()
        
        return len(result.data) if result.data else 0
    except Exception as e:
        print(f"   ⚠️  Error getting sequence: {e}")
        # Fallback to timestamp-based sequence
        return int(time.time()) % 10000

# ─── META HELPERS ────────────────────────────────────
def fb_get(endpoint: str, **params):
    """GET wrapper with 3-retry & 15 s timeout."""
    params["access_token"] = PAGE_TOKEN
    for attempt in range(3):
        try:
            r = requests.get(f"https://graph.facebook.com/v23.0/{endpoint}",
                             params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  Meta API error (attempt {attempt + 1}/3):", e)
            if attempt < 2:  # Don't sleep on the last attempt
                time.sleep(2)
        except Exception as e:
            print(f"   ⚠️  Unexpected error (attempt {attempt + 1}/3):", e)
            if attempt < 2:
                time.sleep(2)
    return {}

def list_forms():
    return fb_get(f"{PAGE_ID}/leadgen_forms").get("data", [])

def list_leads(form_id):
    return fb_get(f"{form_id}/leads").get("data", [])

# ─── MAPPING ─────────────────────────────────────────
def map_lead(raw: dict) -> dict | None:
    """Return dict ready for DB insert (or None if unusable)."""
    answers = {f["name"].lower(): f["values"][0] for f in raw.get("field_data", [])}
    name  = answers.get("full_name") or answers.get("full name")
    phone = answers.get("phone_number") or answers.get("contact_number")
    if not (name or phone):
        return None                                      # skip useless rows

    created = raw.get("created_time", "")[:10]           # YYYY-MM-DD
    try:
        datetime.strptime(created, "%Y-%m-%d")
    except ValueError:
        created = datetime.utcnow().date().isoformat()

    # Get sequence and generate proper UID
    sequence = get_next_sequence_for_source("Meta")
    uid = generate_uid("Meta", phone or "0000", sequence)

    return {
        "uid": uid,                                      # Include UID in the data
        "data": {                                        # Actual data to insert
            "uid": uid,                                  # Include UID here too
            "date": created,
            "customer_name": name or "",
            "customer_mobile_number": phone or "",
            "source": "Meta",
        }
    }

# ─── OPTIONAL PREVIEW ────────────────────────────────
def preview_field_names():
    """Print every form's unique field names (for verification)."""
    print("\n📝 Field-name preview – use Ctrl-C to abort if wrong\n")
    global_set = set()
    for f in list_forms():
        print(f"📄 {f['name']} ({f['id']})")
        local = set()
        for lead in list_leads(f["id"]):
            for fd in lead.get("field_data", []):
                local.add(fd["name"])
                global_set.add(fd["name"])
        print("   • " + "  • ".join(sorted(local)) if local else "   ⚠️  No leads.")
    print("\n🧾  ALL UNIQUE FIELDS:", ", ".join(sorted(global_set)), "\n")

# ─── DB SYNC ─────────────────────────────────────────
def sync_to_db():
    inserted = skipped = 0
    for f in list_forms():
        print(f"Processing form: {f['name']}")
        leads = list_leads(f["id"])
        
        for raw in leads:
            row = map_lead(raw)
            if not row:
                skipped += 1
                continue
                
            try:
                # Check if lead already exists based on phone and name
                existing = supabase.table("lead_master")\
                    .select("uid")\
                    .eq("customer_name", row["data"]["customer_name"])\
                    .eq("customer_mobile_number", row["data"]["customer_mobile_number"])\
                    .eq("source", "Meta")\
                    .execute()
                
                if existing.data:
                    print(f"   ⏭️  Skipped duplicate: {row['data']['customer_name']}")
                    skipped += 1
                    continue
                
                # Insert new record
                response = supabase.table("lead_master")\
                    .insert(row["data"])\
                    .execute()
                inserted += 1
                print(f"   ✅ Inserted: {row['data']['customer_name']} (UID: {row['data']['uid']})")
                
            except Exception as e:
                print(f"   ❌ DB insert error: {e}")
                skipped += 1
                    
    print(f"\n✅  Inserted {inserted}  |  Skipped {skipped}")

# ─── ALTERNATIVE DB SYNC (with better error handling) ────
def sync_to_db_alternative():
    """Alternative approach with better duplicate handling."""
    inserted = updated = skipped = 0
    
    for f in list_forms():
        print(f"Processing form: {f['name']}")
        leads = list_leads(f["id"])
        
        for raw in leads:
            row = map_lead(raw)
            if not row:
                skipped += 1
                continue
                
            try:
                # Check if record exists (more flexible matching)
                existing = supabase.table("lead_master")\
                    .select("uid")\
                    .eq("customer_mobile_number", row["data"]["customer_mobile_number"])\
                    .eq("source", "Meta")\
                    .execute()
                
                if existing.data:
                    print(f"   ⏭️  Skipped duplicate: {row['data']['customer_name']} (phone: {row['data']['customer_mobile_number']})")
                    skipped += 1
                    continue
                
                # Insert new record
                response = supabase.table("lead_master")\
                    .insert(row["data"])\
                    .execute()
                inserted += 1
                print(f"   ✅ Inserted: {row['data']['customer_name']} (UID: {row['data']['uid']})")
                    
            except Exception as e:
                print(f"   ❌ DB operation error: {e}")
                skipped += 1
                
    print(f"\n✅  Inserted {inserted}  |  Updated {updated}  |  Skipped {skipped}")

# ─── RUN ─────────────────────────────────────────────
if __name__ == "__main__":
    try:
        # 1) Preview all field names
        preview_field_names()
        
        # 2) Sync to database
        print("Starting database sync...")
        sync_to_db()
        
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        print("\nTrying alternative sync method...")
        try:
            sync_to_db_alternative()
        except Exception as e2:
            print(f"❌ Alternative method also failed: {e2}")