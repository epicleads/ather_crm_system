# Receptionist Role Setup Guide

This guide provides step-by-step instructions to set up the new Receptionist role in the Ather CRM system.

## Overview

The Receptionist role has been added to provide a new user type with similar functionality to PS (Product Specialist) users. Receptionists can:
- Log in to the CRM system
- View branch-specific statistics
- Access a dedicated dashboard
- Be managed by administrators

## Database Setup

### Step 1: Create Database Table

Run the following SQL queries in your Supabase SQL editor:

```sql
-- Create receptionist_users table
CREATE TABLE IF NOT EXISTS receptionist_users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255), -- For backward compatibility during migration
    password_hash VARCHAR(255),
    salt VARCHAR(255),
    phone VARCHAR(20),
    email VARCHAR(255),
    branch VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    role VARCHAR(50) DEFAULT 'receptionist',
    failed_login_attempts INTEGER DEFAULT 0,
    account_locked_until TIMESTAMP,
    last_login TIMESTAMP,
    password_changed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_receptionist_users_username ON receptionist_users(username);
CREATE INDEX IF NOT EXISTS idx_receptionist_users_branch ON receptionist_users(branch);
CREATE INDEX IF NOT EXISTS idx_receptionist_users_active ON receptionist_users(is_active);

-- Add RLS (Row Level Security) policies
ALTER TABLE receptionist_users ENABLE ROW LEVEL SECURITY;

-- Policy for admins to manage all receptionists
CREATE POLICY "Admins can manage all receptionists" ON receptionist_users
    FOR ALL USING (auth.role() = 'authenticated');

-- Policy for receptionists to view their own data
CREATE POLICY "Receptionists can view own data" ON receptionist_users
    FOR SELECT USING (auth.uid()::text = id::text);

-- Create trigger for updated_at timestamp
CREATE OR REPLACE FUNCTION update_receptionist_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_receptionist_users_updated_at
    BEFORE UPDATE ON receptionist_users
    FOR EACH ROW
    EXECUTE FUNCTION update_receptionist_users_updated_at();
```

### Step 2: Verify Table Creation

Run this query to verify the table was created correctly:

```sql
SELECT 
    table_name, 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'receptionist_users' 
ORDER BY ordinal_position;
```

## Code Changes Applied

### 1. Authentication System Updates

- **app.py**: Added receptionist to valid user types in unified_login
- **auth.py**: Added receptionist session handling and decorator
- **templates/index.html**: Added receptionist option to login dropdown

### 2. Admin Management Features

- **app.py**: Added routes for managing receptionists:
  - `/add_receptionist` - Add new receptionist
  - `/manage_receptionist` - View all receptionists
  - `/toggle_receptionist_status/<id>` - Activate/deactivate receptionist
  - `/delete_receptionist/<id>` - Delete receptionist
- **templates/admin_dashboard.html**: Added receptionist management link and stats
- **templates/add_receptionist.html**: Form to add new receptionist
- **templates/manage_receptionist.html**: Interface to manage receptionists

### 3. Receptionist Dashboard

- **app.py**: Added `/receptionist_dashboard` route
- **templates/receptionist_dashboard.html**: Dashboard for receptionist users
- **templates/receptionist_login.html**: Dedicated login page

### 4. Security Updates

- **security_verification.py**: Updated to include receptionist_users table
- Username availability checking extended to support receptionist type

## Configuration Steps

### Step 1: Database Setup
1. Open your Supabase dashboard
2. Go to the SQL Editor
3. Run the database setup queries from the "Database Setup" section above
4. Verify the table was created successfully

### Step 2: Deploy Code Changes
1. Upload all the modified files to your server
2. Restart your Flask application
3. Clear any cached sessions if necessary

### Step 3: Test the Implementation
1. **Test Admin Features:**
   - Log in as admin
   - Navigate to "Manage Receptionist" in the sidebar
   - Try adding a new receptionist
   - Test the status toggle functionality
   - Verify the receptionist count appears in admin dashboard stats

2. **Test Receptionist Login:**
   - Go to the main login page
   - Select "Receptionist" from the role dropdown
   - Log in with a receptionist account
   - Verify the receptionist dashboard loads correctly

### Step 4: Create Sample Receptionist (Optional)

You can create a sample receptionist for testing:

```sql
INSERT INTO receptionist_users (name, username, password, phone, email, branch, role) 
VALUES ('Sample Receptionist', 'receptionist1', 'password123', '+91-9876543210', 'receptionist1@ather.com', 'SOMAJIGUDA', 'receptionist');
```

## Features Available

### For Administrators:
- ✅ Add new receptionist users
- ✅ View all receptionist users
- ✅ Activate/deactivate receptionist accounts
- ✅ Delete receptionist users
- ✅ View receptionist count in admin dashboard
- ✅ Manage receptionist branches

### For Receptionists:
- ✅ Login to the CRM system
- ✅ Access dedicated receptionist dashboard
- ✅ View branch-specific statistics
- ✅ See total leads, today's leads, and unassigned leads
- ✅ Quick action buttons (placeholder for future features)

## Security Features

- ✅ Password hashing with bcrypt
- ✅ Account lockout after failed attempts
- ✅ Session management
- ✅ Role-based access control
- ✅ Audit logging for all actions
- ✅ Row Level Security (RLS) policies

## Future Enhancements

The receptionist role is set up with a foundation that can be extended with:

1. **Lead Management**: Allow receptionists to add/edit leads
2. **Call Logging**: Track customer interactions
3. **Appointment Scheduling**: Manage customer appointments
4. **Reporting**: Generate branch-specific reports
5. **Customer Communication**: Send notifications to customers

## Troubleshooting

### Common Issues:

1. **"Table receptionist_users does not exist"**
   - Solution: Run the database setup queries in Supabase SQL editor

2. **"Invalid user type" error during login**
   - Solution: Ensure the code changes have been deployed and the application restarted

3. **Receptionist count not showing in admin dashboard**
   - Solution: Check that the `receptionist_count` variable is being passed to the template

4. **Permission denied errors**
   - Solution: Verify RLS policies are correctly set up in Supabase

### Verification Commands:

Check if the table exists:
```sql
SELECT EXISTS (
   SELECT FROM information_schema.tables 
   WHERE table_schema = 'public' 
   AND table_name = 'receptionist_users'
);
```

Check receptionist users:
```sql
SELECT id, name, username, branch, is_active FROM receptionist_users;
```

## Support

If you encounter any issues during setup, please:
1. Check the application logs for error messages
2. Verify all database queries executed successfully
3. Ensure all code files have been updated
4. Test with a fresh browser session

The receptionist role is now fully integrated into the Ather CRM system and ready for use! 