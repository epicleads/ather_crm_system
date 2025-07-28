-- Database Setup for Receptionist Role
-- Run these queries in your Supabase SQL editor

-- 1. Create receptionist_users table
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

-- 2. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_receptionist_users_username ON receptionist_users(username);
CREATE INDEX IF NOT EXISTS idx_receptionist_users_branch ON receptionist_users(branch);
CREATE INDEX IF NOT EXISTS idx_receptionist_users_active ON receptionist_users(is_active);

-- 3. Add RLS (Row Level Security) policies
ALTER TABLE receptionist_users ENABLE ROW LEVEL SECURITY;

-- Policy for admins to manage all receptionists
CREATE POLICY "Admins can manage all receptionists" ON receptionist_users
    FOR ALL USING (auth.role() = 'authenticated');

-- Policy for receptionists to view their own data
CREATE POLICY "Receptionists can view own data" ON receptionist_users
    FOR SELECT USING (auth.uid()::text = id::text);

-- 4. Create trigger for updated_at timestamp
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

-- 5. Insert sample receptionist (optional - for testing)
-- INSERT INTO receptionist_users (name, username, password, phone, email, branch, role) 
-- VALUES ('Sample Receptionist', 'receptionist1', 'password123', '+91-9876543210', 'receptionist1@ather.com', 'SOMAJIGUDA', 'receptionist');

-- 6. Verify table creation
SELECT 
    table_name, 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'receptionist_users' 
ORDER BY ordinal_position; 