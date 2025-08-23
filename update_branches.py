#!/usr/bin/env python3
"""
Script to update all hardcoded branch lists in app.py to use get_system_branches()
"""

import re

def update_branches_in_file(file_path):
    """Update all hardcoded branch lists to use get_system_branches()"""
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Pattern to match hardcoded branch lists
    # This will match the common pattern: branches = ['SOMAJIGUDA', 'ATTAPUR', ...]
    pattern = r"branches\s*=\s*\[['\"][^'\"]+['\"](?:\s*,\s*['\"][^'\"]+['\"])*\s*\]"
    
    # Replacement string
    replacement = "branches = get_system_branches()"
    
    # Count matches
    matches = re.findall(pattern, content)
    print(f"Found {len(matches)} hardcoded branch lists to update:")
    
    for i, match in enumerate(matches, 1):
        print(f"  {i}. {match.strip()}")
    
    # Perform the replacement
    updated_content = re.sub(pattern, replacement, content)
    
    # Check if any changes were made
    if updated_content != content:
        # Backup the original file
        backup_path = file_path + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as backup_file:
            backup_file.write(content)
        print(f"\n✅ Backup created: {backup_path}")
        
        # Write the updated content
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(updated_content)
        print(f"✅ Updated {file_path}")
        print(f"✅ Replaced {len(matches)} hardcoded branch lists with get_system_branches()")
    else:
        print("\n❌ No changes were made. Check if the pattern matches your file.")
    
    return len(matches)

def main():
    """Main function"""
    file_path = 'app.py'
    
    print("🔄 TEST Branch Implementation - Branch List Updater")
    print("=" * 60)
    
    try:
        count = update_branches_in_file(file_path)
        
        if count > 0:
            print("\n🎉 Successfully updated all hardcoded branch lists!")
            print("\n📋 Next steps:")
            print("1. Restart your Flask application")
            print("2. Go to 'Add PS' page - TEST should appear in branch dropdown")
            print("3. Go to 'Add Lead' page - TEST should appear in branch dropdown")
            print("4. Test creating users and leads with TEST branch")
            print("5. Verify data separation works correctly")
        else:
            print("\n⚠️  No hardcoded branch lists found to update.")
            print("   The file may already be updated or the pattern doesn't match.")
            
    except FileNotFoundError:
        print(f"❌ Error: File '{file_path}' not found!")
        print("   Make sure you're running this script from the correct directory.")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    main()
