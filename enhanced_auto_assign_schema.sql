-- Enhanced Auto-Assign System Schema
-- This script adds fair distribution tracking and history logging

-- 1. Add auto_assign_count column to cre_users table
ALTER TABLE cre_users 
ADD COLUMN IF NOT EXISTS auto_assign_count INTEGER DEFAULT 0;

-- 2. Create auto_assign_history table for tracking assignment details
CREATE TABLE IF NOT EXISTS auto_assign_history (
    id SERIAL PRIMARY KEY,
    lead_uid VARCHAR(255) NOT NULL,
    source VARCHAR(255) NOT NULL,
    assigned_cre_id INTEGER NOT NULL,
    assigned_cre_name VARCHAR(255) NOT NULL,
    cre_total_leads_before INTEGER NOT NULL,
    cre_total_leads_after INTEGER NOT NULL,
    assignment_method VARCHAR(50) NOT NULL DEFAULT 'fair_distribution', -- 'fair_distribution' or 'round_robin'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Kolkata'),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Kolkata')
);

-- 3. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_auto_assign_history_lead_uid ON auto_assign_history(lead_uid);
CREATE INDEX IF NOT EXISTS idx_auto_assign_history_source ON auto_assign_history(source);
CREATE INDEX IF NOT EXISTS idx_auto_assign_history_cre_id ON auto_assign_history(assigned_cre_id);
CREATE INDEX IF NOT EXISTS idx_auto_assign_history_created_at ON auto_assign_history(created_at);

-- 4. Add foreign key constraints
ALTER TABLE auto_assign_history 
ADD CONSTRAINT fk_auto_assign_history_cre_id 
FOREIGN KEY (assigned_cre_id) REFERENCES cre_users(id) ON DELETE CASCADE;

-- 5. Create a function to update auto_assign_count
CREATE OR REPLACE FUNCTION update_cre_auto_assign_count()
RETURNS TRIGGER AS $$
BEGIN
    -- Increment auto_assign_count for the assigned CRE
    UPDATE cre_users 
    SET auto_assign_count = auto_assign_count + 1
    WHERE id = NEW.assigned_cre_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 6. Create trigger to automatically update auto_assign_count
DROP TRIGGER IF EXISTS trigger_update_auto_assign_count ON auto_assign_history;
CREATE TRIGGER trigger_update_auto_assign_count
    AFTER INSERT ON auto_assign_history
    FOR EACH ROW
    EXECUTE FUNCTION update_cre_auto_assign_count();

