import requests
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load .env credentials
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
KNOW_SR_KEY = os.getenv("KNOW_SR_KEY")
KNOW_X_API_KEY = os.getenv("KNOW_X_API_KEY")

# SR number to source mapping
number_to_source = {
    '+918929841338': 'Google',
    '+917353089911': 'Meta',
    '+919513249906': 'BTL',
    '+918071023606': 'BTL'
}

def generate_uid(source, mobile_number, sequence):
    source_map = {'Google': 'G', 'Meta': 'M', 'Affiliate': 'A', 'Know': 'K', 'Whatsapp': 'W', 'Tele': 'T', 'BTL': 'B'}
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

    def get_call_logs(self, start_date, end_date, limit=500):
        url = f"{self.base_url}/{self.channel}/v1/account/calllog"
        headers = self.headers.copy()
        headers.update({
            'start_time': f"{start_date} 00:00:00+05:30",
            'end_time': f"{end_date} 23:59:59+05:30"
        })
        try:
            resp = requests.get(url, headers=headers, params={'limit': limit})
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            print("❌ Request failed:", e)
        return {}

    def extract_records(self, response):
        return response.get('objects', []) if isinstance(response, dict) else []

def main():
    client = KnowlarityAPI(KNOW_SR_KEY, KNOW_X_API_KEY)
    today_str = datetime.now().strftime("%Y-%m-%d")
    records = client.extract_records(client.get_call_logs(today_str, today_str))
    df = pd.DataFrame(records)

    if df.empty:
        print(f"❌ No call logs for {today_str}")
        return

    df = df[df['knowlarity_number'].isin(number_to_source)].copy()
    if df.empty:
        print("⚠ No known SR calls (Google/Meta/BTL) found.")
        return

    df['source'] = df['knowlarity_number'].map(number_to_source)
    df['customer_mobile_number'] = df['customer_number']
    df['customer_name'] = 'No Name(Knowlarity)'
    
    # FIX: Convert date to string format for JSON serialization
    df['date'] = pd.to_datetime(df['start_time']).dt.date.astype(str)
    
    df = df.drop_duplicates(subset=['customer_mobile_number', 'source']).reset_index(drop=True)
    df['uid'] = [generate_uid(row['source'], row['customer_mobile_number'], idx) for idx, row in df.iterrows()]
    
    # FIX: Convert timestamps to ISO format strings for JSON serialization
    current_time = datetime.now().isoformat()
    df['created_at'] = df['updated_at'] = current_time

    # Add default nulls
    default_fields = {
        'cre_name': None, 'lead_category': None, 'model_interested': None, 'branch': None, 'ps_name': None,
        'assigned': 'No', 'mail_status': None, 'lead_status': 'Pending', 'follow_up_date': None,
        'first_call_date': None, 'first_remark': None, 'second_call_date': None, 'second_remark': None,
        'third_call_date': None, 'third_remark': None, 'fourth_call_date': None, 'fourth_remark': None,
        'fifth_call_date': None, 'fifth_remark': None, 'sixth_call_date': None, 'sixth_remark': None,
        'seventh_call_date': None, 'seventh_remark': None, 'final_status': 'Pending'
    }
    for col, val in default_fields.items():
        df[col] = val

    final_cols = ['uid', 'date', 'customer_name', 'customer_mobile_number', 'source',
                  'cre_name', 'lead_category', 'model_interested', 'branch', 'ps_name',
                  'assigned', 'mail_status', 'lead_status', 'follow_up_date',
                  'first_call_date', 'first_remark', 'second_call_date', 'second_remark',
                  'third_call_date', 'third_remark', 'fourth_call_date', 'fourth_remark',
                  'fifth_call_date', 'fifth_remark', 'sixth_call_date', 'sixth_remark',
                  'seventh_call_date', 'seventh_remark', 'final_status',
                  'created_at', 'updated_at']
    df = df[final_cols]

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    existing = supabase.table("lead_master").select("uid").execute()
    existing_uids = {row['uid'] for row in existing.data}
    to_insert = df[~df['uid'].isin(existing_uids)]

    if to_insert.empty:
        print("✅ No new leads to insert.")
        return

    print(f"🚀 Inserting {len(to_insert)} new leads...")

    for row in to_insert.to_dict(orient="records"):
        try:
            supabase.table("lead_master").insert(row).execute()
            print(f"✅ Inserted UID: {row['uid']}")
        except Exception as e:
            print(f"❌ Failed to insert {row['uid']}: {e}")

if __name__ == "__main__":
    main()