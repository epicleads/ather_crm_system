-- Database Optimization Script for Ather CRM
-- This script adds indexes to improve query performance
-- Only creates indexes for existing tables

-- Indexes for lead_master table (main table - should exist)
CREATE INDEX IF NOT EXISTS idx_lead_master_customer_mobile_number ON lead_master(customer_mobile_number);
CREATE INDEX IF NOT EXISTS idx_lead_master_cre_name ON lead_master(cre_name);
CREATE INDEX IF NOT EXISTS idx_lead_master_ps_name ON lead_master(ps_name);
CREATE INDEX IF NOT EXISTS idx_lead_master_source ON lead_master(source);
CREATE INDEX IF NOT EXISTS idx_lead_master_sub_source ON lead_master(sub_source);
CREATE INDEX IF NOT EXISTS idx_lead_master_lead_status ON lead_master(lead_status);
CREATE INDEX IF NOT EXISTS idx_lead_master_final_status ON lead_master(final_status);
CREATE INDEX IF NOT EXISTS idx_lead_master_created_at ON lead_master(created_at);
CREATE INDEX IF NOT EXISTS idx_lead_master_updated_at ON lead_master(updated_at);
CREATE INDEX IF NOT EXISTS idx_lead_master_uid ON lead_master(uid);
CREATE INDEX IF NOT EXISTS idx_lead_master_branch ON lead_master(branch);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_lead_master_cre_status ON lead_master(cre_name, lead_status);
CREATE INDEX IF NOT EXISTS idx_lead_master_ps_status ON lead_master(ps_name, final_status);
CREATE INDEX IF NOT EXISTS idx_lead_master_source_date ON lead_master(source, created_at);
CREATE INDEX IF NOT EXISTS idx_lead_master_phone_source ON lead_master(customer_mobile_number, source, sub_source);

-- Indexes for duplicate_leads table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'duplicate_leads') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_duplicate_leads_customer_mobile_number ON duplicate_leads(customer_mobile_number)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_duplicate_leads_uid ON duplicate_leads(uid)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_duplicate_leads_created_at ON duplicate_leads(created_at)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_duplicate_leads_updated_at ON duplicate_leads(updated_at)';
    END IF;
END $$;

-- Indexes for ps_followup_master table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ps_followup_master') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_followup_lead_uid ON ps_followup_master(lead_uid)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_followup_ps_name ON ps_followup_master(ps_name)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_followup_final_status ON ps_followup_master(final_status)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_followup_lead_status ON ps_followup_master(lead_status)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_followup_created_at ON ps_followup_master(created_at)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_followup_updated_at ON ps_followup_master(updated_at)';
        
        -- Composite indexes for ps_followup
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_followup_ps_status ON ps_followup_master(ps_name, final_status)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_followup_uid_status ON ps_followup_master(lead_uid, lead_status)';
    END IF;
END $$;

-- Indexes for call attempt tables (if they exist)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cre_call_attempts') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_cre_call_attempts_lead_uid ON cre_call_attempts(lead_uid)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_cre_call_attempts_cre_name ON cre_call_attempts(cre_name)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_cre_call_attempts_created_at ON cre_call_attempts(created_at)';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ps_call_attempts') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_call_attempts_lead_uid ON ps_call_attempts(lead_uid)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_call_attempts_ps_name ON ps_call_attempts(ps_name)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_call_attempts_created_at ON ps_call_attempts(created_at)';
    END IF;
END $$;

-- Indexes for user tables (if they exist)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cre_users') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_cre_users_username ON cre_users(username)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_cre_users_name ON cre_users(name)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_cre_users_is_active ON cre_users(is_active)';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ps_users') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_users_username ON ps_users(username)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_users_name ON ps_users(name)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_users_branch ON ps_users(branch)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ps_users_is_active ON ps_users(is_active)';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'admin_users') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_admin_users_username ON admin_users(username)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_admin_users_is_active ON admin_users(is_active)';
    END IF;
END $$;

-- Indexes for activity tables (if they exist)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'activity_leads') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_activity_leads_activity_uid ON activity_leads(activity_uid)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_activity_leads_ps_name ON activity_leads(ps_name)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_activity_leads_customer_phone_number ON activity_leads(customer_phone_number)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_activity_leads_created_at ON activity_leads(created_at)';
    END IF;
END $$;

-- Indexes for walkin_leads table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'walkin_leads') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_walkin_leads_customer_phone_number ON walkin_leads(customer_phone_number)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_walkin_leads_rec_name ON walkin_leads(rec_name)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_walkin_leads_created_at ON walkin_leads(created_at)';
    END IF;
END $$;

-- Indexes for audit_log table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'audit_log') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_audit_log_lead_uid ON audit_log(lead_uid)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_audit_log_user_name ON audit_log(user_name)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)';
    END IF;
END $$;

-- Performance optimization: Analyze tables to update statistics (only for existing tables)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'lead_master') THEN
        EXECUTE 'ANALYZE lead_master';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'duplicate_leads') THEN
        EXECUTE 'ANALYZE duplicate_leads';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ps_followup_master') THEN
        EXECUTE 'ANALYZE ps_followup_master';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cre_call_attempts') THEN
        EXECUTE 'ANALYZE cre_call_attempts';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ps_call_attempts') THEN
        EXECUTE 'ANALYZE ps_call_attempts';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cre_users') THEN
        EXECUTE 'ANALYZE cre_users';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ps_users') THEN
        EXECUTE 'ANALYZE ps_users';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'admin_users') THEN
        EXECUTE 'ANALYZE admin_users';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'activity_leads') THEN
        EXECUTE 'ANALYZE activity_leads';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'walkin_leads') THEN
        EXECUTE 'ANALYZE walkin_leads';
    END IF;
END $$;

-- Create a function to clean up old audit logs (only if audit_log table exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'audit_log') THEN
        EXECUTE '
        CREATE OR REPLACE FUNCTION cleanup_old_audit_logs()
        RETURNS void AS $func$
        BEGIN
            DELETE FROM audit_log WHERE timestamp < NOW() - INTERVAL ''90 days'';
        END;
        $func$ LANGUAGE plpgsql;
        ';
    END IF;
END $$;

-- Create a function to get lead statistics efficiently
CREATE OR REPLACE FUNCTION get_lead_stats(cre_name_param TEXT DEFAULT NULL, ps_name_param TEXT DEFAULT NULL)
RETURNS TABLE(
    total_leads BIGINT,
    pending_leads BIGINT,
    won_leads BIGINT,
    lost_leads BIGINT,
    avg_processing_time NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_leads,
        COUNT(CASE WHEN final_status = 'Pending' THEN 1 END) as pending_leads,
        COUNT(CASE WHEN final_status = 'Won' THEN 1 END) as won_leads,
        COUNT(CASE WHEN final_status = 'Lost' THEN 1 END) as lost_leads,
        AVG(EXTRACT(EPOCH FROM (updated_at::timestamp - created_at::timestamp))/3600) as avg_processing_time
    FROM lead_master
    WHERE (cre_name_param IS NULL OR cre_name = cre_name_param)
      AND (ps_name_param IS NULL OR ps_name = ps_name_param);
END;
$$ LANGUAGE plpgsql;
