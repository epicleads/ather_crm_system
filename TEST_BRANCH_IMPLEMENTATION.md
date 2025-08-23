# TEST Branch Implementation Guide

## **Overview**

You want to create a TEST branch (like SOMAJIGUDA, KOMPALLY) so you can have a separate branch for development and testing purposes. This is an excellent idea for maintaining data separation between production and testing environments.

## **Current Status**

✅ **Branch Management Functions Added**: Centralized branch management functions have been added to `app.py`
✅ **TEST Branch Added**: 'TEST' has been added to the system branches list
✅ **Display Names**: Branch display names are properly configured

## **What Has Been Implemented**

### **1. Centralized Branch Management Functions**

```python
def get_system_branches():
    """Centralized function to get all system branches"""
    return [
        'SOMAJIGUDA', 
        'ATTAPUR', 
        'BEGUMPET', 
        'KOMPALLY', 
        'MALAKPET', 
        'SRINAGAR COLONY', 
        'TOLICHOWKI',
        'VANASTHALIPURAM',
        'TEST'  # New TEST branch for development/testing
    ]

def get_branch_display_name(branch_code):
    """Get display name for branch codes"""
    branch_names = {
        'SOMAJIGUDA': 'Somajiguda',
        'ATTAPUR': 'Attapur',
        'BEGUMPET': 'Begumpet',
        'KOMPALLY': 'Kompally',
        'MALAKPET': 'Malakpet',
        'SRINAGAR COLONY': 'Srinagar Colony',
        'TOLICHOWKI': 'Tolichowki',
        'VANASTHALIPURAM': 'Vanasthalipuram',
        'TEST': 'TEST Branch'
    }
    return branch_names.get(branch_code, branch_code)
```

## **What Still Needs to Be Done**

### **1. Update All Hardcoded Branch Lists**

The following functions still have hardcoded branch lists that need to be updated:

- `add_ps()` function (lines ~1551, ~5066)
- `add_lead()` function (line ~2698)
- Other functions with hardcoded branches

### **2. Manual Updates Required**

You need to manually update these locations in `app.py`:

```python
# Replace this:
branches = ['SOMAJIGUDA', 'ATTAPUR', 'BEGUMPET', 'KOMPALLY', 'MALAKPET', 'SRINAGAR COLONY', 'TOLICHOWKI', 'VANASTHALIPURAM']

# With this:
branches = get_system_branches()
```

## **Step-by-Step Implementation**

### **Step 1: Update add_ps Function**

Find the `add_ps` function around line 1551 and update:

```python
@app.route('/add_ps', methods=['GET', 'POST'])
@require_admin
def add_ps():
    branches = get_system_branches()  # Updated to use centralized function
```

### **Step 2: Update add_lead Function**

Find the `add_lead` function around line 2698 and update:

```python
@app.route('/add_lead', methods=['GET', 'POST'])
@require_cre
def add_lead():
    branches = get_system_branches()  # Updated to use centralized function
```

### **Step 3: Update Other Functions**

Search for all occurrences of hardcoded branch lists and replace them with `get_system_branches()`.

## **Benefits of TEST Branch**

### **1. Data Separation**
- **Production Data**: Real leads, customers, and business data
- **Test Data**: Dummy leads, test scenarios, development data

### **2. Development Safety**
- Test new features without affecting production data
- Safe environment for developers and QA testing
- No risk of accidentally modifying real customer data

### **3. Training and Demo**
- Perfect for training new staff
- Demo environment for stakeholders
- Safe environment for learning system features

## **How to Use TEST Branch**

### **1. Creating Test Users**
- Create PS users assigned to TEST branch
- Create CRE users (they don't have branches)
- Create test leads assigned to TEST branch

### **2. Testing Workflows**
- Test lead assignment processes
- Test PS follow-up workflows
- Test reporting and analytics
- Test new features and updates

### **3. Data Management**
- Test data can be easily identified by branch
- Can be cleaned up periodically without affecting production
- Safe environment for bulk operations testing

## **Database Considerations**

### **1. Branch Field Usage**
The TEST branch will be used in these tables:
- `ps_users.branch` - PS users assigned to TEST branch
- `lead_master.branch` - Leads assigned to TEST branch
- `ps_followup_master.ps_branch` - PS follow-up records for TEST branch
- `walkin_table.branch` - Walk-in leads for TEST branch
- `activity_leads.location` - Event leads for TEST branch

### **2. Data Isolation**
- All TEST branch data will be completely separate from production
- Reports can filter by branch to exclude test data
- Analytics can be run separately for TEST vs production

## **Testing the Implementation**

### **1. Verify Branch Appears**
- Go to "Add PS" page - TEST should appear in branch dropdown
- Go to "Add Lead" page - TEST should appear in branch dropdown
- Check all other forms that use branches

### **2. Create Test Data**
- Create a PS user assigned to TEST branch
- Create some test leads assigned to TEST branch
- Verify data appears correctly in dashboards

### **3. Verify Separation**
- Check that TEST branch data doesn't mix with production data
- Verify reports and analytics work correctly with branch filtering

## **Maintenance and Best Practices**

### **1. Regular Cleanup**
- Periodically clean up old test data
- Archive test data if needed for reference
- Keep TEST branch data minimal and focused

### **2. Naming Conventions**
- Use clear prefixes for test data (e.g., "TEST_", "DEMO_")
- Document test scenarios and data
- Maintain test data quality standards

### **3. Access Control**
- Consider restricting TEST branch access to developers/testers only
- Monitor TEST branch usage
- Ensure production users don't accidentally use TEST branch

## **Troubleshooting**

### **1. Branch Not Appearing**
- Check if `get_system_branches()` function is properly defined
- Verify function is being called in the right places
- Check for syntax errors in the function definition

### **2. Data Not Saving**
- Verify TEST branch is accepted by database constraints
- Check if branch field validation is working
- Ensure TEST branch is included in any branch validation logic

### **3. Reports Not Working**
- Verify branch filtering is working correctly
- Check if TEST branch data is being excluded/included as expected
- Test with both TEST and production branch data

## **Next Steps**

1. **Update all hardcoded branch lists** to use `get_system_branches()`
2. **Test the TEST branch** in all relevant forms and functions
3. **Create test data** to verify separation works correctly
4. **Document TEST branch usage** for your team
5. **Set up regular cleanup** procedures for test data

## **Summary**

The TEST branch implementation provides you with:
- ✅ **Safe testing environment** separate from production
- ✅ **Data isolation** for development and testing
- ✅ **Training environment** for new staff
- ✅ **Demo environment** for stakeholders
- ✅ **Centralized branch management** for future updates

Once you complete the manual updates to replace hardcoded branch lists, your TEST branch will be fully functional and ready for use!
