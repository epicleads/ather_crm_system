#!/usr/bin/env python3
"""
Test script to debug Meta script execution
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_environment_variables():
    """Test if all required environment variables are present"""
    print("🔍 Testing Meta Script Environment Variables...")
    print("=" * 50)
    
    # Required variables for Meta script
    required_vars = [
        'SUPABASE_URL',
        'SUPABASE_ANON_KEY', 
        'META_PAGE_ACCESS_TOKEN',
        'PAGE_ID'
    ]
    
    missing_vars = []
    present_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Show first 10 characters for security
            masked_value = value[:10] + "..." if len(value) > 10 else "***"
            print(f"✅ {var}: {masked_value}")
            present_vars.append(var)
        else:
            print(f"❌ {var}: MISSING")
            missing_vars.append(var)
    
    print("=" * 50)
    print(f"📊 Summary:")
    print(f"✅ Present: {len(present_vars)}/{len(required_vars)}")
    print(f"❌ Missing: {len(missing_vars)}/{len(required_vars)}")
    
    if missing_vars:
        print(f"\n❌ Missing variables: {', '.join(missing_vars)}")
        print("🔧 Please add these to your GitHub Secrets or .env file")
        return False
    else:
        print("✅ All required variables are present!")
        return True

def test_supabase_connection():
    """Test Supabase connection"""
    print("\n🔍 Testing Supabase Connection...")
    print("=" * 50)
    
    try:
        from supabase import create_client
        
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            print("❌ Missing Supabase credentials")
            return False
        
        supabase = create_client(supabase_url, supabase_key)
        
        # Test connection by querying lead_master table
        result = supabase.table("lead_master").select("id").limit(1).execute()
        print("✅ Supabase connection successful!")
        print(f"📊 Found {len(result.data)} records in lead_master table")
        return True
        
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False

def test_meta_api():
    """Test Meta API connection"""
    print("\n🔍 Testing Meta API Connection...")
    print("=" * 50)
    
    try:
        import requests
        
        page_token = os.getenv('META_PAGE_ACCESS_TOKEN')
        page_id = os.getenv('PAGE_ID')
        
        if not page_token or not page_id:
            print("❌ Missing Meta API credentials")
            return False
        
        # Test Meta API connection
        url = f"https://graph.facebook.com/v18.0/{page_id}/forms"
        params = {
            'access_token': page_token,
            'limit': 1
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Meta API connection successful!")
            print(f"📊 Found {len(data.get('data', []))} forms")
            return True
        else:
            print(f"❌ Meta API connection failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Meta API connection failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Meta Script Debug Test")
    print("=" * 50)
    
    # Test 1: Environment variables
    env_ok = test_environment_variables()
    
    # Test 2: Supabase connection
    supabase_ok = test_supabase_connection()
    
    # Test 3: Meta API connection
    meta_ok = test_meta_api()
    
    print("\n" + "=" * 50)
    print("📊 FINAL RESULTS:")
    print(f"✅ Environment Variables: {'PASS' if env_ok else 'FAIL'}")
    print(f"✅ Supabase Connection: {'PASS' if supabase_ok else 'FAIL'}")
    print(f"✅ Meta API Connection: {'PASS' if meta_ok else 'FAIL'}")
    
    if env_ok and supabase_ok and meta_ok:
        print("\n🎉 All tests passed! Meta script should work correctly.")
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")

if __name__ == "__main__":
    main() 