-- 7. Create a view for easy querying of auto-assign statistics
CREATE OR REPLACE VIEW auto_assign_stats AS
SELECT 
    c.id as cre_id,
    c.name as cre_name,
    c.auto_assign_count,
    COUNT(h.id) as total_assignments,
    MAX(h.created_at) as last_assignment,
    COUNT(CASE WHEN h.created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as assignments_24h,
    COUNT(CASE WHEN h.created_at >= NOW() - INTERVAL '7 days' THEN 1 END) as assignments_7d
FROM cre_users c
LEFT JOIN auto_assign_history h ON c.id = h.assigned_cre_id
GROUP BY c.id, c.name, c.auto_assign_count
ORDER BY c.auto_assign_count ASC, c.name ASC;

-- 8. Create a function to get the fairest CRE for assignment
CREATE OR REPLACE FUNCTION get_fairest_cre_for_source(source_name VARCHAR)
RETURNS TABLE(cre_id INTEGER, cre_name VARCHAR, auto_assign_count INTEGER) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id,
        c.name,
        c.auto_assign_count
    FROM cre_users c
    INNER JOIN auto_assign_config ac ON c.id = ac.cre_id
    WHERE ac.source = source_name
    ORDER BY c.auto_assign_count ASC, c.id ASC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- 9. Create a function to log auto-assignment
CREATE OR REPLACE FUNCTION log_auto_assignment(
    p_lead_uid VARCHAR,
    p_source VARCHAR,
    p_cre_id INTEGER,
    p_cre_name VARCHAR,
    p_assignment_method VARCHAR DEFAULT 'fair_distribution'
)
RETURNS VOID AS $$
DECLARE
    v_total_before INTEGER;
    v_total_after INTEGER;
BEGIN
    -- Get current auto_assign_count for the CRE
    SELECT auto_assign_count INTO v_total_before
    FROM cre_users 
    WHERE id = p_cre_id;
    
    -- Calculate total after assignment
    v_total_after := v_total_before + 1;
    
    -- Insert into history table
    INSERT INTO auto_assign_history (
        lead_uid,
        source,
        assigned_cre_id,
        assigned_cre_name,
        cre_total_leads_before,
        cre_total_leads_after,
        assignment_method,
        created_at
    ) VALUES (
        p_lead_uid,
        p_source,
        p_cre_id,
        p_cre_name,
        v_total_before,
        v_total_after,
        p_assignment_method,
        NOW() AT TIME ZONE 'Asia/Kolkata'
    );
    
    -- Update cre_users auto_assign_count
    UPDATE cre_users 
    SET auto_assign_count = auto_assign_count + 1
    WHERE id = p_cre_id;
END;
$$ LANGUAGE plpgsql;

-- 10. Create a function to reset auto_assign_count (for testing or maintenance)
CREATE OR REPLACE FUNCTION reset_auto_assign_counts()
RETURNS VOID AS $$
BEGIN
    UPDATE cre_users SET auto_assign_count = 0;
    DELETE FROM auto_assign_history;
END;
$$ LANGUAGE plpgsql;

-- 11. Create a function to get auto-assign statistics for a specific source
CREATE OR REPLACE FUNCTION get_source_auto_assign_stats(source_name VARCHAR)
RETURNS TABLE(
    cre_id INTEGER,
    cre_name VARCHAR,
    auto_assign_count INTEGER,
    assignments_24h INTEGER,
    assignments_7d INTEGER,
    last_assignment TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id,
        c.name,
        c.auto_assign_count,
        COUNT(CASE WHEN h.created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as assignments_24h,
        COUNT(CASE WHEN h.created_at >= NOW() - INTERVAL '7 days' THEN 1 END) as assignments_7d,
        MAX(h.created_at) as last_assignment
    FROM cre_users c
    INNER JOIN auto_assign_config ac ON c.id = ac.cre_id
    LEFT JOIN auto_assign_history h ON c.id = h.assigned_cre_id AND h.source = source_name
    WHERE ac.source = source_name
    GROUP BY c.id, c.name, c.auto_assign_count
    ORDER BY c.auto_assign_count ASC, c.name ASC;
END;
$$ LANGUAGE plpgsql;

-- 12. Add comments for documentation
COMMENT ON TABLE auto_assign_history IS 'Tracks all auto-assignment activities with IST timestamps';
COMMENT ON COLUMN auto_assign_history.assignment_method IS 'Method used: fair_distribution or round_robin';
COMMENT ON COLUMN auto_assign_history.created_at IS 'IST timestamp (UTC+05:30)';
COMMENT ON COLUMN cre_users.auto_assign_count IS 'Total number of leads auto-assigned to this CRE';

-- 13. Create a view for recent auto-assignments
CREATE OR REPLACE VIEW recent_auto_assignments AS
SELECT 
    h.lead_uid,
    h.source,
    h.assigned_cre_name,
    h.assignment_method,
    h.created_at as assigned_at,
    EXTRACT(EPOCH FROM (NOW() - h.created_at))/3600 as hours_ago
FROM auto_assign_history h
ORDER BY h.created_at DESC;

-- 14. Create a function to get fair distribution statistics
CREATE OR REPLACE FUNCTION get_fair_distribution_stats()
RETURNS TABLE(
    source_name VARCHAR,
    total_cres INTEGER,
    min_assignments INTEGER,
    max_assignments INTEGER,
    avg_assignments NUMERIC,
    distribution_variance NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ac.source as source_name,
        COUNT(DISTINCT c.id) as total_cres,
        MIN(c.auto_assign_count) as min_assignments,
        MAX(c.auto_assign_count) as max_assignments,
        AVG(c.auto_assign_count) as avg_assignments,
        VARIANCE(c.auto_assign_count) as distribution_variance
    FROM auto_assign_config ac
    INNER JOIN cre_users c ON ac.cre_id = c.id
    GROUP BY ac.source
    ORDER BY ac.source;
END;
$$ LANGUAGE plpgsql; 