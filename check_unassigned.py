#!/usr/bin/env python3
"""Check for unassigned leads and test auto assign"""

from auto_assign_system import supabase

# Check for unassigned leads
result = supabase.table('lead_master').select('uid, source, assigned, cre_name').eq('assigned', 'No').limit(10).execute()

if result.data:
    print(f"Found {len(result.data)} unassigned leads:")
    for lead in result.data:
        print(f"  {lead['uid']} ({lead['source']})")
    
    # Test auto assign for first source
    first_source = result.data[0]['source']
    print(f"\nTesting auto assign for source: {first_source}")
    
    from auto_assign_system import EnhancedAutoAssignTrigger
    trigger = EnhancedAutoAssignTrigger()
    
    # Trigger assignment
    assignment_result = trigger.trigger_manual_assignment(first_source)
    print(f"Assignment result: {assignment_result}")
    
else:
    print("No unassigned leads found") 