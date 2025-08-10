#!/usr/bin/env python3
"""
Setup Auto Assign Configuration
==============================

This script sets up auto assign configurations for all available sources,
distributing them among the available CREs for fair distribution.
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL_UDAY3') or os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_ANON_KEY_UDAY3') or os.getenv('SUPABASE_ANON_KEY')

if not supabase_url or not supabase_key:
    print("❌ Error: Missing Supabase credentials")
    sys.exit(1)

supabase: Client = create_client(supabase_url, supabase_key)

def get_available_sources():
    """Get all available sources from lead_master table"""
    try:
        result = supabase.table('lead_master').select('source').execute()
        sources = list(set([lead['source'] for lead in result.data if lead.get('source')]))
        return sorted(sources)
    except Exception as e:
        print(f"❌ Error getting sources: {e}")
        return []

def get_active_cres():
    """Get all active CREs"""
    try:
        result = supabase.table('cre_users').select('id, name, auto_assign_count').eq('is_active', True).execute()
        return result.data or []
    except Exception as e:
        print(f"❌ Error getting CREs: {e}")
        return []

def clear_existing_configs():
    """Clear existing auto assign configurations"""
    try:
        result = supabase.table('auto_assign_config').delete().neq('id', 0).execute()
        print(f"✅ Cleared {len(result.data) if result.data else 0} existing configurations")
        return True
    except Exception as e:
        print(f"❌ Error clearing configs: {e}")
        return False

def create_auto_assign_configs():
    """Create auto assign configurations for all sources"""
    sources = get_available_sources()
    cres = get_active_cres()
    
    if not sources:
        print("❌ No sources found")
        return False
    
    if not cres:
        print("❌ No active CREs found")
        return False
    
    print(f"📊 Setting up auto assign for {len(sources)} sources among {len(cres)} CREs")
    
    # Sort CREs by auto_assign_count to distribute fairly
    cres_sorted = sorted(cres, key=lambda x: x.get('auto_assign_count', 0))
    
    configs_created = 0
    
    for i, source in enumerate(sources):
        # Round-robin distribution among CREs
        cre = cres_sorted[i % len(cres_sorted)]
        
        try:
            # Create configuration
            config_data = {
                'source': source,
                'cre_id': cre['id'],
                'is_active': True,
                'priority': 1
            }
            
            result = supabase.table('auto_assign_config').insert(config_data).execute()
            
            if result.data:
                print(f"✅ {source} -> {cre['name']} (ID: {cre['id']})")
                configs_created += 1
            else:
                print(f"❌ Failed to create config for {source}")
                
        except Exception as e:
            print(f"❌ Error creating config for {source}: {e}")
    
    print(f"\n🎯 Created {configs_created} auto assign configurations")
    return configs_created > 0

def verify_configurations():
    """Verify that configurations were created properly"""
    print("\n🔍 Verifying configurations...")
    
    try:
        result = supabase.table('auto_assign_config').select('*').execute()
        configs = result.data or []
        
        if configs:
            print(f"✅ Found {len(configs)} configurations:")
            for config in configs:
                print(f"   • {config['source']} -> CRE ID: {config['cre_id']} (Active: {config['is_active']})")
        else:
            print("❌ No configurations found")
            return False
            
        return True
    except Exception as e:
        print(f"❌ Error verifying configs: {e}")
        return False

def test_auto_assign():
    """Test the auto assign system with the new configurations"""
    print("\n🧪 Testing auto assign system...")
    
    try:
        from auto_assign_system import EnhancedAutoAssignTrigger
        
        trigger = EnhancedAutoAssignTrigger()
        
        # Test with META source
        result = trigger.trigger_manual_assignment('META')
        
        if result and 'assigned_count' in result:
            print(f"✅ Auto assign test successful: {result['assigned_count']} leads assigned")
            print(f"   Message: {result['message']}")
            return True
        else:
            print("⚠️ Auto assign test completed but no result returned")
            return False
            
    except Exception as e:
        print(f"❌ Error testing auto assign: {e}")
        return False

def main():
    """Main function"""
    print("🚀 Setting up Auto Assign Configuration")
    print("=" * 50)
    
    # Step 1: Clear existing configs
    if not clear_existing_configs():
        print("❌ Failed to clear existing configs")
        return
    
    # Step 2: Create new configs
    if not create_auto_assign_configs():
        print("❌ Failed to create configurations")
        return
    
    # Step 3: Verify configs
    if not verify_configurations():
        print("❌ Failed to verify configurations")
        return
    
    # Step 4: Test auto assign
    if not test_auto_assign():
        print("❌ Auto assign test failed")
        return
    
    print("\n🎉 Auto assign configuration setup completed successfully!")
    print("\n📋 Next steps:")
    print("   1. The system will now automatically assign leads based on the configurations")
    print("   2. All assignments will be logged to auto_assign_history table")
    print("   3. You can monitor assignments in the admin dashboard")
    print("   4. Run 'python test_auto_assign.py' to verify everything is working")

if __name__ == "__main__":
    main() 