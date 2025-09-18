-- Supabase RPC Functions for Ultra-Fast CRM Operations
-- Execute these functions in your Supabase SQL Editor

-- ==========================================
-- 1. OPTIMIZED CRE DASHBOARD RPC
-- ==========================================

CREATE OR REPLACE FUNCTION get_cre_dashboard_optimized(
    p_cre_name TEXT,
    p_final_status TEXT DEFAULT NULL,
    p_lead_status TEXT DEFAULT NULL,
    p_date_from TIMESTAMP DEFAULT NULL,
    p_date_to TIMESTAMP DEFAULT NULL,
    p_source TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 1000
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSON;
    leads_data JSON;
    stats_data JSON;
    total_count INTEGER;
    won_count INTEGER;
    lost_count INTEGER;
    pending_count INTEGER;
    follow_up_count INTEGER;
BEGIN
    -- Build dynamic query for leads
    WITH filtered_leads AS (
        SELECT
            uid,
            customer_name,
            customer_mobile_number,
            source,
            sub_source,
            lead_status,
            final_status,
            follow_up_date,
            created_at,
            updated_at,
            first_call_date,
            first_remark,
            model_interested,
            lead_category,
            branch
        FROM lead_master
        WHERE cre_name = p_cre_name
            AND (p_final_status IS NULL OR p_final_status = 'All' OR final_status = p_final_status)
            AND (p_lead_status IS NULL OR p_lead_status = 'All' OR lead_status = p_lead_status)
            AND (p_date_from IS NULL OR created_at >= p_date_from)
            AND (p_date_to IS NULL OR created_at <= p_date_to)
            AND (p_source IS NULL OR p_source = 'All' OR source = p_source)
        ORDER BY created_at DESC
        LIMIT p_limit
    ),
    lead_stats AS (
        SELECT
            COUNT(*) as total_leads,
            COUNT(*) FILTER (WHERE final_status = 'Won') as won_leads,
            COUNT(*) FILTER (WHERE final_status = 'Lost') as lost_leads,
            COUNT(*) FILTER (WHERE final_status = 'Pending') as pending_leads,
            COUNT(*) FILTER (WHERE lead_status = 'Follow-up') as follow_up_leads
        FROM filtered_leads
    )
    SELECT
        json_build_object(
            'leads', COALESCE(json_agg(to_json(filtered_leads.*)), '[]'::json),
            'stats', json_build_object(
                'total_count', ls.total_leads,
                'won_count', ls.won_leads,
                'lost_count', ls.lost_leads,
                'pending_count', ls.pending_leads,
                'follow_up_count', ls.follow_up_leads,
                'conversion_rate', CASE
                    WHEN ls.total_leads > 0 THEN ROUND((ls.won_leads::DECIMAL / ls.total_leads * 100), 2)
                    ELSE 0
                END
            ),
            'execution_time', extract(epoch from now()),
            'user_type', 'cre',
            'user_name', p_cre_name
        )
    INTO result
    FROM filtered_leads
    CROSS JOIN lead_stats ls;

    RETURN result;
END;
$$;

-- ==========================================
-- 2. OPTIMIZED PS DASHBOARD RPC
-- ==========================================

CREATE OR REPLACE FUNCTION get_ps_dashboard_optimized(
    p_ps_name TEXT,
    p_final_status TEXT DEFAULT NULL,
    p_lead_status TEXT DEFAULT NULL,
    p_date_from TIMESTAMP DEFAULT NULL,
    p_date_to TIMESTAMP DEFAULT NULL,
    p_limit INTEGER DEFAULT 1000
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSON;
BEGIN
    WITH filtered_ps_leads AS (
        SELECT
            lead_uid,
            customer_name,
            customer_mobile_number,
            source,
            lead_status,
            final_status,
            follow_up_date,
            created_at,
            updated_at,
            ps_branch,
            first_call_date,
            first_call_remark,
            second_call_date,
            second_call_remark,
            third_call_date,
            third_call_remark
        FROM ps_followup_master
        WHERE ps_name = p_ps_name
            AND (p_final_status IS NULL OR p_final_status = 'All' OR final_status = p_final_status)
            AND (p_lead_status IS NULL OR p_lead_status = 'All' OR lead_status = p_lead_status)
            AND (p_date_from IS NULL OR created_at >= p_date_from)
            AND (p_date_to IS NULL OR created_at <= p_date_to)
        ORDER BY created_at DESC
        LIMIT p_limit
    ),
    ps_stats AS (
        SELECT
            COUNT(*) as total_leads,
            COUNT(*) FILTER (WHERE final_status = 'Won') as won_leads,
            COUNT(*) FILTER (WHERE final_status = 'Lost') as lost_leads,
            COUNT(*) FILTER (WHERE final_status = 'Pending') as pending_leads,
            COUNT(*) FILTER (WHERE lead_status = 'Follow-up') as follow_up_leads
        FROM filtered_ps_leads
    )
    SELECT
        json_build_object(
            'leads', COALESCE(json_agg(to_json(filtered_ps_leads.*)), '[]'::json),
            'stats', json_build_object(
                'total_count', ps.total_leads,
                'won_count', ps.won_leads,
                'lost_count', ps.lost_leads,
                'pending_count', ps.pending_leads,
                'follow_up_count', ps.follow_up_leads,
                'conversion_rate', CASE
                    WHEN ps.total_leads > 0 THEN ROUND((ps.won_leads::DECIMAL / ps.total_leads * 100), 2)
                    ELSE 0
                END
            ),
            'execution_time', extract(epoch from now()),
            'user_type', 'ps',
            'user_name', p_ps_name
        )
    INTO result
    FROM filtered_ps_leads
    CROSS JOIN ps_stats ps;

    RETURN result;
END;
$$;

-- ==========================================
-- 3. ULTRA-FAST DUPLICATE CHECK RPC
-- ==========================================

CREATE OR REPLACE FUNCTION check_duplicates_batch(
    phone_numbers TEXT[]
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSON;
BEGIN
    WITH lead_master_dups AS (
        SELECT
            customer_mobile_number,
            uid,
            source,
            sub_source,
            created_at,
            'lead_master' as table_name
        FROM lead_master
        WHERE customer_mobile_number = ANY(phone_numbers)
    ),
    duplicate_leads_dups AS (
        SELECT
            customer_mobile_number,
            uid,
            unnest(ARRAY[source1, source2, source3, source4, source5, source6, source7, source8, source9, source10]) as source,
            unnest(ARRAY[sub_source1, sub_source2, sub_source3, sub_source4, sub_source5, sub_source6, sub_source7, sub_source8, sub_source9, sub_source10]) as sub_source,
            unnest(ARRAY[date1, date2, date3, date4, date5, date6, date7, date8, date9, date10]) as created_at,
            'duplicate_leads' as table_name
        FROM duplicate_leads
        WHERE customer_mobile_number = ANY(phone_numbers)
            AND (source1 IS NOT NULL OR source2 IS NOT NULL OR source3 IS NOT NULL)
    ),
    all_duplicates AS (
        SELECT * FROM lead_master_dups
        UNION ALL
        SELECT * FROM duplicate_leads_dups
        WHERE source IS NOT NULL
    )
    SELECT
        json_build_object(
            'duplicates', COALESCE(
                json_object_agg(
                    customer_mobile_number,
                    json_agg(
                        json_build_object(
                            'uid', uid,
                            'source', source,
                            'sub_source', sub_source,
                            'created_at', created_at,
                            'table_name', table_name
                        )
                    )
                ),
                '{}'::json
            ),
            'phones_checked', array_length(phone_numbers, 1),
            'duplicates_found', COUNT(DISTINCT customer_mobile_number),
            'execution_time', extract(epoch from now())
        )
    INTO result
    FROM all_duplicates;

    RETURN result;
END;
$$;

-- ==========================================
-- 4. OPTIMIZED TEST DRIVE OPERATIONS RPC
-- ==========================================

CREATE OR REPLACE FUNCTION update_test_drive_optimized(
    p_lead_uid TEXT,
    p_test_drive_date DATE,
    p_feedback TEXT,
    p_status TEXT DEFAULT 'Completed'
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSON;
    source_table_name TEXT;
    update_count INTEGER := 0;
    operations_log TEXT[] := '{}';
BEGIN
    -- Determine source table in single query
    WITH source_check AS (
        SELECT
            CASE
                WHEN EXISTS (SELECT 1 FROM activity_leads WHERE activity_uid = p_lead_uid) THEN 'activity_leads'
                WHEN EXISTS (SELECT 1 FROM ps_followup_master WHERE lead_uid = p_lead_uid) THEN 'ps_followup_master'
                WHEN EXISTS (SELECT 1 FROM lead_master WHERE uid = p_lead_uid) THEN 'lead_master'
                ELSE 'lead_master'
            END as table_name
    )
    SELECT table_name INTO source_table_name FROM source_check;

    -- Update or insert alltest_drive record
    INSERT INTO alltest_drive (
        source_table,
        original_id,
        test_drive_date,
        test_drive_feedback,
        test_drive_status,
        created_at,
        updated_at
    ) VALUES (
        source_table_name,
        p_lead_uid,
        p_test_drive_date,
        p_feedback,
        p_status,
        now(),
        now()
    )
    ON CONFLICT (source_table, original_id)
    DO UPDATE SET
        test_drive_date = EXCLUDED.test_drive_date,
        test_drive_feedback = EXCLUDED.test_drive_feedback,
        test_drive_status = EXCLUDED.test_drive_status,
        updated_at = now();

    GET DIAGNOSTICS update_count = ROW_COUNT;
    operations_log := operations_log || ('alltest_drive: ' || update_count::TEXT);

    -- Update source table based on determined table
    IF source_table_name = 'lead_master' THEN
        UPDATE lead_master
        SET test_drive_done = CASE WHEN p_status = 'Completed' THEN 'Yes' ELSE 'No' END,
            updated_at = now()
        WHERE uid = p_lead_uid;

        GET DIAGNOSTICS update_count = ROW_COUNT;
        operations_log := operations_log || ('lead_master: ' || update_count::TEXT);

    ELSIF source_table_name = 'ps_followup_master' THEN
        UPDATE ps_followup_master
        SET test_drive_done = CASE WHEN p_status = 'Completed' THEN 'Yes' ELSE 'No' END,
            updated_at = now()
        WHERE lead_uid = p_lead_uid;

        GET DIAGNOSTICS update_count = ROW_COUNT;
        operations_log := operations_log || ('ps_followup_master: ' || update_count::TEXT);

    ELSIF source_table_name = 'activity_leads' THEN
        UPDATE activity_leads
        SET test_drive_done = CASE WHEN p_status = 'Completed' THEN 'Yes' ELSE 'No' END,
            updated_at = now()
        WHERE activity_uid = p_lead_uid;

        GET DIAGNOSTICS update_count = ROW_COUNT;
        operations_log := operations_log || ('activity_leads: ' || update_count::TEXT);
    END IF;

    -- Return result
    SELECT json_build_object(
        'success', true,
        'source_table', source_table_name,
        'lead_uid', p_lead_uid,
        'test_drive_status', p_status,
        'operations_completed', operations_log,
        'execution_time', extract(epoch from now())
    ) INTO result;

    RETURN result;
END;
$$;

-- ==========================================
-- 5. BULK LEAD CREATION WITH DUPLICATE HANDLING
-- ==========================================

CREATE OR REPLACE FUNCTION create_leads_bulk_optimized(
    leads_data JSONB
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSON;
    lead_record JSONB;
    insert_count INTEGER := 0;
    duplicate_count INTEGER := 0;
    error_count INTEGER := 0;
    operations_log TEXT[] := '{}';
BEGIN
    -- Process each lead
    FOR lead_record IN SELECT * FROM jsonb_array_elements(leads_data)
    LOOP
        BEGIN
            -- Check for duplicates first
            IF EXISTS (
                SELECT 1 FROM lead_master
                WHERE customer_mobile_number = (lead_record->>'customer_mobile_number')
                AND source = (lead_record->>'source')
                AND sub_source = (lead_record->>'sub_source')
            ) THEN
                duplicate_count := duplicate_count + 1;
                operations_log := operations_log || ('Duplicate: ' || (lead_record->>'customer_mobile_number'));
            ELSE
                -- Insert new lead
                INSERT INTO lead_master (
                    uid, customer_name, customer_mobile_number, source, sub_source,
                    campaign, cre_name, lead_category, model_interested, branch,
                    ps_name, assigned, lead_status, follow_up_date, final_status,
                    created_at, updated_at, date
                ) VALUES (
                    lead_record->>'uid',
                    lead_record->>'customer_name',
                    lead_record->>'customer_mobile_number',
                    lead_record->>'source',
                    lead_record->>'sub_source',
                    lead_record->>'campaign',
                    lead_record->>'cre_name',
                    lead_record->>'lead_category',
                    lead_record->>'model_interested',
                    lead_record->>'branch',
                    lead_record->>'ps_name',
                    COALESCE(lead_record->>'assigned', 'No'),
                    COALESCE(lead_record->>'lead_status', 'Pending'),
                    (lead_record->>'follow_up_date')::TIMESTAMP,
                    COALESCE(lead_record->>'final_status', 'Pending'),
                    COALESCE((lead_record->>'created_at')::TIMESTAMP, now()),
                    COALESCE((lead_record->>'updated_at')::TIMESTAMP, now()),
                    COALESCE((lead_record->>'date')::DATE, CURRENT_DATE)
                );

                insert_count := insert_count + 1;
                operations_log := operations_log || ('Inserted: ' || (lead_record->>'uid'));
            END IF;
        EXCEPTION WHEN OTHERS THEN
            error_count := error_count + 1;
            operations_log := operations_log || ('Error: ' || (lead_record->>'customer_mobile_number') || ' - ' || SQLERRM);
        END;
    END LOOP;

    -- Return comprehensive result
    SELECT json_build_object(
        'success', true,
        'total_processed', jsonb_array_length(leads_data),
        'inserted', insert_count,
        'duplicates_skipped', duplicate_count,
        'errors', error_count,
        'operations_log', operations_log,
        'execution_time', extract(epoch from now())
    ) INTO result;

    RETURN result;
END;
$$;

-- ==========================================
-- 6. ANALYTICS DASHBOARD RPC
-- ==========================================

CREATE OR REPLACE FUNCTION get_analytics_optimized(
    p_date_from TIMESTAMP DEFAULT NULL,
    p_date_to TIMESTAMP DEFAULT NULL,
    p_cre_name TEXT DEFAULT NULL,
    p_ps_name TEXT DEFAULT NULL,
    p_branch TEXT DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSON;
BEGIN
    WITH filtered_data AS (
        SELECT
            uid, source, sub_source, final_status, lead_status,
            cre_name, ps_name, branch, created_at,
            won_timestamp, lost_timestamp
        FROM lead_master
        WHERE (p_date_from IS NULL OR created_at >= p_date_from)
            AND (p_date_to IS NULL OR created_at <= p_date_to)
            AND (p_cre_name IS NULL OR cre_name = p_cre_name)
            AND (p_ps_name IS NULL OR ps_name = p_ps_name)
            AND (p_branch IS NULL OR branch = p_branch)
    ),
    summary_stats AS (
        SELECT
            COUNT(*) as total_leads,
            COUNT(*) FILTER (WHERE final_status = 'Won') as won_leads,
            COUNT(*) FILTER (WHERE final_status = 'Lost') as lost_leads,
            COUNT(*) FILTER (WHERE final_status = 'Pending') as pending_leads,
            COUNT(DISTINCT source) as unique_sources,
            COUNT(DISTINCT cre_name) as unique_cres,
            COUNT(DISTINCT ps_name) as unique_ps
        FROM filtered_data
    ),
    source_breakdown AS (
        SELECT
            source,
            COUNT(*) as count,
            COUNT(*) FILTER (WHERE final_status = 'Won') as won_count
        FROM filtered_data
        GROUP BY source
    ),
    cre_performance AS (
        SELECT
            cre_name,
            COUNT(*) as total_leads,
            COUNT(*) FILTER (WHERE final_status = 'Won') as won_leads,
            ROUND(COUNT(*) FILTER (WHERE final_status = 'Won')::DECIMAL / COUNT(*) * 100, 2) as conversion_rate
        FROM filtered_data
        WHERE cre_name IS NOT NULL
        GROUP BY cre_name
        ORDER BY total_leads DESC
    ),
    daily_trends AS (
        SELECT
            DATE(created_at) as lead_date,
            COUNT(*) as daily_count,
            COUNT(*) FILTER (WHERE final_status = 'Won') as daily_won
        FROM filtered_data
        WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(created_at)
        ORDER BY lead_date DESC
        LIMIT 30
    )
    SELECT json_build_object(
        'summary', (
            SELECT json_build_object(
                'total_leads', total_leads,
                'won_leads', won_leads,
                'lost_leads', lost_leads,
                'pending_leads', pending_leads,
                'conversion_rate', CASE
                    WHEN total_leads > 0 THEN ROUND(won_leads::DECIMAL / total_leads * 100, 2)
                    ELSE 0
                END,
                'unique_sources', unique_sources,
                'unique_cres', unique_cres,
                'unique_ps', unique_ps
            ) FROM summary_stats
        ),
        'source_breakdown', COALESCE((
            SELECT json_agg(
                json_build_object(
                    'source', source,
                    'count', count,
                    'won_count', won_count,
                    'conversion_rate', CASE
                        WHEN count > 0 THEN ROUND(won_count::DECIMAL / count * 100, 2)
                        ELSE 0
                    END
                )
            ) FROM source_breakdown
        ), '[]'::json),
        'cre_performance', COALESCE((
            SELECT json_agg(
                json_build_object(
                    'cre_name', cre_name,
                    'total_leads', total_leads,
                    'won_leads', won_leads,
                    'conversion_rate', conversion_rate
                )
            ) FROM cre_performance
        ), '[]'::json),
        'daily_trends', COALESCE((
            SELECT json_agg(
                json_build_object(
                    'date', lead_date,
                    'total_leads', daily_count,
                    'won_leads', daily_won
                )
            ) FROM daily_trends
        ), '[]'::json),
        'execution_time', extract(epoch from now()),
        'filters_applied', json_build_object(
            'date_from', p_date_from,
            'date_to', p_date_to,
            'cre_name', p_cre_name,
            'ps_name', p_ps_name,
            'branch', p_branch
        )
    ) INTO result;

    RETURN result;
END;
$$;

-- ==========================================
-- 7. CREATE INDEXES FOR ULTRA-FAST PERFORMANCE
-- ==========================================

-- Indexes for lead_master table
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_master_cre_created
ON lead_master(cre_name, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_master_ps_created
ON lead_master(ps_name, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_master_phone_source
ON lead_master(customer_mobile_number, source, sub_source);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_master_status_filters
ON lead_master(final_status, lead_status, created_at);

-- Indexes for ps_followup_master table
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ps_followup_ps_created
ON ps_followup_master(ps_name, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ps_followup_lead_uid
ON ps_followup_master(lead_uid);

-- Indexes for duplicate_leads table
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_duplicate_leads_phone
ON duplicate_leads(customer_mobile_number);

-- Indexes for alltest_drive table
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alltest_drive_source_original
ON alltest_drive(source_table, original_id);

-- Composite indexes for common filter combinations
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_master_composite_filters
ON lead_master(cre_name, final_status, lead_status, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ps_followup_composite_filters
ON ps_followup_master(ps_name, final_status, lead_status, created_at DESC);

-- ==========================================
-- GRANT PERMISSIONS (Adjust as needed)
-- ==========================================

-- Grant execute permissions to authenticated users
GRANT EXECUTE ON FUNCTION get_cre_dashboard_optimized TO authenticated;
GRANT EXECUTE ON FUNCTION get_ps_dashboard_optimized TO authenticated;
GRANT EXECUTE ON FUNCTION check_duplicates_batch TO authenticated;
GRANT EXECUTE ON FUNCTION update_test_drive_optimized TO authenticated;
GRANT EXECUTE ON FUNCTION create_leads_bulk_optimized TO authenticated;
GRANT EXECUTE ON FUNCTION get_analytics_optimized TO authenticated;